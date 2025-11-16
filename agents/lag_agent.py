# agents/lag_agent.py
import random

class LAGAgent:
    """
    Loose Aggressive agent:
    - plays most hands
    - raises/bets frequently
    - folds rarely
    """

    def act(self, **kw):
        to_call = kw["to_call"]
        stack = kw["stack"]

        # If facing bet
        if to_call > 0:
            # LAG calls most of the time
            if random.random() < 0.85:
                return {"type": "call"}
            else:
                return {"type": "fold"}

        # If no bet — bet aggressively
        if random.random() < 0.4:
            return {"type": "bet", "amount": min(25, stack)}

        return {"type": "call"}
