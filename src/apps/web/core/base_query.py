from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from sqlalchemy import Select, inspect

if TYPE_CHECKING:
    import logging

    from sqlalchemy.ext.asyncio import AsyncSession

    from apps.db_models.base import AsyncBase
    from apps.utils.schemas import PageParams

AccessControllerType = TypeVar("AccessControllerType")


class BaseQueries(Generic[AccessControllerType]):
    """Базовый класс запросов."""

    _access_controller: AccessControllerType

    def __init__(
        self,
        session: AsyncSession,
        access_controller: AccessControllerType | None,
        logger: logging.Logger,
    ) -> None:
        """
        Инициализация запросов к БД.

        Args:
            session: Сессия SQLAlchemy ORM.
            access_controller: Контроллер доступа.
            logger: Логгер.
        """
        self._session = session
        self._access_controller = access_controller
        self._logger = logger

    @staticmethod
    def _apply_pagination(stmt: Select, page_params: PageParams) -> Select:
        """
        Применить к запросу параметры пагинации

        Args:
            stmt: Запрос SQLAlchemy ORM
            page_params: Параметры пагинации.
        """
        return stmt.limit(page_params.limit).offset(page_params.skip)

    @staticmethod
    def _model_to_dict(orm_model: AsyncBase) -> dict[str, Any]:
        """
        Преобразовать orm-модель в словарь, содержащий поля модели, включая связи.

        Args:
            orm_model: Orm-модель.
        """
        return {c.key: getattr(orm_model, c.key) for c in inspect(orm_model, raiseerr=True).mapper.column_attrs}
