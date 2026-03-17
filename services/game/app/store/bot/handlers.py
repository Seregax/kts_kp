from __future__ import annotations

import asyncio
import logging
import typing
from datetime import datetime, timedelta

from shared.models.game import GameStatus
from shared.rabbit.schemas import EventAnswer, OutgoingMessage

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

LOBBY_TIMEOUT = 10  # seconds
_PEER_OFFSET = 2_000_000_000

logger = logging.getLogger(__name__)


def _build_join_keyboard() -> dict:
    return {
        "inline": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "callback",
                        "label": "JOIN",
                        "payload": '{"action":"join"}',
                    },
                    "color": "positive",
                }
            ]
        ],
    }


class LobbyHandler:
    def __init__(self, app: Application) -> None:
        self.app = app

    async def handle_start(self, chat_id: int, user_id: int) -> None:
        existing = await self.app.store.game.get_active_game_by_chat_id(chat_id)
        if existing is not None:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="A game is already in progress!",
                )
            )
            return

        expires_at = datetime.utcnow() + timedelta(seconds=LOBBY_TIMEOUT)
        game = await self.app.store.game.create_game(chat_id, expires_at)
        settings = await self.app.store.game.get_or_create_settings(chat_id)

        await self.app.store.game.get_or_create_player(
            user_id, f"Player {user_id}"
        )
        await self.app.store.game.add_player_to_game(
            game.id, user_id, settings.initial_balance
        )

        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id,
                text=(
                    f"Game starting in {LOBBY_TIMEOUT}s!"
                    " Press JOIN to participate."
                ),
                keyboard=_build_join_keyboard(),
                correlation_id=str(game.id),
            )
        )

        task = asyncio.create_task(self._lobby_timer(game.id, LOBBY_TIMEOUT))
        self.app.store.bot_manager.timers[game.id] = task

    async def handle_join(
        self, chat_id: int, user_id: int, event_id: str
    ) -> None:
        game = await self.app.store.game.get_active_game_by_chat_id(chat_id)
        if game is None or game.status != GameStatus.LOBBY:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="No active lobby!",
                    ),
                )
            )
            return

        players = await self.app.store.game.get_game_players(game.id)
        if any(gp.player_id == user_id for gp in players):
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="You already joined!",
                    ),
                )
            )
            return

        settings = await self.app.store.game.get_or_create_settings(chat_id)
        await self.app.store.game.get_or_create_player(
            user_id, f"Player {user_id}"
        )
        await self.app.store.game.add_player_to_game(
            game.id, user_id, settings.initial_balance
        )

        players = await self.app.store.game.get_game_players(game.id)
        names = ", ".join(f"Player {gp.player_id}" for gp in players)
        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id,
                text=f"Players in lobby: {names}",
                event_answer=EventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    text="You joined!",
                ),
            )
        )

    async def _lobby_timer(self, game_id: int, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await self._start_game_or_cancel(game_id)
        except asyncio.CancelledError:
            logger.info("Lobby timer for game %d was cancelled", game_id)

    async def _start_game_or_cancel(self, game_id: int) -> None:
        game = await self.app.store.game.get_game_by_id(game_id)
        if game is None or game.status != GameStatus.LOBBY:
            self.app.store.bot_manager.timers.pop(game_id, None)
            return

        chat_id = game.chat_id

        welcome_id = self.app.store.bot_manager.welcome_message_ids.pop(
            game_id, None
        )
        if welcome_id is not None:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    delete_cmid=welcome_id,
                )
            )

        players = await self.app.store.game.get_active_game_players(game_id)

        if len(players) < 2:
            await self.app.store.game.update_game_status(
                game_id,
                GameStatus.FINISHED,
                finished_at=datetime.utcnow(),
            )
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="Not enough players joined. Game cancelled.",
                )
            )
        else:
            # round start will be implemented in feature/7-blackjack-logic
            logger.info(
                "Game %d lobby closed with %d players — starting round (stub)",
                game_id,
                len(players),
            )
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text=f"Lobby closed! {len(players)} players. Starting...",
                )
            )

        self.app.store.bot_manager.timers.pop(game_id, None)
