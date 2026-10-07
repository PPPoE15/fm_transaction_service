"""
Изоляция данных пользователей на всех эндпоинтах — на настоящем Postgres.

Пользователь A заводит статью и транзакцию через API, пользователь B пытается их увидеть, изменить
или удалить. Чужой объект для B выглядит как несуществующий (404), данные A не меняются.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from tests.conftest import TokenFactory

pytestmark = pytest.mark.db

TRANSACTION_DATE = "2026-10-01T12:00:00"


@dataclass
class User:
    """Пользователь API с заголовком авторизации."""

    uid: UUID
    headers: dict[str, str]


@dataclass
class Seed:
    """Данные пользователя A, заведённые через API."""

    category_uid: str
    transaction_uid: str


@pytest.fixture
def user_a(make_token: TokenFactory) -> User:
    """Владелец данных."""
    uid = uuid4()
    return User(uid=uid, headers={"Authorization": f"Bearer {make_token(uid)}"})


@pytest.fixture
def user_b(make_token: TokenFactory) -> User:
    """Посторонний пользователь."""
    uid = uuid4()
    return User(uid=uid, headers={"Authorization": f"Bearer {make_token(uid)}"})


async def _create_category(client: AsyncClient, user: User, name: str) -> str:
    response = await client.post(
        "/category",
        headers=user.headers,
        json={"name": name, "money_plan": 1000, "category_type": "outcome", "description": None},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    [category] = [item for item in (await _categories(client, user)) if item["name"] == name]
    return str(category["uid"])


async def _create_transaction(client: AsyncClient, user: User, category_uid: str, description: str) -> str:
    response = await client.post(
        "/transactions",
        headers=user.headers,
        json={
            "transaction_date": TRANSACTION_DATE,
            "category": category_uid,
            "money_sum": 100,
            "transaction_type": "outcome",
            "description": description,
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    [transaction] = [item for item in response.json()["content"] if item["description"] == description]
    return str(transaction["uid"])


async def _categories(client: AsyncClient, user: User) -> list[dict[str, Any]]:
    response = await client.get("/categories", headers=user.headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["content"]


async def _transactions(client: AsyncClient, user: User) -> list[dict[str, Any]]:
    response = await client.get("/transactions", headers=user.headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["content"]


def _transaction_update(category_uid: str) -> dict[str, Any]:
    return {
        "transaction_date": TRANSACTION_DATE,
        "category": category_uid,
        "money_sum": 999,
        "transaction_type": "outcome",
        "description": "Изменено",
    }


CATEGORY_UPDATE = {"name": "Изменено", "money_plan": 1, "category_type": "income", "description": "Изменено"}


@pytest.fixture
async def seed(db_engine: AsyncEngine, client: AsyncClient, user_a: User) -> Seed:
    """Статья и транзакция пользователя A."""
    category_uid = await _create_category(client, user_a, "Еда")
    transaction_uid = await _create_transaction(client, user_a, category_uid, "Обед")
    return Seed(category_uid=category_uid, transaction_uid=transaction_uid)


def _assert_not_found(response: Any) -> None:  # noqa: ANN401
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json()["code"] == "FM-404000"


async def test_list_transactions_shows_only_own(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """GET /transactions: B не видит транзакций A."""
    assert [item["uid"] for item in await _transactions(client, user_a)] == [seed.transaction_uid]
    response = await client.get("/transactions", headers=user_b.headers)

    assert response.json() == {"total": 0, "content": []}


async def test_list_categories_shows_only_own(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """GET /categories: B не видит статей A."""
    assert [item["uid"] for item in await _categories(client, user_a)] == [seed.category_uid]
    response = await client.get("/categories", headers=user_b.headers)

    assert response.json() == {"total": 0, "content": []}


async def test_update_foreign_transaction(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """PATCH /transactions: чужая транзакция — 404, у A ничего не меняется."""
    before = await _transactions(client, user_a)
    b_category = await _create_category(client, user_b, "Своя статья B")

    response = await client.patch(
        "/transactions",
        params={"transaction_uid": seed.transaction_uid},
        headers=user_b.headers,
        json=_transaction_update(b_category),
    )

    _assert_not_found(response)
    assert await _transactions(client, user_a) == before


async def test_delete_foreign_transaction(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """DELETE /transactions: чужая транзакция — 404 и не удаляется."""
    response = await client.delete(
        "/transactions", params={"transaction_uid": seed.transaction_uid}, headers=user_b.headers
    )

    _assert_not_found(response)
    assert [item["uid"] for item in await _transactions(client, user_a)] == [seed.transaction_uid]


async def test_create_transaction_in_foreign_category(
    client: AsyncClient, seed: Seed, user_a: User, user_b: User
) -> None:
    """POST /transactions: в чужую статью — 404, транзакция не создаётся ни у кого."""
    response = await client.post(
        "/transactions",
        headers=user_b.headers,
        json={**_transaction_update(seed.category_uid), "description": "Чужая статья"},
    )

    _assert_not_found(response)
    assert await _transactions(client, user_b) == []
    assert [item["uid"] for item in await _transactions(client, user_a)] == [seed.transaction_uid]


async def test_move_own_transaction_to_foreign_category(
    client: AsyncClient, seed: Seed, user_a: User, user_b: User
) -> None:
    """PATCH /transactions: свою транзакцию нельзя перенести в чужую статью."""
    b_category = await _create_category(client, user_b, "Своя статья B")
    b_transaction = await _create_transaction(client, user_b, b_category, "Своя транзакция B")
    before = await _transactions(client, user_b)

    response = await client.patch(
        "/transactions",
        params={"transaction_uid": b_transaction},
        headers=user_b.headers,
        json=_transaction_update(seed.category_uid),
    )

    _assert_not_found(response)
    assert await _transactions(client, user_b) == before


async def test_update_foreign_category(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """PATCH /category: чужая статья — 404, у A ничего не меняется."""
    before = await _categories(client, user_a)

    response = await client.patch(
        "/category", params={"category_uid": seed.category_uid}, headers=user_b.headers, json=CATEGORY_UPDATE
    )

    _assert_not_found(response)
    assert await _categories(client, user_a) == before


async def test_delete_foreign_category(client: AsyncClient, seed: Seed, user_a: User, user_b: User) -> None:
    """DELETE /category: чужая статья — 404, статья и её транзакции остаются."""
    response = await client.delete("/category", params={"category_uid": seed.category_uid}, headers=user_b.headers)

    _assert_not_found(response)
    assert [item["uid"] for item in await _categories(client, user_a)] == [seed.category_uid]
    assert [item["uid"] for item in await _transactions(client, user_a)] == [seed.transaction_uid]


async def test_create_category_is_visible_only_to_creator(
    client: AsyncClient, seed: Seed, user_a: User, user_b: User
) -> None:
    """POST /category: статья B видна только B."""
    b_category = await _create_category(client, user_b, "Своя статья B")

    assert [item["uid"] for item in await _categories(client, user_b)] == [b_category]
    assert [item["uid"] for item in await _categories(client, user_a)] == [seed.category_uid]


async def test_owner_can_update_and_delete_own_data(client: AsyncClient, seed: Seed, user_a: User) -> None:
    """Владелец меняет и удаляет свои транзакцию и статью — проверки не мешают законным операциям."""
    response = await client.patch(
        "/transactions",
        params={"transaction_uid": seed.transaction_uid},
        headers=user_a.headers,
        json=_transaction_update(seed.category_uid),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    [transaction] = response.json()["content"]
    assert (transaction["money_sum"], transaction["description"]) == (999, "Изменено")

    response = await client.patch(
        "/category", params={"category_uid": seed.category_uid}, headers=user_a.headers, json=CATEGORY_UPDATE
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    [category] = await _categories(client, user_a)
    assert (category["name"], category["money_plan"]) == ("Изменено", 1)

    response = await client.delete(
        "/transactions", params={"transaction_uid": seed.transaction_uid}, headers=user_a.headers
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    response = await client.delete("/category", params={"category_uid": seed.category_uid}, headers=user_a.headers)
    assert response.status_code == status.HTTP_200_OK, response.text

    assert await _transactions(client, user_a) == []
    assert await _categories(client, user_a) == []
