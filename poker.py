import random
from itertools import combinations

# ==========================================================
# Card & Deck
# ==========================================================

RANKS = "23456789TJQKA"
SUITS = "♠♥♦♣"

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def deal(self, n=1):
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt

# ==========================================================
# Hand evaluation (simple, decent for simulation)
# ==========================================================

HAND_RANK_ORDER = {
    "High Card": 0,
    "Pair": 1,
    "Two Pair": 2,
    "Three of a Kind": 3,
    "Straight": 4,
    "Flush": 5,
    "Full House": 6,
    "Four of a Kind": 7,
    "Straight Flush": 8,
}


def evaluate_7card_hand(cards):
    """
    Returns (category_rank, tiebreaker_values) for choosing winners.
    Very simple evaluator for sim purposes. 
    You can replace with `treys`, `pbots_calc`, or `eval7`.
    """

    ranks = [RANKS.index(c.rank) for c in cards]
    suits = [c.suit for c in cards]

    # --------- helpers ---------
    def is_flush():
        for s in SUITS:
            if suits.count(s) >= 5:
                return True
        return False

    def is_straight():
        unique = sorted(set(ranks))
        # wheel
        if {12, 0, 1, 2, 3}.issubset(set(ranks)):
            return True
        for i in range(len(unique) - 4):
            if unique[i] + 4 == unique[i + 4]:
                return True
        return False

    # Count occurrences
    counts = {r: ranks.count(r) for r in set(ranks)}
    count_values = sorted(counts.values(), reverse=True)

    flush = is_flush()
    straight = is_straight()

    # CATEGORY: Straight Flush
    if flush and straight:
        return (HAND_RANK_ORDER["Straight Flush"], sorted(ranks, reverse=True))

    # CATEGORY: Four of a Kind
    if 4 in count_values:
        return (HAND_RANK_ORDER["Four of a Kind"], sorted(ranks, reverse=True))

    # CATEGORY: Full House
    if 3 in count_values and 2 in count_values:
        return (HAND_RANK_ORDER["Full House"], sorted(ranks, reverse=True))

    # CATEGORY: Flush
    if flush:
        return (HAND_RANK_ORDER["Flush"], sorted(ranks, reverse=True))

    # CATEGORY: Straight
    if straight:
        return (HAND_RANK_ORDER["Straight"], sorted(ranks, reverse=True))

    # CATEGORY: Trips
    if 3 in count_values:
        return (HAND_RANK_ORDER["Three of a Kind"], sorted(ranks, reverse=True))

    # CATEGORY: Two Pair
    if count_values.count(2) >= 2:
        return (HAND_RANK_ORDER["Two Pair"], sorted(ranks, reverse=True))

    # CATEGORY: One Pair
    if 2 in count_values:
        return (HAND_RANK_ORDER["Pair"], sorted(ranks, reverse=True))

    # CATEGORY: High Card
    return (HAND_RANK_ORDER["High Card"], sorted(ranks, reverse=True))


# ==========================================================
# Betting Logic (placeholder)
# ==========================================================

def simple_bet(player_stack, opponent_stack, pot, street):
    """
    Dumb betting placeholder:
    - Preflop: P2 calls
    - Flop/Turn/River: do nothing
    Modify to plug in real logic (GTO agents, MCTS, RL, etc.)
    """
    return pot, player_stack, opponent_stack


# ==========================================================
# Main Hand Simulator
# ==========================================================

def play_hand(p1_stack=100, p2_stack=100, sb=1, bb=2):
    deck = Deck()

    # blinds
    p1_stack -= sb
    p2_stack -= bb
    pot = sb + bb

    # deal hole cards
    p1 = deck.deal(2)
    p2 = deck.deal(2)

    print(f"Player 1 hole cards: {p1}")
    print(f"Player 2 hole cards: {p2}")

    # ------------------------------------------------------
    # PRE-FLOP
    # ------------------------------------------------------
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "preflop")

    # ------------------------------------------------------
    # FLOP
    # ------------------------------------------------------
    deck.deal(1)  # burn
    flop = deck.deal(3)
    print(f"Flop: {flop}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "flop")

    # ------------------------------------------------------
    # TURN
    # ------------------------------------------------------
    deck.deal(1)  # burn
    turn = deck.deal(1)
    print(f"Turn: {turn}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "turn")

    # ------------------------------------------------------
    # RIVER
    # ------------------------------------------------------
    deck.deal(1)  # burn
    river = deck.deal(1)
    print(f"River: {river}")
    pot, p1_stack, p2_stack = simple_bet(p1_stack, p2_stack, pot, "river")

    board = flop + turn + river
    print(f"Final board: {board}")

    # ------------------------------------------------------
    # Showdown
    # ------------------------------------------------------
    p1_eval = evaluate_7card_hand(p1 + board)
    p2_eval = evaluate_7card_hand(p2 + board)

    print("\nHand Strength:")
    print("P1:", p1_eval)
    print("P2:", p2_eval)

    if p1_eval > p2_eval:
        print("Player 1 wins", pot)
        p1_stack += pot
    elif p2_eval > p1_eval:
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
