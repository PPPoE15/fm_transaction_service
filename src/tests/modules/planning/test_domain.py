"""Правила планов без обращения к хранилищу."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.modules.planning.domain.errors import CompletedPlanError, InvalidPlanDateError, PlanVersionError
from apps.modules.planning.domain.model import Plan, PlanChanges, PlanInput
from apps.shared.apps_types import TransactionType

INITIAL_AMOUNT = 10
SECOND_VERSION = 2
THIRD_VERSION = 3
TODAY = date(2026, 11, 9)


def make_plan() -> Plan:
    """Создать невыполненный план с допустимыми исходными значениями."""
    return Plan.create(
        uuid4(), TransactionType.OUTCOME, PlanInput(planned_date=TODAY, money_sum=10, category_uid=uuid4()), TODAY
    )


@pytest.mark.parametrize("value", [0, -1, 1.5, "100", True, 1_000_000_001])
def test_invalid_money(value: object) -> None:
    """Сумма принимает только целые положительные рубли в границах контракта."""
    with pytest.raises(ValidationError):
        PlanInput.model_validate({"planned_date": TODAY, "money_sum": value, "category_uid": uuid4()})


def test_plan_date_and_version() -> None:
    """Создание и изменение проверяют дату; правка сохраняет неуказанные поля."""
    plan = make_plan()
    plan.update(PlanChanges(description="Новый комментарий"), 1, TODAY)
    assert plan.version == SECOND_VERSION
    assert plan.money_sum == INITIAL_AMOUNT
    with pytest.raises(PlanVersionError):
        plan.update(PlanChanges(money_sum=20), 1, TODAY)
    with pytest.raises(InvalidPlanDateError):
        plan.update(PlanChanges(money_sum=20), 2, date(2026, 11, 10))
    plan.update(PlanChanges(planned_date=date(2026, 11, 12), description=None), 2, date(2026, 11, 10))
    assert plan.description is None
    assert plan.version == THIRD_VERSION


def test_completed_is_immutable_but_deletable() -> None:
    """Выполненный план нельзя менять, но проверка версии допускает его удаление."""
    plan = make_plan().model_copy(
        update={"status": "completed", "completed_at": datetime.now(UTC), "category_name_snapshot": "ЖКХ"}
    )
    with pytest.raises(CompletedPlanError):
        plan.update(PlanChanges(money_sum=20), 1, TODAY)
    plan.check_version(1)


@pytest.mark.parametrize(
    "changes", [{}, {"money_sum": None}, {"planned_date": None}, {"category_uid": None}, {"transaction_type": "income"}]
)
def test_invalid_changes(changes: dict[str, object]) -> None:
    """Изменения непустые; null разрешён только для комментария, тип неизменяем."""
    with pytest.raises(ValidationError):
        PlanChanges.model_validate(changes)


@pytest.mark.parametrize("day", [date(1999, 12, 31), date(2100, 1, 1), date(2026, 11, 8)])
def test_create_invalid_date(day: date) -> None:
    """Нельзя создать план в прошлом или вне диапазона календаря."""
    with pytest.raises(InvalidPlanDateError):
        Plan.create(
            uuid4(), TransactionType.OUTCOME, PlanInput(planned_date=day, money_sum=10, category_uid=uuid4()), TODAY
        )


def test_complete_preserves_plan_values_and_prevents_repeat() -> None:
    """Подтверждение сохраняет исходные поля и не допускает второго перехода."""
    plan = make_plan()
    original = plan.model_dump(include={"planned_date", "money_sum", "category_uid", "description", "transaction_type"})
    fact_uid = uuid4()
    moment = datetime(2026, 11, 10, 12, tzinfo=UTC)
    plan.complete(1, fact_uid, "Исходная категория", moment)
    assert plan.status == "completed"
    assert plan.version == SECOND_VERSION
    assert plan.transaction_uid == fact_uid
    assert plan.completed_at == moment
    assert plan.category_name_snapshot == "Исходная категория"
    assert plan.model_dump(include=set(original)) == original
    with pytest.raises(CompletedPlanError):
        plan.complete(1, uuid4(), "Другая", moment)


def test_complete_rejects_stale_version_without_mutation() -> None:
    """Устаревшее подтверждение не меняет план и его связь."""
    plan = make_plan()
    original = plan.model_dump()
    with pytest.raises(PlanVersionError):
        plan.complete(SECOND_VERSION, uuid4(), "Категория", datetime.now(UTC))
    assert plan.model_dump() == original
