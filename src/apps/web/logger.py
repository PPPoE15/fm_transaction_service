import logging

logger = logging.getLogger("default")


def get_logger() -> logging.Logger:
    """Возвращает логгер."""
    return logger
