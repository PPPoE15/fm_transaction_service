import abc

from apps import apps_types
from apps.web.app.aggregators.models.user.user_transactions import UserTransactions


class AbstractUserTransactionRepo(abc.ABC):
    """Абстрактный репозиторий для транзакций пользователя."""

    @abc.abstractmethod
    async def create(self, user_transaction: UserTransactions) -> None:
        """
        Создать транзакцию пользователя.

        Args:
            user_transaction: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def update(self, user_transactions_agg: UserTransactions) -> None:
        """
        Обновить транзакции пользователя.

        Args:
            user_transactions_agg: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> UserTransactions | None:
        """
        Получить пользователя и его транзакции по UID пользователя.

        Args:
            user_uid: UID пользователя.
        """
