from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi import Query

    from modules import types


class Incomes(Base):
    """Список доходов пользователя"""

    income_date: datetime = Field(
        description="Дата транзакции.",
    )
    category: types.CategoryName = Field(
        description="Категория транзакции.",
    )
    money_sum: types.MoneySum = Field(
        description="Сумма транзакции.",
    )
    description: types.Description | None = Field(
        description="Описание транзакции.",
    )


@dataclass
class IncomeFilters:
    """Фильтр по транзакциям."""

    category: Annotated[
        str | None,
        Query(
            title="Название категории",
            description="Поиск по совпадению символов в названиях категорий, без учета регистра",
        ),
    ] = None
