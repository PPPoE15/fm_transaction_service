from modules.web.logger import get_logger

from .connection import connect_rmq, disconnect_rmq
from .consumers import add_service_consumer, stop_consumers
from .rmq_cluster import build_rmq_cluster


async def connect() -> None:
    """Выполнить сценарий при старте сервиса."""
    logger = get_logger()

    await connect_rmq()
    await build_rmq_cluster(logger=logger)
    add_service_consumer(logger=logger)


async def disconnect() -> None:
    """Выполнить сценарий при остановке сервиса."""
    stop_consumers()
    await disconnect_rmq()
