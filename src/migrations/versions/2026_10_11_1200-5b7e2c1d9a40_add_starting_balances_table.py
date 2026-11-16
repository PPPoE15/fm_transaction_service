"""add_starting_balances_table

Revision ID: 5b7e2c1d9a40
Revises: 0c78b83336a0
Create Date: 2026-10-11 12:00:00.000000+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5b7e2c1d9a40"
down_revision = "0c78b83336a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ###Стартовый остаток: одна строка на пользователя (FM-37)###
    op.create_table(
        "starting_balances",
        sa.Column("user_uid", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_uid", name=op.f("pk_starting_balances")),
    )


def downgrade() -> None:
    ###Удаление стартовых остатков###
    op.drop_table("starting_balances")
