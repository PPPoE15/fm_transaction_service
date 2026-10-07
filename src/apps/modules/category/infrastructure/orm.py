from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from apps.shared import apps_types
from apps.shared.db.base import AsyncBase


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

    # NOTE(FM-30): единственная связь category -> transaction. Модуль статей не импортирует модуль транзакций:
    # модель задаётся по имени класса и находится через реестр `apps.db_models`, а аннотация — общий `AsyncBase`.
    # Каскад нужен только для удаления статьи вместе с транзакциями и уйдёт вместе с ним (TODO(FM-4)).
    transactions: Mapped[list[AsyncBase]] = relationship(
        "Transaction",
        back_populates="category",
        cascade="all, delete-orphan",
    )
