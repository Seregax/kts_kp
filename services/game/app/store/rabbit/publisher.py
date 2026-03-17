from __future__ import annotations

import typing

import aio_pika

from shared.base.base_accessor import BaseAccessor

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

    from shared.rabbit.schemas import OutgoingMessage

_QUEUE = "vk_outgoing"


class RabbitPublisher(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None

    async def connect(self, app: Application) -> None:
        self._connection = await aio_pika.connect_robust(app.config.rabbit.dsn)
        self._channel = await self._connection.channel()
        await self._channel.declare_queue(_QUEUE, durable=True)

    async def disconnect(self, app: Application) -> None:
        if self._connection:
            await self._connection.close()

    async def publish(self, msg: OutgoingMessage) -> None:
        body = msg.model_dump_json().encode()
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=_QUEUE,
        )
