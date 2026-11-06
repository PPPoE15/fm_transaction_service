from apps.modules.transaction.application.exceptions import TransactionVersionConflictError
from apps.modules.transaction.application.guards import get_own_transaction
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.shared import apps_types


class DeleteTransactionCommandHandler:
    """Класс обработчика команды удаления транзакции."""

    def __init__(
        self,
        unit_of_work: AbstractTransactionUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды удаления транзакции.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
        expected_version: int | None = None,
    ) -> None:
        """
        Удалить транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_uid: UID транзакции.
            expected_version: Версия клиента; отсутствие отключает проверку.

        Raises:
            TransactionNotFoundError: Если транзакции нет или она принадлежит другому пользователю.
        """
        async with self._uow as uow:
            transaction = await get_own_transaction(uow, user_uid, transaction_uid)
            if expected_version is not None and transaction.version != expected_version:
                raise TransactionVersionConflictError
            await uow.transactions_repo.delete(transaction_uid)
            await uow.commit()
