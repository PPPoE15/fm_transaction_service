from datetime import date
from uuid import uuid4

import pytest

from apps.modules.starting_balance.application.commands import CreateStartingBalanceCommandHandler
from apps.modules.starting_balance.application.exceptions import StartingBalanceAlreadyExistsError
from apps.modules.starting_balance.domain import InvalidBalanceDateError, StartingBalance
from tests.modules.starting_balance.fakes import FakeStartingBalanceUnitOfWork, InMemoryStartingBalanceRepo

OWNER = uuid4()
TODAY = date(2026, 3, 15)


@pytest.fixture
def starting_balances() -> InMemoryStartingBalanceRepo:
    """Хранилище стартовых остатков."""
    return InMemoryStartingBalanceRepo()


@pytest.fixture
def uow(starting_balances: InMemoryStartingBalanceRepo) -> FakeStartingBalanceUnitOfWork:
    """Единица работы модуля стартового остатка."""
    return FakeStartingBalanceUnitOfWork(starting_balances)


async def test_create(uow: FakeStartingBalanceUnitOfWork, starting_balances: InMemoryStartingBalanceRepo) -> None:
    """Остаток сохраняется и возвращается."""
    created = await CreateStartingBalanceCommandHandler(uow).handle(
        user_uid=OWNER, amount=120_000, balance_date=date(2026, 1, 1), today=TODAY
    )

    assert created == StartingBalance(user_uid=OWNER, amount=120_000, balance_date=date(2026, 1, 1))
    assert starting_balances.items[OWNER] == created
    assert uow.committed


async def test_default_date_is_yesterday(
    uow: FakeStartingBalanceUnitOfWork, starting_balances: InMemoryStartingBalanceRepo
) -> None:
    """Без даты сохраняется вчерашний день."""
    await CreateStartingBalanceCommandHandler(uow).handle(user_uid=OWNER, amount=100, balance_date=None, today=TODAY)

    assert starting_balances.items[OWNER].balance_date == date(2026, 3, 14)


async def test_second_create_is_rejected(
    uow: FakeStartingBalanceUnitOfWork, starting_balances: InMemoryStartingBalanceRepo
) -> None:
    """Остаток задаётся один раз: повторное создание — 409 `FM-409201`, первый остаток не меняется."""
    first = StartingBalance(user_uid=OWNER, amount=100, balance_date=date(2026, 1, 1))
    await starting_balances.create(first)

    with pytest.raises(StartingBalanceAlreadyExistsError) as exc_info:
        await CreateStartingBalanceCommandHandler(uow).handle(
            user_uid=OWNER, amount=999, balance_date=None, today=TODAY
        )

    assert exc_info.value.code == "FM-409201"
    assert starting_balances.items == {OWNER: first}
    assert not uow.committed


async def test_other_user_balance_does_not_block_create(
    uow: FakeStartingBalanceUnitOfWork, starting_balances: InMemoryStartingBalanceRepo
) -> None:
    """Остаток другого пользователя не мешает задать свой."""
    stranger = uuid4()
    await starting_balances.create(StartingBalance(user_uid=stranger, amount=1, balance_date=date(2026, 1, 1)))

    await CreateStartingBalanceCommandHandler(uow).handle(user_uid=OWNER, amount=100, balance_date=None, today=TODAY)

    assert set(starting_balances.items) == {stranger, OWNER}


async def test_invalid_date_saves_nothing(
    uow: FakeStartingBalanceUnitOfWork, starting_balances: InMemoryStartingBalanceRepo
) -> None:
    """Недопустимая дата — ошибка, ничего не сохраняется."""
    with pytest.raises(InvalidBalanceDateError):
        await CreateStartingBalanceCommandHandler(uow).handle(
            user_uid=OWNER, amount=100, balance_date=date(2026, 3, 16), today=TODAY
        )

    assert starting_balances.items == {}
    assert not uow.committed
