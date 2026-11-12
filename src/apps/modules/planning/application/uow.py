"""Единица работы команд планирования."""

from apps.modules.category import AbstractCategoryRepo
from apps.modules.planning.application.ports import AbstractPlanRepo, AbstractRegularTransactionRuleRepo
from apps.modules.transaction import AbstractTransactionRepo
from apps.shared.unit_of_work import AbstractUnitOfWork


class AbstractPlanUnitOfWork(AbstractUnitOfWork):
    """Планы и категории в одной транзакции."""

    plans: AbstractPlanRepo
    categories: AbstractCategoryRepo
    transactions: AbstractTransactionRepo
    regular_transaction_rules: AbstractRegularTransactionRuleRepo
