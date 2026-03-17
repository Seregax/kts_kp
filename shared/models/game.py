import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import BaseModel


class GameStatus(enum.Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class RoundStatus(enum.Enum):
    DEALING = "dealing"
    PLAYER_TURN = "player_turn"
    DEALER_TURN = "dealer_turn"
    FINISHED = "finished"


class GameSettings(BaseModel):
    __tablename__ = "game_settings"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    initial_balance: Mapped[int] = mapped_column(nullable=False, default=100)
    target_balance: Mapped[int] = mapped_column(nullable=False, default=500)
    bet_amount: Mapped[int] = mapped_column(nullable=False, default=10)


class Game(BaseModel):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(nullable=False, index=True)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus), nullable=False, default=GameStatus.LOBBY
    )
    lobby_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    players: Mapped[list["GamePlayer"]] = relationship(
        "GamePlayer", back_populates="game", lazy="selectin"
    )
    rounds: Mapped[list["GameRound"]] = relationship(
        "GameRound", back_populates="game", lazy="selectin"
    )


class Player(BaseModel):
    __tablename__ = "players"

    vk_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)


class GamePlayer(BaseModel):
    __tablename__ = "game_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.vk_id"), nullable=False
    )
    balance: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    hand: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    game: Mapped["Game"] = relationship("Game", back_populates="players")
    player: Mapped["Player"] = relationship("Player", lazy="selectin")


class GameRound(BaseModel):
    __tablename__ = "game_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(nullable=False)
    dealer_hand: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    current_player_index: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus), nullable=False, default=RoundStatus.DEALING
    )

    game: Mapped["Game"] = relationship("Game", back_populates="rounds")
