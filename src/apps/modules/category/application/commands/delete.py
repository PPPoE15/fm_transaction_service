from apps.modules.category.application.guards import get_own_category
from apps.modules.category.application.uow import AbstractCategoryUnitOfWork
from apps.shared import apps_types


class DeleteCommandHandler:
    """Класс обработчика команды удаления категории."""

    def __init__(
        self,
        unit_of_work: AbstractCategoryUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды удаления категории.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        category_uid: apps_types.CategoryUID,
    ) -> None:
        """
        Удалить категорию.

        Args:
            user_uid: UID пользователя.
            category_uid: UID категории.

        Raises:
            CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
        """
        async with self._uow as uow:
            await get_own_category(uow.repo, user_uid, category_uid)
            # TODO(FM-4): по контракту статью с транзакциями удалять нельзя (409). Сейчас каскад
            # Category.transactions (delete-orphan) удаляет вместе со статьёй все её транзакции.
            await uow.repo.delete(category_uid)
            await uow.commit()
