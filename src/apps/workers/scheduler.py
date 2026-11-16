"""Календарное расписание фоновых задач."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True, slots=True)
class DailyJob:
    """Ежедневная задача с собственным временем и запуском при старте."""

    name: str
    at: time
    run: Callable[[asyncio.Event], Awaitable[None]]
    run_at_startup: bool = False


def next_run(at: time, now: datetime) -> datetime:
    """Вернуть ближайший будущий момент запуска по Москве."""
    local = now.astimezone(MOSCOW)
    deadline = datetime.combine(local.date(), at, MOSCOW)
    return deadline if deadline > local else deadline + timedelta(days=1)


async def run_jobs(jobs: Sequence[DailyJob], stopped: asyncio.Event, *, now: Callable[[], datetime]) -> None:
    """Обслуживать расписание до сигнала остановки, выполняя задачи последовательно."""
    started_at = now()
    deadlines = [next_run(job.at, started_at) for job in jobs]
    for job in jobs:
        if stopped.is_set():
            return
        if job.run_at_startup:
            await job.run(stopped)

    while jobs and not stopped.is_set():
        index = min(range(len(jobs)), key=deadlines.__getitem__)
        deadline = deadlines[index]
        delay = (deadline.astimezone(UTC) - now().astimezone(UTC)).total_seconds()
        if delay > 0:
            try:
                await asyncio.wait_for(stopped.wait(), timeout=min(delay, 60))
            except TimeoutError:
                continue
            return
        job = jobs[index]
        await job.run(stopped)
        deadlines[index] = next_run(job.at, max(deadline, now()))
