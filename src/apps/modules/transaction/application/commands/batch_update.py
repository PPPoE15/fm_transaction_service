"""Атомарное сохранение пакета проверенных правок."""

from http import HTTPStatus

from apps.modules.category import Category
from apps.modules.transaction.application.batch_models import BatchIssue, BatchTransactionError, UpdateItem
from apps.modules.transaction.application.queries.schemas import CategoryRef, TransactionSchema
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.modules.transaction.domain import Transaction
from apps.shared import apps_types


class BatchUpdateCommandHandler:
    """Проверить все строки и сохранить их одной единицей работы."""

    def __init__(self, unit_of_work: AbstractTransactionUnitOfWork) -> None:
        """Сохранить единицу работы пакетного изменения."""
        self._uow = unit_of_work

    async def handle(self, user_uid: apps_types.UserUID, items: list[UpdateItem]) -> list[TransactionSchema]:
        """Зафиксировать пакет либо вернуть ошибки с приоритетом доступа, версии, категории."""
        async with self._uow as uow:
            transactions = {}
            for item in sorted(items, key=lambda item: item.uid):
                transactions[item.uid] = await uow.transactions_repo.get_by_uid_for_update(item.uid)
            own = self._validate_transactions(user_uid, items, transactions)
            categories = await self._load_categories(uow, items, own)
            checked_categories = self._validate_categories(user_uid, items, own, categories)
            result = []
            for item in items:
                transaction = own[item.uid]
                transaction.update(item.changes.for_transaction(transaction.transaction_date))
                category = checked_categories[transaction.category_uid]
                await uow.transactions_repo.update(transaction)
                result.append(
                    TransactionSchema(
                        **transaction.model_dump(exclude={"user_uid", "category_uid"}),
                        category=CategoryRef(uid=category.uid, name=category.name),
                    )
                )
            await uow.commit()
        return result

    @staticmethod
    def _validate_transactions(
        user_uid: apps_types.UserUID,
        items: list[UpdateItem],
        transactions: dict[apps_types.TransactionUID, Transaction | None],
    ) -> dict[apps_types.TransactionUID, Transaction]:
        """Сначала проверить доступ ко всем строкам, затем версии доступных операций."""
        missing, conflicts = [], []
        own = {}
        for index, item in enumerate(items):
            transaction = transactions[item.uid]
            if transaction is None or not transaction.belongs_to(user_uid):
                missing.append(BatchIssue(index=index, uid=item.uid, code="FM-404000", message="Операция не найдена"))
                continue
            own[item.uid] = transaction
            if transaction.version != item.expected_version:
                conflicts.append(
                    BatchIssue(
                        index=index,
                        uid=item.uid,
                        field="expected_version",
                        code="FM-409204",
                        message="Версия операции изменилась",
                    )
                )
        if missing:
            raise BatchTransactionError(HTTPStatus.NOT_FOUND, missing)
        if conflicts:
            raise BatchTransactionError(HTTPStatus.CONFLICT, conflicts)
        return own

    @staticmethod
    async def _load_categories(
        uow: AbstractTransactionUnitOfWork,
        items: list[UpdateItem],
        transactions: dict[apps_types.TransactionUID, Transaction],
    ) -> dict[apps_types.CategoryUID, Category | None]:
        """Прочитать итоговые категории под блокировками в стабильном порядке UID."""
        uids = {item.changes.category_uid or transactions[item.uid].category_uid for item in items}
        return {uid: await uow.categories_repo.get_by_uid_for_key_share(uid) for uid in sorted(uids)}

    @staticmethod
    def _validate_categories(
        user_uid: apps_types.UserUID,
        items: list[UpdateItem],
        transactions: dict[apps_types.TransactionUID, Transaction],
        categories: dict[apps_types.CategoryUID, Category | None],
    ) -> dict[apps_types.CategoryUID, Category]:
        """Проверить принадлежность и совместимость категории до записи первой операции."""
        errors = []
        for index, item in enumerate(items):
            transaction = transactions[item.uid]
            category = categories[item.changes.category_uid or transaction.category_uid]
            if category is None or not category.belongs_to(user_uid):
                errors.append(
                    BatchIssue(
                        index=index,
                        uid=item.uid,
                        field="changes.category_uid",
                        code="FM-400201",
                        message="Статья с данным UID не найдена",
                    )
                )
            elif category.category_type != transaction.transaction_type:
                errors.append(
                    BatchIssue(
                        index=index,
                        uid=item.uid,
                        field="changes.category_uid",
                        code="FM-400202",
                        message="Тип транзакции не совпадает с типом статьи",
                    )
                )
        if errors:
            raise BatchTransactionError(HTTPStatus.BAD_REQUEST, errors)
        return {uid: category for uid, category in categories.items() if category is not None}
