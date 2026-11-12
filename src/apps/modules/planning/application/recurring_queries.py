"""Чтение серий владельца в одном снимке."""

from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select, true

from apps.modules.category import CategoryORM
from apps.modules.planning.application.recurring_schemas import SeriesItem, SeriesList, SeriesView
from apps.modules.planning.domain.errors import RecurringNotFoundError
from apps.modules.planning.domain.recurring import Series
from apps.modules.planning.infrastructure.orm import RecurringOperation
from apps.shared.db.base_query import BaseQueries
from apps.shared.schemas import PageParams

MAX_SQL_OFFSET = 2**63 - 1


class RecurringQueries(BaseQueries):
    """Читает доступные серии и актуальные имена их категорий."""

    @staticmethod
    def _select(user_uid: UUID) -> Select:
        """Собрать запрос только по доступным сериям владельца."""
        return (
            select(*RecurringOperation.__table__.columns, CategoryORM.name.label("category_name"))
            .join(CategoryORM, CategoryORM.uid == RecurringOperation.category_uid)
            .where(RecurringOperation.user_uid == user_uid, RecurringOperation.deleted_at.is_(None))
        )

    async def get(self, user_uid: UUID, uid: UUID, today: date) -> SeriesView:
        """Вернуть детали с календарём запроса."""
        row = (
            (await self._session.execute(self._select(user_uid).where(RecurringOperation.uid == uid)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecurringNotFoundError
        return SeriesView.build(Series.model_validate(row), row["category_name"], today)

    async def list(self, user_uid: UUID, page_params: PageParams, source: UUID | None, today: date) -> SeriesList:
        """Получить страницу и общий размер даже при пустом результате."""
        query = self._select(user_uid)
        if source is not None:
            query = query.where(RecurringOperation.source_plan_uid == source)
        owned = query.cte("owned_series")
        counts = select(func.count().label("total")).select_from(owned).cte("series_count")
        # Контракт допускает произвольное неотрицательное смещение, PostgreSQL принимает bigint.
        sql_page = page_params.model_copy(update={"skip": min(page_params.skip, MAX_SQL_OFFSET)})
        page = self._apply_pagination(select(owned).order_by(owned.c.first_date, owned.c.uid), sql_page).cte(
            "series_page"
        )
        stmt = select(counts, page).select_from(counts.outerjoin(page, true())).order_by(page.c.first_date, page.c.uid)
        rows = (await self._session.execute(stmt)).mappings().all()
        content = [
            SeriesItem.model_validate(SeriesItem.fields(Series.model_validate(row), row["category_name"], today))
            for row in rows
            if row["uid"] is not None
        ]
        total = rows[0]["total"]
        offset = page_params.skip + len(content)
        return SeriesList(total=total, next_skip=offset if offset < total else None, content=content, today=today)
