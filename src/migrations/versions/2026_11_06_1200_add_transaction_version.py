"""Добавить версии существующим и новым операциям для оптимистической блокировки."""

import sqlalchemy as sa
from alembic import op

revision = "a99b102c0001"
down_revision = "8d3f6a2b1c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Инициализировать версии всех операций единицей."""
    op.add_column("transactions", sa.Column("version", sa.BigInteger(), server_default="1", nullable=False))
    op.create_check_constraint("version_positive", "transactions", "version >= 1")


def downgrade() -> None:
    """Удалить проверку и поле версии."""
    op.drop_constraint("version_positive", "transactions", type_="check")
    op.drop_column("transactions", "version")
