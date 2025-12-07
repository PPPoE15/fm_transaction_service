from apps.web.app.utils.exceptions import BaseNotFoundError


class UserNotFoundError(BaseNotFoundError):
    """Пользователь не найден"""


class ForbiddenError(BaseNotFoundError):
    """Запрет на удаление"""


class TransactionNotFoundError(BaseNotFoundError):
    """Транзакция не найдена"""

