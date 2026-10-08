from datetime import datetime
from uuid import uuid4

import pytest

from apps.modules.category import CategoryNotFoundError
from apps.modules.category.domain import Category
from apps.modules.transaction.application.commands import (
    CreateTransactionCommandHandler,
    DeleteTransactionCommandHandler,
    UpdateTransactionCommandHandler,
)
from apps.modules.transaction.application.exceptions import TransactionNotFoundError
from apps.modules.transaction.domain import Transaction
from apps.shared import apps_types
from tests.modules.category.fakes import InMemoryCategoryRepo
from tests.modules.transaction.fakes import FakeTransactionUnitOfWork, InMemoryTransactionRepo

OWNER = uuid4()
STRANGER = uuid4()
OUTCOME = apps_types.TransactionType.OUTCOME
# По контракту transaction_date — локальное время без часового пояса.
DATE = datetime(2026, 10, 1, 12, 0)  # noqa: DTZ001


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


async def _add_category(categories: InMemoryCategoryRepo, user_uid: apps_types.UserUID) -> Category:
    category = Category.create(name="Еда", user_uid=user_uid, money_plan=1000, category_type=OUTCOME, description=None)
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


async def test_create_in_own_category(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Транзакция создаётся в своей статье."""
    category = await _add_category(categories, OWNER)

    uid = await CreateTransactionCommandHandler(uow).handle(
        user_uid=OWNER,
        transaction_date=DATE,
        category=category.uid,
        money_sum=100,
        transaction_type=OUTCOME,
        description=None,
    )

    assert transactions.items[uid].user_uid == OWNER
    assert uow.committed


@pytest.mark.parametrize("category_owner", [STRANGER, None], ids=["чужая статья", "несуществующая статья"])
async def test_create_in_foreign_or_missing_category_is_not_found(
    uow: FakeTransactionUnitOfWork,
    transactions: InMemoryTransactionRepo,
    categories: InMemoryCategoryRepo,
    category_owner: apps_types.UserUID | None,
) -> None:
    """Нельзя создать транзакцию в чужой или несуществующей статье: ответ как на несуществующую."""
    category_uid = (await _add_category(categories, category_owner)).uid if category_owner else uuid4()

    with pytest.raises(CategoryNotFoundError):
        await CreateTransactionCommandHandler(uow).handle(
            user_uid=OWNER,
            transaction_date=DATE,
            category=category_uid,
            money_sum=100,
            transaction_type=OUTCOME,
            description=None,
        )

    assert not transactions.items
    assert not uow.committed


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


async def test_move_own_transaction_to_foreign_category_is_not_found(
    uow: FakeTransactionUnitOfWork, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo
) -> None:
    """Свою транзакцию нельзя перенести в чужую статью."""
    category = await _add_category(categories, OWNER)
    stranger_category = await _add_category(categories, STRANGER)
    transaction = await _add_transaction(transactions, OWNER, category)

    with pytest.raises(CategoryNotFoundError):
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
