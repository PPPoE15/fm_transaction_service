from sqlalchemy.ext.asyncio import AsyncSession


class BaseSqlAlchemyRepo:
    """Базовый класс SqlAlchemy репозиториев."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Конструктор репозитория SQLAlchemy ORM.

        Args:
            session: Активная сессия.
        """
        self._session = session
