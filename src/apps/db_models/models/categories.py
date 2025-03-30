from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from apps import apps_types
from apps.db_models.base import AsyncBase

if TYPE_CHECKING:
    from .users import User


class Category(AsyncBase):
    """Сущность категории бюджета."""

    __tablename__ = "categories"

    uid: Mapped[apps_types.CategoryUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи бюджета пользователя.",
    )
    user_uid: Mapped[apps_types.UserUID] = mapped_column(
        ForeignKey("users.uid", ondelete="CASCADE"),
        doc="Внешний ключ на uid пользователя.",
    )
    name: Mapped[apps_types.CategoryName] = mapped_column(
        String,
        doc="Категория.",
    )
    money_sum: Mapped[apps_types.MoneySum] = mapped_column(
        Integer,
        doc="Денежная сумма по категории.",
    )

    user: Mapped["User"] = relationship(
        back_populates="categories",
        foreign_keys=user_uid,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_uid",
            "name",
            name="categories_uc",
        ),
    )
