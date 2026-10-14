from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Query
from pydantic import Field

from apps.modules.transaction.application.exceptions import InvalidDateRangeError
from apps.shared import apps_types
from apps.shared.api_types import LocalDateTimeIn
from apps.shared.schemas import Base, PageParams


class TransactionPageParams(PageParams):
    """Ограничения пагинации списка транзакций."""

    skip: int = Field(Query(default=0, ge=0, le=100_000))
    limit: int = Field(Query(default=500, ge=1, le=500))


class CategoryRef(Base):
    """Статья транзакции в ответе: UID и название (`CategoryRef` контракта)."""

    uid: apps_types.CategoryUID = Field(
        description="UID статьи.",
    )
    name: apps_types.CategoryName = Field(
        description="Название статьи.",
    )


class TransactionSchema(Base):
    """
    Транзакция в ответах API (`Transaction` контракта): элемент списка и ответ создания.

    Одна схема на все ответы с транзакцией, чтобы список и создание не расходились.
    """

    uid: apps_types.TransactionUID = Field(
        description="UID транзакции.",
    )
    transaction_date: datetime = Field(
        description="Дата и время транзакции (локальные, без часового пояса).",
    )
    category: CategoryRef = Field(
        description="Статья транзакции.",
    )
    money_sum: apps_types.MoneySum = Field(
        description="Сумма транзакции.",
    )
    transaction_type: apps_types.TransactionType = Field(
        description="Тип транзакции.",
    )
    description: apps_types.Description = Field(
        description="Описание транзакции.",
    )


@dataclass
class TransactionFilters:
    """Фильтр по транзакциям."""

    category: Annotated[
        str | None,
        Query(
            title="Название категории",
            description="Поиск по совпадению символов в названиях категорий, без учета регистра",
        ),
    ] = None

    transaction_type: Annotated[
        apps_types.TransactionType | None,
        Query(
            title="Тип транзакции",
            description="Поиск по типу транзакции.",
        ),
    ] = None

    before: Annotated[
        LocalDateTimeIn | None,
        Query(
            title="Последняя дата совершения транзакции.",
            description="Фильтрация транзакций по времени их совершения.",
        ),
    ] = None

    after: Annotated[
        LocalDateTimeIn | None,
        Query(
            title="Первая дата совершения транзакции.",
            description="Фильтрация транзакций по времени их совершения.",
        ),
    ] = None

    sort: Annotated[Literal["-transaction_date", "transaction_date"], Query()] = "-transaction_date"

    def __post_init__(self) -> None:
        """Отклонить обратный диапазон дат до обращения к БД."""
        if self.after is not None and self.before is not None and self.before < self.after:
            raise InvalidDateRangeError
