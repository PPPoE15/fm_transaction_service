"""Проверка версии существующих строк при миграции FM-99."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.db
async def test_existing_transactions_receive_version_one(db_engine: AsyncEngine) -> None:
    """После downgrade/upgrade старая операция сохраняет данные и получает version=1."""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[3] / "migrations"))
    await asyncio.to_thread(command.downgrade, config, "8d3f6a2b1c47")
    try:
        async with db_engine.begin() as connection:
            owner, category, transaction = uuid4(), uuid4(), uuid4()
            await connection.execute(
                text("INSERT INTO categories (uid,user_uid,name,category_type) VALUES (:uid,:owner,'Еда','outcome')"),
                {"uid": category, "owner": owner},
            )
            await connection.execute(
                text(
                    "INSERT INTO transactions (uid,user_uid,category_uid,transaction_date,money_sum,transaction_type) "
                    "VALUES (:uid,:owner,:category,'2026-01-01',100,'outcome')"
                ),
                {"uid": transaction, "owner": owner, "category": category},
            )
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    async with db_engine.connect() as connection:
        row = (await connection.execute(text("SELECT version,money_sum FROM transactions"))).one()
        assert tuple(row) == (1, 100)
