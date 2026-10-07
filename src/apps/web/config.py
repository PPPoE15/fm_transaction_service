from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILES = ("dev.env", "prod.env")
SECRETS_DIR = "/run/secrets"


class AppSettings(BaseSettings):
    """Конфигуратор настроек для FastAPI."""

    SERVICE_NAME: str = Field(description="Наименование сервиса.")
    HEALTHCHECK_MODE: bool = Field(False, description="Для проверки сборки.")
    PUBLIC_KEY_PATH: str = Field(
        f"{SECRETS_DIR}/jwt_public_key",
        description=(
            "Расположение публичного ключа проверки подписи JWT (PEM) — того же, что у сервиса авторизации. "
            "Приватный ключ сервису транзакций не нужен."
        ),
    )
    TOKEN_SIGNING_ALGORITHM: str = Field(
        "RS256",
        description="Алгоритм подписи JWT-токена (асимметричный, как в сервисе авторизации).",
    )

    model_config = SettingsConfigDict(
        env_prefix="WEB_",
        case_sensitive=True,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        extra="ignore",
    )


app_settings = AppSettings()
