import datetime as dt


def aware_now() -> dt.datetime:
    """Получить текущую "безопасную" дату со временем по UTC с явно указанной временной зоной UTC."""
    return dt.datetime.now(tz=dt.UTC)


def init_utc_tz(d: dt.datetime) -> dt.datetime:
    """
    Добавить к дате UTC временную зону, если никакой временной зоны не указано.

    Args:
        d: Дата и время.
    """
    if d.tzinfo is None:
        return d.replace(tzinfo=dt.UTC)
    return d
