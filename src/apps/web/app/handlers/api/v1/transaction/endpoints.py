from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from apps.utils.schemas import PageParams
from apps.web.app.application.queries.user import schemas as q_schemas
from apps.web.app.handlers.api.schemas import BaseListResponseSchema
from apps.web.app.handlers.deps import async_session_factory
from apps.web.security import UserInfo, get_user_info

from . import deps, schemas

router = APIRouter(tags=["Пользователь"])


@router.get(
    "/transactions",
    summary="Получение списка транзакций пользователя",
    description="Получить список транзакций пользователя",
)
async def get_transactions(
    page_params: Annotated[PageParams, Depends()],
    user: Annotated[UserInfo, Depends(get_user_info)],
    filter_params: Annotated[q_schemas.TransactionFilters, Depends()],
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
            user_uid=user.uid,
            page_params=page_params,
            filter_params=filter_params,
        )
    return BaseListResponseSchema(total=total, content=transactions)


@router.post(
    "/transactions",
    summary="Создание транзакции пользователя",
    description="Создать транзакцию пользователя",
)
async def create_user_transaction(
    item_in: schemas.CreateTransactionSchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
    page_params: Annotated[PageParams, Depends()],
) -> BaseListResponseSchema[q_schemas.TransactionSchema]:
    """
    Создать транзакцию пользователя.

    Args:
        page_params: Параметры пагинации.
        item_in: Информация о транзакции.
        user: Информация об авторизованном пользователе.
    """
    command_handler = deps.build_transaction_create_command_handler()
    await command_handler.handle(
        user_uid=user.uid,
        transaction_date=item_in.transaction_date,
        category=item_in.category,
        money_sum=item_in.money_sum,
        transaction_type=item_in.transaction_type,
        description=item_in.description,
    )
    async with async_session_factory() as session:
        transactions_queries = deps.build_queries(session)
        transactions, total = await transactions_queries.get_transactions(
            user_uid=user.uid,
            page_params=page_params,
            filter_params=q_schemas.TransactionFilters(),
        )
    return BaseListResponseSchema(total=total, content=transactions)
