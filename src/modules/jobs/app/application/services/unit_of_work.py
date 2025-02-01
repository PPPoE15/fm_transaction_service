import abc
from types import TracebackType
from typing import Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing_extensions import Self


class AbstractUnitOfWork(abc.ABC):
    """
    Абстрактный класс шаблона Единица работы.

    Является дополнительным уровнем абстракции между сервисом и репозиторием. Позволяет изолировать уровень приложения
    от изменений в хранилище данных и упрощает автоматическое модульное тестирование или разработку на основе
    тестирования.
    """

    @abc.abstractmethod
    async def __aenter__(self) -> Self:
        """Зайти в асинхронный контекстный менеджер."""

    async def __aexit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        """
        Выйти из асинхронного контекстного менеджера.

        Args:
            exctype: Класс ошибки.
            excinst: Объект ошибки.
            exctb: Объект трассировки ошибки.
        """
        await self.rollback()

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Откатить транзакцию."""

    @abc.abstractmethod
    async def commit(self) -> None:
        """Применить транзакцию."""


class AbstractSQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """Абстрактный класс Единицы работы для репозиториев SQLAlchemy ORM."""

    _session: AsyncSession

    def __init__(self, session_factory: async_sessionmaker) -> None:
        """
        Конструктор Единицы работы.

        Args:
            session_factory: Фабрика сессий.
        """
        self._session_factory = session_factory

    async def __aexit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        """
        Выйти из асинхронного контекстного менеджера.

        Args:
            exctype: Класс ошибки.
            excinst: Объект ошибки.
            exctb: Объект трассировки ошибки.
        """
        await super().__aexit__(exctype, excinst, exctb)
        await self._session.close()

    async def rollback(self) -> None:
        """Откатить транзакцию."""
        await self._session.rollback()

    async def commit(self) -> None:
        """Применить транзакцию."""
        await self._session.commit()
