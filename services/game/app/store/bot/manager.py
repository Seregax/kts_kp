from __future__ import annotations

import asyncio
import logging
import typing
from datetime import datetime

from shared.base.base_accessor import BaseAccessor
from shared.models.game import GameStatus, RoundStatus

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

    from shared.rabbit.schemas import VkUpdate

logger = logging.getLogger(__name__)


class BotManager(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self.timers: dict[int, asyncio.Task] = {}

    async def connect(self, app: Application) -> None:
        await self.restore_state()

    async def handle_update(self, update: VkUpdate) -> None:
        logger.info(
            "Received update: type=%s chat_id=%s user_id=%s",
            update.type,
            update.chat_id,
            update.user_id,
        )

    async def restore_state(self) -> None:
        active_games = await self.app.store.game.get_all_active_games()
        for game in active_games:
            if (
                game.status == GameStatus.LOBBY
                and game.lobby_expires_at is not None
            ):
                remaining = (
                    game.lobby_expires_at - datetime.utcnow()
                ).total_seconds()
                logger.info(
                    "Found lobby game %d, %.1fs remaining",
                    game.id,
                    remaining,
                )
            elif game.status == GameStatus.PLAYING:
                current_round = await self.app.store.game.get_current_round(
                    game.id
                )
                if (
                    current_round
                    and current_round.status == RoundStatus.PLAYER_TURN
                ):
                    logger.info(
                        "Found in-progress round %d for game %d",
                        current_round.id,
                        game.id,
                    )
