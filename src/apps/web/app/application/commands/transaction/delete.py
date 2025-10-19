from datetime import datetime

from apps import apps_types

from . import exceptions
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
            transaction_date: Дата транзакции.

        Raises:
            exceptions.UserNotFoundError: Пользователь не существует.
        """
        async with self._uow as uow:
            user_transactions_agg = await uow.user_transactions_repo.get_by_user_uid(user_uid)
            if not user_transactions_agg:
                msg = f'Пользователь с UID "{user_uid}" не существует.'
                raise exceptions.UserNotFoundError(msg)

            user_transaction_agg = await uow.user_transactions_repo.get_by_user_transaction_uid(
                user_uid=user_uid,
                transaction_uid=transaction_uid,
            )
            if not user_transaction_agg:
                msg = f'Транзакция с идентификатором "{transaction_uid}" не существует.'
                raise exceptions.TransactionNotFoundError(msg)

            await uow.distribution_repo.delete(user_transaction_agg.transactions[0])
            await uow.commit()
