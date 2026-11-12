"""SQLAlchemy-адаптер планов и блокировок PostgreSQL."""

from uuid import UUID

from sqlalchemy import delete, func, select, text, update

from apps.modules.planning.application.ports import AbstractPlanRepo
from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.regular import Position, RegularTransactionRule
from apps.modules.planning.infrastructure import builders
from apps.modules.planning.infrastructure.orm import PlannedTransaction
from apps.modules.planning.infrastructure.regular_repo import RegularTransactionRuleRepo
from apps.shared.db.base_repo import BaseSqlAlchemyRepo


class PlanRepo(AbstractPlanRepo, BaseSqlAlchemyRepo):
    """Загружает и сохраняет планы без переноса доменных правил в SQL."""

    async def lock_owner(self, user_uid: UUID) -> None:
        """Сериализовать команды планирования по владельцу."""
        await self._session.execute(text("SELECT pg_advisory_xact_lock(107, hashtext(:uid))"), {"uid": str(user_uid)})

    async def count_for_update(self, user_uid: UUID) -> int:
        """Сериализовать создание по владельцу даже для пустого набора."""
        await self.lock_owner(user_uid)
        return int(
            await self._session.scalar(
                select(func.count()).select_from(PlannedTransaction).where(PlannedTransaction.user_uid == user_uid)
            )
            or 0
        )

    async def get_for_update(self, user_uid: UUID, plan_uid: UUID) -> Plan | None:
        """Прочитать собственную запись под блокировкой до конца команды."""
        await self.lock_owner(user_uid)
        stmt = (
            select(PlannedTransaction)
            .where(PlannedTransaction.uid == plan_uid, PlannedTransaction.user_uid == user_uid)
            .with_for_update()
        )
        row = await self._session.scalar(stmt)
        return builders.build(row) if row is not None else None

    async def create(self, plan: Plan) -> None:
        """Подготовить вставку нового агрегата."""
        self._session.add(builders.build_orm(plan))

    async def update(self, plan: Plan) -> None:
        """Обновить заблокированную запись, не затрагивая связи ORM."""
        await self._session.execute(
            update(PlannedTransaction)
            .where(PlannedTransaction.uid == plan.uid, PlannedTransaction.user_uid == plan.user_uid)
            .values(**plan.model_dump(exclude={"uid", "user_uid"}))
        )

    async def delete(self, plan: Plan) -> None:
        """Удалить заблокированную запись без удаления факта."""
        await self._session.execute(
            delete(PlannedTransaction).where(
                PlannedTransaction.uid == plan.uid, PlannedTransaction.user_uid == plan.user_uid
            )
        )

    async def link(self, plan_uid: UUID) -> tuple[Position, RegularTransactionRule] | None:
        """Прочитать метаданные регулярного платежа в транзакции плана."""
        return await RegularTransactionRuleRepo(self._session).link(plan_uid)

    async def mark_exception(self, plan_uid: UUID) -> None:
        """Отметить ручную правку связанной позиции."""
        await RegularTransactionRuleRepo(self._session).mark_exception(plan_uid)
