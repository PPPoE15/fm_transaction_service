from datetime import date, datetime

from sqlalchemy import Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID, Integer

from apps.shared import apps_types
from apps.shared.db.base import AsyncBase


class StartingBalance(AsyncBase):
    """Стартовый остаток пользователя: одна строка на пользователя."""

    __tablename__ = "starting_balances"

    user_uid: Mapped[apps_types.UserUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="UID пользователя (первичный ключ: остаток задаётся один раз).",
    )
    amount: Mapped[int] = mapped_column(
        Integer,
        doc="Сумма в целых рублях на конец дня balance_date, может быть отрицательной.",
    )
    balance_date: Mapped[date] = mapped_column(
        Date,
        doc="День, на конец которого задан остаток.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Когда остаток задан; для диагностики, в API не отдаётся.",
    )
