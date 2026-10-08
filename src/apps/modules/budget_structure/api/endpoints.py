from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from apps.modules.budget_structure.application.queries import schemas as q_schemas
from apps.modules.budget_structure.application.queries.get import GetBudgetStructure
from apps.modules.budget_structure.domain import BudgetStructure
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

from . import deps

router = APIRouter(tags=["Отчёты"])


@router.get(
    "/budget-structure",
    summary="Структура бюджета по месяцам",
    description=(
        "Факт по статьям выбранного типа за каждый месяц года: у будущих месяцев null, "
        "среднее — по завершённым месяцам, итоговая строка — суммы по всем статьям."
    ),
)
async def get_budget_structure(
    params: Annotated[q_schemas.BudgetStructureParams, Depends()],
    user: Annotated[UserInfo, Depends(get_user_info)],
    today: Annotated[date, Depends(deps.get_today)],
) -> BudgetStructure:
    """
    Таблица «Структура бюджета».

    Args:
        params: Год и тип статей.
        user: Информация об авторизованном пользователе.
        today: Текущая дата.
    """
    async with async_session_factory() as session:
        return await GetBudgetStructure(session).execute(
            user_uid=user.uid,
            year=params.year if params.year is not None else today.year,
            category_type=params.category_type,
            today=today,
        )
