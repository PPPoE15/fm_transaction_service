from collections.abc import Callable

from apps.modules.import_export.domain.errors import ImportFileError, ImportIssue, file_error
from apps.modules.import_export.domain.models import (
    MAX_ERRORS,
    MAX_FILE_BYTES,
    MAX_RECORDS,
    FileFormat,
    ParsedRecord,
    RawRecord,
    TransactionKind,
)
from apps.modules.import_export.domain.validation import FIELDS, normalize_category, validate_record
from apps.modules.import_export.infrastructure.csv_files import read_csv
from apps.modules.import_export.infrastructure.templates import XLSX_MEDIA_TYPE
from apps.modules.import_export.infrastructure.xlsx_files import read_xlsx

CSV_MIME_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def validate_file_type(content: bytes, filename: str, file_format: FileFormat, content_type: str | None) -> None:
    """Проверить расширение, MIME и контейнер до разбора структуры."""
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    allowed = CSV_MIME_TYPES if file_format == "csv" else {XLSX_MEDIA_TYPE}
    if not filename.lower().endswith(f".{file_format}") or mime not in allowed | {"", "application/octet-stream"}:
        raise ImportFileError(code="FM-415301", message="Формат файла не поддерживается")
    if content.startswith(OLE_SIGNATURE) or (file_format == "csv" and content.startswith(b"PK")):
        raise ImportFileError(code="FM-415301", message="Формат файла не поддерживается")
    if content and file_format == "xlsx" and not content.startswith(b"PK"):
        raise ImportFileError(code="FM-415301", message="Формат файла не поддерживается")


def read_file_records(
    content: bytes,
    *,
    transaction_type: TransactionKind,
    file_format: FileFormat,
    filename: str,
    content_type: str | None = None,
) -> list[RawRecord]:
    """Проверить контейнер, структуру и ограничения всего файла до обращения к БД."""
    if len(content) > MAX_FILE_BYTES:
        raise ImportFileError(code="FM-413301", message="Размер файла превышает 5 МиБ")
    validate_file_type(content, filename, file_format, content_type)
    if not content:
        raise file_error(reason="empty_file", row=1 if file_format == "csv" else None)
    source = read_csv(content) if file_format == "csv" else read_xlsx(content, transaction_type)
    records: list[RawRecord] = []
    for raw in source:
        if all(cell.value in (None, "") and not cell.formula for cell in raw.cells):
            continue
        if len(records) >= MAX_RECORDS:
            raise ImportFileError(code="FM-413302", message="В файле больше 10000 операций")
        records.append(raw)
    if not records:
        raise file_error(reason="empty_file", row=1 if file_format == "csv" else None)
    return records


def validate_records(
    raw_records: list[RawRecord],
    category_matches: Callable[[str], int] | None = None,
) -> list[ParsedRecord]:
    """Объединить ошибки полей и категорий в порядке строк и колонок, без записи в БД."""
    records = []
    errors: list[ImportIssue] = []
    for raw in raw_records:
        record, issues = validate_record(raw)
        if category_matches is not None and not any(issue.field == "category" for issue in issues):
            count = category_matches(normalize_category(raw.cells[2].value))
            if count != 1:
                issues.append(
                    ImportIssue(
                        raw.row,
                        "category",
                        "ambiguous_category" if count else "unknown_category",
                        "Неоднозначная категория" if count else "Категория не найдена",
                    )
                )
        issues.sort(key=_issue_order)
        errors.extend(issues[: MAX_ERRORS + 1 - len(errors)])
        if record is not None:
            records.append(record)
    if errors:
        raise ImportFileError(
            code="FM-422303",
            message="Исправьте строки файла",
            errors=tuple(errors[:MAX_ERRORS]),
            errors_truncated=len(errors) > MAX_ERRORS,
        )
    return records


def parse_file(
    content: bytes,
    *,
    transaction_type: TransactionKind,
    file_format: FileFormat,
    filename: str,
    content_type: str | None = None,
) -> list[ParsedRecord]:
    """Разобрать и проверить файл без БД, сохранив публичный интерфейс парсера."""
    return validate_records(
        read_file_records(
            content,
            transaction_type=transaction_type,
            file_format=file_format,
            filename=filename,
            content_type=content_type,
        )
    )


def _issue_order(issue: ImportIssue) -> int:
    """Вернуть порядок поля в строке шаблона."""
    return FIELDS.index(issue.field)
