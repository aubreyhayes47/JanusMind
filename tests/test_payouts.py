from payouts import split_pot_evenly


def test_split_pot_evenly_handles_exact_division():
    result = split_pot_evenly(100, [0, 1])
    assert result == {0: 50, 1: 50}


def test_split_pot_evenly_assigns_odd_chip_to_lowest_seat():
    result = split_pot_evenly(5, [2, 0])
    # seat 0 receives the odd chip because it is the lowest seat number.
    assert result == {2: 2, 0: 3}
