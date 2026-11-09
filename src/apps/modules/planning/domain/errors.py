"""Ошибки правил запланированных операций."""

from apps.shared.exceptions import (
    BaseConflictError,
    BaseCustomValidationError,
    BaseError,
    BaseNotFoundError,
    BaseUnprocessableError,
)


class PlanNotFoundError(BaseNotFoundError):
    """Собственный план с указанным UID отсутствует."""

    msg = "План не найден"
    code = "FM-404000"


class CompletedPlanError(BaseConflictError):
    """Выполненный план нельзя менять или повторно подтверждать."""

    msg = "План уже выполнен"
    code = "FM-409401"


class PlanVersionError(BaseConflictError):
    """Версия плана устарела."""

    msg = "План изменён. Обновите данные"
    code = "FM-409402"


class PlanLimitError(BaseConflictError):
    """Превышена квота планов владельца."""

    msg = "Достигнут лимит планов"
    code = "FM-409404"


class InvalidPlanDateError(BaseUnprocessableError):
    """Итоговая дата плана недопустима."""

    msg = "Выберите сегодня или будущую дату в пределах 2000–2099 годов"
    code = "FM-422000"
    field = "planned_date"


class PlanCategoryError(BaseCustomValidationError):
    """Категория отсутствует или принадлежит другому пользователю."""

    msg = "Категория недоступна"
    code = "FM-400201"


class PlanCategoryTypeError(BaseCustomValidationError):
    """Тип выбранной категории не соответствует исходному плану."""

    msg = "Категория должна иметь тот же тип"
    code = "FM-400202"


class PlanOutcomeUnknownError(BaseError):
    """Ответ COMMIT потерян: нельзя обещать откат или повторять создание."""

    msg = "Не удалось подтвердить сохранение операции. Проверьте список перед повторным созданием"
    code = "FM-503401"
