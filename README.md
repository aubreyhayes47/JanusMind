# JanusMind — Poker Simulation & AI Research Engine

JanusMind is a modular Texas Hold'em environment for experimenting with hand engines, seat management, self-play agents, and largescale evaluation. The code base favors readability and deterministic flows so you can plug in new agent strategies, collect action logs, or run millions of hands without opaque side effects.

---

## 🔍 Highlights

- **Full hand pipeline**: deck management, blinds, four betting streets, side pots, and Treys-backed showdowns (`hand.py`).
- **Rule-based agents** that expose a single `act()` method and can be loaded dynamically via dotted paths (`agents/`).
- **Seat + stack orchestration** with optional auto-reload, button rotation, and blind assignment (`simulation/seating.py`).
- **High-volume runner** capable of batching multi-table simulations with concurrency, checkpoints, and structured hooks (`simulation/runner.py`).
- **Action logging** to stdout/JSONL/Parquet plus EV + bb/100 tracking (`logging/self_play_logger.py`, `metrics/ev.py`).
- **Test scaffolding** for deck sanity checks, CLI smoke runs, and pytest-based unit tests.

---

## 🗂 Project Structure

| Path                     | Description                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `deck.py`                | Card and deck utilities (shuffle, deal, burn).                                                               |
| `hand.py`                | Single-hand orchestration: blinds → betting rounds → community cards → side pots → showdown.                |
| `hand_evaluator.py`      | Wrapper around [Treys](https://pypi.org/project/treys/) for fast hand scoring.                               |
| `player.py` / `actions.py` | Player state helpers and action enumerations shared by agents and betting logic.                          |
| `payouts.py`             | Pot splitting utilities used by the showdown + metrics layers.                                               |
| `agents/`                | Baseline policies (`always_call`, `always_fold`, `random`, `TAG`, `LAG`).                                     |
| `simulation/`            | Multi-table runner, CLI entry point, and seating manager.                                                    |
| `logging/self_play_logger.py` | Append-only action log backends (stdout, JSONL, Parquet).                                               |
| `metrics/ev.py`          | EV + bb/100 aggregators fed from simulation summaries.                                                       |
| `tests/`                 | Pytest suite that covers deck operations, payouts, and seating behavior.                                     |
| `scratch.py`             | Quick manual sanity check for the deck module.                                                               |

---

## 🎮 Built-in Agents

Each agent implements `act(**state)` with the same payload passed from `HoldemHand.run_betting_round`. Available baselines:

| Module                                | Strategy summary                         |
| ------------------------------------- | ---------------------------------------- |
| `agents.always_fold.AlwaysFoldAgent`  | Immediately folds every decision.        |
| `agents.always_call.AlwaysCallAgent`  | Calls any bet until stack is exhausted.  |
| `agents.random_agent.RandomAgent`     | Chooses uniformly among legal actions.   |
| `agents.tag_agent.TAGAgent`           | Tight-aggressive heuristic betting.      |
| `agents.lag_agent.LAGAgent`           | Loose-aggressive heuristic betting.      |

When you add new agents, export them in `agents/__init__.py` so dotted-path imports keep working.

---

## ⚙️ Requirements & Installation

- Python 3.10+
- [`treys`](https://pypi.org/project/treys/) (required)
- [`pyarrow`](https://pypi.org/project/pyarrow/) (optional, Parquet logging)

```bash
pip install treys           # base dependency
pip install pyarrow         # optional, for --action-log-mode parquet
```

---

## 🧪 Single-Hand Sandbox

```python
from agents.random_agent import RandomAgent
from hand import HoldemHand, PlayerState

players = [
    PlayerState(seat=0, stack=100),
    PlayerState(seat=1, stack=100),
]
agents = [RandomAgent(), RandomAgent()]

hand = HoldemHand(players)
summary = hand.play_hand(agents, sb=5, bb=10)
print("Board:", hand.board_str())
print("Side pots:", summary["side_pots"])
print("Showdown:", summary["result"])
```

`HoldemHand` handles blinds, one bet per street, community cards, side pots, and Treys-backed showdowns. Pass an optional `action_logger` (see below) to capture every decision.

---

## 🏎 Simulation Runner & CLI

`simulation.runner` batches hands across one or more tables. Tables carry initial stacks, blind sizes, and agent classes. The `SeatManager` enforces button/blind rotation and persists stacks with optional `auto_reload` rebuys.

### Basic CLI usage

```bash
python -m simulation.runner \
  --hands 1000 \
  --concurrency 4 \
  --seed 1337 \
  --action-log-mode jsonl \
  --action-log-path logs/actions.jsonl \
  --metrics-path logs/ev_metrics.json
```

Flags:

- `--config`: JSON file with simulation settings (see below).
- `--hands`, `--concurrency`, `--seed`: override config defaults per run.
- `--checkpoint-interval` + `--checkpoint-path`: persist stats snapshots every _N_ hands.
- `--action-log-mode`/`--action-log-path`: stream betting decisions to stdout, JSONL, or Parquet.
- `--metrics-path` + `--metrics-interval`: materialize EV/BB snapshots on disk or at fixed intervals.
- `--verbose`: stream per-hand summaries to stdout.

### Config-driven runs

```json
{
  "num_hands": 1000,
  "concurrency": 2,
  "seed": 42,
  "action_log": {
    "mode": "jsonl",
    "path": "logs/actions.jsonl"
  },
  "tables": [
    {
      "stacks": [200, 200],
      "sb": 1,
      "bb": 2,
      "auto_reload": true,
      "agents": [
        "agents.tag_agent.TAGAgent",
        "agents.random_agent.RandomAgent"
      ]
    }
  ]
}
```

Run it via `python -m simulation.runner --config config/small_batch.json`. CLI flags always override config fields. `auto_reload=false` lets you track bankroll across hands; otherwise stacks reset to their initial buy-ins.

For reproducible benchmarks with no agent randomness, a deterministic expert ring is available in `config/deterministic_experts.json`:

```bash
python -m simulation.runner --config config/deterministic_experts.json --hands 250 --seed 99
```

The table seats six deterministic experts (tight-aggressive, loose-aggressive, and short-stack specialists) so every position is filled without stochastic policies.

---

## 📝 Structured Action Logging

`logging.self_play_logger.SelfPlayLogger` captures every betting action with timestamp, seat, action, bet size, pot size, board texture, the actor's hole cards, and a snapshot of all stack sizes. A dedicated `showdown` event is emitted at the end of each hand that records the final board, every player's hole cards/stack/total contribution, side pots, and the winning seats for each pot.

| Mode     | Description                                  | CLI Example |
| -------- | -------------------------------------------- | ----------- |
| `stdout` | Print newline-separated JSON events.         | `--action-log-mode stdout` |
| `jsonl`  | Append JSONL to a file (path required).      | `--action-log-mode jsonl --action-log-path logs/actions.jsonl` |
| `parquet`| Stream Parquet rows (requires `pyarrow`).    | `--action-log-mode parquet --action-log-path logs/actions.parquet` |

Turn logging on via CLI or by passing `action_logger=create_logger(...)` into `HoldemHand.play_hand` directly.

---

## 📈 EV Metrics

`metrics.ev.EVMetricsAccumulator` subscribes to hand summaries and emits per-seat chip delta, EV/hand, bb/100, and rolling averages (default 200-hand window). Use `--metrics-interval` to print snapshots mid-run and `--metrics-path` to persist the final JSON blob.

---

## ✅ Testing & Validation

Before opening a PR, run:

1. `python scratch.py` – deck sanity check.
2. `python -m simulation.runner --hands 25 --seed 7 --verbose` – end-to-end harness smoke test.
3. `python -m simulation.runner --hands 5 --action-log-mode jsonl --action-log-path /tmp/actions.jsonl` – if action logging changed.
4. `python -m pytest` – run the automated test suite.

Add targeted tests next to critical logic (betting, payouts, seating) and document any new CLI options in this README.

---

## 🧭 Design Goals

- Transparent, readable code with full type hints.
- Deterministic RNG behavior (seed everything explicitly).
- Clear separation between pure simulation logic and side effects (logging, metrics, IO).
- Extensible enough for ML integrations yet lightweight enough for laptops.

---

## 🚀 Roadmap Snapshot

1. **Core engine (complete):** deck, blinds, betting rounds, side pots, Treys integration, pluggable agents.
2. **Multi-agent self-play (current focus):** faster batching, structured logging, EV metrics, seat rotation across tables.
3. **Upcoming:** supervised learning on logged hands, CFR experiments, range estimation, RL/NFSP training, multi-seat abstractions.

---

## 📜 License

Apache License 2.0. See `LICENSE` for details.
