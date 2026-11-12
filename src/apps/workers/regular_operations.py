"""Точка входа воркера продления планов регулярных операций."""

import asyncio
import logging
import os
import re
import signal
from datetime import date, datetime, time

from sqlalchemy.exc import SQLAlchemyError

from apps import db_models
from apps.modules.planning.application.regular import RegularCommands
from apps.modules.planning.infrastructure.generation_queries import generation_candidates
from apps.modules.planning.infrastructure.uow import PlanUnitOfWork
from apps.shared.db.session import async_engine, async_session_factory
from apps.shared.exceptions import BaseError
from apps.workers.scheduler import MOSCOW, DailyJob, run_jobs

logger = logging.getLogger(__name__)


def moscow_now() -> datetime:
    """Вернуть текущее время в Москве."""
    return datetime.now(MOSCOW)


def scheduled_time(value: str) -> time:
    """Разобрать настройку ежедневного запуска в формате ЧЧ:ММ."""
    if re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value) is None:
        msg = "REGULAR_OPERATIONS_RUN_AT: требуется время по Москве в формате ЧЧ:ММ"
        raise ValueError(msg)
    return time.fromisoformat(value)


async def extend_plans(today: date, stopped: asyncio.Event) -> int:
    """Продлить горизонт за один проход, сохранив результат каждой команды отдельно."""
    commands = RegularCommands(PlanUnitOfWork(async_session_factory), lambda: today)
    processed = created = failures = 0
    async for owner, uid in generation_candidates(async_session_factory, today):
        if stopped.is_set():
            break
        processed += 1
        try:
            created += await commands.generate(owner, uid, today)
        except (BaseError, SQLAlchemyError, OSError, ValueError) as exc:
            failures += 1
            logger.error("Ошибка продления регулярной операции %s (%s)", uid, type(exc).__name__)
    logger.info(
        "Проход продления планов: дата=%s обработано=%d создано=%d ошибок=%d остановка=%s",
        today,
        processed,
        created,
        failures,
        stopped.is_set(),
    )
    return created


async def _extend_today(stopped: asyncio.Event) -> None:
    """Зафиксировать дату прохода и передать её всем командам."""
    await extend_plans(moscow_now().date(), stopped)


async def _main(at: time) -> None:
    """Настроить остановку процесса и запустить ежедневное расписание."""
    db_models.AsyncBase.registry.configure()
    async_engine.echo = False
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    logger.info("Воркер продления планов запущен, расписание %s по Москве", at.isoformat(timespec="minutes"))
    try:
        jobs = [DailyJob("regular_operations", at, _extend_today, run_at_startup=True)]
        await run_jobs(jobs, stopped, now=moscow_now)
    except (SQLAlchemyError, OSError) as exc:
        logger.error("Не удалось завершить проход продления планов (%s)", type(exc).__name__)
        raise SystemExit(1) from None
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main(scheduled_time(os.environ.get("REGULAR_OPERATIONS_RUN_AT", "03:00"))))
