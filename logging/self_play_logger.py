"""Structured action logging utilities for self-play simulations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # Optional dependency for Parquet output
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore
except Exception:  # pragma: no cover - pyarrow is optional
    pa = None  # type: ignore
    pq = None  # type: ignore


@dataclass
class ActionEvent:
    """Single betting action emitted by a Hold'em hand."""

    timestamp: str
    hand_id: str
    event: str
    seat: int
    action: str
    bet_size: int
    pot: int
    board: List[str]
    hole_cards: Optional[List[str]] = None
    stack: Optional[int] = None
    to_call: Optional[int] = None
    street: Optional[str] = None
    stacks: Optional[List[int]] = None

    def as_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "hand_id": self.hand_id,
            "event": self.event,
            "seat": self.seat,
            "action": self.action,
            "bet_size": self.bet_size,
            "pot": self.pot,
            "board": self.board,
            "hole_cards": self.hole_cards,
            "stack": self.stack,
            "to_call": self.to_call,
            "street": self.street,
            "stacks": self.stacks,
        }


@dataclass
class ShowdownEvent:
    """Terminal showdown snapshot for a completed hand."""

    timestamp: str
    hand_id: str
    event: str
    board: List[str]
    players: List[Dict[str, Any]]
    side_pots: List[Dict[str, Any]]
    results: List[Dict[str, Any]]

    def as_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "hand_id": self.hand_id,
            "event": self.event,
            "board": self.board,
            "players": self.players,
            "side_pots": self.side_pots,
            "results": self.results,
        }


class _BaseWriter:
    def append(self, event: Dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        return None


class StdoutWriter(_BaseWriter):
    def append(self, event: Dict[str, Any]) -> None:
        print(json.dumps(event, separators=(",", ":")))


class JSONLWriter(_BaseWriter):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def append(self, event: Dict[str, Any]) -> None:
        self._handle.write(json.dumps(event) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


class ParquetWriter(_BaseWriter):
    def __init__(self, path: Path) -> None:
        if pq is None or pa is None:  # pragma: no cover - import-time guard
            raise RuntimeError("pyarrow is required for Parquet logging but is not installed")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer: Optional["pq.ParquetWriter"] = None

    def append(self, event: Dict[str, Any]) -> None:
        if pa is None or pq is None:  # pragma: no cover
            return
        table = pa.Table.from_pylist([event])
        if self._writer is None:
            self._writer = pq.ParquetWriter(self.path, table.schema)
        self._writer.write_table(table)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None


class SelfPlayLogger:
    """Facade that builds append-only writers for action events."""

    def __init__(self, writer: _BaseWriter, hand_id: str) -> None:
        self._writer = writer
        self.hand_id = hand_id

    def log_action(
        self,
        *,
        seat: int,
        action: str,
        bet_size: int,
        pot: int,
        board: List[str],
        hole_cards: Optional[List[str]] = None,
        stack: Optional[int] = None,
        to_call: Optional[int] = None,
        street: Optional[str] = None,
        stacks: Optional[List[int]] = None,
    ) -> None:
        event = ActionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            hand_id=self.hand_id,
            event="action",
            seat=seat,
            action=action,
            bet_size=bet_size,
            pot=pot,
            board=board,
            hole_cards=hole_cards,
            stack=stack,
            to_call=to_call,
            street=street,
            stacks=stacks,
        )
        self._writer.append(event.as_dict())

    def log_showdown(
        self,
        *,
        board: List[str],
        players: Iterable[Any],
        side_pots: Iterable[Any],
        showdown_results: Iterable[Any],
    ) -> None:
        serialized_players = [
            {
                "seat": p.seat,
                "stack": getattr(p, "stack", None),
                "hole_cards": [str(card) for card in getattr(p, "hole_cards", [])],
                "has_folded": getattr(p, "has_folded", None),
                "total_contributed": getattr(p, "total_contributed", None),
            }
            for p in players
        ]

        serialized_side_pots = [
            {
                "pot": pot_amount,
                "eligible_seats": [p.seat for p in eligible],
            }
            for pot_amount, eligible in side_pots
        ]

        serialized_results = [
            {
                "pot": pot_amount,
                "winners": [
                    {
                        "seat": winner.seat,
                        "stack": getattr(winner, "stack", None),
                        "hole_cards": [str(card) for card in getattr(winner, "hole_cards", [])],
                    }
                    for winner in winners
                ],
            }
            for pot_amount, winners in showdown_results
        ]

        event = ShowdownEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            hand_id=self.hand_id,
            event="showdown",
            board=board,
            players=serialized_players,
            side_pots=serialized_side_pots,
            results=serialized_results,
        )
        self._writer.append(event.as_dict())

    def close(self) -> None:
        self._writer.close()


def create_logger(mode: str, *, destination: Optional[Path], hand_id: str) -> SelfPlayLogger:
    """Factory that builds a logger for the requested mode."""

    normalized = mode.lower()
    if normalized == "stdout":
        writer = StdoutWriter()
    elif normalized == "jsonl":
        if not destination:
            raise ValueError("JSONL logging requires a destination path")
        writer = JSONLWriter(destination)
    elif normalized == "parquet":
        if not destination:
            raise ValueError("Parquet logging requires a destination path")
        writer = ParquetWriter(destination)
    else:
        raise ValueError(f"Unknown action log mode: {mode}")

    return SelfPlayLogger(writer, hand_id=hand_id)
