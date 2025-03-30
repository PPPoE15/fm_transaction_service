import logging.config

from apps import config as common_config
from apps.jobs import config
from apps.jobs.logger import get_logger


def setup() -> None:
    """Настройка логгера."""
    logging.config.dictConfig(config=common_config.log_settings.model_dump())
    if config.app_settings.DEBUG:
        logger = get_logger()
        logger.setLevel(logging.DEBUG)
