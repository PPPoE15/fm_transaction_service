"""Строгая проверка JSON-дат, версии и частичных полей."""

import re
from datetime import date
from typing import Annotated, Self

from fastapi import Query
from pydantic import Field, PlainValidator, WithJsonSchema, model_validator

from apps.modules.planning.domain.model import PlanChanges, PlanInput
from apps.shared.schemas import PageParams

DATE_PATTERN = r"^20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"


def parse_date(value: object) -> date:
    """Принять только ISO-дату без времени, смещения и неявного преобразования чисел."""
    if not isinstance(value, str) or not re.fullmatch(DATE_PATTERN, value):
        msg = "Дата должна быть строкой YYYY-MM-DD в пределах 2000–2099 годов"
        raise ValueError(msg)
    return date.fromisoformat(value)


PlanDateIn = Annotated[
    date, PlainValidator(parse_date), WithJsonSchema({"type": "string", "format": "date", "pattern": DATE_PATTERN})
]


class CreatePlanSchema(PlanInput):
    """Новый план с типом, определяемым категорией на сервере."""

    planned_date: PlanDateIn


class UpdatePlanSchema(PlanChanges):
    """Обязательная версия и минимум одно явно переданное поле."""

    planned_date: PlanDateIn | None = None
    expected_version: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        """Не считать версию самостоятельным изменением."""
        if not self.model_fields_set - {"expected_version"}:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        return self

    def changes(self) -> PlanChanges:
        """Передать домену только пользовательские изменения без служебной версии."""
        return PlanChanges.model_validate(self.model_dump(exclude_unset=True, exclude={"expected_version"}))


class PlanPageParams(PageParams):
    """Ограничить страницу планов согласованными границами контракта."""

    skip: int = Field(Query(default=0, ge=0, le=100_000))
    limit: int = Field(Query(default=500, ge=1, le=500))
