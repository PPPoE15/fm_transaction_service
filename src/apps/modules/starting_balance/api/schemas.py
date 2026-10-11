import re
from datetime import date
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from apps.shared.schemas import Base

MIN_AMOUNT = -1_000_000_000
MAX_AMOUNT = 1_000_000_000
# Только `YYYY-MM-DD`: без проверки pydantic принял бы и `2026-03-01T00:00:00`, и число (unix-время).
_DATE_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}")


class StartingBalanceCreateSchema(Base):
    """Схема данных для задания стартового остатка."""

    model_config = ConfigDict(extra="forbid")

    amount: int = Field(
        title="Сумма накоплений",
        description="Сумма накоплений в целых рублях, может быть отрицательной (долг).",
        ge=MIN_AMOUNT,
        le=MAX_AMOUNT,
        strict=True,  # только целое число JSON: без строк "100", 1.0 и true
        examples=[120000],
    )
    balance_date: date | None = Field(
        default=None,
        title="Дата остатка",
        description=(
            "Не передан — вчера (сумма считается остатком на начало сегодняшнего дня). "
            "Год — 2000–2099, не позже сегодняшнего дня."
        ),
        examples=["2026-01-01"],
    )

    @field_validator("balance_date", mode="before")
    @classmethod
    def check_date_format(cls, value: Any) -> Any:  # noqa: ANN401
        """Дата — строка `YYYY-MM-DD`; поле можно не передавать, но `null` по контракту недопустим."""
        if not isinstance(value, str) or not _DATE_FORMAT.fullmatch(value):
            msg = "Дата должна быть строкой в формате YYYY-MM-DD"
            # pydantic превращает в 422 только ValueError/AssertionError, поэтому не TypeError.
            raise ValueError(msg)
        return value
