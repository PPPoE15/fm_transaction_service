from functools import wraps
from typing import Callable, TypeVar

# INFO: Без отключения проверок mypy ругается на "missing library stubs or py.typed marker"
import dramatiq  # type: ignore  # noqa: PGH003
from typing_extensions import ParamSpec

from modules.jobs.logger import get_logger

ACTOR_QUEUE_NAME = "acm.<your-service-name-here>.jobs"

T = TypeVar("T")
P = ParamSpec("P")

logger = get_logger()


def job(function: Callable[P, T]) -> dramatiq.Actor:
    """
    Декоратор для обработчиков задач.

    Args:
        function: Декорируемая функция.
    """
    function = _log_function_calls(function=function)
    return dramatiq.actor(fn=function, queue_name=ACTOR_QUEUE_NAME)


def _log_function_calls(function: Callable[P, T]) -> Callable[P, T]:
    """
    Будет логировать запуск и окончание функции.

    Args:
        function: Декорируемая функция.
    """

    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        logger.info('Job "%s" started...', function.__name__)

        result = function(*args, **kwargs)

        logger.info('Job "%s" finished!', function.__name__)
        return result

    return wrapper
