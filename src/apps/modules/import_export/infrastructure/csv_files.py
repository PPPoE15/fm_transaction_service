import csv
from collections.abc import Iterator
from io import StringIO

from apps.modules.import_export.domain.errors import file_error
from apps.modules.import_export.domain.models import HEADERS, MAX_FILE_BYTES, RawCell, RawRecord

# Размер поля ограничен размером файла; стандартный лимит csv (128 КиБ) не является правилом контракта.
csv.field_size_limit(MAX_FILE_BYTES)


class StrictLines:
    """Проверить расположение кавычек, которое стандартный csv.reader считает допустимым."""

    def __init__(self, text: str) -> None:
        """Подготовить поток с сохранением исходных переводов строк."""
        self.stream = StringIO(text, newline="")
        self.state = "start"

    def __iter__(self) -> Iterator[str]:
        """Проверять строки по мере чтения, не опережая ресурсные проверки записей."""
        for line in self.stream:
            for char in line:
                self._consume(char)
            yield line
        if self.state == "quoted":
            raise file_error()

    def _consume(self, char: str) -> None:
        """Перейти между началом поля, текстом, кавычками и закрывающей кавычкой."""
        if self.state == "quoted":
            if char == '"':
                self.state = "closed"
        elif self.state == "closed":
            if char == '"':
                self.state = "quoted"
            elif char in ";\r\n":
                self.state = "start"
            else:
                raise file_error()
        elif char == '"':
            if self.state != "start":
                raise file_error()
            self.state = "quoted"
        elif char in ";\r\n":
            self.state = "start"
        else:
            self.state = "text"


def read_csv(content: bytes) -> Iterator[RawRecord]:
    """Прочитать строгий UTF-8 CSV, сохраняя номера логических записей."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise file_error(reason="invalid_encoding") from exc
    reader = csv.reader(StrictLines(text), delimiter=";", strict=True)
    try:
        if tuple(next(reader, [])) != HEADERS:
            raise file_error()
        for number, values in enumerate(reader, start=2):
            if not values:
                continue
            if len(values) != len(HEADERS):
                raise file_error()
            yield RawRecord(number, tuple(RawCell(value) for value in values))
    except csv.Error as exc:
        raise file_error() from exc
