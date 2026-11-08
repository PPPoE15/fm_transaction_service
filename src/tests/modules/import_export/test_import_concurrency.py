"""Postgres сериализует импорт с обычными изменениями категорий и созданием операций."""

import asyncio
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.modules.import_export.infrastructure.uow import ImportUnitOfWork
from apps.shared.db.session import async_session_factory
from tests.conftest import TokenFactory
from tests.modules.import_export.test_import_api import add_category, upload_content


async def wait_for_database_lock() -> None:
    """Дождаться реального ожидания блокировки в Postgres, а не предполагать его по задержке."""
    async with asyncio.timeout(5):
        while True:
            async with async_session_factory() as session:
                waiting = await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND wait_event_type='Lock'"
                    )
                )
            if waiting:
                return
            await asyncio.sleep(0.01)


@pytest.mark.db
@pytest.mark.parametrize("change", ["name", "category_type"])
async def test_category_change_waits_for_import(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    """Переименование и смена типа ждут завершения импорта под блокировкой строк."""
    headers = {"Authorization": f"Bearer {make_token()}"}
    uid = await add_category(client, headers, "Еда", "outcome")
    locked, release = asyncio.Event(), asyncio.Event()
    original = ImportUnitOfWork.commit

    async def held_commit(uow: ImportUnitOfWork) -> None:
        """Задержать commit после сопоставления категорий и формирования операций."""
        locked.set()
        await release.wait()
        await original(uow)

    monkeypatch.setattr(ImportUnitOfWork, "commit", held_commit)
    imported = asyncio.create_task(
        client.post(
            "/import-export/imports/outcome?format=csv",
            headers=headers,
            files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
        )
    )
    await asyncio.wait_for(locked.wait(), 5)
    mutation = asyncio.create_task(
        client.patch(
            f"/categories/{uid}", headers=headers, json={change: "income" if change == "category_type" else "Новое"}
        )
    )
    try:
        await wait_for_database_lock()
        assert not mutation.done()
    finally:
        release.set()
    result, changed = await asyncio.wait_for(asyncio.gather(imported, mutation), 10)
    assert result.status_code == HTTPStatus.CREATED, result.text
    assert changed.status_code == (HTTPStatus.BAD_REQUEST if change == "category_type" else HTTPStatus.OK), changed.text
    if change == "category_type":
        assert changed.json()["code"] == "FM-400101"


@pytest.mark.db
async def test_import_quota_competes_with_manual_create(
    db_engine: AsyncEngine,
    client: AsyncClient,
    make_token: TokenFactory,
) -> None:
    """Обычная вставка и пакет вместе не могут превысить квоту в 100000 операций."""
    owner = uuid4()
    headers = {"Authorization": f"Bearer {make_token(owner)}"}
    uid = await add_category(client, headers, "Еда", "outcome")
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO transactions (uid,user_uid,category_uid,transaction_date,money_sum,transaction_type) "
                "SELECT gen_random_uuid(),:owner,:category,'2026-01-01',1,'outcome' FROM generate_series(1,99998)"
            ),
            {"owner": owner, "category": UUID(uid)},
        )
        await session.commit()
    imported, manual = await asyncio.gather(
        client.post(
            "/import-export/imports/outcome?format=csv",
            headers=headers,
            files={"file": ("a.csv", upload_content("outcome", "csv"), "text/csv")},
        ),
        client.post(
            "/transactions",
            headers=headers,
            json={
                "category_uid": uid,
                "money_sum": 1,
                "transaction_type": "outcome",
                "transaction_date": "2026-01-01T00:00:00",
            },
        ),
    )
    assert sorted([imported.status_code, manual.status_code]) == [HTTPStatus.CREATED, HTTPStatus.CONFLICT]
    rejected = imported if imported.status_code == HTTPStatus.CONFLICT else manual
    assert rejected.json()["code"] == "FM-409202"
    listed = await client.get("/transactions", headers=headers)
    assert listed.json()["total"] == (100000 if imported.status_code == HTTPStatus.CREATED else 99999)
