"""Публичный API модуля транзакций: другие модули импортируют из `transaction` только отсюда."""

from apps.modules.transaction.application.exceptions import TransactionLimitExceededError
from apps.modules.transaction.domain import MAX_TRANSACTIONS_PER_USER, Transaction
from apps.modules.transaction.infrastructure.orm import Transaction as TransactionORM
from apps.modules.transaction.infrastructure.uow import TransactionUnitOfWork

__all__ = [
    "MAX_TRANSACTIONS_PER_USER",
    "Transaction",
    "TransactionLimitExceededError",
    "TransactionORM",
    "TransactionUnitOfWork",
]
