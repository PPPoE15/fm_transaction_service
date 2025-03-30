from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from apps.utils.schemas import Base
from apps.web.app.aggregators.models.category import Category

if TYPE_CHECKING:
    from apps import apps_types

    from .user import User


class UserCategories(Base):
    """Агрегатор пользователя с категориями."""

    user: User = Field(description="Пользователь")
    categories: list[Category] = Field(description="Категории пользователя.")

    def create_category(
        self,
        name: apps_types.UserName,
        money_sum: apps_types.MoneySum,
    ) -> None:
        """
        Создать новую категорию транзакций.

        Args:
            name: Имя пользователя.
            money_sum: Денежная сумма по категории.
        """
        new_category = Category.create(
            name=name,
            user_uid=self.user.uid,
            money_sum=money_sum,
        )
        self.categories.append(new_category)
