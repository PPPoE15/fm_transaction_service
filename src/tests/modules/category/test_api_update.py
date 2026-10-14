"""`PATCH /categories/{uid}` на настоящем Postgres: частичное изменение, валидация, дубликат, смена типа и гонки."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status

from apps.modules.category.application.exceptions import CategoryAlreadyExistsError
from apps.modules.category.domain import Category, CategoryChanges
from apps.modules.category.infrastructure.repo import Repo
from apps.modules.transaction import TransactionORM
from apps.shared import apps_types
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory

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


async def _create(client: AsyncClient, headers: dict[str, str], **fields: Any) -> dict[str, Any]:
    response = await client.post("/categories", headers=headers, json={**BODY, **fields})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    created: dict[str, Any] = response.json()
    return created


async def _patch(client: AsyncClient, headers: dict[str, str], uid: str, body: object) -> Response:
    return await client.patch(f"/categories/{uid}", headers=headers, json=body)


async def _list(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = await client.get("/categories", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    content: list[dict[str, Any]] = response.json()["content"]
    return content


def _assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


@pytest.mark.db
async def test_partial_update(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """Меняются только переданные поля; ответ — статья после изменения, она же в списке."""
    created = await _create(client, headers)

    response = await _patch(client, headers, created["uid"], {"name": " Кафе "})

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {**created, "name": "Кафе"}
    assert await _list(client, headers) == [response.json()]


@pytest.mark.db
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"money_plan": None}, {"money_plan": None}),
        ({"money_plan": 0}, {"money_plan": 0}),
        ({"description": None}, {"description": None}),
        ({"description": ""}, {"description": None}),
        ({"category_type": "income"}, {"category_type": "income"}),
    ],
    ids=["план очищен", "план 0", "описание очищено", "пустое описание", "тип без транзакций"],
)
async def test_null_clears_and_zero_is_kept(
    db_engine: AsyncEngine,
    client: AsyncClient,
    headers: dict[str, str],
    body: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """`null` очищает план и описание, `0` в плане — ноль, у статьи без транзакций меняется тип."""
    created = await _create(client, headers)

    response = await _patch(client, headers, created["uid"], body)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {**created, **expected}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("name", "д" * 65),
        ("name", "Еда\x00"),
        ("name", None),
        ("money_plan", -1),
        ("money_plan", 1_000_000_001),
        ("money_plan", "100"),
        ("money_plan", 1.5),
        ("category_type", "transfer"),
        ("category_type", None),
        ("description", "д" * 501),
        ("description", "Кафе\x1b"),
    ],
)
async def test_invalid_field(client: AsyncClient, make_token: TokenFactory, field: str, value: object) -> None:
    """Нарушение ограничения поля — 422 `FM-422000` с этим полем; `null` в названии и типе недопустим."""
    response = await _patch(client, {"Authorization": f"Bearer {make_token()}"}, str(uuid4()), {field: value})

    body = _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")
    assert [item["field"] for item in body["validation"]] == [field]


@pytest.mark.parametrize("body", [{}, {"user_uid": str(uuid4())}, {"name": "Еда", "uid": str(uuid4())}])
async def test_empty_or_unknown_field(client: AsyncClient, make_token: TokenFactory, body: dict[str, Any]) -> None:
    """Пустое тело (`minProperties: 1`) и неизвестное поле (`additionalProperties: false`) — 422."""
    response = await _patch(client, {"Authorization": f"Bearer {make_token()}"}, str(uuid4()), body)

    _assert_error(response, status.HTTP_422_UNPROCESSABLE_CONTENT, "FM-422000")


@pytest.mark.db
async def test_missing_or_foreign_is_not_found(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], make_token: TokenFactory
) -> None:
    """Несуществующая и чужая статья — 404; чужая не меняется."""
    created = await _create(client, headers)
    stranger = {"Authorization": f"Bearer {make_token(uuid4())}"}

    _assert_error(await _patch(client, headers, str(uuid4()), {"name": "Кафе"}), status.HTTP_404_NOT_FOUND, "FM-404000")
    _assert_error(
        await _patch(client, stranger, created["uid"], {"name": "Кафе"}), status.HTTP_404_NOT_FOUND, "FM-404000"
    )
    assert await _list(client, headers) == [created]


@pytest.mark.db
async def test_duplicate_is_conflict(db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]) -> None:
    """
    Название другой статьи того же типа — 409 `FM-409101` (в том числе после обрезки пробелов).

    Своё же название и название статьи другого типа — не дубликат.
    """
    created = await _create(client, headers)
    await _create(client, headers, name="Кафе")
    await _create(client, headers, name="Бонус", category_type="income")

    _assert_error(
        await _patch(client, headers, created["uid"], {"name": "Кафе"}), status.HTTP_409_CONFLICT, "FM-409101"
    )
    response = await _patch(client, headers, created["uid"], {"name": " Кафе "})
    _assert_error(response, status.HTTP_409_CONFLICT, "FM-409101")
    assert (await _patch(client, headers, created["uid"], {"name": BODY["name"]})).status_code == status.HTTP_200_OK
    assert (await _patch(client, headers, created["uid"], {"name": "Бонус"})).status_code == status.HTTP_200_OK


@pytest.mark.db
async def test_type_change_with_transactions_is_forbidden(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]
) -> None:
    """Смена типа у статьи с транзакциями — 400 `FM-400101`; без смены типа такая статья меняется."""
    created = await _create(client, headers)
    response = await client.post(
        "/transactions",
        headers=headers,
        json={
            "transaction_date": "2026-10-01T12:00:00",
            "category": created["uid"],
            "money_sum": 100,
            "transaction_type": "outcome",
            "description": "Обед",
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await _patch(client, headers, created["uid"], {"category_type": "income"})

    _assert_error(response, status.HTTP_400_BAD_REQUEST, "FM-400101")
    assert await _list(client, headers) == [created]
    response = await _patch(client, headers, created["uid"], {"category_type": "outcome", "money_plan": 1})
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.db
async def test_type_change_waits_for_uncommitted_transaction(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str], owner: UUID
) -> None:
    """
    Транзакция, вставленная, но ещё не закоммиченная, задерживает смену типа; после коммита — 400 `FM-400101`.

    Без блокировки строки статьи проверка транзакций не видит незакоммиченную вставку, и обе операции проходят:
    расходная транзакция оказывается в статье дохода.
    """
    created = await _create(client, headers)
    async with async_session_factory() as session:
        session.add(
            TransactionORM(
                uid=uuid4(),
                user_uid=owner,
                transaction_date=datetime(2026, 10, 1, 12),  # noqa: DTZ001 — колонка без часового пояса
                category_uid=UUID(created["uid"]),
                money_sum=100,
                transaction_type=OUTCOME,
                description="Обед",
            )
        )
        await session.flush()
        patch = asyncio.create_task(_patch(client, headers, created["uid"], {"category_type": "income"}))
        # TODO(FM-45): фиксированная пауза ничего не доказывает (PATCH ждёт и без `lock_category` — на UPDATE типа),
        # а на медленном CI он может не дойти до проверки до коммита, и тест ложно пройдёт. Ждать, пока бэкенд PATCH
        # появится в `pg_locks` с `granted = false`.
        await asyncio.sleep(0.5)
        assert not patch.done(), "смена типа не ждёт незакоммиченную транзакцию"
        await session.commit()

    _assert_error(await patch, status.HTTP_400_BAD_REQUEST, "FM-400101")
    assert await _list(client, headers) == [created]


@pytest.mark.db
async def test_concurrent_renames_to_same_name(
    db_engine: AsyncEngine, client: AsyncClient, headers: dict[str, str]
) -> None:
    """Параллельные переименования разных статей в одно название — один 200, остальные 409 `FM-409101`."""
    uids = [(await _create(client, headers, name=f"Статья {n}"))["uid"] for n in range(3)]

    responses = await asyncio.gather(*(_patch(client, headers, uid, {"name": "Кафе"}) for uid in uids))

    codes = sorted(response.status_code for response in responses)
    assert codes == [status.HTTP_200_OK] + [status.HTTP_409_CONFLICT] * 2, [r.text for r in responses]
    assert [item["name"] for item in await _list(client, headers)].count("Кафе") == 1


@pytest.mark.db
async def test_repo_update_translates_unique_violation(db_engine: AsyncEngine) -> None:
    """
    Гонка, прошедшая проверку команды: переименование в занятое название — ошибка «уже есть», а не 500.

    Проверка команды обходится: репозиторий вызывается напрямую.
    """
    user_uid = uuid4()
    first, second = (
        Category.create(name=name, user_uid=user_uid, money_plan=None, category_type=OUTCOME, description=None)
        for name in ("Еда", "Кафе")
    )
    async with async_session_factory() as session:
        await Repo(session).create(first)
        await Repo(session).create(second)
        await session.commit()

    second.update(CategoryChanges(name="Еда"))
    async with async_session_factory() as session:
        with pytest.raises(CategoryAlreadyExistsError):
            await Repo(session).update(second)


async def test_old_path_is_gone(client: AsyncClient, make_token: TokenFactory) -> None:
    """Старый `PATCH /category?category_uid=` удалён: изменение — только `PATCH /categories/{uid}`."""
    response = await client.patch(
        "/category",
        params={"category_uid": str(uuid4())},
        headers={"Authorization": f"Bearer {make_token()}"},
        json=BODY,
    )

    assert response.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED}, response.text
