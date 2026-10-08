from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

from apps.shared import apps_types

MIN_YEAR = 2000
MAX_YEAR = 2099


@dataclass
class BudgetStructureParams:
    """Параметры таблицы структуры бюджета."""

    year: Annotated[
        int | None,
        Query(
            title="Год таблицы",
            description="Год таблицы, 2000–2099. По умолчанию текущий.",
            ge=MIN_YEAR,
            le=MAX_YEAR,
        ),
    ] = None

    category_type: Annotated[
        apps_types.TransactionType,
        Query(
            title="Тип статей",
            description="Тип статей в таблице. По умолчанию расходы.",
        ),
    ] = apps_types.TransactionType.OUTCOME
