from __future__ import annotations

import logging
import typing
from typing import Any

import aiohttp

from shared.base.base_accessor import BaseAccessor
from shared.rabbit.schemas import VkMessageEvent, VkMessageNew

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

_VK_API_URL = "https://api.vk.com/method/"
_VK_API_VERSION = "5.131"

logger = logging.getLogger(__name__)


class VkApiAccessor(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._session: aiohttp.ClientSession | None = None
        self.key: str | None = None
        self.server: str | None = None
        self.ts: int | None = None

    async def connect(self, app: Application) -> None:
        self._session = aiohttp.ClientSession()

    async def disconnect(self, app: Application) -> None:
        if self._session:
            await self._session.close()

    async def _api_call(self, method: str, params: dict[str, Any]) -> dict:
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

    async def _get_long_poll_server(self) -> None:
        data = await self._api_call(
            "groups.getLongPollServer",
            {"group_id": self.app.config.vk.group_id},
        )
        self.key = data["key"]
        self.server = data["server"]
        self.ts = int(data["ts"])

    async def poll(self) -> None:
        if self.server is None:
            await self._get_long_poll_server()
        params = {
            "act": "a_check",
            "key": self.key,
            "ts": self.ts,
            "wait": 25,
        }
        async with self._session.get(self.server, params=params) as resp:
            data = await resp.json()

        failed = data.get("failed")
        if failed == 1:
            self.ts = int(data["ts"])
            return
        if failed in (2, 3):
            await self._get_long_poll_server()
            return

        self.ts = int(data["ts"])
        for update in data.get("updates", []):
            await self._process_update(update)

    async def _process_update(self, update: dict) -> None:
        update_type = update.get("type")
        obj = update.get("object", {})

        if update_type == "message_new":
            msg = obj.get("message", {})
            peer_id = msg.get("peer_id", 0)
            chat_id = (
                peer_id - 2_000_000_000 if peer_id > 2_000_000_000 else peer_id
            )
            vk_update = VkMessageNew(
                type="message_new",
                chat_id=chat_id,
                user_id=msg.get("from_id", 0),
                text=msg.get("text", ""),
                ts=msg.get("date", 0),
            )
            await self.app.store.rabbit.publish(vk_update)

        elif update_type == "message_event":
            peer_id = obj.get("peer_id", 0)
            chat_id = (
                peer_id - 2_000_000_000 if peer_id > 2_000_000_000 else peer_id
            )
            vk_update = VkMessageEvent(
                type="message_event",
                chat_id=chat_id,
                user_id=obj.get("user_id", 0),
                event_id=obj.get("event_id", ""),
                payload=obj.get("payload", {}),
                ts=obj.get("event_ts", 0),
            )
            await self.app.store.rabbit.publish(vk_update)
