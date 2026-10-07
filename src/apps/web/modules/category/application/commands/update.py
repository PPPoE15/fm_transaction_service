from apps import apps_types

from .guards import get_own_category
from .uow import AbstractCategoryUnitOfWork


class UpdateCommandHandler:
    """Класс обработчика команды изменения категории."""

    def __init__(
        self,
        unit_of_work: AbstractCategoryUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды изменения категории.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        category_uid: apps_types.CategoryUID,
        name: apps_types.CategoryName,
        money_plan: apps_types.MoneySum,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> None:
        """
        Изменить категорию.

        Args:
            user_uid: UID пользователя.
            category_uid: UID категории.
            name: Имя категории.
            money_plan: Денежная сумма по категории.
            category_type: Тип категории (доход или расход).
            description: Описание категории.

        Raises:
            CategoryNotFoundError: Если статьи нет или она принадлежит другому пользователю.
        """
        async with self._uow as uow:
            category = await get_own_category(uow, user_uid, category_uid)
            category.update(
                name=name,
                money_plan=money_plan,
                category_type=category_type,
                description=description,
            )
            await uow.repo.update(category)
            await uow.commit()
