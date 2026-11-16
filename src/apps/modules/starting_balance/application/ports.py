import abc

from apps.modules.starting_balance.domain import StartingBalance
from apps.shared import apps_types


class AbstractStartingBalanceRepo(abc.ABC):
    """Абстрактный репозиторий стартовых остатков (не больше одного на пользователя)."""

    @abc.abstractmethod
    async def create(self, starting_balance: StartingBalance) -> None:
        """
        Сохранить стартовый остаток пользователя.

        Args:
            starting_balance: Агрегат стартового остатка.

        Raises:
            StartingBalanceAlreadyExistsError: Если у пользователя остаток уже есть (нарушение первичного ключа
                при гонке двух запросов, прошедших проверку команды).
        """

    @abc.abstractmethod
    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> StartingBalance | None:
        """
        Получить стартовый остаток пользователя.

        Args:
            user_uid: UID пользователя.
        """
