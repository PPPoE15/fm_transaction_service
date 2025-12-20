from pydantic import Field

from apps import apps_types
from apps.utils.schemas import Base


class CreateCategorySchema(Base):
    """Схема данных для создания категории"""

    name: apps_types.CategoryName = Field(
        description="Категория.",
        examples=["ЖКХ", "Еда вне дома"],
    )
    money_plan: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
        examples=[40_000, 3500],
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип категории (доход или расход)",
        examples=[apps_types.TransactionType.INCOME, apps_types.TransactionType.OUTCOME],
    )
    description: apps_types.Description | None = Field(
        description="Описание категории.",
        examples=["Крайне важная категория", "Не очень важная, но очень приятная"],
    )


class UpdateCategorySchema(Base):
    """Схема данных для обновления категории"""

    name: apps_types.CategoryName = Field(
        description="Категория.",
        examples=["ЖКХ", "Еда вне дома"],
    )
    money_plan: apps_types.MoneySum = Field(
        description="Минимум/максимум транзакции по категории.",
        examples=[40_000, 3500],
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип категории (доход или расход)",
        examples=[apps_types.TransactionType.INCOME, apps_types.TransactionType.OUTCOME],
    )
    description: apps_types.Description | None = Field(
        description="Описание категории.",
        examples=["Крайне важная категория", "Не очень важная, но очень приятная"],
    )
