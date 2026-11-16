from apps.modules.transaction.application.exceptions import (
    TransactionTypeMismatchError,
    TransactionVersionConflictError,
)
from apps.modules.transaction.application.guards import get_own_category, get_own_transaction
from apps.modules.transaction.application.queries.schemas import CategoryRef, TransactionSchema
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.domain.changes import TransactionChanges
from apps.shared import apps_types


class UpdateTransactionCommandHandler:
    """Обработчик частичного изменения операции с оптимистической блокировкой."""

    def __init__(self, unit_of_work: AbstractTransactionUnitOfWork) -> None:
        """Сохранить единицу работы для атомарной проверки и записи."""
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
        changes: TransactionChanges,
        expected_version: int | None = None,
    ) -> TransactionSchema:
        """Обновить операцию и вернуть её проверенное состояние после успешного commit."""
        async with self._uow as uow:
            transaction = await get_own_transaction(uow, user_uid, transaction_uid)
            if expected_version is not None and transaction.version != expected_version:
                raise TransactionVersionConflictError
            category = await get_own_category(uow, user_uid, changes.category_uid or transaction.category_uid)
            resulting_type = changes.transaction_type or transaction.transaction_type
            if resulting_type != category.category_type:
                raise TransactionTypeMismatchError
            transaction.update(changes)
            await uow.transactions_repo.update(transaction)
            response = TransactionSchema(
                **transaction.model_dump(exclude={"user_uid", "category_uid"}),
                category=CategoryRef(uid=category.uid, name=category.name),
            )
            await uow.commit()
        return response
