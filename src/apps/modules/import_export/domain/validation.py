import re
from datetime import date, datetime, time
from decimal import Decimal

from apps.modules.import_export.domain.errors import ImportIssue, IssueField
from apps.modules.import_export.domain.models import (
    MAX_AMOUNT,
    MAX_CATEGORY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_YEAR,
    MIN_YEAR,
    ParsedRecord,
    RawRecord,
)

DATE_PATTERN = re.compile(r"[0-9]{2}(?P<sep>[./-])[0-9]{2}(?P=sep)20[0-9]{2}")
AMOUNT_PATTERN = re.compile(r"[1-9][0-9]*")
CATEGORY_CONTROLS = re.compile(r"[\x00-\x1f\x7f]")
DESCRIPTION_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FIELDS: tuple[IssueField, ...] = ("date", "amount", "category", "description")


def normalize_date(value: object) -> datetime:
    """Проверить текстовую или нативную Excel-дату и вернуть полночь без часового пояса."""
    if isinstance(value, datetime):
        if not MIN_YEAR <= value.year <= MAX_YEAR or value.tzinfo or value.time() != datetime.min.time():
            raise ValueError
        return value
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise ValueError
    return datetime.combine(date(int(value[6:]), int(value[3:5]), int(value[:2])), time.min)


def normalize_amount(value: object) -> int:
    """Проверить точную целую сумму без округления и преобразования через float."""
    if isinstance(value, str):
        if len(value) > len(str(MAX_AMOUNT)) or not AMOUNT_PATTERN.fullmatch(value):
            raise ValueError
        amount = int(value)
    elif isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        if not 1 <= value <= MAX_AMOUNT:
            raise ValueError
        amount = int(value)
    else:
        raise ValueError
    if not 1 <= amount <= MAX_AMOUNT:
        raise ValueError
    return amount


def normalize_category(value: object) -> str:
    """Обрезать края имени категории без изменения регистра и внутреннего текста."""
    if not isinstance(value, str):
        raise TypeError
    value = value.strip()
    if not 1 <= len(value) <= MAX_CATEGORY_LENGTH or CATEGORY_CONTROLS.search(value):
        raise ValueError
    return value


def normalize_description(value: object) -> str | None:
    """Сохранить пробелы описания, нормализовав переводы строк до проверки длины."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if len(value) > MAX_DESCRIPTION_LENGTH or DESCRIPTION_CONTROLS.search(value):
        raise ValueError
    return value or None


def validate_record(record: RawRecord) -> tuple[ParsedRecord | None, list[ImportIssue]]:
    """Проверить поля по порядку, отдавая формулам приоритет над ошибками значений."""
    validators = (normalize_date, normalize_amount, normalize_category, normalize_description)
    issues = []
    for field, cell, validator in zip(FIELDS, record.cells, validators, strict=True):
        if cell.formula:
            issues.append(ImportIssue(record.row, field, "formula_not_allowed", "Формулы в ячейках запрещены"))
            continue
        try:
            validator(cell.value)
        except (TypeError, ValueError):
            issues.append(ImportIssue(record.row, field, f"invalid_{field}", "Недопустимое значение поля"))
    if issues:
        return None, issues
    return ParsedRecord(
        row=record.row,
        transaction_date=normalize_date(record.cells[0].value),
        money_sum=normalize_amount(record.cells[1].value),
        category_name=normalize_category(record.cells[2].value),
        description=normalize_description(record.cells[3].value),
    ), []
