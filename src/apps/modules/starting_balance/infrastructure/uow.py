from typing import Self

from apps.modules.starting_balance.application.uow import AbstractStartingBalanceUnitOfWork
from apps.modules.starting_balance.infrastructure.repo import Repo
from apps.shared.unit_of_work import AbstractSQLAlchemyUnitOfWork


class StartingBalanceUnitOfWork(AbstractStartingBalanceUnitOfWork, AbstractSQLAlchemyUnitOfWork):
    """Единица работы для стартового остатка."""

    async def __aenter__(self) -> Self:
        """Зайти в асинхронный контекстный менеджер."""
        self._session = self._session_factory()
        self.starting_balances_repo = Repo(self._session)
        return self
