"""High-volume Hold'em simulation harness with CLI support."""
from __future__ import annotations

import argparse
import json
import importlib
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

from hand import HoldemHand, PlayerState


# ---------------------------------------------------------------------------
# Configuration structures
# ---------------------------------------------------------------------------


def _load_agent(agent_path: str):
    """Instantiate an agent given a dotted path like ``agents.random.Agent``."""

    if ":" in agent_path:
        module_name, class_name = agent_path.split(":", 1)
    else:
        module_name, class_name = agent_path.rsplit(".", 1)

    module = importlib.import_module(module_name)
    agent_cls = getattr(module, class_name)
    return agent_cls()


@dataclass
class TableConfig:
    stacks: List[int]
    agents: List[str]
    sb: int = 5
    bb: int = 10

    @classmethod
    def from_dict(cls, data: Dict) -> "TableConfig":
        return cls(
            stacks=data["stacks"],
            agents=data["agents"],
            sb=data.get("sb", 5),
            bb=data.get("bb", 10),
        )


@dataclass
class SimulationConfig:
    num_hands: int = 1
    concurrency: int = 1
    seed: Optional[int] = None
    checkpoint_interval: Optional[int] = None
    checkpoint_path: Optional[Path] = None
    tables: List[TableConfig] = field(default_factory=list)

    def ensure_tables(self) -> None:
        if not self.tables:
            self.tables.append(
                TableConfig(
                    stacks=[100, 100],
                    agents=[
                        "agents.random_agent.RandomAgent",
                        "agents.random_agent.RandomAgent",
                    ],
                    sb=5,
                    bb=10,
                )
            )


@dataclass
class HandTask:
    task_id: int
    hand_number: int
    table_index: int
    table_config: TableConfig
    seed: Optional[int]


# ---------------------------------------------------------------------------
# Stats & hooks
# ---------------------------------------------------------------------------


class HandEventPublisher:
    def __init__(self) -> None:
        self._subscribers: List[Callable[[Dict], None]] = []

    def subscribe(self, callback: Callable[[Dict], None]) -> None:
        self._subscribers.append(callback)

    def publish(self, payload: Dict) -> None:
        for callback in list(self._subscribers):
            callback(payload)


@dataclass
class SimulationStats:
    hands_played: int = 0
    aggregate_pot: int = 0
    win_counts: Dict[int, int] = field(default_factory=dict)

    def update_from_summary(self, summary: Dict) -> None:
        self.hands_played += 1
        self.aggregate_pot += summary.get("total_pot", 0)
        for seat in summary.get("winners", []):
            self.win_counts[seat] = self.win_counts.get(seat, 0) + 1

    def as_dict(self) -> Dict:
        return {
            "hands_played": self.hands_played,
            "aggregate_pot": self.aggregate_pot,
            "win_counts": self.win_counts,
        }


# ---------------------------------------------------------------------------
# Core simulation logic
# ---------------------------------------------------------------------------


def _run_single_hand(task: HandTask) -> Dict:
    if task.seed is not None:
        random.seed(task.seed)

    players = [
        PlayerState(seat=i, stack=stack) for i, stack in enumerate(task.table_config.stacks)
    ]
    agents = [_load_agent(spec) for spec in task.table_config.agents]

    hand = HoldemHand(players)
    result = hand.play_hand(agents, sb=task.table_config.sb, bb=task.table_config.bb)

    total_pot = sum(pot for pot, _ in result.get("side_pots", []))
    if not total_pot:
        total_pot = sum(p.total_contributed for p in result.get("players", []))

    winners = [p.seat for _, winners in result.get("result", []) for p in winners]

    return {
        "task_id": task.task_id,
        "hand_number": task.hand_number,
        "table_index": task.table_index,
        "result": result,
        "total_pot": total_pot,
        "winners": winners,
    }


class SimulationRunner:
    def __init__(self, config: SimulationConfig):
        config.ensure_tables()
        self.config = config
        self.publisher = HandEventPublisher()
        self.stats = SimulationStats()

    def subscribe(self, callback: Callable[[Dict], None]) -> None:
        self.publisher.subscribe(callback)

    def _task_iterator(self) -> Iterator[HandTask]:
        total_tables = len(self.config.tables)
        for hand_number in range(self.config.num_hands):
            for table_index, table in enumerate(self.config.tables):
                if self.config.seed is not None:
                    seed = self.config.seed + hand_number * total_tables + table_index
                else:
                    seed = None
                task_id = hand_number * total_tables + table_index
                yield HandTask(
                    task_id=task_id,
                    hand_number=hand_number,
                    table_index=table_index,
                    table_config=table,
                    seed=seed,
                )

    def _handle_summary(self, summary: Dict) -> None:
        self.stats.update_from_summary(summary)
        self.publisher.publish(summary)
        self._maybe_checkpoint()

    def _maybe_checkpoint(self) -> None:
        if not self.config.checkpoint_interval:
            return
        if self.stats.hands_played % self.config.checkpoint_interval != 0:
            return

        checkpoint_path = self.config.checkpoint_path or Path("simulation_checkpoint.json")
        data = {"stats": self.stats.as_dict()}
        checkpoint_path = Path(checkpoint_path)
        checkpoint_path.write_text(json.dumps(data, indent=2))

    def run(self) -> SimulationStats:
        tasks = self._task_iterator()
        if self.config.concurrency > 1:
            with ProcessPoolExecutor(max_workers=self.config.concurrency) as pool:
                for summary in pool.map(_run_single_hand, tasks):
                    self._handle_summary(summary)
        else:
            for task in tasks:
                summary = _run_single_hand(task)
                self._handle_summary(summary)

        return self.stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hold'em simulation harness")
    parser.add_argument("--config", type=Path, help="Optional JSON config file", default=None)
    parser.add_argument("--hands", type=int, help="Number of hands to run", default=None)
    parser.add_argument("--concurrency", type=int, help="Process pool size", default=None)
    parser.add_argument("--seed", type=int, help="Base RNG seed", default=None)
    parser.add_argument("--checkpoint-interval", type=int, help="Hands between checkpoints", default=None)
    parser.add_argument("--checkpoint-path", type=Path, help="Where to write checkpoint stats", default=None)
    parser.add_argument("--verbose", action="store_true", help="Stream per-hand results")
    return parser.parse_args()


def _load_config_from_file(config_path: Optional[Path]) -> Dict:
    if not config_path:
        return {}
    return json.loads(config_path.read_text())


def _build_simulation_config(args: argparse.Namespace) -> SimulationConfig:
    config_data = _load_config_from_file(args.config)

    num_hands = args.hands or config_data.get("num_hands", 1)
    concurrency = args.concurrency or config_data.get("concurrency", 1)
    seed = args.seed if args.seed is not None else config_data.get("seed")
    checkpoint_interval = args.checkpoint_interval or config_data.get("checkpoint_interval")
    checkpoint_path = args.checkpoint_path or config_data.get("checkpoint_path")

    tables_data = config_data.get("tables", [])
    tables = [TableConfig.from_dict(entry) for entry in tables_data]

    return SimulationConfig(
        num_hands=num_hands,
        concurrency=max(1, concurrency),
        seed=seed,
        checkpoint_interval=checkpoint_interval,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else None,
        tables=tables,
    )


def main() -> None:
    args = _parse_args()
    config = _build_simulation_config(args)
    runner = SimulationRunner(config)

    if args.verbose:
        runner.subscribe(
            lambda summary: print(
                f"table={summary['table_index']} hand={summary['hand_number']} total_pot={summary['total_pot']}"
            )
        )

    stats = runner.run()
    print(json.dumps(stats.as_dict(), indent=2))


if __name__ == "__main__":
    main()
