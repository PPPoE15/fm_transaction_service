from __future__ import annotations

from typing import Self
from uuid import uuid4

from pydantic import Field

from apps.shared import apps_types
from apps.shared.schemas import Base

# Лимит статей на пользователя: таблица «Структура бюджета» отдаётся без пагинации (контракт, `FM-409103`).
MAX_CATEGORIES_PER_USER = 100


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
    money_plan: apps_types.MoneySum | None = Field(
        description="Плановая сумма за месяц; `None` — план не задан (не то же самое, что 0).",
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
        money_plan: apps_types.MoneySum | None,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> Self:
        """
        Создать категорию.

        Args:
            name: Имя категории.
            user_uid: UID пользователя.
            money_plan: Плановая сумма за месяц; `None` — план не задан.
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

    def update(
        self,
        name: apps_types.CategoryName,
        money_plan: apps_types.MoneySum | None,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> None:
        """
        Изменить статью (полная замена изменяемых полей).

        Args:
            name: Имя категории.
            money_plan: Денежная сумма по категории.
            category_type: Тип категории (доход или расход).
            description: Описание категории.
        """
        self.name = name
        self.money_plan = money_plan
        self.category_type = category_type
        self.description = description

    def belongs_to(self, user_uid: apps_types.UserUID) -> bool:
        """
        Проверить, что запись принадлежит пользователю.

        Args:
            user_uid: UID пользователя из токена.
        """
        return self.user_uid == user_uid

    def is_in_the_budget(self, money_sum: apps_types.MoneySum) -> bool:
        """
        Проверить укладывается ли сумма в бюджет.

        True - если сумма больше чем запланированный доход или меньше чем запланированный расход,
        а также если плана нет: выходить за него нечем.

        Args:
            money_sum: Потраченная/полученная сумма.
        """
        if self.money_plan is None:
            return True
        if self.category_type == apps_types.TransactionType.INCOME:
            return money_sum > self.money_plan
        return money_sum < self.money_plan
