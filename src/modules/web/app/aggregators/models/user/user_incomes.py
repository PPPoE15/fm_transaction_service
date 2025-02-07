from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from modules.web.app.aggregators.models.income import Income

    from .user import User

class UserIncomes(Base):
    """Агрегатор пользователя с доходами."""

    user: User = Field(
        description="Пользователь"
    )
    incomes: list[Income] = Field(
        description="Доходы пользователя."
    )
