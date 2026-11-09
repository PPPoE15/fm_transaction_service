"""Публичные сценарии планирования на настоящем PostgreSQL."""

import asyncio
from datetime import datetime
from http import HTTPStatus
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.planning.application import commands
from apps.modules.planning.infrastructure.orm import PlannedOperation
from tests.conftest import TokenFactory

pytestmark = pytest.mark.db
SECOND_VERSION = 2
DUE_PLANS = 2
TOTAL_PLANS = 3
URL = "/planned-operations"


def today() -> str:
    """Получить московскую дату для независимых HTTP-примеров."""
    return datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()


async def category(client: AsyncClient, headers: dict[str, str], kind: str = "outcome") -> str:
    """Создать собственную категорию через существующий API."""
    response = await client.post("/categories", headers=headers, json={"name": str(uuid4()), "category_type": kind})
    assert response.status_code == HTTPStatus.CREATED, response.text
    return str(response.json()["uid"])


async def create(client: AsyncClient, headers: dict[str, str], category_uid: str) -> dict[str, Any]:
    """Создать план без ключей повторов и вернуть проверенный ответ."""
    response = await client.post(
        URL, headers=headers, json={"planned_date": today(), "money_sum": 11500, "category_uid": category_uid}
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return dict(response.json())


async def test_crud_and_no_fact(client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory) -> None:
    """CRUD сохраняет версии и отдельность плана от фактических операций."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    assert plan["status"] == "pending"
    assert plan["version"] == 1
    assert plan["transaction_uid"] is None
    assert plan["transaction_type"] == "outcome"
    assert plan["today"] == today()
    assert plan["timezone"] == "Europe/Moscow"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0
    response = await client.patch(
        f"{URL}/{plan['uid']}",
        headers=headers,
        json={"expected_version": 1, "money_sum": 12000, "description": "Правка"},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["version"] == SECOND_VERSION
    stale = await client.patch(f"{URL}/{plan['uid']}", headers=headers, json={"expected_version": 1, "money_sum": 1})
    assert stale.status_code == HTTPStatus.CONFLICT
    assert stale.json()["code"] == "FM-409402"
    assert (
        await client.delete(f"{URL}/{plan['uid']}?expected_version=2", headers=headers)
    ).status_code == HTTPStatus.NO_CONTENT
    assert (await client.get(f"{URL}/{plan['uid']}", headers=headers)).status_code == HTTPStatus.NOT_FOUND
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("money_sum", 0),
        ("money_sum", -1),
        ("money_sum", 1.5),
        ("money_sum", "5"),
        ("planned_date", "2026-02-30"),
        ("planned_date", "2000-01-01"),
        ("planned_date", "2099-01-01T00:00:00"),
        ("transaction_type", "income"),
        ("description", "x" * 501),
    ],
)
async def test_validation(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, field: str, value: object
) -> None:
    """Создание отвергает недопустимые суммы, даты, комментарии и лишние поля."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    payload = {"planned_date": today(), "money_sum": 10, "category_uid": cat, field: value}
    assert (await client.post(URL, headers=headers, json=payload)).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_isolation_and_category_type(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Чужие планы невидимы, чужие категории недоступны, тип существующего плана неизменяем."""
    first = {"Authorization": f"Bearer {make_token()}"}
    second = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, first)
    plan = await create(client, first, cat)
    for method in ("get", "patch", "delete"):
        kwargs: dict[str, Any] = {"headers": second}
        if method == "patch":
            kwargs["json"] = {"expected_version": 1, "money_sum": 5}
        if method == "delete":
            kwargs["params"] = {"expected_version": 1}
        assert (await client.request(method, f"{URL}/{plan['uid']}", **kwargs)).status_code == HTTPStatus.NOT_FOUND
    assert (await client.get(URL, headers=second)).json()["total"] == 0
    invalid = await client.post(
        URL, headers=second, json={"planned_date": today(), "money_sum": 10, "category_uid": cat}
    )
    assert invalid.status_code == HTTPStatus.BAD_REQUEST
    assert invalid.json()["code"] == "FM-400201"
    income = await category(client, first, "income")
    changed = await client.patch(
        f"{URL}/{plan['uid']}", headers=first, json={"expected_version": 1, "category_uid": income}
    )
    assert changed.status_code == HTTPStatus.BAD_REQUEST
    assert changed.json()["code"] == "FM-400202"
    guarded = await client.patch(f"/categories/{cat}", headers=first, json={"category_type": "income"})
    assert guarded.status_code == HTTPStatus.CONFLICT
    assert guarded.json()["code"] == "FM-409405"


async def test_due_sort_filter_and_paging(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Список показывает ближайшие планы, считает наступившие и сохраняет total пустой страницы."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    old = await create(client, headers, cat)
    current = await create(client, headers, cat)
    future = await create(client, headers, await category(client, headers, "income"))
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE planned_operations SET planned_date = planned_date - 1 WHERE uid=:uid"), {"uid": old["uid"]}
        )
        await conn.execute(
            text("UPDATE planned_operations SET planned_date = planned_date + 5 WHERE uid=:uid"), {"uid": future["uid"]}
        )
    result = (await client.get(URL, headers=headers)).json()
    assert [row["uid"] for row in result["content"]] == [old["uid"], current["uid"], future["uid"]]
    assert result["due_count"] == DUE_PLANS
    first = (await client.get(URL, headers=headers, params={"limit": 1})).json()
    assert first["next_skip"] == 1
    empty = (await client.get(URL, headers=headers, params={"skip": 3})).json()
    assert empty["total"] == TOTAL_PLANS
    assert empty["content"] == []
    assert empty["next_skip"] is None
    income = (await client.get(URL, headers=headers, params={"transaction_type": "income"})).json()
    assert income["total"] == 1
    assert income["due_count"] == 0
    invalid = await client.patch(f"{URL}/{old['uid']}", headers=headers, json={"expected_version": 1, "money_sum": 5})
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    moved = await client.patch(
        f"{URL}/{old['uid']}", headers=headers, json={"expected_version": 1, "planned_date": today()}
    )
    assert moved.status_code == HTTPStatus.OK


async def test_parallel_updates_and_duplicate_creation(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """С одинаковой версией сохраняется одна правка; одинаковые POST создают отдельные планы."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    second = await create(client, headers, cat)
    assert second["uid"] != plan["uid"]
    results = await asyncio.gather(
        *(
            client.patch(f"{URL}/{plan['uid']}", headers=headers, json={"expected_version": 1, "money_sum": amount})
            for amount in (10, 20)
        )
    )
    assert sorted(r.status_code for r in results) == [200, 409]


@pytest.mark.parametrize("delete_fact", [False, True])
async def test_completed_snapshot_and_independent_deletion(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, delete_fact: bool
) -> None:
    """Выполненный план хранит исходные поля; удаление любой стороны не удаляет другую."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    fact_uid = uuid4()
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO transactions (uid, user_uid, category_uid, transaction_type, money_sum, transaction_date) "
                "SELECT :fact, user_uid, category_uid, transaction_type, 99, CURRENT_TIMESTAMP "
                "FROM planned_operations WHERE uid=:plan"
            ),
            {"fact": fact_uid, "plan": plan["uid"]},
        )
        await conn.execute(
            text(
                "UPDATE planned_operations SET status='completed', completed_at=CURRENT_TIMESTAMP, "
                "category_name_snapshot='Исходная категория', transaction_uid=:fact, version=2 WHERE uid=:plan"
            ),
            {"fact": fact_uid, "plan": plan["uid"]},
        )
    hidden = (await client.get(URL, headers=headers)).json()
    assert hidden["total"] == 0
    assert hidden["due_count"] == 0
    shown = (await client.get(URL, headers=headers, params={"include_completed": True})).json()
    assert shown["total"] == 1
    assert shown["content"][0]["transaction_state"] == "available"
    await client.patch(f"/categories/{cat}", headers=headers, json={"name": "Новое имя"})
    completed = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    assert completed["category"]["name"] == "Исходная категория"
    assert completed["money_sum"] == plan["money_sum"]
    rejected = await client.patch(
        f"{URL}/{plan['uid']}", headers=headers, json={"expected_version": 1, "money_sum": 10}
    )
    assert rejected.json()["code"] == "FM-409401"
    if delete_fact:
        async with db_engine.begin() as conn:
            await conn.execute(text("DELETE FROM transactions WHERE uid=:uid"), {"uid": fact_uid})
        remaining = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
        assert remaining["transaction_uid"] is None
        assert remaining["transaction_state"] == "deleted"
        assert remaining["version"] == completed["version"] + 1
        assert remaining["status"] == "completed"
        assert remaining["money_sum"] == plan["money_sum"]
        stale = await client.delete(f"{URL}/{plan['uid']}?expected_version=2", headers=headers)
        assert stale.json()["code"] == "FM-409402"
    else:
        deleted = await client.delete(f"{URL}/{plan['uid']}?expected_version=2", headers=headers)
        assert deleted.status_code == HTTPStatus.NO_CONTENT
        assert (await client.get("/transactions", headers=headers)).json()["total"] == 1


async def test_concurrent_quota(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Последнее свободное место занимает только один из параллельных запросов."""
    monkeypatch.setattr(commands, "MAX_PLANS", 1)
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    payload = {"planned_date": today(), "money_sum": 10, "category_uid": cat}
    responses = await asyncio.gather(*(client.post(URL, headers=headers, json=payload) for _ in range(2)))
    assert sorted(r.status_code for r in responses) == [HTTPStatus.CREATED, HTTPStatus.CONFLICT]
    assert next(r for r in responses if r.status_code == HTTPStatus.CONFLICT).json()["code"] == "FM-409404"


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"skip": -1}, {"skip": 100001}])
async def test_pagination_bounds(client: AsyncClient, make_token: TokenFactory, params: dict[str, int]) -> None:
    """Границы пагинации отклоняются до обращения к хранилищу."""
    result = await client.get(URL, headers={"Authorization": f"Bearer {make_token()}"}, params=params)
    assert result.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "values",
    [{"money_sum": 0}, {"status": "unknown"}, {"version": 0}, {"status": "completed"}, {"category_uid": uuid4()}],
)
async def test_database_constraints(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, values: dict[str, object]
) -> None:
    """База отвергает недопустимые значения и связи независимо от API."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    plan = await create(client, headers, await category(client, headers))
    with pytest.raises(IntegrityError):
        async with db_engine.begin() as conn:
            await conn.execute(update(PlannedOperation).where(PlannedOperation.uid == plan["uid"]).values(**values))
