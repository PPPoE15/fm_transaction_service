import datetime as dt
from typing import Any, Collection, Dict, Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


class Base(BaseModel):
    """Базовый класс для наследования."""

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,  # model_validate будет заполнять не по alias, а по имени аттрибута
    )

    def to_dict(self, exclude: Optional[Collection[str]] = None) -> Dict[str, Any]:
        """
        Не рекурсивное преобразование модели в словарь.

        Args:
            exclude: Список имен полей, которые не нужно включать в словарь.
        """
        result = dict(self)
        if exclude:
            result = {k: v for k, v in result.items() if k not in exclude}
        return result


class PageParams(Base):
    """
    Представление переменных для пагинации.

    Присутствие fastapi.Query необходимо для корректной валидации параметров со стороны fastapi (422 HTTP_CODE).
    Модель можно создавать только через fastapi.Depends
    """

    skip: int = Field(
        Query(
            title="Смещение",
            description="Смещение",
            ge=0,
            default=0,
        )
    )
    limit: int = Field(
        Query(
            title="Предел",
            description="Предел",
            ge=0,
            default=500,
        )
    )


class CreatingMixin:
    """Миксин, добавляющий стандартные поля с информацией о создании записи."""

    created_date: Optional[dt.datetime] = Field(
        title="Created Date",
        description="Дата создания записи пользователем",
        examples=["2023-08-02T08:25:20.918267"],
        default=None,
        alias="creation_date",
    )
    created_by: Optional[str] = Field(
        title="Created By",
        description="Автор записи",
        default=None,
    )


class UpdatingMixin(Base):
    """Миксин, добавляющий стандартные поля с информацией о последнем обновлении записи."""

    last_modified_date: Optional[dt.datetime] = Field(
        title="Last Modified Date",
        description="Дата обновления записи пользователем",
        examples=["2023-08-02T08:25:20.962678"],
        default=None,
    )
    last_modified_by: Optional[str] = Field(
        title="Last Modified By",
        description="Автор последнего изменения записи",
        default=None,
    )


class NumberOfObjectsMixin(Base):
    """Миксин для отображения общего количества записей"""

    total: int = Field(
        title="Общее количество элементов в БД",
        description="Общее количество элементов в БД",
        examples=[100],
    )
