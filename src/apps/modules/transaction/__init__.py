"""Публичный API модуля транзакций: другие модули импортируют из `transaction` только отсюда."""

from apps.modules.transaction.infrastructure.orm import Transaction as TransactionORM

__all__ = [
    "TransactionORM",
]
