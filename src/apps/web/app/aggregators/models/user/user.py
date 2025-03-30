from __future__ import annotations

from typing import Self
from uuid import uuid4

from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


class User(Base):
    """Агрегатор пользователя."""

    uid: apps_types.UserUID = Field(
        description="Уникальный ID записи пользователя.",
    )
    name: apps_types.UserName = Field(
        description="Имя пользователя",
    )
    email: apps_types.Email | None = Field(
        description="Email пользователя",
    )

    @classmethod
    def create(
        cls,
        name: apps_types.UserName,
        email: apps_types.Email | None,
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
