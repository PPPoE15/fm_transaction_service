from apps import apps_types
from apps.web.modules.category.aggregators import Category

from .uow import AbstractCategoryUnitOfWork


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
        money_plan: apps_types.MoneySum,
        category_type: apps_types.TransactionType,
        description: apps_types.Description,
    ) -> None:
        """
        Создать категорию.

        Args:
            name: Имя категории.
            user_uid: UID пользователя.
            money_plan: Денежная сумма по категории.
            category_type: Тип категории (доход или расход).
            description: Описание категории.
        """
        category_agg = Category.create(
            name=name,
            user_uid=user_uid,
            money_plan=money_plan,
            category_type=category_type,
            description=description,
        )
        async with self._uow as uow:
            await uow.repo.create(category_agg)
            await uow.commit()
