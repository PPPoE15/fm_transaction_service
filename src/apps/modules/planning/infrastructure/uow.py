"""Транзакция команд планов и классификация неизвестного результата COMMIT."""

from types import TracebackType
from typing import Self

from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from apps.modules.category import CategoryRepo
from apps.modules.planning.application.uow import AbstractPlanUnitOfWork
from apps.modules.planning.domain.errors import PlanOutcomeUnknownError
from apps.modules.planning.infrastructure.recurring_repo import RegularTransactionRuleRepo
from apps.modules.planning.infrastructure.repo import PlanRepo
from apps.modules.transaction import TransactionRepo
from apps.shared.unit_of_work import AbstractSQLAlchemyUnitOfWork


class PlanUnitOfWork(AbstractPlanUnitOfWork, AbstractSQLAlchemyUnitOfWork):
    """Объединить планы и категории; не повторять операции после потери ответа."""

    async def __aenter__(self) -> Self:
        """Открыть собственную сессию команды."""
        self._session = self._session_factory()
        self.plans = PlanRepo(self._session)
        self.regular_transaction_rules = RegularTransactionRuleRepo(self._session)
        self.categories = CategoryRepo(self._session)
        self.transactions = TransactionRepo(self._session)
        return self

    async def commit(self) -> None:
        """Отделить ошибки flush от неизвестного результата COMMIT."""
        await self._session.flush()
        try:
            await self._session.commit()
        except (SQLAlchemyError, OSError) as exc:
            sqlstate = str(getattr(getattr(exc, "orig", None), "sqlstate", ""))
            if isinstance(exc, DBAPIError) and not exc.connection_invalidated and sqlstate[:2] in {"23", "40"}:
                raise
            raise PlanOutcomeUnknownError from exc

    async def __aexit__(
        self, exctype: type[BaseException] | None, excinst: BaseException | None, exctb: TracebackType | None
    ) -> None:
        """Не скрыть неизвестный исход вторичной ошибкой освобождения сессии."""
        try:
            try:
                await self.rollback()
            finally:
                await self._session.close()
        except (SQLAlchemyError, OSError) as cleanup_error:
            if isinstance(excinst, PlanOutcomeUnknownError):
                raise excinst from cleanup_error
            raise
