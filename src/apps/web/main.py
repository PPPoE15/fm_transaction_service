from types import TracebackType
from typing import Optional, Type

from fastapi import FastAPI

from apps.web.bootstrap import logger

# from modules.web.bootstrap import dramatiq, logger, metrics, rmq
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
            # await rmq.connect()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        Событие выполняющееся при shutting down.

        Args:
            exc_type: Класс ошибки.
            exc_value: Объект ошибки.
            traceback: Объект трассировки ошибки.
        """
        # if not app_settings.HEALTHCHECK_MODE:
        #     await rmq.disconnect()


def build_app() -> FastAPI:
    """Инициализировать и настроить FastAPI приложение."""
    fastapi_app = FastAPI(
        title=app_settings.PROJECT_NAME,
        description="Сервис управления конфигурациями",
        openapi_url=f"{app_settings.URL_PREFIX}/openapi.json",
        lifespan=LifespanEvent,
    )

    if not app_settings.HEALTHCHECK_MODE:
        # dramatiq.setup()

        from apps.web.router import main_router

        fastapi_app.include_router(main_router)

    # metrics.setup(fastapi_app)

    return fastapi_app


app = build_app()
