from sqlalchemy.ext.asyncio import create_async_engine

from modules.config import db_settings
from modules.web.config import app_settings

async_engine = create_async_engine(
    db_settings.DSN or "",
    echo=app_settings.DEBUG and db_settings.ECHO,
    connect_args={"ssl": "disable"},
)
