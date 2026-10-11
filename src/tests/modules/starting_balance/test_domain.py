"""Правила стартового остатка: дата по умолчанию и допустимый диапазон дат."""

from datetime import date
from uuid import uuid4

import pytest

from apps.modules.starting_balance.domain import InvalidBalanceDateError, StartingBalance

OWNER = uuid4()
TODAY = date(2026, 3, 15)


def test_create_with_explicit_date() -> None:
    """Сумма и дата сохраняются как переданы, сумма может быть отрицательной."""
    starting_balance = StartingBalance.create(user_uid=OWNER, amount=-500, balance_date=date(2026, 1, 1), today=TODAY)

    assert (starting_balance.user_uid, starting_balance.amount, starting_balance.balance_date) == (
        OWNER,
        -500,
        date(2026, 1, 1),
    )


def test_default_date_is_yesterday() -> None:
    """Без даты остаток считается на конец вчерашнего дня."""
    starting_balance = StartingBalance.create(user_uid=OWNER, amount=100, balance_date=None, today=TODAY)

    assert starting_balance.balance_date == date(2026, 3, 14)


def test_default_date_crosses_year_boundary() -> None:
    """1 января «вчера» — 31 декабря прошлого года."""
    starting_balance = StartingBalance.create(user_uid=OWNER, amount=100, balance_date=None, today=date(2026, 1, 1))

    assert starting_balance.balance_date == date(2025, 12, 31)


@pytest.mark.parametrize("balance_date", [TODAY, date(2000, 1, 1)])
def test_boundary_dates_are_allowed(balance_date: date) -> None:
    """Сегодня и 1 января 2000 года — допустимые даты."""
    starting_balance = StartingBalance.create(user_uid=OWNER, amount=100, balance_date=balance_date, today=TODAY)

    assert starting_balance.balance_date == balance_date


@pytest.mark.parametrize(
    ("balance_date", "today"),
    [
        (date(2026, 3, 16), TODAY),  # завтра
        (date(1999, 12, 31), TODAY),
        (date(2100, 1, 1), date(2100, 1, 2)),  # не позже сегодня, но год вне 2000–2099
    ],
)
def test_out_of_range_dates_are_rejected(balance_date: date, today: date) -> None:
    """Дата позже сегодня или с годом вне 2000–2099 — ошибка `FM-422002` по полю `balance_date`."""
    with pytest.raises(InvalidBalanceDateError) as exc_info:
        StartingBalance.create(user_uid=OWNER, amount=100, balance_date=balance_date, today=today)

    assert (exc_info.value.code, exc_info.value.field) == ("FM-422002", "balance_date")


def test_default_date_out_of_range_is_rejected() -> None:
    """Подставленная по умолчанию дата проверяется так же, как переданная."""
    with pytest.raises(InvalidBalanceDateError):
        StartingBalance.create(user_uid=OWNER, amount=100, balance_date=None, today=date(2000, 1, 1))
