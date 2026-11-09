"""Порт хранилища планов без бизнес-решений в адаптере."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.modules.planning.domain.model import Plan


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
