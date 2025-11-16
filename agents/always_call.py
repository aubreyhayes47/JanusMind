# agents/always_call.py
class AlwaysCallAgent:
    def act(self, **kw):
        to_call = kw["to_call"]
        stack = kw["stack"]

        if to_call > 0:
            amount = min(to_call, stack)
            return {"type": "call"}

        # If allowed to check:
        return {"type": "call"}
