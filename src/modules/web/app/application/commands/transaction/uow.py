from typing import Any, Self

from modules.web.app.application.commands.unit_of_work import AbstractSQLAlchemyUnitOfWork, AbstractUnitOfWork
from modules.web.app.infrastructure.db.repos.transaction import AbstractUserTransactionRepo, UserTransactionRepo


class AbstractTransactionUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы для пользователя и его транзакций."""

    user_transactions_repo: AbstractUserTransactionRepo


class TransactionUnitOfWork(AbstractTransactionUnitOfWork, AbstractSQLAlchemyUnitOfWork):
    """Единица работы для пользователя и его транзакций."""

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Инициализация единицы работы для пользователя и его транзакций.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        super().__init__(*args, **kwargs)

    async def __aenter__(self) -> Self:
        """Зайти в асинхронный контекстный менеджер."""
        self._session = self._session_factory()
        self.user_transactions_repo = UserTransactionRepo(self._session)
        return self
