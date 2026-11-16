import csv
from collections.abc import Iterator
from io import StringIO

from apps.modules.import_export.domain.csv_values import normalize_csv_values
from apps.modules.import_export.domain.errors import ImportFileError, ImportIssue, file_error
from apps.modules.import_export.domain.models import HEADERS, MAX_FILE_BYTES, RawCell, RawRecord
from apps.modules.import_export.domain.validation import FIELDS

# Размер поля ограничен размером файла; стандартный лимит csv (128 КиБ) не является правилом контракта.
csv.field_size_limit(MAX_FILE_BYTES)


class StrictLines:
    """Проверить расположение кавычек, которое стандартный csv.reader считает допустимым."""

    def __init__(self, text: str, delimiter: str) -> None:
        """Подготовить поток с сохранением исходных переводов строк."""
        self.stream = StringIO(text, newline="")
        self.state = "start"
        self.separators = delimiter + "\r\n"

    def __iter__(self) -> Iterator[str]:
        """Проверять строки по мере чтения, не опережая ресурсные проверки записей."""
        for line in self.stream:
            for char in line:
                self._consume(char)
            yield line
        if self.state == "quoted":
            raise csv.Error

    def _consume(self, char: str) -> None:
        """Перейти между началом поля, текстом, кавычками и закрывающей кавычкой."""
        if self.state == "quoted":
            if char == '"':
                self.state = "closed"
        elif self.state == "closed":
            if char == '"':
                self.state = "quoted"
            elif char in self.separators:
                self.state = "start"
            else:
                raise csv.Error
        elif char == '"':
            if self.state != "start":
                raise csv.Error
            self.state = "quoted"
        elif char in self.separators:
            self.state = "start"
        else:
            self.state = "text"


def detect_delimiter(text: str) -> str:
    """Выбрать разделитель по распознанным заголовкам, не анализируя значения операций."""
    candidates: list[tuple[int, str]] = []
    for delimiter in (";", ","):
        reader = csv.reader(StrictLines(text, delimiter), delimiter=delimiter, strict=True)
        try:
            headers = {value.strip() for value in next(reader, [])}
        except csv.Error:
            continue
        candidates.append((len(headers.intersection(HEADERS)), delimiter))
    candidates.sort(reverse=True)
    if not candidates:
        raise file_error(row=1, message="Проверьте кавычки и разделитель CSV в строке заголовков")
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0] and candidates[0][0]:
        raise file_error(row=1, message="Неоднозначный разделитель CSV: используйте запятую или точку с запятой")
    return candidates[0][1]


def column_indices(headers: list[str]) -> list[int]:
    """Сопоставить обязательные поля с уникальными заголовками и сообщить отсутствующие."""
    names = [value.strip() for value in headers]
    indices = []
    issues = []
    for name, field in zip(HEADERS, FIELDS, strict=True):
        count = names.count(name)
        if count != 1:
            message = f"Отсутствует обязательный столбец «{name}»" if count == 0 else f"Повторяется столбец «{name}»"
            issues.append(ImportIssue(1, field, "invalid_structure", message))
        else:
            indices.append(names.index(name))
    if issues:
        raise ImportFileError(code="FM-422301", message="Исправьте заголовки CSV в строке 1", errors=tuple(issues))
    return indices


def read_csv(content: bytes) -> Iterator[RawRecord]:
    """Прочитать CSV по именам колонок с физическими номерами начала записей."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        prefix = exc.object[: exc.start]
        row = prefix.count(b"\n") + prefix.count(b"\r") - prefix.count(b"\r\n") + 1
        raise file_error(reason="invalid_encoding", row=row) from exc
    delimiter = detect_delimiter(text)
    reader = csv.reader(StrictLines(text, delimiter), delimiter=delimiter, strict=True)
    row = 1
    try:
        indices = column_indices(next(reader, []))
        while True:
            row = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not values:
                continue
            selected = [values[index] if index < len(values) else "" for index in indices]
            yield RawRecord(row, tuple(RawCell(value) for value in normalize_csv_values(selected)))
    except csv.Error as exc:
        raise file_error(
            row=row, message="Проверьте кавычки CSV: поле должно быть закрыто и корректно экранировано"
        ) from exc
