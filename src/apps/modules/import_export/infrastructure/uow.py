from types import TracebackType

from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from apps.modules.import_export.domain.errors import ImportFileError
from apps.modules.transaction import TransactionUnitOfWork


class ImportUnitOfWork(TransactionUnitOfWork):
    """Сохранить пакет, различая откат до COMMIT и неизвестный исход самого COMMIT."""

    async def commit(self) -> None:
        """Выполнить flush отдельно: его сбой ещё не мог сохранить транзакцию."""
        await self._session.flush()
        try:
            await self._session.commit()
        except (SQLAlchemyError, OSError) as exc:
            # Ответ сервера с SQLSTATE класса 23/40 подтверждает отказ, а не потерю ответа COMMIT.
            sqlstate = str(getattr(getattr(exc, "orig", None), "sqlstate", ""))
            if isinstance(exc, DBAPIError) and not exc.connection_invalidated and sqlstate[:2] in {"23", "40"}:
                raise
            raise ImportFileError(
                code="FM-503301",
                message="Результат импорта неизвестен. Проверьте список операций перед повторной загрузкой",
            ) from exc

    async def __aexit__(
        self,
        exctype: type[BaseException] | None,
        excinst: BaseException | None,
        exctb: TracebackType | None,
    ) -> None:
        """Освободить сессию; ошибка записи переводится в контракт только после rollback."""
        try:
            try:
                await self.rollback()
            finally:
                await self._session.close()
        except (SQLAlchemyError, OSError) as cleanup_error:
            if isinstance(excinst, ImportFileError) and excinst.code == "FM-503301":
                raise excinst from cleanup_error
            raise
        if isinstance(excinst, IntegrityError):
            sqlstate = str(getattr(excinst.orig, "sqlstate", ""))
            if sqlstate == "23503":
                raise ImportFileError(code="FM-409301", message="Категории изменились во время импорта") from excinst
        if isinstance(excinst, (SQLAlchemyError, OSError)):
            raise ImportFileError(
                code="FM-500301", message="Не удалось сохранить операции. Импорт отменён"
            ) from excinst
