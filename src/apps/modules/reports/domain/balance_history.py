"""Дневной общий остаток: перенос суммы и неизвестные дни до стартовой даты."""

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Literal

from pydantic import ConfigDict

from apps.shared.schemas import Base


class BalanceHistoryPoint(Base):
    """Остаток на день; до стартовой даты значение неизвестно."""

    model_config = ConfigDict(extra="forbid")
    date: date
    balance: int | None


class BalanceHistory(Base):
    """Дневной ряд с явно заданными валютой, единицами и календарём."""

    model_config = ConfigDict(extra="forbid")
    date_from: date
    date_to: date
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
    Построить дневной ряд из стартового остатка и чистого движения денег.

    Args:
        date_from: Первый день ряда.
        date_to: Последний день ряда включительно.
        balance_date: Дата стартового остатка.
        amount: Стартовая сумма в рублях.
        daily_changes: Доходы минус расходы по дням, с уже отсечёнными будущими операциями.
    """
    balance = amount + sum(value for day, value in daily_changes.items() if balance_date < day < date_from)
    points = []
    for offset in range((date_to - date_from).days + 1):
        day = date_from + timedelta(days=offset)
        if day > balance_date:
            balance += daily_changes.get(day, 0)
        points.append(BalanceHistoryPoint(date=day, balance=None if day < balance_date else balance))
    return BalanceHistory(date_from=date_from, date_to=date_to, points=points)
