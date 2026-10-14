from apps.shared.exceptions import BaseConflictError, BaseCustomValidationError, BaseNotFoundError


class CategoryNotFoundError(BaseNotFoundError):
    """
    Статья не найдена.

    Чужая статья для пользователя тоже «не найдена»: ответ не раскрывает, что запись с таким UID существует.
    """

    msg = "Статья с данным UID не найдена"


class CategoryAlreadyExistsError(BaseConflictError):
    """У пользователя уже есть статья с таким названием и типом."""

    msg = "Статья с таким названием и типом уже есть"
    code = "FM-409101"


class CategoryLimitExceededError(BaseConflictError):
    """Достигнут лимит статей на пользователя."""

    msg = "Достигнут лимит статей: не больше 100 на пользователя"
    code = "FM-409103"


class CategoryTypeChangeForbiddenError(BaseCustomValidationError):
    """Тип статьи, по которой уже есть транзакции, сменить нельзя: тип транзакций должен совпадать с типом статьи."""

    msg = "Нельзя сменить тип статьи, по которой уже есть транзакции"
    code = "FM-400101"
