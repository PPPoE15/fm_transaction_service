class BaseError(Exception):
    """
    Базовая ошибка.

    Attributes:
        code: Собственный код ошибки (`FM-XXXNNN`); не задан — в ответе код по умолчанию для HTTP-статуса.
    """

    msg: str = ""
    code: str | None = None

    def __init__(self, msg: str | None = None) -> None:
        """
        Конструктор базовой ошибки.

        Args:
            msg: Сообщение ошибки.
        """
        if msg:
            self.msg = msg


class BaseCustomValidationError(BaseError):
    """Базовая ошибка серверной валидации (код 400, см. `custom_validation_exception_handler`)."""


class BaseUnprocessableError(BaseError):
    """
    Базовая ошибка недопустимого значения поля, которое не проверить схемой запроса (код 422).

    Attributes:
        field: Поле запроса, не прошедшее проверку (попадает в список validation ответа).
    """

    field: str | None = None


class BaseNotFoundError(BaseError):
    """Базовая ошибка не найденного ресурса (код 404)."""


class BaseConflictError(BaseError):
    """Базовая ошибка конфликта с текущим состоянием ресурса (код 409)."""


class BaseForbiddenError(BaseError):
    """Базовая ошибка доступа (код 403)."""
