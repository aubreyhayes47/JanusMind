# JanusMind Poker Simulation

JanusMind is a lightweight Texas Hold'em simulation that focuses on heads-up and short-handed experimentation with simple rule-based agents.  The codebase exposes the core building blocks needed to model the flow of a single hand: cards and decks, player state, betting rounds, showdown logic, and pluggable agents that decide how to act.

## Project structure

| Path | Description |
| --- | --- |
| `deck.py` | Card and `Deck` definitions with shuffling and dealing utilities. |
| `actions.py` | Enumerations describing the legal betting actions (`fold`, `check`, `call`, `bet`, `raise`). |
| `player.py` | `PlayerState` dataclass that tracks stack, bet sizing, and status flags used by the betting engine. |
| `betting.py` | `BettingRound` class that enforces single-street betting logic, ensuring all bets are matched before advancing. |
| `hand.py` | `HoldemHand` orchestrates dealing, blinds, betting rounds for each street, side-pot construction, and showdown resolution. |
| `hand_evaluator.py` | Thin wrapper around [Treys](https://pypi.org/project/treys/) used to score hands and translate readable cards into Treys' format. |
| `agents/` | Collection of simple example agents (`always_call`, `always_fold`, `random_agent`, `tag_agent`, `lag_agent`) that illustrate different playing styles. |
| `scratch.py` | Minimal script that shows how to create and use a `Deck`; handy for sanity checking the environment. |

> **Note:** The repository contains `__pycache__` directories from previous runs; they can be removed safely if you prefer a clean tree.

## Requirements

- Python 3.10+
- [`treys`](https://pypi.org/project/treys/) for hand evaluation

Install the runtime dependency with:

```bash
pip install treys
```

## Running a hand simulation

Below is a short example that pits two random agents against each other. Save it as `run_hand.py` (or paste into a REPL) and execute it with `python run_hand.py`.

```python
from agents.random_agent import RandomAgent
from hand import HoldemHand, PlayerState

players = [
    PlayerState(seat=0, stack=100),
    PlayerState(seat=1, stack=100),
]

agents = [RandomAgent(), RandomAgent()]

game = HoldemHand(players)
result = game.play_hand(agents)

print("Board:", game.board_str())
for i, player in enumerate(result["players"]):
    print(f"Player {i} stack:", player.stack)
print("Side pots:", result["side_pots"])
print("Showdown:", result["result"])
```

Key behaviors to keep in mind:

1. `HoldemHand.play_hand` automatically deals cards, posts blinds (default 5/10), runs betting on each street, and handles side pots and showdown payouts.
2. Agent classes only need to implement an `act(**kwargs)` method that returns a dictionary with `type` and optional `amount` keys.  See any of the agents in `agents/` for reference.
3. `BettingRound` and `HoldemHand.run_betting_round` are intentionally simplified: they allow a single bet per street and limit betting to basic actions, making it easier to prototype behaviors.

## Testing utilities

- `scratch.py` can be executed (`python scratch.py`) to confirm the deck logic is working.
- Custom experiments can be added in new scripts by composing `Deck`, `PlayerState`, `HoldemHand`, and any agent implementation.

## Extending the project

- Implement new strategies by adding modules under `agents/` that expose the same `act` interface.
- Swap out the simplified betting logic in `hand.py` with `BettingRound` from `betting.py` if you need more granular control over per-street action order.
- Integrate the `hand_evaluator.hand_class` helper to present human-friendly descriptions (e.g., "Straight", "Full House") when displaying results.

This README is synchronized with every script currently in the repository so you can treat it as a living map of the codebase.  Update this document whenever you introduce new modules or change behavior to keep future contributors oriented.
