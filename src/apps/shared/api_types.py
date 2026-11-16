"""
Ограничения входных данных API, общие для модулей (контракт, `contracts/README.md`, «Валидация»).

Только типы для схем запросов: доменные типы — в `apps_types`.
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import Field, PlainValidator, StringConstraints, WithJsonSchema

# Описание статьи или транзакции: до 500 символов, допустимы табуляция и переводы строк (\t \n \r), другие
# управляющие — нет. Пустую строку схема запроса сохраняет как `null` (своим валидатором поля).
DescriptionIn = Annotated[
    str,
    StringConstraints(max_length=500, pattern=r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$"),
    Field(strict=True),
]

# Шаблон `LocalDateTime` из контракта, с `[0-9]` вместо `\d`: в Python `\d` совпадает и с не-ASCII цифрами.
_LOCAL_DATE_TIME_PATTERN = (
    r"^20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?$"
)
_LOCAL_DATE_TIME = re.compile(_LOCAL_DATE_TIME_PATTERN)


def _parse_local_date_time(value: object) -> datetime:
    """
    Строка `YYYY-MM-DDTHH:MM:SS[.ffffff]` без часового пояса, годы 2000–2099, дата должна существовать.

    Без своей проверки pydantic принял бы и число (unix-время), и дату без времени, и часовой пояс.
    pydantic превращает в 422 только ValueError/AssertionError, поэтому и для не строки — ValueError.
    """
    if not isinstance(value, str) or not _LOCAL_DATE_TIME.fullmatch(value):
        msg = "Дата и время должны быть строкой YYYY-MM-DDTHH:MM:SS[.ffffff] с годом 2000–2099"
        raise ValueError(msg)
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        msg = "Такой даты не существует"
        raise ValueError(msg) from exc


LocalDateTimeIn = Annotated[
    datetime,
    PlainValidator(_parse_local_date_time),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": _LOCAL_DATE_TIME_PATTERN,
            "description": "Локальные дата и время без часового пояса, годы 2000–2099.",
            "examples": ["2026-03-14T19:30:00"],
        }
    ),
]
