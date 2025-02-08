from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, String

from modules import types
from modules.db_models.base import AsyncBase

from .categories import Category
from .transactions import Transaction


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

    categories: Mapped[list[Category]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
    )
