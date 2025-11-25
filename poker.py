import random
import eval7  # NEW

# ==========================================================
# Card & Deck (Using our own card class but eval7 equivalent)
# ==========================================================

RANKS = "23456789TJQKA"
SUITS = "shdc"  # eval7 uses 's','h','d','c'

class Card:
    def __init__(self, rank, suit):
        self.rank = rank  # e.g. 'A'
        self.suit = suit  # e.g. 's'

    def __repr__(self):
        # Pretty-print like: A♠, 7♥, etc.
        pretty_suits = {'s':'♠','h':'♥','d':'♦','c':'♣'}
        return f"{self.rank}{pretty_suits[self.suit]}"

    def to_eval7(self):
        """Convert to eval7.Card()"""
        return eval7.Card(self.rank + self.suit)


class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def deal(self, n=1):
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt


# ==========================================================
# Hand evaluation using eval7
# ==========================================================

def evaluate_7card_hand(cards):
    """Use eval7 evaluator. Input = list of 7 Card objects."""
    eval7_cards = [c.to_eval7() for c in cards]
    score = eval7.evaluate(eval7_cards)

    # eval7: higher score = stronger hand
    return score


# ==========================================================
# Betting Logic (still a placeholder)
# ==========================================================

def simple_bet(player_stack, opponent_stack, pot, street):
    return pot, player_stack, opponent_stack


# ==========================================================
# Hand Simulator
# ==========================================================

def play_hand(p1_stack=100, p2_stack=100, sb=1, bb=2):
    deck = Deck()

    # Post blinds
    p1_stack -= sb
    p2_stack -= bb
    pot = sb + bb

    # Deal hole cards
    p1 = deck.deal(2)
    p2 = deck.deal(2)
    print(f"Player 1 hole cards: {p1}")
    print(f"Player 2 hole cards: {p2}")

    # Preflop betting
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "preflop")

    # Flop
    deck.deal(1)  # burn
    flop = deck.deal(3)
    print(f"Flop: {flop}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "flop")

    # Turn
    deck.deal(1)  # burn
    turn = deck.deal(1)
    print(f"Turn: {turn}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "turn")

    # River
    deck.deal(1)  # burn
    river = deck.deal(1)
    print(f"River: {river}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "river")

    board = flop + turn + river
    print(f"Final board: {board}")

    # Showdown
    p1_score = evaluate_7card_hand(p1 + board)
    p2_score = evaluate_7card_hand(p2 + board)

    print("\nHand Strength:")
    print("P1 eval7 score:", p1_score)
    print("P2 eval7 score:", p2_score)

    if p1_score > p2_score:
        print("Player 1 wins", pot)
        p1_stack += pot
    elif p2_score > p1_score:
        print("Player 2 wins", pot)
        p2_stack += pot
    else:
        print("Split pot")
        p1_stack += pot // 2
        p2_stack += pot // 2

    return p1_stack, p2_stack


# ==========================================================
# Run a sample hand
# ==========================================================

if __name__ == "__main__":
    s1, s2 = play_hand()
    print("\nEnding stacks:")
    print("P1:", s1)
    print("P2:", s2)
