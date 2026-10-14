"""`POST /transactions` по контракту (`createTransaction`): ответ, валидация, правила статьи, лимит и гонки."""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category.infrastructure.orm import Category as CategoryORM
from apps.modules.transaction.domain import MAX_TRANSACTIONS_PER_USER
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory

URL = "/transactions"
OUTCOME = apps_types.TransactionType.OUTCOME
INCOME = apps_types.TransactionType.INCOME
CATEGORY_NAME = "Еда вне дома"


@pytest.fixture
def owner() -> UUID:
    """Пользователь из токена."""
    return uuid4()


@pytest.fixture
def headers(make_token: TokenFactory, owner: UUID) -> dict[str, str]:
    """Заголовок авторизации владельца."""
    return {"Authorization": f"Bearer {make_token(owner)}"}


async def _add_category(user_uid: UUID, category_type: apps_types.TransactionType = OUTCOME) -> UUID:
    """Статья пользователя напрямую в БД, в обход API."""
    category = CategoryORM(
        uid=uuid4(),
        user_uid=user_uid,
        name=CATEGORY_NAME,
        money_plan=None,
        category_type=category_type,
        description=None,
    )
    async with async_session_factory() as session:
        session.add(category)
        await session.commit()
    return category.uid


async def _add_transactions(user_uid: UUID, category_uid: UUID, count: int) -> None:
    """`count` транзакций пользователя одним INSERT … SELECT в обход API: 100 000 строк вставляются за секунды."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO transactions (uid, user_uid, transaction_date, category_uid, money_sum, transaction_type)"
                " SELECT gen_random_uuid(), :user_uid, '2026-01-01T00:00:00', :category_uid, 1, 'outcome'"
                " FROM generate_series(1, :count)"
            ),
            {"user_uid": user_uid, "category_uid": category_uid, "count": count},
        )
        await session.commit()


def _body(category_uid: UUID | str, **fields: Any) -> dict[str, Any]:
    return {
        "transaction_date": "2026-03-14T19:30:00",
        "category_uid": str(category_uid),
        "money_sum": 1250,
        "transaction_type": "outcome",
        "description": "Ужин",
        **fields,
    }


async def _post(client: AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> Response:
    return await client.post(URL, headers=headers, json=body)


async def _list(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get(URL, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


def _assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


@pytest.mark.db
async def test_create(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID) -> None:
    """201, созданная транзакция со статьёй `{uid, name}` и `Location`; транзакция сразу есть в списке."""
    category_uid = await _add_category(owner)

    response = await _post(client, headers, _body(category_uid))

    assert response.status_code == status.HTTP_201_CREATED, response.text
    created = response.json()
    assert created == {
        "uid": created["uid"],
        "transaction_date": "2026-03-14T19:30:00",
        "category": {"uid": str(category_uid), "name": CATEGORY_NAME},
        "money_sum": 1250,
        "transaction_type": "outcome",
        "description": "Ужин",
    }
    assert response.headers["location"] == f"/transaction/transactions/{created['uid']}"
    listed = await _list(client, headers)
    assert listed["total"] == 1
    assert listed["content"] == [created]


@pytest.mark.db
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"description": ""}, {"description": None}),
        ({"description": None}, {"description": None}),
        ({"description": "Строка 1\nСтрока 2\tи\r\nтаб"}, {"description": "Строка 1\nСтрока 2\tи\r\nтаб"}),
        ({"description": "д" * 500}, {"description": "д" * 500}),
        ({"money_sum": 1}, {"money_sum": 1}),
        ({"money_sum": 1_000_000_000}, {"money_sum": 1_000_000_000}),
        ({"transaction_date": "2000-01-01T00:00:00"}, {"transaction_date": "2000-01-01T00:00:00"}),
        ({"transaction_date": "2099-12-31T23:59:59.999999"}, {"transaction_date": "2099-12-31T23:59:59.999999"}),
        ({"transaction_date": "2028-02-29T10:00:00.5"}, {"transaction_date": "2028-02-29T10:00:00.500000"}),
    ],
    ids=[
        "пустое описание — null",
        "описание null",
        "переводы строк и табуляция",
        "500 символов",
        "минимальная сумма",
        "максимальная сумма",
        "первый допустимый момент",
        "последний допустимый момент",
        "29 февраля високосного года, доли секунды",
    ],
)
async def test_boundary_values(
    db_engine: AsyncEngine,
    client: AsyncClient,
    headers: dict[str, str],
    owner: UUID,
    fields: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Граничные допустимые значения сохраняются; `""` в описании — `null`."""
    category_uid = await _add_category(owner)

    response = await _post(client, headers, _body(category_uid, **fields))

    assert response.status_code == status.HTTP_201_CREATED, response.text
    created = response.json()
    assert created | expected == created
    assert (await _list(client, headers))["content"] == [created]


@pytest.mark.db
async def test_description_is_optional(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Описание можно не передавать — `null`."""
    body = _body(await _add_category(owner))
    del body["description"]

    response = await _post(client, headers, body)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("money_sum", 0),
        ("money_sum", -1),
        ("money_sum", 1_000_000_001),
        ("money_sum", "100"),
        ("money_sum", 1.5),
        ("money_sum", True),
        ("money_sum", None),
        ("transaction_date", "1999-12-31T23:59:59"),
        ("transaction_date", "2100-01-01T00:00:00"),
        ("transaction_date", "2026-02-30T12:00:00"),
        ("transaction_date", "2027-02-29T12:00:00"),
        ("transaction_date", "2026-13-01T12:00:00"),
        ("transaction_date", "2026-03-14T24:00:00"),
        ("transaction_date", "2026-03-14"),
        ("transaction_date", "2026-03-14T19:30"),
        ("transaction_date", "2026-03-14 19:30:00"),
        ("transaction_date", "2026-03-14T19:30:00Z"),
        ("transaction_date", "2026-03-14T19:30:00+03:00"),
        ("transaction_date", "2026-03-14T19:30:00.1234567"),
        ("transaction_date", "２０２６-03-14T19:30:00"),
        ("transaction_date", 1773516600),
        ("transaction_date", None),
        ("category_uid", "not-a-uuid"),
        ("category_uid", None),
        ("transaction_type", "transfer"),
        ("transaction_type", None),
        ("description", "д" * 501),
        ("description", "Ужин\x00"),
        ("description", "Ужин\x1b"),
        ("description", "Ужин\x7f"),
        ("description", 5),
    ],
)
async def test_invalid_field(client: AsyncClient, make_token: TokenFactory, field: str, value: object) -> None:
    """Нарушение ограничения поля — 422 `FM-422000` с этим полем в `validation`."""
    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, {**_body(uuid4()), field: value})

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")
    assert [item["field"] for item in body["validation"]] == [field]


@pytest.mark.parametrize("field", ["transaction_date", "category_uid", "money_sum", "transaction_type"])
async def test_missing_required_field(client: AsyncClient, make_token: TokenFactory, field: str) -> None:
    """Без обязательного поля — 422 с этим полем."""
    body = {key: value for key, value in _body(uuid4()).items() if key != field}

    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, body)

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")
    assert [item["field"] for item in body["validation"]] == [field]


@pytest.mark.parametrize("field", ["user_uid", "category", "uid"])
async def test_unknown_field(client: AsyncClient, make_token: TokenFactory, field: str) -> None:
    """Неизвестное поле в теле (в том числе старое `category`) — 422 (`additionalProperties: false`)."""
    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, {**_body(uuid4()), field: "x"})

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")
    assert [item["field"] for item in body["validation"]] == [field]


@pytest.mark.db
async def test_missing_category(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Несуществующая статья — 400 `FM-400201`, транзакция не создаётся."""
    response = await _post(client, headers, _body(uuid4()))

    _assert_error(response, status.HTTP_400_BAD_REQUEST, "FM-400201")
    assert (await _list(client, headers))["total"] == 0


@pytest.mark.db
async def test_foreign_category(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], make_token: TokenFactory
) -> None:
    """Статья другого пользователя — 400 `FM-400201`, как несуществующая; транзакция не создаётся ни у кого."""
    stranger = uuid4()
    foreign_category = await _add_category(stranger)
    stranger_headers = {"Authorization": f"Bearer {make_token(stranger)}"}

    response = await _post(client, headers, _body(foreign_category))

    _assert_error(response, status.HTTP_400_BAD_REQUEST, "FM-400201")
    assert (await _list(client, headers))["total"] == 0
    assert (await _list(client, stranger_headers))["total"] == 0


@pytest.mark.db
@pytest.mark.parametrize(
    ("category_type", "transaction_type"), [(OUTCOME, "income"), (INCOME, "outcome")], ids=["расход", "доход"]
)
async def test_type_mismatch(
    db_engine: AsyncEngine,
    client: AsyncClient,
    headers: dict[str, str],
    owner: UUID,
    category_type: apps_types.TransactionType,
    transaction_type: str,
) -> None:
    """Тип транзакции не совпадает с типом статьи — 400 `FM-400202`; с совпадающим типом создаётся."""
    category_uid = await _add_category(owner, category_type)

    response = await _post(client, headers, _body(category_uid, transaction_type=transaction_type))

    _assert_error(response, status.HTTP_400_BAD_REQUEST, "FM-400202")
    assert (await _list(client, headers))["total"] == 0
    response = await _post(client, headers, _body(category_uid, transaction_type=category_type.value))
    assert response.status_code == status.HTTP_201_CREATED, response.text


@pytest.mark.db
async def test_limit(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID, make_token: TokenFactory
) -> None:
    """
    Транзакция номер 100 000 создаётся, следующая — 409 `FM-409202`.

    Транзакции другого пользователя в лимит не считаются: у него при чужих 100 000 создание проходит.
    """
    category_uid = await _add_category(owner)
    await _add_transactions(owner, category_uid, MAX_TRANSACTIONS_PER_USER - 1)

    assert (await _post(client, headers, _body(category_uid))).status_code == status.HTTP_201_CREATED
    _assert_error(await _post(client, headers, _body(category_uid)), status.HTTP_409_CONFLICT, "FM-409202")

    stranger = uuid4()
    stranger_headers = {"Authorization": f"Bearer {make_token(stranger)}"}
    response = await _post(client, stranger_headers, _body(await _add_category(stranger)))
    assert response.status_code == status.HTTP_201_CREATED, response.text


@pytest.mark.db
async def test_concurrent_posts_do_not_exceed_limit(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Параллельные `POST` при 99 999 транзакциях — ровно один 201, остальные 409 `FM-409202`; всего 100 000."""
    category_uid = await _add_category(owner)
    await _add_transactions(owner, category_uid, MAX_TRANSACTIONS_PER_USER - 1)

    responses = await asyncio.gather(*(_post(client, headers, _body(category_uid)) for _ in range(5)))

    codes = sorted(response.status_code for response in responses)
    assert codes == [status.HTTP_201_CREATED] + [status.HTTP_409_CONFLICT] * 4, [r.text for r in responses]
    assert {r.json()["code"] for r in responses if r.status_code == status.HTTP_409_CONFLICT} == {"FM-409202"}
    assert (await _list(client, headers))["total"] == MAX_TRANSACTIONS_PER_USER


async def _wait_for_blocked_backend(engine: AsyncEngine) -> None:
    """Дождаться, пока какой-то запрос в БД встанет в ожидание блокировки (`pg_locks.granted = false`)."""
    deadline = asyncio.get_running_loop().time() + 5
    while asyncio.get_running_loop().time() < deadline:
        async with engine.connect() as connection:
            if (await connection.scalar(text("SELECT count(*) FROM pg_locks WHERE NOT granted"))) > 0:
                return
        await asyncio.sleep(0.05)
    pytest.fail("запрос не ждёт блокировку")


@pytest.mark.db
async def test_create_waits_for_uncommitted_type_change(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """
    Незакоммиченная смена типа статьи задерживает создание транзакции; после коммита — 400 `FM-400202`.

    Без блокировки статьи при чтении команда видит старый тип и проходит проверку: расходная транзакция
    оказывается в статье дохода.
    """
    category_uid = await _add_category(owner, OUTCOME)
    async with async_session_factory() as session:
        # Как смена типа в PATCH /categories/{uid}: строка статьи под FOR UPDATE, затем UPDATE типа
        await session.execute(text("SELECT uid FROM categories WHERE uid = :uid FOR UPDATE"), {"uid": category_uid})
        await session.execute(
            text("UPDATE categories SET category_type = 'income' WHERE uid = :uid"), {"uid": category_uid}
        )
        post = asyncio.create_task(_post(client, headers, _body(category_uid, transaction_type="outcome")))
        await _wait_for_blocked_backend(db_engine)
        assert not post.done()
        await session.commit()

    _assert_error(await post, status.HTTP_400_BAD_REQUEST, "FM-400202")
    assert (await _list(client, headers))["total"] == 0
