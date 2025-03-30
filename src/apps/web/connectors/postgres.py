from sqlalchemy.ext.asyncio import create_async_engine

from apps.config import db_settings
from apps.web.config import app_settings

async_engine = create_async_engine(
    db_settings.DSN or "",
    echo=app_settings.DEBUG and db_settings.ECHO,
    connect_args={"ssl": "disable"},
)
