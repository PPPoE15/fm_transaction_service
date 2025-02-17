from modules import db_models as orm_models
from modules.web.app.aggregators.models.transaction.transaction import Transaction
from modules.web.app.aggregators.models.user.user import User
from modules.web.app.aggregators.models.user.user_transactions import UserTransactions


def build_orm(user_transactions_agg: UserTransactions) -> orm_models.User:
    """
    Конвертировать агрегатор в orm-модель.

    Args:
       user_transactions_agg : Агрегатор пользователя с транзакциями.
    """
    return orm_models.User(
        **user_transactions_agg.user.to_dict(exclude=["transactions"]),
        transactions=[
            orm_models.Transaction(
                uid=transaction.uid,
                user_uid=transaction.user_uid,
                transaction_date=transaction.transaction_date,
                category=transaction.category,
                money_sum=transaction.money_sum,
                transaction_type=transaction.transaction_type,
                description=transaction.description,
            )
            for transaction in user_transactions_agg.transactions
        ],
    )


def build_agg(orm_user_transactions: orm_models.User) -> UserTransactions:
    """
    Конвертировать orm-модель в агрегатор.

    Args:
        orm_user_transactions: orm-модель пользователя с транзакциями.
    """
    user = User(
        uid=orm_user_transactions.uid,
        name=orm_user_transactions.name,
        email=orm_user_transactions.email,
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
        for transaction in orm_user_transactions.transactions
    ]
    return UserTransactions(
        user=user,
        transactions=transactions,
    )
