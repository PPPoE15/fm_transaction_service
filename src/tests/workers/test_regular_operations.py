"""Проверки запуска и остановки воркера регулярных операций."""

import os
from asyncio import Event
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from apps.config import DBSettings
from apps.modules.planning.application.regular import RegularCommands
from apps.workers import regular_operations


def test_invalid_database_settings_do_not_disclose_password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Не выводить пароль в ошибке загрузки настроек БД при старте воркера."""
    for key in os.environ:
        if key.startswith("DB_"):
            monkeypatch.delenv(key)
    marker = "private-test-db-value"
    monkeypatch.setenv("DB_PASSWORD", marker)
    with pytest.raises(ValidationError, match="PORT") as error:
        DBSettings(_env_file=None, _secrets_dir=tmp_path)
    assert marker not in str(error.value)
    assert "input_value" not in str(error.value)


async def test_stop_does_not_read_next_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Завершить проход после текущей команды, не читая следующую страницу."""
    stopped = Event()
    owner, uid = uuid4(), uuid4()
    today = date(2026, 11, 12)

    async def candidates(_sessions: async_sessionmaker[AsyncSession], _today: date) -> AsyncIterator[tuple[UUID, UUID]]:
        """Зафиксировать чтение после завершения единственной операции."""
        yield owner, uid
        pytest.fail("После остановки следующая страница не читается")

    async def generate(_self: RegularCommands, _owner: UUID, _uid: UUID, _today: date) -> int:
        """Получить сигнал остановки во время текущей команды."""
        stopped.set()
        return 1

    monkeypatch.setattr(regular_operations, "generation_candidates", candidates)
    monkeypatch.setattr(RegularCommands, "generate", generate)
    assert await regular_operations.extend_plans(today, stopped) == 1


@pytest.mark.db
async def test_readiness_marks_reachable_database(db_engine: AsyncEngine, tmp_path: Path) -> None:
    """Подтвердить готовность после подключения к мигрированной БД."""
    path = tmp_path / "ready"
    await regular_operations.mark_ready(path)
    assert path.is_file()
