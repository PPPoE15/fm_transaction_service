"""Контракт multipart и фактические лимиты загрузки."""

from collections.abc import AsyncIterator
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.conftest import TokenFactory

URL = "/import-export/imports/outcome?format=csv"


@pytest.mark.parametrize(
    "parts",
    [
        [],
        [("file", (None, "text"))],
        [("file", ("a.csv", b"x")), ("file", ("b.csv", b"y"))],
        [("file", ("a.csv", b"x")), ("extra", (None, "value"))],
        [("file", ("", b"x"))],
    ],
)
async def test_invalid_parts(client: AsyncClient, make_token: TokenFactory, parts: list) -> None:
    """Ровно одна file-part с непустым filename обязательна, любые лишние поля запрещены."""
    # Пустой список httpx не кодирует как multipart, поэтому задаём пустое тело явно.
    headers = {"Authorization": f"Bearer {make_token()}"}
    if parts:
        response = await client.post(URL, headers=headers, files=parts)
    else:
        response = await client.post(
            URL, headers={**headers, "Content-Type": "multipart/form-data; boundary=x"}, content=b"--x--\r\n"
        )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "FM-422000"
    assert response.json()["validation"]


@pytest.mark.parametrize(
    ("content_type", "content"),
    [
        ("multipart/form-data", b"x"),
        (
            "multipart/form-data; boundary=x",
            b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n\r\nx',
        ),
    ],
)
async def test_malformed_multipart(
    client: AsyncClient,
    make_token: TokenFactory,
    content_type: str,
    content: bytes,
) -> None:
    """Отсутствующая boundary и незавершённая часть — ошибка тела HTTPStatus.BAD_REQUEST."""
    response = await client.post(
        URL, headers={"Authorization": f"Bearer {make_token()}", "Content-Type": content_type}, content=content
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert response.json()["code"] == "FM-400301"


async def test_wrong_content_type(client: AsyncClient, make_token: TokenFactory) -> None:
    """JSON вместо multipart возвращает контрактный HTTPStatus.UNSUPPORTED_MEDIA_TYPE."""
    response = await client.post(URL, headers={"Authorization": f"Bearer {make_token()}"}, json={})
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE, response.text
    assert response.json()["code"] == "FM-415301"


@pytest.mark.parametrize(("size", "code"), [(20_000, "FM-422301"), (5 * 1024 * 1024 + 1, "FM-413301")])
async def test_file_limits(client: AsyncClient, make_token: TokenFactory, size: int, code: str) -> None:
    """Импорт допускает больше 16 КиБ, но не больше 5 МиБ самого файла."""
    response = await client.post(
        URL, headers={"Authorization": f"Bearer {make_token()}"}, files={"file": ("a.csv", b"x" * size, "text/csv")}
    )
    assert response.json()["code"] == code, response.text


@pytest.mark.parametrize("declared_length", [None, "1"])
async def test_actual_body_limit(client: AsyncClient, declared_length: str | None) -> None:
    """Реальные байты ограничены 6 МиБ даже при отсутствии или ложном Content-Length."""

    async def chunks() -> AsyncIterator[bytes]:
        """Передать тело с превышением лимита без большого единовременного выделения памяти."""
        for chunk in [b"x" * (1024 * 1024)] * 7:
            yield chunk

    headers = {} if declared_length is None else {"Content-Length": declared_length}
    response = await client.post(URL, headers=headers, content=chunks())
    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert response.json()["code"] == "FM-413301"


async def test_import_requires_auth(client: AsyncClient) -> None:
    """Авторизация выполняется до разбора файлового содержимого."""
    response = await client.post(URL, files={"file": ("a.csv", b"x")})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_openapi_import_contract(client: AsyncClient) -> None:
    """Клиенты OpenAPI видят обязательный бинарный файл и конкретную схему результата."""
    response = await client.get("http://test/api/openapi.json")
    assert response.status_code == HTTPStatus.OK
    schema = response.json()
    operation = schema["paths"]["/transaction/import-export/imports/{transaction_type}"]["post"]
    body = operation["requestBody"]
    assert body["required"] is True
    file_schema = body["content"]["multipart/form-data"]["schema"]
    assert file_schema["required"] == ["file"]
    assert file_schema["properties"]["file"] == {"type": "string", "format": "binary"}
    result_ref = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    result = schema["components"]["schemas"][result_ref.rsplit("/", 1)[-1]]
    assert set(result["required"]) == {"transaction_type", "imported_count"}
    assert result["additionalProperties"] is False
