from sqlalchemy.ext.asyncio import create_async_engine

from apps import config as common_config
from apps.jobs import config

async_engine = create_async_engine(
    common_config.db_settings.DSN or "",
    echo=config.app_settings.DEBUG and config.db_settings.ECHO,
    connect_args={"ssl": "disable"},
)
