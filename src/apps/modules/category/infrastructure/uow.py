from typing import Any, Self

from apps.modules.category.application.uow import AbstractCategoryUnitOfWork
from apps.modules.category.infrastructure.repo import Repo
from apps.shared.unit_of_work import AbstractSQLAlchemyUnitOfWork


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
