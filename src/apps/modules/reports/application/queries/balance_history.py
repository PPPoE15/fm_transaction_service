"""Чтение стартового остатка и дневных агрегатов из единого снимка PostgreSQL."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import BigInteger, Date, case, cast, func, select, true

from apps.modules.reports.application.exceptions import StartingBalanceRequiredError
from apps.modules.reports.domain.balance_history import BalanceHistory, build_balance_history
from apps.modules.starting_balance import StartingBalanceORM
from apps.modules.transaction import TransactionORM
from apps.shared import apps_types
from apps.shared.db.base_query import BaseQueries


class GetBalanceHistory(BaseQueries):
    """Запрос дневного остатка пользователя без отдельного чтения стартовой суммы."""

    async def execute(
        self,
        user_uid: apps_types.UserUID,
        date_from: date,
        date_to: date,
        now: datetime,
    ) -> BalanceHistory:
        """
        Прочитать общий остаток и построить ряд для проверенного диапазона.

        Args:
            user_uid: Владелец бюджета из токена.
            date_from: Первый день ряда.
            date_to: Последний день ряда.
            now: Зафиксированный московский момент запроса с часовым поясом.
        """
        day = cast(TransactionORM.transaction_date, Date)
        amount = cast(TransactionORM.money_sum, BigInteger)
        signed_amount = case(
            (TransactionORM.transaction_type == apps_types.TransactionType.INCOME, amount), else_=-amount
        )
        daily = (
            select(day.label("day"), func.sum(signed_amount).label("change"))
            .where(
                TransactionORM.user_uid == user_uid,
                TransactionORM.transaction_date < datetime.combine(date_to + timedelta(days=1), time.min),
                TransactionORM.transaction_date <= now.replace(tzinfo=None),
            )
            .group_by(day)
            .subquery()
        )
        # Один SQL statement обеспечивает общий MVCC-снимок остатка и всех операций даже в READ COMMITTED.
        statement = (
            select(StartingBalanceORM.amount, StartingBalanceORM.balance_date, daily.c.day, daily.c.change)
            .select_from(StartingBalanceORM)
            .outerjoin(daily, true())
            .where(StartingBalanceORM.user_uid == user_uid)
        )
        rows = (await self._session.execute(statement)).all()
        if not rows:
            raise StartingBalanceRequiredError
        return build_balance_history(
            date_from=date_from,
            date_to=date_to,
            balance_date=rows[0].balance_date,
            amount=rows[0].amount,
            daily_changes={row.day: int(row.change) for row in rows if row.day is not None},
        )
