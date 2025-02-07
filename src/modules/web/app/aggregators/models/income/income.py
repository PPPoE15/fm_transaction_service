from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import uuid4

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from datetime import datetime

    from modules import types


class Income(Base):
    """Агрегатор доходов пользователя"""

    uid: types.CategoryUID = Field(
        description="Уникальный ID записи транзакции.",
    )
    user_uid: types.UserUID = Field(
        description="UID пользователя.",
    )
    income_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: types.CategoryName = Field(
        description="Категория транзакции.",
    )
    money_sum: types.MoneySum = Field(
        description="Сумма транзакции.",
    )
    description: types.Description | None = Field(
        description="Описание транзакции.",
    )

    @classmethod
    def create(
        cls,
        user_uid: types.UserUID,
        money_sum: types.MoneySum,
        income_date: datetime,
        category: types.CategoryName,
        description: types.Description | None,
    ) -> Self:
        """
        Создать пользователя.

        Args:
            user_uid: UID пользователя.
            money_sum: Денежная сумма по категории.
            income_date: Дата транзакции.
            category: Категория.
            description: Описание.
        """
        uid = uuid4()
        return cls(
            uid=uid,
            user_uid=user_uid,
            money_sum=money_sum,
            income_date=income_date,
            category=category,
            description=description,
        )
