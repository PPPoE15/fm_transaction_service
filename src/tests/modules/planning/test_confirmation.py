"""Атомарное подтверждение и чтение связанного факта через HTTP на PostgreSQL."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from apps.modules.category import Category, CategoryRepo
from apps.modules.planning.api import deps as planning_deps
from apps.modules.planning.application import confirmation
from apps.modules.planning.domain.model import Plan
from apps.modules.planning.infrastructure.repo import PlanRepo
from apps.modules.transaction.application.commands import create as transaction_create
from tests.conftest import TokenFactory
from tests.modules.planning.test_api import URL, category, create, today

pytestmark = pytest.mark.db


def payload(category_uid: str, version: int = 1) -> dict[str, Any]:
    """Сформировать полный набор фактических полей, отличный от значений плана."""
    return {
        "expected_version": version,
        "transaction_date": "2025-10-01T00:00:00",
        "money_sum": 900,
        "category_uid": category_uid,
        "description": "Фактическое значение",
    }


async def confirm(
    client: AsyncClient, headers: dict[str, str], plan_uid: str, values: dict[str, Any]
) -> dict[str, Any]:
    """Подтвердить план и проверить успешный ответ."""
    result = await client.post(f"{URL}/{plan_uid}/confirm", headers=headers, json=values)
    assert result.status_code == HTTPStatus.OK, result.text
    return dict(result.json())


async def test_confirmation_preserves_original_and_fact_is_readable(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Факт получает новые значения; исходный план сохраняется и повтор не создаёт дубля."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    original_cat = await category(client, headers)
    fact_cat = await category(client, headers)
    plan = await create(client, headers, original_cat)
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE planned_transactions SET planned_date=planned_date-1 WHERE uid=:uid"), {"uid": plan["uid"]}
        )
    plan = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    result = await confirm(client, headers, plan["uid"], payload(fact_cat))
    completed, fact = result["plan"], result["transaction"]
    for field in ("planned_date", "money_sum", "category", "description", "transaction_type"):
        assert completed[field] == plan[field]
    assert completed["status"] == "completed"
    assert completed["version"] == plan["version"] + 1
    assert completed["transaction_uid"] == fact["uid"]
    assert completed["transaction_state"] == "available"
    assert completed["completed_at"].endswith("Z")
    for field in ("transaction_date", "money_sum", "description"):
        assert fact[field] == payload(fact_cat)[field]
    assert fact["category"]["uid"] == fact_cat
    assert fact["transaction_type"] == "outcome"
    assert (await client.get(f"/transactions/{fact['uid']}", headers=headers)).json() == fact
    for version in (plan["version"], completed["version"]):
        repeated = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(fact_cat, version))
        assert repeated.status_code == HTTPStatus.CONFLICT
        assert repeated.json()["code"] == "FM-409401"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 1
    assert (await client.get(URL, headers=headers)).json()["total"] == 0


async def test_concurrent_confirmation_creates_one_fact(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Два параллельных подтверждения создают один факт и один переход состояния."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    responses = await asyncio.gather(
        *(client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat)) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [HTTPStatus.OK, HTTPStatus.CONFLICT]
    assert next(r for r in responses if r.status_code == HTTPStatus.CONFLICT).json()["code"] == "FM-409401"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 1


async def test_confirmation_ownership_category_and_version(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Доступ проверяется до версии; неверные категории и версии не создают факт."""
    owner = {"Authorization": f"Bearer {make_token()}"}
    stranger = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, owner)
    foreign_cat = await category(client, stranger)
    income = await category(client, owner, "income")
    plan = await create(client, owner, cat)
    for uid in (plan["uid"], str(uuid4())):
        result = await client.post(f"{URL}/{uid}/confirm", headers=stranger, json=payload(foreign_cat))
        assert result.status_code == HTTPStatus.NOT_FOUND
        assert result.json()["code"] == "FM-404000"
    for cat_uid, code in [(foreign_cat, "FM-400201"), (str(uuid4()), "FM-400201"), (income, "FM-400202")]:
        response = await client.post(f"{URL}/{plan['uid']}/confirm", headers=owner, json=payload(cat_uid))
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json()["code"] == code
        assert response.json()["validation"][0]["field"] == "category_uid"
    changed = await client.patch(f"{URL}/{plan['uid']}", headers=owner, json={"expected_version": 1, "money_sum": 10})
    assert changed.status_code == HTTPStatus.OK
    stale = await client.post(f"{URL}/{plan['uid']}/confirm", headers=owner, json=payload(cat))
    assert stale.json()["code"] == "FM-409402"
    assert (await client.get("/transactions", headers=owner)).json()["total"] == 0
    fact = (await confirm(client, owner, plan["uid"], payload(cat, changed.json()["version"])))["transaction"]
    for uid in (fact["uid"], str(uuid4())):
        assert (await client.get(f"/transactions/{uid}", headers=stranger)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("money_sum", 0),
        ("money_sum", -1),
        ("money_sum", True),
        ("money_sum", 1.5),
        ("transaction_date", "2025-02-30T00:00:00"),
        ("transaction_date", "2025-01-01T00:00:00Z"),
        ("expected_version", 0),
        ("expected_version", True),
        ("description", "x" * 501),
        ("transaction_type", "income"),
        ("user_uid", str(uuid4())),
    ],
)
async def test_confirmation_input_validation(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, field: str, value: object
) -> None:
    """Неверные суммы, даты, версии и лишние поля отвергаются без записи."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    values = payload(cat)
    values[field] = value
    response = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=values)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0
    assert (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()["status"] == "pending"


async def test_fact_changes_and_deletion_do_not_rewrite_plan(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory
) -> None:
    """Редактирование факта и переименование категории не меняют снимок; удаление оставляет completed."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    values = payload(cat)
    values["transaction_date"] = (date.fromisoformat(today()) + timedelta(days=5)).isoformat() + "T00:00:00"
    values.pop("description")
    result = await confirm(client, headers, plan["uid"], values)
    fact = result["transaction"]
    assert fact["description"] is None
    await client.patch(f"/categories/{cat}", headers=headers, json={"name": "Новое имя"})
    changed = await client.patch(
        f"/transactions/{fact['uid']}", headers=headers, json={"money_sum": 500, "expected_version": 1}
    )
    assert changed.status_code == HTTPStatus.OK
    assert (await client.get(f"/transactions/{fact['uid']}", headers=headers)).json() == changed.json()
    current = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    assert current == result["plan"]
    deleted = await client.delete(f"/transactions/{fact['uid']}", headers=headers)
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert (await client.get(f"/transactions/{fact['uid']}", headers=headers)).status_code == HTTPStatus.NOT_FOUND
    current = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    assert current["transaction_state"] == "deleted"
    assert current["transaction_uid"] is None
    assert current["version"] == result["plan"]["version"] + 1
    assert current["status"] == "completed"
    repeated = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat, current["version"]))
    assert repeated.json()["code"] == "FM-409401"


@pytest.mark.parametrize(("kind", "expected_balance"), [("outcome", 100), ("income", 1900)])
async def test_balance_changes_once_and_plan_deletion_preserves_fact(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, kind: str, expected_balance: int
) -> None:
    """Подтверждение учитывается один раз; удаление плана сохраняет факт и финансовый результат."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers, kind)
    plan = await create(client, headers, cat)
    starting = await client.post(
        "/starting-balance", headers=headers, json={"amount": 1000, "balance_date": "2025-09-30"}
    )
    assert starting.status_code == HTTPStatus.CREATED, starting.text
    params = {"date_from": "2025-10-01", "date_to": "2025-10-01"}
    before = (await client.get("/balance-history", headers=headers, params=params)).json()
    assert before["points"] == [{"date": "2025-10-01", "balance": 1000}]
    result = await confirm(client, headers, plan["uid"], payload(cat))
    await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat))
    after = (await client.get("/balance-history", headers=headers, params=params)).json()
    assert after["points"] == [{"date": "2025-10-01", "balance": expected_balance}]
    deleted = await client.delete(
        f"{URL}/{plan['uid']}", headers=headers, params={"expected_version": result["plan"]["version"]}
    )
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert (await client.get("/balance-history", headers=headers, params=params)).json() == after
    fact_uid = result["transaction"]["uid"]
    assert (await client.get(f"/transactions/{fact_uid}", headers=headers)).status_code == HTTPStatus.OK
    assert (
        await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat))
    ).status_code == HTTPStatus.NOT_FOUND


async def test_rollback_after_both_writes(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сбой после INSERT факта и UPDATE плана откатывает оба изменения; явный повтор успешен."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    original_update = PlanRepo.update

    async def fail_after_write(repo: PlanRepo, changed: Plan) -> None:
        """Записать обе стороны и имитировать ошибку до commit."""
        await original_update(repo, changed)
        msg = "Проверка отката после сохранения"
        raise RuntimeError(msg)

    with monkeypatch.context() as patch:
        patch.setattr(PlanRepo, "update", fail_after_write)
        response = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat))
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 0
    assert (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json() == plan
    await confirm(client, headers, plan["uid"], payload(cat))
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 1


async def test_lost_commit_response_does_not_create_duplicate(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Потеря ответа после реального commit даёт 503; чтение и повтор не создают второй факт."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    original_commit = AsyncSession.commit
    calls = 0

    async def lost_commit_response(session: AsyncSession) -> None:
        """Выполнить реальный commit и потерять подтверждение от сервера БД."""
        nonlocal calls
        calls += 1
        await original_commit(session)
        msg = "Ответ COMMIT потерян"
        raise OSError(msg)

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", lost_commit_response)
        response = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat))
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["code"] == "FM-503401"
    assert calls == 1
    current = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    assert current["status"] == "completed"
    retry = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat, current["version"]))
    assert retry.json()["code"] == "FM-409401"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 1


async def test_quota_shared_with_regular_creation(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Обычное создание и подтверждение конкурируют за одну квоту без лишнего факта."""
    monkeypatch.setattr(confirmation, "MAX_TRANSACTIONS_PER_USER", 1)
    monkeypatch.setattr(transaction_create, "MAX_TRANSACTIONS_PER_USER", 1)
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    regular = payload(cat)
    regular.pop("expected_version")
    regular["transaction_type"] = "outcome"
    responses = await asyncio.gather(
        client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat)),
        client.post("/transactions", headers=headers, json=regular),
    )
    assert sum(r.status_code == HTTPStatus.CONFLICT for r in responses) == 1
    assert next(r for r in responses if r.status_code == HTTPStatus.CONFLICT).json()["code"] == "FM-409202"
    assert (await client.get("/transactions", headers=headers)).json()["total"] == 1
    current = (await client.get(f"{URL}/{plan['uid']}", headers=headers)).json()
    if responses[0].status_code == HTTPStatus.CONFLICT:
        assert current == plan
        repeated = await client.post(f"{URL}/{plan['uid']}/confirm", headers=headers, json=payload(cat))
        assert repeated.json()["code"] == "FM-409202"
    else:
        assert responses[0].status_code == HTTPStatus.OK
        assert current["status"] == "completed"


@pytest.mark.parametrize("operation", ["patch", "delete"])
async def test_confirmation_races_with_plan_mutations(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, operation: str
) -> None:
    """Одна версия не позволяет одновременно подтвердить и изменить либо удалить план."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    url = f"{URL}/{plan['uid']}"
    mutation = (
        client.patch(url, headers=headers, json={"expected_version": 1, "money_sum": 10})
        if operation == "patch"
        else client.delete(url, headers=headers, params={"expected_version": 1})
    )
    confirmed, changed = await asyncio.gather(
        client.post(f"{url}/confirm", headers=headers, json=payload(cat)), mutation
    )
    total = (await client.get("/transactions", headers=headers)).json()["total"]
    if confirmed.status_code == HTTPStatus.OK:
        assert changed.status_code == HTTPStatus.CONFLICT
        assert total == 1
    else:
        assert total == 0
        if operation == "patch":
            assert changed.status_code == HTTPStatus.OK
            assert confirmed.json()["code"] == "FM-409402"
        else:
            assert changed.status_code == HTTPStatus.NO_CONTENT
            assert confirmed.status_code == HTTPStatus.NOT_FOUND


async def test_confirmation_clock_is_read_once_after_category_locks(
    client: AsyncClient, db_engine: AsyncEngine, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Один момент после блокировок определяет completed_at и московское сегодня на границе суток."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    cat = await category(client, headers)
    plan = await create(client, headers, cat)
    original = CategoryRepo.get_by_uid_for_key_share
    locked = False
    calls = 0
    moment = datetime(2026, 11, 9, 22, tzinfo=UTC)

    async def tracked_lock(repo: CategoryRepo, uid: UUID) -> Category | None:
        """Зафиксировать завершение реального чтения с блокировкой."""
        nonlocal locked
        result = await original(repo, uid)
        locked = True
        return result

    def fixed_clock() -> datetime:
        """Проверить момент вызова часов и вернуть границу московских суток."""
        nonlocal calls
        assert locked
        calls += 1
        return moment

    with monkeypatch.context() as patch:
        patch.setattr(CategoryRepo, "get_by_uid_for_key_share", tracked_lock)
        patch.setattr(planning_deps, "utc_now", fixed_clock)
        result = await confirm(client, headers, plan["uid"], payload(cat))
    assert calls == 1
    assert result["plan"]["today"] == "2026-11-10"
    assert result["plan"]["completed_at"] == "2026-11-09T22:00:00Z"
