from apps import apps_types
from apps.web.modules.category.aggregators import Category
from apps.web.modules.transaction.aggregators import Transaction

from .exceptions import CategoryNotFoundError, TransactionNotFoundError
from .uow import AbstractTransactionUnitOfWork


async def get_own_category(
    uow: AbstractTransactionUnitOfWork,
    user_uid: apps_types.UserUID,
    category_uid: apps_types.CategoryUID,
) -> Category:
    """
    Получить статью пользователя для привязки к ней транзакции.

    Args:
        uow: Открытая единица работы.
        user_uid: UID пользователя из токена.
        category_uid: UID статьи.

    Raises:
        CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
    """
    category = await uow.categories_repo.get_by_uid(category_uid)
    if category is None or not category.belongs_to(user_uid):
        raise CategoryNotFoundError
    return category


async def get_own_transaction(
    uow: AbstractTransactionUnitOfWork,
    user_uid: apps_types.UserUID,
    transaction_uid: apps_types.TransactionUID,
) -> Transaction:
    """
    Получить транзакцию пользователя.

    Args:
        uow: Открытая единица работы.
        user_uid: UID пользователя из токена.
        transaction_uid: UID транзакции.

    Raises:
        TransactionNotFoundError: Если транзакции нет или она принадлежит другому пользователю.
    """
    transaction = await uow.transactions_repo.get_by_uid(transaction_uid)
    if transaction is None or not transaction.belongs_to(user_uid):
        raise TransactionNotFoundError
    return transaction
