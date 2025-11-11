from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.app.application.commands.transaction.create import CreateTransactionCommandHandler
from apps.web.app.application.commands.transaction.delete import DeleteTransactionCommandHandler
from apps.web.app.application.commands.transaction.patch import UpdateTransactionCommandHandler
from apps.web.app.application.commands.transaction.uow import TransactionUnitOfWork
from apps.web.app.application.queries.user.queries import TransactionQueries
from apps.web.app.handlers import deps as handlers_deps
from apps.web.logger import get_logger


def build_queries(session: AsyncSession) -> TransactionQueries:
    """
    Построить объект с запросами для сущности System User со всеми необходимыми зависимостями.

    Args:
        session: Сессия SQLAlchemy ORM.
        user_uid: Идентификатор пользователя.
    """
    return TransactionQueries(
        session=session,
        access_controller=None,
        logger=get_logger(),
    )


def build_create_transaction_command_handler() -> CreateTransactionCommandHandler:
    """Построить обработчик создания транзакции."""
    return CreateTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=handlers_deps.async_session_factory,
        ),
    )


def build_delete_transaction_command_handler() -> DeleteTransactionCommandHandler:
    """Построить обработчик удаления транзакции."""
    return DeleteTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=handlers_deps.async_session_factory,
        ),
    )

def build_update_transaction_command_handler() -> UpdateTransactionCommandHandler:
    """Построить обработчик обновления транзакции."""
    return UpdateTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=handlers_deps.async_session_factory,
        ),
    )
