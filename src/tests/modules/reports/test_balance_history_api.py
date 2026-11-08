"""Контракт дневного остатка на настоящем PostgreSQL."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category.infrastructure.orm import Category
from apps.modules.reports.api import deps
from apps.modules.starting_balance.infrastructure.orm import StartingBalance
from apps.modules.transaction.infrastructure.orm import Transaction
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Зафиксировать момент, когда в Москве уже следующий день и год."""

    def now() -> datetime:
        """Вернуть 1 января 2026 года, 00:30 по Москве."""
        return datetime(2025, 12, 31, 21, 30, tzinfo=UTC)

    monkeypatch.setattr(deps, "aware_now", now)


@pytest.fixture
def owner() -> UUID:
    """Создать идентификатор владельца бюджета."""
    return uuid4()


@pytest.fixture
def headers(make_token: TokenFactory, owner: UUID) -> dict[str, str]:
    """Авторизовать владельца бюджета."""
    return {"Authorization": f"Bearer {make_token(owner)}"}


async def seed_balance(owner: UUID, day: str = "2025-12-29", amount: int = 100) -> None:
    """Сохранить стартовый остаток для проверки отчёта."""
    async with async_session_factory() as session:
        session.add(StartingBalance(user_uid=owner, balance_date=date.fromisoformat(day), amount=amount))
        await session.commit()


async def seed_transaction(owner: UUID, moment: str, amount: int, kind: str = "income") -> UUID:
    """Сохранить операцию с собственной статьёй и вернуть её UID."""
    category_uid, transaction_uid = uuid4(), uuid4()
    async with async_session_factory() as session:
        session.add(
            Category(
                uid=category_uid,
                user_uid=owner,
                name=str(category_uid),
                category_type=apps_types.TransactionType(kind),
                money_plan=None,
                description=None,
            )
        )
        await session.flush()
        session.add(
            Transaction(
                uid=transaction_uid,
                user_uid=owner,
                category_uid=category_uid,
                transaction_date=datetime.fromisoformat(moment),
                money_sum=amount,
                transaction_type=apps_types.TransactionType(kind),
                description=None,
            )
        )
        await session.commit()
    return transaction_uid


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"date_from": "2025-12-01"},
        {"date_to": "2025-12-01"},
        {"date_from": "2025-02-29", "date_to": "2025-12-01"},
        {"date_from": "2025-12-02", "date_to": "2025-12-01"},
        {"date_from": "2026-01-01", "date_to": "2026-01-02"},
        {"date_from": "2024-12-31", "date_to": "2026-01-01"},
        {"date_from": "1999-12-31", "date_to": "2000-01-01"},
        {"date_from": "2100-01-01", "date_to": "2100-01-01"},
        {"date_from": "2025-1-01", "date_to": "2025-01-02"},
        {"date_from": "2025-12-01T00:00:00", "date_to": "2025-12-01"},
        {"date_from": "1764547200", "date_to": "2025-12-01"},
    ],
)
async def test_invalid_range_before_database(
    client: AsyncClient, headers: dict[str, str], params: dict[str, str]
) -> None:
    """Неверные параметры дают 422 до любого обращения к БД и проверки остатка."""
    response = await client.get("/balance-history", headers=headers, params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"] == "FM-422000"


async def test_requires_authentication(client: AsyncClient) -> None:
    """Отчёт не доступен без access-токена."""
    response = await client.get("/balance-history", params={"date_from": "2025-12-01", "date_to": "2025-12-01"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.db
async def test_missing_own_balance(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Чужой стартовый остаток не заменяет отсутствующий собственный."""
    await seed_balance(uuid4())
    response = await client.get(
        "/balance-history", headers=headers, params={"date_from": "2025-12-01", "date_to": "2025-12-01"}
    )
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert response.json()["code"] == "FM-409203"


@pytest.mark.db
async def test_daily_history(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID) -> None:
    """Неизвестные дни, стартовый день, перенос, долг и московская граница вычисляются точно."""
    await seed_balance(owner)
    for moment, amount, kind in [
        ("2025-12-28T12:00:00", 900, "income"),
        ("2025-12-29T23:59:59", 800, "income"),
        ("2025-12-30T00:00:00", 150, "outcome"),
        ("2026-01-01T00:30:00", 25, "income"),
        ("2026-01-01T00:30:01", 1000, "income"),
        ("2026-01-02T00:00:00", 1000, "income"),
    ]:
        await seed_transaction(owner, moment, amount, kind)
    await seed_transaction(uuid4(), "2025-12-30T12:00:00", 999)
    response = await client.get(
        "/balance-history", headers=headers, params={"date_from": "2025-12-28", "date_to": "2026-01-01"}
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {
        "date_from": "2025-12-28",
        "date_to": "2026-01-01",
        "currency": "RUB",
        "unit": "rubles",
        "timezone": "Europe/Moscow",
        "points": [
            {"date": "2025-12-28", "balance": None},
            {"date": "2025-12-29", "balance": 100},
            {"date": "2025-12-30", "balance": -50},
            {"date": "2025-12-31", "balance": -50},
            {"date": "2026-01-01", "balance": -25},
        ],
    }
    cropped = await client.get(
        "/balance-history", headers=headers, params={"date_from": "2025-12-31", "date_to": "2025-12-31"}
    )
    assert cropped.status_code == status.HTTP_200_OK
    assert cropped.json()["points"] == [{"date": "2025-12-31", "balance": -50}]


@pytest.mark.db
@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2025-01-01", "2026-01-01", 366),
        ("2024-02-29", "2024-02-29", 1),
    ],
)
async def test_fully_unknown_range(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID, start: str, end: str, count: int
) -> None:
    """Допустимый диапазон до стартовой даты содержит все дни с null, включая високосный день."""
    await seed_balance(owner, "2026-01-02")
    response = await client.get("/balance-history", headers=headers, params={"date_from": start, "date_to": end})
    assert response.status_code == status.HTTP_200_OK, response.text
    points = response.json()["points"]
    assert len(points) == count
    assert points[0]["date"] == start
    assert points[-1]["date"] == end
    assert all(point["balance"] is None for point in points)
    assert len({point["date"] for point in points}) == count


@pytest.mark.db
async def test_mutations_and_large_totals(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Повторный запрос пересчитывает прошлые изменения, не переполняя int32."""
    await seed_balance(owner, amount=0)
    params = {"date_from": "2025-12-31", "date_to": "2026-01-01"}
    response = await client.get("/balance-history", headers=headers, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert [p["balance"] for p in response.json()["points"]] == [0, 0]
    for second in range(3):
        await seed_transaction(owner, f"2025-12-30T12:00:0{second}", 1_000_000_000)
    uid = await seed_transaction(owner, "2025-12-31T12:00:00", 10, "outcome")
    response = await client.get("/balance-history", headers=headers, params=params)
    assert [p["balance"] for p in response.json()["points"]] == [2_999_999_990, 2_999_999_990]
    async with async_session_factory() as session:
        await session.execute(update(Transaction).where(Transaction.uid == uid).values(money_sum=20))
        await session.commit()
    response = await client.get("/balance-history", headers=headers, params=params)
    assert [p["balance"] for p in response.json()["points"]] == [2_999_999_980, 2_999_999_980]
    async with async_session_factory() as session:
        await session.execute(delete(Transaction).where(Transaction.uid == uid))
        await session.commit()
    response = await client.get("/balance-history", headers=headers, params=params)
    assert [p["balance"] for p in response.json()["points"]] == [3_000_000_000, 3_000_000_000]
