from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient, Response
from starlette import status
from starlette.exceptions import HTTPException

from apps.web import security
from apps.web.config import app_settings
from apps.web.main import LifespanEvent, app
from tests import FOREIGN_PRIVATE_KEY, PRIVATE_KEY, PUBLIC_KEY
from tests.conftest import TokenFactory

ENDPOINTS = [
    ("GET", "/transactions"),
    ("POST", "/transactions"),
    ("PATCH", "/transactions"),
    ("DELETE", "/transactions"),
    ("GET", "/categories"),
    ("POST", "/category"),
    ("PATCH", "/category"),
    ("DELETE", "/category"),
    ("GET", "/budget-structure"),
]

_HMAC_SECRET = "hmac-secret-long-enough-for-sha256"  # noqa: S105 — тестовый секрет для подмены алгоритма

BAD_TOKENS: dict[str, Callable[[TokenFactory], str]] = {
    "чужая подпись": lambda make_token: make_token(key=FOREIGN_PRIVATE_KEY),
    "истёк срок": lambda make_token: make_token(expires_in=timedelta(seconds=-1)),
    "нет exp": lambda make_token: make_token(drop_claims=("exp",)),
    "нет sub": lambda make_token: make_token(drop_claims=("sub",)),
    "sub не UUID": lambda make_token: make_token(user_uid="not-a-uuid"),
    "не JWT": lambda _: "definitely.not.jwt",
    "alg none": lambda make_token: make_token(key="", algorithm="none"),
    "HS256 вместо RS256": lambda make_token: make_token(key=_HMAC_SECRET, algorithm="HS256"),
}


def _assert_unauthorized(response: Response) -> None:
    """Ответ — 401 в формате RFC 7807."""
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    body = response.json()
    assert body["code"] == "FM-401000"
    assert body["status"] == status.HTTP_401_UNAUTHORIZED


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    """Заголовок Authorization в том виде, в каком его передаёт HTTPBearer."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_request_without_token_is_unauthorized(client: AsyncClient, method: str, path: str) -> None:
    """Запрос без токена к любому эндпоинту получает 401."""
    response = await client.request(method, path)

    _assert_unauthorized(response)


@pytest.mark.parametrize("bad_token", BAD_TOKENS.values(), ids=BAD_TOKENS.keys())
@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_request_with_invalid_token_is_unauthorized(
    client: AsyncClient,
    make_token: TokenFactory,
    method: str,
    path: str,
    bad_token: Callable[[TokenFactory], str],
) -> None:
    """Невалидный, поддельный или просроченный токен на любом эндпоинте получает 401, а не доступ к данным."""
    response = await client.request(method, path, headers={"Authorization": f"Bearer {bad_token(make_token)}"})

    _assert_unauthorized(response)


async def test_valid_token_gives_user_info(make_token: TokenFactory) -> None:
    """Токен, подписанный ключом сервиса авторизации, даёт UID пользователя из claim `sub`."""
    user_uid = uuid4()

    user = await security.get_user_info(_credentials(make_token(user_uid)))

    assert user.uid == user_uid


async def test_expired_token_reports_expiration(make_token: TokenFactory) -> None:
    """Для просроченного токена в ответе указано, что истёк срок действия."""
    with pytest.raises(HTTPException) as exc_info:
        await security.get_user_info(_credentials(make_token(expires_in=timedelta(seconds=-1))))

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Срок действия токена истёк!"


@pytest.fixture
def public_key_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Путь к ключу проверки подписи, подменённый на временный файл (у каждого теста свой путь — кэш не мешает)."""
    path = tmp_path / "jwt_public_key"
    monkeypatch.setattr(app_settings, "PUBLIC_KEY_PATH", str(path))
    return path


def test_validate_public_key_accepts_rsa_public_key(public_key_path: Path) -> None:
    """Публичный ключ RSA в PEM проходит проверку."""
    public_key_path.write_bytes(PUBLIC_KEY)

    security.validate_public_key()


def test_validate_public_key_fails_when_file_is_missing(public_key_path: Path) -> None:
    """Отсутствующий файл ключа — понятная ошибка."""
    with pytest.raises(security.PublicKeyError, match="Не найден файл ключа"):
        security.validate_public_key()


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"not a pem key", id="не PEM"),
        pytest.param(PRIVATE_KEY, id="приватный ключ вместо публичного"),
    ],
)
def test_validate_public_key_rejects_unusable_key(public_key_path: Path, content: bytes) -> None:
    """Не-PEM и приватный ключ отклоняются: сервис транзакций только проверяет подпись."""
    public_key_path.write_bytes(content)

    with pytest.raises(security.PublicKeyError):
        security.validate_public_key()


async def test_app_startup_fails_without_public_key(public_key_path: Path) -> None:
    """Без ключа приложение падает на старте, а не отвечает 401 на каждый запрос."""
    with pytest.raises(security.PublicKeyError):
        async with LifespanEvent(app):
            pass
