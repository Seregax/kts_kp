from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select, update

from shared.base.base_accessor import BaseAccessor
from shared.models.game import (
    Game,
    GamePlayer,
    GameRound,
    GameSettings,
    GameStatus,
    Player,
    RoundStatus,
)

logger = logging.getLogger(__name__)


class GameAccessor(BaseAccessor):
    # --- Game ---

    async def create_game(
        self, chat_id: int, lobby_expires_at: datetime
    ) -> Game:
        async with self.app.database.session() as session:
            game = Game(
                chat_id=chat_id,
                status=GameStatus.LOBBY,
                lobby_expires_at=lobby_expires_at,
            )
            session.add(game)
            await session.commit()
            await session.refresh(game)
            return game

    async def get_game_by_id(self, game_id: int) -> Game | None:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(Game).where(Game.id == game_id)
            )
            return result.scalar_one_or_none()

    async def get_active_game_by_chat_id(self, chat_id: int) -> Game | None:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(Game).where(
                    Game.chat_id == chat_id,
                    Game.status.in_([GameStatus.LOBBY, GameStatus.PLAYING]),
                )
            )
            return result.scalar_one_or_none()

    async def get_all_active_games(self) -> list[Game]:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(Game).where(
                    Game.status.in_([GameStatus.LOBBY, GameStatus.PLAYING])
                )
            )
            return list(result.scalars().all())

    async def update_game_status(
        self,
        game_id: int,
        status: GameStatus,
        finished_at: datetime | None = None,
    ) -> None:
        async with self.app.database.session() as session:
            values: dict = {"status": status}
            if finished_at is not None:
                values["finished_at"] = finished_at
            await session.execute(
                update(Game).where(Game.id == game_id).values(**values)
            )
            await session.commit()

    # --- Player ---

    async def get_or_create_player(self, vk_id: int, name: str) -> Player:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(Player).where(Player.vk_id == vk_id)
            )
            player = result.scalar_one_or_none()
            if player is None:
                player = Player(vk_id=vk_id, name=name)
                session.add(player)
                await session.commit()
                await session.refresh(player)
            return player

    # --- GamePlayer ---

    async def add_player_to_game(
        self, game_id: int, vk_id: int, initial_balance: int
    ) -> GamePlayer:
        async with self.app.database.session() as session:
            gp = GamePlayer(
                game_id=game_id,
                player_id=vk_id,
                balance=initial_balance,
                is_active=True,
                hand=[],
            )
            session.add(gp)
            await session.commit()
            await session.refresh(gp)
            return gp

    async def get_game_players(self, game_id: int) -> list[GamePlayer]:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(GamePlayer).where(GamePlayer.game_id == game_id)
            )
            return list(result.scalars().all())

    async def get_active_game_players(self, game_id: int) -> list[GamePlayer]:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(GamePlayer).where(
                    GamePlayer.game_id == game_id,
                    GamePlayer.is_active == True,  # noqa: E712
                )
            )
            return list(result.scalars().all())

    async def update_player_balance(
        self, game_player_id: int, balance: int
    ) -> None:
        async with self.app.database.session() as session:
            await session.execute(
                update(GamePlayer)
                .where(GamePlayer.id == game_player_id)
                .values(balance=balance)
            )
            await session.commit()

    async def update_player_hand(
        self, game_player_id: int, hand: list[str]
    ) -> None:
        async with self.app.database.session() as session:
            await session.execute(
                update(GamePlayer)
                .where(GamePlayer.id == game_player_id)
                .values(hand=hand)
            )
            await session.commit()

    async def deactivate_player(self, game_player_id: int) -> None:
        async with self.app.database.session() as session:
            await session.execute(
                update(GamePlayer)
                .where(GamePlayer.id == game_player_id)
                .values(is_active=False)
            )
            await session.commit()

    # --- GameRound ---

    async def create_round(self, game_id: int, round_number: int) -> GameRound:
        async with self.app.database.session() as session:
            rnd = GameRound(
                game_id=game_id,
                round_number=round_number,
                dealer_hand=[],
                current_player_index=0,
                status=RoundStatus.DEALING,
            )
            session.add(rnd)
            await session.commit()
            await session.refresh(rnd)
            return rnd

    async def get_current_round(self, game_id: int) -> GameRound | None:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(GameRound).where(
                    GameRound.game_id == game_id,
                    GameRound.status != RoundStatus.FINISHED,
                )
            )
            return result.scalar_one_or_none()

    async def update_round(
        self,
        round_id: int,
        *,
        dealer_hand: list[str] | None = None,
        current_player_index: int | None = None,
        status: RoundStatus | None = None,
    ) -> None:
        values: dict = {}
        if dealer_hand is not None:
            values["dealer_hand"] = dealer_hand
        if current_player_index is not None:
            values["current_player_index"] = current_player_index
        if status is not None:
            values["status"] = status
        if not values:
            return
        async with self.app.database.session() as session:
            await session.execute(
                update(GameRound)
                .where(GameRound.id == round_id)
                .values(**values)
            )
            await session.commit()

    # --- GameSettings ---

    async def get_game_settings(self, chat_id: int) -> GameSettings | None:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(GameSettings).where(GameSettings.chat_id == chat_id)
            )
            return result.scalar_one_or_none()

    async def get_or_create_settings(self, chat_id: int) -> GameSettings:
        settings = await self.get_game_settings(chat_id)
        if settings is not None:
            return settings
        async with self.app.database.session() as session:
            settings = GameSettings(chat_id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
            return settings
