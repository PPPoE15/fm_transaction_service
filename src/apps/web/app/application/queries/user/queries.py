from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import Select, exists, func, select

from apps import db_models as orm_models
from apps.web.app.application.queries.base import BaseQueries

from . import schemas

if TYPE_CHECKING:
    from apps.utils.schemas import PageParams


class TransactionQueries(BaseQueries):
    """Класс с запросами для сущности пользователя"""

    async def get_transactions(
        self,
        page_params: PageParams,
        filter_params: schemas.TransactionFilters,
    ) -> tuple[list[schemas.TransactionSchema], int]:
        """
        Получить список транзакций пользователя с учетом пагинации и фильтрации.

        Args:
            page_params: Параметры пагинации.
            filter_params: Параметры фильтра.

        Returns:
            Список наборов возможностей; Общее количество записей в БД.
        """
        base_stmt = select(orm_models.Transaction)
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
            stmt = stmt.filter(exists().where(orm_models.Transaction.category == filter_params.category))
        if filter_params.transaction_type:
            stmt = stmt.filter(
                exists().where(orm_models.Transaction.transaction_type == filter_params.transaction_type)
            )
        return stmt

    @classmethod
    def build_list(
        cls,
        orm_transactions: Sequence[orm_models.Transaction],
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
                transaction_date=transaction.transaction_date,
                category=transaction.category,
                money_sum=transaction.money_sum,
                transaction_type=transaction.transaction_type,
                description=transaction.description,
            )
            for transaction in orm_transactions
        ]
