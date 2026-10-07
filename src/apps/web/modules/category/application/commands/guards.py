from apps import apps_types
from apps.web.modules.category.aggregators import Category

from .exceptions import CategoryNotFoundError
from .uow import AbstractCategoryUnitOfWork


async def get_own_category(
    uow: AbstractCategoryUnitOfWork,
    user_uid: apps_types.UserUID,
    category_uid: apps_types.CategoryUID,
) -> Category:
    """
    Получить статью пользователя.

    Args:
        uow: Открытая единица работы.
        user_uid: UID пользователя из токена.
        category_uid: UID статьи.

    Raises:
        CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
    """
    category = await uow.repo.get_by_uid(category_uid)
    if category is None or not category.belongs_to(user_uid):
        raise CategoryNotFoundError
    return category
