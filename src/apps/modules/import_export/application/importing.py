from apps.modules.import_export.application.parsing import read_file_records, validate_records
from apps.modules.import_export.domain.models import FileFormat, TransactionKind
from apps.modules.transaction import (
    MAX_TRANSACTIONS_PER_USER,
    Transaction,
    TransactionLimitExceededError,
    TransactionUnitOfWork,
)
from apps.shared import apps_types


class ImportCommandHandler:
    """Сопоставить категории и сохранить весь файл одной транзакцией."""

    def __init__(self, unit_of_work: TransactionUnitOfWork) -> None:
        """Получить единицу работы с общими репозиториями операций и категорий."""
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        content: bytes,
        *,
        transaction_type: TransactionKind,
        file_format: FileFormat,
        filename: str,
        content_type: str | None,
    ) -> int:
        """Проверить весь файл, владельца, тип и квоту; применить один commit."""
        raw_records = read_file_records(
            content,
            transaction_type=transaction_type,
            file_format=file_format,
            filename=filename,
            content_type=content_type,
        )
        kind = apps_types.TransactionType(transaction_type)
        async with self._uow as uow:
            count = await uow.transactions_repo.count_by_user_for_update(user_uid)
            categories = await uow.categories_repo.get_all_for_import(user_uid, kind)
            mapping: dict[str, list[apps_types.CategoryUID]] = {}
            for category in categories:
                mapping.setdefault(category.name.strip(), []).append(category.uid)

            def category_matches(name: str) -> int:
                """Посчитать точные совпадения в заблокированном наборе категорий владельца."""
                return len(mapping.get(name, []))

            records = validate_records(raw_records, category_matches)
            transactions = [
                Transaction.create(
                    user_uid=user_uid,
                    transaction_date=record.transaction_date,
                    category_uid=mapping[record.category_name][0],
                    money_sum=record.money_sum,
                    transaction_type=kind,
                    description=record.description,
                )
                for record in records
            ]
            if count + len(transactions) > MAX_TRANSACTIONS_PER_USER:
                raise TransactionLimitExceededError
            for transaction in transactions:
                await uow.transactions_repo.create(transaction)
            await uow.commit()
        return len(records)
