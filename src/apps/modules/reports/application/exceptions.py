"""Ошибки построения финансовых отчётов."""

from apps.shared.exceptions import BaseConflictError, BaseUnprocessableError


class StartingBalanceRequiredError(BaseConflictError):
    """Для дневного остатка требуется явно заданная стартовая сумма."""

    code = "FM-409203"
    msg = "Для отображения графика задайте стартовый остаток"


class InvalidHistoryRangeError(BaseUnprocessableError):
    """Диапазон дневного отчёта нарушает ограничения контракта."""

    code = "FM-422000"
    field = "date_to"
    msg = "Выберите от 1 до 366 дней: начало не позже конца, конец не позже сегодня"
