import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from pika import PlainCredentials

from apps.config import dramatiq_settings


def setup() -> None:
    """Настройка dramatiq."""
    credentials = PlainCredentials(dramatiq_settings.DEFAULT_USER, dramatiq_settings.DEFAULT_PASS)
    rabbitmq_broker = RabbitmqBroker(
        host=dramatiq_settings.HOST,
        port=dramatiq_settings.PORT,
        credentials=credentials,
        virtual_host=dramatiq_settings.VHOST,
    )
    dramatiq.set_broker(rabbitmq_broker)
