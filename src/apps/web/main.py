from types import TracebackType

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.web.bootstrap import logger
from apps.web.config import app_settings


class LifespanEvent:
    """Логика обработки событий 'starts up' и 'shutting down'."""

    def __init__(self, application: FastAPI) -> None:
        """
        Конструктор LifespanEvent.

        Args:
            application: FastAPI-приложение.
        """
        self.app = application

    async def __aenter__(self) -> None:
        """Событие выполняющееся при starts up."""
        if not app_settings.HEALTHCHECK_MODE:
            logger.setup()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Событие выполняющееся при shutting down.

        Args:
            exc_type: Класс ошибки.
            exc_value: Объект ошибки.
            traceback: Объект трассировки ошибки.
        """


def build_app() -> FastAPI:
    """Инициализировать и настроить FastAPI приложение."""
    fastapi_app = FastAPI(
        title=app_settings.SERVICE_NAME,
        description="Сервис управления конфигурациями",
        openapi_url="/api/openapi.json",
        lifespan=LifespanEvent,
    )

    if not app_settings.HEALTHCHECK_MODE:
        from apps.web.router import main_router  # noqa: PLC0415

        fastapi_app.include_router(main_router, prefix="/transaction")
        fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return fastapi_app


app = build_app()
