from enum import Enum


class TransactionType(str, Enum):
    """Типы транзакций"""

    INCOME = "income"
    OUTCOME = "outcome"
