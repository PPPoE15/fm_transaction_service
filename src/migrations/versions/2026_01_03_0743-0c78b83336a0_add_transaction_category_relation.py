"""add_transaction_category_relation

Revision ID: 0c78b83336a0
Revises: 76c20db4b456
Create Date: 2026-01-03 07:43:25.560012+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0c78b83336a0"
down_revision = "76c20db4b456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ###Добавление связи между транзакциями и категориями###
    op.add_column("transactions", sa.Column("category_uid", sa.UUID(), nullable=False))
    op.create_foreign_key(
        op.f("fk_transactions_category_uid_categories"), "transactions", "categories", ["category_uid"], ["uid"]
    )
    op.drop_column("transactions", "category")


def downgrade() -> None:
    ###Удаление связи между транзакциями и категориями###
    op.add_column("transactions", sa.Column("category", sa.UUID(), autoincrement=False, nullable=False))
    op.drop_constraint(op.f("fk_transactions_category_uid_categories"), "transactions", type_="foreignkey")
    op.drop_column("transactions", "category_uid")
