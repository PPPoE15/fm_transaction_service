"""add_category_table

Revision ID: 76c20db4b456
Revises: 32a341877513
Create Date: 2025-12-20 12:06:41.005154+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "76c20db4b456"
down_revision = "32a341877513"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать таблицу categories"""
    op.create_table(
        "categories",
        sa.Column("uid", sa.UUID(), nullable=False),
        sa.Column("user_uid", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("money_plan", sa.Integer(), nullable=False),
        sa.Column("category_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_categories")),
    )
    op.alter_column(
        "transactions",
        "category",
        type_=sa.UUID(),
        postgresql_using="category::uuid",
        existing_nullable=False,
    )


def downgrade() -> None:
    """Удалить таблицу categories"""
    op.alter_column(
        "transactions",
        "category",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.drop_table("categories")
