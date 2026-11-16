"""Выборка операций владельца настоящим SQL-репозиторием."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.category import CategoryORM
from apps.modules.transaction import TransactionORM
from apps.modules.transaction.infrastructure.repo import Repo
from apps.shared.db.session import async_session_factory


@pytest.mark.db
async def test_get_by_user_uid_isolates_owner(db_engine: AsyncEngine) -> None:
    """UID операции, совпавший с UID другого пользователя, не раскрывает чужую операцию."""
    owner, stranger, empty_owner = uuid4(), uuid4(), uuid4()
    own_ids = {uuid4(), uuid4()}
    async with async_session_factory() as session:
        for user_uid, operation_ids in ((owner, own_ids), (stranger, {owner, empty_owner})):
            category_uid = uuid4()
            session.add(CategoryORM(uid=category_uid, user_uid=user_uid, name="Еда", category_type="outcome"))
            await session.flush()
            session.add_all(
                TransactionORM(
                    uid=uid,
                    user_uid=user_uid,
                    category_uid=category_uid,
                    transaction_date=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                    money_sum=100,
                    transaction_type="outcome",
                )
                for uid in operation_ids
            )
        await session.commit()
    async with async_session_factory() as session:
        repo = Repo(session)
        own = await repo.get_by_user_uid(owner)
        assert own is not None
        assert {item.uid for item in own} == own_ids
        assert all(item.user_uid == owner for item in own)
        assert await repo.get_by_user_uid(empty_owner) == []
        foreign = await repo.get_by_user_uid(stranger)
        assert foreign is not None
        assert {item.uid for item in foreign} == {owner, empty_owner}
