from typing import Dict, Type

from typing_extensions import Annotated

from apps.web.app.handlers.events.base import AbstractHandler

MessageType = Annotated[str, ...]

# Пример маппера событий. Можно группировать по очередям или каким-либо другим удобным способом.
EXAMPLE_HANDLERS_MAPPER: Dict[MessageType, Type[AbstractHandler]] = {
    # "event.type": EventHandler,
    # EventHandler - реализация абстрактного хандлера.
}
