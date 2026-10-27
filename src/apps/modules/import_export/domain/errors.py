from dataclasses import dataclass
from typing import Literal

from apps.shared.exceptions import BaseError

IssueField = Literal["file", "date", "amount", "category", "description"]


@dataclass(frozen=True)
class ImportIssue:
    """Ошибка файла или поля записи с адресом для пользовательского интерфейса."""

    row: int | None
    field: IssueField
    reason: str
    message: str


class ImportFileError(BaseError):
    """Ошибка разбора без частичного результата и без сохранения операций."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        errors: tuple[ImportIssue, ...] = (),
        errors_truncated: bool = False,
    ) -> None:
        """Запомнить код контракта и ограниченный список ошибок."""
        super().__init__(message)
        self.code = code
        self.status = int(code[3:6])
        self.errors = errors
        self.errors_truncated = errors_truncated


def file_error(reason: str = "invalid_structure") -> ImportFileError:
    """Создать адресованную всему файлу ошибку структуры, кодировки или пустого файла."""
    messages = {
        "invalid_structure": "Структура файла не соответствует шаблону",
        "invalid_encoding": "Файл должен быть в кодировке UTF-8",
        "empty_file": "В файле нет операций",
    }
    return ImportFileError(
        "FM-422302" if reason == "empty_file" else "FM-422301",
        messages[reason],
        errors=(ImportIssue(None, "file", reason, messages[reason]),),
    )
