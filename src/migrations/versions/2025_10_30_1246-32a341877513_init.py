"""init

Revision ID: 32a341877513
Revises:
Create Date: 2025-10-30 12:46:14.913489+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "32a341877513"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создание таблицы транзакций"""
    op.create_table(
        "transactions",
        sa.Column("uid", sa.UUID(), nullable=False),
        sa.Column("user_uid", sa.UUID(), nullable=False),
        sa.Column("transaction_date", sa.DateTime(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("money_sum", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_transactions")),
    )


def downgrade() -> None:
    """Удаление таблицы транзакций"""
    op.drop_table("transactions")
