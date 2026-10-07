"""
Реестр ORM-моделей всех модулей.

Импортирует `infrastructure/orm.py` каждого модуля, чтобы все таблицы были в `AsyncBase.metadata`
(Alembic) и связи между моделями разных модулей разрешались по имени класса.
"""

from apps.modules.category.infrastructure.orm import Category
from apps.modules.transaction.infrastructure.orm import Transaction
from apps.shared.db.base import AsyncBase

__all__ = [
    "AsyncBase",
    "Category",
    "Transaction",
]
