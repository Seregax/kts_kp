from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from aiohttp.web import Application


class Store:
    def __init__(self, app: Application) -> None:
        from app.store.rabbit.accessor import RabbitPublisher
        from app.store.vk_api.accessor import VkApiAccessor
        from app.store.vk_api.poller import Poller

        self.rabbit = RabbitPublisher(app)
        self.vk_api = VkApiAccessor(app)
        self.poller = Poller(app)
