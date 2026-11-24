"""Обратный и прямой расчёт остатка от единой стартовой суммы."""

from datetime import date

import pytest

from apps.modules.reports.domain.balance_history import build_balance_history


@pytest.mark.parametrize(
    ("start", "end", "anchor", "amount", "changes", "history_start", "balances"),
    [
        (
            "2026-11-01",
            "2026-11-03",
            "2026-11-24",
            50000,
            {"2026-11-01": 2000, "2026-11-02": -3000, "2026-11-24": 13000},
            "2026-11-01",
            [40000, 37000, 37000],
        ),
        (
            "2026-11-23",
            "2026-11-25",
            "2026-11-24",
            50000,
            {"2026-11-01": 1000, "2026-11-24": 3000, "2026-11-25": -2000},
            "2026-11-01",
            [47000, 50000, 48000],
        ),
        (
            "2026-11-24",
            "2026-11-24",
            "2026-11-24",
            50000,
            {"2026-11-23": 100, "2026-11-24": 3000},
            "2026-11-23",
            [50000],
        ),
        (
            "2026-11-01",
            "2026-11-03",
            "2026-11-03",
            -1000,
            {"2026-11-01": 100, "2026-11-02": -1000},
            "2026-11-01",
            [0, -1000, -1000],
        ),
        (
            "2000-01-01",
            "2000-01-02",
            "2000-01-02",
            5000,
            {"1999-12-31": 999, "2000-01-01": 1000, "2000-01-02": 2000},
            "2000-01-01",
            [3000, 5000],
        ),
        ("2026-11-23", "2026-11-25", "2026-11-24", 50000, {}, "2026-11-24", [None, 50000, 50000]),
        ("2026-11-23", "2026-11-25", "2026-11-24", 50000, {"2026-11-25": 1000}, "2026-11-24", [None, 50000, 51000]),
        ("2026-10-30", "2026-10-31", "2026-11-24", 50000, {"2026-11-01": 1000}, "2026-11-01", [None, None]),
        (
            "2026-11-25",
            "2026-11-26",
            "2026-11-24",
            50000,
            {"2026-11-23": 999, "2026-11-24": 999, "2026-11-25": 10},
            "2026-11-23",
            [50010, 50010],
        ),
        (
            "2026-11-01",
            "2026-11-02",
            "2026-11-24",
            0,
            {"2026-11-01": 0, "2026-11-24": 3_000_000_000},
            "2026-11-01",
            [-3_000_000_000, -3_000_000_000],
        ),
    ],
)
def test_balance_history_from_anchor(
    start: str,
    end: str,
    anchor: str,
    amount: int,
    changes: dict[str, int],
    history_start: str,
    balances: list[int | None],
) -> None:
    """Проверить вручную рассчитанные ряды, границы, стартовый день и суммы свыше int32."""
    history = build_balance_history(
        date.fromisoformat(start),
        date.fromisoformat(end),
        date.fromisoformat(anchor),
        amount,
        {date.fromisoformat(day): value for day, value in changes.items()},
    )
    assert [point.balance for point in history.points] == balances
    assert history.history_start_date == date.fromisoformat(history_start)
    assert history.starting_balance_date == date.fromisoformat(anchor)
