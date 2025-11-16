from dataclasses import dataclass, field
from typing import List
from deck import Card

@dataclass
class PlayerState:
    seat_id: int
    stack: int
    hole_cards: List[Card] = field(default_factory=list)
    has_folded: bool = False
    is_all_in: bool = False
    current_bet: int = 0  # bet committed in current betting round

    def reset_for_new_hand(self) -> None:
        self.hole_cards.clear()
        self.has_folded = False
        self.is_all_in = False
        self.current_bet = 0

    def __str__(self):
        cards_str = " ".join(str(c) for c in self.hole_cards) if self.hole_cards else "[]"
        flags = []
        if self.has_folded:
            flags.append("FOLDED")
        if self.is_all_in:
            flags.append("ALL-IN")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        return f"Seat {self.seat_id}: stack={self.stack}, bet={self.current_bet}, cards={cards_str}{flag_str}"
