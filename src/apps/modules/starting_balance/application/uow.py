from apps.modules.starting_balance.application.ports import AbstractStartingBalanceRepo
from apps.shared.unit_of_work import AbstractUnitOfWork


class AbstractStartingBalanceUnitOfWork(AbstractUnitOfWork):
    """Абстрактная единица работы для стартового остатка."""

    starting_balances_repo: AbstractStartingBalanceRepo
