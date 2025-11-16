# deck.py
from dataclasses import dataclass
import random
from typing import List

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]  # spades, hearts, diamonds, clubs

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return str(self)


class Deck:
    def __init__(self) -> None:
        self.cards: List[Card] = [
            Card(rank, suit) for suit in SUITS for rank in RANKS
        ]
        self.shuffle()

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def deal(self, n: int = 1):
        """Return a Card if n=1, otherwise return a list of Cards."""
        if n > len(self.cards):
            raise ValueError("Not enough cards left in the deck")

        if n == 1:
            return self.cards.pop()

        dealt = self.cards[-n:]
        del self.cards[-n:]
        return dealt

    def __len__(self) -> int:
        return len(self.cards)
