from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.postgres import PostgresContainer

from apps.config import db_settings
from apps.shared.db.session import async_engine, async_session_factory
from apps.web.main import app
from tests import PRIVATE_KEY

TokenFactory = Callable[..., str]


@pytest.fixture
def make_token() -> TokenFactory:
    """Фабрика access-токенов в формате сервиса авторизации (RS256, claims `sub` и `exp`)."""

    def _make_token(
        user_uid: UUID | str | None = None,
        *,
        expires_in: timedelta = timedelta(minutes=5),
        key: bytes | str = PRIVATE_KEY,
        algorithm: str = "RS256",
        extra_claims: dict[str, Any] | None = None,
        drop_claims: tuple[str, ...] = (),
    ) -> str:
        payload: dict[str, Any] = {
            "sub": str(user_uid or uuid4()),
            "exp": datetime.now(UTC) + expires_in,
            **(extra_claims or {}),
        }
        for claim in drop_claims:
            payload.pop(claim, None)
        return jwt.encode(payload, key=key, algorithm=algorithm)

    return _make_token


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """
    HTTP-клиент API приложения: пути в тестах задаются без префикса `/transaction`, его добавляет `base_url`.

    Ошибки приложения возвращаются ответом 500, а не исключением в тесте.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test/transaction") as http_client:
        yield http_client


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    """
    Postgres в Docker на всю сессию тестов, с применёнными миграциями.

    Без запущенного Docker тесты с БД падают с понятным сообщением, а не пропускаются молча.
    Быстрый прогон без БД: `poetry run pytest -m "not db"`.
    """
    container = PostgresContainer("postgres:16", driver="asyncpg")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001 — testcontainers/docker бросают ошибки разных типов
        pytest.fail(
            f"Не удалось запустить Postgres в Docker для тестов с маркером db: {exc}. "
            'Запустите Docker или исключите эти тесты: pytest -m "not db".',
            pytrace=False,
        )
    try:
        dsn = container.get_connection_url()
        # migrations/env.py берёт DSN из db_settings — подменяем его на адрес контейнера.
        db_settings.DSN = dsn
        alembic_config = Config()
        alembic_config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
        command.upgrade(alembic_config, "head")
        yield dsn
    finally:
        container.stop()


@pytest.fixture
async def db_engine(postgres_dsn: str) -> AsyncIterator[AsyncEngine]:
    """
    Подключить фабрику сессий приложения к тестовому Postgres; после теста очистить таблицы.

    NullPool — соединения не переживают event loop теста (у pytest-asyncio он свой на каждый тест).
    """
    engine = create_async_engine(postgres_dsn, poolclass=pool.NullPool)
    async_session_factory.configure(bind=engine)
    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE transactions, categories"))
        async_session_factory.configure(bind=async_engine)
        await engine.dispose()
