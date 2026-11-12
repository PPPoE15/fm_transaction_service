"""Управление регулярными операциями и переиспользуемая транзакционная генерация."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from apps.modules.category import Category
from apps.modules.planning.application.regular_schemas import ConversionResult, RegularOperationView
from apps.modules.planning.application.schemas import PlanView
from apps.modules.planning.application.uow import AbstractPlanUnitOfWork
from apps.modules.planning.domain.errors import (
    PlanLimitError,
    PlanNotFoundError,
    PlanVersionError,
    RegularDuplicateError,
    RegularNotFoundError,
    RegularSourceError,
    RegularViolationError,
)
from apps.modules.planning.domain.model import MAX_PLANS, Money, Plan, PlanChanges
from apps.modules.planning.domain.regular import Position, RegularOperationRule
from apps.modules.planning.domain.schedule import Frequency
from apps.shared.api_types import DescriptionIn
from apps.shared.schemas import Base


class RegularOperationRuleInput(Base):
    """Поля новой регулярной операции, прошедшие проверку формата."""

    category_uid: UUID
    money_sum: Money
    description: DescriptionIn | None = None
    frequency: Frequency
    first_date: date
    end_date: date | None = None


class RegularCommands:
    """Изменяет регулярные операции и платежи под общей блокировкой владельца."""

    def __init__(self, uow: AbstractPlanUnitOfWork, clock: Callable[[], date]) -> None:
        """Принять общую транзакцию и московский календарь."""
        self.uow = uow
        self.clock = clock

    async def _load(self, user_uid: UUID, uid: UUID, expected_version: int | None = None) -> RegularOperationRule:
        """Получить регулярную операцию владельца, проверив версию до бизнес-валидации."""
        await self.uow.plans.lock_owner(user_uid)
        rule = await self.uow.regular_operation_rules.get(user_uid, uid)
        if rule is None:
            raise RegularNotFoundError
        if expected_version is not None and rule.version != expected_version:
            raise PlanVersionError
        return rule

    async def _category(
        self, user_uid: UUID, uid: UUID, rule: RegularOperationRule | None, source: Plan | None
    ) -> Category:
        """Проверить категорию и сохранить её тип под блокировкой."""
        category = await self.uow.categories.get_by_uid_for_key_share(uid)
        if category is None or not category.belongs_to(user_uid):
            msg = "Категория недоступна"
            raise RegularViolationError(msg, field="category_uid")
        previous = rule.transaction_type if rule else source.transaction_type if source else None
        if previous is not None and category.category_type != previous:
            msg = "Категория должна иметь тот же тип"
            raise RegularViolationError(msg, field="category_uid")
        return category

    async def _materialize(self, rule: RegularOperationRule, start: date, end: date) -> dict[date, Plan]:
        """Создать свободные позиции включительно и передвинуть границу в той же транзакции."""
        occupied = {position.scheduled_date for position in await self.uow.regular_operation_rules.positions(rule.uid)}
        dates = [when for when in rule.schedule().dates_between(start, end) if when not in occupied]
        if dates and await self.uow.plans.count_for_update(rule.user_uid) + len(dates) > MAX_PLANS:
            raise PlanLimitError
        payments = {}
        for when in dates:
            payment = Plan.create(rule.user_uid, rule.transaction_type, rule.payment(when), when)
            await self.uow.plans.create(payment)
            payments[when] = payment
        if payments:
            await self.uow.regular_operation_rules.add_positions(
                [
                    Position(operation_uid=rule.uid, scheduled_date=when, plan_uid=payment.uid)
                    for when, payment in payments.items()
                ]
            )
        if rule.generated_through is None or rule.generated_through < end:
            rule.generated_through = end
            await self.uow.regular_operation_rules.save(rule)
        return payments

    async def generate(self, user_uid: UUID, uid: UUID, today: date) -> int:
        """Достроить необработанный диапазон до горизонта, в том числе пропущенные даты."""
        async with self.uow:
            await self.uow.plans.lock_owner(user_uid)
            rule = await self.uow.regular_operation_rules.get(user_uid, uid)
            if rule is None:
                return 0
            end = rule.horizon(today)
            if rule.generated_through is not None and rule.generated_through >= end:
                return 0
            start = (
                rule.generated_through + timedelta(days=1) if rule.generated_through is not None else rule.first_date
            )
            count = len(await self._materialize(rule, start, end))
            await self.uow.commit()
        return count

    async def _create(
        self, user_uid: UUID, values: RegularOperationRuleInput, source: Plan | None
    ) -> tuple[RegularOperationView, PlanView | None]:
        """Создать регулярную операцию, при необходимости присоединив невыполненный источник."""
        today = self.clock()
        category = await self._category(user_uid, values.category_uid, None, source)
        rule = RegularOperationRule(
            uid=uuid4(),
            user_uid=user_uid,
            transaction_type=category.category_type,
            source_plan_uid=source.uid if source else None,
            **(
                values.model_dump(include=set(RegularOperationRuleInput.model_fields))
                | {"description": values.description or None}
            ),
        )
        rule.validate_schedule(today)
        await self.uow.regular_operation_rules.save(rule, new=True)
        first = source if source is not None and source.status == "pending" else None
        position = None
        if first is not None:
            first.update(PlanChanges(**rule.payment(rule.first_date).model_dump()), first.version, today)
            await self.uow.plans.update(first)
            position = Position(operation_uid=rule.uid, scheduled_date=rule.first_date, plan_uid=first.uid)
            await self.uow.regular_operation_rules.add_positions([position])
        horizon = rule.horizon(today)
        generated = await self._materialize(rule, rule.first_date, horizon)
        if first is None:
            first = generated.get(rule.first_date)
            if first is not None:
                position = Position(operation_uid=rule.uid, scheduled_date=rule.first_date, plan_uid=first.uid)
        return (
            RegularOperationView.build(rule, category.name, today),
            PlanView.build(first, category.name, today, (position, rule)) if first and position else None,
        )

    async def create(self, user_uid: UUID, values: RegularOperationRuleInput) -> RegularOperationView:
        """Создать регулярную операцию и её первый горизонт одним commit."""
        async with self.uow:
            await self.uow.plans.lock_owner(user_uid)
            rule = (await self._create(user_uid, values, None))[0]
            await self.uow.commit()
        return rule

    async def convert(
        self, user_uid: UUID, plan_uid: UUID, values: RegularOperationRuleInput, expected_version: int
    ) -> ConversionResult:
        """Присоединить исходный план или создать новую регулярную операцию из выполненного."""
        async with self.uow:
            source = await self.uow.plans.get_for_update(user_uid, plan_uid)
            if source is None:
                raise PlanNotFoundError
            source.check_version(expected_version)
            if await self.uow.plans.link(source.uid) is not None:
                raise RegularSourceError
            if await self.uow.regular_operation_rules.has_source(user_uid, plan_uid):
                raise RegularDuplicateError
            rule, first = await self._create(user_uid, values, source)
            await self.uow.commit()
        return ConversionResult(
            operation=rule,
            first_plan=first,
            source_plan_uid=plan_uid,
            source_disposition="attached" if source.status == "pending" else "unchanged",
        )

    async def update(
        self, user_uid: UUID, uid: UUID, changes: dict[str, object], expected_version: int
    ) -> RegularOperationView:
        """Достроить прошлое и применить новые условия к заменяемым платежам."""
        async with self.uow:
            original = await self._load(user_uid, uid, expected_version)
            today = self.clock()
            updated = RegularOperationRule.model_validate(original.model_dump() | changes)
            updated.description = updated.description or None
            updated.validate_schedule(today, original.first_date)
            category = await self._category(user_uid, updated.require_category_uid(), original, None)
            yesterday = today - timedelta(days=1)
            start = (
                original.generated_through + timedelta(days=1)
                if original.generated_through is not None
                else original.first_date
            )
            end = min(yesterday, original.end_date or yesterday)
            if start <= end:
                await self._materialize(original, start, end)
            schedule_changed = original.schedule() != updated.schedule()
            for position, plan in await self.uow.regular_operation_rules.payments_for_update(uid):
                if position.is_exception or plan.status == "completed" or plan.planned_date < today:
                    continue
                if schedule_changed:
                    await self.uow.regular_operation_rules.remove_position(position)
                    await self.uow.plans.delete(plan)
                    continue
                values = updated.payment(plan.planned_date).model_dump(exclude={"planned_date"})
                delta = {field: value for field, value in values.items() if getattr(plan, field) != value}
                if delta:
                    plan.update(PlanChanges.model_validate(delta), plan.version, today)
                    await self.uow.plans.update(plan)
            updated.version += 1
            updated.generated_through = yesterday if schedule_changed else original.generated_through
            await self.uow.regular_operation_rules.save(updated)
            horizon = updated.horizon(today)
            if updated.generated_through is None or updated.generated_through < horizon:
                first = (
                    max(today, updated.generated_through + timedelta(days=1))
                    if updated.generated_through is not None
                    else today
                )
                await self._materialize(updated, first, horizon)
            result = RegularOperationView.build(updated, category.name, today)
            await self.uow.commit()
        return result

    async def delete(self, user_uid: UUID, uid: UUID, expected_version: int) -> None:
        """Остановить регулярную операцию и удалить её невыполненные платежи, сохранив факты."""
        async with self.uow:
            rule = await self._load(user_uid, uid, expected_version)
            for payment in await self.uow.regular_operation_rules.payments_for_update(uid):
                plan = payment[1]
                if plan.status == "pending":
                    await self.uow.plans.delete(plan)
            rule.deleted_at = datetime.now(UTC)
            rule.category_uid = None
            await self.uow.regular_operation_rules.save(rule)
            await self.uow.commit()
