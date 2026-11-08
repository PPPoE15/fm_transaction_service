"""Пересчёт отчётов после исправления и удаления операций через публичный API."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.reports.api import deps
from tests.conftest import TokenFactory


async def assert_reports(
    client: AsyncClient, headers: dict[str, str], expected: dict[str, list[int]], balances: list[int]
) -> None:
    """Проверить факты по статьям и месяцам, дневные остатки и неизменные планы."""
    budget = await client.get("/budget-structure", headers=headers, params={"year": 2026, "category_type": "outcome"})
    assert budget.status_code == status.HTTP_200_OK, budget.text
    rows = budget.json()["rows"]
    assert {row["category"]["uid"]: [month["fact"] for month in row["months"][:2]] for row in rows} == expected
    assert {row["money_plan"] for row in rows} == {1000}
    history = await client.get(
        "/balance-history", headers=headers, params={"date_from": "2026-01-02", "date_to": "2026-02-02"}
    )
    assert history.status_code == status.HTTP_200_OK, history.text
    points = history.json()["points"]
    assert [points[0]["balance"], points[-1]["balance"]] == balances


@pytest.mark.db
@pytest.mark.parametrize("mode", ["single", "batch"])
async def test_edit_and_delete_recalculate_reports(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Сумма, месяц и статья меняют факты, удаление убирает их; стартовый остаток и планы сохраняются."""

    def now() -> datetime:
        """Зафиксировать дату после всех проверяемых операций."""
        return datetime(2026, 3, 15, 12, tzinfo=UTC)

    monkeypatch.setattr(deps, "aware_now", now)
    headers = {"Authorization": f"Bearer {make_token()}"}
    category_ids = []
    for name in ("Еда", "Транспорт"):
        response = await client.post(
            "/categories", headers=headers, json={"name": name, "category_type": "outcome", "money_plan": 1000}
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        category_ids.append(response.json()["uid"])
    balance = await client.post(
        "/starting-balance", headers=headers, json={"amount": 10000, "balance_date": "2025-12-31"}
    )
    assert balance.status_code == status.HTTP_201_CREATED, balance.text
    before_balance = (await client.get("/starting-balance", headers=headers)).json()
    operations = []
    for category_uid, amount in zip(category_ids, (100, 200), strict=True):
        response = await client.post(
            "/transactions",
            headers=headers,
            json={
                "category_uid": category_uid,
                "money_sum": amount,
                "transaction_date": "2026-01-02T12:00:00",
                "transaction_type": "outcome",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        operations.append(response.json())
    first, second = operations
    a, b = category_ids
    await assert_reports(client, headers, {a: [100, 0], b: [200, 0]}, [9700, 9700])
    changes: dict[str, Any] = {"money_sum": 300, "category_uid": b}
    if mode == "single":
        changed = await client.patch(
            f"/transactions/{first['uid']}",
            headers=headers,
            json={**changes, "transaction_date": "2026-02-02T12:00:00", "expected_version": 1},
        )
    else:
        changed = await client.patch(
            "/transactions/batch",
            headers=headers,
            json={
                "items": [{"uid": first["uid"], "expected_version": 1, "changes": {**changes, "date": "2026-02-02"}}]
            },
        )
    assert changed.status_code == status.HTTP_200_OK, changed.text
    await assert_reports(client, headers, {a: [0, 0], b: [200, 300]}, [9800, 9500])
    if mode == "single":
        deleted = await client.delete(f"/transactions/{first['uid']}", headers=headers, params={"expected_version": 2})
        assert deleted.status_code == status.HTTP_204_NO_CONTENT
    else:
        deleted = await client.post(
            "/transactions/batch-delete",
            headers=headers,
            json={
                "items": [{"uid": first["uid"], "expected_version": 2}, {"uid": second["uid"], "expected_version": 99}]
            },
        )
        assert deleted.status_code == status.HTTP_200_OK, deleted.text
        assert [item["status"] for item in deleted.json()["results"]] == [204, 409]
    await assert_reports(client, headers, {a: [0, 0], b: [200, 0]}, [9800, 9800])
    assert (await client.get("/starting-balance", headers=headers)).json() == before_balance
