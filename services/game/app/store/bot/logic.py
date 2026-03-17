import random

SUITS = ["S", "H", "D", "C"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

_SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def new_deck() -> list[str]:
    deck = [rank + suit for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def remaining_deck(known_cards: list[str]) -> list[str]:
    """Return a shuffled deck with already-dealt cards removed."""
    full = [rank + suit for suit in SUITS for rank in RANKS]
    known_set = set(known_cards)
    remaining = [c for c in full if c not in known_set]
    random.shuffle(remaining)
    return remaining


def _rank_value(card: str) -> int:
    rank = card[:-1]  # everything except last char (suit)
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_value(hand: list[str]) -> int:
    value = 0
    aces = 0
    for card in hand:
        v = _rank_value(card)
        if v == 11:
            aces += 1
        value += v
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value


def is_bust(hand: list[str]) -> bool:
    return hand_value(hand) > 21


def is_blackjack(hand: list[str]) -> bool:
    return hand_value(hand) == 21 and len(hand) == 2


def dealer_should_draw(hand: list[str]) -> bool:
    return hand_value(hand) < 17


def format_card(card: str) -> str:
    rank = card[:-1]
    suit = card[-1]
    return rank + _SUIT_SYMBOLS.get(suit, suit)


def format_hand(hand: list[str]) -> str:
    cards = " ".join(format_card(c) for c in hand)
    return f"{cards} = {hand_value(hand)}"


def resolve_round(
    player_hands: dict[int, list[str]],
    dealer_hand: list[str],
    active_player_ids: list[int],
) -> dict[int, str]:
    """Return a mapping of player_id → 'win' | 'lose' | 'push'."""
    dealer_val = hand_value(dealer_hand)
    dealer_busted = is_bust(dealer_hand)
    results: dict[int, str] = {}
    for pid in active_player_ids:
        hand = player_hands[pid]
        if is_bust(hand):
            results[pid] = "lose"
        elif dealer_busted:
            results[pid] = "win"
        elif hand_value(hand) > dealer_val:
            results[pid] = "win"
        elif hand_value(hand) == dealer_val:
            results[pid] = "push"
        else:
            results[pid] = "lose"
    return results
