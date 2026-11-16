"""Неизвестный исход сохранения не провоцирует повторное создание."""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.modules.planning.domain.errors import PlanOutcomeUnknownError
from apps.modules.planning.infrastructure.uow import PlanUnitOfWork


async def test_commit_failure_is_not_retried() -> None:
    """Потеря ответа commit даёт неизвестный исход; ошибка cleanup не подменяет его."""
    session = AsyncMock(spec=AsyncSession)
    session.commit.side_effect = OSError("Соединение потеряно")
    session.rollback.side_effect = OSError("Соединение закрыто")
    factory = Mock(spec=async_sessionmaker, return_value=session)
    with pytest.raises(PlanOutcomeUnknownError):
        async with PlanUnitOfWork(factory) as uow:
            await uow.commit()
    session.commit.assert_awaited_once()
    session.flush.assert_awaited_once()
    session.close.assert_awaited_once()


async def test_flush_failure_is_known_rollback() -> None:
    """Ошибка до отправки commit не маскируется как неизвестное сохранение."""
    session = AsyncMock(spec=AsyncSession)
    session.flush.side_effect = OSError("Нет подключения")
    factory = Mock(spec=async_sessionmaker, return_value=session)
    with pytest.raises(OSError, match="Нет подключения"):
        async with PlanUnitOfWork(factory) as uow:
            await uow.commit()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
