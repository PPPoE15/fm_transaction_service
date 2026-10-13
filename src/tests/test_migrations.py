"""Миграции на данных: обновление схемы не теряет и не ломает существующие записи."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

BEFORE_FM_41 = "5b7e2c1d9a40"
FM_41 = "8d3f6a2b1c47"
MAX_NAME_LENGTH = 64


@pytest.fixture
def alembic_config(postgres_dsn: str) -> Iterator[Config]:
    """
    Конфигурация Alembic тестового Postgres; после теста схема снова на `head`, а таблицы пусты.

    Тест синхронный: `migrations/env.py` сам запускает event loop (`asyncio.run`).
    """
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    try:
        yield config
    finally:
        command.upgrade(config, "head")
        _run(postgres_dsn, "TRUNCATE transactions, categories, starting_balances")


def _run(dsn: str, sql: str, params: list[dict[str, Any]] | None = None) -> list[Any]:
    async def _execute() -> list[Any]:
        engine = create_async_engine(dsn, poolclass=pool.NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(sql), params or [{}])
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(_execute())


def _insert_categories(dsn: str, rows: list[tuple[UUID, UUID, str, str, int]]) -> None:
    _run(
        dsn,
        "INSERT INTO categories (uid, user_uid, name, money_plan, category_type, description) "
        "VALUES (:uid, :user_uid, :name, :money_plan, :category_type, NULL)",
        [
            {"uid": uid, "user_uid": user_uid, "name": name, "category_type": category_type, "money_plan": plan}
            for uid, user_uid, name, category_type, plan in rows
        ],
    )


def _names(dsn: str) -> dict[UUID, str]:
    return {row.uid: row.name for row in _run(dsn, "SELECT uid, name FROM categories")}


@pytest.mark.db
def test_fm_41_renames_existing_duplicates(postgres_dsn: str, alembic_config: Config) -> None:
    """
    Дубликаты «пользователь + тип + название», созданные до FM-41, не удаляются и не роняют миграцию.

    Первая статья группы (по uid) сохраняет название, остальные — с суффиксом и не длиннее 64 символов.
    Совпадение названия с другим типом или у другого пользователя дубликатом не считается.
    """
    command.downgrade(alembic_config, BEFORE_FM_41)
    user, other_user = uuid4(), uuid4()
    first, second, third = sorted([uuid4(), uuid4(), uuid4()])
    long_first, long_second = sorted([uuid4(), uuid4()])
    income, others = uuid4(), uuid4()
    long_name = "я" * MAX_NAME_LENGTH
    _insert_categories(
        postgres_dsn,
        [
            (first, user, "Еда", "outcome", 1),
            (second, user, "Еда", "outcome", 2),
            (third, user, "Еда", "outcome", 3),
            (income, user, "Еда", "income", 4),
            (others, other_user, "Еда", "outcome", 5),
            (long_first, user, long_name, "outcome", 6),
            (long_second, user, long_name, "outcome", 7),
        ],
    )

    command.upgrade(alembic_config, FM_41)

    names = _names(postgres_dsn)
    assert set(names) == {first, second, third, income, others, long_first, long_second}
    assert (names[first], names[income], names[others], names[long_first]) == ("Еда", "Еда", "Еда", long_name)
    assert names[second] == f"Еда (дубликат {str(second)[:8]})"
    assert names[third] == f"Еда (дубликат {str(third)[:8]})"
    suffix = f" (дубликат {str(long_second)[:8]})"
    assert names[long_second] == long_name[: MAX_NAME_LENGTH - len(suffix)] + suffix
    assert len(names[long_second]) == MAX_NAME_LENGTH


@pytest.mark.db
def test_fm_41_plan_becomes_optional_and_downgrade_restores_zero(postgres_dsn: str, alembic_config: Config) -> None:
    """План после FM-41 может быть NULL; откат переводит NULL в 0 (прежняя схема его не допускает)."""
    command.upgrade(alembic_config, FM_41)
    without_plan, with_plan = uuid4(), uuid4()
    _run(
        postgres_dsn,
        "INSERT INTO categories (uid, user_uid, name, money_plan, category_type) "
        "VALUES (:uid, :user_uid, :name, :money_plan, 'outcome')",
        [
            {"uid": without_plan, "user_uid": uuid4(), "name": "Без плана", "money_plan": None},
            {"uid": with_plan, "user_uid": uuid4(), "name": "С планом", "money_plan": 5},
        ],
    )

    command.downgrade(alembic_config, BEFORE_FM_41)

    plans = {row.uid: row.money_plan for row in _run(postgres_dsn, "SELECT uid, money_plan FROM categories")}
    assert plans == {without_plan: 0, with_plan: 5}
