import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BeforeValidator, Field

from apps.modules.transaction.application.exceptions import InvalidDateRangeError
from apps.shared import apps_types
from apps.shared.schemas import Base, PageParams

LOCAL_DATETIME_PATTERN = (
    r"20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?"
)


def validate_local_datetime(value: object) -> datetime:
    """Проверить точный локальный формат даты из контракта."""
    if not isinstance(value, str) or re.fullmatch(LOCAL_DATETIME_PATTERN, value) is None:
        message = "Ожидается локальная дата YYYY-MM-DDTHH:MM:SS[.ffffff], годы 2000–2099"
        raise ValueError(message)
    return datetime.fromisoformat(value)


LocalDateTime = Annotated[datetime, BeforeValidator(validate_local_datetime)]


class TransactionPageParams(PageParams):
    """Ограничения пагинации списка транзакций."""

    skip: int = Field(Query(default=0, ge=0, le=100_000))
    limit: int = Field(Query(default=500, ge=1, le=500))


class CategoryRef(Base):
    """Идентификатор и название статьи транзакции."""

    uid: apps_types.CategoryUID
    name: apps_types.CategoryName


class TransactionSchema(Base):
    """Список транзакций пользователя"""

    uid: apps_types.TransactionUID = Field(
        description="UID транзакции.",
    )
    transaction_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: CategoryRef = Field(
        description="Категория транзакции.",
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
        LocalDateTime | None,
        Query(
            title="Последняя дата совершения транзакции.",
            description="Фильтрация транзакций по времени их совершения.",
        ),
    ] = None

    after: Annotated[
        LocalDateTime | None,
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
