from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from modules.utils.schemas import Base
from modules.web.app.aggregators.models.transaction import Transaction

if TYPE_CHECKING:
    from datetime import datetime

    from modules import types

from .user import User


class UserTransactions(Base):
    """Агрегатор пользователя с данными о транзакциях."""

    user: User = Field(description="Пользователь")
    transactions: list[Transaction] = Field(description="Транзакции пользователя.")

    def create(
        self,
        transaction_date: datetime,
        category: types.CategoryName,
        money_sum: types.MoneySum,
        transaction_type: types.TransactionType,
        description: types.Description
    ) -> None:
        """
        Создать новую категорию транзакций.

        Args:
            transaction_date: Дата транзакции.
            money_sum: Денежная сумма по категории.
            transaction_type:Тип транзакции.
            category: Категория.
            description: Описание.
        """
        new_transaction = Transaction.create(
            user_uid=self.user.uid,
            transaction_date=transaction_date,
            category=category,
            money_sum=money_sum,
            transaction_type=transaction_type,
            description=description,
        )
        self.transactions.append(new_transaction)
