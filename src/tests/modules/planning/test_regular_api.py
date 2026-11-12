"""Проверки API регулярных операций на PostgreSQL."""

import asyncio
from collections.abc import Callable
from datetime import date
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.planning.api.deps import get_clock, regular_commands
from apps.modules.planning.application import regular
from apps.web.main import app
from tests.conftest import TokenFactory
from tests.modules.planning.test_api import category
from tests.modules.planning.test_confirmation import confirm, payload

pytestmark = pytest.mark.db


@pytest.fixture
def move_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[date], None]:
    """Управлять датой запроса независимо от календаря машины."""
    current = date(2028, 1, 31)

    def clock() -> date:
        """Вернуть зафиксированный день."""
        return current

    def clock_dependency() -> Callable[[], date]:
        """Подменить зависимость часов."""
        return clock

    def move(today: date) -> None:
        """Перевести часы на заданный день."""
        nonlocal current
        current = today

    overrides: dict[Callable[[], Callable[[], date]], Callable[[], Callable[[], date]]] = app.dependency_overrides
    monkeypatch.setitem(overrides, get_clock, clock_dependency)
    return move


async def test_materializes_calendar_and_filters(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, move_clock: Callable[[date], None]
) -> None:
    """Создание сохраняет календарь, а фильтр скрывает регулярные планы из всех счётчиков."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    created = await client.post(
        "/regular-operations",
        headers=headers,
        json={
            "category_uid": cat,
            "money_sum": 100,
            "first_date": "2028-01-31",
            "end_date": "2028-03-31",
            "frequency": "monthly",
        },
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    plans = (await client.get("/planned-operations", headers=headers)).json()
    assert [plan["planned_date"] for plan in plans["content"]] == ["2028-01-31", "2028-02-29", "2028-03-31"]
    assert all(plan["recurrence"]["operation_uid"] == created.json()["uid"] for plan in plans["content"])
    filtered = (await client.get("/planned-operations?include_regular=false", headers=headers)).json()
    assert filtered["total"] == filtered["due_count"] == 0
    page = (await client.get("/regular-operations", headers=headers)).json()
    assert page["today"] == "2028-01-31"
    assert "today" not in page["content"][0]


async def test_recalculation_keeps_exceptions_and_deleted_dates(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, move_clock: Callable[[date], None]
) -> None:
    """Просроченные, выполненные, изменённые и удалённые позиции переживают пересчёт."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    created = await client.post(
        "/regular-operations",
        headers=headers,
        json={"category_uid": cat, "money_sum": 100, "first_date": "2028-01-31", "frequency": "monthly"},
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    url = f"/regular-operations/{created.json()['uid']}"
    plans = (await client.get("/planned-operations", headers=headers)).json()["content"]
    first, edited, removed, completed = plans[:4]
    updated = await client.patch(
        f"/planned-operations/{edited['uid']}",
        headers=headers,
        json={"expected_version": 1, "planned_date": "2028-03-01"},
    )
    assert updated.status_code == HTTPStatus.OK, updated.text
    assert updated.json()["recurrence"]["is_exception"]
    assert (
        await client.delete(f"/planned-operations/{removed['uid']}", headers=headers, params={"expected_version": 1})
    ).status_code == HTTPStatus.NO_CONTENT
    result = await confirm(client, headers, completed["uid"], payload(cat))
    assert result["plan"]["money_sum"] == completed["money_sum"]
    assert result["plan"]["recurrence"] == completed["recurrence"]
    move_clock(date(2028, 2, 1))
    changed = await client.patch(
        url,
        headers=headers,
        json={
            "expected_version": 1,
            "money_sum": 200,
            "end_date": "2028-05-31",
        },
    )
    assert changed.status_code == HTTPStatus.OK, changed.text
    plans = (await client.get("/planned-operations?include_completed=true", headers=headers)).json()["content"]
    assert [(p["planned_date"], p["money_sum"]) for p in plans] == [
        ("2028-01-31", 100),
        ("2028-03-01", 100),
        ("2028-04-30", 100),
        ("2028-05-31", 200),
    ]
    assert plans[0]["uid"] == first["uid"]
    assert plans[1]["uid"] == edited["uid"]
    assert plans[2]["uid"] == completed["uid"]
    deleted = await client.delete(url, headers=headers, params={"expected_version": 2})
    assert deleted.status_code == HTTPStatus.NO_CONTENT, deleted.text
    assert (await client.get(url, headers=headers)).status_code == HTTPStatus.NOT_FOUND
    remaining = (await client.get("/planned-operations?include_completed=true", headers=headers)).json()["content"]
    assert [p["uid"] for p in remaining] == [completed["uid"]]
    assert remaining[0]["recurrence"]["operation_status"] == "deleted"
    assert (
        await client.delete(f"/planned-operations/{completed['uid']}", headers=headers, params={"expected_version": 2})
    ).status_code == HTTPStatus.NO_CONTENT
    assert (
        await client.get(f"/transactions/{result['transaction']['uid']}", headers=headers)
    ).status_code == HTTPStatus.OK


@pytest.mark.parametrize("completed", [False, True])
async def test_conversion_reuses_pending_only_and_isolates_sources(
    client: AsyncClient,
    db_engine: AsyncEngine,
    make_token: TokenFactory,
    move_clock: Callable[[date], None],
    completed: bool,
) -> None:
    """Преобразование сохраняет источник и не раскрывает регулярную операцию другому владельцу."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    other = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    response = await client.post(
        "/planned-operations",
        headers=headers,
        json={"category_uid": cat, "money_sum": 100, "planned_date": "2028-01-31"},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    plan = response.json()
    source = f"/planned-operations/{plan['uid']}"
    if completed:
        await confirm(client, headers, plan["uid"], payload(cat))
    original = (await client.get(source, headers=headers)).json()
    values = {
        "category_uid": cat,
        "money_sum": 100,
        "first_date": "2028-02-29",
        "end_date": "2028-02-29",
        "frequency": "monthly",
        "expected_version": original["version"],
    }
    assert (await client.post(f"{source}/recurrence", headers=other, json=values)).status_code == HTTPStatus.NOT_FOUND
    converted = await client.post(f"{source}/recurrence", headers=headers, json=values)
    assert converted.status_code == HTTPStatus.CREATED, converted.text
    data = converted.json()
    assert data["source_plan_uid"] == original["uid"]
    assert data["source_disposition"] == ("unchanged" if completed else "attached")
    assert (data["first_plan"]["uid"] == original["uid"]) is not completed
    if completed:
        assert (await client.get(source, headers=headers)).json() == original
    regular_transaction_url = f"/regular-operations/{data['operation']['uid']}"
    assert (await client.get(regular_transaction_url, headers=other)).status_code == HTTPStatus.NOT_FOUND
    page = await client.get("/regular-operations", headers=headers, params={"source_plan_uid": original["uid"]})
    assert page.json()["total"] == 1
    values["expected_version"] = original["version"] if completed else data["first_plan"]["version"]
    repeated = await client.post(f"{source}/recurrence", headers=headers, json=values)
    assert repeated.status_code == HTTPStatus.CONFLICT
    assert repeated.json()["code"] == ("FM-409407" if completed else "FM-409406")
    assert (await client.get("/planned-operations", headers=headers)).json()["total"] == 1


async def test_parallel_generation_catches_up_and_quota_rolls_back(
    client: AsyncClient,
    db_engine: AsyncEngine,
    make_token: TokenFactory,
    move_clock: Callable[[date], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Повторные проходы безопасны, а лимит откатывает регулярную операцию и платежи целиком."""
    initial = date(2028, 1, 31)
    move_clock(initial)
    owner = uuid4()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    cat = await category(client, headers)
    values = {"category_uid": cat, "money_sum": 100, "first_date": "2028-01-31", "frequency": "monthly"}
    with monkeypatch.context() as limited:
        limited.setattr(regular, "MAX_PLANS", 1)
        rejected = await client.post("/regular-operations", headers=headers, json=values)
    assert rejected.status_code == HTTPStatus.CONFLICT, rejected.text
    assert rejected.json()["code"] == "FM-409404"
    assert (await client.get("/regular-operations", headers=headers)).json()["total"] == 0
    assert (await client.get("/planned-operations", headers=headers)).json()["total"] == 0
    created = await client.post("/regular-operations", headers=headers, json=values)
    assert created.status_code == HTTPStatus.CREATED, created.text
    uid = UUID(created.json()["uid"])
    later = date(2029, 3, 1)
    results = await asyncio.gather(*(regular_commands(date.today).generate(owner, uid, later) for _worker in range(2)))
    assert sorted(results) == [0, 13]
    move_clock(later)
    plans = (await client.get("/planned-operations", headers=headers)).json()
    assert "2029-02-28" in [p["planned_date"] for p in plans["content"]]
    assert plans["content"][-1]["planned_date"] == "2030-02-28"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0


async def test_update_catches_up_old_schedule_and_extends_ended_rule(
    client: AsyncClient,
    db_engine: AsyncEngine,
    make_token: TokenFactory,
    move_clock: Callable[[date], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Изменение атомарно достраивает старые даты и возобновляет завершённую регулярную операцию."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    created = await client.post(
        "/regular-operations",
        headers=headers,
        json={
            "category_uid": cat,
            "money_sum": 100,
            "first_date": "2028-01-31",
            "end_date": "2029-02-28",
            "frequency": "monthly",
        },
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    url = f"/regular-operations/{created.json()['uid']}"
    move_clock(date(2029, 3, 1))
    original = (await client.get(url, headers=headers)).json()
    assert original["status"] == "ended"
    changes = {"expected_version": 1, "money_sum": 200, "end_date": "2029-03-31"}
    with monkeypatch.context() as limited:
        limited.setattr(regular, "MAX_PLANS", 14)
        failed = await client.patch(url, headers=headers, json=changes)
    assert failed.status_code == HTTPStatus.CONFLICT, failed.text
    assert (await client.get(url, headers=headers)).json() == original
    before = (await client.get("/planned-operations", headers=headers)).json()["content"]
    assert before[-1]["planned_date"] == "2029-01-31"
    extended = await client.patch(url, headers=headers, json=changes)
    assert extended.status_code == HTTPStatus.OK, extended.text
    assert extended.json()["status"] == "active"
    after = (await client.get("/planned-operations", headers=headers)).json()["content"]
    assert [(plan["planned_date"], plan["money_sum"]) for plan in after[-2:]] == [
        ("2029-02-28", 100),
        ("2029-03-31", 200),
    ]


async def test_regular_transaction_without_payments_protects_category(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, move_clock: Callable[[date], None]
) -> None:
    """Активная регулярная операция защищает тип категории даже за горизонтом генерации."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    created = await client.post(
        "/regular-operations",
        headers=headers,
        json={"category_uid": cat, "money_sum": 100, "first_date": "2029-02-01", "frequency": "monthly"},
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    assert (await client.get("/planned-operations", headers=headers)).json()["total"] == 0
    category_url = f"/categories/{cat}"
    conflict = await client.patch(category_url, headers=headers, json={"category_type": "income"})
    assert conflict.status_code == HTTPStatus.CONFLICT, conflict.text
    assert conflict.json()["code"] == "FM-409405"
    regular_transaction_url = f"/regular-operations/{created.json()['uid']}"
    assert (
        await client.delete(regular_transaction_url, headers=headers, params={"expected_version": 1})
    ).status_code == HTTPStatus.NO_CONTENT
    assert (
        await client.patch(category_url, headers=headers, json={"category_type": "income"})
    ).status_code == HTTPStatus.OK


async def test_regular_transaction_page_accepts_skip_above_database_integer_range(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, move_clock: Callable[[date], None]
) -> None:
    """Допустимое смещение за пределами bigint даёт пустую страницу."""
    move_clock(date(2028, 1, 31))
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    created = await client.post(
        "/regular-operations",
        headers=headers,
        json={"category_uid": cat, "money_sum": 100, "first_date": "2028-01-31", "frequency": "yearly"},
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    response = await client.get("/regular-operations", headers=headers, params={"skip": 2**63})
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["total"] == 1
    assert response.json()["content"] == []
    assert response.json()["next_skip"] is None
