from __future__ import annotations

"""
Deterministic baseline agents used for reproducible simulations.
"""
from typing import Dict, Iterable, List

RANK_ORDER = "23456789TJQKA"


class ConservativeTAGAgent:
    """
    Very tight-aggressive policy tuned for low variance simulations.

    - Only continues with premium preflop holdings (big pairs and top broadways).
    - Bets when it has paired the board or started with a premium pocket pair.
    - Folds quickly to pressure when holding marginal hands.
    """

    PREMIUM = {
        "AA",
        "KK",
        "QQ",
        "JJ",
        "TT",
        "AKs",
        "AQs",
        "AKo",
    }

    def act(self, **state: Dict[str, object]) -> Dict[str, object]:
        hole_cards: List[object] = state["hole_cards"]
        board: Iterable[object] = state["board"]
        pot: int = int(state["pot"])
        to_call: int = int(state["to_call"])
        stack: int = int(state["stack"])
        street: str = str(state["street"])

        ranks = "".join(card.rank for card in hole_cards)
        suited = len(hole_cards) == 2 and hole_cards[0].suit == hole_cards[1].suit
        key = ranks + ("s" if suited else "o")

        has_premium = key in self.PREMIUM
        board_ranks = {card.rank for card in board}
        paired_board = bool(board_ranks.intersection({hole_cards[0].rank, hole_cards[1].rank}))
        starting_pair = hole_cards[0].rank == hole_cards[1].rank

        if street == "preflop":
            if has_premium:
                if to_call > 0:
                    return {"type": "call"}
                raise_size = min(max(to_call * 3 if to_call else 12, 8), stack)
                return {"type": "bet", "amount": raise_size}
            if to_call > 0:
                return {"type": "fold"}
            return {"type": "call"}

        if has_premium or starting_pair or paired_board:
            if to_call > 0:
                call_amount = min(to_call, stack)
                return {"type": "call", "amount": call_amount}
            bet_amount = min(max(pot // 2, 10), stack)
            return {"type": "bet", "amount": bet_amount}

        if to_call > 0:
            return {"type": "fold"}
        return {"type": "call"}


class DeterministicLAGAgent:
    """
    Loose-aggressive agent without randomness.

    - Opens and continues with most hands, preferring to apply pressure.
    - Uses pot size to size bets/raises deterministically.
    - Only relinquishes marginal spots when very deep to avoid oversized pots.
    """

    def act(self, **state: Dict[str, object]) -> Dict[str, object]:
        hole_cards: List[object] = state["hole_cards"]
        board: Iterable[object] = state["board"]
        pot: int = int(state["pot"])
        to_call: int = int(state["to_call"])
        stack: int = int(state["stack"])
        street: str = str(state["street"])

        board_pressure = len(list(board))
        high_card = max(hole_cards, key=lambda card: RANK_ORDER.index(card.rank)).rank
        street_multiplier = 1 + 0.25 * (street != "preflop")

        if to_call > 0:
            if stack <= to_call:
                return {"type": "call", "amount": stack}
            aggression = max(8, pot // 3 + board_pressure * 2)
            raise_amount = min(int(to_call * 2 * street_multiplier), stack)
            raise_amount = max(raise_amount, aggression)
            return {"type": "raise", "amount": raise_amount}

        baseline = pot // 2 if pot > 0 else 12
        bet_amount = min(max(int(baseline * street_multiplier), 6 + board_pressure), stack)
        if high_card in {"A", "K"} and stack > bet_amount:
            bet_amount = min(max(bet_amount, baseline + 4), stack)
        if stack <= bet_amount:
            return {"type": "bet", "amount": stack}
        return {"type": "bet", "amount": bet_amount}


class ShortStackSurvivalAgent:
    """
    Deterministic push/fold heuristic for small stacks.

    - Shoves premium and connected hands preflop when at risk.
    - Defends with top pairs on later streets; otherwise preserves chips by folding.
    - Bet sizing scales with remaining stack to keep decisions reproducible.
    """

    COMPACT_STARTS = {"AA", "KK", "QQ", "JJ", "AKs", "AQs", "AJs", "KQs", "AKo"}

    def act(self, **state: Dict[str, object]) -> Dict[str, object]:
        hole_cards: List[object] = state["hole_cards"]
        board: Iterable[object] = state["board"]
        pot: int = int(state["pot"])
        to_call: int = int(state["to_call"])
        stack: int = int(state["stack"])
        street: str = str(state["street"])

        ranks = "".join(card.rank for card in hole_cards)
        suited = len(hole_cards) == 2 and hole_cards[0].suit == hole_cards[1].suit
        key = ranks + ("s" if suited else "o")
        board_ranks = {card.rank for card in board}

        premium = key in self.COMPACT_STARTS
        paired_board = bool(board_ranks.intersection({hole_cards[0].rank, hole_cards[1].rank}))
        short_stack = stack <= max(20, pot // 2 or 1)

        if street == "preflop" and short_stack:
            if premium or hole_cards[0].rank == hole_cards[1].rank:
                shove = stack
                return {"type": "bet", "amount": shove}
            if to_call > stack // 3:
                return {"type": "fold"}
            return {"type": "call", "amount": min(to_call, stack)}

        if paired_board or premium:
            if to_call > 0:
                call_amount = min(to_call, stack)
                return {"type": "call", "amount": call_amount}
            bet_amount = min(max(pot // 2, 6), stack)
            return {"type": "bet", "amount": bet_amount}

        if to_call > 0:
            return {"type": "fold"}
        return {"type": "call"}
