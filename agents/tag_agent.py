# agents/tag_agent.py
import random

class TAGAgent:
    """
    Tight-Aggressive bot.
    - Only plays strong hands
    - Bets good flops
    - Folds often
    """

    STRONG_HANDS = {
        # Pairs
        "AA", "KK", "QQ", "JJ", "TT",
        # Broadways
        "AKs", "AQs", "AJs", "KQs",
        "AKo", "AQo"
    }

    def act(self, **kw):
        hole = kw["hole_cards"]
        to_call = kw["to_call"]
        stack = kw["stack"]
        street = kw["street"]

        # Encode hand like "AKs"
        ranks = "".join([c.rank for c in hole])
        suits = [c.suit for c in hole]
        suited = suits[0] == suits[1]
        key = ranks + ("s" if suited else "o")

        strong = key in self.STRONG_HANDS

        if street == "preflop":
            if strong:
                # raise or call
                if to_call > 0:
                    return {"type": "call"}
                else:
                    bet = min(15, stack)
                    return {"type": "bet", "amount": bet}
            else:
                # weak hand facing a bet -> fold
                if to_call > 0:
                    return {"type": "fold"}
                return {"type": "call"}

        # Postflop:
        if strong:
            if to_call > 0:
                return {"type": "call"}
            return {"type": "bet", "amount": min(20, stack)}

        # weak hand
        if to_call > 0:
            return {"type": "fold"}
        return {"type": "call"}
