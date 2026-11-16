from datetime import date

from pydantic import Field

from apps.shared.schemas import Base


class StartingBalanceSchema(Base):
    """Стартовый остаток пользователя."""

    amount: int = Field(
        title="Сумма",
        description="Сумма в целых рублях на конец дня balance_date. Может быть отрицательной (долг).",
        examples=[120000],
    )
    balance_date: date = Field(
        title="Дата остатка",
        description="День, на конец которого задан остаток.",
        examples=["2026-01-01"],
    )
