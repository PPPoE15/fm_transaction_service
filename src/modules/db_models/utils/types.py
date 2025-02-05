from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import DateTime as _DateTime
from sqlalchemy import Dialect, TypeDecorator

AnyT = TypeVar("AnyT", bound=Any)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class TZDateTime(TypeDecorator):
    """Type для datetime.datetime() по UTC без timezone. В PostgreSQL время лежит без timezone, в UTC."""

    impl = _DateTime
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> datetime:  # noqa: ARG002, ANN401
        if value is not None:
            if not value.tzinfo:
                msg = "'tzinfo' is required."
                raise TypeError(msg)
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any | None, dialect: Dialect) -> datetime:  # noqa: ARG002, ANN401
        if value is not None:
            value = value.replace(tzinfo=UTC)
        return value
