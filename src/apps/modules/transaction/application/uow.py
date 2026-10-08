from apps.modules.category import AbstractCategoryRepo
from apps.modules.transaction.application.ports import AbstractTransactionRepo
from apps.shared.unit_of_work import AbstractUnitOfWork


class AbstractTransactionUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы для пользователя и его транзакций."""

    transactions_repo: AbstractTransactionRepo
    # Статьи нужны, чтобы проверить, что транзакция привязывается к статье того же пользователя.
    categories_repo: AbstractCategoryRepo
