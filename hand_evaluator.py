# hand_evaluator.py
from treys import Evaluator, Card

evaluator = Evaluator()

def str_to_treys(card_str: str):
    """Convert 'Ah' to Treys internal representation."""
    rank = card_str[0]
    suit = card_str[1]

    # treys uses:
    # s = spades, h = hearts, d = diamonds, c = clubs
    return Card.new(rank + suit)

def evaluate_hand(hole_cards, board_cards) -> int:
    """
    Returns Treys score: lower = better.
    """
    hole = [str_to_treys(str(c)) for c in hole_cards]
    board = [str_to_treys(str(c)) for c in board_cards]
    return evaluator.evaluate(hole, board)

def hand_class(score: int) -> str:
    return evaluator.class_to_string(evaluator.get_rank_class(score))
