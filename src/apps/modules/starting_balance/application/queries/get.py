from __future__ import annotations

from typing import TYPE_CHECKING

from apps.modules.starting_balance.infrastructure import orm
from apps.shared.db.base_query import BaseQueries

from . import schemas

if TYPE_CHECKING:
    from apps.shared import apps_types


class StartingBalanceQueries(BaseQueries):
    """Запросы стартового остатка."""

    async def get(self, user_uid: apps_types.UserUID) -> schemas.StartingBalanceSchema | None:
        """
        Получить стартовый остаток пользователя.

        Args:
            user_uid: UID пользователя.
        """
        starting_balance = await self._session.get(orm.StartingBalance, user_uid)
        return schemas.StartingBalanceSchema.model_validate(starting_balance) if starting_balance else None
