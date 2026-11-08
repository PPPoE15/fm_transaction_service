from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TransactionKind = Literal["income", "outcome"]
FileFormat = Literal["csv", "xlsx"]
HEADERS = ("Дата", "Сумма", "Категория", "Описание")
SHEET_NAMES: dict[TransactionKind, str] = {"income": "Доходы", "outcome": "Расходы"}


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 10000
MAX_ERRORS = 100
MAX_AMOUNT = 1000000000
MAX_CATEGORY_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 500
MIN_YEAR = 2000
MAX_YEAR = 2099


@dataclass(frozen=True)
class RawCell:
    """Значение ячейки и признак формулы, сохранённые адаптером без вычисления."""

    value: object = None
    formula: bool = False


@dataclass(frozen=True)
class RawRecord:
    """Четыре ячейки и исходный номер записи CSV или строки XLSX."""

    row: int
    cells: tuple[RawCell, ...]


@dataclass(frozen=True)
class ParsedRecord:
    """Проверенная операция до сопоставления категории и сохранения в FM-93."""

    row: int
    transaction_date: datetime
    money_sum: int
    category_name: str
    description: str | None
