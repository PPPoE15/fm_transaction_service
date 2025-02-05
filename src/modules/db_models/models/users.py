from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, String

from modules import types
from modules.db_models.base import AsyncBase

if TYPE_CHECKING:
    from .categories import Category
    from .incomes import Income
    from .outcomes import Outcome

class User(AsyncBase):
    """Сущность пользователя."""

    __tablename__ = "users"

    uid: Mapped[types.UserUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи пользователя.",
    )
    name: Mapped[types.UserName] = mapped_column(
        String,
        doc="Имя пользователя",
    )
    email: Mapped[types.Email | None] = mapped_column(
        String,
        doc="Email пользователя",
    )

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
    )
    incomes: Mapped[list["Income"]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
    )
    outcomes: Mapped[list["Outcome"]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
    )
