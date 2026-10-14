import abc

from apps.modules.transaction.domain import Transaction
from apps.shared import apps_types


class AbstractTransactionRepo(abc.ABC):
    """Абстрактный репозиторий для транзакций пользователя."""

    @abc.abstractmethod
    async def create(self, transaction: Transaction) -> None:
        """
        Создать транзакцию пользователя.

        Args:
            transaction: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def count_by_user_for_update(self, user_uid: apps_types.UserUID) -> int:
        """
        Число транзакций пользователя под блокировкой их набора до конца транзакции единицы работы.

        Пока блокировка держится, другое создание транзакции того же пользователя ждёт её снятия, поэтому решение
        «лимит не достигнут» команды остаётся верным до commit. Блокирует и пустой набор, поэтому строки не подходят.

        Args:
            user_uid: UID пользователя.
        """

    @abc.abstractmethod
    async def update(self, transaction_agg: Transaction) -> None:
        """
        Обновить транзакции пользователя.

        Args:
            transaction_agg: UID пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def delete(self, transaction_uid: apps_types.TransactionUID) -> None:
        """
        Удалить транзакцию пользователя.

        Args:
            transaction_uid: UID пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def get_by_uid(self, transaction_uid: apps_types.TransactionUID) -> Transaction | None:
        """
        Получить транзакцию по UID.

        Args:
            transaction_uid: UID транзакции.
        """

    @abc.abstractmethod
    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> list[Transaction] | None:
        """
        Получить пользователя и его транзакции по UID пользователя.

        Args:
            user_uid: UID пользователя.
        """
