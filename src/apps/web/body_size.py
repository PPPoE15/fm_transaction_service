"""
Ограничение тела: 16 КиБ для обычного API, 6 МиБ для multipart-импорта (FM-93).

Основной лимит задаёт прокси (`client_max_body_size`), здесь — дубль на случай прямого доступа к сервису.
"""

from starlette import status
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.web.exception_handlers.base import BaseErrorResponseSchema

MAX_BODY_SIZE = 16 * 1024
MAX_IMPORT_BODY_SIZE = 6 * 1024 * 1024


class BodySizeLimitMiddleware:
    """
    ASGI-middleware: тело больше `max_body_size` байт отклоняется до авторизации и разбора JSON.

    Заявленный `Content-Length` проверяется сразу. Тело без него (chunked) читается до лимита и, если уложилось,
    передаётся приложению целиком: в памяти держится не больше `max_body_size` байт.
    """

    def __init__(self, app: ASGIApp, max_body_size: int = MAX_BODY_SIZE) -> None:
        """
        Обернуть приложение.

        Args:
            app: ASGI-приложение.
            max_body_size: Наибольший допустимый размер тела в байтах.
        """
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Пропустить запрос с телом в пределах лимита, иначе ответить 413."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import_request = scope.get("method") == "POST" and scope["path"].rstrip("/") in {
            "/transaction/import-export/imports/income",
            "/transaction/import-export/imports/outcome",
            "/import-export/imports/income",
            "/import-export/imports/outcome",
        }
        limit = MAX_IMPORT_BODY_SIZE if import_request else self.max_body_size
        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            # Для обычного API сервер проверяет Content-Length; импорт дополнительно считает реальные байты.
            if content_length.isascii() and content_length.isdigit() and int(content_length) > limit:
                await self._reject(scope, receive, send, import_request)
                return
            if not import_request:
                await self.app(scope, receive, send)
                return

        messages: list[Message] = []
        received = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if received > limit:
                await self._reject(scope, receive, send, import_request)
                return
            if not message.get("more_body", False):
                break

        async def replay() -> Message:
            """Повторить проверенное тело для внутреннего приложения."""
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, import_request: bool = False) -> None:
        """Ответить 413 с кодом обычного API или импорта в формате RFC 7807."""
        error = BaseErrorResponseSchema(
            type="/help-center?helpSectionId=errors#413",
            title="Content Too Large",
            status=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Тело запроса больше 6 МиБ" if import_request else "Тело запроса больше 16 КиБ",
            instance=scope["path"],
            code="FM-413301" if import_request else "FM-413000",
        )
        await error.json_response()(scope, receive, send)
