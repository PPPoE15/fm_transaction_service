"""Контракт HTTP для управления регулярными операциями."""

from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import ConfigDict, Field, model_validator

from apps.modules.planning.api import deps
from apps.modules.planning.api.endpoints import Clock, User
from apps.modules.planning.api.schemas import PlanDateIn
from apps.modules.planning.application.regular import RegularOperationRuleInput
from apps.modules.planning.application.regular_queries import RegularQueries
from apps.modules.planning.application.regular_schemas import (
    ConversionResult,
    RegularOperationList,
    RegularOperationView,
)
from apps.modules.planning.domain.model import Money
from apps.modules.planning.domain.schedule import Frequency
from apps.shared.api_types import DescriptionIn
from apps.shared.db.session import async_session_factory
from apps.shared.schemas import Base, PageParams

router = APIRouter(tags=["Планирование"])
URL = "/regular-operations"


class CreateRegularOperationSchema(RegularOperationRuleInput):
    """Строгие входные даты и запрет лишних полей."""

    model_config = ConfigDict(extra="forbid")
    first_date: PlanDateIn
    end_date: PlanDateIn | None = None


class ConvertRegularOperationSchema(CreateRegularOperationSchema):
    """Новые параметры регулярной операции и версия исходного плана."""

    expected_version: int = Field(ge=1, strict=True)


class UpdateRegularOperationSchema(Base):
    """Частичные параметры с различением пропуска и очистки."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    first_date: PlanDateIn | None = None
    end_date: PlanDateIn | None = None
    frequency: Frequency | None = None
    category_uid: UUID | None = None
    money_sum: Money | None = None
    description: DescriptionIn | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        """Проверить наличие изменения и разрешённые значения null."""
        changed = self.model_fields_set - {"expected_version"}
        if not changed:
            msg = "Необходимо передать хотя бы одно изменяемое поле"
            raise ValueError(msg)
        for field in changed - {"description", "end_date"}:
            if getattr(self, field) is None:
                msg = f"Поле {field} не может быть null"
                raise ValueError(msg)
        return self


class RegularOperationPageParams(PageParams):
    """Границы страницы регулярных операций."""

    skip: int = Field(Query(default=0, ge=0))
    limit: int = Field(Query(default=500, ge=1, le=500))


@router.get(URL)
async def list_regular_operations(
    user: User,
    clock: Clock,
    page: Annotated[RegularOperationPageParams, Depends()],
    source_plan_uid: UUID | None = None,
) -> RegularOperationList:
    """Прочитать страницу собственных регулярных операций."""
    async with async_session_factory() as session:
        return await RegularQueries(session).list(user.uid, page, source_plan_uid, clock())


@router.post(URL, status_code=status.HTTP_201_CREATED)
async def create_regular_operation(
    item: CreateRegularOperationSchema, user: User, clock: Clock
) -> RegularOperationView:
    """Создать регулярную операцию и рассчитанные платежи."""
    return await deps.regular_commands(clock).create(user.uid, item)


@router.get(URL + "/{operation_uid}")
async def get_regular_operation(operation_uid: UUID, user: User, clock: Clock) -> RegularOperationView:
    """Прочитать собственную регулярную операцию."""
    async with async_session_factory() as session:
        return await RegularQueries(session).get(user.uid, operation_uid, clock())


@router.patch(URL + "/{operation_uid}")
async def update_regular_operation(
    operation_uid: UUID, item: UpdateRegularOperationSchema, user: User, clock: Clock
) -> RegularOperationView:
    """Изменить условия регулярной операции и пересчитать платежи."""
    changes = item.model_dump(exclude_unset=True, exclude={"expected_version"})
    return await deps.regular_commands(clock).update(user.uid, operation_uid, changes, item.expected_version)


@router.delete(URL + "/{operation_uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regular_operation(
    operation_uid: UUID, user: User, clock: Clock, expected_version: Annotated[int, Query(ge=1)]
) -> Response:
    """Удалить регулярную операцию и её невыполненные платежи."""
    await deps.regular_commands(clock).delete(user.uid, operation_uid, expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/planned-operations/{plan_uid}/recurrence", status_code=status.HTTP_201_CREATED)
async def convert_plan(
    plan_uid: UUID, item: ConvertRegularOperationSchema, user: User, clock: Clock
) -> ConversionResult:
    """Сделать план регулярным с учётом состояния источника."""
    return await deps.regular_commands(clock).convert(user.uid, plan_uid, item, item.expected_version)
