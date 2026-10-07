from typing import Any, Self

from apps.web.core.unit_of_work import AbstractSQLAlchemyUnitOfWork, AbstractUnitOfWork
from apps.web.modules.category.infrastructure.db.repos import AbstractCategoryRepo
from apps.web.modules.category.infrastructure.db.repos import Repo as CategoryRepo
from apps.web.modules.transaction.infrastructure.db.repos import AbstractTransactionRepo, Repo


class AbstractTransactionUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы для пользователя и его транзакций."""

    transactions_repo: AbstractTransactionRepo
    # Статьи нужны, чтобы проверить, что транзакция привязывается к статье того же пользователя.
    categories_repo: AbstractCategoryRepo


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
