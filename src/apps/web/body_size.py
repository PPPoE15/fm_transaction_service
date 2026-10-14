"""
Ограничение размера тела запроса: больше 16 КиБ — 413 `FM-413000` (контракт, «Объёмы»).

Основной лимит задаёт прокси (`client_max_body_size`), здесь — дубль на случай прямого доступа к сервису.
"""

from starlette import status
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.web.exception_handlers.base import BaseErrorResponseSchema

MAX_BODY_SIZE = 16 * 1024


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

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            # Тело длиннее заявленного сервер (h11/httptools) приложению не передаст, поэтому заголовка достаточно.
            if content_length.isdigit() and int(content_length) > self.max_body_size:
                await self._reject(scope, receive, send)
                return
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
            if received > self.max_body_size:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def replay() -> Message:
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        """Ответ 413 `FM-413000` в формате RFC 7807, как у остальных ошибок."""
        error = BaseErrorResponseSchema(
            type="/help-center?helpSectionId=errors#413",
            title="Content Too Large",
            status=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Тело запроса больше 16 КиБ",
            instance=scope["path"],
            code="FM-413000",
        )
        await error.json_response()(scope, receive, send)
