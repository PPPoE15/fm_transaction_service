from typing import Any, Self

from apps.web.core.unit_of_work import AbstractSQLAlchemyUnitOfWork, AbstractUnitOfWork
from apps.web.modules.category.infrastructure.db.repos import AbstractCategoryRepo, Repo


class AbstractCategoryUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы."""

    repo: AbstractCategoryRepo


class UnitOfWork(AbstractCategoryUnitOfWork, AbstractSQLAlchemyUnitOfWork):
    """Единица работы."""

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Инициализация единицы работы.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        super().__init__(*args, **kwargs)

    async def __aenter__(self) -> Self:
        """Зайти в асинхронный контекстный менеджер."""
        self._session = self._session_factory()
        self.repo = Repo(self._session)
        return self
