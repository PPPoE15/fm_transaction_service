from modules.web.app.utils.exceptions import BaseError


class EventHeadersValidationError(BaseError):
    """Ошибка валидации заголовков события."""


class EventMessageTypeValidationError(BaseError):
    """Ошибка не найденного типа события."""


class EventMessageHandlerNotFoundError(BaseError):
    """Ошибка не найденного обработчика события."""
