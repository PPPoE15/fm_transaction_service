class BaseError(Exception):
    """Базовая ошибка."""

    msg: str = ""

    def __init__(self, msg: str | None = None) -> None:
        """
        Конструктор базовой ошибки.

        Args:
            msg: Сообщение ошибки.
        """
        if msg:
            self.msg = msg


class BaseCustomValidationError(BaseError):
    """Базовая ошибка серверной валидации (код 422)."""


class BaseNotFoundError(BaseError):
    """Базовая ошибка не найденного ресурса (код 404)."""


class BaseForbiddenError(BaseError):
    """Базовая ошибка доступа (код 403)."""
