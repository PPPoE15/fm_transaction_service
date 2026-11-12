"""Публичные read-модели планов."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.regular import (
    Position,
    RegularTransactionRule,
    RegularTransactionStatus,
    regular_transaction_status,
)
from apps.modules.transaction import TransactionSchema
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base


class CategoryRef(Base):
    """Идентификатор и имя текущей либо зафиксированной категории."""

    uid: UUID
    name: str


class RecurrenceView(Base):
    """Данные позиции, сохраняемые после переноса и подтверждения."""

    operation_uid: UUID
    scheduled_date: date
    operation_status: RegularTransactionStatus
    is_exception: bool


class PlanView(Base):
    """План без приватного UID владельца, с календарём и состоянием ссылки."""

    uid: UUID
    planned_date: date
    money_sum: int
    category: CategoryRef
    transaction_type: TransactionType
    description: str | None
    version: int
    status: Literal["pending", "completed"]
    completed_at: datetime | None
    transaction_uid: UUID | None
    transaction_state: Literal["none", "available", "deleted"]
    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"

    recurrence: RecurrenceView | None = Field(default=None, exclude_if=lambda value: value is None)

    @classmethod
    def build(
        cls, plan: Plan, category_name: str, today: date, link: tuple[Position, RegularTransactionRule] | None = None
    ) -> "PlanView":
        """Представить исходные значения и вычислить наличие связанного факта."""
        recurrence = None
        if link is not None:
            position, rule = link
            recurrence = RecurrenceView(
                operation_uid=position.operation_uid,
                scheduled_date=position.scheduled_date,
                operation_status=regular_transaction_status(rule.end_date, rule.deleted_at, today),
                is_exception=position.is_exception,
            )
        return cls(
            recurrence=recurrence,
            **plan.model_dump(exclude={"user_uid", "category_uid", "category_name_snapshot"}),
            category=CategoryRef(uid=plan.category_uid, name=plan.category_name_snapshot or category_name),
            today=today,
            transaction_state="none"
            if plan.status == "pending"
            else "available"
            if plan.transaction_uid
            else "deleted",
        )


class PlanList(Base):
    """Страница из одного снимка данных и одного календарного дня."""

    total: int
    due_count: int
    next_skip: int | None
    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    content: list[PlanView]


class PlanConfirmation(Base):
    """Снимок атомарно выполненного плана и созданного факта."""

    plan: PlanView
    transaction: TransactionSchema
