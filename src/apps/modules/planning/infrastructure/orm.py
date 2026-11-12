"""Хранение планов отдельно от фактических операций."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Uuid, false, text
from sqlalchemy.orm import Mapped, mapped_column

from apps.shared.db.base import AsyncBase


class PlannedTransaction(AsyncBase):
    """Исходные поля плана и безопасная nullable-ссылка на факт."""

    __tablename__ = "planned_transactions"
    __table_args__ = (
        Index("ix_planned_transactions_user_date_uid", "user_uid", "planned_date", "uid"),
        Index("ix_planned_transactions_category_uid", "category_uid"),
    )

    uid: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_uid: Mapped[UUID] = mapped_column(Uuid)
    planned_date: Mapped[date] = mapped_column(Date)
    money_sum: Mapped[int] = mapped_column(Integer)
    category_uid: Mapped[UUID] = mapped_column(Uuid, ForeignKey("categories.uid", ondelete="RESTRICT"))
    transaction_type: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, server_default="1")
    status: Mapped[str] = mapped_column(String, server_default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category_name_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    transaction_uid: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("transactions.uid", ondelete="SET NULL"), nullable=True, unique=True
    )


class RecurringOperation(AsyncBase):
    """Правило регулярной операции и граница генерации; запись сохраняется после логического удаления."""

    __tablename__ = "recurring_operations"
    __table_args__ = (
        Index("ix_recurring_operations_user_first_uid", "user_uid", "first_date", "uid"),
        Index("ix_recurring_operations_category_uid", "category_uid"),
        Index(
            "uq_recurring_operations_live_source",
            "user_uid",
            "source_plan_uid",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND source_plan_uid IS NOT NULL"),
        ),
    )

    uid: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_uid: Mapped[UUID] = mapped_column(Uuid)
    category_uid: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("categories.uid", ondelete="RESTRICT"))
    money_sum: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    frequency: Mapped[str] = mapped_column(String)
    first_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(BigInteger, server_default="1")
    source_plan_uid: Mapped[UUID | None] = mapped_column(Uuid)
    generated_through: Mapped[date | None] = mapped_column(Date)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecurringOccurrence(AsyncBase):
    """Позиция расписания регулярной операции; NULL вместо UID плана резервирует отдельно удалённый платёж."""

    __tablename__ = "recurring_occurrences"

    operation_uid: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("recurring_operations.uid", ondelete="RESTRICT"), primary_key=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, primary_key=True)
    plan_uid: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("planned_transactions.uid", ondelete="SET NULL"), unique=True
    )
    is_exception: Mapped[bool] = mapped_column(Boolean, server_default=false())
