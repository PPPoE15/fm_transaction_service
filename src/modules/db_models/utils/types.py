from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Type, TypeVar

import sqlalchemy as sa
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import JSON, Dialect, TypeDecorator
from sqlalchemy import DateTime as _DateTime
from sqlalchemy.sql.type_api import TypeEngine

AnyT = TypeVar("AnyT", bound=Any)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class PydanticType(sa.types.TypeDecorator):
    """
    Тип для представления Pydantic схемы в ORM.

    Расширяет тип JSON, добавляя возможность сохранять схему в JSON
    и восстанавливать из JSON в схему.
    """

    impl = sa.types.JSON
    cache_ok = True

    def __init__(self, pydantic_type: Type[SchemaT]) -> None:
        """
        Конструктор маппера Pydantic схемы в ORM.

        Args:
            pydantic_type: Класс схемы Pydantic.
        """
        super().__init__()
        self.pydantic_type = pydantic_type

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[AnyT]:
        """Преобразовывает универсальный тип в тип диалекта"""
        return dialect.type_descriptor(JSON())

    def process_bind_param(
        self,
        value: Optional[AnyT],
        dialect: Dialect,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """Преобразует Pydantic схему в JSON"""
        return jsonable_encoder(value) if value else None

    def process_result_value(
        self,
        value: Optional[Any],  # noqa: ANN401
        dialect: Dialect,  # noqa: ARG002
    ) -> Optional[Any]:  # noqa: ANN401
        """Преобразует JSON в Pydantic схему"""
        if not value:
            return None

        if isinstance(value, Sequence):
            return [self.pydantic_type.model_validate(data) for data in value]

        return self.pydantic_type.model_validate(value)


class TZDateTime(TypeDecorator):
    """Type для datetime.datetime() по UTC без timezone. В PostgreSQL время лежит без timezone, в UTC."""

    impl = _DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[Any], dialect: Dialect) -> datetime:  # noqa: ARG002, ANN401
        if value is not None:
            if not value.tzinfo:
                msg = "'tzinfo' is required."
                raise TypeError(msg)
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Optional[Any], dialect: Dialect) -> datetime:  # noqa: ARG002, ANN401
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value
