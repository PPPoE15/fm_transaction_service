from typing import Annotated

from pydantic import ConfigDict, Field, StringConstraints, field_validator

from apps.shared import apps_types
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
# Описание: до 500 символов, допустимы табуляция и переводы строк (\t \n \r), другие управляющие — нет.
DescriptionIn = Annotated[
    str,
    StringConstraints(max_length=500, pattern=r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$"),
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


class UpdateCategorySchema(Base):
    """Схема данных для обновления категории"""

    name: apps_types.CategoryName = Field(
        description="Категория.",
        examples=["ЖКХ", "Еда вне дома"],
    )
    money_plan: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
        examples=[40_000, 3500],
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип категории (доход или расход)",
        examples=[apps_types.TransactionType.INCOME, apps_types.TransactionType.OUTCOME],
    )
    description: apps_types.Description | None = Field(
        description="Описание категории.",
        examples=["Крайне важная категория", "Не очень важная, но очень приятная"],
    )
