"""Проверки расписания фоновых задач."""

import asyncio
from asyncio import Event
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from apps.workers.scheduler import DailyJob, next_run, run_jobs

MOSCOW = ZoneInfo("Europe/Moscow")


def test_next_run_uses_moscow_calendar() -> None:
    """Рассчитать ближайший будущий запуск по московскому календарю."""
    assert next_run(time(3), datetime(2026, 11, 12, 2, 59, tzinfo=MOSCOW)) == datetime(2026, 11, 12, 3, tzinfo=MOSCOW)
    assert next_run(time(3), datetime(2026, 11, 12, 3, tzinfo=MOSCOW)) == datetime(2026, 11, 13, 3, tzinfo=MOSCOW)


async def test_startup_and_independent_schedules() -> None:
    """Выполнить стартовую задачу и последующие запуски в их собственное время."""
    stopped = Event()
    current = datetime(2026, 11, 12, 2, tzinfo=MOSCOW)
    calls: list[str] = []

    def now() -> datetime:
        """Вернуть время сценария."""
        return current

    async def generate(_stop: Event) -> None:
        """Перевести часы за срок очередной задачи."""
        nonlocal current
        calls.append("generate")
        current = current.replace(hour=current.hour + 1)

    async def another(stop: Event) -> None:
        """Завершить цикл после второй задачи."""
        calls.append("another")
        stop.set()

    await run_jobs(
        [DailyJob("generate", time(3), generate, run_at_startup=True), DailyJob("another", time(4), another)],
        stopped,
        now=now,
    )

    assert calls == ["generate", "generate", "another"]


async def test_stop_interrupts_wait() -> None:
    """Остановка прерывает ожидание и не запускает запланированную задачу."""
    stopped = Event()
    current = datetime(2026, 11, 12, 2, tzinfo=MOSCOW)

    def now() -> datetime:
        """Вернуть время задолго до следующего запуска."""
        return current

    async def generate(_stop: Event) -> None:
        """Зафиксировать неожиданный запуск."""
        pytest.fail("Задача не должна запускаться")

    runner = asyncio.create_task(run_jobs([DailyJob("generate", time(3), generate)], stopped, now=now))
    await asyncio.sleep(0)
    stopped.set()
    await asyncio.wait_for(runner, timeout=1)
