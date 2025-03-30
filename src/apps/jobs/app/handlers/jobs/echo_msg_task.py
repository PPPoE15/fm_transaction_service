from apps.jobs.app.handlers.jobs.job_decorator import job
from apps.jobs.logger import get_logger


@job
def echo_msg_task(msg: str) -> None:
    """Пример задачи."""
    logger = get_logger()
    logger.info(msg)
