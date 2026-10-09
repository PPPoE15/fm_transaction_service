"""Расчёт структуры бюджета без БД: наступившие/будущие месяцы, среднее и итоговая строка."""

from datetime import date
from uuid import uuid4

import pytest

from apps.modules.reports.domain import BudgetCategory, BudgetStructure
from apps.shared import apps_types

OUTCOME = apps_types.TransactionType.OUTCOME
FOOD = BudgetCategory(uid=uuid4(), name="еда вне дома", money_plan=5000)
RENT = BudgetCategory(uid=uuid4(), name="ЖКХ", money_plan=None)


def _facts(structure_months: list) -> list[int | None]:
    return [month.fact for month in structure_months]


def test_months_are_january_to_december() -> None:
    """В строке и итоге всегда 12 месяцев по порядку."""
    structure = BudgetStructure.build(
        year=2026, category_type=OUTCOME, today=date(2026, 5, 15), categories=[FOOD], facts={}
    )

    assert [month.month for month in structure.rows[0].months] == list(range(1, 13))
    assert [month.month for month in structure.total.months] == list(range(1, 13))
    assert (structure.year, structure.category_type) == (2026, OUTCOME)


def test_current_year_january() -> None:
    """Январь текущего года: факт только за январь, остальное в будущем, завершённых месяцев нет."""
    structure = BudgetStructure.build(
        year=2026,
        category_type=OUTCOME,
        today=date(2026, 1, 10),
        categories=[FOOD],
        facts={(FOOD.uid, 1): 700},
    )

    [row] = structure.rows
    assert _facts(row.months) == [700] + [None] * 11
    assert row.average is None
    assert structure.total.average is None


def test_current_year_middle() -> None:
    """Середина года: наступившие месяцы без операций — 0, среднее только по завершённым месяцам."""
    structure = BudgetStructure.build(
        year=2026,
        category_type=OUTCOME,
        today=date(2026, 4, 1),
        categories=[FOOD],
        # Апрель (текущий, неполный) в среднее не входит.
        facts={(FOOD.uid, 1): 300, (FOOD.uid, 3): 600, (FOOD.uid, 4): 10_000},
    )

    [row] = structure.rows
    assert (_facts(row.months), row.average) == ([300, 0, 600, 10_000] + [None] * 8, 300)


def test_past_year_uses_all_twelve_months() -> None:
    """Прошедший год: все 12 месяцев наступили и завершены."""
    structure = BudgetStructure.build(
        year=2025,
        category_type=OUTCOME,
        today=date(2026, 1, 1),
        categories=[FOOD],
        facts={(FOOD.uid, 12): 1200},
    )

    [row] = structure.rows
    assert (_facts(row.months), row.average) == ([0] * 11 + [1200], 100)


def test_future_year_has_no_facts() -> None:
    """Будущий год: ни одного наступившего месяца, среднего нет."""
    structure = BudgetStructure.build(
        year=2027,
        category_type=OUTCOME,
        today=date(2026, 12, 31),
        categories=[FOOD],
        facts={},
    )

    [row] = structure.rows
    assert _facts(row.months) == [None] * 12
    assert row.average is None
    assert _facts(structure.total.months) == [None] * 12
    assert structure.total.average is None


@pytest.mark.parametrize(
    ("march_fact", "expected_average"),
    [
        (1, 1),  # 1 / 2 = 0.5 -> 1
        (3, 2),  # 3 / 2 = 1.5 -> 2
        (2, 1),  # ровно 1
        (0, 0),
    ],
)
def test_average_rounds_half_up(march_fact: int, expected_average: int) -> None:
    """Среднее округляется до целого рубля, половина — вверх."""
    structure = BudgetStructure.build(
        year=2026,
        category_type=OUTCOME,
        today=date(2026, 3, 20),  # завершены январь и февраль
        categories=[FOOD],
        facts={(FOOD.uid, 2): march_fact},
    )

    assert structure.rows[0].average == expected_average


def test_average_rounds_below_half_down() -> None:
    """Меньше половины отбрасывается: 10 / 3 = 3.33 -> 3, 11 / 3 = 3.67 -> 4."""
    today = date(2026, 4, 2)  # завершены три месяца
    low = BudgetStructure.build(
        year=2026, category_type=OUTCOME, today=today, categories=[FOOD], facts={(FOOD.uid, 1): 10}
    )
    high = BudgetStructure.build(
        year=2026, category_type=OUTCOME, today=today, categories=[FOOD], facts={(FOOD.uid, 1): 11}
    )

    assert (low.rows[0].average, high.rows[0].average) == (3, 4)


def test_total_row_sums_rows() -> None:
    """Итог — суммы по строкам; план — сумма заданных планов; среднее — по итоговым фактам."""
    taxi = BudgetCategory(uid=uuid4(), name="такси", money_plan=1000)
    structure = BudgetStructure.build(
        year=2026,
        category_type=OUTCOME,
        today=date(2026, 3, 5),
        categories=[FOOD, RENT, taxi],
        facts={(FOOD.uid, 1): 1, (RENT.uid, 1): 1, (taxi.uid, 2): 1, (FOOD.uid, 3): 50},
    )

    assert [row.category.name for row in structure.rows] == ["еда вне дома", "ЖКХ", "такси"]
    assert [row.average for row in structure.rows] == [1, 1, 1]  # 0.5 -> 1 в каждой строке
    assert _facts(structure.total.months) == [2, 1, 50] + [None] * 9
    # Среднее итоговых фактов (2 + 1) / 2 = 1.5 -> 2, а не сумма средних строк (1 + 1 + 1).
    assert (structure.total.money_plan, structure.total.average) == (6000, 2)


def test_total_plan_is_null_when_no_category_has_plan() -> None:
    """Отсутствующий план отличается от нулевого: без планов итоговый план — null."""
    without_plan = BudgetStructure.build(
        year=2026, category_type=OUTCOME, today=date(2026, 3, 5), categories=[RENT], facts={}
    )
    zero_plan = BudgetStructure.build(
        year=2026,
        category_type=OUTCOME,
        today=date(2026, 3, 5),
        categories=[RENT, BudgetCategory(uid=uuid4(), name="подписки", money_plan=0)],
        facts={},
    )

    assert without_plan.rows[0].money_plan is None
    assert without_plan.total.money_plan is None
    assert zero_plan.total.money_plan == 0


def test_no_categories() -> None:
    """Статей нет: строк нет, итог по наступившим месяцам — нули."""
    structure = BudgetStructure.build(year=2026, category_type=OUTCOME, today=date(2026, 2, 5), categories=[], facts={})

    assert structure.rows == []
    assert _facts(structure.total.months) == [0, 0] + [None] * 10
    assert structure.total.money_plan is None
    assert structure.total.average == 0


def test_facts_above_int32_are_summed() -> None:
    """Итоги не ограничены 32 битами."""
    big = 2_000_000_000
    structure = BudgetStructure.build(
        year=2025,
        category_type=OUTCOME,
        today=date(2026, 1, 1),
        categories=[FOOD, RENT],
        facts={(FOOD.uid, 1): big, (RENT.uid, 1): big},
    )

    assert structure.total.months[0].fact == 2 * big
