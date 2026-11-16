"""Постраничное чтение регулярных операций для продления горизонта."""

from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.modules.planning.domain.schedule import generation_horizon
from apps.modules.planning.infrastructure.orm import RegularOperation

BATCH_SIZE = 200


async def generation_candidates(
    sessions: async_sessionmaker[AsyncSession], today: date
) -> AsyncIterator[tuple[UUID, UUID]]:
    """Перечислить владельцев и UID операций с необработанными датами в горизонте."""
    horizon = generation_horizon(today)
    stmt = (
        select(RegularOperation.user_uid, RegularOperation.uid)
        .where(
            RegularOperation.deleted_at.is_(None),
            RegularOperation.first_date <= horizon,
            or_(RegularOperation.generated_through.is_(None), RegularOperation.generated_through < horizon),
            or_(
                RegularOperation.end_date.is_(None),
                RegularOperation.generated_through.is_(None),
                RegularOperation.generated_through < RegularOperation.end_date,
            ),
        )
        .order_by(RegularOperation.uid)
        .limit(BATCH_SIZE)
    )
    page = stmt
    while True:
        async with sessions() as session:
            rows = (await session.execute(page)).tuples().all()
        if not rows:
            return
        for owner, uid in rows:
            yield owner, uid
        page = stmt.where(RegularOperation.uid > uid)
