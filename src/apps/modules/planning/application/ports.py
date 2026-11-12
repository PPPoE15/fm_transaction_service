"""Порт хранилища планов без бизнес-решений в адаптере."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.modules.planning.domain.model import Plan
from apps.modules.planning.domain.recurring import Position, RegularTransactionRule


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
        """Заблокировать изменения планов и регулярных операций владельца."""

    @abstractmethod
    async def link(self, plan_uid: UUID) -> tuple[Position, RegularTransactionRule] | None:
        """Прочитать метаданные регулярного платежа."""

    @abstractmethod
    async def mark_exception(self, plan_uid: UUID) -> None:
        """Отметить ручное изменение позиции."""


class AbstractRegularTransactionRuleRepo(ABC):
    """Порт записи регулярных операций и позиций в транзакции планирования."""

    @abstractmethod
    async def get(self, user_uid: UUID, uid: UUID) -> RegularTransactionRule | None:
        """Получить регулярную операцию под блокировкой."""

    @abstractmethod
    async def has_source(self, user_uid: UUID, source_uid: UUID) -> bool:
        """Проверить наличие регулярной операции у исходного плана."""

    @abstractmethod
    async def save(self, rule: RegularTransactionRule, *, new: bool = False) -> None:
        """Сохранить регулярную операцию и её границу."""

    @abstractmethod
    async def positions(self, uid: UUID) -> list[Position]:
        """Получить все зарезервированные позиции."""

    @abstractmethod
    async def payments_for_update(self, uid: UUID) -> list[tuple[Position, Plan]]:
        """Получить позиции с доступными планами под блокировкой."""

    @abstractmethod
    async def add_positions(self, positions: list[Position]) -> None:
        """Создать позиции в текущей транзакции."""

    @abstractmethod
    async def remove_position(self, position: Position) -> None:
        """Освободить позицию при пересчёте."""
