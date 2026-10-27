from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.modules.import_export import ImportFileError, ImportIssue, api


@pytest.mark.parametrize("code", ["FM-422301", "FM-422302", "FM-422303", "FM-413301", "FM-413302", "FM-415301"])
async def test_import_error_response(code: str) -> None:
    """HTTP-адаптер переводит ошибки парсера в предусмотренную контрактом схему."""
    app = FastAPI()
    api.setup_exception_handlers(app)
    issues = (ImportIssue(2, "amount", "invalid_amount", "Недопустимая сумма"),) if code == "FM-422303" else ()

    @app.get("/parse")
    def fail() -> None:
        """Смоделировать ошибку будущего обработчика FM-93 без добавления рабочего POST."""
        raise ImportFileError(code=code, message="Ошибка файла", errors=issues, errors_truncated=bool(issues))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/parse")
    assert response.status_code == int(code[3:6])
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == code
    assert body["instance"] == "/parse"
    assert body["detail"] == "Ошибка файла"
    if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
        assert body["imported_count"] == 0
        assert body["errors_truncated"] is bool(issues)
        if issues:
            assert body["errors"] == [
                {"row": 2, "field": "amount", "reason": "invalid_amount", "message": "Недопустимая сумма"}
            ]
    else:
        assert "errors" not in body
        assert "imported_count" not in body
