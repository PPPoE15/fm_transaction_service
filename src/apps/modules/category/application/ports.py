import abc

from apps.modules.category.domain import Category
from apps.shared import apps_types


class AbstractCategoryRepo(abc.ABC):
    """Абстрактный репозиторий."""

    @abc.abstractmethod
    async def create(self, category: Category) -> None:
        """
        Создать категорию пользователя.

        Нарушение уникальности «пользователь + название + тип» (гонка, прошедшая проверку команды)
        переводится в `CategoryAlreadyExistsError`.

        Args:
            category: Агрегатор пользователя и его транзакций.
        """

    @abc.abstractmethod
    async def lock_user_categories(self, user_uid: apps_types.UserUID) -> None:
        """
        Заблокировать набор статей пользователя до конца транзакции единицы работы.

        Нужна перед проверками, которые зависят от всех статей пользователя (дубликат, лимит): два параллельных
        создания иначе оба пройдут проверку. Блокирует и пустой набор, поэтому строки статей не подходят.

        Args:
            user_uid: UID пользователя.
        """

    @abc.abstractmethod
    async def count_by_user(self, user_uid: apps_types.UserUID) -> int:
        """
        Число статей пользователя.

        Args:
            user_uid: UID пользователя.
        """

    @abc.abstractmethod
    async def get_by_name(
        self,
        user_uid: apps_types.UserUID,
        name: apps_types.CategoryName,
        category_type: apps_types.TransactionType,
    ) -> Category | None:
        """
        Статья пользователя с точно таким названием и типом.

        Args:
            user_uid: UID пользователя.
            name: Название статьи.
            category_type: Тип статьи.
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
