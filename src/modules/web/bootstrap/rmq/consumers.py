import logging
from typing import Optional

from lib_message_broker import ConsumerPool

from modules.web.app.handlers.events import handlers_mappers
from modules.web.app.handlers.events.dispatcher import EventDispatcher
from modules.web.config import mq_settings
from modules.web.connectors import rmq

consumer_pool = ConsumerPool()


def add_service_consumer(logger: Optional[logging.Logger] = None) -> None:
    """
    Подключиться к RMQ очереди сервисных сообщений для прослушивания.

    Args:
        logger: Логгер.
    """
    event_dispatcher = EventDispatcher(
        handlers_mappers.EXAMPLE_HANDLERS_MAPPER,
        dlx_retry_limit=mq_settings.RETRY_ATTEMPTS,
        logger=logger,
    )

    # consumer = Consumer(
    #     connection=rmq.rmq_connection,
    #     queue_name=queue_name,
    #     callback=event_dispatcher.dispatch,
    #     logger=logger,
    # )
    # consumer_pool.add(consumer)


def stop_consumers() -> None:
    """Отключить всех слушателей."""
    consumer_pool.stop()
