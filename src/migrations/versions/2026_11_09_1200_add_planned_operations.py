"""Отдельная таблица планов и безопасное удаление связанного факта."""

import sqlalchemy as sa
from alembic import op

revision = "a10700000001"
down_revision = "a33b00000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить хранение планов без изменения существующих категорий и фактов."""
    op.create_table(
        "planned_operations",
        sa.Column("uid", sa.Uuid(), primary_key=True),
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("money_sum", sa.Integer(), nullable=False),
        sa.Column("category_uid", sa.Uuid(), sa.ForeignKey("categories.uid", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category_name_snapshot", sa.String(), nullable=True),
        sa.Column(
            "transaction_uid",
            sa.Uuid(),
            sa.ForeignKey("transactions.uid", ondelete="SET NULL"),
            unique=True,
            nullable=True,
        ),
    )
    op.create_index("ix_planned_operations_user_date_uid", "planned_operations", ["user_uid", "planned_date", "uid"])
    op.create_index("ix_planned_operations_category_uid", "planned_operations", ["category_uid"])
    # NOTE(FM-107): FK SET NULL обслуживает все способы удаления факта, включая пакетный маршрут;
    # триггер повышает версию в той же транзакции, не создавая циклических зависимостей модулей.
    op.execute("""
        CREATE FUNCTION planned_fact_unlinked() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.transaction_uid IS NOT NULL AND NEW.transaction_uid IS NULL THEN
                NEW.version := OLD.version + 1;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER planned_fact_unlinked BEFORE UPDATE OF transaction_uid ON planned_operations
        FOR EACH ROW EXECUTE FUNCTION planned_fact_unlinked();
    """)


def downgrade() -> None:
    """Удалить только планы и их триггер, сохранив факты и категории."""
    op.drop_table("planned_operations")
    op.execute("DROP FUNCTION planned_fact_unlinked()")
