from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from starlette import status

from apps.modules.category.application.commands import (
    CreateCommandHandler,
    UpdateCommandHandler,
)
from apps.modules.category.application.queries import schemas as q_schemas
from apps.modules.category.application.queries.list import ListCategories
from apps.modules.category.domain import CategoryChanges
from apps.modules.category.infrastructure.uow import UnitOfWork
from apps.shared import apps_types
from apps.shared.api_schemas import BaseListResponseSchema
from apps.shared.db.session import async_session_factory
from apps.shared.schemas import PageParams
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
) -> BaseListResponseSchema[q_schemas.CategorySchema]:
    """
    Список категорий пользователя.

    Args:
        page_params: Параметры пагинации.
        filter_params: Параметры фильтрации.
        user: Информация об авторизованном пользователе.
    """
    async with async_session_factory() as session:
        categories_queries = ListCategories(session)
        categories, total = await categories_queries.execute(
            user_uid=user.uid,
            page_params=page_params,
            filter_params=filter_params,
        )
    return BaseListResponseSchema(total=total, content=categories)


@router.post(
    "/categories",
    status_code=status.HTTP_201_CREATED,
    summary="Создание статьи",
    description=(
        "Создать статью дохода или расхода. 409 `FM-409101` — у пользователя уже есть статья с таким названием "
        "и типом; 409 `FM-409103` — достигнут лимит в 100 статей."
    ),
)
async def create_category(
    item_in: schemas.CreateCategorySchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
    request: Request,
    response: Response,
) -> q_schemas.CategorySchema:
    """
    Создать статью.

    Args:
        item_in: Информация о статье.
        user: Информация об авторизованном пользователе.
        request: Запрос: от его пути строится `Location` созданной статьи.
        response: Ответ: в него добавляется `Location`.
    """
    command_handler = CreateCommandHandler(
        unit_of_work=UnitOfWork(async_session_factory),
    )
    category = await command_handler.handle(
        user_uid=user.uid,
        name=item_in.name,
        money_plan=item_in.money_plan,
        category_type=item_in.category_type,
        description=item_in.description,
    )
    # От пути запроса, а не фиксированный: так префикс `/transaction` (и переходный путь без него) сохраняется.
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{category.uid}"
    # Все отдаваемые поля есть в агрегате, только что сохранённом командой, — повторно читать из БД не нужно.
    return q_schemas.CategorySchema.model_validate(category)


@router.patch(
    "/categories/{category_uid}",
    summary="Изменение статьи",
    description=(
        "Частичное изменение: меняются только переданные поля, `null` очищает план и описание. "
        "404 — статьи нет или она чужая; 409 `FM-409101` — у пользователя уже есть статья с таким названием и типом; "
        "400 `FM-400101` — нельзя сменить тип статьи, по которой уже есть транзакции."
    ),
)
async def update_category(
    category_uid: apps_types.CategoryUID,
    item_in: schemas.UpdateCategorySchema,
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> q_schemas.CategorySchema:
    """
    Изменить статью.

    Args:
        category_uid: UID статьи.
        item_in: Новые значения переданных полей.
        user: Информация об авторизованном пользователе.
    """
    command_handler = UpdateCommandHandler(
        unit_of_work=UnitOfWork(async_session_factory),
    )
    category = await command_handler.handle(
        user_uid=user.uid,
        category_uid=category_uid,
        changes=CategoryChanges(**item_in.model_dump(exclude_unset=True)),
    )
    # Статья после изменения — в агрегате, сохранённом командой: повторно читать из БД не нужно.
    return q_schemas.CategorySchema.model_validate(category)
