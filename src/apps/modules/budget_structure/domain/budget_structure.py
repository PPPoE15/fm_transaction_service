from collections.abc import Mapping, Sequence
from datetime import date
from typing import Self

from pydantic import Field

from apps.shared import apps_types
from apps.shared.schemas import Base

MONTHS_IN_YEAR = 12


class BudgetCategory(Base):
    """Статья, для которой строится строка таблицы."""

    uid: apps_types.CategoryUID = Field(
        description="UID статьи.",
    )
    name: apps_types.CategoryName = Field(
        description="Название статьи.",
    )
    money_plan: apps_types.MoneySum | None = Field(
        description="План статьи; null — плана нет (не то же, что 0).",
    )


class CategoryRef(Base):
    """Ссылка на статью в строке таблицы."""

    uid: apps_types.CategoryUID = Field(
        description="UID статьи.",
    )
    name: apps_types.CategoryName = Field(
        description="Название статьи.",
    )


class MonthFact(Base):
    """Факт за месяц."""

    month: int = Field(
        ge=1,
        le=MONTHS_IN_YEAR,
        description="Номер месяца, 1–12.",
    )
    fact: apps_types.MoneyTotal | None = Field(
        description="Сумма транзакций за месяц; null — месяц ещё не наступил.",
    )


class BudgetStructureRow(Base):
    """Строка таблицы — одна статья."""

    category: CategoryRef = Field(
        description="Статья.",
    )
    money_plan: apps_types.MoneySum | None = Field(
        description="План статьи; null — плана нет.",
    )
    average: apps_types.MoneyTotal | None = Field(
        description="Среднее факта по завершённым месяцам; null — завершённых месяцев нет.",
    )
    months: list[MonthFact] = Field(
        description="Факты за январь–декабрь.",
    )


class BudgetStructureTotal(Base):
    """Итоговая строка «сумма»."""

    money_plan: apps_types.MoneyTotal | None = Field(
        description="Сумма заданных планов; null — ни у одной статьи плана нет.",
    )
    average: apps_types.MoneyTotal | None = Field(
        description="Среднее итоговых фактов по завершённым месяцам; null — завершённых месяцев нет.",
    )
    months: list[MonthFact] = Field(
        description="Суммы фактов всех статей за январь–декабрь.",
    )


class BudgetStructure(Base):
    """Таблица «Структура бюджета»: факт по статьям и месяцам выбранного года."""

    year: int = Field(
        description="Год таблицы.",
    )
    category_type: apps_types.TransactionType = Field(
        description="Тип статей в таблице.",
    )
    rows: list[BudgetStructureRow] = Field(
        description="Строки по статьям в порядке переданных статей.",
    )
    total: BudgetStructureTotal = Field(
        description="Итоговая строка.",
    )

    @classmethod
    def build(
        cls,
        *,
        year: int,
        category_type: apps_types.TransactionType,
        today: date,
        categories: Sequence[BudgetCategory],
        facts: Mapping[tuple[apps_types.CategoryUID, int], apps_types.MoneyTotal],
    ) -> Self:
        """
        Посчитать таблицу.

        Args:
            year: Год таблицы.
            category_type: Тип статей.
            today: Текущая дата: по ней месяцы делятся на наступившие и будущие.
            categories: Статьи в порядке строк таблицы.
            facts: Суммы транзакций по (UID статьи, номер месяца); отсутствующая пара — 0.
        """
        elapsed, completed = _elapsed_and_completed_months(year, today)
        rows = [
            _build_row(category, [facts.get((category.uid, month), 0) for month in range(1, elapsed + 1)], completed)
            for category in categories
        ]
        total_facts = [sum(row.months[month].fact or 0 for row in rows) for month in range(elapsed)]
        plans = [category.money_plan for category in categories if category.money_plan is not None]
        total = BudgetStructureTotal(
            money_plan=sum(plans) if plans else None,
            average=_average(total_facts[:completed]),
            months=_months(total_facts),
        )
        return cls(year=year, category_type=category_type, rows=rows, total=total)


def _elapsed_and_completed_months(year: int, today: date) -> tuple[int, int]:
    """
    Число наступивших (включая текущий, неполный) и завершённых месяцев года.

    Args:
        year: Год таблицы.
        today: Текущая дата.
    """
    if year < today.year:
        return MONTHS_IN_YEAR, MONTHS_IN_YEAR
    if year == today.year:
        return today.month, today.month - 1
    return 0, 0


def _build_row(category: BudgetCategory, elapsed_facts: list[int], completed: int) -> BudgetStructureRow:
    """
    Строка статьи.

    Args:
        category: Статья.
        elapsed_facts: Факты наступивших месяцев, начиная с января.
        completed: Число завершённых месяцев.
    """
    return BudgetStructureRow(
        category=CategoryRef(uid=category.uid, name=category.name),
        money_plan=category.money_plan,
        average=_average(elapsed_facts[:completed]),
        months=_months(elapsed_facts),
    )


def _months(elapsed_facts: list[int]) -> list[MonthFact]:
    """
    12 месяцев: факты наступивших, null у будущих.

    Args:
        elapsed_facts: Факты наступивших месяцев, начиная с января.
    """
    padded: list[int | None] = [*elapsed_facts, *[None] * (MONTHS_IN_YEAR - len(elapsed_facts))]
    return [MonthFact(month=month, fact=fact) for month, fact in enumerate(padded, start=1)]


def _average(completed_facts: list[int]) -> int | None:
    """
    Среднее, округлённое до целого, половина — вверх; null для пустого списка.

    Целочисленно, без float: суммы могут не уместиться в точность double. Факты неотрицательны.

    Args:
        completed_facts: Факты завершённых месяцев.
    """
    if not completed_facts:
        return None
    count = len(completed_facts)
    return (2 * sum(completed_facts) + count) // (2 * count)
