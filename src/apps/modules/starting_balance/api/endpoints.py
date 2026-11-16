from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from apps.modules.starting_balance.application.exceptions import StartingBalanceNotFoundError
from apps.modules.starting_balance.application.queries import schemas as q_schemas
from apps.modules.starting_balance.application.queries.get import StartingBalanceQueries
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

from . import deps, schemas

router = APIRouter(tags=["Остаток"])


@router.get(
    "/starting-balance",
    summary="Стартовый остаток",
    description="Получить стартовый остаток пользователя; 404, если он ещё не задан.",
)
async def get_starting_balance(
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> q_schemas.StartingBalanceSchema:
    """
    Стартовый остаток пользователя.

    Args:
        user: Информация об авторизованном пользователе.
    """
    async with async_session_factory() as session:
        starting_balance = await StartingBalanceQueries(session).get(user_uid=user.uid)
    if starting_balance is None:
        raise StartingBalanceNotFoundError
    return starting_balance


@router.post(
    "/starting-balance",
    status_code=status.HTTP_201_CREATED,
    summary="Задание стартового остатка",
    description=(
        "Задать стартовый остаток. Задаётся один раз и потом не изменяется и не удаляется: повторный вызов — 409. "
        "Транзакцию не создаёт."
    ),
)
async def create_starting_balance(
    item_in: schemas.StartingBalanceCreateSchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
    today: Annotated[date, Depends(deps.get_today)],
) -> q_schemas.StartingBalanceSchema:
    """
    Задать стартовый остаток пользователя.

    Args:
        item_in: Сумма и необязательная дата остатка.
        user: Информация об авторизованном пользователе.
        today: Текущая дата.
    """
    command_handler = deps.build_create_starting_balance_command_handler()
    starting_balance = await command_handler.handle(
        user_uid=user.uid,
        amount=item_in.amount,
        balance_date=item_in.balance_date,
        today=today,
    )
    # Остаток неизменяем и все его отдаваемые поля есть в агрегате — повторно читать из БД не нужно.
    return q_schemas.StartingBalanceSchema.model_validate(starting_balance)
