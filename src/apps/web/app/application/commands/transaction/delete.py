from apps import apps_types

from .exceptions import ForbiddenError
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
        """
        async with self._uow as uow:
            transaction = await uow.transactions_repo.get_by_uid(transaction_uid)
            if not transaction:
                return
            if transaction.user_uid != user_uid:
                msg = "Запрещено удалять запись, которая вам не принадлежит"
                raise ForbiddenError(msg)
            await uow.transactions_repo.delete(transaction_uid)
            await uow.commit()
