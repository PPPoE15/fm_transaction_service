"""Частичные изменения операции с различением отсутствующего поля и null."""

from datetime import datetime
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from apps.shared import apps_types
from apps.shared.schemas import Base


class TransactionChanges(Base):
    """Поля изменения операции; только описание допускает явный null."""

    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime | None = None
    category_uid: apps_types.CategoryUID | None = None
    money_sum: int | None = Field(default=None, ge=1, le=1_000_000_000, strict=True)
    transaction_type: apps_types.TransactionType | None = None
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        """Отклонить пустые изменения и null у обязательных полей операции."""
        if not self.model_fields_set:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        for name in self.model_fields_set - {"description"}:
            if getattr(self, name) is None:
                msg = f"Поле {name} не допускает null"
                raise ValueError(msg)
        return self
