"""Ограничение размера тела запроса (контракт, «Объёмы»): больше 16 КиБ — 413 `FM-413000` до разбора тела."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient, Response
from starlette import status

from apps.web.body_size import MAX_BODY_SIZE
from tests.conftest import TokenFactory

URL = "/transactions"


def _json_of_size(size: int) -> bytes:
    """Синтаксически верный JSON-объект ровно из `size` байт."""
    prefix, suffix = b'{"description": "', b'"}'
    return prefix + b"x" * (size - len(prefix) - len(suffix)) + suffix


def _assert_too_large(response: Response) -> None:
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "FM-413000"
    assert body["status"] == status.HTTP_413_CONTENT_TOO_LARGE
    assert body["instance"] == "/transaction/transactions"


async def test_body_over_limit(client: AsyncClient, make_token: TokenFactory) -> None:
    """Тело на байт больше 16 КиБ — 413 `FM-413000` в формате RFC 7807."""
    response = await client.post(
        URL,
        headers={"Authorization": f"Bearer {make_token()}", "Content-Type": "application/json"},
        content=_json_of_size(MAX_BODY_SIZE + 1),
    )

    _assert_too_large(response)


async def test_body_over_limit_without_auth(client: AsyncClient) -> None:
    """Лимит проверяется до авторизации и разбора: тело не читается целиком ни при каком токене."""
    response = await client.post(URL, content=b"x" * (MAX_BODY_SIZE * 4))

    _assert_too_large(response)


async def test_chunked_body_over_limit(client: AsyncClient, make_token: TokenFactory) -> None:
    """Тело без `Content-Length` (chunked) тоже ограничено: считаются фактически полученные байты."""

    async def _chunks() -> AsyncIterator[bytes]:
        for chunk in [b"x" * 4096] * 5:
            yield chunk

    response = await client.post(
        URL,
        headers={"Authorization": f"Bearer {make_token()}", "Content-Type": "application/json"},
        content=_chunks(),
    )

    assert "content-length" not in response.request.headers
    _assert_too_large(response)


@pytest.mark.parametrize("chunked", [False, True], ids=["Content-Length", "chunked"])
async def test_body_at_limit_is_processed(client: AsyncClient, make_token: TokenFactory, *, chunked: bool) -> None:
    """Тело ровно 16 КиБ доходит до обработчика: ответ — от валидации тела (422), а не 413."""
    content = _json_of_size(MAX_BODY_SIZE)

    async def _chunks() -> AsyncIterator[bytes]:
        yield content[:1000]
        yield content[1000:]

    response = await client.post(
        URL,
        headers={"Authorization": f"Bearer {make_token()}", "Content-Type": "application/json"},
        content=_chunks() if chunked else content,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"] == "FM-422000"
