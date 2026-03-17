from __future__ import annotations

import logging
import typing

import aio_pika
from pydantic import TypeAdapter

from shared.base.base_accessor import BaseAccessor
from shared.rabbit.schemas import OutgoingMessage, VkSentCallback

if typing.TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage
    from aiohttp.web import Application

_QUEUE_IN = "vk_outgoing"
_QUEUE_CALLBACKS = "vk_sent_callbacks"

logger = logging.getLogger(__name__)

_adapter = TypeAdapter(OutgoingMessage)


class RabbitConsumer(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None

    async def connect(self, app: Application) -> None:
        self._connection = await aio_pika.connect_robust(app.config.rabbit.dsn)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        await self._channel.declare_queue(_QUEUE_CALLBACKS, durable=True)
        queue = await self._channel.declare_queue(_QUEUE_IN, durable=True)
        await queue.consume(self._on_message)

    async def disconnect(self, app: Application) -> None:
        if self._connection:
            await self._connection.close()

    async def publish_callback(self, callback: VkSentCallback) -> None:
        body = callback.model_dump_json().encode()
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=_QUEUE_CALLBACKS,
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=True):
            try:
                msg = _adapter.validate_json(message.body)
                await self.app.store.vk_api.send_message(msg)
            except Exception:
                logger.exception("Failed to process outgoing message")
                raise
