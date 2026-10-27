import csv
from datetime import datetime
from io import StringIO
from itertools import permutations

import pytest

from apps.modules.import_export.domain.models import HEADERS
from tests.modules.import_export.test_parsing import error, parse
from tests.modules.import_export.test_xlsx import parse_xlsx, workbook_bytes, xlsx_error

EXPECTED_AMOUNT = 50
EXPECTED_ERROR_ROW = 4
FIRST_DATA_ROW = 2


def csv_bytes(rows: list[list[str]], delimiter: str = ",") -> bytes:
    """Сформировать синтетический CSV с корректным экранированием полей."""
    stream = StringIO(newline="")
    csv.writer(stream, delimiter=delimiter).writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


@pytest.mark.parametrize("delimiter", [",", ";"])
@pytest.mark.parametrize("headers", list(permutations(HEADERS)))
def test_columns_mapped_by_name(headers: tuple[str, ...], delimiter: str) -> None:
    """Любой порядок обязательных колонок и дополнительные поля дают те же операции."""
    values = dict(zip(HEADERS, ["01.09.22", " 50 ", " Еда ", " текст "], strict=True))
    content = csv_bytes(
        [["Заметки", *headers, "", "Итог"], ["дополнение", *(values[h] for h in headers), "", "100"]], delimiter
    )
    record = parse(content)[0]
    assert record.transaction_date == datetime.fromisoformat("2022-09-01")
    assert record.money_sum == EXPECTED_AMOUNT
    assert record.category_name == "Еда"
    assert record.description == "текст"


@pytest.mark.parametrize("separator", [".", "/", "-", " ", ",", ";", "|", "年", "💠", "::"])
@pytest.mark.parametrize("year", ["22", "2022"])
def test_any_date_separator(separator: str, year: str) -> None:
    """Разделители даты не ограничены списком знаков, включая разделитель CSV."""
    record = parse(csv_bytes([list(HEADERS), [f"01{separator}09{separator}{year}", "50", "Еда", ""]]))[0]
    assert record.transaction_date == datetime.fromisoformat("2022-09-01")


@pytest.mark.parametrize("date_value", ["01.09/22", "01/09-2022"])
def test_mixed_date_separators(date_value: str) -> None:
    """Каждый разделитель даты может быть произвольным при фиксированном порядке компонентов."""
    assert parse(csv_bytes([list(HEADERS), [date_value, "50", "Еда", ""]]))[
        0
    ].transaction_date == datetime.fromisoformat("2022-09-01")


@pytest.mark.parametrize("date_value", ["29.02.23", "31|04|2022", "1.09.22", "01.9.22", "2022-09-01", "010922"])
def test_invalid_flexible_date(date_value: str) -> None:
    """Произвольный разделитель не отменяет календарь и порядок компонентов даты."""
    exc = error(csv_bytes([list(HEADERS), [date_value, "50", "Еда", ""]]), "FM-422303")
    assert (exc.errors[0].row, exc.errors[0].field) == (2, "date")


@pytest.mark.parametrize(("year", "expected"), [("00", 2000), ("99", 2099)])
def test_short_year_century(year: str, expected: int) -> None:
    """Двузначные годы относятся к 2000–2099 без зависимости от текущего года."""
    assert parse(csv_bytes([list(HEADERS), [f"01.01.{year}", "1", "Еда", ""]]))[0].transaction_date.year == expected


def test_unicode_strip_for_every_field() -> None:
    """Все значения и заголовки очищаются по краям, внутренние пробелы остаются."""
    content = csv_bytes(
        [
            [f"\u00a0 {header}\t" for header in HEADERS],
            [" 01.09.22\u00a0", "\t50\u00a0", "\u00a0Еда  дома ", ' \tтекст, с; "кавычками"\r\nвнутри  строки\u00a0'],
        ]
    )
    record = parse(content)[0]
    assert record.category_name == "Еда  дома"
    assert record.description == 'текст, с; "кавычками"\nвнутри  строки'


@pytest.mark.parametrize("header", ["Дата,Сумма,Категория", "Дата,Сумма,Категория,Описание, Сумма "])
def test_header_errors_have_row_and_field(header: str) -> None:
    """Отсутствующий или повторяющийся заголовок адресуется первой строкой и именем."""
    exc = error(header.encode(), "FM-422301")
    issue = exc.errors[0]
    assert issue.row == 1
    assert issue.field == ("description" if "Описание" not in header else "amount")
    assert ("Описание" if issue.field == "description" else "Сумма") in issue.message


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_physical_line_of_missing_value(newline: str) -> None:
    """Ошибка после многострочного поля указывает физическую строку, включая пустые строки."""
    content = newline.join(
        ["Описание,Категория,Сумма,Дата", '"первая', 'вторая",Еда,50,01.09.22', "", "текст,Еда,   ,01.09.22"]
    )
    exc = error(content.encode(), "FM-422303")
    assert [(issue.row, issue.field) for issue in exc.errors] == [(5, "amount")]
    assert "Сумма" in exc.errors[0].message


@pytest.mark.parametrize("broken", ['"незакрыто', '01.09.22,50,Е"да,', '"01.09.22"x,50,Еда,'])
def test_broken_quotes_have_start_line(broken: str) -> None:
    """Повреждённые кавычки возвращают строку начала записи и понятное пояснение."""
    content = 'Дата,Сумма,Категория,Описание\n01.09.22,50,Еда,"строка\nпродолжение"\n' + broken
    exc = error(content.encode(), "FM-422301")
    assert exc.errors[0].row == EXPECTED_ERROR_ROW
    assert "кавыч" in exc.errors[0].message.lower()


def test_short_record_reports_missing_fields() -> None:
    """Короткая запись сообщает отсутствующее обязательное значение, а не общую структуру."""
    exc = error(b"\xef\xbb\xbf" + "Дата,Описание,Сумма,Категория\n01.09.22,текст".encode(), "FM-422303")
    assert [(issue.row, issue.field) for issue in exc.errors] == [(2, "amount"), (2, "category")]


def test_delimiters_inside_extra_header() -> None:
    """Запятые и точки с запятой в дополнительных заголовках не мешают выбору диалекта."""
    for delimiter in [",", ";"]:
        record = parse(csv_bytes([["Заметки,;", *HEADERS], ["", "01.09.22", "50", "Еда", ""]], delimiter))[0]
        assert record.category_name == "Еда"


def test_xlsx_rules_unchanged() -> None:
    """Расширение CSV не меняет даты, суммы и пробелы описания в XLSX."""
    for date_value, amount in [("01.09.22", "50"), ("01|09|2022", "50"), ("01.09.2022", " 50 ")]:
        xlsx_error(workbook_bytes([[date_value, amount, "Еда", ""]]), "FM-422303")
    record = parse_xlsx(workbook_bytes([["01.09.2022", "50", "Еда", " текст "]]))[0]
    assert record.description == " текст "


@pytest.mark.parametrize(
    "content", [b"", "Дата,Сумма,Категория,Описание\n".encode(), "Дата,Сумма,Категория,Описание\n , , , ".encode()]
)
def test_empty_csv_points_to_file_start(content: bytes) -> None:
    """Файл без операций сообщает отсутствие данных с адресом начала файла."""
    exc = error(content, "FM-422302")
    assert exc.errors[0].row == 1


def test_encoding_error_has_physical_line() -> None:
    """Ошибка UTF-8 сообщает физическую строку байтового повреждения."""
    exc = error("Дата,Сумма,Категория,Описание\r\n".encode() + b"\xff", "FM-422301")
    assert exc.errors[0].row == FIRST_DATA_ROW
