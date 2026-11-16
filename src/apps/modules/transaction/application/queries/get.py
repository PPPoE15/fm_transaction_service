from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Select, func, select, true
from sqlalchemy.orm import selectinload

from apps.modules.category import CategoryORM
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
        filtered = self._apply_filters(
            select(
                orm.Transaction.uid,
                orm.Transaction.transaction_date,
                orm.Transaction.money_sum,
                orm.Transaction.transaction_type,
                orm.Transaction.description,
                orm.Transaction.version,
                CategoryORM.uid.label("category_uid"),
                CategoryORM.name.label("category_name"),
            )
            .join(CategoryORM, orm.Transaction.category_uid == CategoryORM.uid)
            .where(orm.Transaction.user_uid == user_uid),
            filter_params,
        ).cte("filtered_transactions")
        count = select(func.count().label("total")).select_from(filtered).cte("transaction_count")
        date_order = (
            filtered.c.transaction_date.desc()
            if filter_params.sort == "-transaction_date"
            else filtered.c.transaction_date.asc()
        )
        page_stmt = select(filtered).order_by(date_order, filtered.c.uid.asc())
        page = self._apply_pagination(page_stmt, page_params).cte("transaction_page")
        outer_order = (
            page.c.transaction_date.desc()
            if filter_params.sort == "-transaction_date"
            else page.c.transaction_date.asc()
        )
        # LEFT JOIN сохраняет total при пустой странице; всё читается одним MVCC-снимком.
        stmt = select(count.c.total, page).select_from(count.outerjoin(page, true()))
        rows = (await self._session.execute(stmt.order_by(outer_order, page.c.uid.asc()))).mappings().all()
        content = [
            schemas.TransactionSchema(
                uid=row["uid"],
                transaction_date=row["transaction_date"],
                money_sum=row["money_sum"],
                transaction_type=row["transaction_type"],
                description=row["description"],
                version=row["version"],
                category=schemas.CategoryRef(uid=row["category_uid"], name=row["category_name"]),
            )
            for row in rows
            if row["uid"] is not None
        ]
        return content, rows[0]["total"]

    async def get_transaction(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
    ) -> schemas.TransactionSchema | None:
        """
        Получить транзакцию пользователя.

        Args:
            user_uid: UID пользователя.
            transaction_uid: UID транзакции.

        Returns:
            Транзакция; `None` — если её нет или она принадлежит другому пользователю.
        """
        stmt = (
            select(orm.Transaction)
            .options(selectinload(orm.Transaction.category))
            .where(orm.Transaction.uid == transaction_uid, orm.Transaction.user_uid == user_uid)
        )
        orm_transaction = (await self._session.scalars(stmt)).one_or_none()
        return self.build(orm_transaction) if orm_transaction else None

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
                CategoryORM.name.icontains(filter_params.category, autoescape=True),
            )
        if filter_params.category_uid is not None:
            stmt = stmt.filter(orm.Transaction.category_uid == filter_params.category_uid)
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
        Преобразовать orm-модели к схеме TransactionSchema.

        Args:
            orm_transactions: Orm-модели транзакций.

        Returns:
            Список транзакций.
        """
        return [cls.build(transaction) for transaction in orm_transactions]

    @staticmethod
    def build(transaction: orm.Transaction) -> schemas.TransactionSchema:
        """
        Преобразовать orm-модель к схеме TransactionSchema.

        Args:
            transaction: Orm-модель транзакции с загруженной статьёй.
        """
        return schemas.TransactionSchema(
            version=transaction.version,
            uid=transaction.uid,
            transaction_date=transaction.transaction_date,
            category=schemas.CategoryRef(uid=transaction.category.uid, name=transaction.category.name),
            money_sum=transaction.money_sum,
            transaction_type=transaction.transaction_type,
            description=transaction.description,
        )
