"""High-volume Hold'em simulation harness with CLI support."""
from __future__ import annotations

import argparse
import json
import importlib
import importlib.util
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from hand import HoldemHand, PlayerState
from simulation.seating import SeatManager

_SELF_PLAY_LOGGER_PATH = Path(__file__).resolve().parent.parent / "logging" / "self_play_logger.py"
_SELF_PLAY_LOGGER_SPEC = importlib.util.spec_from_file_location(
    "janus_logging.self_play_logger", _SELF_PLAY_LOGGER_PATH
)
if _SELF_PLAY_LOGGER_SPEC is None or _SELF_PLAY_LOGGER_SPEC.loader is None:
    raise ImportError("Unable to load self_play_logger module")
_SELF_PLAY_LOGGER = importlib.util.module_from_spec(_SELF_PLAY_LOGGER_SPEC)
sys.modules[_SELF_PLAY_LOGGER_SPEC.name] = _SELF_PLAY_LOGGER
_SELF_PLAY_LOGGER_SPEC.loader.exec_module(_SELF_PLAY_LOGGER)
SelfPlayLogger = _SELF_PLAY_LOGGER.SelfPlayLogger
create_logger = _SELF_PLAY_LOGGER.create_logger


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
    auto_reload: bool = True

    @classmethod
    def from_dict(cls, data: Dict) -> "TableConfig":
        return cls(
            stacks=data["stacks"],
            agents=data["agents"],
            sb=data.get("sb", 5),
            bb=data.get("bb", 10),
            auto_reload=data.get("auto_reload", True),
        )


@dataclass
class SimulationConfig:
    num_hands: int = 1
    concurrency: int = 1
    seed: Optional[int] = None
    checkpoint_interval: Optional[int] = None
    checkpoint_path: Optional[Path] = None
    tables: List[TableConfig] = field(default_factory=list)
    action_log_mode: Optional[str] = None
    action_log_path: Optional[Path] = None

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
                    auto_reload=True,
                )
            )


@dataclass
class HandTask:
    task_id: int
    hand_number: int
    table_index: int
    table_config: TableConfig
    players: List[PlayerState]
    agent_paths: List[str]
    seed: Optional[int]
    action_log_mode: Optional[str]
    action_log_path: Optional[Path]


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
        # ``summary['winners']`` can contain duplicate seat numbers when the
        # same player scoops multiple side pots. We only want to count a win
        # once per hand so that win totals add up to the number of hands
        # played (barring true split pots). Deduplicate the winners before
        # tallying.
        for seat in set(summary.get("winners", [])):
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

    players = [PlayerState(
        seat=p.seat,
        stack=p.stack,
        hole_cards=list(p.hole_cards),
        current_bet=p.current_bet,
        total_contributed=p.total_contributed,
        has_folded=p.has_folded,
    ) for p in task.players]
    agents = [_load_agent(spec) for spec in task.agent_paths]

    hand = HoldemHand(players)
    logger: Optional[SelfPlayLogger] = None
    if task.action_log_mode:
        destination = task.action_log_path
        if destination:
            destination = destination.expanduser()
        logger = create_logger(
            task.action_log_mode,
            destination=destination,
            hand_id=str(task.task_id),
        )

    try:
        result = hand.play_hand(
            agents,
            sb=task.table_config.sb,
            bb=task.table_config.bb,
            hand_id=str(task.task_id),
            action_logger=logger,
        )
    finally:
        if logger is not None:
            logger.close()

    total_pot = sum(pot for pot, _ in result.get("side_pots", []))
    if not total_pot:
        total_pot = sum(p.total_contributed for p in result.get("players", []))

    # ``result['result']`` is ordered such that the main pot is first followed by
    # any side pots. We only want to count a "hand win" for the players who won
    # the main pot so that the win counts sum to the number of hands (aside from
    # true split pots). Side-pot winners should not be double-counted.
    winners: List[int] = []
    showdown_results = result.get("result", [])
    if showdown_results:
        _, main_winners = showdown_results[0]
        winners = [p.seat for p in main_winners]

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
        self._seat_managers = [
            SeatManager(
                table.stacks,
                table.agents,
                auto_reload=table.auto_reload,
            )
            for table in self.config.tables
        ]

    def subscribe(self, callback: Callable[[Dict], None]) -> None:
        self.publisher.subscribe(callback)

    def _tasks_for_hand(self, hand_number: int) -> List[HandTask]:
        total_tables = len(self.config.tables)
        tasks: List[HandTask] = []
        for table_index, (table, manager) in enumerate(
            zip(self.config.tables, self._seat_managers)
        ):
            assignment = manager.next_hand()
            if self.config.seed is not None:
                seed = self.config.seed + hand_number * total_tables + table_index
            else:
                seed = None
            task_id = hand_number * total_tables + table_index
            tasks.append(
                HandTask(
                    task_id=task_id,
                    hand_number=hand_number,
                    table_index=table_index,
                    table_config=table,
                    players=assignment.players,
                    agent_paths=assignment.agent_paths,
                    seed=seed,
                    action_log_mode=self.config.action_log_mode,
                    action_log_path=self.config.action_log_path,
                )
            )
        return tasks

    def _handle_summary(self, summary: Dict) -> None:
        self.stats.update_from_summary(summary)
        self.publisher.publish(summary)
        self._update_seating(summary)
        self._maybe_checkpoint()

    def _update_seating(self, summary: Dict) -> None:
        result = summary.get("result") or {}
        players = result.get("players")
        if not players:
            return
        manager = self._seat_managers[summary["table_index"]]
        manager.complete_hand(players)

    def _maybe_checkpoint(self) -> None:
        if not self.config.checkpoint_interval:
            return
        if self.stats.hands_played % self.config.checkpoint_interval != 0:
            return

        checkpoint_path = self.config.checkpoint_path or Path("simulation_checkpoint.json")
        data = {"stats": self.stats.as_dict()}
        checkpoint_path = Path(checkpoint_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(data, indent=2))

    def run(self) -> SimulationStats:
        if self.config.concurrency > 1:
            with ProcessPoolExecutor(max_workers=self.config.concurrency) as pool:
                for hand_number in range(self.config.num_hands):
                    tasks = self._tasks_for_hand(hand_number)
                    for summary in pool.map(_run_single_hand, tasks):
                        self._handle_summary(summary)
        else:
            for hand_number in range(self.config.num_hands):
                tasks = self._tasks_for_hand(hand_number)
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
    parser.add_argument(
        "--action-log-mode",
        choices=["stdout", "jsonl", "parquet"],
        help="Where to stream structured action logs",
        default=None,
    )
    parser.add_argument(
        "--action-log-path",
        type=Path,
        help="Destination file for JSONL or Parquet logs",
        default=None,
    )
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
    action_log_config = config_data.get("action_log", {})
    action_log_mode = args.action_log_mode or action_log_config.get("mode")
    action_log_path_value = args.action_log_path or action_log_config.get("path")

    tables_data = config_data.get("tables", [])
    tables = [TableConfig.from_dict(entry) for entry in tables_data]

    return SimulationConfig(
        num_hands=num_hands,
        concurrency=max(1, concurrency),
        seed=seed,
        checkpoint_interval=checkpoint_interval,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else None,
        tables=tables,
        action_log_mode=action_log_mode,
        action_log_path=Path(action_log_path_value) if action_log_path_value else None,
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
