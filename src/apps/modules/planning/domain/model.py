"""Агрегат плана и разрешённые изменения его исходных полей."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field, model_validator

from apps.modules.planning.domain.errors import CompletedPlanError, InvalidPlanDateError, PlanVersionError
from apps.shared.api_types import DescriptionIn
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base

Money = Annotated[int, Field(ge=1, le=1_000_000_000, strict=True)]
MAX_PLANS = 100_000


class PlanInput(Base):
    """Полный набор пользовательских полей для нового плана."""

    model_config = ConfigDict(extra="forbid")
    planned_date: date
    money_sum: Money
    category_uid: UUID
    description: DescriptionIn | None = None


class PlanChanges(Base):
    """Только явно изменённые поля; тип плана недоступен для изменения."""

    model_config = ConfigDict(extra="forbid")
    planned_date: date | None = None
    money_sum: Money | None = None
    category_uid: UUID | None = None
    description: DescriptionIn | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        """Запретить пустые изменения и null вне комментария."""
        if not self.model_fields_set:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        for name in self.model_fields_set - {"description"}:
            if getattr(self, name) is None:
                msg = f"Поле {name} не может быть null"
                raise ValueError(msg)
        return self


class Plan(PlanInput):
    """Исходный план, версия и связь с фактом независимо от его дальнейших изменений."""

    uid: UUID
    user_uid: UUID
    transaction_type: TransactionType
    version: int = Field(default=1, ge=1)
    status: Literal["pending", "completed"] = "pending"
    completed_at: datetime | None = None
    transaction_uid: UUID | None = None
    category_name_snapshot: str | None = None

    @classmethod
    def create(cls, user_uid: UUID, transaction_type: TransactionType, values: PlanInput, today: date) -> Self:
        """Создать план с новой идентичностью, не создавая фактическую операцию."""
        cls.validate_date(values.planned_date, today)
        return cls(
            uid=uuid4(), user_uid=user_uid, transaction_type=transaction_type, **values.model_dump()
        ).normalized()

    def normalized(self) -> Self:
        """Сохранить пустой комментарий как отсутствие значения."""
        self.description = self.description or None
        return self

    @staticmethod
    def validate_date(value: date, today: date) -> None:
        """Проверить календарный диапазон и дату относительно серверного сегодня."""
        if not max(date(2000, 1, 1), today) <= value <= date(2099, 12, 31):
            raise InvalidPlanDateError

    def check_version(self, expected_version: int) -> None:
        """Проверить версию перед записью или удалением независимо от статуса."""
        if self.version != expected_version:
            raise PlanVersionError

    def ensure_editable(self, expected_version: int) -> None:
        """Проверить статус раньше версии, как предписывает контракт."""
        if self.status == "completed":
            raise CompletedPlanError
        self.check_version(expected_version)

    def update(self, changes: PlanChanges, expected_version: int, today: date) -> None:
        """Атомарно проверить и применить только явно указанные поля."""
        self.ensure_editable(expected_version)
        self.validate_date(changes.planned_date or self.planned_date, today)
        for name in changes.model_fields_set:
            setattr(self, name, getattr(changes, name))
        self.normalized()
        self.version += 1
