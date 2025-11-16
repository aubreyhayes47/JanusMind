"""Tests for the seat manager rotation and persistence logic."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from hand import PlayerState
from simulation.seating import SeatManager


def test_seat_manager_rotates_and_preserves_stacks() -> None:
    stacks = [100, 120, 140, 160]
    manager = SeatManager(stacks, ["a", "b", "c", "d"], auto_reload=False)
    initial = {player.seat: player.stack for player in manager.player_states}
    deltas = {seat: 0 for seat in range(len(stacks))}
    orders = []

    for hand_number in range(2000):
        assignment = manager.next_hand()
        orders.append([player.seat for player in assignment.players])
        updated_players = []
        for offset, player in enumerate(assignment.players):
            deltas[player.seat] += offset
            updated_players.append(
                PlayerState(
                    seat=player.seat,
                    stack=player.stack + offset,
                )
            )
        manager.complete_hand(updated_players)

    assert orders[0] == [0, 1, 2, 3]
    assert orders[1] == [1, 2, 3, 0]
    assert orders[2] == [2, 3, 0, 1]
    assert orders[3] == [3, 0, 1, 2]

    for seat, player in enumerate(manager.player_states):
        assert player.stack == initial[seat] + deltas[seat]


def test_headsup_button_follows_small_blind() -> None:
    manager = SeatManager([50, 60], ["x", "y"])
    sb_sequence = []

    for _ in range(10):
        assignment = manager.next_hand()
        sb_sequence.append(assignment.players[0].seat)
        manager.complete_hand(
            [PlayerState(seat=p.seat, stack=p.stack) for p in assignment.players]
        )

    assert sb_sequence == [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]


def test_auto_reload_restores_initial_stacks() -> None:
    stacks = [75, 150, 225]
    manager = SeatManager(stacks, ["a", "b", "c"], auto_reload=True)

    assignment = manager.next_hand()
    depleted = [
        PlayerState(seat=player.seat, stack=1) for player in assignment.players
    ]
    manager.complete_hand(depleted)

    reloaded = manager.player_states
    assert [player.stack for player in reloaded] == stacks
