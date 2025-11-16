import pytest

from hand import PlayerState
from metrics.ev import EVMetricsAccumulator
from simulation.runner import SimulationStats


def test_simulation_stats_win_counts_sum_to_hands():
    stats = SimulationStats()

    stats.update_from_summary({"total_pot": 10, "winners": [0]})
    stats.update_from_summary({"total_pot": 10, "winners": [0, 1]})

    assert stats.hands_played == 2
    total_wins = sum(stats.win_counts.values())
    assert total_wins == pytest.approx(2.0)
    assert stats.win_counts[0] == pytest.approx(1.5)
    assert stats.win_counts[1] == pytest.approx(0.5)


def test_ev_metrics_chip_deltas_conserve_chips_on_split_pots():
    players = [
        PlayerState(seat=0, stack=100, total_contributed=2),
        PlayerState(seat=1, stack=100, total_contributed=3),
    ]
    result = {
        "players": players,
        "result": [
            (5, [players[0], players[1]]),
        ],
    }
    summary = {"table_index": 0, "bb": 10, "result": result}

    metrics = EVMetricsAccumulator()
    metrics.record_hand(summary)

    player_metrics = {entry["seat"]: entry for entry in metrics.as_dict()["players"]}
    assert player_metrics[0]["chip_delta"] == pytest.approx(1)
    assert player_metrics[1]["chip_delta"] == pytest.approx(-1)
    assert sum(entry["chip_delta"] for entry in player_metrics.values()) == pytest.approx(0.0)
