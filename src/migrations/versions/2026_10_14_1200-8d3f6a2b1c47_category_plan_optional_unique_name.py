"""category_plan_optional_unique_name

Revision ID: 8d3f6a2b1c47
Revises: 5b7e2c1d9a40
Create Date: 2026-10-14 12:00:00.000000+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8d3f6a2b1c47"
down_revision = "5b7e2c1d9a40"
branch_labels = None
depends_on = None

_UNIQUE_NAME = "uq_categories_user_uid_category_type_name"

# Дубликаты «пользователь + тип + название», созданные до ограничения, не удаляются: первая статья группы
# (по uid) сохраняет название, остальные получают суффикс с началом своего uid — он не совпадёт с другой статьёй
# группы, а пользователь увидит, какие статьи переименовать. Название укорачивается, чтобы влезть в 64 символа.
# NOTE(FM-41): какая статья группы сохранит название, решает порядок случайных uid (`created_at` у статей нет) —
# может переименоваться и старая статья с транзакциями. Новое название не сверяется с уже существующими: если
# у пользователя уже есть буквально «Еда (дубликат 1a2b3c4d)», создание ограничения упадёт (практически невозможно).
_RENAME_DUPLICATES = """
WITH duplicates AS (
    SELECT
        uid,
        ' (дубликат ' || left(uid::text, 8) || ')' AS suffix,
        row_number() OVER (PARTITION BY user_uid, category_type, name ORDER BY uid) AS position
    FROM categories
)
UPDATE categories
SET name = left(categories.name, 64 - length(duplicates.suffix)) || duplicates.suffix
FROM duplicates
WHERE categories.uid = duplicates.uid AND duplicates.position > 1
"""


def upgrade() -> None:
    ###План статьи необязателен, название уникально у пользователя в пределах типа (FM-41)###
    op.alter_column("categories", "money_plan", existing_type=sa.Integer(), nullable=True)
    op.execute(_RENAME_DUPLICATES)
    op.create_unique_constraint(_UNIQUE_NAME, "categories", ["user_uid", "category_type", "name"])


def downgrade() -> None:
    ###Снять уникальность; статьи без плана получают план 0 (прежняя схема не допускает NULL)###
    op.drop_constraint(_UNIQUE_NAME, "categories", type_="unique")
    op.execute("UPDATE categories SET money_plan = 0 WHERE money_plan IS NULL")
    op.alter_column("categories", "money_plan", existing_type=sa.Integer(), nullable=False)
