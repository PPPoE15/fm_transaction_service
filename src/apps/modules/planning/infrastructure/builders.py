"""Преобразование данных между агрегатом и ORM."""

from apps.modules.planning.domain.model import Plan
from apps.modules.planning.infrastructure.orm import PlannedTransaction


def build(row: PlannedTransaction) -> Plan:
    """Построить агрегат из явно перечисленных полей ORM."""
    return Plan.model_validate({name: getattr(row, name) for name in Plan.model_fields})


def build_orm(plan: Plan) -> PlannedTransaction:
    """Построить ORM без связей, способных каскадно изменить факт."""
    return PlannedTransaction(**plan.model_dump())
