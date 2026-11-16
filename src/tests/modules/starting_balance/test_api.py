"""`GET` / `POST /starting-balance` на настоящем Postgres: ответы, валидация, изоляция и гонка двух `POST`."""

import asyncio
from collections.abc import Iterator
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.starting_balance.api.deps import get_today
from apps.modules.starting_balance.application.exceptions import StartingBalanceAlreadyExistsError
from apps.modules.starting_balance.domain import StartingBalance
from apps.modules.starting_balance.infrastructure.orm import StartingBalance as StartingBalanceORM
from apps.modules.starting_balance.infrastructure.repo import Repo
from apps.shared.db.session import async_session_factory
from apps.web.main import app
from tests.conftest import TokenFactory

TODAY = date(2026, 3, 15)
URL = "/starting-balance"


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


async def _post(client: AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> Response:
    return await client.post(URL, headers=headers, json=body)


def _assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


@pytest.mark.db
async def test_create_and_get(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """До создания `GET` — 404 `FM-404201`; `POST` — 201 с остатком; после — `GET` отдаёт то же."""
    _assert_error(await client.get(URL, headers=headers), status.HTTP_404_NOT_FOUND, "FM-404201")

    response = await _post(client, headers, {"amount": 120000, "balance_date": "2026-01-01"})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json() == {"amount": 120000, "balance_date": "2026-01-01"}
    response = await client.get(URL, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {"amount": 120000, "balance_date": "2026-01-01"}


@pytest.mark.db
async def test_default_date_is_yesterday(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Без `balance_date` — вчера; `created_at` проставляет БД, в ответ он не попадает."""
    response = await _post(client, headers, {"amount": -500})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json() == {"amount": -500, "balance_date": "2026-03-14"}
    async with async_session_factory() as session:
        row = await session.scalar(select(StartingBalanceORM).where(StartingBalanceORM.user_uid == owner))
    assert row is not None
    assert row.created_at.tzinfo is not None


@pytest.mark.db
async def test_second_post_is_conflict(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Повторный `POST` — 409 `FM-409201`, остаток не меняется."""
    await _post(client, headers, {"amount": 100})

    response = await _post(client, headers, {"amount": 999, "balance_date": "2026-01-01"})

    _assert_error(response, status.HTTP_409_CONFLICT, "FM-409201")
    assert (await client.get(URL, headers=headers)).json() == {"amount": 100, "balance_date": "2026-03-14"}


@pytest.mark.db
async def test_balance_is_visible_only_to_owner(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], make_token: TokenFactory
) -> None:
    """Остаток одного пользователя не виден другому и не мешает ему задать свой."""
    other = {"Authorization": f"Bearer {make_token(uuid4())}"}
    await _post(client, headers, {"amount": 100, "balance_date": "2026-01-01"})

    _assert_error(await client.get(URL, headers=other), status.HTTP_404_NOT_FOUND, "FM-404201")
    response = await _post(client, other, {"amount": 7})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert (await client.get(URL, headers=headers)).json() == {"amount": 100, "balance_date": "2026-01-01"}


@pytest.mark.db
async def test_concurrent_posts_give_one_created_and_one_conflict(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]
) -> None:
    """Два параллельных `POST` одного пользователя — ровно один 201 и один 409."""
    responses = await asyncio.gather(
        _post(client, headers, {"amount": 1}),
        _post(client, headers, {"amount": 2}),
    )

    assert sorted(response.status_code for response in responses) == [
        status.HTTP_201_CREATED,
        status.HTTP_409_CONFLICT,
    ], [response.text for response in responses]
    [created] = [response for response in responses if response.status_code == status.HTTP_201_CREATED]
    assert (await client.get(URL, headers=headers)).json() == created.json()


@pytest.mark.db
async def test_repo_translates_primary_key_violation(db_engine: AsyncEngine) -> None:
    """
    Гонка, когда оба запроса прошли проверку команды: вставка второй строки — ошибка «уже задан», а не 500.

    Проверка команды обходится: репозиторий вызывается напрямую, вторая вставка — в отдельной сессии.
    """
    user_uid = uuid4()
    async with async_session_factory() as session:
        await Repo(session).create(StartingBalance(user_uid=user_uid, amount=1, balance_date=TODAY))
        await session.commit()

    async with async_session_factory() as session:
        with pytest.raises(StartingBalanceAlreadyExistsError):
            await Repo(session).create(StartingBalance(user_uid=user_uid, amount=2, balance_date=TODAY))


@pytest.mark.db
@pytest.mark.parametrize("amount", [-1_000_000_000, 0, 1_000_000_000])
async def test_amount_bounds_are_allowed(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], amount: int
) -> None:
    """Сумма от −1 000 000 000 до 1 000 000 000 включительно."""
    response = await _post(client, headers, {"amount": amount})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["amount"] == amount


@pytest.mark.db
@pytest.mark.parametrize("balance_date", ["2026-03-15", "2000-01-01"])
async def test_date_bounds_are_allowed(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], balance_date: str
) -> None:
    """Сегодня и 1 января 2000 года — допустимые даты."""
    response = await _post(client, headers, {"amount": 1, "balance_date": balance_date})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["balance_date"] == balance_date


@pytest.mark.parametrize("balance_date", ["2026-03-16", "1999-12-31"])
async def test_out_of_range_date_is_rejected(client: AsyncClient, headers: dict[str, str], balance_date: str) -> None:
    """Завтра или год вне 2000–2099 — 422 `FM-422002` с полем `balance_date`."""
    response = await _post(client, headers, {"amount": 1, "balance_date": balance_date})

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422002")
    assert [field["field"] for field in body["validation"]] == ["balance_date"]


@pytest.mark.parametrize(
    "body",
    [
        {"amount": 1_000_000_001},
        {"amount": -1_000_000_001},
        {"amount": "100"},
        {"amount": 1.5},
        {"amount": True},
        {"amount": None},
        {},
        {"amount": 1, "balance_date": None},
        {"amount": 1, "balance_date": "2026-02-30"},
        {"amount": 1, "balance_date": "15.03.2026"},
        {"amount": 1, "balance_date": "2026-03-01T00:00:00"},
        {"amount": 1, "balance_date": 0},
        {"amount": 1, "created_at": "2026-01-01T00:00:00Z"},
    ],
)
async def test_invalid_body_is_rejected(client: AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> None:
    """Нарушение формата тела, в том числе лишнее поле, — 422 `FM-422000`."""
    response = await _post(client, headers, body)

    _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_requires_token(client: AsyncClient, method: str) -> None:
    """Без токена — 401."""
    response = await client.request(method, URL, json={"amount": 1})

    _assert_error(response, status.HTTP_401_UNAUTHORIZED, "FM-401000")
