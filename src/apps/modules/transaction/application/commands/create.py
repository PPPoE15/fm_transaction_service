from datetime import datetime

from apps.modules.transaction.application.exceptions import (
    TransactionLimitExceededError,
    TransactionTypeMismatchError,
)
from apps.modules.transaction.application.guards import get_own_category
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.domain import MAX_TRANSACTIONS_PER_USER, Transaction
from apps.shared import apps_types


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
        category_uid: apps_types.CategoryUID,
        money_sum: apps_types.MoneySum,
        transaction_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> Transaction:
        """
        Создать транзакцию.

        Args:
            user_uid: UID пользователя.
            transaction_date: Дата транзакции.
            category_uid: UID статьи пользователя.
            money_sum: Денежная сумма.
            transaction_type: Тип транзакции; должен совпадать с типом статьи.
            description: Описание.

        Returns:
            Созданная транзакция.

        Raises:
            TransactionCategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
            TransactionTypeMismatchError: Если тип транзакции не совпадает с типом статьи.
            TransactionLimitExceededError: Если у пользователя уже `MAX_TRANSACTIONS_PER_USER` транзакций.
        """
        transaction = Transaction.create(
            user_uid=user_uid,
            transaction_date=transaction_date,
            category_uid=category_uid,
            money_sum=money_sum,
            transaction_type=transaction_type,
            description=description,
        )
        async with self._uow as uow:
            # NOTE(FM-52): блокировка и подсчёт идут раньше проверок статьи, хотя обратный порядок тоже без взаимных
            # блокировок (KEY SHARE с KEY SHARE не конфликтуют, смена типа статьи advisory 52 не берёт). Из-за этого
            # и запрос с чужой статьёй или неверным типом ждёт блокировку и считает транзакции пользователя; с индексом
            # из TODO(FM-33) подсчёт дешёвый. Если начнёт мешать — сначала статья, потом `count_by_user_for_update`.
            transactions_count = await uow.transactions_repo.count_by_user_for_update(user_uid)
            category = await get_own_category(uow, user_uid, category_uid)
            if category.category_type != transaction_type:
                raise TransactionTypeMismatchError
            if transactions_count >= MAX_TRANSACTIONS_PER_USER:
                raise TransactionLimitExceededError
            await uow.transactions_repo.create(transaction)
            await uow.commit()
        return transaction
