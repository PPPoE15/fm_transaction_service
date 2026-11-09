"""Чтение плана и страницы с одним MVCC-снимком."""

from datetime import date
from uuid import UUID

from sqlalchemy import Select, and_, func, select, true

from apps.modules.category import CategoryORM
from apps.modules.planning.application.schemas import PlanList, PlanView
from apps.modules.planning.domain.errors import PlanNotFoundError
from apps.modules.planning.domain.model import Plan
from apps.modules.planning.infrastructure.orm import PlannedTransaction
from apps.shared.apps_types import TransactionType
from apps.shared.db.base_query import BaseQueries
from apps.shared.schemas import PageParams


class PlanQueries(BaseQueries):
    """Читает только планы владельца, включая актуальное имя категории."""

    @staticmethod
    def _select(user_uid: UUID) -> Select:
        """Выбрать поля агрегата и имя категории без дополнительных ORM-запросов."""
        return (
            select(*PlannedTransaction.__table__.columns, CategoryORM.name.label("category_name"))
            .join(CategoryORM, CategoryORM.uid == PlannedTransaction.category_uid)
            .where(PlannedTransaction.user_uid == user_uid)
        )

    async def get(self, user_uid: UUID, plan_uid: UUID, today: date) -> PlanView:
        """Получить собственный план или одинаковую ошибку отсутствующего/чужого."""
        row = (
            (await self._session.execute(self._select(user_uid).where(PlannedTransaction.uid == plan_uid)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise PlanNotFoundError
        plan = Plan.model_validate({key: row[key] for key in Plan.model_fields})
        return PlanView.build(plan, row["category_name"], today)

    async def list(
        self,
        user_uid: UUID,
        page_params: PageParams,
        transaction_type: TransactionType | None,
        include_completed: bool,
        today: date,
    ) -> PlanList:
        """Вернуть страницу, total и due_count даже при пустой странице одним SELECT."""
        source = self._select(user_uid)
        if transaction_type is not None:
            source = source.where(PlannedTransaction.transaction_type == transaction_type)
        owned = source.cte("owned_plans")
        visible = true() if include_completed else owned.c.status == "pending"
        counts = (
            select(
                func.count().filter(visible).label("total"),
                func.count()
                .filter(and_(owned.c.status == "pending", owned.c.planned_date <= today))
                .label("due_count"),
            )
            .select_from(owned)
            .cte("plan_counts")
        )
        page_query = select(owned).where(visible).order_by(owned.c.planned_date, owned.c.uid)
        page = self._apply_pagination(page_query, page_params).cte("plan_page")
        stmt = (
            select(counts, page).select_from(counts.outerjoin(page, true())).order_by(page.c.planned_date, page.c.uid)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        content = [
            PlanView.build(
                Plan.model_validate({key: row[key] for key in Plan.model_fields}), row["category_name"], today
            )
            for row in rows
            if row["uid"] is not None
        ]
        next_skip = page_params.skip + len(content)
        total = rows[0]["total"]
        return PlanList(
            total=total,
            due_count=rows[0]["due_count"],
            content=content,
            today=today,
            next_skip=next_skip if next_skip < total else None,
        )
