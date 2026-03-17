from __future__ import annotations

import asyncio
import logging
import typing
from datetime import datetime

from app.store.bot.handlers import LobbyHandler, RoundHandler
from shared.base.base_accessor import BaseAccessor
from shared.models.game import GameStatus, RoundStatus

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

    from shared.rabbit.schemas import (
        VkMessageEvent,
        VkMessageNew,
        VkSentCallback,
        VkUpdate,
    )

logger = logging.getLogger(__name__)


class BotManager(BaseAccessor):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self.timers: dict[int, asyncio.Task] = {}
        # game_id → welcome message_id (populated via vk_sent_callbacks)
        self.welcome_message_ids: dict[int, int] = {}
        self._lobby = LobbyHandler(app)
        self.round_handler = RoundHandler(app)

    async def connect(self, app: Application) -> None:
        await self.restore_state()

    async def start_round(self, game_id: int) -> None:
        await self.round_handler.start_round(game_id)

    async def handle_update(self, update: VkUpdate) -> None:
        logger.info(
            "Received update: type=%s chat_id=%s user_id=%s",
            update.type,
            update.chat_id,
            update.user_id,
        )
        if update.type == "message_new":
            await self._handle_message(update)  # type: ignore[arg-type]
        elif update.type == "message_event":
            await self._handle_event(update)  # type: ignore[arg-type]

    async def _handle_message(self, update: VkMessageNew) -> None:
        text = update.text.strip().lower()
        if text == "/start":
            await self._lobby.handle_start(update.chat_id, update.user_id)

    async def on_sent_callback(self, callback: VkSentCallback) -> None:
        try:
            game_id = int(callback.correlation_id)
        except ValueError:
            return
        self.welcome_message_ids[game_id] = callback.message_id

    async def _handle_event(self, update: VkMessageEvent) -> None:
        action = update.payload.get("action")
        logger.info(update)
        if action == "join":
            await self._lobby.handle_join(
                update.chat_id, update.user_id, update.event_id
            )
        elif action == "hit":
            round_id = update.payload.get("round_id")
            if round_id is not None:
                await self.round_handler.handle_hit(
                    update.chat_id,
                    int(round_id),
                    update.user_id,
                    update.event_id,
                )
        elif action == "stand":
            round_id = update.payload.get("round_id")
            if round_id is not None:
                await self.round_handler.handle_stand(
                    update.chat_id,
                    int(round_id),
                    update.user_id,
                    update.event_id,
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
                    "Found lobby game %d, %.1fs remaining", game.id, remaining
                )
                if remaining > 0:
                    task = asyncio.create_task(
                        self._lobby._lobby_timer(game.id, remaining)
                    )
                    self.timers[game.id] = task
                else:
                    task = asyncio.create_task(
                        self._lobby._start_game_or_cancel(game.id)
                    )
                    self.timers[game.id] = task

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
                    await self.round_handler.resend_player_turn(
                        game.chat_id, current_round
                    )
