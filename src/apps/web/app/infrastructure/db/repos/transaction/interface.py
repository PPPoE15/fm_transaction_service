import abc

from apps import apps_types
from apps.web.app.aggregators.models.transaction.transaction import Transaction
from apps.web.app.aggregators.models.user.user_transactions import UserTransactions


class AbstractTransactionRepo(abc.ABC):
    """Абстрактный репозиторий для транзакций пользователя."""

    @abc.abstractmethod
    async def update(self, user_transactions_agg: UserTransactions) -> None:
        """
        Обновить транзакции пользователя.

        Args:
            user_transactions_agg: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def delete(self, transaction_agg: Transaction) -> None:
        """
        Удалить транзакцию.

        Args:
            transaction_agg: Агрегатор транзакции.
        """

    @abc.abstractmethod
    async def get_by_user_transaction_uid(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
    ) -> Transaction | None:
        """
        Получить транзакцию по UID пользователя и транзакции.

        Args:
            user_uid: UID пользователя.
            transaction_uid: UID транзакции.
        """
