from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette import status
from starlette.exceptions import HTTPException

from . import base


class UnauthorizedErrorResponseSchema(base.BaseErrorResponseSchema):
    """Модель ответа об ошибке авторизации в соответствии с RFC7807."""

    type: str = Field(
        title="URI",
        description="Ссылка на документацию",
        examples=["/help-center?helpSectionId=errors#401"],
        default="/help-center?helpSectionId=errors#401",
    )
    title: str = Field(
        title="Ответ (описание)",
        description="Описание HTTP-кода ответа",
        max_length=256,
        examples=["Unauthorized"],
        default="Unauthorized",
    )
    status: int = Field(
        title="Ответ (код)",
        description="Число, строго соответствует HTTP-коду ответа",
        examples=[status.HTTP_401_UNAUTHORIZED],
        default=status.HTTP_401_UNAUTHORIZED,
    )
    detail: str = Field(
        title="Информация",
        description="Интернациолизируемое описание ошибки",
        examples=["Неавторизованный запрос"],
        default="Неавторизованный запрос",
    )
    code: str = Field(
        title="Внутренний код ошибки",
        description="Числобуквенный код ошибки в рамках продута FM",
        examples=["FM-401000"],
        default="FM-401000",
    )


def setup_unauthorized_exception_handlers(app: FastAPI) -> None:
    """
    Настройка обработчиков ошибок авторизации.

    Args:
        app: Приложение FastAPI.
    """

    @app.exception_handler(status.HTTP_401_UNAUTHORIZED)
    async def unauthorized_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        instance = request.url.path
        return UnauthorizedErrorResponseSchema(instance=instance, detail=exc.detail).json_response()
