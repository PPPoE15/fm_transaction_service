from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


class TransactionSchema(Base):
    """Список транзакций пользователя"""

    transaction_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: apps_types.CategoryName = Field(
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
        datetime | None,
        Query(
            title="Последняя дата совершения транзакции.",
            description="Фильтрация транзакций по времени их совершения.",
        ),
    ] = None

    after: Annotated[
        datetime | None,
        Query(
            title="Первая дата совершения транзакции.",
            description="Фильтрация транзакций по времени их совершения.",
        ),
    ] = None
