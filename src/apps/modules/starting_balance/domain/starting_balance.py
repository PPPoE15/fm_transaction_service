from datetime import date, timedelta
from typing import Self

from pydantic import Field

from apps.shared import apps_types
from apps.shared.exceptions import BaseUnprocessableError
from apps.shared.schemas import Base

MIN_BALANCE_DATE = date(2000, 1, 1)
MAX_BALANCE_DATE = date(2099, 12, 31)


class InvalidBalanceDateError(BaseUnprocessableError):
    """Дата стартового остатка вне 2000–2099 годов или позже сегодняшнего дня."""

    msg = "Дата остатка должна быть не раньше 2000 года и не позже сегодняшнего дня"
    code = "FM-422002"
    field = "balance_date"


class StartingBalance(Base):
    """Агрегат стартового остатка пользователя: задаётся один раз и потом не меняется."""

    user_uid: apps_types.UserUID = Field(
        description="UID пользователя.",
    )
    amount: int = Field(
        description="Сумма в целых рублях на конец дня `balance_date`, может быть отрицательной.",
    )
    balance_date: date = Field(
        description="День, на конец которого задан остаток.",
    )

    @classmethod
    def create(
        cls,
        user_uid: apps_types.UserUID,
        amount: int,
        balance_date: date | None,
        today: date,
    ) -> Self:
        """
        Создать стартовый остаток.

        Args:
            user_uid: UID пользователя.
            amount: Сумма в целых рублях.
            balance_date: День, на конец которого задан остаток; не передан — вчера (остаток на начало сегодня).
            today: Текущая дата.

        Raises:
            InvalidBalanceDateError: Если дата вне 2000–2099 годов или позже сегодняшнего дня.
        """
        if balance_date is None:
            balance_date = today - timedelta(days=1)
        if not MIN_BALANCE_DATE <= balance_date <= min(today, MAX_BALANCE_DATE):
            raise InvalidBalanceDateError
        return cls(user_uid=user_uid, amount=amount, balance_date=balance_date)
