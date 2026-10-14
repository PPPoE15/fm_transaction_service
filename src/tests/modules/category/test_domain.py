"""Правила агрегата статьи."""

from uuid import uuid4

import pytest

from apps.modules.category.domain import Category
from apps.shared import apps_types

INCOME = apps_types.TransactionType.INCOME
OUTCOME = apps_types.TransactionType.OUTCOME


def _category(category_type: apps_types.TransactionType, money_plan: int | None) -> Category:
    return Category.create(
        name="Статья", user_uid=uuid4(), money_plan=money_plan, category_type=category_type, description=None
    )


@pytest.mark.parametrize("category_type", [INCOME, OUTCOME])
def test_without_plan_any_sum_is_in_the_budget(category_type: apps_types.TransactionType) -> None:
    """Плана нет — выходить за него нечем, любая сумма в бюджете."""
    assert _category(category_type, None).is_in_the_budget(1_000_000)


@pytest.mark.parametrize(
    ("category_type", "money_sum", "expected"),
    [(OUTCOME, 999, True), (OUTCOME, 1000, False), (INCOME, 1001, True), (INCOME, 1000, False)],
)
def test_with_plan(category_type: apps_types.TransactionType, money_sum: int, *, expected: bool) -> None:
    """С планом прежнее правило: расход меньше плана, доход больше плана."""
    assert _category(category_type, 1000).is_in_the_budget(money_sum) is expected
