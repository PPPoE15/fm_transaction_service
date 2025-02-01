from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.web.connectors.postgres import async_engine

async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
