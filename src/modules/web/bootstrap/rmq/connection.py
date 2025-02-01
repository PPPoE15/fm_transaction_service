from acm_lib_message_broker import get_connection

from modules.web.config import mq_settings
from modules.web.connectors import rmq
from modules.web.logger import get_logger


async def connect_rmq() -> None:
    """Подключиться к RMQ"""
    rmq.rmq_connection = await get_connection(
        login=mq_settings.DEFAULT_USER,
        password=mq_settings.DEFAULT_PASS,
        host=mq_settings.HOST,
        port=mq_settings.PORT,
        virtualhost=mq_settings.VHOST,
    )
    get_logger().info("Подключен к RMQ.")


async def disconnect_rmq() -> None:
    """Отключиться от RMQ"""
    if rmq.rmq_connection:
        await rmq.rmq_connection.close()
        get_logger().info("Отключен от RMQ.")
