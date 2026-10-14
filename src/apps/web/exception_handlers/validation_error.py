from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette import status

from apps.shared.exceptions import BaseCustomValidationError, BaseUnprocessableError

from . import base

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse


class ValidationField(BaseModel):
    """Поле ошибки с детальной информацией"""

    message: str = Field(
        title="Сообщение",
        description="Текст ошибки валидации",
        examples=["Не должно быть пустым"],
    )
    field: str = Field(
        title="Поле в запросе",
        description="Название поля в запросе, на котором сработала валидация",
        examples=["card.surname"],
    )
    rejected_value: str | None = Field(
        title="Содержимое поля",
        description="Значение поля, не прошедшее валидацию",
        examples=["comment"],
        alias="rejectedValue",
    )
    rule: str = Field(
        title="Правило",
        description="Название правила валидации",
        examples=["NotEmpty"],
    )


class ValidationErrorResponseSchema(base.BaseErrorResponseSchema):
    """Модель ответа об ошибке валидации в соответствии с RFC7807."""

    type: str = Field(
        title="URI",
        description="Ссылка на документацию",
        examples=["/help-center?helpSectionId=errors#422"],
        default="/help-center?helpSectionId=errors#422",
    )
    title: str = Field(
        title="Ответ (описание)",
        description="Описание HTTP-кода ответа",
        max_length=256,
        examples=["Bad Request"],
        default="Bad Request",
    )
    status: int = Field(
        title="Ответ (код)",
        description="Число, строго соответствует HTTP-коду ответа",
        examples=[status.HTTP_422_UNPROCESSABLE_ENTITY],
        default=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    detail: str = Field(
        title="Информация",
        description="Интернациолизируемое описание ошибки",
        examples=["Валидация не пройдена"],
        default="Валидация не пройдена",
    )
    validation: list[ValidationField] = Field(
        title="Ошибки валидации",
        description="Список ошибок форматной валидации",
    )
    code: str = Field(
        title="Внутренний код ошибки",
        description="Числобуквенный код ошибки в рамках продута FM",
        examples=["FM-422000"],
        default="FM-422000",
    )


def _field(body: object, loc: tuple) -> str:
    """
    Поле ошибки по её `loc`.

    `("body",)` — тела нет или оно не объект; при невалидном JSON (тело — строка) в `loc` позиция ошибки разбора.
    """
    path = loc[1:]
    if not path:
        return str(loc[0])
    if isinstance(body, str):
        return ".".join(str(part) for part in path)
    return str(path[0])


def _rejected_value(body: object, loc: tuple) -> str | None:
    """Отклонённое значение строкой: числа, bool и объекты из тела попадают в `rejectedValue`, а не роняют ответ."""
    # TODO(FM-37): для ошибки на всё тело (`loc` без пути) `get_body_info` при теле-массиве пишет в лог трейсбек
    # IndexError, а без тела отдаёт "" вместо null — при пустом пути возвращать None.
    # TODO(FM-37): не строки отдаются как Python repr (`True`, `{'a': 1}`); отдавать JSON (`json.dumps`),
    # и поправить аннотацию `get_body_info` — она возвращает сырые объекты, а не `str | None`.
    value = base.get_body_info(body, loc)
    return None if value is None else str(value)


def setup_validation_exception_handlers(app: FastAPI) -> None:
    """
    Настройка обработчиков ошибок валидации.

    Args:
        app: Приложение FastAPI.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        error_validation = [
            ValidationField(
                message=err["msg"],
                field=_field(exc.body, err["loc"]),
                rejectedValue=_rejected_value(exc.body, err["loc"][1:]),
                rule=err["type"],
            )
            for err in exc.errors()
        ]
        error_correct_form = ValidationErrorResponseSchema(
            instance=request.url.path,
            validation=error_validation,
        )

        return error_correct_form.json_response()

    # TODO(FM-37): обработчик игнорирует `exc.code` (и forbidden_error тоже) — перевести на `from_error`,
    # когда появится первый подкласс с собственным кодом.
    @app.exception_handler(BaseCustomValidationError)
    async def custom_validation_exception_handler(request: Request, exc: BaseCustomValidationError) -> JSONResponse:
        # Собственный код ошибки (`FM-400101`) — через from_error, как у остальных доменных ошибок; без него
        # общий код 400, а не FM-422000 по умолчанию схемы ответа
        return ValidationErrorResponseSchema.from_error(
            request,
            exc,
            status=status.HTTP_400_BAD_REQUEST,
            code="FM-400000",
            type="/help-center?helpSectionId=errors#400",
            validation=[],
        ).json_response()

    @app.exception_handler(BaseUnprocessableError)
    async def unprocessable_exception_handler(request: Request, exc: BaseUnprocessableError) -> JSONResponse:
        # NOTE(FM-37): `rejectedValue` — null: ошибка домена не знает исходного значения поля (а дата могла быть
        # подставлена по умолчанию, и клиент её не передавал). Контракт null допускает.
        validation = (
            [ValidationField(message=exc.msg, field=exc.field, rejectedValue=None, rule="value_error")]
            if exc.field
            else []
        )
        return ValidationErrorResponseSchema.from_error(request, exc, validation=validation).json_response()
