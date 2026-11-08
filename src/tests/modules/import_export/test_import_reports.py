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
