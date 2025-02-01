import logging
from typing import Optional

from acm_lib_message_broker.cluster_builder.cluster_builder import ClusterBuilder

from modules.web.config import mq_settings
from modules.web.connectors import rmq

constants = ...  # from modules.web.app.infrastructrure.rmq import constants


async def build_rmq_cluster(logger: Optional[logging.Logger] = None) -> None:
    """Создать необходимые для работы сервиса точки обмена и очереди."""
    async with rmq.rmq_connection.channel() as channel:
        rmq_cluster = ClusterBuilder(channel=channel, logger=logger)
        # await _declare_evt_queue(rmq_cluster)
        # await _declare_error_queue(rmq_cluster)


async def _declare_evt_queue(rmq_cluster: ClusterBuilder) -> None:
    """
    Создание очереди и подключение к точке обмена для событий.

    Args:
        rmq_cluster: Построитель кластера RMQ.
    """
    exchange_name = mq_settings.EXCH_ACM_SERVICE_EVT
    queue_evt_name = ...

    exchange_evt = await rmq_cluster.declare_exchange(name=exchange_name)

    dead_letters_exchange = await rmq_cluster.declare_exchange(
        name=f"{queue_evt_name}_dead_letters",
    )
    dead_letters_queue = await rmq_cluster.declare_queue(
        name=f"{queue_evt_name}_dead_letters",
        dead_letter_exchange=exchange_evt,
        message_ttl=mq_settings.RMQ_RETRY_WAIT,
    )
    await dead_letters_queue.bind(exchange=dead_letters_exchange, routing_key=constants.RKEY_ALL)

    queue_evt = await rmq_cluster.declare_queue(
        name=queue_evt_name,
        dead_letter_exchange=dead_letters_exchange,
    )
    await queue_evt.bind(exchange=exchange_evt, routing_key=constants.RKEY_ALL)


async def _declare_error_queue(rmq_cluster: ClusterBuilder) -> None:
    """
    Создание очереди для ошибок и подключение к точке обмена для ошибок.

    Args:
        rmq_cluster: Построитель кластера RMQ.
    """
    queue_error_name = ...
    exchange_err = await rmq_cluster.declare_exchange(name=mq_settings.EXCH_ACM_SERVICE_ERR)
    queue_err = await rmq_cluster.declare_queue(name=queue_error_name)
    await queue_err.bind(exchange=exchange_err, routing_key=constants.RKEY_ALL)
