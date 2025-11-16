"""Seat management helpers for orchestrating button and blind rotations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from hand import PlayerState


@dataclass(frozen=True)
class SeatAssignment:
    """Represents the ordered players/agents for a single hand."""

    players: List[PlayerState]
    agent_paths: List[str]
    order: List[int]
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int


class SeatManager:
    """Manage seat order, blind posting, and stack persistence across hands."""

    def __init__(
        self,
        stacks: Sequence[int],
        agent_paths: Sequence[str],
        *,
        auto_reload: bool = True,
    ):
        if not 2 <= len(stacks) <= 9:
            raise ValueError("Texas Hold'em tables must have between 2 and 9 seats")
        if len(stacks) != len(agent_paths):
            raise ValueError("Stacks and agent specs must be the same length")

        self._initial_stacks: List[int] = list(stacks)
        self._auto_reload = auto_reload
        self._players: List[PlayerState] = [
            PlayerState(seat=i, stack=stack) for i, stack in enumerate(stacks)
        ]
        self._agent_paths: List[str] = list(agent_paths)
        if len(self._players) == 2:
            # In heads-up play the button posts the small blind.
            self._button_position = 0
        else:
            # Otherwise start with the same ordering as the legacy simulator
            # (seat 0 is the small blind on the first hand).
            self._button_position = len(self._players) - 1

    @property
    def player_states(self) -> List[PlayerState]:
        """Return the current player snapshots indexed by seat."""

        return list(self._players)

    @property
    def button_seat(self) -> int:
        return self._button_position

    def _small_blind_seat(self) -> int:
        if len(self._players) == 2:
            return self._button_position
        return (self._button_position + 1) % len(self._players)

    def _big_blind_seat(self) -> int:
        if len(self._players) == 2:
            return (self._button_position + 1) % len(self._players)
        sb_seat = self._small_blind_seat()
        return (sb_seat + 1) % len(self._players)

    def _seat_order(self) -> List[int]:
        sb_seat = self._small_blind_seat()
        return [
            (sb_seat + offset) % len(self._players) for offset in range(len(self._players))
        ]

    def next_hand(self) -> SeatAssignment:
        """Return the ordered seating/agent configuration for the next hand."""

        order = self._seat_order()
        players = [self._players[idx] for idx in order]
        agents = [self._agent_paths[idx] for idx in order]
        return SeatAssignment(
            players=players,
            agent_paths=agents,
            order=order,
            button_seat=self._button_position,
            small_blind_seat=order[0],
            big_blind_seat=order[1],
        )

    def complete_hand(self, updated_players: Sequence[PlayerState]) -> None:
        """Persist stack changes and advance the button for the next hand."""

        if len(updated_players) != len(self._players):
            raise ValueError("Updated player list length does not match table seats")

        latest = {player.seat: player for player in updated_players}
        if set(latest.keys()) != set(range(len(self._players))):
            raise ValueError("Updated players must cover every seat exactly once")

        if self._auto_reload:
            self._players = [
                PlayerState(seat=seat, stack=self._initial_stacks[seat])
                for seat in range(len(self._players))
            ]
        else:
            self._players = [latest[idx] for idx in range(len(self._players))]
        self._button_position = (self._button_position + 1) % len(self._players)
