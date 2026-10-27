from pydantic import BaseModel, ConfigDict, Field

from apps.modules.import_export.domain.models import MAX_RECORDS, TransactionKind


class ImportResult(BaseModel):
    """Результат атомарного импорта без идентификатора задания и списка операций."""

    model_config = ConfigDict(extra="forbid")
    transaction_type: TransactionKind
    imported_count: int = Field(ge=1, le=MAX_RECORDS)
