from datetime import date, datetime
from zoneinfo import ZoneInfo

from apps.shared.datetime_tz import aware_now


def get_today() -> date:
    """
    Текущая дата, по которой месяцы делятся на наступившие и будущие.

    Вынесена в зависимость, чтобы расчёт не брал время сам и в тестах дату можно было подменить.
    """
    # NOTE(FM-27): дата берётся по UTC, а `transaction_date` — локальное время без часового пояса. В первые часы
    # нового месяца по местному времени (UTC+3: до 03:00) текущим ещё считается прошлый месяц. Часового пояса
    # пользователя сервис пока не знает; когда появится — передавать его сюда.
    return aware_now().date()


def get_now() -> datetime:
    """Зафиксировать текущий момент в московском календаре дневного отчёта."""
    return aware_now().astimezone(ZoneInfo("Europe/Moscow"))
