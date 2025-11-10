from datetime import datetime

from apps import apps_types
from apps.web.app.aggregators.models.transaction.transaction import Transaction

from .exceptions import ForbiddenError
from .exceptions import TransactionNotFoundError
from .uow import AbstractTransactionUnitOfWork


class UpdateTransactionCommandHandler:
    """Класс обработчика команды изменения транзакции."""

    def __init__(
        self,
        unit_of_work: AbstractTransactionUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды изменения транзакции.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
        transaction_date: datetime,
        category: apps_types.CategoryName,
        money_sum: apps_types.MoneySum,
        transaction_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> apps_types.TransactionUID | None:
        """
        Изменить транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_uid: UID транзакции.
            transaction_date: Дата транзакции.
            category: Категория.
            money_sum: Денежная сумма по категории.
            transaction_type:Тип транзакции.
            description: Описание.
        """

        async with self._uow as uow:
            transaction = await uow.transactions_repo.get_by_uid(transaction_uid)
            if not transaction:
                msg = "Транзакция с данным UID не найдена"
                raise TransactionNotFoundError(msg)

            if transaction.user_uid != user_uid:
                msg = "Запрещено изменять запись, которая вам не принадлежит"
                raise ForbiddenError(msg)

            transaction.update(
                transaction_date=transaction_date,
                category=category,
                money_sum=money_sum,
                transaction_type=transaction_type,
                description=description,
            )

            await uow.transactions_repo.update(transaction)
            await uow.commit()
        return transaction.uid
