from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette import status

from apps.shared.exceptions import BaseConflictError

from . import base


class ConflictErrorResponseSchema(base.BaseErrorResponseSchema):
    """Модель ответа о конфликте с текущим состоянием ресурса в соответствии с RFC7807."""

    type: str = Field(
        title="URI",
        description="Ссылка на документацию",
        examples=["/help-center?helpSectionId=errors#409"],
        default="/help-center?helpSectionId=errors#409",
    )
    title: str = Field(
        title="Ответ (описание)",
        description="Описание HTTP-кода ответа",
        max_length=256,
        examples=["Conflict"],
        default="Conflict",
    )
    status: int = Field(
        title="Ответ (код)",
        description="Число, строго соответствует HTTP-коду ответа",
        examples=[status.HTTP_409_CONFLICT],
        default=status.HTTP_409_CONFLICT,
    )
    detail: str = Field(
        title="Информация",
        description="Интернационализируемое описание ошибки",
        examples=["Ресурс уже существует"],
        default="Ресурс уже существует",
    )
    code: str = Field(
        title="Внутренний код ошибки",
        description="Числобуквенный код ошибки в рамках продукта FM",
        examples=["FM-409000"],
        default="FM-409000",
    )


def setup_conflict_exception_handlers(app: FastAPI) -> None:
    """
    Настройка обработчиков ошибок конфликта.

    Args:
        app: Приложение FastAPI.
    """

    @app.exception_handler(BaseConflictError)
    async def conflict_exception_handler(request: Request, exc: BaseConflictError) -> JSONResponse:
        return ConflictErrorResponseSchema.from_error(request, exc).json_response()
