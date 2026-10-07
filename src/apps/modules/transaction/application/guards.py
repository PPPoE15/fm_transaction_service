from apps.modules import category as category_module
from apps.modules.transaction.application.exceptions import TransactionNotFoundError
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

    Правило «статья своя» одно на оба модуля — `category.get_own_category`.

    Args:
        uow: Открытая единица работы.
        user_uid: UID пользователя из токена.
        category_uid: UID статьи.

    Raises:
        CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
    """
    # NOTE(FM-9): по контракту чужая/несуществующая статья в теле POST/PATCH /transactions — 400 FM-400201;
    # сейчас отвечаем 404 FM-404000: коды ошибок задаются классом ответа, а не исключением. Привести вместе
    # с остальными кодами контракта. Статья читается без блокировки: при параллельном удалении статьи её
    # владельцем INSERT/UPDATE транзакции упадёт на FK (500 вместо 404) — изоляцию это не нарушает.
    return await category_module.get_own_category(uow.categories_repo, user_uid, category_uid)


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
