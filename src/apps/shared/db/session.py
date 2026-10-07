from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.config import db_settings

async_engine = create_async_engine(
    db_settings.DSN or "",
    echo=db_settings.ECHO,
    connect_args={"ssl": "disable"},
)

async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
