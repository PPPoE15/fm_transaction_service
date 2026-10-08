from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from apps.modules.transaction.infrastructure import orm
from apps.shared.db.base_query import BaseQueries

from . import schemas

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apps.shared import apps_types
    from apps.shared.schemas import PageParams


class TransactionQueries(BaseQueries):
    """Класс с запросами для сущности пользователя"""

    async def get_transactions(
        self,
        user_uid: apps_types.UserUID,
        page_params: PageParams,
        filter_params: schemas.TransactionFilters,
    ) -> tuple[list[schemas.TransactionSchema], int]:
        """
        Получить список транзакций пользователя с учетом пагинации и фильтрации.

        Args:
            user_uid: UID пользователя.
            page_params: Параметры пагинации.
            filter_params: Параметры фильтра.

        Returns:
            Список наборов возможностей; Общее количество записей в БД.
        """
        base_stmt = (
            select(orm.Transaction)
            .options(
                selectinload(orm.Transaction.category),
            )
            .where(orm.Transaction.user_uid == user_uid)
        )
        select_stmt = self._apply_filters(base_stmt, filter_params)

        count_stmt = select_stmt.with_only_columns(func.count(), maintain_column_froms=True)
        select_stmt = self._apply_pagination(select_stmt, page_params)

        orm_transactions = (await self._session.scalars(select_stmt)).all()
        total = (await self._session.scalars(count_stmt)).one()
        return self.build_list(orm_transactions), total

    @staticmethod
    def _apply_filters(
        stmt: Select,
        filter_params: schemas.TransactionFilters,
    ) -> Select:
        """
        Применить фильтры к запросу.

        Args:
            stmt: Запрос.
            filter_params: Параметры фильтрации.
        """
        if filter_params.category:
            stmt = stmt.filter(
                orm.Transaction.category == filter_params.category,
            )
        if filter_params.transaction_type:
            stmt = stmt.filter(
                orm.Transaction.transaction_type == filter_params.transaction_type,
            )
        if filter_params.before:
            stmt = stmt.filter(
                orm.Transaction.transaction_date <= filter_params.before,
            )
        if filter_params.after:
            stmt = stmt.filter(
                orm.Transaction.transaction_date >= filter_params.after,
            )
        return stmt

    @classmethod
    def build_list(
        cls,
        orm_transactions: Sequence[orm.Transaction],
    ) -> list[schemas.TransactionSchema]:
        """
        Преобразовать orm-модель к схеме TransactionSchema.

        Args:
            orm_transactions: Orm-модели транзакций.

        Returns:
            Список транзакций.
        """
        return [
            schemas.TransactionSchema(
                uid=transaction.uid,
                transaction_date=transaction.transaction_date,
                category=transaction.category.name,
                money_sum=transaction.money_sum,
                transaction_type=transaction.transaction_type,
                description=transaction.description,
            )
            for transaction in orm_transactions
        ]
