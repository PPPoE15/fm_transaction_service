from apps.web.utils.exceptions import BaseNotFoundError


class UserNotFoundError(BaseNotFoundError):
    """Пользователь не найден"""


class TransactionNotFoundError(BaseNotFoundError):
    """
    Транзакция не найдена.

    Чужая транзакция для пользователя тоже «не найдена»: ответ не раскрывает, что запись с таким UID существует.
    """

    msg = "Транзакция с данным UID не найдена"


class CategoryNotFoundError(BaseNotFoundError):
    """Статья транзакции не найдена (или принадлежит другому пользователю)."""

    msg = "Статья с данным UID не найдена"
