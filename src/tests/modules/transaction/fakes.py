"""Фейки модуля транзакций: хранилище в памяти и единица работы поверх него."""

from apps.modules.transaction.application.ports import AbstractTransactionRepo
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.domain import Transaction
from apps.shared import apps_types
from tests.modules.category.fakes import InMemoryCategoryRepo
from tests.modules.fakes import FakeUnitOfWorkMixin


class InMemoryTransactionRepo(AbstractTransactionRepo):
    """Репозиторий транзакций в памяти."""

    def __init__(self) -> None:
        """Пустое хранилище."""
        self.items: dict[apps_types.TransactionUID, Transaction] = {}

    async def create(self, transaction: Transaction) -> None:
        self.items[transaction.uid] = transaction.model_copy()

    async def update(self, transaction_agg: Transaction) -> None:
        self.items[transaction_agg.uid] = transaction_agg.model_copy()

    async def delete(self, transaction_uid: apps_types.TransactionUID) -> None:
        self.items.pop(transaction_uid)

    async def get_by_uid(self, transaction_uid: apps_types.TransactionUID) -> Transaction | None:
        transaction = self.items.get(transaction_uid)
        return transaction.model_copy() if transaction else None

    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> list[Transaction] | None:
        return [item.model_copy() for item in self.items.values() if item.user_uid == user_uid]


class FakeTransactionUnitOfWork(FakeUnitOfWorkMixin, AbstractTransactionUnitOfWork):
    """Единица работы модуля транзакций в памяти."""

    def __init__(self, transactions: InMemoryTransactionRepo, categories: InMemoryCategoryRepo) -> None:
        """
        Единица работы поверх хранилищ транзакций и статей.

        Args:
            transactions: Хранилище транзакций.
            categories: Хранилище статей (общее с модулем статей).
        """
        self.transactions_repo = transactions
        self.categories_repo = categories
