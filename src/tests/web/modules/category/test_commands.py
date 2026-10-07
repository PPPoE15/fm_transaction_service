from uuid import uuid4

import pytest

from apps import apps_types
from apps.web.modules.category.aggregators import Category
from apps.web.modules.category.application.commands import (
    CreateCommandHandler,
    DeleteCommandHandler,
    UpdateCommandHandler,
)
from apps.web.modules.category.application.commands.exceptions import CategoryNotFoundError
from tests.fakes import FakeCategoryUnitOfWork, InMemoryCategoryRepo

OWNER = uuid4()
STRANGER = uuid4()
INCOME = apps_types.TransactionType.INCOME
OUTCOME = apps_types.TransactionType.OUTCOME


@pytest.fixture
def categories() -> InMemoryCategoryRepo:
    """Хранилище статей."""
    return InMemoryCategoryRepo()


@pytest.fixture
def uow(categories: InMemoryCategoryRepo) -> FakeCategoryUnitOfWork:
    """Единица работы модуля статей."""
    return FakeCategoryUnitOfWork(categories)


async def _add_category(categories: InMemoryCategoryRepo, user_uid: apps_types.UserUID) -> Category:
    category = Category.create(name="Еда", user_uid=user_uid, money_plan=1000, category_type=OUTCOME, description=None)
    await categories.create(category)
    return category


async def test_create_belongs_to_current_user(uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo) -> None:
    """Статья создаётся от имени пользователя из токена."""
    await CreateCommandHandler(uow).handle(
        name="Зарплата", user_uid=OWNER, money_plan=100_000, category_type=INCOME, description=None
    )

    [created] = categories.items.values()
    assert created.user_uid == OWNER


async def test_update_own_category(uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo) -> None:
    """Свою статью можно изменить."""
    category = await _add_category(categories, OWNER)

    await UpdateCommandHandler(uow).handle(
        user_uid=OWNER,
        category_uid=category.uid,
        name="Продукты",
        money_plan=2000,
        category_type=OUTCOME,
        description="Магазин у дома",
    )

    updated = categories.items[category.uid]
    assert (updated.name, updated.money_plan, updated.description) == ("Продукты", 2000, "Магазин у дома")
    assert updated.user_uid == OWNER
    assert uow.committed


@pytest.mark.parametrize("category_owner", [STRANGER, None], ids=["чужая статья", "несуществующая статья"])
async def test_update_foreign_or_missing_category_is_not_found(
    uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo, category_owner: apps_types.UserUID | None
) -> None:
    """Чужую статью изменить нельзя, ответ — как на несуществующую; данные не меняются."""
    foreign = await _add_category(categories, category_owner) if category_owner else None
    category_uid = foreign.uid if foreign else uuid4()

    with pytest.raises(CategoryNotFoundError) as exc_info:
        await UpdateCommandHandler(uow).handle(
            user_uid=OWNER,
            category_uid=category_uid,
            name="Взлом",
            money_plan=0,
            category_type=INCOME,
            description=None,
        )

    assert "не найдена" in exc_info.value.msg

    if foreign:
        assert categories.items[foreign.uid] == foreign
    assert not uow.committed


async def test_delete_own_category(uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo) -> None:
    """Свою статью можно удалить."""
    category = await _add_category(categories, OWNER)

    await DeleteCommandHandler(uow).handle(user_uid=OWNER, category_uid=category.uid)

    assert category.uid not in categories.items
    assert uow.committed


@pytest.mark.parametrize("category_owner", [STRANGER, None], ids=["чужая статья", "несуществующая статья"])
async def test_delete_foreign_or_missing_category_is_not_found(
    uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo, category_owner: apps_types.UserUID | None
) -> None:
    """Чужую статью удалить нельзя, ответ — как на несуществующую."""
    foreign = await _add_category(categories, category_owner) if category_owner else None

    with pytest.raises(CategoryNotFoundError) as exc_info:
        await DeleteCommandHandler(uow).handle(user_uid=OWNER, category_uid=foreign.uid if foreign else uuid4())

    assert "не найдена" in exc_info.value.msg

    if foreign:
        assert foreign.uid in categories.items
    assert not uow.committed
