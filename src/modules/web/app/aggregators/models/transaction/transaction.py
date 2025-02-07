from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import uuid4

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from datetime import datetime

    from modules import types


class Transaction(Base):
    """Агрегатор транзакции пользователя"""

    uid: types.TransactionUID = Field(
        description="Уникальный ID записи транзакции.",
    )
    user_uid: types.UserUID = Field(
        description="UID пользователя.",
    )
    transaction_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: types.CategoryName = Field(
        description="Категория транзакции.",
    )
    money_sum: types.MoneySum = Field(
        description="Сумма транзакции.",
    )
    transaction_type: types.TransactionType = Field(
        description="Тип транзакции.",
    )
    description: types.Description = Field(
        description="Описание транзакции.",
    )

    @classmethod
    def create(
        cls,
        user_uid: types.UserUID,
        transaction_date: datetime,
        category: types.CategoryName,
        money_sum: types.MoneySum,
        transaction_type: types.TransactionType,
        description: types.Description,
    ) -> Self:
        """
        Создать транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_date: Дата транзакции.
            money_sum: Денежная сумма по категории.
            transaction_type:Тип транзакции.
            category: Категория.
            description: Описание.
        """
        uid = uuid4()
        return cls(
            uid=uid,
            user_uid=user_uid,
            transaction_date=transaction_date,
            category=category,
            money_sum=money_sum,
            transaction_type=transaction_type,
            description=description,
        )
