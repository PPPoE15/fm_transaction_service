import abc
import logging
from typing import Generic, Optional, Type

from aio_pika.abc import AbstractIncomingMessage
from lib_message_broker.producer.schemas import HeadersRMQSchema
from pydantic import BaseModel
from typing_extensions import TypeVar

DataT = TypeVar("DataT", bound=BaseModel)


class AbstractHandler(abc.ABC, Generic[DataT]):
    """Абстрактный класс обработчика входящих событий от RMQ."""

    _body_schema: Type[DataT]

    def __init__(
        self,
        message: AbstractIncomingMessage,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Инициализация обработчика.

        Args:
            message: Входящее сообщение.
            logger: Логгер.
        """
        self.headers: HeadersRMQSchema = HeadersRMQSchema.model_validate(message.headers)
        self.body = self._body_schema.model_validate_json(message.body)
        self.logger = logger or logging.getLogger("default")

    @abc.abstractmethod
    async def run(self) -> None:
        """Запуск обработчика."""
        raise NotImplementedError
