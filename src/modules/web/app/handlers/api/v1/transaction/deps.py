from sqlalchemy.ext.asyncio import AsyncSession

from modules.web.app.application.commands.transaction.create import CreateTransactionCommandHandler
from modules.web.app.application.commands.transaction.uow import TransactionUnitOfWork
from modules.web.app.application.queries.user.queries import TransactionQueries
from modules.web.app.handlers import deps as handlers_deps
from modules.web.logger import get_logger


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


def build_transaction_create_command_handler() -> CreateTransactionCommandHandler:
    """Построить обработчик создания транзакции."""
    return CreateTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=handlers_deps.async_session_factory,
        ),
    )
