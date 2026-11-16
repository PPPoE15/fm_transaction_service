"""Календарь регулярных платежей без зависимости от текущего времени и хранилища."""

from calendar import monthrange
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

MIN_SCHEDULE_DATE = date(2000, 1, 1)
MAX_SCHEDULE_DATE = date(2099, 12, 31)


class Frequency(StrEnum):
    """Поддерживаемые периодичности календарного расписания."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


def _add_months(anchor: date, months: int) -> date:
    """Прибавить календарные месяцы, ограничив день концом целевого месяца."""
    year, month_index = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
    month = month_index + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def generation_horizon(today: date) -> date:
    """Вернуть включительную границу на двенадцать месяцев от серверного сегодня."""
    if today.year >= MAX_SCHEDULE_DATE.year:
        return MAX_SCHEDULE_DATE
    return _add_months(today, 12)


@dataclass(frozen=True, slots=True)
class RegularSchedule:
    """Хранит исходный календарный якорь и необязательное включительное окончание."""

    first_date: date
    frequency: Frequency
    end_date: date | None = None

    def __post_init__(self) -> None:
        """Проверить границы расписания независимо от даты выполнения команды."""
        if not MIN_SCHEDULE_DATE <= self.first_date <= MAX_SCHEDULE_DATE:
            msg = "Первая дата должна быть в пределах 2000–2099 годов"
            raise ValueError(msg)
        if self.end_date is not None and not self.first_date <= self.end_date <= MAX_SCHEDULE_DATE:
            msg = "Дата окончания должна быть не раньше первой даты и не позже 2099-12-31"
            raise ValueError(msg)

    def validate_first_date(self, today: date, *, previous_first_date: date | None = None) -> None:
        """Разрешить прошлый якорь только при сохранении прежней первой даты."""
        if self.first_date != previous_first_date and self.first_date < today:
            msg = "Первая дата должна быть сегодня или в будущем"
            raise ValueError(msg)

    def dates_between(self, start: date, end: date) -> Iterator[date]:
        """Перечислить позиции внутри включительного диапазона, сохраняя исходный якорь."""
        start = max(start, self.first_date)
        end = min(end, self.end_date or MAX_SCHEDULE_DATE)
        if start > end:
            return

        if self.frequency in (Frequency.DAILY, Frequency.WEEKLY):
            step = 1 if self.frequency is Frequency.DAILY else 7
            elapsed = (start - self.first_date).days
            first_offset = (elapsed + step - 1) // step * step
            for offset in range(first_offset, (end - self.first_date).days + 1, step):
                yield self.first_date + timedelta(days=offset)
            return

        step = 1 if self.frequency is Frequency.MONTHLY else 12
        first_month = self.first_date.year * 12 + self.first_date.month
        start_month = start.year * 12 + start.month
        end_month = end.year * 12 + end.month
        first_offset = (start_month - first_month + step - 1) // step * step
        for offset in range(first_offset, end_month - first_month + 1, step):
            candidate = _add_months(self.first_date, offset)
            if start <= candidate <= end:
                yield candidate
