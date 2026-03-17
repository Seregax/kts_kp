from __future__ import annotations

from sqlalchemy import func, select

from shared.base.base_accessor import BaseAccessor
from shared.models.game import (
    Game,
    GamePlayer,
    GameSettings,
    GameStatus,
    Player,
)


class GameAccessor(BaseAccessor):
    async def get_all_settings(self) -> list[GameSettings]:
        async with self.app.database.session() as session:
            result = await session.execute(select(GameSettings))
            return list(result.scalars().all())

    async def upsert_settings(
        self,
        chat_id: int,
        initial_balance: int | None = None,
        target_balance: int | None = None,
        bet_amount: int | None = None,
    ) -> GameSettings:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(GameSettings).where(GameSettings.chat_id == chat_id)
            )
            settings = result.scalar_one_or_none()
            if settings is None:
                settings = GameSettings(
                    chat_id=chat_id,
                    initial_balance=initial_balance
                    if initial_balance is not None
                    else 100,
                    target_balance=target_balance
                    if target_balance is not None
                    else 500,
                    bet_amount=bet_amount if bet_amount is not None else 10,
                )
                session.add(settings)
            else:
                if initial_balance is not None:
                    settings.initial_balance = initial_balance
                if target_balance is not None:
                    settings.target_balance = target_balance
                if bet_amount is not None:
                    settings.bet_amount = bet_amount
            await session.commit()
            await session.refresh(settings)
            return settings

    async def get_game_stats(self) -> dict:
        async with self.app.database.session() as session:
            total = await session.scalar(select(func.count(Game.id)))
            finished = await session.scalar(
                select(func.count(Game.id)).where(
                    Game.status == GameStatus.FINISHED
                )
            )
            active = await session.scalar(
                select(func.count(Game.id)).where(
                    Game.status.in_([GameStatus.LOBBY, GameStatus.PLAYING])
                )
            )
            return {
                "total_games": total or 0,
                "finished_games": finished or 0,
                "active_games": active or 0,
            }

    async def get_player_stats(self) -> list[dict]:
        async with self.app.database.session() as session:
            games_played_subq = (
                select(
                    GamePlayer.player_id,
                    func.count(GamePlayer.id).label("games_played"),
                )
                .group_by(GamePlayer.player_id)
                .subquery()
            )

            max_balance_subq = (
                select(
                    GamePlayer.game_id,
                    func.max(GamePlayer.balance).label("max_balance"),
                )
                .join(Game, Game.id == GamePlayer.game_id)
                .where(Game.status == GameStatus.FINISHED)
                .group_by(GamePlayer.game_id)
                .subquery()
            )

            wins_subq = (
                select(
                    GamePlayer.player_id,
                    func.count(GamePlayer.id).label("total_wins"),
                )
                .join(
                    max_balance_subq,
                    (GamePlayer.game_id == max_balance_subq.c.game_id)
                    & (GamePlayer.balance == max_balance_subq.c.max_balance),
                )
                .group_by(GamePlayer.player_id)
                .subquery()
            )

            stmt = (
                select(
                    Player.vk_id,
                    Player.name,
                    func.coalesce(games_played_subq.c.games_played, 0).label(
                        "games_played"
                    ),
                    func.coalesce(wins_subq.c.total_wins, 0).label(
                        "total_wins"
                    ),
                )
                .outerjoin(
                    games_played_subq,
                    Player.vk_id == games_played_subq.c.player_id,
                )
                .outerjoin(wins_subq, Player.vk_id == wins_subq.c.player_id)
                .order_by(
                    func.coalesce(games_played_subq.c.games_played, 0).desc()
                )
            )

            result = await session.execute(stmt)
            return [
                {
                    "vk_id": row.vk_id,
                    "name": row.name,
                    "games_played": row.games_played,
                    "total_wins": row.total_wins,
                }
                for row in result
            ]
