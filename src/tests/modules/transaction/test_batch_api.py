"""Пакетное сохранение и частичное удаление операций."""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.transaction.infrastructure.uow import TransactionUnitOfWork
from tests.conftest import TokenFactory


@pytest.fixture
async def batch_seed(
    db_engine: AsyncEngine, client: AsyncClient, make_token: TokenFactory
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Создать две реальные операции для проверки атомарности пакета."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    category = await client.post("/categories", headers=headers, json={"name": "Еда", "category_type": "outcome"})
    items = []
    for amount in (100, 200):
        response = await client.post(
            "/transactions",
            headers=headers,
            json={
                "category_uid": category.json()["uid"],
                "transaction_date": "2026-10-01T12:34:56.123456",
                "money_sum": amount,
                "transaction_type": "outcome",
                "description": "Обед",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        items.append(response.json())
    return headers, items


@pytest.mark.db
async def test_atomic_batch_and_repeat(
    client: AsyncClient, batch_seed: tuple[dict[str, str], list[dict[str, Any]]]
) -> None:
    """Пакет сохраняет время и порядок; повтор со старой версией не меняет данные."""
    headers, original = batch_seed
    items = [
        {"uid": item["uid"], "expected_version": 1, "changes": {"date": "2026-11-02", "description": None}}
        for item in reversed(original)
    ]
    response = await client.patch("/transactions/batch", headers=headers, json={"items": items})
    assert response.status_code == status.HTTP_200_OK, response.text
    expected = [
        {**item, "version": 2, "transaction_date": "2026-11-02T12:34:56.123456", "description": None}
        for item in reversed(original)
    ]
    assert response.json() == {"content": expected}
    repeated = await client.patch("/transactions/batch", headers=headers, json={"items": items})
    assert repeated.status_code == status.HTTP_409_CONFLICT, repeated.text
    assert repeated.json()["code"] == "FM-409204"
    assert repeated.json()["errors"][0]["uid"] == items[0]["uid"]
    actual = (await client.get("/transactions", headers=headers)).json()["content"]
    assert sorted(actual, key=lambda item: item["uid"]) == sorted(expected, key=lambda item: item["uid"])


@pytest.mark.db
@pytest.mark.parametrize("failure", ["missing", "version", "category", "type"])
async def test_batch_failure_rolls_back(
    client: AsyncClient, batch_seed: tuple[dict[str, str], list[dict[str, Any]]], failure: str
) -> None:
    """Ошибка позднего элемента не сохраняет ранний; коды соответствуют причине."""
    headers, original = batch_seed
    items = [{"uid": item["uid"], "expected_version": 1, "changes": {"money_sum": 999}} for item in original]
    expected_status = status.HTTP_400_BAD_REQUEST
    if failure == "missing":
        items[1]["uid"] = str(uuid4())
        expected_status = status.HTTP_404_NOT_FOUND
    elif failure == "version":
        items[1]["expected_version"] = 10
        expected_status = status.HTTP_409_CONFLICT
    elif failure == "category":
        items[1]["changes"] = {"category_uid": str(uuid4())}
    else:
        category = await client.post(
            "/categories", headers=headers, json={"name": "Зарплата", "category_type": "income"}
        )
        items[1]["changes"] = {"category_uid": category.json()["uid"]}
    response = await client.patch("/transactions/batch", headers=headers, json={"items": items})
    assert response.status_code == expected_status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"]
    actual = (await client.get("/transactions", headers=headers)).json()["content"]
    assert sorted(actual, key=lambda item: item["uid"]) == sorted(original, key=lambda item: item["uid"])


@pytest.mark.db
async def test_partial_delete_and_repeat(
    client: AsyncClient, batch_seed: tuple[dict[str, str], list[dict[str, Any]]]
) -> None:
    """Удаляется только доступная актуальная строка; ошибки и повтор возвращаются внутри 200."""
    headers, original = batch_seed
    missing = str(uuid4())
    items = [
        {"uid": original[0]["uid"], "expected_version": 1},
        {"uid": original[1]["uid"], "expected_version": 10},
        {"uid": missing, "expected_version": 1},
    ]
    response = await client.post("/transactions/batch-delete", headers=headers, json={"items": items})
    assert response.status_code == status.HTTP_200_OK, response.text
    results = response.json()["results"]
    assert [row["status"] for row in results] == [204, 409, 404]
    assert [row["index"] for row in results] == [0, 1, 2]
    assert [row["uid"] for row in results] == [item["uid"] for item in items]
    assert results[0] == {"index": 0, "uid": items[0]["uid"], "status": 204}
    assert results[1]["code"] == "FM-409204"
    assert results[2]["code"] == "FM-404000"
    assert (await client.get("/transactions", headers=headers)).json()["content"] == [original[1]]
    repeated = await client.post("/transactions/batch-delete", headers=headers, json={"items": items})
    assert repeated.status_code == status.HTTP_200_OK
    assert [row["status"] for row in repeated.json()["results"]] == [404, 409, 404]


@pytest.mark.parametrize(("method", "path"), [("PATCH", "/transactions/batch"), ("POST", "/transactions/batch-delete")])
@pytest.mark.parametrize("kind", ["empty", "duplicate", "too_many", "missing_version", "extra", "null_version"])
async def test_batch_invalid_structure(
    client: AsyncClient, make_token: TokenFactory, method: str, path: str, kind: str
) -> None:
    """Структура всего пакета проверяется до БД, ошибки имеют массив errors."""
    item: dict[str, Any] = {"uid": str(uuid4()), "expected_version": 1}
    if method == "PATCH":
        item["changes"] = {"description": None}
    items = [item]
    if kind == "empty":
        items = []
    elif kind == "duplicate":
        items = [item, item]
    elif kind == "too_many":
        items = [{**item, "uid": str(uuid4())} for _ in range(101)]
    elif kind == "missing_version":
        del item["expected_version"]
    elif kind == "null_version":
        item["expected_version"] = None
    else:
        item["unknown"] = True
    response = await client.request(
        method, path, headers={"Authorization": f"Bearer {make_token()}"}, json={"items": items}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["errors"]


@pytest.mark.db
async def test_overlapping_batches_have_one_winner(
    client: AsyncClient, batch_seed: tuple[dict[str, str], list[dict[str, Any]]]
) -> None:
    """Пакеты в противоположном порядке блокируют строки стабильно и не теряют изменения."""
    headers, original = batch_seed
    first = [{"uid": row["uid"], "expected_version": 1, "changes": {"money_sum": 500}} for row in original]
    responses = await asyncio.gather(
        client.patch("/transactions/batch", headers=headers, json={"items": first}),
        client.patch("/transactions/batch", headers=headers, json={"items": list(reversed(first))}),
    )
    assert sorted(response.status_code for response in responses) == [status.HTTP_200_OK, status.HTTP_409_CONFLICT]


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"date": None},
        {"date": "2026-02-30"},
        {"date": "1999-01-01"},
        {"date": "2026-01-01T12:00:00"},
        {"date": 1},
        {"money_sum": True},
        {"money_sum": 1.5},
        {"money_sum": 0},
        {"category_uid": None},
        {"description": "x" * 501},
        {"description": "\x00"},
        {"transaction_type": "income"},
    ],
)
async def test_batch_rejects_invalid_changes(
    client: AsyncClient, make_token: TokenFactory, changes: dict[str, Any]
) -> None:
    """Недопустимые правки не доходят до записи; ошибка содержит UID и индекс строки."""
    uid = str(uuid4())
    response = await client.patch(
        "/transactions/batch",
        headers={"Authorization": f"Bearer {make_token()}"},
        json={"items": [{"uid": uid, "expected_version": 1, "changes": changes}]},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["errors"][0]["index"] == 0
    assert response.json()["errors"][0]["uid"] == uid


@pytest.mark.db
@pytest.mark.parametrize("method", ["PATCH", "POST"])
async def test_unexpected_failure_rolls_back_batch(
    client: AsyncClient,
    batch_seed: tuple[dict[str, str], list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    """Сбой после flush до commit откатывает все записи и удаления запроса."""

    async def fail_before_commit(self: TransactionUnitOfWork) -> None:
        """Сымитировать непредвиденную ошибку после реальной записи в транзакции БД."""
        await self._session.flush()
        msg = "Искусственный сбой перед commit"
        raise RuntimeError(msg)

    headers, original = batch_seed
    items = [{"uid": item["uid"], "expected_version": 1} for item in original]
    if method == "PATCH":
        for item in items:
            item["changes"] = {"money_sum": 999}
    monkeypatch.setattr(TransactionUnitOfWork, "commit", fail_before_commit)
    path = "/transactions/batch" if method == "PATCH" else "/transactions/batch-delete"
    response = await client.request(method, path, headers=headers, json={"items": items})
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    actual = (await client.get("/transactions", headers=headers)).json()["content"]
    assert sorted(actual, key=lambda item: item["uid"]) == sorted(original, key=lambda item: item["uid"])


@pytest.mark.db
async def test_batch_error_priority_and_foreign_isolation(
    client: AsyncClient,
    batch_seed: tuple[dict[str, str], list[dict[str, Any]]],
    make_token: TokenFactory,
) -> None:
    """Чужая строка не раскрывает версию и имеет приоритет перед конфликтом собственной."""
    headers, original = batch_seed
    stranger_headers = {"Authorization": f"Bearer {make_token()}"}
    items = [{"uid": row["uid"], "expected_version": 999, "changes": {"money_sum": 500}} for row in original]
    response = await client.patch("/transactions/batch", headers=stranger_headers, json={"items": items})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert {error["code"] for error in response.json()["errors"]} == {"FM-404000"}
    items[1]["uid"] = str(uuid4())
    response = await client.patch("/transactions/batch", headers=headers, json={"items": items})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    deleted = await client.post(
        "/transactions/batch-delete",
        headers=stranger_headers,
        json={"items": [{"uid": row["uid"], "expected_version": 1} for row in original]},
    )
    assert deleted.status_code == status.HTTP_200_OK
    assert [result["status"] for result in deleted.json()["results"]] == [404, 404]
    actual = (await client.get("/transactions", headers=headers)).json()["content"]
    assert sorted(actual, key=lambda item: item["uid"]) == sorted(original, key=lambda item: item["uid"])
