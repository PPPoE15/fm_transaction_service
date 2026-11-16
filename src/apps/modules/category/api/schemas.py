from typing import Annotated, Self

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from apps.shared import apps_types
from apps.shared.api_types import DescriptionIn
from apps.shared.schemas import Base

# Ограничения полей статьи — по контракту (`contracts/README.md`, «Валидация»).
MAX_MONEY_PLAN = 1_000_000_000
# Название: после обрезки пробелов 1–64 символа без управляющих. Шаблон без lookahead контракта `(?=.*\S)`
# (rust-regex pydantic его не поддерживает): строку только из пробелов отсекает обрезка + `min_length`.
CategoryNameIn = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[^\x00-\x1F\x7F]+$"),
    Field(strict=True),
]


class CreateCategorySchema(Base):
    """Схема данных для создания статьи."""

    model_config = ConfigDict(extra="forbid")

    name: CategoryNameIn = Field(
        description="Название статьи: 1–64 символа после обрезки пробелов по краям, без управляющих символов.",
        examples=["ЖКХ", "еда вне дома"],
    )
    money_plan: apps_types.MoneySum | None = Field(
        default=None,
        description="Плановая сумма за месяц в целых рублях, 0 … 1 000 000 000. Не передана или `null` — плана нет.",
        ge=0,
        le=MAX_MONEY_PLAN,
        strict=True,  # только целое число JSON: без строк "100", 1.0 и true
        examples=[5000, None],
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип статьи (доход или расход).",
        examples=[apps_types.TransactionType.INCOME, apps_types.TransactionType.OUTCOME],
    )
    description: DescriptionIn | None = Field(
        default=None,
        description="Описание до 500 символов; пустая строка сохраняется как `null`.",
        examples=["Кафе и доставка"],
    )

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, value: str | None) -> str | None:
        """Пустое описание — то же, что его отсутствие."""
        return value or None


# TODO(FM-45): ограничения плана (`ge`/`le`/`strict`) и `empty_description_is_none` скопированы из
# `CreateCategorySchema` — вынести общий `Annotated` (вроде `MoneyPlanIn`), чтобы схемы не разошлись снова.
# TODO(FM-45): сгенерированный `/openapi.json` расходится с контрактом: у `name` и `category_type` `anyOf [.., null]`,
# нет `minProperties` и ответов 400/404/409 (у `POST /categories` ответы тоже не описаны). Источник правды — контракт.
class UpdateCategorySchema(Base):
    """
    Схема частичного изменения статьи: те же ограничения полей, что при создании.

    Значимы только переданные поля (`model_fields_set`). `null` очищает план и описание; у названия и типа `null`
    недопустим. Пустое тело — 422 (`minProperties: 1`).
    """

    model_config = ConfigDict(extra="forbid")

    name: CategoryNameIn | None = Field(
        default=None,
        description="Название статьи: 1–64 символа после обрезки пробелов по краям, без управляющих символов.",
        examples=["ЖКХ"],
    )
    money_plan: apps_types.MoneySum | None = Field(
        default=None,
        description="Плановая сумма за месяц в целых рублях, 0 … 1 000 000 000; `null` — плана нет.",
        ge=0,
        le=MAX_MONEY_PLAN,
        strict=True,
        examples=[5000, None],
    )
    category_type: apps_types.TransactionType | None = Field(
        default=None,
        description="Тип статьи; у статьи с транзакциями не меняется (400 `FM-400101`).",
        examples=[apps_types.TransactionType.OUTCOME],
    )
    description: DescriptionIn | None = Field(
        default=None,
        description="Описание до 500 символов; пустая строка и `null` очищают его.",
        examples=["Кафе и доставка"],
    )

    @field_validator("name", "category_type")
    @classmethod
    def not_null(cls, value: object) -> object:
        """Название и тип очистить нельзя: валидатор вызывается только для переданных значений, в том числе `null`."""
        if value is None:
            msg = "Поле не может быть null"
            raise ValueError(msg)
        return value

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, value: str | None) -> str | None:
        """Пустое описание — то же, что его отсутствие."""
        return value or None

    @model_validator(mode="after")
    def not_empty(self) -> Self:
        """Хотя бы одно поле (`minProperties: 1`)."""
        if not self.model_fields_set:
            msg = "Нужно передать хотя бы одно поле"
            raise ValueError(msg)
        return self
