from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, cast, extract, func, select

from apps.modules.budget_structure.domain import BudgetCategory, BudgetStructure
from apps.modules.category import CategoryORM
from apps.modules.transaction import TransactionORM
from apps.shared.db.base_query import BaseQueries

if TYPE_CHECKING:
    from datetime import date

    from apps.shared import apps_types


class GetBudgetStructure(BaseQueries):
    """Запрос таблицы «Структура бюджета»."""

    async def execute(
        self,
        user_uid: apps_types.UserUID,
        year: int,
        category_type: apps_types.TransactionType,
        today: date,
    ) -> BudgetStructure:
        """
        Получить факт по статьям пользователя выбранного типа за каждый месяц года.

        Args:
            user_uid: UID пользователя.
            year: Год таблицы.
            category_type: Тип статей.
            today: Текущая дата: по ней месяцы делятся на наступившие и будущие.
        """
        # NOTE(FM-27): статьи и факты читаются двумя запросами в READ COMMITTED — статья, изменённая между ними,
        # даст на один ответ несогласованную строку. Для отчёта это допустимо; если станет важно — один запрос
        # с LEFT JOIN или транзакция REPEATABLE READ.
        # TODO(FM-27): факты будущих месяцев домен отбрасывает — для будущего года запрос можно не выполнять,
        # для текущего ограничить верхнюю границу началом следующего месяца.
        categories = await self._get_categories(user_uid, category_type)
        facts = await self._get_month_facts(user_uid, year, category_type)
        return BudgetStructure.build(
            year=year,
            category_type=category_type,
            today=today,
            categories=categories,
            facts=facts,
        )

    async def _get_categories(
        self,
        user_uid: apps_types.UserUID,
        category_type: apps_types.TransactionType,
    ) -> list[BudgetCategory]:
        """
        Все статьи пользователя выбранного типа, по названию.

        Args:
            user_uid: UID пользователя.
            category_type: Тип статей.
        """
        stmt = (
            select(CategoryORM.uid, CategoryORM.name, CategoryORM.money_plan)
            .where(
                CategoryORM.user_uid == user_uid,
                CategoryORM.category_type == category_type,
            )
            # UID — для стабильного порядка статей с одинаковым названием.
            .order_by(CategoryORM.name, CategoryORM.uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return [BudgetCategory(uid=row.uid, name=row.name, money_plan=row.money_plan) for row in rows]

    async def _get_month_facts(
        self,
        user_uid: apps_types.UserUID,
        year: int,
        category_type: apps_types.TransactionType,
    ) -> dict[tuple[apps_types.CategoryUID, int], apps_types.MoneyTotal]:
        """
        Суммы транзакций пользователя по (статья, месяц) за год; пары без транзакций в ответ не попадают.

        Args:
            user_uid: UID пользователя.
            year: Год.
            category_type: Тип статей.
        """
        month = cast(extract("month", TransactionORM.transaction_date), Integer).label("month")
        # Отдельная сумма не больше int32, но сумма за месяц может его превысить — считаем в BIGINT.
        money_total = func.sum(cast(TransactionORM.money_sum, BigInteger), type_=BigInteger).label("money_total")
        stmt = (
            select(TransactionORM.category_uid, month, money_total)
            .join(CategoryORM, CategoryORM.uid == TransactionORM.category_uid)
            .where(
                TransactionORM.user_uid == user_uid,
                CategoryORM.user_uid == user_uid,
                # NOTE(FM-27): факт отбирается по типу статьи, тип самой транзакции не сверяется. Пока создание
                # транзакции не проверяет совпадение типов (FM-5, `FM-400202`), а тип статьи с транзакциями можно
                # сменить (FM-4), чужой по типу транзакции попадёт в таблицу этого типа.
                CategoryORM.category_type == category_type,
                # Полуинтервал [1 января; 1 января следующего года), а не extract по году — чтобы индекс по дате
                # мог применяться.
                # TODO(FM-27): индекса на `transactions (user_uid, transaction_date)` пока нет — запрос сканирует
                # таблицу транзакций всех пользователей; добавить миграцией отдельной задачей.
                TransactionORM.transaction_date >= datetime(year, 1, 1),  # noqa: DTZ001 — даты транзакций без пояса
                TransactionORM.transaction_date < datetime(year + 1, 1, 1),  # noqa: DTZ001
            )
            .group_by(TransactionORM.category_uid, month)
        )
        rows = (await self._session.execute(stmt)).all()
        return {(row.category_uid, row.month): int(row.money_total) for row in rows}
