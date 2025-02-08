from fastapi import FastAPI

# from prometheus_client import make_asgi_app

# from modules.web.config import app_settings

# from .metrics import PrometheusMiddleware


def setup(app: FastAPI) -> None:  # noqa: ARG001
    """
    Настройка обработчиков внутренних приложений.

    Args:
        app: Приложение FastAPI.
    """
    # TODO: Есть конфликт с зависимостями Dramatiq 1.15.0
    # app.add_middleware(PrometheusMiddleware, app_name=app_settings.PROJECT_NAME)
    # metrics_app = make_asgi_app()
    # app.mount("/metrics", metrics_app)
