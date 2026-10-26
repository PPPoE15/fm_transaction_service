"""HTTP-контракт дневной истории общего остатка."""

import re
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BeforeValidator

from apps.modules.reports.application.exceptions import InvalidHistoryRangeError
from apps.modules.reports.application.queries.balance_history import GetBalanceHistory
from apps.modules.reports.domain.balance_history import BalanceHistory
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

from .deps import get_now

MAX_HISTORY_DAYS = 366
router = APIRouter()


def parse_history_date(value: object) -> date:
    """
    Принять только существующую дату YYYY-MM-DD в пределах 2000–2099.

    Args:
        value: Строковое значение query-параметра.
    """
    if not isinstance(value, str) or not re.fullmatch(r"20\d{2}-[0-9]{2}-[0-9]{2}", value):
        msg = "Ожидается дата YYYY-MM-DD, годы 2000–2099"
        raise ValueError(msg)
    return date.fromisoformat(value)


HistoryDate = Annotated[date, BeforeValidator(parse_history_date)]


@router.get("/balance-history", summary="Общий остаток по дням", operation_id="getBalanceHistory")
async def get_balance_history(
    date_from: Annotated[HistoryDate, Query()],
    date_to: Annotated[HistoryDate, Query()],
    user: Annotated[UserInfo, Depends(get_user_info)],
    now: Annotated[datetime, Depends(get_now)],
) -> BalanceHistory:
    """
    Вернуть остаток на каждый день включительного диапазона.

    Args:
        date_from: Начало диапазона.
        date_to: Конец диапазона.
        user: Авторизованный пользователь.
        now: Московский момент запроса, общий для валидации и расчёта.
    """
    if not 1 <= (date_to - date_from).days + 1 <= MAX_HISTORY_DAYS or date_to > now.date():
        raise InvalidHistoryRangeError
    async with async_session_factory() as session:
        return await GetBalanceHistory(session).execute(user.uid, date_from, date_to, now)
