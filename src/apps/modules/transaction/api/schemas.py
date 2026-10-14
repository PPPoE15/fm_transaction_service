from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from apps.shared import apps_types
from apps.shared.api_types import DescriptionIn, LocalDateTimeIn
from apps.shared.schemas import Base

# Ограничения суммы транзакции — по контракту (`contracts/README.md`, «Валидация»).
MIN_MONEY_SUM = 1
MAX_MONEY_SUM = 1_000_000_000


class CreateTransactionSchema(Base):
    """Схема данных для создания транзакции (`TransactionCreate` контракта)."""

    model_config = ConfigDict(extra="forbid")

    transaction_date: LocalDateTimeIn = Field(
        description=(
            "Дата и время транзакции: `YYYY-MM-DDTHH:MM:SS[.ffffff]` без часового пояса, годы 2000–2099, "
            "дата должна существовать."
        ),
        examples=["2026-03-14T19:30:00"],
    )
    category_uid: apps_types.CategoryUID = Field(
        description="UID статьи пользователя (чужая или несуществующая — 400 `FM-400201`).",
        examples=["f171258a-1772-4ff3-b797-04bae1e0b3dc"],
    )
    money_sum: apps_types.MoneySum = Field(
        description="Сумма в целых рублях, 1 … 1 000 000 000.",
        ge=MIN_MONEY_SUM,
        le=MAX_MONEY_SUM,
        strict=True,  # только целое число JSON: без строк "100", 1.0 и true
        examples=[1250],
    )
    transaction_type: apps_types.TransactionType = Field(
        description="Тип транзакции; должен совпадать с типом статьи (иначе 400 `FM-400202`).",
        examples=[apps_types.TransactionType.OUTCOME, apps_types.TransactionType.INCOME],
    )
    description: DescriptionIn | None = Field(
        default=None,
        description="Описание до 500 символов; пустая строка сохраняется как `null`.",
        examples=["Ужин"],
    )

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, value: str | None) -> str | None:
        """Пустое описание — то же, что его отсутствие."""
        return value or None


class UpdateTransactionSchema(Base):
    """Схема данных для обновления транзакции"""

    transaction_date: datetime = Field(
        title="Дата транзакции.",
        description="Дата транзакции.",
        examples=["2025-11-07T16:52:48.249989"],
    )
    category: apps_types.CategoryUID = Field(
        title="Категория.",
        description="Категория.",
        examples=[],
    )
    money_sum: apps_types.MoneySum = Field(
        title="Денежная сумма по категории.",
        description="Денежная сумма по категории.",
        examples=[120, 4590],
    )
    transaction_type: apps_types.TransactionType = Field(
        title="Тип транзакции",
        description="Тип транзакции",
        examples=["outcome", "income"],
    )
    description: apps_types.Description = Field(
        default=None,
        title="Описание.",
        description="Описание транзакции.",
        examples=["Корм коту", "котлеты"],
    )
