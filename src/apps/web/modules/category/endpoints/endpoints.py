from typing import Annotated

from fastapi import APIRouter, Depends

from apps import apps_types
from apps.utils.schemas import PageParams
from apps.web.core.deps import async_session_factory
from apps.web.core.schemas import BaseListResponseSchema
from apps.web.modules.category.application.commands import CreateCommandHandler
from apps.web.modules.category.application.commands.uow import UnitOfWork
from apps.web.modules.category.application.queries import schemas as q_schemas
from apps.web.security import UserInfo, get_user_info

from . import schemas

router = APIRouter(tags=["Категории"])


@router.get(
    "/categories",
    summary="Получение списка категорий пользователя",
    description="Получить список категорий пользователя",
)
async def get_categories(
    page_params: Annotated[PageParams, Depends()],
    user: Annotated[UserInfo, Depends(get_user_info)],
    filter_params: Annotated[q_schemas.CategoryFilters, Depends()],
) -> BaseListResponseSchema[q_schemas.TransactionSchema]:
    """
    Список категорий пользователя.

    Args:
        page_params: Параметры пагинации.
        filter_params: Параметры фильтрации.
        user: Информация об авторизованном пользователе.
    """
    async with async_session_factory() as session:
        categories_queries = deps.build_queries(session)
        categories, total = await categories_queries.get_categories(
            user_uid=user.uid,
            page_params=page_params,
            filter_params=filter_params,
        )
    return BaseListResponseSchema(total=total, content=categories)


@router.post(
    "/category",
    summary="Создание категории",
    description="Создать категорию",
)
async def create_category(
    item_in: schemas.CreateCategorySchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> None:
    """
    Создать категорию.

    Args:
        item_in: Информация о категории.
        user: Информация об авторизованном пользователе.
    """
    command_handler = CreateCommandHandler(
        unit_of_work=UnitOfWork(async_session_factory),
    )
    await command_handler.handle(
        user_uid=user.uid,
        name=item_in.name,
        money_plan=item_in.money_plan,
        category_type=item_in.category_type,
        description=item_in.description,
    )


@router.delete(
    "/category",
    summary="Удаление категории пользователя",
    description="Удалить категорию пользователя",
)
async def delete_user_category(
    category_uid: apps_types.TransactionUID,
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> None:
    """
    Удалить категорию пользователя.

    Args:
        category_uid: UID категории
        user: Информация об авторизованном пользователе.
    """
    # command_handler = DeleteCommandHandler(
    #     unit_of_work=UnitOfWork(async_session_factory),
    # )
    # await command_handler.handle(
    #     user_uid=user.uid,
    #     category_uid=category_uid,
    # )


@router.patch(
    "/category",
    summary="Изменение категории",
    description="Изменить категорию",
)
async def update_category(
    category_uid: apps_types.TransactionUID,
    item_in: schemas.UpdateCategorySchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> None:
    """
    Изменить категорию.

    Args:
        category_uid: UID категории
        item_in: Измененная информация о категории
        user: Информация об авторизованном пользователе.
    """
    # command_handler = UpdateCommandHandler(
    #     unit_of_work=UnitOfWork(async_session_factory),
    # )
    # await command_handler.handle(
    #     user_uid=user.uid,
    #     category_uid=category_uid,
    #     name=item_in.name,
    #     money_plan=item_in.money_plan,
    #     category_type=item_in.category_type,
    #     description=item_in.description,
    # )
