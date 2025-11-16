# agents/always_fold.py
class AlwaysFoldAgent:
    def act(self, **kw):
        to_call = kw["to_call"]
        if to_call > 0:
            return {"type": "fold"}
        return {"type": "call"}
