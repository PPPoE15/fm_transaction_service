"""Индекс операций: соответствие ORM, сохранность данных и обратимость миграций."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

INDEX_NAME = "ix_transactions_user_uid_transaction_date"


def migration_config() -> Config:
    """Создаёт конфигурацию миграций из текущего checkout для тестового Postgres."""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[3] / "migrations"))
    return config


def index_columns(connection: Connection) -> list[str | None] | None:
    """Читает фактический порядок колонок составного индекса в Postgres."""
    for index in inspect(connection).get_indexes("transactions"):
        if index["name"] == INDEX_NAME:
            assert not index["unique"]
            return list(index["column_names"])
    return None


@pytest.mark.db
async def test_index_migration_preserves_data_and_matches_metadata(db_engine: AsyncEngine) -> None:
    """Upgrade/downgrade меняют только индекс, ORM и Alembic не расходятся."""
    config = migration_config()
    owner, category, transaction = uuid4(), uuid4(), uuid4()
    async with db_engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO categories (uid,user_uid,name,category_type) VALUES (:uid,:owner,'Еда','outcome')"),
            {"uid": category, "owner": owner},
        )
        await connection.execute(
            text(
                "INSERT INTO transactions "
                "(uid,user_uid,category_uid,transaction_date,money_sum,transaction_type,version) "
                "VALUES (:uid,:owner,:category,'2026-01-01',100,'outcome',7)"
            ),
            {"uid": transaction, "owner": owner, "category": category},
        )
    try:
        async with db_engine.connect() as connection:
            assert await connection.run_sync(index_columns) == ["user_uid", "transaction_date"]
        await asyncio.to_thread(command.check, config)
        await asyncio.to_thread(command.downgrade, config, "a99b102c0001")
        async with db_engine.connect() as connection:
            assert await connection.run_sync(index_columns) is None
            row = (await connection.execute(text("SELECT uid,money_sum,version FROM transactions"))).one()
            assert tuple(row) == (transaction, 100, 7)
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    async with db_engine.connect() as connection:
        assert await connection.run_sync(index_columns) == ["user_uid", "transaction_date"]
        row = (await connection.execute(text("SELECT uid,money_sum,version FROM transactions"))).one()
        assert tuple(row) == (transaction, 100, 7)


@pytest.mark.db
async def test_full_migration_chain_round_trip(db_engine: AsyncEngine) -> None:
    """Полная цепочка откатывается до base и повторно создаёт согласованную схему."""
    config = migration_config()
    try:
        await asyncio.to_thread(command.downgrade, config, "base")
        async with db_engine.connect() as connection:
            assert (await connection.execute(text("SELECT to_regclass('transactions')"))).scalar_one() is None
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.check, config)
