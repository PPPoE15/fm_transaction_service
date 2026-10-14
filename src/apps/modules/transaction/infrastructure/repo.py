from sqlalchemy import func, select, text

from apps.modules.transaction.application.ports import AbstractTransactionRepo
from apps.modules.transaction.domain import Transaction
from apps.modules.transaction.infrastructure import orm
from apps.shared import apps_types
from apps.shared.db.base_repo import BaseSqlAlchemyRepo

from . import builders

# Пространство ключей advisory-блокировок транзакций (у статей — 41): первый ключ `pg_advisory_xact_lock(int, int)`,
# второй — хеш UID пользователя. Совпадение хешей двух пользователей лишь сериализует их создания транзакций.
_USER_TRANSACTIONS_LOCK_NAMESPACE = 52


class Repo(AbstractTransactionRepo, BaseSqlAlchemyRepo):
    """Репозиторий транзакций."""

    async def create(self, transaction: Transaction) -> None:
        orm_transaction = builders.build_orm(transaction)
        self._session.add(orm_transaction)

    async def count_by_user_for_update(self, user_uid: apps_types.UserUID) -> int:
        # Advisory-блокировка, а не `SELECT … FOR UPDATE`: блокировка строк не мешает вставке новых (и у пользователя
        # без транзакций блокировать нечего). Снимается сама на commit/rollback.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:user_uid))"),
            {"namespace": _USER_TRANSACTIONS_LOCK_NAMESPACE, "user_uid": str(user_uid)},
        )
        # TODO(FM-33): индекса по `user_uid` нет — подсчёт сканирует таблицу транзакций всех пользователей при каждом
        # создании. Индекс `(user_uid, transaction_date)` из FM-33 покроет и этот запрос.
        stmt = select(func.count()).select_from(orm.Transaction).where(orm.Transaction.user_uid == user_uid)
        return (await self._session.scalars(stmt)).one()

    async def update(self, transaction_agg: Transaction) -> None:
        orm_transactions = builders.build_orm(transaction_agg=transaction_agg)
        await self._session.merge(orm_transactions)

    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> list[Transaction] | None:
        stmt = select(orm.Transaction).where(
            orm.Transaction.uid == user_uid,
        )
        transactions = (await self._session.scalars(stmt)).all()
        return builders.build_list(transactions)

    async def delete(self, transaction_uid: apps_types.TransactionUID) -> None:
        transaction = await self._session.get(orm.Transaction, transaction_uid)
        await self._session.delete(transaction)

    async def get_by_uid(self, transaction_uid: apps_types.TransactionUID) -> Transaction | None:
        transaction = await self._session.get(orm.Transaction, transaction_uid)
        return builders.build(transaction) if transaction else None
