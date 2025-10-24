from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import DecodeError
from pydantic import BaseModel, Field
from starlette import status
from starlette.exceptions import HTTPException

from apps import apps_types

_security_token = HTTPBearer(auto_error=False)


class UserInfo(BaseModel):
    """Информация о пользователе."""

    uid: apps_types.UserUID = Field(description="Идентификатор пользователя.", alias="sub")
    login: apps_types.UserName = Field(description="Логин пользователя.")


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
    Извлечь из токена информацию о пользователе.

    Args:
        token: JWT-токен пользователя.

    Raises:
        HTTPException: Если токен некорректный.
    """
    try:
        payload = jwt.decode(token.credentials, options={"verify_signature": False})
    except DecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен!",
        ) from None
    return UserInfo.model_validate(payload)
