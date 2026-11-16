"""Публичный API модуля транзакций: другие модули импортируют из `transaction` только отсюда."""

from apps.modules.transaction.application.creation_rules import validate_creation
from apps.modules.transaction.application.exceptions import (
    TransactionCategoryNotFoundError,
    TransactionLimitExceededError,
    TransactionTypeMismatchError,
)
from apps.modules.transaction.application.ports import AbstractTransactionRepo
from apps.modules.transaction.application.queries.schemas import CategoryRef, TransactionSchema
from apps.modules.transaction.domain import MAX_TRANSACTIONS_PER_USER, Transaction
from apps.modules.transaction.infrastructure.orm import Transaction as TransactionORM
from apps.modules.transaction.infrastructure.repo import Repo as TransactionRepo
from apps.modules.transaction.infrastructure.uow import TransactionUnitOfWork

__all__ = [
    "MAX_TRANSACTIONS_PER_USER",
    "AbstractTransactionRepo",
    "CategoryRef",
    "Transaction",
    "TransactionCategoryNotFoundError",
    "TransactionLimitExceededError",
    "TransactionORM",
    "TransactionRepo",
    "TransactionSchema",
    "TransactionTypeMismatchError",
    "TransactionUnitOfWork",
    "validate_creation",
]
