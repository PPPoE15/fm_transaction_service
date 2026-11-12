"""Хранение регулярных операций и устойчивых позиций расписания."""

import sqlalchemy as sa
from alembic import op

revision = "a11400000001"
down_revision = "a10700000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить таблицы регулярных операций и позиций, сохранив существующие планы и факты."""
    op.create_table(
        "recurring_operations",
        sa.Column("uid", sa.Uuid(), primary_key=True),
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("category_uid", sa.Uuid(), sa.ForeignKey("categories.uid", ondelete="RESTRICT"), nullable=True),
        sa.Column("money_sum", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("frequency", sa.String(), nullable=False),
        sa.Column("first_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("source_plan_uid", sa.Uuid(), nullable=True),
        sa.Column("generated_through", sa.Date(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recurring_operations_user_first_uid", "recurring_operations", ["user_uid", "first_date", "uid"])
    op.create_index("ix_recurring_operations_category_uid", "recurring_operations", ["category_uid"])
    op.create_index(
        "uq_recurring_operations_live_source",
        "recurring_operations",
        ["user_uid", "source_plan_uid"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND source_plan_uid IS NOT NULL"),
    )
    op.create_table(
        "recurring_occurrences",
        sa.Column(
            "operation_uid",
            sa.Uuid(),
            sa.ForeignKey("recurring_operations.uid", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("scheduled_date", sa.Date(), primary_key=True),
        sa.Column(
            "plan_uid",
            sa.Uuid(),
            sa.ForeignKey("planned_transactions.uid", ondelete="SET NULL"),
            unique=True,
            nullable=True,
        ),
        sa.Column("is_exception", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Удалить данные расписания, оставив все планы и фактические операции."""
    op.drop_table("recurring_occurrences")
    op.drop_table("recurring_operations")
