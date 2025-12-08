from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import uuid4

from pydantic import Field

from apps.utils.schemas import Base

if TYPE_CHECKING:
    from apps import apps_types


class Category(Base):
    """Агрегатор категории."""

    uid: apps_types.CategoryUID = Field(
        description="Уникальный ID записи бюджета пользователя.",
    )
    user_uid: apps_types.UserUID = Field(
        description="UID пользователя.",
    )
    name: apps_types.CategoryName = Field(
        description="Категория.",
    )
    money_sum: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
    )
    # TODO: Добавить описание категорий.

    @classmethod
    def create(
        cls,
        name: apps_types.UserName,
        user_uid: apps_types.UserUID,
        money_sum: apps_types.MoneySum,
    ) -> Self:
        """
        Создать пользователя.

        Args:
            name: Имя пользователя.
            user_uid: UID пользователя.
            money_sum: Денежная сумма по категории.
        """
        category_uid = uuid4()
        return cls(
            uid=category_uid,
            user_uid=user_uid,
            name=name,
            money_sum=money_sum,
        )
