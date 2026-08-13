from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Select, func, select

from apps import apps_types, db_models
from apps.web.core.base_query import BaseQueries

from . import schemas

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apps.utils.schemas import PageParams


class ListCategories(BaseQueries):
    """Класс с запросами для списка категорий"""

    async def execute(
        self,
        user_uid: apps_types.UserUID,
        page_params: PageParams,
        filter_params: schemas.CategoryFilters,
    ) -> tuple[list[schemas.CategorySchema], int]:
        """
        Получить список категорий пользователя с учетом пагинации и фильтрации.

        Args:
            user_uid: UID пользователя.
            page_params: Параметры пагинации.
            filter_params: Параметры фильтра.

        Returns:
            Список наборов возможностей; Общее количество записей в БД.
        """
        base_stmt = select(db_models.Category).where(db_models.Category.user_uid == user_uid)
        select_stmt = self._apply_filters(base_stmt, filter_params)

        count_stmt = select_stmt.with_only_columns(func.count(), maintain_column_froms=True)
        select_stmt = self._apply_pagination(select_stmt, page_params)

        orm_transactions = (await self._session.scalars(select_stmt)).all()
        total = (await self._session.scalars(count_stmt)).one()
        return self.build_list(orm_transactions), total

    @staticmethod
    def _apply_filters(
        stmt: Select,
        filter_params: schemas.CategoryFilters,
    ) -> Select:
        """
        Применить фильтры к запросу.

        Args:
            stmt: Запрос.
            filter_params: Параметры фильтрации.
        """
        if filter_params.name:
            stmt = stmt.filter(
                db_models.Category.name == filter_params.name,
            )
        if filter_params.category_type:
            stmt = stmt.filter(
                db_models.Category.category_type == filter_params.category_type,
            )
        if filter_params.below_money_sum:
            stmt = stmt.filter(
                db_models.Category.money_plan <= filter_params.below_money_sum,
            )
        if filter_params.above_money_sum:
            stmt = stmt.filter(
                db_models.Category.money_plan >= filter_params.above_money_sum,
            )
        return stmt

    @classmethod
    def build_list(
        cls,
        orm_categories: Sequence[db_models.Category],
    ) -> list[schemas.CategorySchema]:
        """
        Преобразовать orm-модель к схеме TransactionSchema.

        Args:
            orm_categories: Orm-модели категорий.

        Returns:
            Список категорий.
        """
        return [
            schemas.CategorySchema(
                uid=category.uid,
                name=category.name,
                money_plan=category.money_plan,
                category_type=category.category_type,
                description=category.description,
            )
            for category in orm_categories
        ]
