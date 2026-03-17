from __future__ import annotations

import logging
import typing

import aio_pika
from pydantic import TypeAdapter

from shared.base.base_accessor import BaseAccessor
from shared.rabbit.schemas import VkSentCallback

if typing.TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage
    from aiohttp.web import Application

_QUEUE = "vk_sent_callbacks"

logger = logging.getLogger(__name__)

_adapter = TypeAdapter(VkSentCallback)


class RabbitCallbackConsumer(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None

    async def connect(self, app: Application) -> None:
        self._connection = await aio_pika.connect_robust(app.config.rabbit.dsn)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        queue = await self._channel.declare_queue(_QUEUE, durable=True)
        await queue.consume(self._on_message)

    async def disconnect(self, app: Application) -> None:
        if self._connection:
            await self._connection.close()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=True):
            try:
                callback = _adapter.validate_json(message.body)
                await self.app.store.bot_manager.on_sent_callback(callback)
            except Exception:
                logger.exception("Failed to process sent callback")
                raise
