from apps.shared.exceptions import BaseNotFoundError


class UserNotFoundError(BaseNotFoundError):
    """Пользователь не найден"""


class TransactionNotFoundError(BaseNotFoundError):
    """
    Транзакция не найдена.

    Чужая транзакция для пользователя тоже «не найдена»: ответ не раскрывает, что запись с таким UID существует.
    """

    msg = "Транзакция с данным UID не найдена"
