from typing import Any

from pydantic import AliasChoices, Field, PostgresDsn, ValidationError, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILES = ("dev.env", "prod.env")
SECRETS_DIR = "/run/secrets"


class DBSettings(BaseSettings):
    """Конфигуратор настроек для БД."""

    _db_env_prefix = "DB_"

    DRIVERNAME: str = "postgresql+asyncpg"
    HOST: str = Field(description="Хост БД.")
    PORT: int = Field(description="Порт БД.")
    DATABASE: str = Field(
        validation_alias=AliasChoices(
            f"{_db_env_prefix}NAME",
            f"{_db_env_prefix}DATABASE",
        ),
    )
    USERNAME: str = Field(
        description="Логин для подключения к БД.",
        validation_alias=AliasChoices(
            f"{_db_env_prefix}USER",
            f"{_db_env_prefix}USERNAME",
        ),
    )
    PASSWORD: str = Field(
        description="Пароль для подключения к БД.",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", f"{_db_env_prefix}PASSWORD"),
    )
    ECHO: bool = Field(
        False,
        description="Нужно ли выводить диагностические сообщения",
    )
    DSN: str | None = None

    @validator("DSN", pre=True)
    def assemble_postgres_dsn(cls, v: str | None, values: dict[str, Any]) -> str | None:
        if isinstance(v, str):
            return v
        try:
            return str(
                PostgresDsn.build(
                    scheme=values.get("DRIVERNAME", ""),
                    username=values.get("USERNAME"),
                    password=values.get("PASSWORD"),
                    host=values.get("HOST"),
                    port=values.get("PORT"),
                    path=f"{values.get('DATABASE')}",
                )
            )
        except ValidationError:
            return None

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_prefix=_db_env_prefix,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        extra="ignore",
    )


class LogConfig(BaseSettings):
    """Конфигуратор логера"""

    LOG_FORMAT: str = "%(levelname)s | %(asctime)s | %(pathname)s | %(lineno)s | %(message)s"
    LOG_LEVEL: str = "ERROR"

    version: int = 1
    disable_existing_loggers: bool = False

    formatters: dict = {
        "default": {
            "format": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: dict = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    loggers: dict = {
        "default": {"handlers": ["default"], "level": LOG_LEVEL},
    }


db_settings = DBSettings()
log_settings = LogConfig()
