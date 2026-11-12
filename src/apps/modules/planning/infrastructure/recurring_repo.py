"""Адаптер хранения серий и позиций расписания."""

from uuid import UUID

from sqlalchemy import delete, select, update

from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.recurring import Position, Series
from apps.modules.planning.infrastructure import builders
from apps.modules.planning.infrastructure.orm import PlannedTransaction, RecurringOccurrence, RecurringOperation
from apps.shared.db.base_repo import BaseSqlAlchemyRepo


class RecurringRepo(BaseSqlAlchemyRepo):
    """Читает и записывает позиции в общей транзакции планирования."""

    async def get(self, user_uid: UUID, uid: UUID) -> Series | None:
        """Получить доступную серию владельца под блокировкой."""
        row = await self._session.scalar(
            select(RecurringOperation)
            .where(
                RecurringOperation.uid == uid,
                RecurringOperation.user_uid == user_uid,
                RecurringOperation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return Series.model_validate(row, from_attributes=True) if row is not None else None

    async def has_source(self, user_uid: UUID, source_uid: UUID) -> bool:
        """Проверить наличие неудалённой серии, созданной из плана."""
        stmt = select(RecurringOperation.uid).where(
            RecurringOperation.user_uid == user_uid,
            RecurringOperation.source_plan_uid == source_uid,
            RecurringOperation.deleted_at.is_(None),
        )
        return await self._session.scalar(stmt) is not None

    async def save(self, series: Series, *, new: bool = False) -> None:
        """Записать параметры серии, сохранив ссылочную целостность при создании позиций."""
        fields = series.model_dump(mode="json", include={"frequency"})
        values = series.model_dump(exclude={"uid", "frequency"}) | fields
        if new:
            self._session.add(RecurringOperation(uid=series.uid, **values))
        else:
            await self._session.execute(
                update(RecurringOperation).where(RecurringOperation.uid == series.uid).values(**values)
            )
        await self._session.flush()

    async def positions(self, uid: UUID) -> list[Position]:
        """Прочитать все занятые позиции, включая удалённые платежи."""
        rows = await self._session.scalars(select(RecurringOccurrence).where(RecurringOccurrence.operation_uid == uid))
        return [Position.model_validate(row, from_attributes=True) for row in rows]

    async def payments_for_update(self, uid: UUID) -> list[tuple[Position, Plan]]:
        """Заблокировать существующие платежи серии в порядке UID."""
        stmt = (
            select(RecurringOccurrence, PlannedTransaction)
            .join(PlannedTransaction, PlannedTransaction.uid == RecurringOccurrence.plan_uid)
            .where(RecurringOccurrence.operation_uid == uid)
            .order_by(PlannedTransaction.uid)
            .with_for_update(of=PlannedTransaction)
        )
        return [
            (Position.model_validate(position, from_attributes=True), builders.build(plan))
            for position, plan in (await self._session.execute(stmt)).tuples()
        ]

    async def add_positions(self, positions: list[Position]) -> None:
        """Вставить позиции после записи связанных планов."""
        await self._session.flush()
        self._session.add_all([RecurringOccurrence(**position.model_dump()) for position in positions])
        await self._session.flush()

    async def remove_position(self, position: Position) -> None:
        """Освободить дату заменяемого платежа при пересчёте."""
        await self._session.execute(
            delete(RecurringOccurrence).where(
                RecurringOccurrence.operation_uid == position.operation_uid,
                RecurringOccurrence.scheduled_date == position.scheduled_date,
            )
        )

    async def mark_exception(self, plan_uid: UUID) -> None:
        """Сохранить отметку ручного изменения у связанного платежа."""
        await self._session.execute(
            update(RecurringOccurrence).where(RecurringOccurrence.plan_uid == plan_uid).values(is_exception=True)
        )

    async def link(self, plan_uid: UUID) -> tuple[Position, Series] | None:
        """Получить метаданные связи, в том числе с удалённой серией."""
        stmt = (
            select(RecurringOccurrence, RecurringOperation)
            .join(RecurringOperation, RecurringOperation.uid == RecurringOccurrence.operation_uid)
            .where(RecurringOccurrence.plan_uid == plan_uid)
        )
        row = (await self._session.execute(stmt)).tuples().one_or_none()
        if row is None:
            return None
        position, series = row
        return Position.model_validate(position, from_attributes=True), Series.model_validate(
            series, from_attributes=True
        )
