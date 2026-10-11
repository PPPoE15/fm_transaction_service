"""Ответ 422 на нарушение формата тела: значения любых типов попадают в `rejectedValue`, а не роняют ответ в 500."""

import pytest
from httpx import AsyncClient
from starlette import status

from tests.conftest import TokenFactory


@pytest.mark.parametrize(("money_sum", "rejected"), [(1.5, "1.5"), ([1], "[1]"), ({"a": 1}, "{'a': 1}")])
async def test_non_string_rejected_value(
    client: AsyncClient, make_token: TokenFactory, money_sum: object, rejected: str
) -> None:
    """Число, список или объект в неверном поле — 422 `FM-422000` с этим значением строкой."""
    response = await client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {make_token()}"},
        json={
            "transaction_date": "2026-10-01T12:00:00",
            "category": "f171258a-1772-4ff3-b797-04bae1e0b3dc",
            "money_sum": money_sum,
            "transaction_type": "outcome",
            "description": None,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    body = response.json()
    assert body["code"] == "FM-422000"
    assert [(item["field"], item["rejected_value"]) for item in body["validation"]] == [("money_sum", rejected)]
