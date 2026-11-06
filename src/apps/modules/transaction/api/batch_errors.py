"""RFC7807 и привязка ошибок пакетного запроса к входным элементам."""

from collections.abc import Callable, Coroutine
from contextlib import suppress
from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from apps.modules.transaction.application.batch_models import BatchIssue, BatchTransactionError

_ITEM_LOCATION_LENGTH = 3


def validation_issues(exc: RequestValidationError) -> list[BatchIssue]:
    """Сохранить доступные индекс, корректный UID и поле без отражения значений из запроса."""
    result = []
    for error in exc.errors():
        loc = error["loc"]
        index = loc[2] if len(loc) >= _ITEM_LOCATION_LENGTH and loc[1] == "items" and isinstance(loc[2], int) else None
        uid = None
        if index is not None and isinstance(exc.body, dict):
            items = exc.body.get("items")
            if isinstance(items, list) and index < len(items) and isinstance(items[index], dict):
                with suppress(ValueError):
                    uid = UUID(str(items[index].get("uid")))
        path = loc[_ITEM_LOCATION_LENGTH:] if index is not None else loc[1:]
        field = ".".join(str(part) for part in path) if path and isinstance(path[0], str) else None
        result.append(BatchIssue(code="FM-422000", message=error["msg"], index=index, uid=uid, field=field))
    return result


def error_response(request: Request, status_code: int, errors: list[BatchIssue]) -> JSONResponse:
    """Сформировать пакетную ошибку с общим кодом и непустым массивом errors."""
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"/help-center?helpSectionId=errors#{status_code}",
            "title": HTTPStatus(status_code).phrase,
            "status": status_code,
            "detail": errors[0].message,
            "instance": request.url.path,
            "code": errors[0].code,
            "errors": [item.model_dump(mode="json", exclude_none=True) for item in errors],
        },
    )


class BatchRoute(APIRoute):
    """Маршрут с пакетными ошибками, включая ошибки разбора и валидации FastAPI."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Обернуть стандартный обработчик без изменения авторизации и бизнес-логики."""
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            """Преобразовать ошибки пакетной команды и входа в согласованный формат."""
            try:
                return await original(request)
            except RequestValidationError as exc:
                return error_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, validation_issues(exc))
            except BatchTransactionError as exc:
                return error_response(request, exc.status_code, exc.errors)

        return handle
