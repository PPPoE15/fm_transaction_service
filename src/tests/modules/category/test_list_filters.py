"""Фильтры плана статей на PostgreSQL, включая нулевую границу и чужие данные."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category import CategoryORM
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory


@pytest.mark.db
@pytest.mark.parametrize(
    ("filters", "expected_names"),
    [
        ({}, ["А без плана", "Б ноль", "В сто"]),
        ({"below_money_sum": 0}, ["Б ноль"]),
        ({"above_money_sum": 0}, ["Б ноль", "В сто"]),
        ({"below_money_sum": 0, "above_money_sum": 0}, ["Б ноль"]),
        ({"below_money_sum": 100}, ["Б ноль", "В сто"]),
        ({"above_money_sum": 100}, ["В сто"]),
    ],
)
async def test_plan_filters_and_pagination(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    filters: dict[str, int],
    expected_names: list[str],
) -> None:
    """Границы включительны, NULL исключается при фильтре, total и страницы учитывают владельца."""
    owner, stranger = uuid4(), uuid4()
    async with async_session_factory() as session:
        for user_uid in (owner, stranger):
            session.add_all(
                CategoryORM(uid=uuid4(), user_uid=user_uid, name=name, money_plan=plan, category_type="outcome")
                for name, plan in [("А без плана", None), ("Б ноль", 0), ("В сто", 100)]
            )
        await session.commit()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    for skip in range(len(expected_names) + 1):
        response = await client.get("/categories", headers=headers, params={**filters, "limit": 1, "skip": skip})
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["total"] == len(expected_names)
        assert [item["name"] for item in response.json()["content"]] == expected_names[skip : skip + 1]
