from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps import apps_types, db_models
from apps.web.app.aggregators.models.transaction import Transaction
from apps.web.app.aggregators.models.user.user_transactions import UserTransactions
from apps.web.app.infrastructure.db.repos.base import BaseSqlAlchemyRepo

from . import builders
from .interface import AbstractTransactionRepo


class TransactionRepo(AbstractTransactionRepo, BaseSqlAlchemyRepo):
    """Репозиторий для объекта пользователя с данными о транзакциях."""

    async def update(self, user_transactions_agg: UserTransactions) -> None:
        orm_transactions = builders.build_orm(transactions_agg=user_transactions_agg)
        await self._session.merge(orm_transactions)

    async def delete(self, transaction_agg: Transaction) -> None:
        orm_transaction = await self._session.get(db_models.Transaction, transaction_agg.uid)
        await self._session.delete(orm_transaction)

    async def get_by_user_transaction_uid(
        self,
        user_uid: apps_types.UserUID,
        transaction_uid: apps_types.TransactionUID,
    ) -> Transaction | None:
        stmt = (
            select(db_models.Transaction)
            .where(
                db_models.Transaction.user_uid == user_uid,
                db_models.Transaction.uid == transaction_uid,
            )
        )
        orm_user_transactions = await self._session.scalar(stmt)
        return builders.build_agg(orm_user_transactions).transactions[0] if orm_user_transactions else None
