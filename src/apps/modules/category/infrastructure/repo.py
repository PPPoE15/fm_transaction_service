from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.modules.category.domain import Category
from apps.modules.category.infrastructure import orm
from apps.shared import apps_types
from apps.shared.db.base_repo import BaseSqlAlchemyRepo

from . import builders


class Repo(AbstractCategoryRepo, BaseSqlAlchemyRepo):
    """Репозиторий категорий."""

    async def create(self, category: Category) -> None:
        orm_category = builders.build_orm(category)
        self._session.add(orm_category)

    async def update(self, category_agg: Category) -> None:
        orm_category = builders.build_orm(category_agg=category_agg)
        await self._session.merge(orm_category)

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        category = await self._session.get(orm.Category, category_uid)
        await self._session.delete(category)

    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        category = await self._session.get(orm.Category, category_uid)
        return builders.build(category) if category else None
