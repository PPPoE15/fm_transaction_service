from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import uuid4

from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


class Transaction(Base):
    """Агрегатор транзакции пользователя"""

    uid: apps_types.TransactionUID = Field(
        description="Уникальный ID записи транзакции.",
    )
    user_uid: apps_types.UserUID = Field(
        description="UID пользователя.",
    )
    transaction_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: apps_types.CategoryName = Field(
        description="Категория транзакции.",
    )
    money_sum: apps_types.MoneySum = Field(
        description="Сумма транзакции.",
    )
    transaction_type: apps_types.TransactionType = Field(
        description="Тип транзакции.",
    )
    description: apps_types.Description = Field(
        description="Описание транзакции.",
    )

    @classmethod
    def create(
        cls,
        user_uid: apps_types.UserUID,
        transaction_date: datetime,
        category: apps_types.CategoryName,
        money_sum: apps_types.MoneySum,
        transaction_type: apps_types.TransactionType,
        description: apps_types.Description,
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
