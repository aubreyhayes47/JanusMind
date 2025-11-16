"""Structured action logging utilities for self-play simulations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

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
    seat: int
    action: str
    bet_size: int
    pot: int
    board: List[str]

    def as_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "hand_id": self.hand_id,
            "seat": self.seat,
            "action": self.action,
            "bet_size": self.bet_size,
            "pot": self.pot,
            "board": self.board,
        }


class _BaseWriter:
    def append(self, event: ActionEvent) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        return None


class StdoutWriter(_BaseWriter):
    def append(self, event: ActionEvent) -> None:
        print(json.dumps(event.as_dict(), separators=(",", ":")))


class JSONLWriter(_BaseWriter):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def append(self, event: ActionEvent) -> None:
        self._handle.write(json.dumps(event.as_dict()) + "\n")
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

    def append(self, event: ActionEvent) -> None:
        if pa is None or pq is None:  # pragma: no cover
            return
        table = pa.Table.from_pylist([event.as_dict()])
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
    ) -> None:
        event = ActionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            hand_id=self.hand_id,
            seat=seat,
            action=action,
            bet_size=bet_size,
            pot=pot,
            board=board,
        )
        self._writer.append(event)

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
