"""Атомарное подтверждение плана фактической транзакцией."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from apps.modules.planning.application.schemas import PlanConfirmation, PlanView
from apps.modules.planning.application.uow import AbstractPlanUnitOfWork
from apps.modules.planning.domain.errors import PlanCategoryError, PlanCategoryTypeError, PlanNotFoundError
from apps.modules.transaction import (
    MAX_TRANSACTIONS_PER_USER,
    CategoryRef,
    Transaction,
    TransactionCategoryNotFoundError,
    TransactionSchema,
    TransactionTypeMismatchError,
    validate_creation,
)


class ConfirmPlanCommand:
    """Создаёт один факт и выполняет план в одной транзакции без повторных попыток."""

    def __init__(self, uow: AbstractPlanUnitOfWork, clock: Callable[[], datetime]) -> None:
        """Принять общую единицу работы и часы, вызываемые после получения блокировок."""
        self.uow = uow
        self.clock = clock

    async def handle(
        self,
        user_uid: UUID,
        plan_uid: UUID,
        expected_version: int,
        transaction_date: datetime,
        money_sum: int,
        category_uid: UUID,
        description: str | None,
    ) -> PlanConfirmation:
        """Проверить доступ и состояние; сохранить факт, снимок и новую версию одним commit."""
        async with self.uow:
            plan = await self.uow.plans.get_for_update(user_uid, plan_uid)
            if plan is None:
                raise PlanNotFoundError
            plan.ensure_editable(expected_version)
            # Квота использует ту же advisory-блокировку, что обычное создание и импорт фактов.
            count = await self.uow.transactions.count_by_user_for_update(user_uid)
            # Обе категории читаются в порядке UID, совместимом с пакетными правками фактов.
            categories = {
                uid: await self.uow.categories.get_by_uid_for_key_share(uid)
                for uid in sorted({plan.category_uid, category_uid})
            }
            original_category = categories[plan.category_uid]
            if original_category is None or not original_category.belongs_to(user_uid):
                raise PlanCategoryError
            try:
                fact_category = validate_creation(
                    categories[category_uid], user_uid, plan.transaction_type, count, MAX_TRANSACTIONS_PER_USER
                )
            except TransactionCategoryNotFoundError as exc:
                raise PlanCategoryError from exc
            except TransactionTypeMismatchError as exc:
                raise PlanCategoryTypeError from exc
            now = self.clock()
            transaction = Transaction.create(
                user_uid=user_uid,
                transaction_date=transaction_date,
                category_uid=category_uid,
                money_sum=money_sum,
                transaction_type=plan.transaction_type,
                description=description or None,
            )
            await self.uow.transactions.create(transaction)
            plan.complete(expected_version, transaction.uid, original_category.name, now)
            # UPDATE плана с FK на новый факт заставляет сессию сначала сбросить ожидающую INSERT.
            await self.uow.plans.update(plan)
            result = PlanConfirmation(
                plan=PlanView.build(plan, original_category.name, now.astimezone(ZoneInfo("Europe/Moscow")).date()),
                transaction=TransactionSchema(
                    **transaction.model_dump(exclude={"user_uid", "category_uid"}),
                    category=CategoryRef(uid=fact_category.uid, name=fact_category.name),
                ),
            )
            await self.uow.commit()
        return result
