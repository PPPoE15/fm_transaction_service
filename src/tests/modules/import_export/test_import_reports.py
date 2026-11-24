"""Операции импорта участвуют в обычных отчётах без отдельной ветки расчёта."""

from datetime import date, datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.reports.api.deps import get_now, get_today
from apps.web.main import app
from tests.conftest import TokenFactory
from tests.modules.import_export.test_import_api import add_category

EXPECTED_INCOME = 3_000_000_000
EXPECTED_COUNT = 6


@pytest.mark.db
async def test_import_financial_totals(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
) -> None:
    """Целые суммы свыше int32, доходы, расходы и чужие операции корректно учитываются в отчётах."""

    def today() -> date:
        """Зафиксировать месяц отчёта независимо от часов тестовой машины."""
        return date(2026, 10, 27)

    def now() -> datetime:
        """Зафиксировать московский момент расчёта истории."""
        return datetime(2026, 10, 27, tzinfo=ZoneInfo("Europe/Moscow"))

    headers = {"Authorization": f"Bearer {make_token()}"}
    stranger = {"Authorization": f"Bearer {make_token()}"}
    app.dependency_overrides[get_today] = today
    app.dependency_overrides[get_now] = now
    try:
        response = await client.post(
            "/starting-balance", headers=headers, json={"amount": 10, "balance_date": "2026-09-30"}
        )
        assert response.status_code == HTTPStatus.CREATED, response.text
        for auth, kind, amount in [(headers, "income", 1000000000), (headers, "outcome", 1), (stranger, "income", 999)]:
            await add_category(client, auth, "Еда", kind)
            content = ("Дата;Сумма;Категория;Описание\n" + f"01.10.2026;{amount};Еда;\n" * 3).encode()
            imported = await client.post(
                f"/import-export/imports/{kind}?format=csv",
                headers=auth,
                files={"file": ("a.csv", content, "text/csv")},
            )
            assert imported.status_code == HTTPStatus.CREATED, imported.text
        report = await client.get("/budget-structure?year=2026&category_type=income", headers=headers)
        assert report.status_code == HTTPStatus.OK, report.text
        assert report.json()["total"]["months"][9]["fact"] == EXPECTED_INCOME
        history = await client.get("/balance-history?date_from=2026-10-01&date_to=2026-10-02", headers=headers)
        assert history.status_code == HTTPStatus.OK, history.text
        assert history.json()["points"] == [
            {"date": "2026-10-01", "balance": 3000000007},
            {"date": "2026-10-02", "balance": 3000000007},
        ]
        listed = await client.get("/transactions", headers=headers)
        assert listed.json()["total"] == EXPECTED_COUNT
    finally:
        app.dependency_overrides.pop(get_today, None)
        app.dependency_overrides.pop(get_now, None)


@pytest.mark.db
async def test_import_before_starting_balance_restores_history(
    db_engine: AsyncEngine, client: AsyncClient, make_token: TokenFactory
) -> None:
    """Импорт старых доходов и расходов восстанавливает историю, сохраняя стартовую сумму."""

    def now() -> datetime:
        """Вернуть момент после импортируемых операций и стартовой даты."""
        return datetime(2026, 10, 27, tzinfo=ZoneInfo("Europe/Moscow"))

    headers = {"Authorization": f"Bearer {make_token()}"}
    app.dependency_overrides[get_now] = now
    try:
        starting = await client.post(
            "/starting-balance", headers=headers, json={"amount": 50000, "balance_date": "2026-10-24"}
        )
        assert starting.status_code == HTTPStatus.CREATED, starting.text
        params = {"date_from": "2026-10-01", "date_to": "2026-10-02"}
        before = await client.get("/balance-history", headers=headers, params=params)
        assert before.status_code == HTTPStatus.OK, before.text
        assert before.json()["history_start_date"] == "2026-10-24"
        assert [point["balance"] for point in before.json()["points"]] == [None, None]
        for kind, rows in [
            ("income", "01.10.2026;2000;Импорт;\n24.10.2026;13000;Импорт;\n"),
            ("outcome", "02.10.2026;3000;Импорт;\n"),
        ]:
            await add_category(client, headers, "Импорт", kind)
            response = await client.post(
                f"/import-export/imports/{kind}?format=csv",
                headers=headers,
                files={"file": ("history.csv", ("Дата;Сумма;Категория;Описание\n" + rows).encode(), "text/csv")},
            )
            assert response.status_code == HTTPStatus.CREATED, response.text
        after = await client.get("/balance-history", headers=headers, params=params)
        assert after.status_code == HTTPStatus.OK, after.text
        assert after.json()["history_start_date"] == "2026-10-01"
        assert [point["balance"] for point in after.json()["points"]] == [40000, 37000]
        anchor = await client.get(
            "/balance-history", headers=headers, params={"date_from": "2026-10-24", "date_to": "2026-10-27"}
        )
        assert anchor.status_code == HTTPStatus.OK, anchor.text
        assert [point["balance"] for point in anchor.json()["points"]] == [50000, 50000, 50000, 50000]
        stored = await client.get("/starting-balance", headers=headers)
        assert stored.status_code == HTTPStatus.OK, stored.text
        assert stored.json() == starting.json()
    finally:
        app.dependency_overrides.pop(get_now, None)
