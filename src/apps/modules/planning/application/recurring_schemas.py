"""Представления серии и результата преобразования."""

from datetime import date
from typing import Literal
from uuid import UUID

from apps.modules.planning.application.schemas import CategoryRef, PlanView
from apps.modules.planning.domain.recurring import Series
from apps.modules.planning.domain.schedule import Frequency
from apps.shared.apps_types import TransactionType
from apps.shared.schemas import Base


class SeriesItem(Base):
    """Публичные поля серии без календаря запроса."""

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
    def fields(cls, series: Series, category_name: str, today: date) -> dict[str, object]:
        """Сформировать общие поля списка и деталей."""
        return series.model_dump(include=set(SeriesItem.model_fields) - {"category", "status"}) | {
            "category": CategoryRef(uid=series.require_category_uid(), name=category_name),
            "status": "ended" if series.end_date is not None and series.end_date < today else "active",
        }


class SeriesView(SeriesItem):
    """Одна серия с календарём запроса."""

    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"

    @classmethod
    def build(cls, series: Series, category_name: str, today: date) -> "SeriesView":
        """Собрать детали из снимка команды или запроса."""
        return cls.model_validate(cls.fields(series, category_name, today) | {"today": today})


class SeriesList(Base):
    """Страница серий с общей датой и часовым поясом."""

    total: int
    next_skip: int | None
    today: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    content: list[SeriesItem]


class ConversionResult(Base):
    """Серия, способ использования источника и первый платёж."""

    operation: SeriesView
    source_plan_uid: UUID
    source_disposition: Literal["attached", "unchanged"]
    first_plan: PlanView | None
