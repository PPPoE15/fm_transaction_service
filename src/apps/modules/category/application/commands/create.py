from apps.modules.category.application.exceptions import CategoryAlreadyExistsError, CategoryLimitExceededError
from apps.modules.category.application.uow import AbstractCategoryUnitOfWork
from apps.modules.category.domain import MAX_CATEGORIES_PER_USER, Category
from apps.shared import apps_types


class CreateCommandHandler:
    """Класс обработчика команды создания категории."""

    def __init__(
        self,
        unit_of_work: AbstractCategoryUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды создания категории.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        name: apps_types.CategoryName,
        user_uid: apps_types.UserUID,
        money_plan: apps_types.MoneySum | None,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> Category:
        """
        Создать категорию.

        Args:
            name: Имя категории.
            user_uid: UID пользователя.
            money_plan: Плановая сумма за месяц; `None` — план не задан.
            category_type: Тип категории (доход или расход).
            description: Описание категории.

        Raises:
            CategoryAlreadyExistsError: Если у пользователя уже есть статья с таким названием и типом.
            CategoryLimitExceededError: Если у пользователя уже `MAX_CATEGORIES_PER_USER` статей.
        """
        category_agg = Category.create(
            name=name,
            user_uid=user_uid,
            money_plan=money_plan,
            category_type=category_type,
            description=description,
        )
        async with self._uow as uow:
            await uow.repo.lock_user_categories(user_uid)
            if await uow.repo.get_by_name(user_uid, name, category_type) is not None:
                raise CategoryAlreadyExistsError
            if await uow.repo.count_by_user(user_uid) >= MAX_CATEGORIES_PER_USER:
                raise CategoryLimitExceededError
            await uow.repo.create(category_agg)
            await uow.commit()
        return category_agg
