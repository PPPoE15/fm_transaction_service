from apps.modules.category.application.exceptions import (
    CategoryAlreadyExistsError,
    CategoryTypeChangeForbiddenError,
)
from apps.modules.category.application.guards import get_own_category
from apps.modules.category.application.uow import AbstractCategoryUnitOfWork
from apps.modules.category.domain import Category, CategoryChanges
from apps.shared import apps_types


class UpdateCommandHandler:
    """Класс обработчика команды изменения статьи."""

    def __init__(
        self,
        unit_of_work: AbstractCategoryUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды изменения статьи.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        category_uid: apps_types.CategoryUID,
        changes: CategoryChanges,
    ) -> Category:
        """
        Изменить статью (частично: только переданные поля).

        Args:
            user_uid: UID пользователя.
            category_uid: UID статьи.
            changes: Новые значения полей.

        Raises:
            CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
            CategoryAlreadyExistsError: Если у пользователя уже есть другая статья с новым названием и типом.
            CategoryTypeChangeForbiddenError: Если меняется тип статьи, по которой уже есть транзакции.
        """
        async with self._uow as uow:
            # Под той же блокировкой, что и создание: иначе параллельные создание и переименование в одно
            # название обе пройдут проверку дубликата
            await uow.repo.lock_user_categories(user_uid)
            category = await get_own_category(uow.repo, user_uid, category_uid)
            type_changed = changes.category_type is not None and changes.category_type != category.category_type
            if type_changed:
                # Строка статьи блокируется до проверки: иначе параллельно вставляемая транзакция не видна, и обе
                # операции проходят — расходная транзакция в статье дохода
                # NOTE(FM-45): обратный порядок (тип сменился и закоммичен до вставки транзакции) закрывает проверка
                # типа при создании транзакции — `FM-400202` в FM-5, пока не реализована.
                await uow.repo.lock_category(category.uid)
                if await uow.repo.has_transactions(category.uid):
                    raise CategoryTypeChangeForbiddenError
            category.update(changes)
            # NOTE(FM-41): дубликат — точное совпадение с учётом регистра, как и уникальное ограничение в БД
            same_name = await uow.repo.get_by_name(user_uid, category.name, category.category_type)
            if same_name is not None and same_name.uid != category.uid:
                raise CategoryAlreadyExistsError
            await uow.repo.update(category)
            await uow.commit()
        return category
