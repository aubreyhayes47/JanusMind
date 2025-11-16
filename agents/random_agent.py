# agents/random_agent.py
import random

class RandomAgent:
    """
    Simplest possible poker agent:
    - calls/checks most of the time
    - sometimes bets small
    - sometimes folds
    """

    def act(self, **kw):
        to_call = kw["to_call"]
        stack = kw["stack"]

        # If facing a bet:
        if to_call > 0:
            # Randomly pick between calling or folding
            return random.choice([
                {"type": "call"},
                {"type": "fold"}
            ])

        # If not facing a bet:
        r = random.random()

        if r < 0.7:
            return {"type": "call"}  # check
        else:
            # small bet
            amount = min(10, stack)
            return {"type": "bet", "amount": amount}
