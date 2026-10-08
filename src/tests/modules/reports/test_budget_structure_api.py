"""`GET /budget-structure`: агрегация фактов на настоящем Postgres и валидация параметров."""

from collections.abc import Iterator
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category.infrastructure.orm import Category
from apps.modules.reports.api.deps import get_today
from apps.modules.transaction.infrastructure.orm import Transaction
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory
from apps.web.main import app
from tests.conftest import TokenFactory

TODAY = date(2026, 3, 15)
OUTCOME = apps_types.TransactionType.OUTCOME
INCOME = apps_types.TransactionType.INCOME


@pytest.fixture(autouse=True)
def fixed_today() -> Iterator[None]:
    """Текущая дата эндпоинта — `TODAY`."""
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


@pytest.fixture
def owner() -> UUID:
    """Пользователь из токена."""
    return uuid4()


@pytest.fixture
def headers(make_token: TokenFactory, owner: UUID) -> dict[str, str]:
    """Заголовок авторизации владельца."""
    return {"Authorization": f"Bearer {make_token(owner)}"}


async def _add_category(
    user_uid: UUID,
    name: str,
    category_type: apps_types.TransactionType = OUTCOME,
    money_plan: int = 1000,
) -> UUID:
    category = Category(
        uid=uuid4(),
        user_uid=user_uid,
        name=name,
        money_plan=money_plan,
        category_type=category_type,
        description=None,
    )
    async with async_session_factory() as session:
        session.add(category)
        await session.commit()
    return category.uid


async def _add_transactions(user_uid: UUID, category_uid: UUID, *items: tuple[datetime, int]) -> None:
    async with async_session_factory() as session:
        session.add_all(
            Transaction(
                uid=uuid4(),
                user_uid=user_uid,
                transaction_date=transaction_date,
                category_uid=category_uid,
                money_sum=money_sum,
                transaction_type=OUTCOME,
                description=None,
            )
            for transaction_date, money_sum in items
        )
        await session.commit()


def _local(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    """Дата транзакции — локальное время без пояса, как в `transaction_date`."""
    return datetime(year, month, day, hour, minute, second)  # noqa: DTZ001


def _facts(months: list[dict[str, Any]]) -> list[int | None]:
    assert [month["month"] for month in months] == list(range(1, 13))
    return [month["fact"] for month in months]


async def _get(client: AsyncClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    response = await client.get("/budget-structure", headers=headers, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.db
async def test_month_and_year_boundaries(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Последняя секунда месяца/года относится к нему, полночь первого числа — к следующему."""
    food = await _add_category(owner, "еда")
    await _add_transactions(
        owner,
        food,
        (_local(2025, 12, 31, 23, 59, 59), 1),
        (_local(2026, 1, 1, 0, 0), 10),
        (_local(2026, 1, 31, 23, 59, 59), 100),
        (_local(2026, 2, 1, 0, 0), 1000),
        (_local(2026, 12, 31, 23, 59, 59), 5),  # будущий месяц — не показывается
        (_local(2027, 1, 1, 0, 0), 7),
    )

    body = await _get(client, headers, year=2026)

    facts = [110, 1000, 0] + [None] * 9
    [row] = body["rows"]
    assert (body["year"], body["category_type"]) == (2026, "outcome")
    assert row["category"] == {"uid": str(food), "name": "еда"}
    assert (row["money_plan"], row["average"], _facts(row["months"])) == (1000, 555, facts)
    total = body["total"]
    assert (total["money_plan"], total["average"], _facts(total["months"])) == (1000, 555, facts)

    past = await _get(client, headers, year=2025)
    assert _facts(past["rows"][0]["months"]) == [0] * 11 + [1]


@pytest.mark.db
async def test_defaults_are_current_year_and_outcome(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Без параметров — текущий год и расходы."""
    food = await _add_category(owner, "еда")
    await _add_category(owner, "зарплата", category_type=INCOME)
    await _add_transactions(owner, food, (_local(2026, 3, 1), 5))

    body = await _get(client, headers)

    assert (body["year"], body["category_type"]) == (TODAY.year, "outcome")
    assert [row["category"]["name"] for row in body["rows"]] == ["еда"]
    assert _facts(body["rows"][0]["months"]) == [0, 0, 5] + [None] * 9


@pytest.mark.db
async def test_only_own_categories_of_requested_type_sorted_by_name(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Все свои статьи типа (и без транзакций), по названию; чужие статьи и статьи другого типа не попадают."""
    stranger = uuid4()
    salary = await _add_category(owner, "зарплата", category_type=INCOME)
    await _add_category(owner, "бонус", category_type=INCOME)
    await _add_category(owner, "аренда", category_type=OUTCOME)
    foreign = await _add_category(stranger, "аванс", category_type=INCOME)
    await _add_transactions(owner, salary, (_local(2026, 1, 10), 100))
    await _add_transactions(stranger, foreign, (_local(2026, 1, 10), 999))

    body = await _get(client, headers, year=2026, category_type="income")

    assert body["category_type"] == "income"
    assert [row["category"]["name"] for row in body["rows"]] == ["бонус", "зарплата"]
    assert _facts(body["rows"][0]["months"]) == [0, 0, 0] + [None] * 9
    assert _facts(body["rows"][1]["months"]) == [100, 0, 0] + [None] * 9
    assert _facts(body["total"]["months"]) == [100, 0, 0] + [None] * 9
    assert body["total"]["money_plan"] == 2 * 1000


@pytest.mark.db
async def test_foreign_transactions_in_own_category_are_not_counted(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Учитываются только транзакции пользователя из токена, даже если статья его."""
    food = await _add_category(owner, "еда")
    await _add_transactions(uuid4(), food, (_local(2026, 1, 10), 999))

    body = await _get(client, headers, year=2026)

    assert _facts(body["rows"][0]["months"]) == [0, 0, 0] + [None] * 9


@pytest.mark.db
async def test_sum_above_int32_does_not_overflow(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Сумма за месяц больше 2^31 − 1 считается в BIGINT."""
    food = await _add_category(owner, "еда")
    await _add_transactions(owner, food, *[(_local(2026, 1, day), 1_000_000_000) for day in (1, 2, 3)])

    body = await _get(client, headers, year=2026)

    expected = [3_000_000_000, 0, 0] + [None] * 9
    assert _facts(body["rows"][0]["months"]) == expected
    assert _facts(body["total"]["months"]) == expected


@pytest.mark.db
async def test_no_categories(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Статей нет — пустые строки и нулевой итог по наступившим месяцам."""
    body = await _get(client, headers, year=2026)

    assert body["rows"] == []
    assert _facts(body["total"]["months"]) == [0, 0, 0] + [None] * 9
    assert body["total"]["money_plan"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"year": 1999},
        {"year": 2100},
        {"year": "abc"},
        {"category_type": "other"},
    ],
)
async def test_invalid_params_are_rejected(
    client: AsyncClient, headers: dict[str, str], params: dict[str, Any]
) -> None:
    """Год вне 2000–2099 и неизвестный тип статей — 422 `FM-422000`."""
    response = await client.get("/budget-structure", headers=headers, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"] == "FM-422000"
