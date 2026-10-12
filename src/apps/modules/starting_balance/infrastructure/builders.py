from apps.modules.starting_balance.domain import StartingBalance
from apps.modules.starting_balance.infrastructure import orm


def build_orm(starting_balance: StartingBalance) -> orm.StartingBalance:
    """
    Конвертировать агрегат в orm-модель.

    Args:
        starting_balance: Агрегат стартового остатка.
    """
    return orm.StartingBalance(
        user_uid=starting_balance.user_uid,
        amount=starting_balance.amount,
        balance_date=starting_balance.balance_date,
    )


def build(starting_balance: orm.StartingBalance) -> StartingBalance:
    """
    Конвертировать orm-модель в агрегат.

    Args:
        starting_balance: Результат запроса.
    """
    return StartingBalance(
        user_uid=starting_balance.user_uid,
        amount=starting_balance.amount,
        balance_date=starting_balance.balance_date,
    )
