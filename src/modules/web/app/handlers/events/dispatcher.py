import logging
from typing import Dict, Optional, Type

from acm_lib_message_broker.producer.schemas import HeadersRMQSchema
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_random

from modules.web.app.utils.exceptions import BaseError
from modules.web.config import mq_settings

from . import exceptions
from .base import AbstractHandler
from .handlers_mappers import MessageType

retry = AsyncRetrying(
    stop=stop_after_attempt(mq_settings.RETRY_ATTEMPTS),
    wait=wait_random(min=mq_settings.RETRY_WAIT_MIN, max=mq_settings.RETRY_WAIT_MAX),
)


class EventDispatcher:
    """Диспетчер входящих сообщений из RMQ."""

    def __init__(
        self,
        handlers_mapper: Dict[MessageType, Type[AbstractHandler]],
        dlx_retry_limit: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Инициализация диспетчера.

        Args:
            handlers_mapper: Маппинг входящих сообщений и их обработчиков.
            dlx_retry_limit: Лимит попыток обработки события через механизм Dead Letter.
            logger: Логгер.
        """
        self._retry_limit = dlx_retry_limit
        self._map_handlers = handlers_mapper
        self.logger = logger or logging.getLogger("default")

    @staticmethod
    def _get_headers(
        message: AbstractIncomingMessage,
    ) -> HeadersRMQSchema:
        """
        Получить заголовок события.

        Args:
            message: Входящее сообщение.

        Raises:
            EventHeadersValidationError: Ошибка валидации заголовков события.

        Returns:
            Заголовок события.
        """
        try:
            headers = HeadersRMQSchema.model_validate(message.headers)
        except ValidationError as err:
            msg = f"Ошибка валидации заголовков события. ({err})"
            raise exceptions.EventHeadersValidationError(msg) from err

        return headers

    def _get_handler(
        self,
        headers: HeadersRMQSchema,
    ) -> Optional[Type[AbstractHandler]]:
        """
        Получить обработчик события.

        Args:
            headers: Заголовок события.

        Raises:
            EventMessageTypeValidationError: Ошибка не найденного типа события.
            EventMessageHandlerNotFoundError: Ошибка не найденного обработчика события.

        Returns:
            Обработчик события и текст возможной ошибки.
        """
        if not headers.message_type:
            msg = "В заголовке события отсутствует тип."
            raise exceptions.EventMessageTypeValidationError(msg)

        handler = self._map_handlers.get(headers.message_type)
        if not handler:
            msg = f'Обработчик для события "{headers.message_type}" не найден.'
            self.logger.info(msg)
            return None

        return handler

    async def dispatch(
        self,
        message: AbstractIncomingMessage,
    ) -> None:
        """
        Определяет и запускает обработчик события.

        Args:
            message: Входящее сообщение.
        """
        msg = f"Получено событие: {message}"
        self.logger.debug(msg)

        async with message.process(ignore_processed=True):
            try:
                if self._is_dlx_retry_limit_exceed(message):
                    await message.ack()
                    msg = (
                        "[Dead Letter] Обработка события не удалась! "
                        f"Сообщение отклонено после исчерпанных попыток... {message}"
                    )
                    self.logger.error(msg)
                    return

                headers = self._get_headers(message)
                handler = self._get_handler(headers)
                if handler is None:
                    return

                async for attempt in retry:
                    with attempt:
                        await handler(message, self.logger).run()
                        msg = f"Событие успешно обработано: {message}"
                        self.logger.debug(msg)
            except BaseError as err:
                await message.reject()
                self.logger.error(err)
            except RetryError as err:
                await message.reject()
                msg = (
                    "[AsyncRetrying] Обработка события не удалась! "
                    f"Сообщение отклонено после исчерпанных попыток... {message}"
                )
                self.logger.error(msg, exc_info=err)

    def _is_dlx_retry_limit_exceed(self, message: AbstractIncomingMessage) -> bool:
        """
        Проверить достигнут ли лимит попыток обработки события через механизм dead letter.

        Args:
            message: Входящее сообщение.
        """
        retries = 0
        if "x-death" in message.headers:
            # У mypy не получается разобрать тип FieldValue поля headers
            retries = message.headers["x-death"][0]["count"] # type: ignore[index, call-overload]
        return retries > self._retry_limit
