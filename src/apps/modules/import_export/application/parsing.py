from apps.modules.import_export.domain.errors import ImportFileError, ImportIssue, file_error
from apps.modules.import_export.domain.models import (
    MAX_ERRORS,
    MAX_FILE_BYTES,
    MAX_RECORDS,
    FileFormat,
    ParsedRecord,
    TransactionKind,
)
from apps.modules.import_export.domain.validation import validate_record
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


def parse_file(
    content: bytes,
    *,
    transaction_type: TransactionKind,
    file_format: FileFormat,
    filename: str,
    content_type: str | None = None,
) -> list[ParsedRecord]:
    """
    Разобрать файл без БД, возвратив записи только после проверки всего файла.

    Вызывающий код FM-93 ограничивает поток загрузки до 5 МиБ, проверяет параметры HTTP,
    затем сопоставляет категории и сохраняет результат атомарно. Здесь проверяется и размер готовых байтов.
    """
    if len(content) > MAX_FILE_BYTES:
        raise ImportFileError(code="FM-413301", message="Размер файла превышает 5 МиБ")
    validate_file_type(content, filename, file_format, content_type)
    if not content:
        raise file_error(reason="empty_file")
    source = read_csv(content) if file_format == "csv" else read_xlsx(content, transaction_type)
    records = []
    errors: list[ImportIssue] = []
    count = 0
    for raw in source:
        if all(cell.value in (None, "") and not cell.formula for cell in raw.cells):
            continue
        count += 1
        if count > MAX_RECORDS:
            raise ImportFileError(code="FM-413302", message="В файле больше 10000 операций")
        record, issues = validate_record(raw)
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
    if not count:
        raise file_error(reason="empty_file")
    return records
