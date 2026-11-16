import re

# CSV принимает любой нецифровой разделитель, сохраняя порядок день–месяц–год.
CSV_DATE_PATTERN = re.compile(r"([0-9]{1,2})\D+([0-9]{1,2})\D+((?:20)?[0-9]{2})")
CSV_AMOUNT_PATTERN = re.compile(r"[1-9][0-9]*(?:[.,\s]+[0-9]+)*")


def normalize_csv_values(values: list[str]) -> tuple[str, ...]:
    """Очистить значения CSV и привести текстовую дату к общей календарной проверке."""
    normalized = [value.strip() for value in values]
    match = CSV_DATE_PATTERN.fullmatch(normalized[0])
    if match:
        day, month, year = match.groups()
        normalized[0] = f"{int(day):02}.{int(month):02}.{2000 + int(year[-2:])}"
    if CSV_AMOUNT_PATTERN.fullmatch(normalized[1]):
        normalized[1] = re.sub(r"[.,\s]", "", normalized[1])
    return tuple(normalized)
