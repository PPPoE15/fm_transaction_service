"""Одиночные изменения и версии транзакций по FM-99."""

import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from tests.conftest import TokenFactory


@pytest.mark.db
async def test_partial_update_and_versioned_delete(
    db_engine: AsyncEngine, client: AsyncClient, make_token: TokenFactory
) -> None:
    """PATCH очищает комментарий, сохраняет остальные поля и защищает повторную запись версией."""
    headers = {"Authorization": f"Bearer {make_token(uuid4())}"}
    category = await client.post("/categories", headers=headers, json={"name": "Обеды", "category_type": "outcome"})
    assert category.status_code == status.HTTP_201_CREATED, category.text
    created = await client.post(
        "/transactions",
        headers=headers,
        json={
            "transaction_date": "2026-10-01T12:34:56.123456",
            "category_uid": category.json()["uid"],
            "money_sum": 100,
            "transaction_type": "outcome",
            "description": "Обед",
        },
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    original = created.json()
    assert original["version"] == 1
    url = f"/transactions/{original['uid']}"
    changed = await client.patch(url, headers=headers, json={"description": None, "expected_version": 1})
    assert changed.status_code == status.HTTP_200_OK, changed.text
    assert changed.json() == {**original, "description": None, "version": 2}
    repeated = await client.patch(url, headers=headers, json={"money_sum": 300, "expected_version": 1})
    assert repeated.status_code == status.HTTP_409_CONFLICT, repeated.text
    assert repeated.json()["code"] == "FM-409204"
    stale_delete = await client.delete(url, headers=headers, params={"expected_version": 1})
    assert stale_delete.status_code == status.HTTP_409_CONFLICT
    deleted = await client.delete(url, headers=headers, params={"expected_version": 2})
    assert deleted.status_code == status.HTTP_204_NO_CONTENT, deleted.text
    assert deleted.content == b""
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"expected_version": 1},
        {"money_sum": None},
        {"money_sum": True},
        {"money_sum": 0},
        {"money_sum": 1_000_000_001},
        {"money_sum": "100"},
        {"transaction_date": "2026-02-30T12:00:00"},
        {"transaction_date": "2026-01-01T12:00:00Z"},
        {"category_uid": None},
        {"description": "x" * 501},
        {"description": "x\x00"},
        {"description": None, "expected_version": None},
        {"description": None, "unexpected": 1},
    ],
)
async def test_invalid_patch_is_rejected_before_database(
    client: AsyncClient, make_token: TokenFactory, body: dict[str, object]
) -> None:
    """Невалидные поля и пустое изменение отклоняются до обращения к базе."""
    response = await client.patch(
        f"/transactions/{uuid4()}", headers={"Authorization": f"Bearer {make_token()}"}, json=body
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"] == "FM-422000"


@pytest.mark.db
async def test_concurrent_updates_have_one_winner(
    db_engine: AsyncEngine, client: AsyncClient, make_token: TokenFactory
) -> None:
    """Две записи с одной версией дают одного победителя и не теряют его данные."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    category = await client.post("/categories", headers=headers, json={"name": "Гонка", "category_type": "outcome"})
    created = await client.post(
        "/transactions",
        headers=headers,
        json={
            "transaction_date": "2026-10-01T12:00:00",
            "category_uid": category.json()["uid"],
            "money_sum": 100,
            "transaction_type": "outcome",
        },
    )
    url = f"/transactions/{created.json()['uid']}"
    responses = await asyncio.gather(
        *(
            client.patch(url, headers=headers, json={"money_sum": amount, "expected_version": 1})
            for amount in (200, 300)
        )
    )
    assert sorted(response.status_code for response in responses) == [status.HTTP_200_OK, status.HTTP_409_CONFLICT]
    winner = next(response.json() for response in responses if response.status_code == status.HTTP_200_OK)
    expected_version = 2
    assert winner["version"] == expected_version
    assert (await client.get("/transactions", headers=headers)).json()["content"] == [winner]
    same = await client.patch(url, headers=headers, json={"money_sum": winner["money_sum"]})
    assert same.status_code == status.HTTP_200_OK, same.text
    assert same.json() == {**winner, "version": 3}
