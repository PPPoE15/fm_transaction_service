from collections.abc import Sequence

from apps import db_models
from apps.web.app.aggregators.models.transaction.transaction import Transaction


def build_orm(transaction_agg: Transaction) -> db_models.Transaction:
    """
    Конвертировать агрегатор в orm-модель.

    Args:
       transaction_agg : Агрегатор пользователя с транзакциями.
    """
    return db_models.Transaction(
        uid=transaction_agg.uid,
        user_uid=transaction_agg.user_uid,
        transaction_date=transaction_agg.transaction_date,
        category=transaction_agg.category,
        money_sum=transaction_agg.money_sum,
        transaction_type=transaction_agg.transaction_type,
        description=transaction_agg.description,
    )


def build_list(transactions: Sequence[db_models.Transaction]) -> list[Transaction]:
    """
    Конвертировать orm-модель в агрегатор.

    Args:
        transactions: Результаты запроса.
    """
    return [
        Transaction(
            uid=transaction.uid,
            user_uid=transaction.user_uid,
            transaction_date=transaction.transaction_date,
            category=transaction.category,
            money_sum=transaction.money_sum,
            transaction_type=transaction.transaction_type,
            description=transaction.description,
        )
        for transaction in transactions
    ]


def build(transaction: db_models.Transaction) -> Transaction:
    """
    Конвертировать orm-модель в агрегатор.

    Args:
        transaction: Результаты запроса.
    """
    return Transaction(
        uid=transaction.uid,
        user_uid=transaction.user_uid,
        transaction_date=transaction.transaction_date,
        category=transaction.category,
        money_sum=transaction.money_sum,
        transaction_type=transaction.transaction_type,
        description=transaction.description,
    )
