from typing import Dict

from fastapi import APIRouter, Depends

from modules.web.app.handlers.api.schemas import BaseListResponseSchema, BaseResponseSchema
from .endpoints import deps
from modules.web.app.handlers.deps import async_session_factory
from modules.web.app.application.queries.user import schemas as q_schemas

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
    page_params: PageParamsType,
    user: Annotated[UserInfo, Depends(get_user_info)],
    filter_params: q_schemas.UserFilters = Depends(),
) -> BaseListResponseSchema[q_schemas.TransactionSchema]:
    """
    Список транзакций пользователя.

    Args:
        page_params: Параметры пагинации.
        filter_params: Параметры фильтрации.
        user: Информация об авторизованном пользователе.
    """
    async with async_session_factory() as session:
        system_users_queries = deps.build_queries(
            session=session,
            user_uid=user.uid,
        )
        system_users, total = await system_users_queries.get_list(
            page_params=page_params,
            filter_params=filter_params,
        )
    return BaseListResponseSchema(total=total, content=system_users)


