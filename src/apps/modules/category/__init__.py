"""Публичный API модуля статей: другие модули импортируют из `category` только отсюда."""

from apps.modules.category.application.exceptions import CategoryNotFoundError
from apps.modules.category.application.guards import get_own_category
from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.modules.category.domain import Category
from apps.modules.category.infrastructure.orm import Category as CategoryORM
from apps.modules.category.infrastructure.repo import Repo as CategoryRepo

__all__ = [
    "AbstractCategoryRepo",
    "Category",
    "CategoryNotFoundError",
    "CategoryORM",
    "CategoryRepo",
    "get_own_category",
]
