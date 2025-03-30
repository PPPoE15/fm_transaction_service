from typing import Generic, List, TypeVar

from pydantic import Field

from apps.utils.schemas import Base

DataT = TypeVar("DataT")


class BaseResponseSchema(Base, Generic[DataT]):
    """Базовый класс ответа с одним элементом для API."""

    content: DataT


class BaseListResponseSchema(Base, Generic[DataT]):
    """Базовый класс ответа со списком для API."""

    total: int = Field(
        title="Общее количество элементов в БД",
        description="Общее количество элементов в БД",
        examples=[100],
    )
    content: List[DataT]
