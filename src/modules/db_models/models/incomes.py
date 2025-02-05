from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from modules import types
from modules.db_models.base import AsyncBase
from modules.db_models.utils.types import TZDateTime

if TYPE_CHECKING:
    from .users import User

class Income(AsyncBase):
    """Сущность единицы дохода."""

    __tablename__ = "incomes"

    uid: Mapped[types.IncomeUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи дохода.",
    )
    user_uid: Mapped[types.UserUID] = mapped_column(
        ForeignKey("users.uid", ondelete="CASCADE"),
        doc="Внешний ключ на uid пользователя.",
    )
    income_date: Mapped[datetime] = mapped_column(
        TZDateTime,
        doc="Дата дохода.",
    )
    category: Mapped[types.CategoryName] = mapped_column(
        String,
        doc="Категория дохода.",
    )
    money_sum: Mapped[types.MoneySum] = mapped_column(
        Integer,
        doc="Сумма дохода.",
    )
    description: Mapped[types.Description] = mapped_column(
        String,
        doc="Описание дохода.",
    )

    user: Mapped["User"] = relationship(
        back_populates="incomes",
        foreign_keys=user_uid,
    )
