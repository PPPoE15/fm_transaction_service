"""Дневной общий остаток: восстановление истории от стартовой суммы."""

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Literal

from pydantic import ConfigDict

from apps.shared.schemas import Base


class BalanceHistoryPoint(Base):
    """Остаток на конец дня, неизвестный только до нижней границы истории."""

    model_config = ConfigDict(extra="forbid")
    date: date
    balance: int | None


class BalanceHistory(Base):
    """Дневной ряд с явно заданными валютой, единицами и календарём."""

    model_config = ConfigDict(extra="forbid")
    date_from: date
    date_to: date
    history_start_date: date
    starting_balance_date: date
    currency: Literal["RUB"] = "RUB"
    unit: Literal["rubles"] = "rubles"
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    points: list[BalanceHistoryPoint]


def build_balance_history(
    date_from: date,
    date_to: date,
    balance_date: date,
    amount: int,
    daily_changes: Mapping[date, int],
) -> BalanceHistory:
    """
    Построить дневной ряд вперёд и назад от стартового остатка на конец дня.

    Args:
        date_from: Первый день ряда.
        date_to: Последний день ряда включительно.
        balance_date: Дата стартового остатка.
        amount: Стартовая сумма в рублях.
        daily_changes: Доходы минус расходы по дням всей истории пользователя до момента запроса.
            Дни с нулевым итогом также присутствуют, если в них были операции.
    """
    history_start = min(balance_date, max(date(2000, 1, 1), min(daily_changes, default=balance_date)))
    # Остаток на конец дня перед date_from. Затем движение каждого дня учитывается один раз.
    balance = (
        amount
        + sum(value for day, value in daily_changes.items() if balance_date < day < date_from)
        - sum(value for day, value in daily_changes.items() if date_from <= day <= balance_date)
    )
    points = []
    for offset in range((date_to - date_from).days + 1):
        day = date_from + timedelta(days=offset)
        balance += daily_changes.get(day, 0)
        points.append(BalanceHistoryPoint(date=day, balance=None if day < history_start else balance))
    return BalanceHistory(
        date_from=date_from,
        date_to=date_to,
        history_start_date=history_start,
        starting_balance_date=balance_date,
        points=points,
    )
