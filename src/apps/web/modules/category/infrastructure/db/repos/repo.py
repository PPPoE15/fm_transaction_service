from sqlalchemy import select

from apps import apps_types, db_models
from apps.web.core.base import BaseSqlAlchemyRepo
from apps.web.modules.category.aggregators.category import Category

from . import builders
from .interface import AbstractCategoryRepo


class Repo(AbstractCategoryRepo, BaseSqlAlchemyRepo):
    """Репозиторий транзакций."""

    async def create(self, category: Category) -> None:
        orm_category = builders.build_orm(category)
        self._session.add(orm_category)

    async def update(self, category_agg: Category) -> None:
        orm_category = builders.build_orm(category_agg=category_agg)
        await self._session.merge(orm_category)

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        category = await self._session.get(db_models.Category, category_uid)
        await self._session.delete(category)

    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        category = await self._session.get(db_models.Category, category_uid)
        return builders.build(category) if category else None
