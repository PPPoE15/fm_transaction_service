"""Порт хранилища планов без бизнес-решений в адаптере."""

from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.recurring import Position, Series


class AbstractPlanRepo(ABC):
    """Контракт чтения и записи агрегатов, включая блокировки."""

    @abstractmethod
    async def count_for_update(self, user_uid: UUID) -> int:
        """Заблокировать набор пользователя и вернуть его размер, включая completed."""

    @abstractmethod
    async def get_for_update(self, user_uid: UUID, plan_uid: UUID) -> Plan | None:
        """Заблокировать только собственную запись для проверки версии и состояния."""

    @abstractmethod
    async def create(self, plan: Plan) -> None:
        """Добавить агрегат в текущую транзакцию."""

    @abstractmethod
    async def update(self, plan: Plan) -> None:
        """Записать агрегат после проверки инвариантов командой."""

    @abstractmethod
    async def delete(self, plan: Plan) -> None:
        """Удалить только план, не затрагивая факт."""

    @abstractmethod
    async def lock_owner(self, user_uid: UUID) -> None:
        """Заблокировать изменения планов и серий владельца."""

    @abstractmethod
    async def link(self, plan_uid: UUID) -> tuple[Position, Series] | None:
        """Прочитать метаданные регулярного платежа."""

    @abstractmethod
    async def mark_exception(self, plan_uid: UUID) -> None:
        """Отметить ручное изменение позиции."""


class RecurringStorage(Protocol):
    """Порт записи серий и позиций в транзакции планирования."""

    async def get(self, user_uid: UUID, uid: UUID) -> Series | None:
        """Получить серию под блокировкой."""

    async def has_source(self, user_uid: UUID, source_uid: UUID) -> bool:
        """Проверить наличие серии у исходного плана."""

    async def save(self, series: Series, *, new: bool = False) -> None:
        """Сохранить серию и её границу."""

    async def positions(self, uid: UUID) -> list[Position]:
        """Получить все зарезервированные позиции."""

    async def payments_for_update(self, uid: UUID) -> list[tuple[Position, Plan]]:
        """Получить позиции с доступными планами под блокировкой."""

    async def add_positions(self, positions: list[Position]) -> None:
        """Создать позиции в текущей транзакции."""

    async def remove_position(self, position: Position) -> None:
        """Освободить позицию при пересчёте."""
