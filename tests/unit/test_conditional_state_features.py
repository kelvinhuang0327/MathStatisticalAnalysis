from __future__ import annotations

import pytest

from lottolab.research.conditional_state_features import (
    LAST_SEEN_GAP_CAP,
    ZoneObservation,
    compute_zone_observations,
)


def test_pool_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="pool_size must be positive"):
        compute_zone_observations([frozenset({1})], pool_size=0)


def test_draw_number_sets_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        compute_zone_observations([], pool_size=3)


def test_first_position_produces_no_observations() -> None:
    draws = [frozenset({1, 2})]
    observations = compute_zone_observations(draws, pool_size=3)
    assert observations == ()


def test_observation_count_excludes_only_position_zero() -> None:
    draws = [frozenset({1, 2}), frozenset({2, 3}), frozenset({1, 3}), frozenset({1, 2})]
    observations = compute_zone_observations(draws, pool_size=3)
    assert len(observations) == (len(draws) - 1) * 3


def test_hand_traced_small_example() -> None:
    draws = [
        frozenset({1, 2}),  # position 0
        frozenset({2, 3}),  # position 1
        frozenset({1, 3}),  # position 2
        frozenset({1, 2}),  # position 3
    ]
    observations = compute_zone_observations(draws, pool_size=3)
    by_key = {(o.draw_index, o.number): o for o in observations}

    expected = {
        (1, 1): ZoneObservation(1, 1, 1, 1, 0),
        (1, 2): ZoneObservation(1, 2, 1, 1, 1),
        (1, 3): ZoneObservation(1, 3, 0, LAST_SEEN_GAP_CAP, 1),
        (2, 1): ZoneObservation(2, 1, 0, 2, 1),
        (2, 2): ZoneObservation(2, 2, 1, 1, 0),
        (2, 3): ZoneObservation(2, 3, 1, 1, 1),
        (3, 1): ZoneObservation(3, 1, 1, 1, 1),
        (3, 2): ZoneObservation(3, 2, 0, 2, 1),
        (3, 3): ZoneObservation(3, 3, 1, 1, 0),
    }
    assert by_key == expected


def test_gap_is_capped_for_a_number_absent_for_a_long_stretch() -> None:
    # number 1 appears at position 0, then is absent for far more than the
    # cap before reappearing.
    draws = [frozenset({1, 2})] + [frozenset({2, 3}) for _ in range(LAST_SEEN_GAP_CAP + 20)]
    observations = compute_zone_observations(draws, pool_size=3)
    last_position_index = len(draws) - 1
    last_obs_for_1 = next(
        o for o in observations if o.draw_index == last_position_index and o.number == 1
    )
    assert last_obs_for_1.last_seen_gap == LAST_SEEN_GAP_CAP
    assert last_obs_for_1.was_in_previous_draw == 0


def test_never_seen_number_gets_capped_gap_not_an_error() -> None:
    draws = [frozenset({2, 3}), frozenset({2, 3})]
    observations = compute_zone_observations(draws, pool_size=3)
    obs_for_1 = next(o for o in observations if o.number == 1)
    assert obs_for_1.last_seen_gap == LAST_SEEN_GAP_CAP
    assert obs_for_1.was_in_previous_draw == 0


def test_number_drawn_immediately_before_has_gap_one() -> None:
    draws = [frozenset({5}), frozenset({1, 2})]
    observations = compute_zone_observations(draws, pool_size=5)
    obs_for_5 = next(o for o in observations if o.number == 5)
    assert obs_for_5.was_in_previous_draw == 1
    assert obs_for_5.last_seen_gap == 1
