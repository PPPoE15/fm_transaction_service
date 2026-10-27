from io import BytesIO

from openpyxl import Workbook

from apps.modules.import_export.domain.models import HEADERS, SHEET_NAMES, FileFormat, TransactionKind

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def generate_template(transaction_type: TransactionKind, file_format: FileFormat) -> bytes:
    """Создать пустой шаблон выбранного типа с фиксированными заголовками."""
    if file_format == "csv":
        return (";".join(HEADERS) + "\r\n").encode("utf-8-sig")
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None  # noqa: S101 — Workbook создаёт первый лист по умолчанию
    sheet.title = SHEET_NAMES[transaction_type]
    sheet.append(HEADERS)
    for column, number_format in zip("ABCD", ("@", "0", "@", "@"), strict=True):
        sheet.column_dimensions[column].number_format = number_format
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()
