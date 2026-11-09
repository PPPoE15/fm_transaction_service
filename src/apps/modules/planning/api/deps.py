"""Зависимости команд и часов планирования."""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apps.modules.planning.application.commands import PlanCommands
from apps.modules.planning.infrastructure.uow import PlanUnitOfWork
from apps.shared.db.session import async_session_factory


def moscow_today() -> date:
    """Определить дату по серверному московскому календарю."""
    return datetime.now(ZoneInfo("Europe/Moscow")).date()


def get_clock() -> Callable[[], date]:
    """Вернуть часы, чтобы команда могла вызвать их после получения блокировок."""
    return moscow_today


def commands(clock: Callable[[], date]) -> PlanCommands:
    """Собрать команду с отдельной транзакцией и переданными часами."""
    return PlanCommands(PlanUnitOfWork(async_session_factory), clock)
