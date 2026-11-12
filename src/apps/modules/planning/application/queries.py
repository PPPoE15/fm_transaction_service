"""Чтение плана и страницы с одним MVCC-снимком."""

from datetime import date
from uuid import UUID

from sqlalchemy import RowMapping, Select, and_, func, select, true

from apps.modules.category import CategoryORM
from apps.modules.planning.application.schemas import PlanList, PlanView, RecurrenceView
from apps.modules.planning.domain.errors import PlanNotFoundError
from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.recurring import regular_transaction_status
from apps.modules.planning.infrastructure.orm import PlannedTransaction, RecurringOccurrence, RecurringOperation
from apps.shared.apps_types import TransactionType
from apps.shared.db.base_query import BaseQueries
from apps.shared.schemas import PageParams


class PlanQueries(BaseQueries):
    """Читает только планы владельца, включая актуальное имя категории."""

    @staticmethod
    def _select(user_uid: UUID) -> Select:
        """Выбрать поля агрегата и имя категории без дополнительных ORM-запросов."""
        return (
            select(
                *PlannedTransaction.__table__.columns,
                CategoryORM.name.label("category_name"),
                RecurringOccurrence.operation_uid,
                RecurringOccurrence.scheduled_date,
                RecurringOccurrence.is_exception,
                RecurringOperation.deleted_at,
                RecurringOperation.end_date,
            )
            .join(CategoryORM, CategoryORM.uid == PlannedTransaction.category_uid)
            .outerjoin(RecurringOccurrence, RecurringOccurrence.plan_uid == PlannedTransaction.uid)
            .outerjoin(RecurringOperation, RecurringOperation.uid == RecurringOccurrence.operation_uid)
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
        return self._view(row, today)

    @staticmethod
    def _view(row: RowMapping, today: date) -> PlanView:
        """Представить план и его позицию из одного снимка."""
        plan = Plan.model_validate({key: row[key] for key in Plan.model_fields})
        view = PlanView.build(plan, row["category_name"], today)
        if row["operation_uid"] is not None:
            view.recurrence = RecurrenceView(
                operation_uid=row["operation_uid"],
                scheduled_date=row["scheduled_date"],
                is_exception=row["is_exception"],
                operation_status=regular_transaction_status(row["end_date"], row["deleted_at"], today),
            )
        return view

    async def list(
        self,
        user_uid: UUID,
        page_params: PageParams,
        transaction_type: TransactionType | None,
        include_completed: bool,
        today: date,
        include_recurring: bool = True,
    ) -> PlanList:
        """Вернуть страницу, total и due_count даже при пустой странице одним SELECT."""
        source = self._select(user_uid)
        if transaction_type is not None:
            source = source.where(PlannedTransaction.transaction_type == transaction_type)
        if not include_recurring:
            source = source.where(RecurringOccurrence.operation_uid.is_(None))
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
        content = [self._view(row, today) for row in rows if row["uid"] is not None]
        next_skip = page_params.skip + len(content)
        total = rows[0]["total"]
        return PlanList(
            total=total,
            due_count=rows[0]["due_count"],
            content=content,
            today=today,
            next_skip=next_skip if next_skip < total else None,
        )
