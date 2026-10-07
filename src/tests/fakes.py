"""
Фейки репозиториев и единиц работы для юнит-тестов обработчиков команд.

Это простое хранилище в памяти: правила (владелец записи, существование статьи) живут в агрегатах
и обработчиках, фейки их не повторяют. Транзакции БД не моделируются: commit/rollback только отмечаются.
"""

from typing import Self

from apps import apps_types
from apps.web.modules.category.aggregators import Category
from apps.web.modules.category.application.commands.uow import AbstractCategoryUnitOfWork
from apps.web.modules.category.infrastructure.db.repos import AbstractCategoryRepo
from apps.web.modules.transaction.aggregators import Transaction
from apps.web.modules.transaction.application.commands.uow import AbstractTransactionUnitOfWork
from apps.web.modules.transaction.infrastructure.db.repos import AbstractTransactionRepo


class InMemoryCategoryRepo(AbstractCategoryRepo):
    """Репозиторий статей в памяти."""

    def __init__(self) -> None:
        """Пустое хранилище."""
        self.items: dict[apps_types.CategoryUID, Category] = {}

    async def create(self, category: Category) -> None:
        self.items[category.uid] = category.model_copy()

    async def update(self, category_agg: Category) -> None:
        self.items[category_agg.uid] = category_agg.model_copy()

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        self.items.pop(category_uid)

    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        category = self.items.get(category_uid)
        return category.model_copy() if category else None


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


class _FakeUnitOfWorkMixin:
    """Отметки о commit/rollback вместо транзакции БД."""

    committed = False

    async def __aenter__(self) -> Self:
        return self

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        """Откат не моделируется: изменения в памяти остаются (тесты проверяют, что их не было)."""


class FakeCategoryUnitOfWork(_FakeUnitOfWorkMixin, AbstractCategoryUnitOfWork):
    """Единица работы модуля статей в памяти."""

    def __init__(self, categories: InMemoryCategoryRepo) -> None:
        """
        Единица работы поверх хранилища статей.

        Args:
            categories: Хранилище статей.
        """
        self.repo = categories


class FakeTransactionUnitOfWork(_FakeUnitOfWorkMixin, AbstractTransactionUnitOfWork):
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
