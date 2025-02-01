from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette import status

from . import base


class ServerErrorResponseSchema(base.BaseErrorResponseSchema):
    """Модель ответа об ошибке валидации в соответствии с RFC7807."""

    type: str = Field(
        title="URI",
        description="Ссылка на документацию",
        example="/help-center?helpSectionId=errors#500",
        default="/help-center?helpSectionId=errors#500",
    )
    title: str = Field(
        title="Ответ (описание)",
        description="Описание HTTP-кода ответа",
        max_length=256,
        example="Internal Server Error",
        default="Internal Server Error",
    )
    status: int = Field(
        title="Ответ (код)",
        description="Число, строго соответствует HTTP-коду ответа",
        example=status.HTTP_500_INTERNAL_SERVER_ERROR,
        default=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    detail: str = Field(
        title="Информация",
        description="Интернациолизируемое описание ошибки",
        example="Внутренняя ошибка сервера",
        default="Внутренняя ошибка сервера",
    )
    code: str = Field(
        title="Внутренний код ошибки",
        description="Числобуквенный код ошибки в рамках продута ACM",
        example="ACM-500000",
        default="ACM-500000",
    )


def setup_server_exception_handlers(app: FastAPI) -> None:
    """
    Настройка обработчиков внутренних ошибок.

    Args:
        app: Приложение FastAPI.
    """

    @app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
    async def server_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        instance = request.url.path
        return ServerErrorResponseSchema(instance=instance, detail=str(exc)).json_response()
