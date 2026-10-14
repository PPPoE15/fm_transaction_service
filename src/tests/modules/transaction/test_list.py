from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category import CategoryORM
from apps.modules.transaction import TransactionORM
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory

OWN_OUTCOMES = 7
INCOME_NUMBER = 8
FOREIGN_NUMBER = 9
TIED_COUNT = 3


@pytest.mark.parametrize(
    ("field", "value"),
    [("skip", "-1"), ("skip", "100001"), ("limit", "0"), ("limit", "501"), ("sort", "uid")]
    + [
        (field, value)
        for field in ("after", "before")
        for value in (
            "1999-12-31T23:59:59",
            "2100-01-01T00:00:00",
            "2026-02-30T00:00:00",
            "2026-01-01",
            "2026-01-01 00:00:00",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00+03:00",
            "2026-01-01T00:00:00.1234567",
            "1767225600",
        )
    ],
)
async def test_invalid_list_params(client: AsyncClient, make_token: TokenFactory, field: str, value: str) -> None:
    """Проверить отклонение неверных параметров списка."""
    response = await client.get(
        "/transactions", params={field: value}, headers={"Authorization": f"Bearer {make_token()}"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text


async def test_reversed_dates(client: AsyncClient, make_token: TokenFactory) -> None:
    """Проверить код ошибки обратного диапазона."""
    response = await client.get(
        "/transactions",
        params={"after": "2026-02-01T00:00:00", "before": "2026-01-01T00:00:00"},
        headers={"Authorization": f"Bearer {make_token()}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "FM-422001"


@pytest.mark.db
@pytest.mark.parametrize("sort", [None, "-transaction_date", "transaction_date"])
async def test_list_order_and_filters(
    client: AsyncClient, make_token: TokenFactory, db_engine: AsyncEngine, sort: str | None
) -> None:
    """Проверить порядок, пагинацию, фильтры и изоляцию пользователей."""
    owner, stranger, category_uid = uuid4(), uuid4(), uuid4()
    async with async_session_factory() as session:
        session.add(CategoryORM(uid=category_uid, user_uid=owner, name="Еда", category_type="outcome"))
        await session.flush()
        for number in reversed(range(1, 10)):
            session.add(
                TransactionORM(
                    uid=UUID(int=number, version=4),
                    user_uid=stranger if number == FOREIGN_NUMBER else owner,
                    category_uid=category_uid,
                    transaction_date=datetime(2026, 1, min(number, 5), tzinfo=UTC).replace(tzinfo=None),
                    money_sum=100,
                    transaction_type="income" if number == INCOME_NUMBER else "outcome",
                    description=None,
                )
            )
        await session.commit()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    params = {"transaction_type": "outcome", "limit": "5"}
    if sort:
        params["sort"] = sort
    response = await client.get("/transactions", headers=headers, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    expected = [1, 2, 3, 4, 5] if sort == "transaction_date" else [5, 6, 7, 4, 3]
    assert data["total"] == OWN_OUTCOMES
    assert [item["uid"] for item in data["content"]] == [str(UUID(int=n, version=4)) for n in expected]
    assert all(item["category"] == {"uid": str(category_uid), "name": "Еда"} for item in data["content"])
    page = await client.get("/transactions", headers=headers, params={**params, "skip": "1", "limit": "1"})
    assert page.json()["total"] == OWN_OUTCOMES
    assert page.json()["content"] == data["content"][1:2]
    bounded = await client.get(
        "/transactions",
        headers=headers,
        params={
            **params,
            "after": "2026-01-05T00:00:00",
            "before": "2026-01-05T00:00:00.000000",
        },
    )
    assert bounded.json()["total"] == TIED_COUNT
    assert [item["uid"] for item in bounded.json()["content"]] == [str(UUID(int=n, version=4)) for n in [5, 6, 7]]


@pytest.mark.db
@pytest.mark.parametrize("date", ["2000-01-01T00:00:00", "2099-12-31T23:59:59.999999"])
async def test_valid_boundaries(
    client: AsyncClient, make_token: TokenFactory, db_engine: AsyncEngine, date: str
) -> None:
    """Проверить допустимые границы параметров."""
    response = await client.get(
        "/transactions",
        headers={"Authorization": f"Bearer {make_token()}"},
        params={
            "skip": "100000",
            "limit": "500",
            "after": date,
            "before": date,
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {"total": 0, "content": []}
