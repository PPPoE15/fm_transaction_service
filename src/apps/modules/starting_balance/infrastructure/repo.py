from sqlalchemy.exc import IntegrityError

from apps.modules.starting_balance.application.exceptions import StartingBalanceAlreadyExistsError
from apps.modules.starting_balance.application.ports import AbstractStartingBalanceRepo
from apps.modules.starting_balance.domain import StartingBalance
from apps.modules.starting_balance.infrastructure import orm
from apps.shared import apps_types
from apps.shared.db.base_repo import BaseSqlAlchemyRepo

from . import builders

_PRIMARY_KEY_CONSTRAINT = "pk_starting_balances"


# TODO(FM-37): имя ограничения берётся из `__cause__` — внутренности адаптера asyncpg в SQLAlchemy; при смене драйвера
# гонка двух POST даст 500 вместо 409 (ловит `test_repo_translates_primary_key_violation`). Надёжнее сначала проверять
# SQLSTATE 23505 (`exc.orig.sqlstate`).
def _constraint_name(exc: IntegrityError) -> str | None:
    """Имя нарушенного ограничения из исходной ошибки asyncpg (адаптер SQLAlchemy хранит её в `__cause__`)."""
    return getattr(exc.orig.__cause__, "constraint_name", None) if exc.orig else None


class Repo(AbstractStartingBalanceRepo, BaseSqlAlchemyRepo):
    """Репозиторий стартовых остатков."""

    async def create(self, starting_balance: StartingBalance) -> None:
        self._session.add(builders.build_orm(starting_balance))
        # flush сразу, чтобы нарушение первичного ключа при гонке проявилось здесь, а не на commit.
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _constraint_name(exc) == _PRIMARY_KEY_CONSTRAINT:
                raise StartingBalanceAlreadyExistsError from exc
            raise

    async def get_by_user_uid(self, user_uid: apps_types.UserUID) -> StartingBalance | None:
        starting_balance = await self._session.get(orm.StartingBalance, user_uid)
        return builders.build(starting_balance) if starting_balance else None
