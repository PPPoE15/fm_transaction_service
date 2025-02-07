from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import uuid4

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from modules import types


class User(Base):
    """Агрегатор пользователя."""

    uid: types.UserUID = Field(
        description="Уникальный ID записи пользователя.",
    )
    name: types.UserName = Field(
        description="Имя пользователя",
    )
    email: types.Email | None = Field(
        description="Email пользователя",
    )

    @classmethod
    def create(
        cls,
        name: types.UserName,
        email: types.Email | None,
    ) -> Self:
        """
        Создать пользователя.

        Args:
            name: Имя пользователя.
            email: Email пользователя.
        """
        user_uid = uuid4()
        return cls(
            uid=user_uid,
            name=name,
            email=email,
        )
