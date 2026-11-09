"""Команды планирования: инварианты, владение, версии и календарь."""

from collections.abc import Callable
from datetime import date
from uuid import UUID

from apps.modules.category import Category
from apps.modules.planning.application.schemas import PlanView
from apps.modules.planning.application.uow import AbstractPlanUnitOfWork
from apps.modules.planning.domain.errors import (
    PlanCategoryError,
    PlanCategoryTypeError,
    PlanLimitError,
    PlanNotFoundError,
)
from apps.modules.planning.domain.model import MAX_PLANS, Plan, PlanChanges, PlanInput


class PlanCommands:
    """Выполняет один пользовательский запрос в собственной единице работы."""

    def __init__(self, uow: AbstractPlanUnitOfWork, clock: Callable[[], date]) -> None:
        """Принять хранилище и часы, вызываемые после ожидания блокировок."""
        self.uow = uow
        self.clock = clock

    async def _category(self, user_uid: UUID, category_uid: UUID) -> Category:
        """Проверить принадлежность категории под блокировкой от смены типа."""
        category = await self.uow.categories.get_by_uid_for_key_share(category_uid)
        if category is None or category.user_uid != user_uid:
            raise PlanCategoryError
        return category

    async def _plan(self, user_uid: UUID, plan_uid: UUID) -> Plan:
        """Прочитать собственный план, не раскрывая наличие чужого."""
        plan = await self.uow.plans.get_for_update(user_uid, plan_uid)
        if plan is None:
            raise PlanNotFoundError
        return plan

    async def create(self, user_uid: UUID, values: PlanInput) -> PlanView:
        """Создать новый план и вернуть снимок без повторного чтения после commit."""
        async with self.uow:
            count = await self.uow.plans.count_for_update(user_uid)
            category = await self._category(user_uid, values.category_uid)
            today = self.clock()
            plan = Plan.create(user_uid, category.category_type, values, today)
            if count >= MAX_PLANS:
                raise PlanLimitError
            await self.uow.plans.create(plan)
            result = PlanView.build(plan, category.name, today)
            await self.uow.commit()
        return result

    async def update(self, user_uid: UUID, plan_uid: UUID, changes: PlanChanges, expected_version: int) -> PlanView:
        """Сохранить одну строку или перенести дату с проверкой статуса и версии."""
        async with self.uow:
            plan = await self._plan(user_uid, plan_uid)
            plan.ensure_editable(expected_version)
            category = await self._category(user_uid, changes.category_uid or plan.category_uid)
            if category.category_type != plan.transaction_type:
                raise PlanCategoryTypeError
            today = self.clock()
            plan.update(changes, expected_version, today)
            await self.uow.plans.update(plan)
            result = PlanView.build(plan, category.name, today)
            await self.uow.commit()
        return result

    async def delete(self, user_uid: UUID, plan_uid: UUID, expected_version: int) -> None:
        """Удалить план в любом статусе, сохранив фактическую операцию."""
        async with self.uow:
            plan = await self._plan(user_uid, plan_uid)
            plan.check_version(expected_version)
            await self.uow.plans.delete(plan)
            await self.uow.commit()
