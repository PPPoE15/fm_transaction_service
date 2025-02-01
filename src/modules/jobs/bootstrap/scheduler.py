import datetime as dt
import logging
from typing import Dict, Optional, Union

# INFO: Без отключения проверок mypy ругается на "missing library stubs or py.typed marker"
from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore   # noqa: PGH003
from apscheduler.triggers.cron import CronTrigger  # type: ignore   # noqa: PGH003
from pytz import utc  # type: ignore   # noqa: PGH003

from modules.jobs.logger import get_logger

scheduler = BlockingScheduler(timezone=utc)


# TODO: разобраться что он делает, по возможности сделать проще.
class CustomCron(CronTrigger):
    """Кастомный обработчик расписания для cron job"""

    @classmethod
    def from_parameters(
        cls,
        interval_type: str,
        interval_value: int,
        start_date: dt.datetime,
        end_date: Optional[dt.datetime] = None,
    ) -> "CustomCron":
        data: Dict[str, Dict[str, Union[int, str]]] = {
            "minute": {
                "second": start_date.second,
                "minute": f"*/{interval_value}",
            },
            "hour": {
                "second": start_date.second,
                "minute": start_date.minute,
                "hour": f"*/{interval_value}",
            },
            "day": {
                "second": start_date.second,
                "minute": start_date.minute,
                "hour": start_date.hour,
                "day": f"*/{interval_value}",
            },
            "week": {
                "second": start_date.second,
                "minute": start_date.minute,
                "hour": start_date.hour,
                "day": f"*/{7 * interval_value}",
            },
            "month": {
                "second": start_date.second,
                "minute": start_date.minute,
                "hour": start_date.hour,
                "day": f"*/{interval_value}",
                "month": f"*/{interval_value}",
            },
        }

        return cls(
            **data[interval_type],
            start_date=start_date,
            end_date=end_date,
        )


def setup(logger: Optional[logging.Logger] = None) -> None:
    """Настройка и запуск планировщика задач."""
    if logger is None:
        logger = get_logger()
    scheduler.configure(logger=logger)

    # Регистрируем джобы. Пример:
    # task_settings = worker_settings.TASK_NAME
    # scheduler.add_job(
    #     task_path.task.send,
    #     CustomCron.from_parameters(
    #         interval_type=task_settings.INTERVAL_TYPE,
    #         interval_value=task_settings.INTERVAL_VALUE,
    #         start_date=aware_now() + dt.timedelta(seconds=task_settings.START_OFFSET),
    #         end_date=None,
    #     ),
    # )

    scheduler.start()
