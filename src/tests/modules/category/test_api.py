"""`POST /categories` на настоящем Postgres: ответ, валидация, дубликат, лимит и гонки параллельных запросов."""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category.application.exceptions import CategoryAlreadyExistsError
from apps.modules.category.domain import MAX_CATEGORIES_PER_USER, Category
from apps.modules.category.infrastructure.orm import Category as CategoryORM
from apps.modules.category.infrastructure.repo import Repo
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory

URL = "/categories"
OUTCOME = apps_types.TransactionType.OUTCOME
BODY = {"name": "еда вне дома", "money_plan": 5000, "category_type": "outcome", "description": "Кафе и доставка"}


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


async def _list(client: AsyncClient, headers: dict[str, str], **params: str) -> list[dict[str, Any]]:
    response = await client.get(URL, headers=headers, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    content: list[dict[str, Any]] = response.json()["content"]
    return content


def _assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


async def _add_categories(user_uid: UUID, count: int) -> None:
    """Статьи пользователя напрямую в БД, в обход API."""
    async with async_session_factory() as session:
        session.add_all(
            CategoryORM(
                uid=uuid4(),
                user_uid=user_uid,
                name=f"Статья {number}",
                money_plan=None,
                category_type=OUTCOME,
                description=None,
            )
            for number in range(count)
        )
        await session.commit()


@pytest.mark.db
async def test_create(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """`POST` — 201, созданная статья и `Location`; статья сразу есть в списке своего типа и нет в чужом."""
    response = await _post(client, headers, BODY)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    created = response.json()
    assert created == {**BODY, "uid": created["uid"]}
    assert response.headers["location"] == f"/transaction/categories/{created['uid']}"
    assert await _list(client, headers, category_type="outcome") == [created]
    assert await _list(client, headers, category_type="income") == []


@pytest.mark.db
@pytest.mark.parametrize(
    ("body", "money_plan"),
    [({}, None), ({"money_plan": None}, None), ({"money_plan": 0}, 0), ({"money_plan": 1_000_000_000}, 1_000_000_000)],
    ids=["план не передан", "план null", "план 0", "максимальный план"],
)
async def test_plan_is_optional(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], body: dict[str, Any], money_plan: int | None
) -> None:
    """План необязателен: не передан или `null` — `null`, `0` остаётся нулём."""
    response = await _post(client, headers, {"name": "Подарки", "category_type": "outcome", **body})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["money_plan"] == money_plan
    [listed] = await _list(client, headers)
    assert listed["money_plan"] == money_plan
    assert listed["description"] is None


@pytest.mark.db
@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("name", "  Продукты \t", "Продукты"),
        ("name", "я" * 64, "я" * 64),
        ("description", "", None),
        ("description", "Строка 1\nСтрока 2\tи\r\nтаб", "Строка 1\nСтрока 2\tи\r\nтаб"),
        ("description", "д" * 500, "д" * 500),
    ],
    ids=["пробелы по краям обрезаются", "64 символа", "пустое описание — null", "переводы строк", "500 символов"],
)
async def test_normalized_values(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], field: str, value: str, expected: str | None
) -> None:
    """Допустимые граничные значения сохраняются, пробелы по краям названия обрезаются, `""` — `null`."""
    response = await _post(client, headers, {**BODY, field: value})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()[field] == expected
    [listed] = await _list(client, headers)
    assert listed[field] == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("name", "я" * 65),
        ("name", " " + "я" * 65),
        ("name", "Еда\x00"),
        ("name", "Еда\nвне дома"),
        ("name", "Еда\x7f"),
        ("name", 5),
        ("name", None),
        ("money_plan", -1),
        ("money_plan", 1_000_000_001),
        ("money_plan", "100"),
        ("money_plan", 1.5),
        ("money_plan", True),
        ("category_type", "transfer"),
        ("category_type", None),
        ("description", "д" * 501),
        ("description", "Кафе\x00"),
        ("description", "Кафе\x1b"),
        ("description", 5),
    ],
)
async def test_invalid_field(client: AsyncClient, make_token: TokenFactory, field: str, value: object) -> None:
    """Нарушение ограничения поля — 422 `FM-422000` с этим полем в `validation`."""
    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, {**BODY, field: value})

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")
    assert [item["field"] for item in body["validation"]] == [field]


@pytest.mark.parametrize("field", ["name", "category_type"])
async def test_missing_required_field(client: AsyncClient, make_token: TokenFactory, field: str) -> None:
    """Без названия или типа — 422."""
    body = {key: value for key, value in BODY.items() if key != field}

    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, body)

    _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")


async def test_unknown_field(client: AsyncClient, make_token: TokenFactory) -> None:
    """Неизвестное поле в теле — 422 (`additionalProperties: false`)."""
    response = await _post(client, {"Authorization": f"Bearer {make_token()}"}, {**BODY, "user_uid": str(uuid4())})

    _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")


async def test_old_path_is_gone(client: AsyncClient, make_token: TokenFactory) -> None:
    """Старый `POST /category` удалён: создание — только `POST /categories`."""
    response = await client.post("/category", headers={"Authorization": f"Bearer {make_token()}"}, json=BODY)

    assert response.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED}, response.text


@pytest.mark.db
async def test_duplicate_is_conflict(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], make_token: TokenFactory
) -> None:
    """
    Повтор названия и типа у пользователя — 409 `FM-409101`, в том числе после обрезки пробелов.

    То же название с другим типом или у другого пользователя — допустимо.
    """
    await _post(client, headers, BODY)

    _assert_error(await _post(client, headers, BODY), status.HTTP_409_CONFLICT, "FM-409101")
    response = await _post(client, headers, {**BODY, "name": f" {BODY['name']} "})
    _assert_error(response, status.HTTP_409_CONFLICT, "FM-409101")
    response = await _post(client, headers, {**BODY, "category_type": "income"})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    other = {"Authorization": f"Bearer {make_token(uuid4())}"}
    assert (await _post(client, other, BODY)).status_code == status.HTTP_201_CREATED
    assert [item["category_type"] for item in await _list(client, headers)] == ["income", "outcome"]


@pytest.mark.db
async def test_limit(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID, make_token: TokenFactory
) -> None:
    """Сотая статья создаётся, сто первая — 409 `FM-409103`; лимит считается по пользователю."""
    await _add_categories(owner, MAX_CATEGORIES_PER_USER - 1)

    assert (await _post(client, headers, BODY)).status_code == status.HTTP_201_CREATED
    response = await _post(client, headers, {**BODY, "name": "Лишняя"})

    _assert_error(response, status.HTTP_409_CONFLICT, "FM-409103")
    other = {"Authorization": f"Bearer {make_token(uuid4())}"}
    assert (await _post(client, other, BODY)).status_code == status.HTTP_201_CREATED


@pytest.mark.db
async def test_concurrent_posts_do_not_exceed_limit(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """Параллельные `POST` на 99 статьях — ровно один 201, остальные 409 `FM-409103`; статей ровно 100."""
    await _add_categories(owner, MAX_CATEGORIES_PER_USER - 1)

    responses = await asyncio.gather(*(_post(client, headers, {**BODY, "name": f"Новая {n}"}) for n in range(5)))

    codes = sorted(response.status_code for response in responses)
    assert codes == [status.HTTP_201_CREATED] + [status.HTTP_409_CONFLICT] * 4, [r.text for r in responses]
    assert {response.json()["code"] for response in responses if response.status_code == status.HTTP_409_CONFLICT} == {
        "FM-409103"
    }
    assert len(await _list(client, headers)) == MAX_CATEGORIES_PER_USER


@pytest.mark.db
async def test_concurrent_duplicates_give_one_created(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]
) -> None:
    """Параллельные одинаковые `POST` — один 201, остальные 409 `FM-409101`."""
    responses = await asyncio.gather(*(_post(client, headers, BODY) for _ in range(3)))

    codes = sorted(response.status_code for response in responses)
    assert codes == [status.HTTP_201_CREATED] + [status.HTTP_409_CONFLICT] * 2, [r.text for r in responses]
    assert len(await _list(client, headers)) == 1


@pytest.mark.db
async def test_repo_translates_unique_violation(db_engine: AsyncEngine) -> None:
    """
    Гонка, прошедшая проверку команды: вставка дубликата — ошибка «уже есть», а не 500.

    Проверка команды обходится: репозиторий вызывается напрямую, вторая вставка — в отдельной сессии.
    """
    user_uid = uuid4()

    def _category() -> Category:
        return Category.create(name="Еда", user_uid=user_uid, money_plan=None, category_type=OUTCOME, description=None)

    async with async_session_factory() as session:
        await Repo(session).create(_category())
        await session.commit()

    async with async_session_factory() as session:
        with pytest.raises(CategoryAlreadyExistsError):
            await Repo(session).create(_category())


@pytest.mark.db
async def test_list_is_sorted_by_name(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Список статей отсортирован по названию."""
    for name in ["Транспорт", "Аренда", "Еда"]:
        await _post(client, headers, {**BODY, "name": name})

    assert [item["name"] for item in await _list(client, headers)] == ["Аренда", "Еда", "Транспорт"]
