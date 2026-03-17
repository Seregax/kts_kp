from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from aiohttp.web import Application


class Store:
    def __init__(self, app: Application) -> None:
        from app.store.bot.manager import BotManager
        from app.store.game.accessor import GameAccessor
        from app.store.rabbit.callbacks import RabbitCallbackConsumer
        from app.store.rabbit.consumer import RabbitConsumer
        from app.store.rabbit.publisher import RabbitPublisher

        self.game = GameAccessor(app)
        self.publisher = RabbitPublisher(app)
        self.bot_manager = BotManager(app)
        self.consumer = RabbitConsumer(app)
        self.callbacks = RabbitCallbackConsumer(app)
