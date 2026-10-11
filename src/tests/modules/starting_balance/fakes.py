"""Фейки модуля стартового остатка: хранилище в памяти и единица работы поверх него."""

from apps.modules.starting_balance.application.ports import AbstractStartingBalanceRepo
from apps.modules.starting_balance.application.uow import AbstractStartingBalanceUnitOfWork
from apps.modules.starting_balance.domain import StartingBalance
from apps.shared import apps_types
from tests.modules.fakes import FakeUnitOfWorkMixin


class InMemoryStartingBalanceRepo(AbstractStartingBalanceRepo):
    """Репозиторий стартовых остатков в памяти."""

    def __init__(self) -> None:
        """Пустое хранилище."""
        self.items: dict[apps_types.UserUID, StartingBalance] = {}

    async def create(self, starting_balance: StartingBalance) -> None:
        self.items[starting_balance.user_uid] = starting_balance.model_copy()

    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> StartingBalance | None:
        starting_balance = self.items.get(user_uid)
        return starting_balance.model_copy() if starting_balance else None


class FakeStartingBalanceUnitOfWork(FakeUnitOfWorkMixin, AbstractStartingBalanceUnitOfWork):
    """Единица работы модуля стартового остатка в памяти."""

    def __init__(self, starting_balances: InMemoryStartingBalanceRepo) -> None:
        """
        Единица работы поверх хранилища стартовых остатков.

        Args:
            starting_balances: Хранилище стартовых остатков.
        """
        self.starting_balances_repo = starting_balances
