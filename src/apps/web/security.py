from functools import cache
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from starlette import status
from starlette.exceptions import HTTPException

from apps import apps_types
from apps.web.config import app_settings

_security_token = HTTPBearer(auto_error=False)


class PublicKeyError(RuntimeError):
    """Публичный ключ проверки подписи JWT отсутствует или непригоден для настроенного алгоритма."""


class UserInfo(BaseModel):
    """Информация о пользователе."""

    uid: apps_types.UserUID = Field(description="Идентификатор пользователя.", alias="sub")


@cache
def _read_key(path: str) -> bytes:
    """
    Прочитать ключ из файла (с кэшированием по пути).

    Кэш намеренный: при старте validate_public_key проверяет именно эти байты, и дальше
    сервис работает только с ними. Ротация ключа требует перезапуска сервиса.

    Args:
        path: Путь к файлу ключа.

    Raises:
        PublicKeyError: Если файла нет.
    """
    # TODO(FM-9): PermissionError/IsADirectoryError (secret с чужими правами, путь на каталог) тоже
    # переводить в PublicKeyError — сейчас старт падает с сырым исключением без пояснения.
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        msg = f"Не найден файл ключа проверки подписи JWT: {path}"
        raise PublicKeyError(msg) from None


def load_public_key() -> bytes:
    """Загрузить публичный ключ проверки подписи JWT по пути из настроек."""
    return _read_key(app_settings.PUBLIC_KEY_PATH)


def validate_public_key() -> None:
    """
    Проверить, что файл ключа читается и содержит публичный ключ для настроенного алгоритма.

    Вызывается при старте приложения, чтобы ошибка конфигурации проявлялась сразу,
    а не ответом 401 на каждый запрос. Приватный ключ и симметричный секрет отклоняются:
    сервис транзакций только проверяет подпись и не должен уметь выпускать токены.

    Raises:
        PublicKeyError: Если ключ не найден, не в формате PEM, не подходит к алгоритму или не публичный.
    """
    algorithm_name = app_settings.TOKEN_SIGNING_ALGORITHM
    key_path = app_settings.PUBLIC_KEY_PATH
    try:
        algorithm = jwt.PyJWS().get_algorithm_by_name(algorithm_name)
        jwk = algorithm.to_jwk(algorithm.prepare_key(load_public_key()), as_dict=True)
    except (jwt.PyJWTError, NotImplementedError, TypeError, ValueError) as exc:
        msg = (
            f"Ключ проверки подписи JWT ({key_path}) непригоден для алгоритма {algorithm_name}: {exc}. "
            "Ожидается публичный ключ в формате PEM."
        )
        raise PublicKeyError(msg) from exc
    # Приватный ключ RSA/EC содержит параметр "d", симметричный секрет имеет kty "oct".
    if "d" in jwk or jwk.get("kty") == "oct":
        msg = f"В {key_path} должен лежать публичный ключ проверки подписи JWT, а не приватный ключ или секрет."
        raise PublicKeyError(msg)


async def _get_token(
    token: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_token)],
) -> HTTPAuthorizationCredentials:
    """
    Извлечь JWT-токен из запроса.

    Raises:
        HTTPException: Если токен не передан.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизованный запрос!",
        )
    return token


async def get_user_info(token: Annotated[HTTPAuthorizationCredentials, Depends(_get_token)]) -> UserInfo:
    """
    Извлечь из токена информацию о пользователе, проверив подпись и срок действия.

    Args:
        token: JWT-токен пользователя.

    Raises:
        HTTPException: Если подпись неверна, токен истёк или некорректен.
    """
    # TODO(FM-9): PEM разбирается на каждом запросе — кэшировать подготовленный ключ. load_public_key внутри
    # try ловится не здесь: без lifespan (тесты на ASGITransport) отсутствие ключа даёт 500, а не понятную ошибку.
    try:
        payload = jwt.decode(
            token.credentials,
            key=load_public_key(),
            algorithms=[app_settings.TOKEN_SIGNING_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return UserInfo.model_validate(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена истёк!",
        ) from None
    except (jwt.InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен!",
        ) from None
