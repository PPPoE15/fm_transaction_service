"""Зависимости команд и часов планирования."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from apps.modules.planning.application.commands import PlanCommands
from apps.modules.planning.application.confirmation import ConfirmPlanCommand
from apps.modules.planning.application.regular import RegularCommands
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


def utc_now() -> datetime:
    """Получить момент подтверждения в UTC."""
    return datetime.now(UTC)


def get_confirmation_clock() -> Callable[[], datetime]:
    """Передать команде часы для единого момента после ожидания блокировок."""
    return utc_now


def confirmation_command(clock: Callable[[], datetime]) -> ConfirmPlanCommand:
    """Собрать подтверждение с общей сессией планов, фактов и категорий."""
    return ConfirmPlanCommand(PlanUnitOfWork(async_session_factory), clock)


def regular_commands(clock: Callable[[], date]) -> RegularCommands:
    """Собрать команды регулярных операций в отдельной транзакции."""
    return RegularCommands(PlanUnitOfWork(async_session_factory), clock)
