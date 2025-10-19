from apps.web.app.utils.exceptions import BaseNotFoundError


class UserNotFoundError(BaseNotFoundError):
    """Пользователь не найден"""


class TransactionNotFoundError(BaseNotFoundError):
    """Транзакция не найдена"""
