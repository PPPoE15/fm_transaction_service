"""Проверки запуска и остановки воркера регулярных операций."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.config import DBSettings


def test_invalid_database_settings_do_not_disclose_password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Не выводить пароль в ошибке загрузки настроек БД при старте воркера."""
    for key in os.environ:
        if key.startswith("DB_"):
            monkeypatch.delenv(key)
    marker = "private-test-db-value"
    monkeypatch.setenv("DB_PASSWORD", marker)
    with pytest.raises(ValidationError, match="PORT") as error:
        DBSettings(_env_file=None, _secrets_dir=tmp_path)
    assert marker not in str(error.value)
    assert "input_value" not in str(error.value)
