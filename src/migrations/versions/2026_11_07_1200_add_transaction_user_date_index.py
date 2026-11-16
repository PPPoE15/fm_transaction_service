"""Индекс для операций пользователя за период и подсчёта его квоты."""

from alembic import op

revision = "a33b00000001"
down_revision = "a99b102c0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать составной индекс, не меняя существующие операции."""
    op.create_index("ix_transactions_user_uid_transaction_date", "transactions", ["user_uid", "transaction_date"])


def downgrade() -> None:
    """Удалить только индекс, сохранив все операции."""
    op.drop_index("ix_transactions_user_uid_transaction_date", table_name="transactions")
