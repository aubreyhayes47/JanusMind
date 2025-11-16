# JanusMind Contributor Guide

Welcome to JanusMind! This document codifies the expectations for AI coding tools and human contributors working anywhere in this repository. Please read it fully before making changes.

## 1. Project Overview
- **Goal:** Modular Texas Hold'em simulator for experimentation with rule-based agents, logging, and large-scale self-play research.
- **Core modules:**
  - `deck.py`, `hand_evaluator.py`, `hand.py` implement the card/dealing/betting/showdown pipeline.
  - `agents/` houses simple policy baselines; each class exposes a single `act(**state)` method that returns a dict such as `{"type": "call"}` or `{"type": "bet", "amount": 25}`.
  - `simulation/runner.py` batches many hands via `SimulationRunner`, integrates logging/metrics, and exposes the CLI.
  - `simulation/seating.py` is the source of truth for button rotation, blind posting, and optional auto-reload stacks.
  - `logging/self_play_logger.py` emits structured action events to stdout/JSONL/Parquet.
  - `metrics/ev.py` computes chip/EV/bb/100 summaries from hand results.

## 2. Coding Conventions
1. **Python version:** Target Python ≥3.10. Prefer `from __future__ import annotations` in new modules with type annotations.
2. **Style:** Follow PEP 8/PEP 257. Keep functions short, name things descriptively, and prefer dataclasses for immutable or structured state (see `deck.Card`, `player.PlayerState`).
3. **Type hints everywhere:** Include precise typing (e.g., `List[int]`, `Optional[SelfPlayLogger]`). When objects cross module boundaries, document the expected fields. Avoid `Any` unless absolutely necessary.
4. **Determinism first:** Accept RNG seeds instead of calling `random.seed` globally. Where seeding is required (e.g., `_run_single_hand`), derive it from the task descriptor the way the runner already does.
5. **Side-effect boundaries:** Keep IO (disk, stdout) inside dedicated helpers (`SelfPlayLogger`, CLI) so that simulation/betting logic stays pure and testable.
6. **Dependencies:** Only rely on the standard library plus `treys` (and optionally `pyarrow` for Parquet logging). Guard optional imports exactly like `logging/self_play_logger.py` and never crash if `pyarrow` is missing.
7. **Error handling:** Raise `ValueError`/`RuntimeError` for invalid inputs; avoid swallowing exceptions silently. Never wrap imports in bare `except` blocks—be explicit about expected failures.
8. **Imports & structure:** Use absolute imports within the repo (`from hand import HoldemHand`). Do not introduce circular imports; extract shared helpers instead.
9. **Documentation sync:** When changing CLI flags, config fields, logging/metrics modes, or agent wiring, update `README.md` in the same PR with runnable examples.

## 3. Working With Agents
- Every agent must implement `act(**kwargs)` using the same keyword arguments sent from `HoldemHand.run_betting_round` (hole cards, board, pot, to_call, stack, street).
- Returned actions are normalized strings: `fold`, `call`, `bet`, `raise`. Include an `amount` key for bets/raises and ensure amounts are integers expressed in chips.
- Agents must never mutate global state or other players. All randomness should come from the agent’s own `random.Random` instance when reproducibility is required.
- If you add new agent modules, also export them in `agents/__init__.py` so they can be referenced by dotted paths in the simulation config.

## 4. Simulation Runner Guidelines
- `SimulationConfig.ensure_tables()` guarantees at least one table. Preserve this behavior so CLI defaults keep working.
- `HandTask` objects must remain pickleable because they cross process boundaries when `concurrency > 1`. Avoid lambdas/closures in task payloads.
- When expanding `_run_single_hand`, keep the `try/finally` that closes `SelfPlayLogger` even on errors. Make sure returned summaries always include `table_index`, `hand_number`, `total_pot`, and `winners` so `SimulationStats` and EV metrics stay consistent.
- Any new CLI option must be plumbed through `_parse_args`, `_build_simulation_config`, and (if persisted) documented in `README.md`. Keep parser help strings, config keys, and README tables in sync.
- Checkpointing (`--checkpoint-interval`/`--checkpoint-path`), action logging (`--action-log-*`), and metrics streaming (`--metrics-*`) are user-facing features—exercise them when you modify the runner.

## 5. Structured Logging
- Use `SelfPlayLogger` for all per-action logging. Pass fully stringified board cards (see the existing `action_logger` call in `hand.run_betting_round`).
- When adding new logging backends, mimic `_BaseWriter` subclasses: create directories before writing, flush frequently for streaming formats, and guard optional dependencies.
- Parquet logging must remain optional; raise `RuntimeError` with a helpful message if `pyarrow` is missing.

## 6. Testing & Validation
Run the following before opening a PR (add new commands if your change warrants it):
1. `python scratch.py` – quick deck sanity check.
2. `python -m simulation.runner --hands 25 --seed 7 --verbose` – exercises the full pipeline in-process.
3. If action logging is touched: `python -m simulation.runner --hands 5 --action-log-mode jsonl --action-log-path /tmp/actions.jsonl` and inspect the emitted file.
4. Prefer targeted unit tests when touching critical logic (betting, side pots, simulation stats). If you add tests, place them near the code they cover or inside a new `tests/` package and ensure they run with `python -m pytest`.

## 7. Documentation Expectations
- Update `README.md` whenever you add/remove CLI flags, logger modes, or agent behaviors that impact users.
- Provide inline comments explaining non-obvious poker math (e.g., side-pot calculations). Use docstrings on public functions/classes.
- Maintain this `AGENTS.md` if you introduce repo-wide policy changes.

## 8. Required Dependencies
- **treys** – Poker hand evaluation helper used throughout `hand_evaluator.py` and agent logic. Install via `pip install treys` before running the simulator or tests.
- **pyarrow** *(optional)* – Enables Parquet action logging; without it the rest of the project should still run. Match the guarded import pattern in `logging/self_play_logger.py` if you need additional optional backends.

## 9. Pull Request Checklist
- [ ] All touched modules comply with the conventions above.
- [ ] Tests/commands listed in section 6 have been run, and results are summarized in the PR.
- [ ] Any new dependencies are optional and documented.
- [ ] User-facing changes are documented.
- [ ] Added files are referenced in relevant `__init__.py` exports when necessary.

Following these practices keeps the simulator deterministic, extensible, and friendly to downstream AI tooling. Thank you for contributing!

## 10. Seat Management & Metrics
- Keep `SeatManager` authoritative for seat order, blind posting, and stack persistence. Do not reimplement this logic elsewhere—augment `SeatAssignment` if new metadata is required.
- Respect the `auto_reload` flag when mutating stacks. Any new table-level option must round-trip through `TableConfig.from_dict`, `SeatManager`, and the README docs.
- `metrics.ev.EVMetricsAccumulator` expects summaries to include `table_index`, `bb`, and a `result` containing `players` (with `seat`, `stack`, `total_contributed`) and showdown winners. Update the accumulator + docs together if you alter that contract.

