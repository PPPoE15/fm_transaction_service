import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from apps.modules.category.domain import Category
from apps.modules.transaction.application.commands import (
    CreateTransactionCommandHandler,
    DeleteTransactionCommandHandler,
    UpdateTransactionCommandHandler,
)
from apps.modules.transaction.application.commands import create as create_command
from apps.modules.transaction.application.exceptions import (
    TransactionCategoryNotFoundError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionTypeMismatchError,
)
from apps.modules.transaction.domain import MAX_TRANSACTIONS_PER_USER, Transaction
from apps.shared import apps_types
from tests.modules.category.fakes import InMemoryCategoryRepo
from tests.modules.transaction.fakes import FakeTransactionUnitOfWork, InMemoryTransactionRepo

OWNER = uuid4()
STRANGER = uuid4()
OUTCOME = apps_types.TransactionType.OUTCOME
INCOME = apps_types.TransactionType.INCOME
# По контракту transaction_date — локальное время без часового пояса.
DATE = datetime(2026, 10, 1, 12, 0)  # noqa: DTZ001
SMALL_LIMIT = 3
CONTRACT_LIMIT = 100_000


@pytest.fixture
def categories() -> InMemoryCategoryRepo:
    """Хранилище статей."""
    return InMemoryCategoryRepo()


@pytest.fixture
def transactions() -> InMemoryTransactionRepo:
    """Хранилище транзакций."""
    return InMemoryTransactionRepo()


@pytest.fixture
def uow(transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo) -> FakeTransactionUnitOfWork:
    """Единица работы модуля транзакций."""
    return FakeTransactionUnitOfWork(transactions, categories)


async def _add_category(
    categories: InMemoryCategoryRepo,
    user_uid: apps_types.UserUID,
    category_type: apps_types.TransactionType = OUTCOME,
) -> Category:
    category = Category.create(
        name="Еда", user_uid=user_uid, money_plan=1000, category_type=category_type, description=None
    )
    await categories.create(category)
    return category


async def _add_transaction(
    transactions: InMemoryTransactionRepo, user_uid: apps_types.UserUID, category: Category
) -> Transaction:
    transaction = Transaction.create(
        user_uid=user_uid,
        transaction_date=DATE,
        category_uid=category.uid,
        money_sum=100,
        transaction_type=OUTCOME,
        description="Обед",
    )
    await transactions.create(transaction)
    return transaction


async def _add_transactions(
    transactions: InMemoryTransactionRepo, user_uid: apps_types.UserUID, category: Category, count: int
) -> None:
    await asyncio.gather(*(_add_transaction(transactions, user_uid, category) for _ in range(count)))


async def _create(uow: FakeTransactionUnitOfWork, category_uid: apps_types.CategoryUID, **fields: Any) -> Transaction:
    return await CreateTransactionCommandHandler(uow).handle(
        **{
            "user_uid": OWNER,
            "transaction_date": DATE,
            "category_uid": category_uid,
            "money_sum": 100,
            "transaction_type": OUTCOME,
            "description": None,
            **fields,
        },
    )


async def test_create_in_own_category(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Транзакция создаётся в своей статье; обработчик возвращает созданный агрегат."""
    category = await _add_category(categories, OWNER)

    created = await _create(uow, category.uid)

    assert transactions.items[created.uid] == created
    assert (created.user_uid, created.category_uid) == (OWNER, category.uid)
    assert uow.committed


@pytest.mark.parametrize("category_owner", [STRANGER, None], ids=["чужая статья", "несуществующая статья"])
async def test_create_in_foreign_or_missing_category_is_rejected(
    uow: FakeTransactionUnitOfWork,
    transactions: InMemoryTransactionRepo,
    categories: InMemoryCategoryRepo,
    category_owner: apps_types.UserUID | None,
) -> None:
    """Нельзя создать транзакцию в чужой или несуществующей статье: 400 `FM-400201`, ответ одинаковый."""
    category_uid = (await _add_category(categories, category_owner)).uid if category_owner else uuid4()

    with pytest.raises(TransactionCategoryNotFoundError) as exc_info:
        await _create(uow, category_uid)

    assert exc_info.value.code == "FM-400201"
    assert not transactions.items
    assert not uow.committed


@pytest.mark.parametrize(
    ("category_type", "transaction_type"), [(OUTCOME, INCOME), (INCOME, OUTCOME)], ids=["расход", "доход"]
)
async def test_create_with_other_type_than_category_is_rejected(
    uow: FakeTransactionUnitOfWork,
    transactions: InMemoryTransactionRepo,
    categories: InMemoryCategoryRepo,
    category_type: apps_types.TransactionType,
    transaction_type: apps_types.TransactionType,
) -> None:
    """Тип транзакции должен совпадать с типом статьи: иначе 400 `FM-400202`."""
    category = await _add_category(categories, OWNER, category_type)

    with pytest.raises(TransactionTypeMismatchError) as exc_info:
        await _create(uow, category.uid, transaction_type=transaction_type)

    assert exc_info.value.code == "FM-400202"
    assert not transactions.items
    assert not uow.committed


@pytest.fixture
def small_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    """Лимит транзакций, уменьшенный для юнит-тестов (настоящий 100 000 проверяется на Postgres)."""
    monkeypatch.setattr(create_command, "MAX_TRANSACTIONS_PER_USER", SMALL_LIMIT)
    return SMALL_LIMIT


async def test_limit_is_100_000() -> None:
    """Лимит по контракту — 100 000 транзакций на пользователя."""
    assert MAX_TRANSACTIONS_PER_USER == CONTRACT_LIMIT


async def test_create_over_limit_is_conflict(
    uow: FakeTransactionUnitOfWork,
    transactions: InMemoryTransactionRepo,
    categories: InMemoryCategoryRepo,
    small_limit: int,
) -> None:
    """При лимите транзакций пользователя новая не создаётся: 409 `FM-409202`."""
    category = await _add_category(categories, OWNER)
    await _add_transactions(transactions, OWNER, category, small_limit)

    with pytest.raises(TransactionLimitExceededError) as exc_info:
        await _create(uow, category.uid)

    assert exc_info.value.code == "FM-409202"
    assert len(transactions.items) == small_limit
    assert not uow.committed


async def test_create_last_under_limit_and_foreign_transactions_are_not_counted(
    uow: FakeTransactionUnitOfWork,
    transactions: InMemoryTransactionRepo,
    categories: InMemoryCategoryRepo,
    small_limit: int,
) -> None:
    """Последняя транзакция до лимита создаётся; транзакции других пользователей в лимит не входят."""
    category = await _add_category(categories, OWNER)
    stranger_category = await _add_category(categories, STRANGER)
    await _add_transactions(transactions, OWNER, category, small_limit - 1)
    await _add_transactions(transactions, STRANGER, stranger_category, small_limit)

    created = await _create(uow, category.uid)

    assert created.uid in transactions.items
    assert uow.committed


async def test_update_own_transaction(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Свою транзакцию можно изменить, в том числе перенести в другую свою статью."""
    category = await _add_category(categories, OWNER)
    other_category = await _add_category(categories, OWNER)
    transaction = await _add_transaction(transactions, OWNER, category)

    await UpdateTransactionCommandHandler(uow).handle(
        user_uid=OWNER,
        transaction_uid=transaction.uid,
        transaction_date=transaction.transaction_date,
        category=other_category.uid,
        money_sum=250,
        transaction_type=OUTCOME,
        description="Ужин",
    )

    updated = transactions.items[transaction.uid]
    assert (updated.category_uid, updated.money_sum, updated.description) == (other_category.uid, 250, "Ужин")
    assert uow.committed


async def test_update_foreign_transaction_is_not_found(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Чужую транзакцию изменить нельзя, ответ — как на несуществующую; данные не меняются."""
    stranger_category = await _add_category(categories, STRANGER)
    foreign = await _add_transaction(transactions, STRANGER, stranger_category)

    with pytest.raises(TransactionNotFoundError) as exc_info:
        await UpdateTransactionCommandHandler(uow).handle(
            user_uid=OWNER,
            transaction_uid=foreign.uid,
            transaction_date=foreign.transaction_date,
            category=stranger_category.uid,
            money_sum=999,
            transaction_type=OUTCOME,
            description="Взлом",
        )

    assert "не найдена" in exc_info.value.msg

    assert transactions.items[foreign.uid] == foreign
    assert not uow.committed


async def test_update_missing_transaction_is_not_found(
    uow: FakeTransactionUnitOfWork, categories: InMemoryCategoryRepo
) -> None:
    """Несуществующая транзакция — 404."""
    category = await _add_category(categories, OWNER)

    with pytest.raises(TransactionNotFoundError):
        await UpdateTransactionCommandHandler(uow).handle(
            user_uid=OWNER,
            transaction_uid=uuid4(),
            transaction_date=DATE,
            category=category.uid,
            money_sum=1,
            transaction_type=OUTCOME,
            description=None,
        )


async def test_move_own_transaction_to_foreign_category_is_rejected(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Свою транзакцию нельзя перенести в чужую статью: 400 `FM-400201`, как при создании."""
    category = await _add_category(categories, OWNER)
    stranger_category = await _add_category(categories, STRANGER)
    transaction = await _add_transaction(transactions, OWNER, category)

    with pytest.raises(TransactionCategoryNotFoundError):
        await UpdateTransactionCommandHandler(uow).handle(
            user_uid=OWNER,
            transaction_uid=transaction.uid,
            transaction_date=transaction.transaction_date,
            category=stranger_category.uid,
            money_sum=100,
            transaction_type=OUTCOME,
            description=None,
        )

    assert transactions.items[transaction.uid].category_uid == category.uid
    assert not uow.committed


async def test_delete_own_transaction(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Свою транзакцию можно удалить."""
    transaction = await _add_transaction(transactions, OWNER, await _add_category(categories, OWNER))

    await DeleteTransactionCommandHandler(uow).handle(user_uid=OWNER, transaction_uid=transaction.uid)

    assert transaction.uid not in transactions.items
    assert uow.committed


async def test_delete_foreign_transaction_is_not_found(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Чужую транзакцию удалить нельзя, ответ — как на несуществующую."""
    foreign = await _add_transaction(transactions, STRANGER, await _add_category(categories, STRANGER))

    with pytest.raises(TransactionNotFoundError) as exc_info:
        await DeleteTransactionCommandHandler(uow).handle(user_uid=OWNER, transaction_uid=foreign.uid)

    assert "не найдена" in exc_info.value.msg

    assert foreign.uid in transactions.items
    assert not uow.committed
