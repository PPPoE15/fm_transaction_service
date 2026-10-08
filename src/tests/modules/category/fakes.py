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

    async def create(self, category: Category) -> None:
        self.items[category.uid] = category.model_copy()

    async def update(self, category_agg: Category) -> None:
        self.items[category_agg.uid] = category_agg.model_copy()

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        self.items.pop(category_uid)

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
