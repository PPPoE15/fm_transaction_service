from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILES = ("dev.env", "prod.env")
SECRETS_DIR = "/run/secrets"


class AppSettings(BaseSettings):
    """Конфигуратор настроек для FastAPI."""

    SERVICE_NAME: str = Field(description="Наименование сервиса.")

    model_config = SettingsConfigDict(
        env_prefix="WEB_",
        case_sensitive=True,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        extra="ignore",
    )


app_settings = AppSettings()
