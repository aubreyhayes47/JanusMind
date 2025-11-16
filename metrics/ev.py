"""EV and bb/100 aggregation helpers for poker simulations."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, Tuple


@dataclass
class _PlayerSnapshot:
    table_index: int
    seat: int
    total_chip_delta: float = 0.0
    total_bb_delta: float = 0.0
    hands_played: int = 0
    history: Deque[Tuple[int, int]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = deque()

    def record(self, chip_delta: int, big_blind: int) -> None:
        self.hands_played += 1
        self.total_chip_delta += chip_delta
        if big_blind:
            self.total_bb_delta += chip_delta / big_blind
        self.history.append((chip_delta, big_blind))

    def ev_per_hand(self) -> float:
        if not self.hands_played:
            return 0.0
        return self.total_chip_delta / self.hands_played

    def bb_per_100(self) -> float:
        if not self.hands_played:
            return 0.0
        return 100.0 * self.total_bb_delta / self.hands_played

    def rolling_ev_per_hand(self) -> float:
        if not self.history:
            return 0.0
        total = sum(delta for delta, _ in self.history)
        return total / len(self.history)

    def rolling_bb_per_100(self) -> float:
        if not self.history:
            return 0.0
        total_bb = 0.0
        valid_hands = 0
        for delta, bb in self.history:
            if bb:
                total_bb += delta / bb
                valid_hands += 1
        if not valid_hands:
            return 0.0
        return 100.0 * total_bb / valid_hands

    def as_dict(self) -> Dict:
        return {
            "table_index": self.table_index,
            "seat": self.seat,
            "hands": self.hands_played,
            "chip_delta": self.total_chip_delta,
            "ev_per_hand": self.ev_per_hand(),
            "bb_per_100": self.bb_per_100(),
            "rolling_window": self.history.maxlen or len(self.history),
            "rolling_ev_per_hand": self.rolling_ev_per_hand(),
            "rolling_bb_per_100": self.rolling_bb_per_100(),
        }


class EVMetricsAccumulator:
    """Track per-seat EV and bb/100 statistics from hand summaries."""

    def __init__(self, *, rolling_window: int = 200):
        self.rolling_window = rolling_window
        self._players: Dict[Tuple[int, int], _PlayerSnapshot] = {}
        self.total_events: int = 0

    def _player(self, table_index: int, seat: int) -> _PlayerSnapshot:
        key = (table_index, seat)
        if key not in self._players:
            self._players[key] = _PlayerSnapshot(
                table_index=table_index,
                seat=seat,
                history=deque(maxlen=self.rolling_window),
            )
        return self._players[key]

    def record_hand(self, summary: Dict) -> None:
        result = summary.get("result") or {}
        players: Iterable = result.get("players", [])
        if not players:
            return
        chip_deltas = self._chip_deltas(result)
        bb = summary.get("bb") or 0
        table_index = summary.get("table_index", 0)
        for seat, delta in chip_deltas.items():
            snapshot = self._player(table_index, seat)
            snapshot.record(delta, bb if bb else 1)
        self.total_events += 1

    def _chip_deltas(self, result: Dict) -> Dict[int, int]:
        contributions: Dict[int, int] = {}
        for player in result.get("players", []):
            contributions[player.seat] = getattr(player, "total_contributed", 0)
        winnings: Dict[int, int] = defaultdict(int)
        for pot_amount, winners in result.get("result", []):
            if not winners:
                continue
            share = pot_amount // len(winners)
            for winner in winners:
                winnings[winner.seat] += share
        return {seat: winnings.get(seat, 0) - contrib for seat, contrib in contributions.items()}

    def as_dict(self) -> Dict:
        players = [snapshot.as_dict() for snapshot in sorted(self._players.values(), key=lambda s: (s.table_index, s.seat))]
        return {
            "hands_observed": self.total_events,
            "players": players,
        }
