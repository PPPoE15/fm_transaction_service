"""Фейки модуля статей: хранилище в памяти и единица работы поверх него."""

from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.modules.category.application.uow import AbstractCategoryUnitOfWork
from apps.modules.category.domain import Category
from apps.shared import apps_types
from tests.modules.fakes import FakeUnitOfWorkMixin


class InMemoryCategoryRepo(AbstractCategoryRepo):
    """Репозиторий статей в памяти."""

    def __init__(self) -> None:
        """Пустое хранилище."""
        self.items: dict[apps_types.CategoryUID, Category] = {}
        self.locked_users: list[apps_types.UserUID] = []
        # Статьи, по которым есть транзакции: транзакции живут в другом модуле, фейку хватает их наличия
        self.with_transactions: set[apps_types.CategoryUID] = set()
        # Порядок обращений, важных для гонок: блокировка строки статьи должна идти до проверки транзакций
        self.calls: list[str] = []

    async def get_all_for_import(
        self,
        user_uid: apps_types.UserUID,
        category_type: apps_types.TransactionType,
    ) -> list[Category]:
        """Вернуть копии категорий пользователя нужного типа; блокировки проверяются на Postgres."""
        return [
            category.model_copy()
            for category in self.items.values()
            if category.user_uid == user_uid and category.category_type == category_type
        ]

    async def create(self, category: Category) -> None:
        self.items[category.uid] = category.model_copy()

    async def lock_user_categories(self, user_uid: apps_types.UserUID) -> None:
        self.locked_users.append(user_uid)

    async def count_by_user(self, user_uid: apps_types.UserUID) -> int:
        return sum(1 for category in self.items.values() if category.user_uid == user_uid)

    async def get_by_name(
        self,
        user_uid: apps_types.UserUID,
        name: apps_types.CategoryName,
        category_type: apps_types.TransactionType,
    ) -> Category | None:
        for category in self.items.values():
            if (category.user_uid, category.name, category.category_type) == (user_uid, name, category_type):
                return category.model_copy()
        return None

    async def lock_category(self, category_uid: apps_types.CategoryUID) -> None:
        self.calls.append(f"lock_category {category_uid}")

    async def has_transactions(self, category_uid: apps_types.CategoryUID) -> bool:
        self.calls.append(f"has_transactions {category_uid}")
        return category_uid in self.with_transactions

    async def update(self, category_agg: Category) -> None:
        self.items[category_agg.uid] = category_agg.model_copy()

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        self.items.pop(category_uid)

    async def get_by_uid_for_key_share(self, category_uid: apps_types.CategoryUID) -> Category | None:
        return await self.get_by_uid(category_uid)

    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        category = self.items.get(category_uid)
        return category.model_copy() if category else None


class FakeCategoryUnitOfWork(FakeUnitOfWorkMixin, AbstractCategoryUnitOfWork):
    """Единица работы модуля статей в памяти."""

    def __init__(self, categories: InMemoryCategoryRepo) -> None:
        """
        Единица работы поверх хранилища статей.

        Args:
            categories: Хранилище статей.
        """
        self.repo = categories
