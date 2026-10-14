from apps.shared.exceptions import BaseNotFoundError, BaseUnprocessableError


class UserNotFoundError(BaseNotFoundError):
    """Пользователь не найден"""


class TransactionNotFoundError(BaseNotFoundError):
    """
    Транзакция не найдена.

    Чужая транзакция для пользователя тоже «не найдена»: ответ не раскрывает, что запись с таким UID существует.
    """

    msg = "Транзакция с данным UID не найдена"


class InvalidDateRangeError(BaseUnprocessableError):
    """Конец периода предшествует его началу."""

    code = "FM-422001"
    field = "before"
    msg = "Конец периода не может быть раньше начала"
