"""Длительный разбор файла не останавливает обработку других HTTP-запросов."""

import asyncio
import threading
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from apps.modules.import_export.application import importing
from apps.modules.import_export.application.parsing import read_file_records
from apps.modules.import_export.domain.models import FileFormat, RawRecord, TransactionKind
from apps.modules.import_export.infrastructure.templates import generate_template
from tests.conftest import TokenFactory


async def test_other_requests_continue_while_file_is_parsed(
    client: AsyncClient,
    make_token: TokenFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Обычный запрос завершается, пока импорт ещё занят синхронным файловым разбором."""
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    original = read_file_records

    def slow_reader(
        content: bytes,
        *,
        transaction_type: TransactionKind,
        file_format: FileFormat,
        filename: str,
        content_type: str | None = None,
    ) -> list[RawRecord]:
        """Задержать настоящий парсер до завершения соседнего HTTP-запроса."""
        loop.call_soon_threadsafe(started.set)
        # Тайм-аут только освобождает тест при регрессии, когда event loop заблокирован самим парсером.
        release.wait(timeout=5)
        return original(
            content,
            transaction_type=transaction_type,
            file_format=file_format,
            filename=filename,
            content_type=content_type,
        )

    monkeypatch.setattr(importing, "read_file_records", slow_reader)
    headers = {"Authorization": f"Bearer {make_token()}"}
    request = asyncio.create_task(
        client.post(
            "/import-export/imports/outcome?format=xlsx",
            headers=headers,
            files={"file": ("a.xlsx", generate_template("outcome", "xlsx"), "application/octet-stream")},
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 10)
        ordinary = await client.get("/import-export/templates/outcome?format=csv", headers=headers)
        assert ordinary.status_code == HTTPStatus.OK
        assert not request.done(), "Файловый разбор заблокировал соседний HTTP-запрос"
    finally:
        release.set()
        response = await request
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "FM-422302"
