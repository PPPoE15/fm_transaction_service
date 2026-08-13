from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


class CategorySchema(Base):
    """Схема данных категории бюджета"""

    uid: apps_types.TransactionUID = Field(
        description="UID транзакции.",
    )
    name: apps_types.CategoryName = Field(
        description="Категория.",
    )
    money_plan: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип категории (доход или расход)",
    )
    description: apps_types.Description = Field(
        description="Описание категории.",
    )


@dataclass
class CategoryFilters:
    """Фильтр по категориям."""

    name: Annotated[
        str | None,
        Query(
            title="Название категории.",
            description="Поиск по совпадению символов в названиях категорий, без учета регистра",
        ),
    ] = None

    category_type: Annotated[
        apps_types.TransactionType | None,
        Query(
            title="Тип категории",
            description="Поиск по типу категории.",
        ),
    ] = None

    below_money_sum: Annotated[
        apps_types.MoneySum | None,
        Query(
            title="Фильтр по запланированному бюджету.",
            description="Получить все что ниже указанной суммы.",
        ),
    ] = None

    above_money_sum: Annotated[
        apps_types.MoneySum | None,
        Query(
            title="Фильтр по запланированному бюджету.",
            description="Получить все что выше указанной суммы.",
        ),
    ] = None
