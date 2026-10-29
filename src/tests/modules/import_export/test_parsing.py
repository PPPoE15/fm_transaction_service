from datetime import datetime

import pytest

from apps.modules import import_export

EXPECTED_ROW = 4
EXPECTED_AMOUNT = 100
EXPECTED_ERRORS = 100
EXPECTED_RECORD_LIMIT = 10000

HEADER = "Дата;Сумма;Категория;Описание\r\n"
VALID = "01.10.2026;100;  Продукты  ;Описание"


def parse(content: bytes, content_type: str | None = None) -> list[import_export.ParsedRecord]:
    """Вызвать публичный разбор CSV без подключения к БД."""
    return import_export.parse_file(
        content, transaction_type="outcome", file_format="csv", filename="test.csv", content_type=content_type
    )


def error(content: bytes, code: str, content_type: str | None = None) -> import_export.ImportFileError:
    """Проверить код ошибки разбора через публичный интерфейс."""
    with pytest.raises(import_export.ImportFileError) as caught:
        parse(content, content_type=content_type)
    assert caught.value.code == code
    return caught.value


def test_csv_normalizes_records_and_physical_lines() -> None:
    """Кириллица, кавычки и multiline сохраняются; пустые записи учитываются в адресах."""
    content = HEADER + '\n;;;\n01/10/2026;100;  Продукты  ;"Первая; ""цитата""\r\nВторая\rТретья"\n'
    records = parse(content.encode("utf-8-sig"))
    assert len(records) == 1
    record = records[0]
    assert record.row == EXPECTED_ROW
    assert record.transaction_date == datetime.fromisoformat("2026-10-01")
    assert record.money_sum == EXPECTED_AMOUNT
    assert record.category_name == "Продукты"
    assert record.description == 'Первая; "цитата"\nВторая\nТретья'


@pytest.mark.parametrize(
    "value",
    ["01.10.2026", "01/10/2026", "01-10-2026", "29.02.2024", "31.12.2099", "01.10/2026", "01.10.26", " 01.10.2026"],
)
def test_valid_dates(value: str) -> None:
    """Разрешённые разделители и календарные даты читаются без текущего времени."""
    records = parse((HEADER + f"{value};1;Еда;").encode())
    assert records[0].transaction_date.hour == 0


@pytest.mark.parametrize(
    "value",
    [
        "29.02.2026",
        "31/04/2026",
        "1.10.2026",
        "2026-10-01",
        "01.01.1999",
        "01.01.2100",
        "٠١.10.2026",
    ],
)
def test_invalid_dates(value: str) -> None:
    """Некалендарные и неоднозначные даты отклоняются с адресом поля."""
    exc = error((HEADER + f"{value};1;Еда;").encode(), "FM-422303")
    assert [(issue.row, issue.field, issue.reason) for issue in exc.errors] == [(2, "date", "invalid_date")]


@pytest.mark.parametrize(
    "value", ["0", "-1", "1000000001", "1.1", "100.00", "100,00", "1e3", "+100", "001", "١", "9" * 5000]
)
def test_invalid_amounts(value: str) -> None:
    """Сумма проверяется лексически и не округляется, включая очень длинные числа."""
    exc = error((HEADER + f"01.10.2026;{value};Еда;").encode(), "FM-422303")
    assert exc.errors[0].reason == "invalid_amount"


@pytest.mark.parametrize("value", ["1", "1000000000", " 1", "1 "])
def test_amount_boundaries(value: str) -> None:
    """Граничные суммы принимаются как точные целые рубли."""
    assert parse((HEADER + f"01.10.2026;{value};Еда;").encode())[0].money_sum == int(value)


@pytest.mark.parametrize(
    ("category", "description", "field"),
    [
        (" ", "", "category"),
        ("я" * 65, "", "category"),
        ("А\x00Б", "", "category"),
        ("Еда", "я" * 501, "description"),
        ("Еда", "\x7f", "description"),
    ],
)
def test_invalid_text(category: str, description: str, field: str) -> None:
    """Проверяются длины и управляющие символы текстовых полей."""
    exc = error((HEADER + f"01.10.2026;1;{category};{description}").encode(), "FM-422303")
    assert exc.errors[0].field == field


@pytest.mark.parametrize("description", ["", " ", "=пояснение", "\tтекст"])
def test_description_preserved(description: str) -> None:
    """Описание очищается по краям и не исполняется как формула CSV."""
    assert parse((HEADER + f"01.10.2026;1;Еда;{description}").encode())[0].description == (description.strip() or None)


@pytest.mark.parametrize("content", [b"", HEADER.encode(), (HEADER + "\n;;;\n").encode(), (HEADER + ";;;;").encode()])
def test_empty_files(content: bytes) -> None:
    """Нулевой файл и корректный заголовок без операций дают empty_file."""
    exc = error(content, "FM-422302")
    assert exc.errors[0].row == 1
    assert exc.errors[0].reason == "empty_file"


@pytest.mark.parametrize("content", [" ", "\n" + HEADER])
def test_invalid_headers(content: str) -> None:
    """Отсутствие заголовков даёт адрес первой строки для каждого обязательного поля."""
    exc = error(content.encode(), "FM-422301")
    assert [(issue.row, issue.field, issue.reason) for issue in exc.errors] == [
        (1, field, "invalid_structure") for field in ("date", "amount", "category", "description")
    ]


@pytest.mark.parametrize("record", ['"unterminated', '"01.10.2026"x;1;Еда;', '01.10.2026;1;Е"да;'])
def test_invalid_structure(record: str) -> None:
    """Некорректные кавычки дают ошибку структуры с адресом начала записи."""
    exc = error((HEADER + record).encode(), "FM-422301")
    assert [(issue.row, issue.field, issue.reason) for issue in exc.errors] == [(2, "file", "invalid_structure")]


@pytest.mark.parametrize("content", [HEADER.replace("Дата", " Дата") + VALID, HEADER + VALID + ";extra"])
def test_relaxed_structure(content: str) -> None:
    """Пробелы заголовка и дополнительные поля больше не являются ошибкой структуры."""
    assert parse(content.encode())[0].money_sum == EXPECTED_AMOUNT


def test_short_record_validates_values() -> None:
    """Короткая запись проверяется по полям; отсутствующее необязательное описание допустимо."""
    exc = error((HEADER + "1;2;3").encode(), "FM-422303")
    assert [(issue.row, issue.field) for issue in exc.errors] == [(2, "date")]


def test_encoding() -> None:
    """Некорректный UTF-8 не заменяется молча."""
    assert error(HEADER.encode() + b"\xff", "FM-422301").errors[0].reason == "invalid_encoding"


def test_error_order_and_truncation() -> None:
    """Ошибки упорядочены по записи и колонке; лимит проверяется на 101-й ошибке."""
    for count, truncated in [(25, False), (26, True)]:
        exc = error((HEADER + ("bad;0; ;\x00\n" * count)).encode(), "FM-422303")
        assert len(exc.errors) == EXPECTED_ERRORS
        assert exc.errors_truncated is truncated
        assert [issue.field for issue in exc.errors[:4]] == ["date", "amount", "category", "description"]


def test_structure_overrides_row_errors() -> None:
    """Повреждение в конце заменяет уже накопленные ошибки значений."""
    exc = error((HEADER + "bad;0; ;\x00\n" * 30 + '"broken').encode(), "FM-422301")
    assert len(exc.errors) == 1
    assert exc.errors_truncated is False


def test_record_limit() -> None:
    """Лимит считает операции, а не пустые строки, и разрешает ровно 10000."""
    assert len(parse((HEADER + (VALID + "\n\n") * 10000).encode())) == EXPECTED_RECORD_LIMIT
    error((HEADER + (VALID + "\n") * 10001).encode(), "FM-413302")


def test_file_limit() -> None:
    """Размер проверяется до разбора содержимого."""
    error(b"x" * (5 * 1024 * 1024 + 1), "FM-413301")


@pytest.mark.parametrize("content", [b"PK\x03\x04test", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"])
def test_csv_rejects_binary_containers(content: bytes) -> None:
    """ZIP и OLE нельзя выдавать за текстовый CSV."""
    error(content, "FM-415301")


def test_mime_validation() -> None:
    """MIME с параметрами допустим; несовместимый MIME отклоняется."""
    assert parse((HEADER + VALID).encode(), content_type="text/csv; charset=utf-8")
    error((HEADER + VALID).encode(), "FM-415301", content_type="image/png")


def test_large_field_is_value_error() -> None:
    """Поле в пределах размера файла даёт ошибку длины, а не лимита csv-модуля."""
    exc = error((HEADER + "01.10.2026;1;Еда;" + "x" * 200000).encode(), "FM-422303")
    assert exc.errors[0].reason == "invalid_description"
