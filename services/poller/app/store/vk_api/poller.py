from __future__ import annotations

import asyncio
import logging
import typing

from shared.base.base_accessor import BaseAccessor

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

logger = logging.getLogger(__name__)


class Poller(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self._task: asyncio.Task | None = None

    async def connect(self, app: Application) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, app: Application) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self.app.store.vk_api.poll()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in poll loop")
                await asyncio.sleep(1)
