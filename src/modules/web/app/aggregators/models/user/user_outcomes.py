from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from modules.utils.schemas import Base

if TYPE_CHECKING:
    from modules.web.app.aggregators.models.outcome import Outcome

    from .user import User

class UserOutcomes(Base):
    """Агрегатор пользователя с расходами."""

    user: User = Field(
        description="Пользователь"
    )
    outcomes: list[Outcome] = Field(
        description="Расходы пользователя."
    )
