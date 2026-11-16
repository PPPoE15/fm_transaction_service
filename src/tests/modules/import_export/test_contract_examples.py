from pathlib import Path

import pytest

from apps.modules.import_export import parse_file
from apps.modules.import_export.domain.models import TransactionKind

EXPECTED_COUNT = 2


@pytest.mark.parametrize("kind", ["income", "outcome"])
def test_contract_examples(kind: TransactionKind) -> None:
    """Нормативные примеры FM-91 дают одинаковые записи при обоих форматах файла."""
    fixtures = Path(__file__).parent / "fixtures"
    csv_name = f"{kind}-example.csv"
    xlsx_name = f"{kind}-example.xlsx"
    csv_rows = parse_file(
        (fixtures / csv_name).read_bytes(), transaction_type=kind, file_format="csv", filename=csv_name
    )
    xlsx_rows = parse_file(
        (fixtures / xlsx_name).read_bytes(), transaction_type=kind, file_format="xlsx", filename=xlsx_name
    )
    assert csv_rows == xlsx_rows
    assert len(csv_rows) == EXPECTED_COUNT
