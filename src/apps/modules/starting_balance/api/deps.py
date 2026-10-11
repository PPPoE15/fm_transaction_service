from datetime import date

from apps.modules.starting_balance.application.commands import CreateStartingBalanceCommandHandler
from apps.modules.starting_balance.infrastructure.uow import StartingBalanceUnitOfWork
from apps.shared.datetime_tz import aware_now
from apps.shared.db.session import async_session_factory


def get_today() -> date:
    """
    Текущая дата: от неё считаются дата остатка по умолчанию (вчера) и граница «не позже сегодня».

    Вынесена в зависимость, чтобы команда не брала время сама и в тестах дату можно было подменить.
    """
    # NOTE(FM-37): дата берётся по UTC, как `get_today` в reports (см. NOTE(FM-27) там): в первые часы суток
    # по местному времени (UTC+3: до 03:00) «сегодня» — ещё вчерашний день. Часового пояса пользователя сервис
    # пока не знает.
    return aware_now().date()


def build_create_starting_balance_command_handler() -> CreateStartingBalanceCommandHandler:
    """Построить обработчик задания стартового остатка."""
    return CreateStartingBalanceCommandHandler(
        unit_of_work=StartingBalanceUnitOfWork(
            session_factory=async_session_factory,
        ),
    )
