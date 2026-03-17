from __future__ import annotations

import json
import logging
import random
import typing
from typing import Any

import aiohttp

from shared.base.base_accessor import BaseAccessor
from shared.rabbit.schemas import VkSentCallback

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

    from shared.rabbit.schemas import OutgoingMessage

_VK_API_URL = "https://api.vk.com/method/"
_VK_API_VERSION = "5.131"

logger = logging.getLogger(__name__)


class VkApiAccessor(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, app: Application) -> None:
        self._session = aiohttp.ClientSession()

    async def disconnect(self, app: Application) -> None:
        if self._session:
            await self._session.close()

    async def _api_call(self, method: str, params: dict[str, Any]) -> Any:
        all_params = {
            "access_token": self.app.config.vk.token,
            "v": _VK_API_VERSION,
            **params,
        }
        async with self._session.get(
                _VK_API_URL + method, params=all_params
        ) as resp:
            data = await resp.json()
        if "error" in data:
            raise RuntimeError(
                f"VK API error {data['error']['error_code']}: "
                f"{data['error']['error_msg']}"
            )
        return data["response"]

    async def send_message(self, msg: OutgoingMessage) -> None:

        if msg.text or msg.keyboard is not None:
            params: dict[str, Any] = {
                "peer_id": msg.peer_id,
                "message": msg.text,
                "random_id": random.randint(0, 2 ** 31),
            }
            if msg.keyboard is not None:
                params["keyboard"] = json.dumps(msg.keyboard)
            message_id: int = await self._api_call("messages.send", params)

            if msg.correlation_id is not None:
                await self.app.store.rabbit.publish_callback(
                    VkSentCallback(
                        correlation_id=msg.correlation_id,
                        peer_id=msg.peer_id,
                        message_id=message_id,
                    )
                )

        if msg.event_answer is not None:
            await self._api_call(
                "messages.sendMessageEventAnswer",
                {
                    "event_id": msg.event_answer.event_id,
                    "user_id": msg.event_answer.user_id,
                    "peer_id": msg.peer_id,
                    "event_data": json.dumps(
                        {"type": "show_snackbar", "text": msg.event_answer.text}
                    ),
                },
            )
