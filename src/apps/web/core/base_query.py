from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, inspect

from apps.web.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apps.db_models.base import AsyncBase
    from apps.utils.schemas import PageParams


class BaseQueries:
    """Базовый класс запросов."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """
        Инициализация запросов к БД.

        Args:
            session: Сессия SQLAlchemy ORM.
            access_controller: Контроллер доступа.
        """
        self._session = session
        self._logger = get_logger()

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
