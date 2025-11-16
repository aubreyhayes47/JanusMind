"""Utilities for distributing pot chips among winners."""
from __future__ import annotations

from typing import Dict, Sequence


def split_pot_evenly(pot_amount: int, winner_seats: Sequence[int]) -> Dict[int, int]:
    """Return the chip payout for each seat when splitting a pot evenly.

    Odd chips are assigned deterministically to the lowest-numbered seats so that
    chip accounting is consistent between the showdown logic and EV metrics.
    """

    seats = list(winner_seats)
    if not seats:
        return {}

    base_share, remainder = divmod(pot_amount, len(seats))
    payouts = {seat: base_share for seat in seats}
    if remainder:
        for seat in sorted(seats)[:remainder]:
            payouts[seat] += 1
    return payouts
