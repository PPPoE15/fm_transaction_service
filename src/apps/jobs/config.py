from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILES = ("dev.env", "prod.env")
SECRETS_DIR = "/run/secrets"


class AppSettings(BaseSettings):
    """Конфигуратор настроек для FastAPI."""

    URL_PREFIX: str = Field("/api", description="Префикс в генерируемых FastAPI url'ах.")
    SERVER_NAME: str = Field(description="Наименование сервиса.")
    PROJECT_NAME: str = Field(description="Наименование проекта.")
    DEBUG: bool = Field(False, description="Запущен ли сервис в режиме дебага.")
    HEALTHCHECK_MODE: bool = Field(
        False,
        description=(
            "Запуск сервиса в режиме проверки состояния (Запускает пустое приложение FastAPI). "
            "Нужен DevOps'ам для проверки сборки."
        ),
    )
    model_config = SettingsConfigDict(
        env_prefix="JOBS_",
        case_sensitive=True,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        extra="ignore",
    )


# class WorkerSettings(BaseSettings):
#     """Конфигратор настроек для периодических задач"""

#     class SubClass(BaseSettings):
#         """Подкласс для настроек периодических задач"""

#         INTERVAL_TYPE: str = "hour"
#         INTERVAL_VALUE: int = 1
#         START_OFFSET: int = 0  # Смещение времени старта в минутах

#     TASK_NAME: SubClass

#     model_config = SettingsConfigDict(
#         case_sensitive=True,
#         env_prefix="JOBS_WORKER_",
#         env_nested_delimiter="__",
#         extra="ignore",
#         env_file=ENV_FILES,
#     )


app_settings = AppSettings()
# worker_settings = WorkerSettings()
