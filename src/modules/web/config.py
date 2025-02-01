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
        env_prefix="WEB_",
        case_sensitive=True,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        extra="ignore",
    )


class MQSettings(BaseSettings):
    """Конфигуратор для брокера сообщений."""

    DEFAULT_USER: str = Field(description="Логин для RMQ.")
    DEFAULT_PASS: str = Field(description="Пароль для RMQ.")
    HOST: str = Field(description="Хост RMQ.")
    PORT: int = Field(description="Порт RMQ.")
    VHOST: str = Field(description="Виртаульный хост RMQ.")

    SOURCE: str = Field(description="Источник сообщений.")
    EXCH_ACM_SERVICE_EVT: str = Field(description="Имя Exchange RMQ, обрабатывающий исходящие сообщения.")
    EXCH_ACM_SERVICE_ERR: str = Field(description="Имя Exchange RMQ, обрабатывающий ошибки.")

    RETRY_ATTEMPTS: int = Field(description="Количество попыток повтора.")
    RETRY_WAIT_MIN: int = Field(description="Минимальное время ожидания в секундах между попытками повтора.")
    RETRY_WAIT_MAX: int = Field(description="Максимальное время ожидания в секундах между попытками повтора.")

    RMQ_RETRY_WAIT: int = Field(
        description="Время ожидания в секундах между попытками повтора через механизм RMQ Dead Letter.",
    )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        secrets_dir=SECRETS_DIR,
        env_file=ENV_FILES,
        env_prefix="WEB_RABBITMQ_",
        extra="ignore",
    )


app_settings = AppSettings()
mq_settings = MQSettings()
