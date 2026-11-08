"""План фактического запроса отчёта на 100000 операциях нескольких пользователей."""

import json
import logging
from datetime import date

import pytest
from sqlalchemy import Select, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import ClauseElement

from apps.modules.reports.application.queries.budget_structure import GetBudgetStructure
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory

INDEX_NAME = "ix_transactions_user_uid_transaction_date"


@pytest.mark.db
async def test_fact_query_uses_user_date_index(db_engine: AsyncEngine) -> None:
    """Обычный планировщик выбирает составной индекс на селективном годовом диапазоне пользователя."""
    async with db_engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TEMP TABLE fm33_owners ON COMMIT DROP AS "
                "SELECT n, gen_random_uuid() AS owner, gen_random_uuid() AS category FROM generate_series(1,100) AS n"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO categories (uid,user_uid,name,category_type) "
                "SELECT category, owner, 'Еда', 'outcome' FROM fm33_owners"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO transactions (uid,user_uid,category_uid,transaction_date,money_sum,transaction_type) "
                "SELECT gen_random_uuid(), owner, category, "
                "timestamp '2026-01-01' + (((g.n-1)/100)%365) * interval '1 day', 100, 'outcome' "
                "FROM generate_series(1,100000) AS g(n) JOIN fm33_owners AS o ON o.n=(g.n-1)%100+1"
            )
        )
        await connection.execute(text("ANALYZE categories"))
        await connection.execute(text("ANALYZE transactions"))
        owner = (await connection.execute(text("SELECT user_uid FROM categories ORDER BY uid LIMIT 1"))).scalar_one()
    statements: list[str] = []

    def record_query(connection: Connection, clause: ClauseElement, *_args: object) -> None:
        """Сохраняет реальный SQL фактов для EXPLAIN без копии запроса в тесте."""
        if isinstance(clause, Select) and "FROM transactions" in str(clause):
            statements.append(str(clause.compile(dialect=connection.dialect, compile_kwargs={"literal_binds": True})))

    event.listen(db_engine.sync_engine, "before_execute", record_query)
    try:
        async with async_session_factory() as session:
            report = await GetBudgetStructure(session).execute(
                owner, 2026, apps_types.TransactionType.OUTCOME, date(2026, 3, 15)
            )
    finally:
        event.remove(db_engine.sync_engine, "before_execute", record_query)
    assert len(statements) == 1
    assert len(report.rows) == 1
    async with db_engine.connect() as connection:
        plan = (await connection.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statements[0]))).scalar_one()
    rendered = json.dumps(plan, ensure_ascii=False, indent=2)
    assert INDEX_NAME in rendered
    logging.getLogger(__name__).info("FM-33 SQL:\n%s\nFM-33 EXPLAIN:\n%s", statements[0], rendered)
