"""Представления регулярной операции и результата преобразования."""

from datetime import date
from typing import Literal
from uuid import UUID

from apps.modules.planning.application.schemas import CategoryRef, PlanView
from apps.modules.planning.domain.regular import RegularOperationRule
from apps.modules.planning.domain.schedule import Frequency
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base


class RegularOperationItem(Base):
    """Публичные поля регулярной операции без календаря запроса."""

    uid: UUID
    money_sum: int
    category: CategoryRef
    description: str | None
    transaction_type: TransactionType
    frequency: Frequency
    first_date: date
    end_date: date | None
    version: int
    status: Literal["active", "ended"]
    source_plan_uid: UUID | None

    @classmethod
    def fields(cls, rule: RegularOperationRule, category_name: str, today: date) -> dict[str, object]:
        """Сформировать общие поля списка и деталей."""
        return rule.model_dump(include=set(RegularOperationItem.model_fields) - {"category", "status"}) | {
            "category": CategoryRef(uid=rule.require_category_uid(), name=category_name),
            "status": "ended" if rule.end_date is not None and rule.end_date < today else "active",
        }


class RegularOperationView(RegularOperationItem):
    """Одна регулярная операция с календарём запроса."""

    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"

    @classmethod
    def build(cls, rule: RegularOperationRule, category_name: str, today: date) -> "RegularOperationView":
        """Собрать детали из снимка команды или запроса."""
        return cls.model_validate(cls.fields(rule, category_name, today) | {"today": today})


class RegularOperationList(Base):
    """Страница регулярных операций с общей датой и часовым поясом."""

    total: int
    next_skip: int | None
    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    content: list[RegularOperationItem]


class ConversionResult(Base):
    """Регулярная операция, способ использования источника и первый платёж."""

    operation: RegularOperationView
    source_plan_uid: UUID
    source_disposition: Literal["attached", "unchanged"]
    first_plan: PlanView | None
