from uuid import uuid4

import pytest

from apps.modules.category.application.commands import (
    CreateCommandHandler,
    DeleteCommandHandler,
    UpdateCommandHandler,
)
from apps.modules.category.application.exceptions import (
    CategoryAlreadyExistsError,
    CategoryLimitExceededError,
    CategoryNotFoundError,
)
from apps.modules.category.domain import MAX_CATEGORIES_PER_USER, Category
from apps.shared import apps_types
from tests.modules.category.fakes import FakeCategoryUnitOfWork, InMemoryCategoryRepo

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
    """Статья создаётся от имени пользователя из токена; команда возвращает созданную статью."""
    category = await CreateCommandHandler(uow).handle(
        name="Зарплата", user_uid=OWNER, money_plan=100_000, category_type=INCOME, description="Основная"
    )

    [created] = categories.items.values()
    assert created == category
    assert (created.user_uid, created.name, created.money_plan, created.category_type, created.description) == (
        OWNER,
        "Зарплата",
        100_000,
        INCOME,
        "Основная",
    )
    assert uow.committed


@pytest.mark.parametrize("money_plan", [None, 0], ids=["без плана", "план 0"])
async def test_create_without_plan_or_with_zero_plan(
    uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo, money_plan: int | None
) -> None:
    """План необязателен: `None` — плана нет, `0` — нулевой план; они не подменяют друг друга."""
    await CreateCommandHandler(uow).handle(
        name="Подарки", user_uid=OWNER, money_plan=money_plan, category_type=OUTCOME, description=None
    )

    [created] = categories.items.values()
    assert created.money_plan == money_plan


async def test_create_duplicate_name_and_type_is_conflict(
    uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo
) -> None:
    """У пользователя уже есть статья с таким названием и типом — ошибка `FM-409101`, новая не создаётся."""
    existing = await _add_category(categories, OWNER)

    with pytest.raises(CategoryAlreadyExistsError) as exc_info:
        await CreateCommandHandler(uow).handle(
            name=existing.name, user_uid=OWNER, money_plan=None, category_type=OUTCOME, description=None
        )

    assert exc_info.value.code == "FM-409101"
    assert list(categories.items) == [existing.uid]
    assert not uow.committed


@pytest.mark.parametrize(
    ("user_uid", "category_type"),
    [(OWNER, INCOME), (STRANGER, OUTCOME)],
    ids=["то же название, другой тип", "то же название у другого пользователя"],
)
async def test_create_same_name_with_other_type_or_user(
    uow: FakeCategoryUnitOfWork,
    categories: InMemoryCategoryRepo,
    user_uid: apps_types.UserUID,
    category_type: apps_types.TransactionType,
) -> None:
    """Дубликатом считается только совпадение названия и типа у одного пользователя."""
    existing = await _add_category(categories, OWNER)

    await CreateCommandHandler(uow).handle(
        name=existing.name, user_uid=user_uid, money_plan=None, category_type=category_type, description=None
    )

    assert {(item.user_uid, item.category_type) for item in categories.items.values()} == {
        (OWNER, OUTCOME),
        (user_uid, category_type),
    }


async def _fill(categories: InMemoryCategoryRepo, user_uid: apps_types.UserUID, count: int) -> None:
    for number in range(count):
        await categories.create(
            Category.create(
                name=f"Статья {number}", user_uid=user_uid, money_plan=None, category_type=OUTCOME, description=None
            )
        )


async def test_create_over_limit_is_conflict(uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo) -> None:
    """Лимит — 100 статей на пользователя: сотая создаётся, сто первая — ошибка `FM-409103`."""
    await _fill(categories, OWNER, MAX_CATEGORIES_PER_USER - 1)
    await CreateCommandHandler(uow).handle(
        name="Сотая", user_uid=OWNER, money_plan=None, category_type=INCOME, description=None
    )

    with pytest.raises(CategoryLimitExceededError) as exc_info:
        await CreateCommandHandler(uow).handle(
            name="Лишняя", user_uid=OWNER, money_plan=None, category_type=INCOME, description=None
        )

    assert exc_info.value.code == "FM-409103"
    assert len(categories.items) == MAX_CATEGORIES_PER_USER


async def test_limit_does_not_count_other_users(uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo) -> None:
    """Статьи другого пользователя в лимит не входят."""
    await _fill(categories, STRANGER, MAX_CATEGORIES_PER_USER)

    await CreateCommandHandler(uow).handle(
        name="Первая", user_uid=OWNER, money_plan=None, category_type=INCOME, description=None
    )

    assert len(categories.items) == MAX_CATEGORIES_PER_USER + 1


async def test_create_locks_user_categories_before_checks(
    uow: FakeCategoryUnitOfWork, categories: InMemoryCategoryRepo
) -> None:
    """Проверки дубликата и лимита идут под блокировкой статей пользователя (иначе гонка двух запросов)."""
    await CreateCommandHandler(uow).handle(
        name="Зарплата", user_uid=OWNER, money_plan=None, category_type=INCOME, description=None
    )

    assert categories.locked_users == [OWNER]


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
