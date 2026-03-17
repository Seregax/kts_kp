from __future__ import annotations

import asyncio
import json
import logging
import typing
from datetime import datetime, timedelta

from app.store.bot.logic import (
    dealer_should_draw,
    format_card,
    format_hand,
    is_bust,
    new_deck,
    remaining_deck,
    resolve_round,
)
from shared.models.game import GameStatus, RoundStatus
from shared.rabbit.schemas import EventAnswer, OutgoingMessage

if typing.TYPE_CHECKING:
    from aiohttp.web import Application

    from shared.models.game import GamePlayer, GameRound

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
                        "label": "ВСТУПИТЬ",
                        "payload": '{"action":"join"}',
                    },
                    "color": "positive",
                }
            ]
        ],
    }


def _build_hit_stand_keyboard(round_id: int) -> dict:
    return {
        "inline": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "callback",
                        "label": "ХИТ",
                        "payload": json.dumps(
                            {"action": "hit", "round_id": round_id}
                        ),
                    },
                    "color": "positive",
                },
                {
                    "action": {
                        "type": "callback",
                        "label": "СТЕНД",
                        "payload": json.dumps(
                            {"action": "stand", "round_id": round_id}
                        ),
                    },
                    "color": "negative",
                },
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
                    text="Игра уже началась!",
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
                    f"Игра начнётся через {LOBBY_TIMEOUT}с!"
                    "  Нажмите ВСТУПИТЬ чтобы присоединится.."
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
                        text="Нет активных игр!",
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
                        text="Вы уже присоединились!",
                    ),
                )
            )
            return

        settings = await self.app.store.game.get_or_create_settings(chat_id)
        await self.app.store.game.get_or_create_player(
            user_id, f"Игрок {user_id}"
        )
        await self.app.store.game.add_player_to_game(
            game.id, user_id, settings.initial_balance
        )

        players = await self.app.store.game.get_game_players(game.id)
        names = ", ".join(f"Игрок @id{gp.player_id}" for gp in players)
        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id,
                text=f"Присоединились к игре: {names}",
                event_answer=EventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    text="Вы присоединились!",
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

        if len(players) < 1:
            await self.app.store.game.update_game_status(
                game_id,
                GameStatus.FINISHED,
                finished_at=datetime.utcnow(),
            )
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="Недостаточно игроков. Игра отменена.",
                )
            )
        else:
            await self.app.store.bot_manager.start_round(game_id)

        self.app.store.bot_manager.timers.pop(game_id, None)


class RoundHandler:
    def __init__(self, app: Application) -> None:
        self.app = app

    async def start_round(self, game_id: int) -> None:
        game = await self.app.store.game.get_game_by_id(game_id)
        if game is None:
            return

        chat_id = game.chat_id
        settings = await self.app.store.game.get_or_create_settings(chat_id)
        players = await self.app.store.game.get_active_game_players(game_id)

        if not players:
            return

        # Transition to PLAYING on first round
        if game.status == GameStatus.LOBBY:
            await self.app.store.game.update_game_status(
                game_id, GameStatus.PLAYING
            )

        round_number = await self.app.store.game.get_round_count(game_id) + 1
        round_ = await self.app.store.game.create_round(game_id, round_number)

        # Build initial deck and deal
        deck = new_deck()
        player_hands: dict[int, list[str]] = {}
        for gp in players:
            new_balance = gp.balance - settings.bet_amount
            await self.app.store.game.update_player_balance(gp.id, new_balance)
            hand = [deck.pop(), deck.pop()]
            await self.app.store.game.update_player_hand(gp.id, hand)
            player_hands[gp.player_id] = hand

        dealer_hand = [deck.pop(), deck.pop()]
        await self.app.store.game.update_round(
            round_.id,
            dealer_hand=dealer_hand,
            status=RoundStatus.PLAYER_TURN,
        )

        # Round start announcement
        dealer_up = format_card(dealer_hand[0])
        lines = [
            f"🃏 Раунд {round_number}!",
            f"Рука дилера: {dealer_up} [?]",
            "",
        ]
        for gp in players:
            name = gp.player.name if gp.player else f"Player {gp.player_id}"
            lines.append(f"{name}: {format_hand(player_hands[gp.player_id])}")
        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id, text="\n".join(lines)
            )
        )

        # Re-fetch players with updated hands, then send first turn
        fresh_players = await self.app.store.game.get_active_game_players(
            game_id
        )
        fresh_round = await self.app.store.game.get_round_by_id(round_.id)
        await self._send_player_turn(chat_id, fresh_round, fresh_players, 0)

    async def handle_hit(
        self, chat_id: int, round_id: int, user_id: int, event_id: str
    ) -> None:
        round_ = await self.app.store.game.get_round_by_id(round_id)
        if round_ is None or round_.status != RoundStatus.PLAYER_TURN:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="Сейчас не Ваш ход!",
                    ),
                )
            )
            return

        players = await self.app.store.game.get_active_game_players(
            round_.game_id
        )
        if round_.current_player_index >= len(players):
            return

        current = players[round_.current_player_index]
        if current.player_id != user_id:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="Сейчас не Ваш ход!",
                    ),
                )
            )
            return

        # Draw a card from the remaining deck
        all_known = list(round_.dealer_hand)
        for gp in players:
            all_known.extend(gp.hand)
        deck = remaining_deck(all_known)
        new_card = deck[0]

        new_hand = [*current.hand, new_card]
        await self.app.store.game.update_player_hand(current.id, new_hand)

        name = current.player.name if current.player else f"Player {user_id}"
        if is_bust(new_hand):
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text=f"{name} перебрал! {format_hand(new_hand)}",
                    event_answer=EventAnswer(
                        event_id=event_id, user_id=user_id, text="Перебор!"
                    ),
                )
            )
            fresh_round = await self.app.store.game.get_round_by_id(round_id)
            await self._advance_player(chat_id, fresh_round, players)
        else:
            fresh_round = await self.app.store.game.get_round_by_id(round_id)
            fresh_players = await self.app.store.game.get_active_game_players(
                round_.game_id
            )
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text=f"Карта: {format_card(new_card)}",
                    ),
                )
            )
            await self._send_player_turn(
                chat_id,
                fresh_round,
                fresh_players,
                fresh_round.current_player_index,
            )

    async def handle_stand(
        self, chat_id: int, round_id: int, user_id: int, event_id: str
    ) -> None:
        round_ = await self.app.store.game.get_round_by_id(round_id)
        if round_ is None or round_.status != RoundStatus.PLAYER_TURN:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="Сейчас не Ваш ход!",
                    ),
                )
            )
            return

        players = await self.app.store.game.get_active_game_players(
            round_.game_id
        )
        if round_.current_player_index >= len(players):
            return

        current = players[round_.current_player_index]
        if current.player_id != user_id:
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text="",
                    event_answer=EventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        text="Сейчас не Ваш ход!",
                    ),
                )
            )
            return

        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id,
                text="",
                event_answer=EventAnswer(
                    event_id=event_id, user_id=user_id, text="СТЕНД"
                ),
            )
        )
        await self._advance_player(chat_id, round_, players)

    async def _advance_player(
        self,
        chat_id: int,
        round_: GameRound,
        players: list[GamePlayer],
    ) -> None:
        next_index = round_.current_player_index + 1
        if next_index >= len(players):
            await self.app.store.game.update_round(
                round_.id, status=RoundStatus.DEALER_TURN
            )
            fresh_round = await self.app.store.game.get_round_by_id(round_.id)
            await self._dealer_turn(chat_id, fresh_round, players)
        else:
            await self.app.store.game.update_round(
                round_.id, current_player_index=next_index
            )
            fresh_round = await self.app.store.game.get_round_by_id(round_.id)
            await self._send_player_turn(
                chat_id, fresh_round, players, next_index
            )

    async def _dealer_turn(
        self,
        chat_id: int,
        round_: GameRound,
        players: list[GamePlayer],
    ) -> None:
        game_id = round_.game_id
        settings = await self.app.store.game.get_or_create_settings(chat_id)

        # Refresh player hands from DB
        fresh_players = await self.app.store.game.get_active_game_players(
            game_id
        )

        dealer_hand = list(round_.dealer_hand)
        all_known = list(dealer_hand)
        for gp in fresh_players:
            all_known.extend(gp.hand)

        while dealer_should_draw(dealer_hand):
            deck = remaining_deck(all_known)
            card = deck[0]
            dealer_hand.append(card)
            all_known.append(card)

        await self.app.store.game.update_round(
            round_.id,
            dealer_hand=dealer_hand,
            status=RoundStatus.FINISHED,
        )

        # Resolve results
        player_hands = {gp.player_id: gp.hand for gp in fresh_players}
        active_ids = [gp.player_id for gp in fresh_players]
        results = resolve_round(player_hands, dealer_hand, active_ids)

        # Build result message
        dealer_str = format_hand(dealer_hand)
        lines = [f"Дилер: {dealer_str}", ""]
        outcome_labels = {
            "win": "Победа 🎉",
            "lose": "Поражение 💀",
            "push": "Ничья 🤝",
        }
        for gp in fresh_players:
            result = results.get(gp.player_id, "lose")
            name = gp.player.name if gp.player else f"Player @{gp.player_id}"
            hand_str = format_hand(gp.hand)
            if result == "win":
                new_balance = gp.balance + settings.bet_amount * 2
            elif result == "push":
                new_balance = gp.balance + settings.bet_amount
            else:
                new_balance = gp.balance
            lines.append(
                f"{name}: {hand_str} → "
                f"{outcome_labels[result]}. Баланс: {new_balance}"
            )
            await self.app.store.game.update_player_balance(gp.id, new_balance)

        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id, text="\n".join(lines)
            )
        )

        await self.check_game_end(game_id, chat_id)

    async def check_game_end(self, game_id: int, chat_id: int) -> None:
        settings = await self.app.store.game.get_or_create_settings(chat_id)
        players = await self.app.store.game.get_active_game_players(game_id)
        all_players = await self.app.store.game.get_game_players(game_id)

        # Deactivate broke players
        for gp in players:
            if gp.balance <= 0:
                await self.app.store.game.deactivate_player(gp.id)

        active_players = await self.app.store.game.get_active_game_players(
            game_id
        )

        # Check target balance winner
        winner = next(
            (
                gp
                for gp in active_players
                if gp.balance >= settings.target_balance
            ),
            None,
        )

        # Check last-player-standing
        if (
            winner is None
            and len(active_players) <= 1
            and len(all_players) != 1
        ):
            winner = active_players[0] if active_players else None

        if winner is None and len(all_players) == 1 and not active_players:
            winner = all_players[0]

        if winner is not None:
            name = (
                winner.player.name
                if winner.player
                else f"Player {winner.player_id}"
            )
            await self.app.store.game.update_game_status(
                game_id,
                GameStatus.FINISHED,
                finished_at=datetime.utcnow(),
            )
            await self.app.store.publisher.publish(
                OutgoingMessage(
                    peer_id=_PEER_OFFSET + chat_id,
                    text=f"🏆 Игра окончена! {name} побеждает с "
                    f"{winner.balance} на балансе!",
                )
            )
        else:
            await self.start_round(game_id)

    async def resend_player_turn(self, chat_id: int, round_: GameRound) -> None:
        players = await self.app.store.game.get_active_game_players(
            round_.game_id
        )
        if round_.current_player_index < len(players):
            await self._send_player_turn(
                chat_id, round_, players, round_.current_player_index
            )

    async def _send_player_turn(
        self,
        chat_id: int,
        round_: GameRound,
        players: list[GamePlayer],
        index: int,
    ) -> None:
        gp = players[index]
        name = gp.player.name if gp.player else f"Player {gp.player_id}"
        hand_str = format_hand(gp.hand)
        dealer_up = (
            format_card(round_.dealer_hand[0]) if round_.dealer_hand else "?"
        )
        text = f"Ход {name}:\nВаша рука: {hand_str}\nРука дилера: {dealer_up}"
        await self.app.store.publisher.publish(
            OutgoingMessage(
                peer_id=_PEER_OFFSET + chat_id,
                text=text,
                keyboard=_build_hit_stand_keyboard(round_.id),
            )
        )
