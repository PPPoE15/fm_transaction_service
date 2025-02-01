from fastapi import FastAPI

from modules.web.exception_handlers.forbidden_error import setup_forbidden_exception_handlers
from modules.web.exception_handlers.not_found_error import setup_not_found_exception_handlers
from modules.web.exception_handlers.server_error import setup_server_exception_handlers
from modules.web.exception_handlers.unauthorized_error import setup_unauthorized_exception_handlers
from modules.web.exception_handlers.validation_error import setup_validation_exception_handlers


def setup(app: FastAPI) -> None:
    """
    Настройка обработчиков внутренних ошибок.

    Args:
        app: Приложение FastAPI.
    """
    setup_server_exception_handlers(app)
    setup_unauthorized_exception_handlers(app)
    setup_validation_exception_handlers(app)
    setup_forbidden_exception_handlers(app)
    setup_not_found_exception_handlers(app)
