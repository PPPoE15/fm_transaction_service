"""Перевод неизвестного исхода COMMIT в контрактную ошибку."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.modules.planning.domain.errors import (
    PlanCategoryError,
    PlanCategoryTypeError,
    PlanOutcomeUnknownError,
    RecurringViolationError,
)


async def outcome_unknown_handler(request: Request, exc: PlanOutcomeUnknownError) -> JSONResponse:
    """Сообщить неопределённый результат без обещания rollback и указания повторить POST."""
    return JSONResponse(
        {
            "type": "/help-center?helpSectionId=errors#503",
            "title": "Service Unavailable",
            "status": 503,
            "detail": exc.msg,
            "instance": request.url.path,
            "code": exc.code,
        },
        status_code=503,
        media_type="application/problem+json",
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Подключить обработчик при сборке приложения."""
    app.exception_handler(PlanOutcomeUnknownError)(outcome_unknown_handler)
    app.exception_handler(RecurringViolationError)(recurring_violation_handler)


def category_error_response(request: Request, exc: PlanCategoryError | PlanCategoryTypeError) -> JSONResponse:
    """Привязать ошибку категории подтверждения к полю формы по контракту FM-106."""
    return JSONResponse(
        {
            "type": "/help-center?helpSectionId=errors#400",
            "title": "Bad Request",
            "status": 400,
            "detail": exc.msg,
            "instance": request.url.path,
            "code": exc.code,
            "validation": [{"field": "category_uid", "message": exc.msg}],
        },
        status_code=400,
        media_type="application/problem+json",
    )


async def recurring_violation_handler(request: Request, exc: RecurringViolationError) -> JSONResponse:
    """Вернуть бизнес-ошибку серии с конкретным полем формы."""
    return JSONResponse(
        {
            "type": "/help-center?helpSectionId=errors#400",
            "title": "Bad Request",
            "status": 400,
            "detail": exc.msg,
            "instance": request.url.path,
            "code": exc.code,
            "validation": [{"field": exc.field, "rule": "value_error", "message": exc.msg}],
        },
        status_code=400,
        media_type="application/problem+json",
    )
