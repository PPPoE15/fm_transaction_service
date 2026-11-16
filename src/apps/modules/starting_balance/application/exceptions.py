from apps.shared.exceptions import BaseConflictError, BaseNotFoundError


class StartingBalanceNotFoundError(BaseNotFoundError):
    """Стартовый остаток пользователя ещё не задан."""

    msg = "Стартовый остаток ещё не задан"
    code = "FM-404201"


class StartingBalanceAlreadyExistsError(BaseConflictError):
    """Стартовый остаток уже задан: он задаётся один раз и не изменяется."""

    msg = "Стартовый остаток уже задан и не может быть изменён"
    code = "FM-409201"
