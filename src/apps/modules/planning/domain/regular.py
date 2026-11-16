"""Правило регулярной операции и её календарь."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from apps.modules.planning.domain.errors import RegularViolationError
from apps.modules.planning.domain.model import PlanInput
from apps.modules.planning.domain.schedule import Frequency, RegularSchedule, generation_horizon
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base

RegularOperationStatus = Literal["active", "ended", "deleted"]


def regular_operation_status(end_date: date | None, deleted_at: datetime | None, today: date) -> RegularOperationStatus:
    """Вычислить состояние ссылки на регулярную операцию на заданную дату."""
    if deleted_at is not None:
        return "deleted"
    return "ended" if end_date is not None and end_date < today else "active"


class RegularOperationRule(Base):
    """Параметры и последняя обработанная граница регулярной операции."""

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

    def schedule(self) -> RegularSchedule:
        """Построить календарь из сохранённых условий."""
        return RegularSchedule(self.first_date, self.frequency, self.end_date)

    def horizon(self, today: date) -> date:
        """Ограничить горизонт включительной датой окончания регулярной операции."""
        horizon = generation_horizon(today)
        return min(horizon, self.end_date) if self.end_date is not None else horizon

    def validate_schedule(self, today: date, previous: date | None = None) -> None:
        """Привязать календарную ошибку к полю запроса."""
        try:
            schedule = self.schedule()
        except ValueError as exc:
            raise RegularViolationError(str(exc), field="end_date") from exc
        try:
            schedule.validate_first_date(today, previous_first_date=previous)
        except ValueError as exc:
            raise RegularViolationError(str(exc), field="first_date") from exc

    def payment(self, when: date) -> PlanInput:
        """Построить исходные значения платежа по регулярной операции."""
        return PlanInput(
            planned_date=when,
            category_uid=self.require_category_uid(),
            money_sum=self.money_sum,
            description=self.description,
        )

    def require_category_uid(self) -> UUID:
        """Получить категорию действующей записи регулярной операции."""
        if self.category_uid is None:
            msg = "У доступной регулярной операции отсутствует категория"
            raise ValueError(msg)
        return self.category_uid


class Position(Base):
    """Исходная дата и ссылка на план, включая отдельно удалённый платёж."""

    operation_uid: UUID
    scheduled_date: date
    plan_uid: UUID | None
    is_exception: bool = False
