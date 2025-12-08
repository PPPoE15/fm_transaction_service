from sqlalchemy import select

from apps import apps_types, db_models
from apps.web.app.aggregators.models.transaction import Transaction
from apps.web.app.infrastructure.db.repos.base import BaseSqlAlchemyRepo

from . import builders
from .interface import AbstractTransactionRepo


class TransactionRepo(AbstractTransactionRepo, BaseSqlAlchemyRepo):
    """Репозиторий транзакций."""

    async def create(self, transaction: Transaction) -> None:
        orm_transaction = builders.build_orm(transaction)
        self._session.add(orm_transaction)

    async def update(self, transaction_agg: Transaction) -> None:
        orm_transactions = builders.build_orm(transaction_agg=transaction_agg)
        await self._session.merge(orm_transactions)

    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> list[Transaction] | None:
        stmt = select(db_models.Transaction).where(
            db_models.Transaction.uid == user_uid,
        )
        transactions = (await self._session.scalars(stmt)).all()
        return builders.build_list(transactions)

    async def delete(self, transaction_uid: apps_types.TransactionUID) -> None:
        transaction = await self._session.get(db_models.Transaction, transaction_uid)
        await self._session.delete(transaction)

    async def get_by_uid(self, transaction_uid: apps_types.TransactionUID) -> Transaction | None:
        transaction = await self._session.get(db_models.Transaction, transaction_uid)
        return builders.build(transaction) if transaction else None
