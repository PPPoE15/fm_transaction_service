from apps.modules import category as category_module
from apps.modules.transaction.application.exceptions import (
    TransactionCategoryNotFoundError,
    TransactionNotFoundError,
)
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.domain import Transaction
from apps.shared import apps_types


async def get_own_category(
    uow: AbstractTransactionUnitOfWork,
    user_uid: apps_types.UserUID,
    category_uid: apps_types.CategoryUID,
) -> category_module.Category:
    """
    Получить статью пользователя для привязки к ней транзакции.

    Статья читается под блокировкой (`get_by_uid_for_key_share`): до конца единицы работы её не удалят и не сменят
    её тип, поэтому проверки по статье остаются верными до commit, а вставка транзакции не падает на внешнем ключе.

    Args:
        uow: Открытая единица работы.
        user_uid: UID пользователя из токена.
        category_uid: UID статьи из тела запроса.

    Raises:
        TransactionCategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю (400 `FM-400201`).
    """
    # NOTE(FM-52): старый `PATCH /transactions` тоже берёт здесь `FOR KEY SHARE` на статью, а каскадное удаление статьи
    # (`DELETE /category`) блокирует сначала строки транзакций, потом статью — их гонка может кончиться deadlock
    # (500 у одного из запросов). Оба эндпоинта старые, каскад уходит по TODO(FM-4) в `category/…/commands/delete.py`.
    category = await uow.categories_repo.get_by_uid_for_key_share(category_uid)
    if category is None or not category.belongs_to(user_uid):
        raise TransactionCategoryNotFoundError
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
