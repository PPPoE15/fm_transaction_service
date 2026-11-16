"""Пакетные маршруты таблицы операций."""

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.modules.transaction.api.batch_errors import BatchRoute
from apps.modules.transaction.application.batch_models import BatchDeleteResult, BatchRequest, DeleteItem, UpdateItem
from apps.modules.transaction.application.commands.batch_delete import BatchDeleteCommandHandler
from apps.modules.transaction.application.commands.batch_update import BatchUpdateCommandHandler
from apps.modules.transaction.application.queries.schemas import TransactionSchema
from apps.modules.transaction.infrastructure.uow import TransactionUnitOfWork
from apps.shared.api_schemas import BaseResponseSchema
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

router = APIRouter(tags=["Транзакции"], route_class=BatchRoute)


@router.patch("/transactions/batch")
async def update_batch(
    item_in: BatchRequest[UpdateItem], user: Annotated[UserInfo, Depends(get_user_info)]
) -> BaseResponseSchema[list[TransactionSchema]]:
    """Сохранить все переданные строки одной атомарной командой."""
    handler = BatchUpdateCommandHandler(TransactionUnitOfWork(async_session_factory))
    return BaseResponseSchema(content=await handler.handle(user.uid, item_in.items))


@router.post("/transactions/batch-delete")
async def delete_batch(
    item_in: BatchRequest[DeleteItem], user: Annotated[UserInfo, Depends(get_user_info)]
) -> BatchDeleteResult:
    """Удалить доступные актуальные операции и вернуть результат каждой входной строки."""
    handler = BatchDeleteCommandHandler(TransactionUnitOfWork(async_session_factory))
    return BatchDeleteResult(results=await handler.handle(user.uid, item_in.items))
