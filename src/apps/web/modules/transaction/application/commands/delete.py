from apps import apps_types

from .guards import get_own_transaction
from .uow import AbstractTransactionUnitOfWork


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
    ) -> None:
        """
        Удалить транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_uid: UID транзакции.

        Raises:
            TransactionNotFoundError: Если транзакции нет или она принадлежит другому пользователю.
        """
        async with self._uow as uow:
            await get_own_transaction(uow, user_uid, transaction_uid)
            await uow.transactions_repo.delete(transaction_uid)
            await uow.commit()
