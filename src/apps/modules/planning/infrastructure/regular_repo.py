"""Адаптер хранения регулярных операций и позиций расписания."""

from uuid import UUID

from sqlalchemy import delete, select, update

from apps.modules.planning.application.ports import AbstractRegularTransactionRuleRepo
from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.regular import Position, RegularTransactionRule
from apps.modules.planning.infrastructure import builders
from apps.modules.planning.infrastructure.orm import PlannedTransaction, RegularOccurrence, RegularOperation
from apps.shared.db.base_repo import BaseSqlAlchemyRepo


class RegularTransactionRuleRepo(AbstractRegularTransactionRuleRepo, BaseSqlAlchemyRepo):
    """Читает и записывает позиции в общей транзакции планирования."""

    async def get(self, user_uid: UUID, uid: UUID) -> RegularTransactionRule | None:
        """Получить доступную регулярную операцию владельца под блокировкой."""
        row = await self._session.scalar(
            select(RegularOperation)
            .where(
                RegularOperation.uid == uid,
                RegularOperation.user_uid == user_uid,
                RegularOperation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return RegularTransactionRule.model_validate(row, from_attributes=True) if row is not None else None

    async def has_source(self, user_uid: UUID, source_uid: UUID) -> bool:
        """Проверить наличие неудалённой регулярной операции, созданной из плана."""
        stmt = select(RegularOperation.uid).where(
            RegularOperation.user_uid == user_uid,
            RegularOperation.source_plan_uid == source_uid,
            RegularOperation.deleted_at.is_(None),
        )
        return await self._session.scalar(stmt) is not None

    async def save(self, rule: RegularTransactionRule, *, new: bool = False) -> None:
        """Записать параметры регулярной операции, сохранив ссылочную целостность при создании позиций."""
        fields = rule.model_dump(mode="json", include={"frequency"})
        values = rule.model_dump(exclude={"uid", "frequency"}) | fields
        if new:
            self._session.add(RegularOperation(uid=rule.uid, **values))
        else:
            await self._session.execute(
                update(RegularOperation).where(RegularOperation.uid == rule.uid).values(**values)
            )
        await self._session.flush()

    async def positions(self, uid: UUID) -> list[Position]:
        """Прочитать все занятые позиции, включая удалённые платежи."""
        rows = await self._session.scalars(select(RegularOccurrence).where(RegularOccurrence.operation_uid == uid))
        return [Position.model_validate(row, from_attributes=True) for row in rows]

    async def payments_for_update(self, uid: UUID) -> list[tuple[Position, Plan]]:
        """Заблокировать существующие платежи регулярной операции в порядке UID."""
        stmt = (
            select(RegularOccurrence, PlannedTransaction)
            .join(PlannedTransaction, PlannedTransaction.uid == RegularOccurrence.plan_uid)
            .where(RegularOccurrence.operation_uid == uid)
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
        self._session.add_all([RegularOccurrence(**position.model_dump()) for position in positions])
        await self._session.flush()

    async def remove_position(self, position: Position) -> None:
        """Освободить дату заменяемого платежа при пересчёте."""
        await self._session.execute(
            delete(RegularOccurrence).where(
                RegularOccurrence.operation_uid == position.operation_uid,
                RegularOccurrence.scheduled_date == position.scheduled_date,
            )
        )

    async def mark_exception(self, plan_uid: UUID) -> None:
        """Сохранить отметку ручного изменения у связанного платежа."""
        await self._session.execute(
            update(RegularOccurrence).where(RegularOccurrence.plan_uid == plan_uid).values(is_exception=True)
        )

    async def link(self, plan_uid: UUID) -> tuple[Position, RegularTransactionRule] | None:
        """Получить метаданные связи, в том числе с удалённой регулярной операцией."""
        stmt = (
            select(RegularOccurrence, RegularOperation)
            .join(RegularOperation, RegularOperation.uid == RegularOccurrence.operation_uid)
            .where(RegularOccurrence.plan_uid == plan_uid)
        )
        row = (await self._session.execute(stmt)).tuples().one_or_none()
        if row is None:
            return None
        position, rule = row
        return Position.model_validate(position, from_attributes=True), RegularTransactionRule.model_validate(
            rule, from_attributes=True
        )
