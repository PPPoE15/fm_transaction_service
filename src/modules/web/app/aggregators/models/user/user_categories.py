from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from modules.utils.schemas import Base
from modules.web.app.aggregators.models.category import Category

if TYPE_CHECKING:
    from modules import types

    from .user import User


class UserCategories(Base):
    """Агрегатор пользователя с категориями."""

    user: User = Field(description="Пользователь")
    categories: list[Category] = Field(description="Категории пользователя.")

    def create_category(
        self,
        name: types.UserName,
        money_sum: types.MoneySum,
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
