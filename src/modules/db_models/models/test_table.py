from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from modules.db_models.base import AsyncBase
from modules.web.app.aggregators import types


class TestTable(AsyncBase):
    """Тестовая таблица."""

    __tablename__ = "test_table"

    uid: Mapped[types.TestUID] = mapped_column(
        UUID,
        primary_key=True,
        doc="Уникальный ID записи лицензии.",
    )
