import logging
from uuid import uuid4

from apps import config as common_config
from apps.web.config import app_settings
from apps.web.logger import get_logger
from apps.web.telemetry.logging_tools import ReplicaIDFilter, SegmentUIDFilter, ServiceNameFilter, TraceIDFilter


def setup() -> None:
    """Настройка логгера."""
    logging.config.dictConfig(config=common_config.log_settings.model_dump())
    logger = get_logger()

    logger.addFilter(ReplicaIDFilter(replica_uid=str(uuid4())))
    logger.addFilter(SegmentUIDFilter(segment_uid="basic"))
    logger.addFilter(ServiceNameFilter(service_name=app_settings.SERVER_NAME))
    logger.addFilter(TraceIDFilter())

    if app_settings.DEBUG:
        logger.setLevel(logging.DEBUG)
