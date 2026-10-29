"""Импорт сохраняет обычные операции атомарно и не раскрывает чужие категории."""

from http import HTTPStatus
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from apps.modules.import_export.infrastructure.uow import ImportUnitOfWork
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory

IMPORT_AMOUNT = 123
MAX_TEST_ROWS = 10000
FLEXIBLE_ROW_COUNT = 2


async def add_category(client: AsyncClient, headers: dict[str, str], name: str, kind: str) -> str:
    """Создать категорию через обычный публичный API."""
    response = await client.post("/categories", headers=headers, json={"name": name, "category_type": kind})
    assert response.status_code == HTTPStatus.CREATED, response.text
    return str(response.json()["uid"])


def upload_content(kind: str, file_format: str) -> bytes:
    """Подготовить два одинаковых ряда, которые должны сохраниться отдельно."""
    rows = [
        ("Дата", "Сумма", "Категория", "Описание"),
        ("01.10.2026", "123", " Еда ", "Тест"),
        ("01.10.2026", "123", " Еда ", "Тест"),
    ]
    if file_format == "csv":
        return "\n".join(";".join(row) for row in rows).encode()
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Доходы" if kind == "income" else "Расходы"
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


@pytest.mark.db
@pytest.mark.parametrize("kind", ["income", "outcome"])
@pytest.mark.parametrize("file_format", ["csv", "xlsx"])
async def test_import_and_repeat(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    kind: str,
    file_format: str,
) -> None:
    """Четыре варианта сохраняют точные значения, дубликаты и повторную загрузку."""
    owner = uuid4()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    category_uid = await add_category(client, headers, "Еда", kind)
    for expected in (2, 4):
        response = await client.post(
            f"/import-export/imports/{kind}?format={file_format}",
            headers=headers,
            files={"file": (f"input.{file_format}", upload_content(kind, file_format), "application/octet-stream")},
        )
        assert response.status_code == HTTPStatus.CREATED, response.text
        assert response.json() == {"transaction_type": kind, "imported_count": 2}
        listed = await client.get("/transactions", headers=headers)
        assert listed.status_code == HTTPStatus.OK
        body = listed.json()
        assert body["total"] == expected
        for item in body["content"]:
            assert item["category"]["uid"] == category_uid
            assert item["money_sum"] == IMPORT_AMOUNT
            assert item["transaction_date"] == "2026-10-01T00:00:00"
            assert item["description"] == "Тест"


@pytest.mark.db
async def test_unknown_category_rolls_back(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
) -> None:
    """Чужая категория в последней строке не сохраняет даже корректную первую."""
    owner: UUID = uuid4()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    await add_category(client, headers, "Еда", "outcome")
    await add_category(client, {"Authorization": f"Bearer {make_token()}"}, "Чужая", "outcome")
    content = "Дата;Сумма;Категория;Описание\n01.10.2026;123;Еда;\n01.10.2026;123;Чужая;".encode()
    response = await client.post(
        "/import-export/imports/outcome?format=csv", headers=headers, files={"file": ("input.csv", content, "text/csv")}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    result = response.json()
    assert result["code"] == "FM-422303"
    assert result["imported_count"] == 0
    assert [(error["row"], error["field"], error["reason"]) for error in result["errors"]] == [
        (3, "category", "unknown_category")
    ]
    listed = await client.get("/transactions", headers=headers)
    assert listed.json()["total"] == 0


@pytest.mark.db
async def test_combined_errors_in_column_order(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
) -> None:
    """Ошибки категории не теряются даже в строках с неверной суммой или датой."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    content = "Дата;Сумма;Категория;Описание\nwrong;1.5;Нет;\n01.10.2026;1;Нет;".encode()
    response = await client.post(
        "/import-export/imports/outcome?format=csv", headers=headers, files={"file": ("input.csv", content, "text/csv")}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    result = response.json()
    assert [(error["row"], error["field"], error["reason"]) for error in result["errors"]] == [
        (2, "date", "invalid_date"),
        (2, "amount", "invalid_amount"),
        (2, "category", "unknown_category"),
        (3, "category", "unknown_category"),
    ]


@pytest.mark.db
@pytest.mark.parametrize("phase", ["flush", "commit"])
async def test_storage_failure_outcome(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    """Сбой записи откатывает пакет, потеря ответа COMMIT не заявляет ложный rollback."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    await add_category(client, headers, "Еда", "outcome")
    original = getattr(AsyncSession, phase)

    async def failing_operation(session: AsyncSession, *args: object, **kwargs: object) -> None:
        """Имитировать потерю соединения после реальной записи или реального commit."""
        await original(session, *args, **kwargs)
        raise DBAPIError(None, None, ConnectionError("connection lost"), connection_invalidated=True)

    monkeypatch.setattr(AsyncSession, phase, failing_operation)
    response = await client.post(
        "/import-export/imports/outcome?format=csv",
        headers=headers,
        files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
    )
    assert response.status_code == (
        HTTPStatus.INTERNAL_SERVER_ERROR if phase == "flush" else HTTPStatus.SERVICE_UNAVAILABLE
    ), response.text
    result = response.json()
    assert result["code"] == ("FM-500301" if phase == "flush" else "FM-503301")
    if phase == "commit":
        assert result["outcome"] == "unknown"
        assert "imported_count" not in result
        assert "retry-after" not in response.headers
    monkeypatch.undo()
    listed = await client.get("/transactions", headers=headers)
    assert listed.json()["total"] == (0 if phase == "flush" else 2)


@pytest.mark.db
async def test_unknown_commit_survives_cleanup_failure(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка rollback после потери ответа commit не скрывает неизвестный результат импорта."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    await add_category(client, headers, "Еда", "outcome")
    original_commit = AsyncSession.commit

    async def lost_commit(session: AsyncSession) -> None:
        """Сохранить данные, но потерять ответ сервера."""
        await original_commit(session)
        raise DBAPIError(None, None, ConnectionError("lost"), connection_invalidated=True)

    async def lost_rollback(uow: ImportUnitOfWork) -> None:
        """Повторное обращение к потерянному соединению тоже не удаётся."""
        raise ConnectionError

    monkeypatch.setattr(AsyncSession, "commit", lost_commit)
    monkeypatch.setattr(ImportUnitOfWork, "rollback", lost_rollback)
    response = await client.post(
        "/import-export/imports/outcome?format=csv",
        headers=headers,
        files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
    )
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, response.text
    assert response.json()["code"] == "FM-503301"
    assert response.json()["outcome"] == "unknown"


@pytest.mark.db
@pytest.mark.parametrize(("rows", "truncated"), [(100, False), (101, True)])
async def test_category_errors_capped(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    rows: int,
    truncated: bool,
) -> None:
    """Сто ошибок возвращаются полностью, сто первая выставляет признак усечения."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    content = ("Дата;Сумма;Категория;Описание\n" + "01.10.2026;1;Нет;\n" * rows).encode()
    response = await client.post(
        "/import-export/imports/outcome?format=csv", headers=headers, files={"file": ("a.csv", content, "text/csv")}
    )
    result = response.json()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert [error["row"] for error in result["errors"]] == list(range(2, 102))
    assert result["errors_truncated"] is truncated


@pytest.mark.db
async def test_ambiguous_trimmed_category(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
) -> None:
    """Старые имена с пробелами по краям сравниваются после strip и могут стать неоднозначными."""
    owner = uuid4()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    await add_category(client, headers, "Еда", "outcome")
    async with async_session_factory() as session:
        await session.execute(
            text("INSERT INTO categories (uid,user_uid,name,category_type) VALUES (:uid,:owner,' Еда ','outcome')"),
            {"uid": uuid4(), "owner": owner},
        )
        await session.commit()
    response = await client.post(
        "/import-export/imports/outcome?format=csv",
        headers=headers,
        files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert [error["reason"] for error in response.json()["errors"]] == ["ambiguous_category", "ambiguous_category"]
    listed = await client.get("/transactions", headers=headers)
    assert listed.json()["total"] == 0


@pytest.mark.db
@pytest.mark.parametrize("row_count", [10000, 10001])
async def test_maximum_import_rows(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    row_count: int,
) -> None:
    """Лимит строк включителен; превышение не сохраняет первые десять тысяч операций."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    await add_category(client, headers, "Еда", "outcome")
    content = ("Дата;Сумма;Категория;Описание\n" + "01.10.2026;1;Еда;\n" * row_count).encode()
    response = await client.post(
        "/import-export/imports/outcome?format=csv", headers=headers, files={"file": ("a.csv", content, "text/csv")}
    )
    if row_count == MAX_TEST_ROWS:
        assert response.status_code == HTTPStatus.CREATED, response.text
        assert response.json() == {"transaction_type": "outcome", "imported_count": row_count}
    else:
        assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE, response.text
        assert response.json()["code"] == "FM-413302"
    listed = await client.get("/transactions", headers=headers)
    assert listed.json()["total"] == (row_count if row_count == MAX_TEST_ROWS else 0)


@pytest.mark.db
@pytest.mark.parametrize(("name", "kind"), [("еда", "outcome"), ("Еда", "income")])
async def test_category_matching_is_exact_and_type_scoped(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    name: str,
    kind: str,
) -> None:
    """Категория другого регистра или другого типа не подходит для импорта расходов."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    await add_category(client, headers, name, kind)
    response = await client.post(
        "/import-export/imports/outcome?format=csv",
        headers=headers,
        files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [item["reason"] for item in response.json()["errors"]] == ["unknown_category", "unknown_category"]


@pytest.mark.db
@pytest.mark.parametrize("last_category", ["Еда", "Нет"])
async def test_flexible_csv_atomic_import(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    last_category: str,
) -> None:
    """Гибкий CSV сохраняется целиком либо сообщает физическую строку и откатывает пакет."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    await add_category(client, headers, "Еда", "outcome")
    content = (
        "Лишнее, Описание ,Категория,Сумма,Дата\n"
        'заметка," текст\nпродолжение ", Еда , 123 ,01|10|26\n'
        f"данные, конец ,{last_category}, 123 ,01.10.26"
    ).encode()
    response = await client.post(
        "/import-export/imports/outcome?format=csv", headers=headers, files={"file": ("a.csv", content, "text/csv")}
    )
    listed = await client.get("/transactions", headers=headers)
    if last_category == "Еда":
        assert response.status_code == HTTPStatus.CREATED, response.text
        assert response.json()["imported_count"] == FLEXIBLE_ROW_COUNT
        assert listed.json()["total"] == FLEXIBLE_ROW_COUNT
        assert {item["description"] for item in listed.json()["content"]} == {"текст\nпродолжение", "конец"}
        assert all(item["money_sum"] == IMPORT_AMOUNT for item in listed.json()["content"])
    else:
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
        assert response.json()["imported_count"] == 0
        assert [(issue["row"], issue["field"], issue["reason"]) for issue in response.json()["errors"]] == [
            (4, "category", "unknown_category")
        ]
        assert listed.json()["total"] == 0
