"""
API сервиса смонтировано под префиксом `/transaction`, как у сервиса авторизации под `/auth`.

Обратный прокси передаёт путь как есть. Проверка по ответу без токена: у существующего маршрута — 401,
у несуществующего — 404.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from starlette import status

from apps.web.main import app

pytestmark = pytest.mark.asyncio


# TODO(FM-31): фикстура повторяет `client` из conftest, а литерал /transaction — main.py; вынести префикс
# в константу и фабрику клиента, чтобы при его смене тесты не разошлись с кодом
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


# TODO(FM-31): после выкатки UI с nginx без срезания /transaction (PPPoE15/financial_manager_ui#5) пути без
# префикса убираются из main.py — тест меняется на 404.
@pytest.mark.parametrize("path", ["/categories", "/transactions"])
async def test_endpoints_without_prefix_work_during_transition(root_client: AsyncClient, path: str) -> None:
    """Переходный режим: старый nginx срезает /transaction, поэтому пути без префикса пока работают."""
    response = await root_client.get(path)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


async def test_openapi_paths_have_prefix(root_client: AsyncClient) -> None:
    """Схема OpenAPI описывает пути с префиксом — как `servers: /transaction` в контракте."""
    response = await root_client.get("/api/openapi.json")

    # NOTE(FM-31): статус ответа не проверяется — при переезде схемы тест упадёт на KeyError/JSONDecodeError
    paths = response.json()["paths"]
    assert paths
    assert all(path.startswith("/transaction/") for path in paths), sorted(paths)
