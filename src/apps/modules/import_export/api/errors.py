from dataclasses import asdict
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.modules.import_export.domain.errors import ImportFileError


async def import_error_handler(request: Request, exc: ImportFileError) -> JSONResponse:
    """Представить ошибку разбора в RFC 7807 с адресами полей для ответов 422."""
    content: dict[str, object] = {
        "type": f"/help-center?helpSectionId=errors#{exc.status}",
        "title": HTTPStatus(exc.status).phrase,
        "status": exc.status,
        "detail": exc.msg,
        "instance": request.url.path,
        "code": exc.code,
    }
    if exc.status == HTTPStatus.UNPROCESSABLE_ENTITY:
        content.update(
            imported_count=0, errors=[asdict(issue) for issue in exc.errors], errors_truncated=exc.errors_truncated
        )
    if exc.code == "FM-503301":
        content["outcome"] = "unknown"
    return JSONResponse(content, status_code=exc.status, media_type="application/problem+json")


def setup_exception_handlers(app: FastAPI) -> None:
    """Подключить перевод ошибок модуля в HTTP при сборке приложения."""
    app.exception_handler(ImportFileError)(import_error_handler)
