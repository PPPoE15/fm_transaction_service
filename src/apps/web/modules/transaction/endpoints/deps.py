from apps.web.core.deps import async_session_factory
from apps.web.modules.transaction.application.commands import (
    CreateTransactionCommandHandler,
    DeleteTransactionCommandHandler,
    TransactionUnitOfWork,
    UpdateTransactionCommandHandler,
)


def build_create_transaction_command_handler() -> CreateTransactionCommandHandler:
    """Построить обработчик создания транзакции."""
    return CreateTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=async_session_factory,
        ),
    )


def build_delete_transaction_command_handler() -> DeleteTransactionCommandHandler:
    """Построить обработчик удаления транзакции."""
    return DeleteTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=async_session_factory,
        ),
    )


def build_update_transaction_command_handler() -> UpdateTransactionCommandHandler:
    """Построить обработчик обновления транзакции."""
    return UpdateTransactionCommandHandler(
        unit_of_work=TransactionUnitOfWork(
            session_factory=async_session_factory,
        ),
    )
