import abc

from apps import apps_types
from apps.web.modules.category.aggregators import Category


class AbstractCategoryRepo(abc.ABC):
    """Абстрактный репозиторий."""

    @abc.abstractmethod
    async def create(self, category: Category) -> None:
        """
        Создать категорию пользователя.

        Args:
            category: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def update(self, category_agg: Category) -> None:
        """
        Обновить транзакции пользователя.

        Args:
            category_agg: UID пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        """
        Удалить категорию пользователя.

        Args:
            category_uid: UID пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        """
        Получить категорию по UID.

        Args:
            category_uid: UID транзакции.
        """
