from enum import Enum, auto

class ActionType(Enum):
    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    BET = auto()
    RAISE = auto()

class Action:
    def __init__(self, action_type: ActionType, amount: int = 0):
        self.type = action_type
        self.amount = amount

    def __repr__(self):
        if self.type in {ActionType.BET, ActionType.RAISE}:
            return f"{self.type.name}({self.amount})"
        return self.type.name
