import abc

from apps import apps_types
from apps.web.app.aggregators.models.transaction.transaction import Transaction


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
