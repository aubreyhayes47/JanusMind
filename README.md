# **JanusMind — Poker Simulation & AI Research Engine**

JanusMind is a modular Texas Hold’em simulation environment built for experimentation with game-theoretic algorithms, range inference, and self-play reinforcement learning. The system starts with a clear, fully transparent hand engine and rule-based agents, and is engineered to scale toward multi-player (2–9 seat) poker AI research.

The project emphasizes clarity, extensibility, and full control over every part of the game flow — ideal for both experimentation and long-term development.

---

# 🗂 **Project Structure**

| Path                | Description                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| `deck.py`           | Card and deck utilities (shuffle, deal).                                                          |
| `actions.py`        | Enumerations for legal poker actions (fold, check, call, bet, raise).                             |
| `player.py`         | `PlayerState` dataclass tracking stack, bets, status flags, and participation.                    |
| `betting.py`        | Optional standalone betting engine for individual streets.                                        |
| `hand.py`           | Full single-hand orchestration: blinds → betting rounds → community cards → side pots → showdown. |
| `hand_evaluator.py` | Wrapper around [Treys](https://pypi.org/project/treys/) for fast hand evaluation.                 |
| `agents/`           | Simple rule-based agents (always-call, always-fold, random, TAG, LAG).                            |
| `scratch.py`        | Simple script for testing deck logic.                                                             |

---

# 🔧 **Requirements**

* Python 3.10+
* [`treys`](https://pypi.org/project/treys/)

Install dependencies:

```bash
pip install treys
```

---

# ▶️ **Running a Hand Simulation**

Example:

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
for i, p in enumerate(result["players"]):
    print(f"Player {i} stack:", p.stack)
print("Side pots:", result["side_pots"])
print("Showdown:", result["result"])
```

**Key Notes:**

* `play_hand()` manages dealing, blinds, betting, community cards, and showdown.
* Agents implement a single `act()` method that returns a dict describing their action.
* Betting is simplified for early experimentation (single bet per street).

---

# 🧪 **Testing Utilities**

* `python scratch.py` — tests basic deck behavior.
* `python -m simulation.runner --hands 25 --seed 7 --verbose` — run the new multi-hand harness.
* Create new experiment scripts to test agent behavior, betting logic, or entire hand flows.

### Structured Action Logging

Every betting decision can be streamed through the new `SelfPlayLogger`, enabling you to capture a complete record of all hands. The logger records timestamped entries with the acting seat, bet size, pot size, and board texture at the moment of the decision.

There are three append-only backends:

| Mode    | Description                                  | CLI usage example |
| ------- | --------------------------------------------- | ----------------- |
| `stdout` | Prints JSON to the console for quick debugging. | `--action-log-mode stdout` |
| `jsonl` | Appends newline-delimited JSON to a file.        | `--action-log-mode jsonl --action-log-path logs/actions.jsonl` |
| `parquet` | Streams Parquet rows (requires `pyarrow`).     | `--action-log-mode parquet --action-log-path logs/actions.parquet` |

To log every simulated hand, pass the desired mode (and path for file-backed modes) when invoking the runner:

```bash
python -m simulation.runner --hands 1000 --action-log-mode jsonl --action-log-path logs/actions.jsonl
```

The same options are available via config files under the `action_log` key:

```json
{
  "action_log": {
    "mode": "jsonl",
    "path": "logs/actions.jsonl"
  }
}
```

All agents automatically emit events, so turning the logger on is sufficient to ensure every hand is fully recorded.

### Simulation Runner Configuration

`simulation/runner.py` can be driven entirely from CLI flags or from a JSON config file. Config files let you describe tables (stacks, blind sizes, agent classes) and batch settings (hand count, concurrency, RNG seeding, checkpoint cadence).

Example `config/small_batch.json`:

```json
{
  "num_hands": 1000,
  "concurrency": 4,
  "seed": 1337,
  "checkpoint_interval": 200,
  "checkpoint_path": "checkpoints/stats.json",
  "tables": [
    {
      "stacks": [200, 200],
      "sb": 1,
      "bb": 2,
      "agents": [
        "agents.tag_agent.TAGAgent",
        "agents.random_agent.RandomAgent"
      ]
    }
  ]
}
```

Run it with `python -m simulation.runner --config config/small_batch.json`. Override any field on the CLI (for example `--hands 100` or `--checkpoint-interval 25`). The harness returns aggregated stats (hands played, total pot, per-seat wins) and exposes a hook API so downstream loggers/metric collectors can subscribe to each completed hand.

---

# 🚀 **Technical Roadmap**

This roadmap outlines the evolution of JanusMind from a simple hand simulator into a full poker AI research system.

---

## **1. Core Poker Engine (Current Stage)**

* Deck + card representation
* Player state
* Blinds and hand initialization
* Betting rounds
* Community card progression
* Showdown + Treys integration
* Side-pot handling
* Plug-and-play agent architecture

---

## **2. Multi-Agent Self-Play System**

* Efficient simulation of thousands/millions of hands
* Logging of all decisions, bets, and outcomes
* Seat rotation + multi-seat support
* EV and bb/100 computation
* Opponent-pool simulations

---

## **3. Supervised Learning (Behavioral Cloning)**

* Encode poker states → tensors
* Small MLP or transformer policy network
* Train on self-play logs
* Output: action probabilities and value estimates
* Produce initial model: `policy_net.pt`

---

## **4. CFR Module (Counterfactual Regret Minimization)**

Implement CFR for simplified games:

* Kuhn Poker
* Leduc Hold’em
* Optional: bigger abstractions of Hold’em

Features:

* Regret tables
* Strategy averaging
* Exploitability estimates

This module provides a theoretically grounded baseline.

---

## **5. Range Estimation Network**

A system that infers opponent hand distributions using:

* actions across streets
* board texture
* pot geometry
* stack sizes
* position and past behavior

Outputs a probability distribution covering all possible hole-card combinations.

---

## **6. Reinforcement Learning via Self-Play**

* PPO or NFSP-style reinforcement learning
* Train models against:

  * earlier snapshots
  * rule-based agents
  * population mixtures
* Curriculum: heads-up → short-handed → 6-max → 9-max
* Periodic checkpointing

---

## **7. Multi-Seat Architecture (2–9 Players)**

* Seat-relative feature encoding
* Masked embeddings for empty seats
* Correct handling of asymmetric information
* Multi-agent value bootstrapping
* Robust training over variable player counts

---

## **8. Advanced Capabilities (Optional)**

* Endgame (turn/river) equilibrium solvers
* Bet-size abstraction and action un-abstraction
* Tournament-mode decision-making (ICM-aware)
* Opponent profiling with long-term stats
* GUI or CLI for humans to play against agents

---

# 🧭 **Design Goals**

* Transparent, readable code
* Deterministic where appropriate
* Easy to extend for research
* Lightweight enough to run fully on a laptop
* Modular architecture suitable for ML integration

---

# 📜 **License**

This project is licensed under the **Apache License 2.0**.
See `LICENSE` for details.
ust tell me.
