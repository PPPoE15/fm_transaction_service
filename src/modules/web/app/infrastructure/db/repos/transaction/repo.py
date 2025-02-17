from sqlalchemy import select
from sqlalchemy.orm import selectinload

from modules import db_models, types
from modules.web.app.aggregators.models.user.user_transactions import UserTransactions
from modules.web.app.infrastructure.db.repos.base import BaseSqlAlchemyRepo

from . import builders
from .interface import AbstractUserTransactionRepo


class UserTransactionRepo(AbstractUserTransactionRepo, BaseSqlAlchemyRepo):
    """Репозиторий для объекта пользователя с данными о транзакциях."""

    async def create(self, user_transaction: UserTransactions) -> None:
        orm_transaction = builders.build_orm(user_transaction)
        self._session.add(orm_transaction)

    async def update(self, user_transactions_agg: UserTransactions) -> None:
        orm_transactions = builders.build_orm(user_transactions_agg=user_transactions_agg)
        await self._session.merge(orm_transactions)

    async def get_by_user_uid(self, user_uid: types.UserUID) -> UserTransactions | None:
        stmt = (
            select(db_models.User)
            .options(selectinload(db_models.User.transactions))
            .where(
                db_models.User.uid == user_uid,
            )
        )
        orm_user_transactions = await self._session.scalar(stmt)
        return builders.build_agg(orm_user_transactions) if orm_user_transactions else None
