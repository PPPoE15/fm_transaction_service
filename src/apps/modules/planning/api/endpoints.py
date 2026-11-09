"""HTTP-методы отдельного списка запланированных операций."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from starlette import status

from apps.modules.planning.api import deps
from apps.modules.planning.api.errors import category_error_response
from apps.modules.planning.api.schemas import ConfirmPlanSchema, CreatePlanSchema, PlanPageParams, UpdatePlanSchema
from apps.modules.planning.application.queries import PlanQueries
from apps.modules.planning.application.schemas import PlanConfirmation, PlanList, PlanView
from apps.modules.planning.domain.errors import PlanCategoryError, PlanCategoryTypeError
from apps.shared.apps_types import TransactionType
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

router = APIRouter(prefix="/planned-operations", tags=["Планирование"])
User = Annotated[UserInfo, Depends(get_user_info)]
Clock = Annotated[Callable[[], date], Depends(deps.get_clock)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_plan(item: CreatePlanSchema, user: User, clock: Clock) -> PlanView:
    """Создать новый план без автоматических повторов или изменения факта."""
    return await deps.commands(clock).create(user.uid, item)


@router.get("")
async def list_plans(
    user: User,
    clock: Clock,
    page: Annotated[PlanPageParams, Depends()],
    transaction_type: TransactionType | None = None,
    include_completed: bool = False,
) -> PlanList:
    """Прочитать ближайшие планы, включая будущие и наступившие."""
    async with async_session_factory() as session:
        return await PlanQueries(session).list(user.uid, page, transaction_type, include_completed, clock())


@router.get("/{plan_uid}")
async def get_plan(plan_uid: UUID, user: User, clock: Clock) -> PlanView:
    """Прочитать актуальный собственный план и состояние ссылки на факт."""
    async with async_session_factory() as session:
        return await PlanQueries(session).get(user.uid, plan_uid, clock())


@router.patch("/{plan_uid}")
async def update_plan(plan_uid: UUID, item: UpdatePlanSchema, user: User, clock: Clock) -> PlanView:
    """Изменить одну строку или перенести её дату с обязательной версией."""
    return await deps.commands(clock).update(user.uid, plan_uid, item.changes(), item.expected_version)


@router.delete("/{plan_uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_uid: UUID, user: User, clock: Clock, expected_version: Annotated[int, Query(ge=1)]
) -> Response:
    """Удалить план в любом статусе без удаления связанного факта."""
    await deps.commands(clock).delete(user.uid, plan_uid, expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{plan_uid}/confirm", response_model=PlanConfirmation)
async def confirm_plan(
    plan_uid: UUID,
    item: ConfirmPlanSchema,
    user: User,
    request: Request,
    clock: Annotated[Callable[[], datetime], Depends(deps.get_confirmation_clock)],
) -> PlanConfirmation | JSONResponse:
    """Подтвердить один план без автоматического повтора при неизвестном результате."""
    try:
        return await deps.confirmation_command(clock).handle(user.uid, plan_uid, **item.model_dump())
    except (PlanCategoryError, PlanCategoryTypeError) as exc:
        return category_error_response(request, exc)
