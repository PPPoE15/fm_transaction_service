from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from apps import apps_types
from apps.db_models.base import AsyncBase

if TYPE_CHECKING:
    from apps.db_models.models.transactions import Transaction


class Category(AsyncBase):
    """Сущность статьи (категории) бюджета."""

    __tablename__ = "categories"

    uid: Mapped[apps_types.CategoryUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи бюджета пользователя.",
    )
    user_uid: Mapped[apps_types.UserUID] = mapped_column(
        UUID,
        doc="UID пользователя.",
    )
    name: Mapped[apps_types.CategoryName] = mapped_column(
        String,
        doc="Категория.",
    )
    money_plan: Mapped[apps_types.MoneySum] = mapped_column(
        Integer,
        doc="Минимум/максимум транзакции по категории.",
    )
    category_type: Mapped[apps_types.TransactionType] = mapped_column(
        String,
        doc="Тип категории (доход или расход)",
    )
    description: Mapped[apps_types.Description | None] = mapped_column(
        String,
        nullable=True,
        doc="Описание категории.",
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )
