from datetime import datetime

from pydantic import Field

from modules import types
from modules.utils.schemas import Base
from modules.web.app.utils.datetime_tz import aware_now


class CreateTransactionSchema(Base):
    """Схема данных для создания транзакции"""

    user_uid: types.UserUID = Field(
        title="UID пользователя.",
        description="UID пользователя.",
        examples=["3a6aa712-fd55-40d6-87f0-512bad5752bc"],
    )
    transaction_date: datetime = Field(
        title="Дата транзакции.",
        description="Дата транзакции.",
        examples=[aware_now()],
    )
    category: types.CategoryName = Field(
        title="Категория.",
        description="Категория.",
        examples=[],
    )
    money_sum: types.MoneySum = Field(
        title="Денежная сумма по категории.",
        description="Денежная сумма по категории.",
        examples=[120, 4590],
    )
    transaction_type: types.TransactionType = Field(
        title="Тип транзакции",
        description="Тип транзакции",
        examples=["outcome", "income"],
    )
    description: types.Description = Field(
        title="Описание.",
        description="Описание транзакции.",
        examples=["Корм коту", "котлеты"],
    )
