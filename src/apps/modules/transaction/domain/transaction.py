from datetime import datetime
from typing import Self
from uuid import uuid4

from pydantic import Field

from apps.modules.transaction.domain.changes import TransactionChanges
from apps.shared import apps_types
from apps.shared.schemas import Base

# Лимит транзакций на пользователя (контракт, «Объёмы», `FM-409202`).
MAX_TRANSACTIONS_PER_USER = 100_000


class Transaction(Base):
    """Агрегатор транзакции пользователя"""

    version: int = Field(default=1, ge=1)

    uid: apps_types.TransactionUID = Field(
        description="Уникальный ID записи транзакции.",
    )
    user_uid: apps_types.UserUID = Field(
        description="UID пользователя.",
    )
    transaction_date: datetime = Field(
        description="Дата транзакции.",
    )
    category_uid: apps_types.CategoryUID = Field(
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
        category_uid: apps_types.CategoryUID,
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
            category_uid: UID Категории.
            description: Описание.
        """
        uid = uuid4()
        return cls(
            uid=uid,
            user_uid=user_uid,
            transaction_date=transaction_date,
            category_uid=category_uid,
            money_sum=money_sum,
            transaction_type=transaction_type,
            description=description,
        )

    def update(self, changes: TransactionChanges) -> None:
        """Применить явно переданные поля и увеличить версию даже при совпадении значений."""
        for name in changes.model_fields_set:
            value = getattr(changes, name)
            setattr(self, name, (value or None) if name == "description" else value)
        self.version += 1

    def belongs_to(self, user_uid: apps_types.UserUID) -> bool:
        """
        Проверить, что запись принадлежит пользователю.

        Args:
            user_uid: UID пользователя из токена.
        """
        return self.user_uid == user_uid
