from typing import Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from apps.modules.transaction.domain.changes import TransactionChanges
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


class UpdateTransactionSchema(TransactionChanges):
    """Частичное обновление с необязательной проверкой версии."""

    transaction_date: LocalDateTimeIn | None = None
    description: DescriptionIn | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        """Версия сама по себе не является изменением операции."""
        if not self.model_fields_set - {"expected_version"}:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        return self

    def changes(self) -> TransactionChanges:
        """Передать команде только явно заданные поля изменения."""
        return TransactionChanges.model_validate(self.model_dump(exclude_unset=True, exclude={"expected_version"}))
