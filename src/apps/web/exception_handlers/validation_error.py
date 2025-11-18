from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette import status

from apps.web.app.utils.exceptions import BaseCustomValidationError

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
                field=".".join(cast(Iterable[str], err["loc"][1:]))  # noqa: TC006
                if isinstance(exc.body, str)
                else str(err["loc"][1]),
                rejectedValue=base.get_body_info(exc.body, err["loc"][1:]),
                rule=err["type"],
            )
            for err in exc.errors()
        ]
        error_correct_form = ValidationErrorResponseSchema(
            instance=request.url.path,
            validation=error_validation,
        )

        return error_correct_form.json_response()

    @app.exception_handler(BaseCustomValidationError)
    async def custom_validation_exception_handler(request: Request, exc: BaseCustomValidationError) -> JSONResponse:
        instance = request.url.path
        return ValidationErrorResponseSchema(
            instance=instance,
            status=status.HTTP_400_BAD_REQUEST,
            detail=exc.msg,
            validation=[],
        ).json_response()
