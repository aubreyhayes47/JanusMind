"""Utilities to transform self-play logs into model-ready tensors."""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from deck import RANKS, SUITS


RANK_TO_INDEX: Dict[str, int] = {rank: idx for idx, rank in enumerate(RANKS)}
SUIT_TO_INDEX: Dict[str, int] = {suit: idx for idx, suit in enumerate(SUITS)}
NUM_CARDS = len(RANKS) * len(SUITS)
ACTION_TYPES: Tuple[str, ...] = ("fold", "check", "call", "bet", "raise")


@dataclass
class EncodedDataset:
    """Container for encoded training samples."""

    hole_cards: np.ndarray
    board_cards: np.ndarray
    stacks: np.ndarray
    pots: np.ndarray
    to_calls: np.ndarray
    action_types: np.ndarray
    bet_targets: np.ndarray

    def split(self, *, val_fraction: float, seed: int) -> Tuple["EncodedDataset", "EncodedDataset"]:
        if not 0.0 < val_fraction < 1.0:
            raise ValueError("val_fraction must be between 0 and 1")
        total = self.hole_cards.shape[0]
        indices = list(range(total))
        random.Random(seed).shuffle(indices)
        cutoff = int(total * (1 - val_fraction))
        train_idx, val_idx = indices[:cutoff], indices[cutoff:]
        if not train_idx or not val_idx:
            raise ValueError("Dataset too small for requested split")
        return self._subset(train_idx), self._subset(val_idx)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            hole_cards=self.hole_cards,
            board_cards=self.board_cards,
            stacks=self.stacks,
            pots=self.pots,
            to_calls=self.to_calls,
            action_types=self.action_types,
            bet_targets=self.bet_targets,
        )

    def _subset(self, indices: Sequence[int]) -> "EncodedDataset":
        return EncodedDataset(
            hole_cards=self.hole_cards[indices],
            board_cards=self.board_cards[indices],
            stacks=self.stacks[indices],
            pots=self.pots[indices],
            to_calls=self.to_calls[indices],
            action_types=self.action_types[indices],
            bet_targets=self.bet_targets[indices],
        )


def encode_card(card: str) -> int:
    if len(card) != 2:
        raise ValueError(f"Unexpected card format: {card}")
    rank, suit = card[0], card[1]
    try:
        rank_idx = RANK_TO_INDEX[rank]
        suit_idx = SUIT_TO_INDEX[suit]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unknown card component in {card}") from exc
    return suit_idx * len(RANKS) + rank_idx


def encode_cards(cards: Iterable[str]) -> np.ndarray:
    vector = np.zeros(NUM_CARDS, dtype=np.float32)
    for card in cards:
        vector[encode_card(card)] = 1.0
    return vector


def one_hot_action(action: str) -> np.ndarray:
    if action not in ACTION_TYPES:
        raise ValueError(f"Unknown action type: {action}")
    vector = np.zeros(len(ACTION_TYPES), dtype=np.float32)
    vector[ACTION_TYPES.index(action)] = 1.0
    return vector


def normalize_amount(amount: Any, *, big_blind: float) -> float:
    if amount is None:
        return 0.0
    try:
        return float(amount) / big_blind
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return 0.0


def load_events(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".parquet":
        return _load_parquet(path)
    raise ValueError(f"Unsupported log format for {path}")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            events.append(json.loads(line))
    return events


def _load_parquet(path: Path) -> List[Dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pyarrow is required to read Parquet logs") from exc

    table = pq.read_table(path)
    return table.to_pylist()


def encode_events(events: Iterable[Dict[str, Any]], *, big_blind: float) -> EncodedDataset:
    hole_vectors: List[np.ndarray] = []
    board_vectors: List[np.ndarray] = []
    stacks: List[float] = []
    pots: List[float] = []
    to_calls: List[float] = []
    action_vectors: List[np.ndarray] = []
    bet_targets: List[float] = []

    for event in events:
        if event.get("event") != "action":
            continue
        action = str(event.get("action", "")).lower()
        hole = encode_cards(event.get("hole_cards", []) or [])
        board = encode_cards(event.get("board", []) or [])
        stacks.append(normalize_amount(event.get("stack"), big_blind=big_blind))
        pots.append(normalize_amount(event.get("pot"), big_blind=big_blind))
        to_calls.append(normalize_amount(event.get("to_call"), big_blind=big_blind))
        action_vectors.append(one_hot_action(action))

        bet_size = normalize_amount(event.get("bet_size"), big_blind=big_blind)
        if action not in {"bet", "raise"}:
            bet_size = 0.0
        bet_targets.append(bet_size)
        hole_vectors.append(hole)
        board_vectors.append(board)

    if not hole_vectors:
        raise ValueError("No action events found in provided logs")

    return EncodedDataset(
        hole_cards=np.vstack(hole_vectors),
        board_cards=np.vstack(board_vectors),
        stacks=np.asarray(stacks, dtype=np.float32)[:, None],
        pots=np.asarray(pots, dtype=np.float32)[:, None],
        to_calls=np.asarray(to_calls, dtype=np.float32)[:, None],
        action_types=np.vstack(action_vectors),
        bet_targets=np.asarray(bet_targets, dtype=np.float32)[:, None],
    )


def persist_metadata(path: Path, *, big_blind: float, val_fraction: float, total_rows: int) -> None:
    metadata = {
        "big_blind": big_blind,
        "val_fraction": val_fraction,
        "num_samples": total_rows,
        "action_types": list(ACTION_TYPES),
        "card_encoding": {
            "ranks": RANKS,
            "suits": SUITS,
            "vector_length": NUM_CARDS,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encode self-play logs for training")
    parser.add_argument("log_path", type=Path, help="Path to JSONL or Parquet action log")
    parser.add_argument("output_dir", type=Path, help="Directory to store encoded datasets")
    parser.add_argument("--big-blind", type=float, default=50.0, help="Big blind size used for normalization")
    parser.add_argument("--val-fraction", type=float, default=0.1, help="Fraction of rows for validation")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for splitting")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = load_events(args.log_path)
    encoded = encode_events(events, big_blind=args.big_blind)
    train, val = encoded.split(val_fraction=args.val_fraction, seed=args.seed)

    train_path = args.output_dir / "train.npz"
    val_path = args.output_dir / "val.npz"
    train.save(train_path)
    val.save(val_path)
    persist_metadata(
        args.output_dir / "metadata.json",
        big_blind=args.big_blind,
        val_fraction=args.val_fraction,
        total_rows=encoded.hole_cards.shape[0],
    )
    print(f"Wrote {train.hole_cards.shape[0]} training samples to {train_path}")
    print(f"Wrote {val.hole_cards.shape[0]} validation samples to {val_path}")


if __name__ == "__main__":
    main()
