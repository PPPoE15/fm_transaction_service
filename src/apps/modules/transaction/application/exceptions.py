from apps.shared.exceptions import (
    BaseConflictError,
    BaseCustomValidationError,
    BaseNotFoundError,
    BaseUnprocessableError,
)


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


class TransactionCategoryNotFoundError(BaseCustomValidationError):
    """
    Статьи из тела запроса нет у пользователя.

    400, а не 404: не найден не ресурс из пути, а значение поля `category_uid`. Чужая статья — тоже «нет»: ответ
    не раскрывает, что статья с таким UID существует.
    """

    msg = "Статья с данным UID не найдена"
    code = "FM-400201"


class TransactionTypeMismatchError(BaseCustomValidationError):
    """Тип транзакции не совпадает с типом статьи: доход записывается только в статью доходов, расход — расходов."""

    msg = "Тип транзакции не совпадает с типом статьи"
    code = "FM-400202"


class TransactionLimitExceededError(BaseConflictError):
    """Достигнут лимит транзакций на пользователя."""

    msg = "Достигнут лимит транзакций: не больше 100 000 на пользователя"
    code = "FM-409202"
