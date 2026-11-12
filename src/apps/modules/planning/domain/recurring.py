"""Данные серии и правила её календаря."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from apps.modules.planning.domain.errors import RecurringViolationError
from apps.modules.planning.domain.model import PlanInput
from apps.modules.planning.domain.schedule import Frequency, RecurringSchedule, generation_horizon
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base

SeriesStatus = Literal["active", "ended", "deleted"]


def series_status(end_date: date | None, deleted_at: datetime | None, today: date) -> SeriesStatus:
    """Вычислить состояние ссылки на серию на заданную дату."""
    if deleted_at is not None:
        return "deleted"
    return "ended" if end_date is not None and end_date < today else "active"


class Series(Base):
    """Параметры и последняя обработанная граница серии."""

    uid: UUID
    user_uid: UUID
    category_uid: UUID | None
    money_sum: int
    description: str | None
    transaction_type: TransactionType
    frequency: Frequency
    first_date: date
    end_date: date | None
    version: int = 1
    source_plan_uid: UUID | None = None
    generated_through: date | None = None
    deleted_at: datetime | None = None

    def schedule(self) -> RecurringSchedule:
        """Построить календарь из сохранённых условий."""
        return RecurringSchedule(self.first_date, self.frequency, self.end_date)

    def horizon(self, today: date) -> date:
        """Ограничить горизонт включительной датой окончания серии."""
        horizon = generation_horizon(today)
        return min(horizon, self.end_date) if self.end_date is not None else horizon

    def validate_schedule(self, today: date, previous: date | None = None) -> None:
        """Привязать календарную ошибку к полю запроса."""
        try:
            schedule = self.schedule()
        except ValueError as exc:
            raise RecurringViolationError(str(exc), field="end_date") from exc
        try:
            schedule.validate_first_date(today, previous_first_date=previous)
        except ValueError as exc:
            raise RecurringViolationError(str(exc), field="first_date") from exc

    def payment(self, when: date) -> PlanInput:
        """Построить исходные значения платежа по серии."""
        return PlanInput(
            planned_date=when,
            category_uid=self.require_category_uid(),
            money_sum=self.money_sum,
            description=self.description,
        )

    def require_category_uid(self) -> UUID:
        """Получить категорию действующей записи серии."""
        if self.category_uid is None:
            msg = "У доступной серии отсутствует категория"
            raise ValueError(msg)
        return self.category_uid


class Position(Base):
    """Исходная дата и ссылка на план, включая отдельно удалённый платёж."""

    operation_uid: UUID
    scheduled_date: date
    plan_uid: UUID | None
    is_exception: bool = False
