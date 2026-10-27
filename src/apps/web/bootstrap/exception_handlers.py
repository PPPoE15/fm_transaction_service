from fastapi import FastAPI

from apps.modules.import_export.api import setup_exception_handlers as setup_import_exception_handlers
from apps.web.exception_handlers.conflict_error import setup_conflict_exception_handlers
from apps.web.exception_handlers.forbidden_error import setup_forbidden_exception_handlers
from apps.web.exception_handlers.not_found_error import setup_not_found_exception_handlers
from apps.web.exception_handlers.server_error import setup_server_exception_handlers
from apps.web.exception_handlers.unauthorized_error import setup_unauthorized_exception_handlers
from apps.web.exception_handlers.validation_error import setup_validation_exception_handlers


# TODO(FM-52): обработчика `HTTPException` нет — ошибка разбора тела (невалидный UTF-8, число длиннее 4300 цифр)
# отдаётся стандартным `400 {"detail": ...}` без `code` и не в RFC 7807, хотя по контракту формат — 422 `FM-422000`,
# а 400 у `POST /transactions` — только `FM-400201`/`FM-400202`. Аналог для сервиса авторизации — FM-19; для этого
# сервиса задачи нет (было до FM-52).
def setup(app: FastAPI) -> None:
    """
    Настройка обработчиков внутренних ошибок.

    Args:
        app: Приложение FastAPI.
    """
    setup_import_exception_handlers(app)
    setup_server_exception_handlers(app)
    setup_unauthorized_exception_handlers(app)
    setup_validation_exception_handlers(app)
    setup_forbidden_exception_handlers(app)
    setup_not_found_exception_handlers(app)
    setup_conflict_exception_handlers(app)
