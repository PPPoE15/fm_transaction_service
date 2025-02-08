from typing import Dict

from fastapi import APIRouter, Depends

from modules.utils.schemas import PageParams
from modules.web.app.application.queries.user import schemas as q_schemas
from modules.web.app.handlers.api.schemas import BaseListResponseSchema
from modules.web.app.handlers.deps import async_session_factory

from . import deps

router = APIRouter(tags=["Пользователь"])


@router.get("/ping")
async def demo() -> Dict[str, str]:
    """Демонстрационный эндпойнт"""
    return {"ping": "pong"}


@router.get(
    "/transactions",
    summary="Получение списка транзакций пользователя",
    description="Получить список транзакций пользователя",
)
async def get_user_transactions(
    page_params: PageParams = Depends(),
    filter_params: q_schemas.TransactionFilters = Depends(),
) -> BaseListResponseSchema[q_schemas.TransactionSchema]:
    """
    Список транзакций пользователя.

    Args:
        page_params: Параметры пагинации.
        filter_params: Параметры фильтрации.
        user: Информация об авторизованном пользователе.
    """
    async with async_session_factory() as session:
        transactions_queries = deps.build_queries(session)
        transactions, total = await transactions_queries.get_transactions(
            page_params=page_params,
            filter_params=filter_params,
        )
    return BaseListResponseSchema(total=total, content=transactions)
