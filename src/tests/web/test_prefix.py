"""
API сервиса смонтировано под префиксом `/transaction`, как у сервиса авторизации под `/auth`.

Обратный прокси передаёт путь как есть, поэтому без префикса эндпоинтов нет. Проверка по ответу без
токена: у существующего маршрута — 401, у несуществующего — 404.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from starlette import status

from apps.web.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def root_client() -> AsyncIterator[AsyncClient]:
    """Клиент от корня приложения, без префикса API."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.mark.parametrize("path", ["/transaction/categories", "/transaction/transactions"])
async def test_endpoints_are_under_prefix(root_client: AsyncClient, path: str) -> None:
    """Эндпоинты доступны по пути с префиксом `/transaction`."""
    response = await root_client.get(path)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


@pytest.mark.parametrize("path", ["/categories", "/transactions"])
async def test_endpoints_without_prefix_are_not_found(root_client: AsyncClient, path: str) -> None:
    """Без префикса эндпоинтов нет."""
    response = await root_client.get(path)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_openapi_paths_have_prefix(root_client: AsyncClient) -> None:
    """Схема OpenAPI описывает пути с префиксом — как `servers: /transaction` в контракте."""
    response = await root_client.get("/api/openapi.json")

    paths = response.json()["paths"]
    assert paths
    assert all(path.startswith("/transaction/") for path in paths), sorted(paths)
