"""Типизированные входы и результаты пакетных команд операций."""

import re
from datetime import date as calendar_date
from datetime import datetime
from typing import Annotated, Generic, Literal, Self, TypeVar

from pydantic import ConfigDict, Field, PlainValidator, WithJsonSchema, model_validator

from apps.modules.transaction.domain.changes import TransactionChanges
from apps.shared import apps_types
from apps.shared.api_types import DescriptionIn
from apps.shared.schemas import Base


def parse_calendar_date(value: object) -> calendar_date:
    """Принять только существующую календарную дату 2000–2099 в формате YYYY-MM-DD."""
    if not isinstance(value, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        msg = "Дата должна быть строкой YYYY-MM-DD с годом 2000–2099"
        raise ValueError(msg)
    return calendar_date.fromisoformat(value)


class BatchChanges(Base):
    """Изменяемые поля строки таблицы без смены типа операции."""

    model_config = ConfigDict(extra="forbid")
    date: (
        Annotated[
            calendar_date,
            PlainValidator(parse_calendar_date),
            WithJsonSchema({"type": "string", "format": "date", "pattern": r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$"}),
        ]
        | None
    ) = None
    category_uid: apps_types.CategoryUID | None = None
    money_sum: int | None = Field(default=None, ge=1, le=1_000_000_000, strict=True)
    description: DescriptionIn | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        """Отклонить пустой набор изменений и null у полей, кроме описания."""
        if not self.model_fields_set:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        for name in self.model_fields_set - {"description"}:
            if getattr(self, name) is None:
                msg = f"Поле {name} не допускает null"
                raise ValueError(msg)
        return self

    def for_transaction(self, original_date: datetime) -> TransactionChanges:
        """Преобразовать дату, сохранив локальное время и микросекунды исходной операции."""
        fields = self.model_dump(exclude_unset=True, exclude={"date"})
        if self.date is not None:
            fields["transaction_date"] = original_date.replace(
                year=self.date.year, month=self.date.month, day=self.date.day
            )
        return TransactionChanges.model_validate(fields)


class DeleteItem(Base):
    """Идентификатор операции и версия, прочитанная клиентом."""

    model_config = ConfigDict(extra="forbid")
    uid: apps_types.TransactionUID
    expected_version: int = Field(ge=1, strict=True)


class UpdateItem(DeleteItem):
    """Версионное изменение одной операции."""

    changes: BatchChanges


ItemT = TypeVar("ItemT", bound=DeleteItem)


class BatchRequest(Base, Generic[ItemT]):
    """Полностью проверенный пакет из 1–100 различных операций."""

    model_config = ConfigDict(extra="forbid")
    items: list[ItemT] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_uids(self) -> Self:
        """Отклонить повтор UID независимо от версий и изменений."""
        if len({item.uid for item in self.items}) != len(self.items):
            msg = "UID операций в пакете должны быть уникальны"
            raise ValueError(msg)
        return self


class BatchIssue(Base):
    """Ошибка пакета без раскрытия сведений о чужих операциях."""

    code: str
    message: str
    index: int | None = None
    uid: apps_types.TransactionUID | None = None
    field: str | None = None


class DeleteSuccess(Base):
    """Подтверждённое удаление без полей ошибки."""

    index: int
    uid: apps_types.TransactionUID
    status: Literal[204] = 204


class DeleteFailure(Base):
    """Ожидаемый отказ одной строки, не мешающий остальным удалениям."""

    index: int
    uid: apps_types.TransactionUID
    status: Literal[404, 409]
    code: str
    message: str


class BatchDeleteResult(Base):
    """Результаты всех элементов в исходном порядке."""

    results: list[DeleteSuccess | DeleteFailure]


class BatchTransactionError(Exception):
    """Ошибка проверки атомарного пакета до изменения любой строки."""

    def __init__(self, status_code: int, errors: list[BatchIssue]) -> None:
        """Сохранить выбранный приоритет ошибки и привязку ошибок к входным строкам."""
        self.status_code = status_code
        self.errors = errors
        super().__init__(errors[0].message)
