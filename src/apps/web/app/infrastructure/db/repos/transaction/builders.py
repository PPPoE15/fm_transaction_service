from apps import db_models as orm_models
from apps.web.app.aggregators.models.transaction import Transaction
from apps.web.app.aggregators.models.user.user import User
from apps.web.app.aggregators.models.user.user_transactions import UserTransactions


def build_orm(transactions_agg: Transaction) -> orm_models.Transaction:
    """
    Конвертировать агрегатор в orm-модель.

    Args:
       transactions_agg : Агрегатор транзакции.
    """
    # return orm_models.Transaction(
    #     uid=transactions_agg.uid,
    #     user_uid=transactions_agg.user_uid,
    #     transaction_date=transactions_agg.transaction_date,
    #     category=transactions_agg.category,
    #     money_sum=transactions_agg.money_sum,
    #     transaction_type=transactions_agg.transaction_type,
    #     description=transactions_agg.description,
    # )
    return orm_models.Transaction(
        **transactions_agg.model_dump()
    )


def build_agg(orm_transactions: orm_models.Transaction) -> Transaction:
    """
    Конвертировать orm-модель в агрегатор.

    Args:
        orm_user_transactions: orm-модель пользователя с транзакциями.
    """
    user = User(
        uid=orm_transactions.uid,
        name=orm_transactions.name,
        email=orm_transactions.email,
    )
    transactions = [
        Transaction(
            uid=transaction.uid,
            user_uid=transaction.user_uid,
            transaction_date=transaction.transaction_date,
            category=transaction.category,
            money_sum=transaction.money_sum,
            transaction_type=transaction.transaction_type,
            description=transaction.description,
        )
        for transaction in orm_transactions.transactions
    ]

