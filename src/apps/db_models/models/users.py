from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, String

from apps import apps_types
from apps.db_models.base import AsyncBase

from .categories import Category
from .transactions import Transaction


class User(AsyncBase):
    """Сущность пользователя."""

    __tablename__ = "users"

    uid: Mapped[apps_types.UserUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи пользователя.",
    )
    name: Mapped[apps_types.UserName] = mapped_column(
        String,
        doc="Имя пользователя",
    )
    email: Mapped[apps_types.Email | None] = mapped_column(
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
