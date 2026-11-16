"""Согласованность страницы и total при записи между SQL-чтениями."""

from datetime import datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.util.concurrency import await_only
from starlette import status

from apps.modules.category import CategoryORM
from apps.modules.transaction import TransactionORM
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory


@pytest.mark.db
async def test_list_uses_one_snapshot_during_concurrent_delete(
    db_engine: AsyncEngine, client: AsyncClient, make_token: TokenFactory
) -> None:
    """Удаление после чтения строк не должно дать старые строки и новый total в одном ответе."""
    owner, category, uid = uuid4(), uuid4(), uuid4()
    async with async_session_factory() as session:
        session.add(CategoryORM(uid=category, user_uid=owner, name="Еда", category_type="outcome"))
        await session.flush()
        session.add(
            TransactionORM(
                uid=uid,
                user_uid=owner,
                category_uid=category,
                money_sum=100,
                transaction_date=datetime.fromisoformat("2026-01-01T12:00:00"),
                transaction_type="outcome",
            )
        )
        await session.commit()
    deleted = False

    async def concurrent_delete() -> None:
        """Зафиксировать удаление через независимое соединение после получения курсора списка."""
        async with db_engine.begin() as connection:
            await connection.execute(text("DELETE FROM transactions WHERE uid = :uid"), {"uid": uid})

    def after_select(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        """Вставить конкурентный commit строго после первого SELECT операций."""
        nonlocal deleted
        if not deleted and "SELECT" in statement and "transactions" in statement:
            deleted = True
            await_only(concurrent_delete())

    event.listen(db_engine.sync_engine, "after_cursor_execute", after_select)
    try:
        response = await client.get("/transactions", headers={"Authorization": f"Bearer {make_token(owner)}"})
    finally:
        event.remove(db_engine.sync_engine, "after_cursor_execute", after_select)
    assert deleted
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["total"] == 1
    assert [row["uid"] for row in response.json()["content"]] == [str(uid)]
    assert response.json()["next_skip"] is None
    async with db_engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM transactions")) == 0
