from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID, Integer, String

from apps.shared import apps_types
from apps.shared.db.base import AsyncBase


class Category(AsyncBase):
    """Сущность статьи (категории) бюджета."""

    __tablename__ = "categories"
    # Название статьи уникально в пределах пользователя и типа (`FM-409101`); индекс по `user_uid` первым
    # служит и выборкам статей пользователя (список, подсчёт для лимита).
    __table_args__ = (UniqueConstraint("user_uid", "category_type", "name"),)

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
    money_plan: Mapped[apps_types.MoneySum | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Плановая сумма за месяц; NULL — план не задан (не то же самое, что 0).",
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
    # модель задаётся по имени класса, а аннотация — общий `AsyncBase` (тип элемента для mypy теряется).
    # Имя разрешается, только когда модель транзакций уже загружена: в приложении это делает `web/router.py`
    # (подключает api обоих модулей), в Alembic — реестр `apps.db_models`. Код вне приложения (скрипт, воркер,
    # тест модуля без `apps.web.main`), работающий с ORM статей, должен сначала импортировать `apps.db_models`,
    # иначе SQLAlchemy разрешит "Transaction" в свой `sqlalchemy.engine.Transaction` (UnmappedClassError).
    # Связь нужна и проверке «есть ли транзакции по статье» (`Repo.has_transactions`, запрет смены типа `FM-400101`,
    # FM-45) — её саму не удалять. Уйдёт только каскад: он нужен лишь для удаления статьи вместе с транзакциями,
    # а по контракту статью с транзакциями удалять нельзя (TODO(FM-4) в `commands/delete.py`).
    transactions: Mapped[list[AsyncBase]] = relationship(
        "Transaction",
        back_populates="category",
        cascade="all, delete-orphan",
    )
