"""Общие правила создания факта напрямую и из запланированной операции."""

from apps.modules.category import Category
from apps.modules.transaction.application.exceptions import (
    TransactionCategoryNotFoundError,
    TransactionLimitExceededError,
    TransactionTypeMismatchError,
)
from apps.shared import apps_types


def validate_creation(
    category: Category | None,
    user_uid: apps_types.UserUID,
    transaction_type: apps_types.TransactionType,
    transactions_count: int,
    limit: int,
) -> Category:
    """Проверить владельца, тип категории и квоту после блокировок; вернуть проверенную категорию."""
    if category is None or not category.belongs_to(user_uid):
        raise TransactionCategoryNotFoundError
    if category.category_type != transaction_type:
        raise TransactionTypeMismatchError
    if transactions_count >= limit:
        raise TransactionLimitExceededError
    return category
