from datetime import datetime

from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base
from apps.web.app.utils.datetime_tz import aware_now


class CreateTransactionSchema(Base):
    """Схема данных для создания транзакции"""

    transaction_date: datetime = Field(
        title="Дата транзакции.",
        description="Дата транзакции.",
        examples=[aware_now()],
    )
    category: apps_types.CategoryName = Field(
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
        title="Описание.",
        description="Описание транзакции.",
        examples=["Корм коту", "котлеты"],
    )
