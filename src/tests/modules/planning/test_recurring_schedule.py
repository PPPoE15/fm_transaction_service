"""Проверки календаря регулярных платежей."""

from datetime import date

import pytest

from apps.modules.planning.domain.schedule import Frequency, RecurringSchedule, generation_horizon


@pytest.mark.parametrize(
    ("frequency", "first_date", "until", "expected"),
    [
        (Frequency.DAILY, "2028-02-28", "2028-03-01", ["2028-02-28", "2028-02-29", "2028-03-01"]),
        (Frequency.WEEKLY, "2028-02-23", "2028-03-08", ["2028-02-23", "2028-03-01", "2028-03-08"]),
        (Frequency.MONTHLY, "2027-01-31", "2027-03-31", ["2027-01-31", "2027-02-28", "2027-03-31"]),
        (
            Frequency.YEARLY,
            "2024-02-29",
            "2028-02-29",
            ["2024-02-29", "2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29"],
        ),
    ],
)
def test_frequency(frequency: Frequency, first_date: str, until: str, expected: list[str]) -> None:
    """Проверить шаги всех периодичностей и возврат к исходному якорю."""
    first = date.fromisoformat(first_date)
    schedule = RecurringSchedule(first, frequency)
    assert list(schedule.dates_between(first, date.fromisoformat(until))) == [date.fromisoformat(x) for x in expected]


def test_inclusive_end_and_lower_bound() -> None:
    """Окончание включительно, нижняя граница не сдвигает недельный якорь."""
    schedule = RecurringSchedule(date(2026, 11, 12), Frequency.WEEKLY, date(2026, 11, 26))
    assert list(schedule.dates_between(date(2026, 11, 13), date(2026, 12, 1))) == [
        date(2026, 11, 19),
        date(2026, 11, 26),
    ]
    assert list(schedule.dates_between(date(2026, 11, 27), date(2026, 12, 1))) == []


def test_horizon() -> None:
    """Горизонт ограничен двенадцатью календарными месяцами и последней датой контракта."""
    assert generation_horizon(date(2028, 2, 29)) == date(2029, 2, 28)
    assert generation_horizon(date(2099, 12, 30)) == date(2099, 12, 31)
    schedule = RecurringSchedule(date(2028, 3, 1), Frequency.DAILY)
    assert list(schedule.dates_between(date(2027, 2, 28), generation_horizon(date(2027, 2, 28)))) == []


def test_invalid_dates() -> None:
    """Отклонить неверный диапазон, а прежний прошедший якорь разрешить сохранить."""
    with pytest.raises(ValueError, match="окончания"):
        RecurringSchedule(date(2026, 11, 12), Frequency.DAILY, date(2026, 11, 11))
    with pytest.raises(ValueError, match="2000"):
        RecurringSchedule(date(1999, 12, 31), Frequency.DAILY)
    schedule = RecurringSchedule(date(2026, 11, 12), Frequency.DAILY)
    today = date(2026, 11, 13)
    with pytest.raises(ValueError, match="сегодня"):
        schedule.validate_first_date(today)
    schedule.validate_first_date(today, previous_first_date=schedule.first_date)
