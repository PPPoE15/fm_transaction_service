"""Переименование таблиц регулярных операций без переноса данных."""

from alembic import op

revision = "a11500000001"
down_revision = "a11400000001"
branch_labels = None
depends_on = None

TABLES = ("operations", "occurrences")
INDEXES = (
    "ix_{prefix}_operations_user_first_uid",
    "ix_{prefix}_operations_category_uid",
    "uq_{prefix}_operations_live_source",
)
CONSTRAINTS = (
    ("operations", "pk_{prefix}_operations"),
    ("operations", "fk_{prefix}_operations_category_uid_categories"),
    ("occurrences", "pk_{prefix}_occurrences"),
    ("occurrences", "fk_{prefix}_occurrences_operation_uid_{prefix}_operations"),
    ("occurrences", "fk_{prefix}_occurrences_plan_uid_planned_transactions"),
    ("occurrences", "uq_{prefix}_occurrences_plan_uid"),
)


def _rename(source: str, target: str) -> None:
    """Переименовать таблицы, индексы и ограничения с сохранением связей."""
    for table in TABLES:
        op.rename_table(f"{source}_{table}", f"{target}_{table}")
    for index in INDEXES:
        old, new = index.format(prefix=source), index.format(prefix=target)
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    for table, constraint in CONSTRAINTS:
        old, new = constraint.format(prefix=source), constraint.format(prefix=target)
        op.execute(f"ALTER TABLE {target}_{table} RENAME CONSTRAINT {old} TO {new}")


def upgrade() -> None:
    """Перейти на имена с префиксом regular."""
    _rename("recurring", "regular")


def downgrade() -> None:
    """Восстановить имена из ревизии FM-114."""
    _rename("regular", "recurring")
