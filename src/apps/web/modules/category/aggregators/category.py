from __future__ import annotations

from typing import Self
from uuid import uuid4

from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


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
    money_plan: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип категории (доход или расход)",
    )
    description: apps_types.Description | None = Field(
        description="Описание категории.",
    )

    @classmethod
    def create(
        cls,
        name: apps_types.CategoryName,
        user_uid: apps_types.UserUID,
        money_plan: apps_types.MoneySum,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> Self:
        """
        Создать категорию.

        Args:
            name: Имя категории.
            user_uid: UID пользователя.
            money_plan: Денежная сумма по категории.
            category_type: Тип категории (доход или расход).
            description: Описание категории.
        """
        category_uid = uuid4()
        return cls(
            uid=category_uid,
            user_uid=user_uid,
            name=name,
            money_plan=money_plan,
            category_type=category_type,
            description=description,
        )

    def is_in_the_budget(self, money_sum: apps_types.MoneySum) -> bool:
        """
        Проверить укладывается ли сумма в бюджет.

        True - если сумма больше чем запланированный доход или меньше чем запланированный расход.

        Args:
            money_sum: Потраченная/полученная сумма.
        """
        if self.category_type == apps_types.TransactionType.INCOME:
            return money_sum > self.money_plan
        return money_sum < self.money_plan
