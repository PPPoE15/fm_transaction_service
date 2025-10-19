from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from apps import apps_types
from apps.db_models.base import AsyncBase
from apps.db_models.utils.tz_type import TZDateTime

if TYPE_CHECKING:
    from .users import User


class Transaction(AsyncBase):
    """Сущность единицы транзакции."""

    __tablename__ = "transactions"

    uid: Mapped[apps_types.TransactionUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи транзакции.",
    )
    user_uid: Mapped[apps_types.UserUID] = mapped_column(
        ForeignKey("users.uid", ondelete="CASCADE"),
        doc="Внешний ключ на uid пользователя.",
    )
    transaction_date: Mapped[datetime] = mapped_column(
        TZDateTime,
        doc="Дата транзакции.",
    )
    category: Mapped[apps_types.CategoryName] = mapped_column(
        String,
        doc="Категория транзакции.",
    )
    money_sum: Mapped[apps_types.MoneySum] = mapped_column(
        Integer,
        doc="Сумма транзакции.",
    )
    transaction_type: Mapped[apps_types.TransactionType] = mapped_column(
        String,
        doc="Тип транзакции.",
    )
    description: Mapped[apps_types.Description] = mapped_column(
        String,
        doc="Описание транзакции.",
    )

    user: Mapped["User"] = relationship(
        back_populates="transactions",
        foreign_keys=user_uid,
    )
