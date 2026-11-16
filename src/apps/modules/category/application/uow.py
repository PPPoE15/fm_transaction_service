from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.shared.unit_of_work import AbstractUnitOfWork


class AbstractCategoryUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы."""

    repo: AbstractCategoryRepo
