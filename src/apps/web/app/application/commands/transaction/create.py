from datetime import datetime

from apps import apps_types

from . import exceptions
from .uow import AbstractTransactionUnitOfWork


class CreateTransactionCommandHandler:
    """Класс обработчика команды создания транзакции."""

    def __init__(
        self,
        unit_of_work: AbstractTransactionUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды создания транзакции.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        transaction_date: datetime,
        category: apps_types.CategoryName,
        money_sum: apps_types.MoneySum,
        transaction_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> apps_types.TransactionUID:
        """
        Создать транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_date: Дата транзакции.
            money_sum: Денежная сумма по категории.
            transaction_type:Тип транзакции.
            category: Категория.
            description: Описание.

        Raises:
            exceptions.RepositoryAlreadyExistsError: Конфигурация репозитория уже существует.
        """
        async with self._uow as uow:
            user_transactions_agg = await uow.user_transactions_repo.get_by_user_uid(user_uid)
            if not user_transactions_agg:
                msg = f'Пользователь с UID "{user_uid}" не существует.'
                raise exceptions.UserNotFoundError(msg)

            user_transactions_agg.create(
                transaction_date=transaction_date,
                category=category,
                money_sum=money_sum,
                transaction_type=transaction_type,
                description=description,
            )

            await uow.user_transactions_repo.update(user_transactions_agg)
            await uow.commit()
        return user_transactions_agg.transactions[-1].uid
