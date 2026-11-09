"""Хранение планов отдельно от фактических операций."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Uuid
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
