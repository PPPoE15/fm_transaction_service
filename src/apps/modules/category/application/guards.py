from apps.modules.category.application.exceptions import CategoryNotFoundError
from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.modules.category.domain import Category
from apps.shared import apps_types


async def get_own_category(
    repo: AbstractCategoryRepo,
    user_uid: apps_types.UserUID,
    category_uid: apps_types.CategoryUID,
) -> Category:
    """
    Получить статью пользователя.

    Используется и модулем транзакций (через публичный API модуля), поэтому принимает репозиторий,
    а не единицу работы модуля статей.

    Args:
        repo: Репозиторий статей открытой единицы работы.
        user_uid: UID пользователя из токена.
        category_uid: UID статьи.

    Raises:
        CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
    """
    category = await repo.get_by_uid(category_uid)
    if category is None or not category.belongs_to(user_uid):
        raise CategoryNotFoundError
    return category
