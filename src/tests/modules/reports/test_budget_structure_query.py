"""Проверки границ чтения фактов бюджета на настоящем Postgres."""

from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.category import CategoryORM
from apps.modules.reports.application.queries.budget_structure import GetBudgetStructure
from apps.modules.transaction import TransactionORM
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory

PLAN_AMOUNT = 100


@pytest.mark.db
async def test_future_year_does_not_read_transactions(db_engine: AsyncEngine) -> None:
    """Будущий год сохраняет статьи и планы, но не выполняет SELECT фактов."""
    owner, category_uid = uuid4(), uuid4()
    async with async_session_factory() as session:
        session.add(
            CategoryORM(uid=category_uid, user_uid=owner, name="Еда", category_type="outcome", money_plan=PLAN_AMOUNT)
        )
        await session.commit()
    statements: list[str] = []

    def record_statement(_connection: object, _cursor: object, statement: str, *_args: object) -> None:
        """Фиксирует выполненные запросы, не меняя их выполнение."""
        statements.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        async with async_session_factory() as session:
            report = await GetBudgetStructure(session).execute(
                owner, 2027, apps_types.TransactionType.OUTCOME, date(2026, 3, 15)
            )
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", record_statement)
    assert len(report.rows) == 1
    assert report.rows[0].money_plan == PLAN_AMOUNT
    assert all(month.fact is None for month in report.rows[0].months)
    assert not any("transactions" in statement for statement in statements)


@pytest.mark.db
@pytest.mark.parametrize(
    ("year", "today", "included", "excluded"),
    [
        (2026, date(2026, 3, 15), "2026-03-31T23:59:59.999999", "2026-04-01T00:00:00"),
        (2026, date(2026, 1, 1), "2026-01-31T23:59:59.999999", "2026-02-01T00:00:00"),
        (2026, date(2026, 12, 1), "2026-12-31T23:59:59.999999", "2027-01-01T00:00:00"),
        (2025, date(2026, 3, 15), "2025-12-31T23:59:59.999999", "2026-01-01T00:00:00"),
        (2099, date(2099, 12, 31), "2099-12-31T23:59:59.999999", "2100-01-01T00:00:00"),
    ],
)
async def test_fact_query_excludes_future_months(
    db_engine: AsyncEngine, year: int, today: date, included: str, excluded: str
) -> None:
    """Сам SQL исключает будущие месяцы, сохраняя весь текущий месяц и полуинтервал."""
    owner, category_uid = uuid4(), uuid4()
    async with async_session_factory() as session:
        session.add(CategoryORM(uid=category_uid, user_uid=owner, name="Еда", category_type="outcome"))
        await session.flush()
        for timestamp, amount in [(included, 100), (excluded, 999)]:
            session.add(
                TransactionORM(
                    uid=uuid4(),
                    user_uid=owner,
                    category_uid=category_uid,
                    transaction_date=datetime.fromisoformat(timestamp),
                    money_sum=amount,
                    transaction_type="outcome",
                )
            )
        await session.commit()
        facts = await GetBudgetStructure(session)._get_month_facts(
            owner, year, apps_types.TransactionType.OUTCOME, today
        )
    assert facts == {(category_uid, datetime.fromisoformat(included).month): 100}
