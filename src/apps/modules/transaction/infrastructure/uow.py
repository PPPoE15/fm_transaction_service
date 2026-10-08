from typing import Any, Self

from apps.modules.category import CategoryRepo
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.infrastructure.repo import Repo
from apps.shared.unit_of_work import AbstractSQLAlchemyUnitOfWork


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
        self.transactions_repo = Repo(self._session)
        self.categories_repo = CategoryRepo(self._session)
        return self
