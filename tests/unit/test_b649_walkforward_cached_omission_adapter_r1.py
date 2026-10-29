"""Focused parity and cache-invariant tests for the K5 research adapter."""

from __future__ import annotations

import random
from random import Random
from typing import cast

from lottolab.research import b649_walkforward_incremental_cache_r1 as _cache
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _multiscale,
)
from lottolab.research.b649_walkforward_cached_omission_adapter_r1 import (
    LOW_OVERLAP_K5_CANDIDATE_ID,
    B649WalkForwardCachedOmissionAdapter,
)

HistoryDraw = tuple[int, int, int, int, int, int]


def _draws(count: int) -> tuple[HistoryDraw, ...]:
    generator = Random(1028)
    return tuple(
        cast(HistoryDraw, tuple(sorted(generator.sample(range(1, 50), 6))))
        for _ in range(count)
    )


def _snapshot(
    draws: tuple[HistoryDraw, ...],
) -> _cache.B649WalkForwardHistory:
    return _cache.B649WalkForwardHistory.from_draws("adapter-test-source-v1", draws)


def _assert_legal_k5(portfolio: tuple[tuple[int, ...], ...]) -> None:
    assert len(portfolio) == 5
    assert len(set(portfolio)) == 5
    for ticket in portfolio:
        assert len(ticket) == 6
        assert tuple(sorted(set(ticket))) == ticket
        assert all(1 <= number <= 49 for number in ticket)


def test_adapter_matches_original_k5_ticket_order_across_cutoffs() -> None:
    draws = _draws(757)
    history = _snapshot(draws)
    adapter = B649WalkForwardCachedOmissionAdapter(
        _cache.B649WalkForwardIncrementalCache()
    )

    for target_index in range(750, 757):
        expected = (
            _multiscale.produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
                LOW_OVERLAP_K5_CANDIDATE_ID,
                draws,
                target_index,
            )
        )
        actual = adapter.produce_low_overlap_k5(history, target_index)

        assert actual == expected
        _assert_legal_k5(actual)

    info = adapter.cache.cache_info
    assert info.misses == 7 * 3
    assert info.incremental_draw_updates == 6 * 3


def test_cached_statistics_match_original_50_300_750_semantics() -> None:
    draws = _draws(761)
    history = _snapshot(draws)
    cache = _cache.B649WalkForwardIncrementalCache()
    target_index = 760

    for window in _multiscale.OMISSION_WINDOWS:
        statistics = cache.get_window_statistics(history, target_index, window)
        prior_window = draws[target_index - window : target_index]

        assert statistics.cutoff_index == target_index
        assert statistics.window == window
        assert statistics.history_draw_count == window
        assert statistics.occurrence_counts == _multiscale.calculate_occurrences(
            prior_window
        )
        assert statistics.current_gaps == _multiscale.calculate_current_gaps(
            prior_window
        )


def test_changed_prefix_with_same_source_identity_causes_cache_miss() -> None:
    draws = _draws(751)
    history = _snapshot(draws)
    cache = _cache.B649WalkForwardIncrementalCache()
    original = cache.get_window_statistics(history, 750, 50)

    changed_draws = list(draws)
    changed_draw = changed_draws[749]
    replacement = next(number for number in range(1, 50) if number not in changed_draw)
    changed_draws[749] = cast(
        HistoryDraw,
        tuple(sorted((*changed_draw[1:], replacement))),
    )
    changed_history = _cache.B649WalkForwardHistory.from_draws(
        "adapter-test-source-v1", changed_draws
    )

    changed = cache.get_window_statistics(changed_history, 750, 50)

    assert changed != original
    assert cache.cache_info.misses == 2
    assert changed.occurrence_counts == _multiscale.calculate_occurrences(
        changed_history.draws[700:750]
    )
    assert changed.current_gaps == _multiscale.calculate_current_gaps(
        changed_history.draws[700:750]
    )


def test_adapter_exposes_repeated_cutoff_cache_hits() -> None:
    draws = _draws(751)
    history = _snapshot(draws)
    adapter = B649WalkForwardCachedOmissionAdapter(
        _cache.B649WalkForwardIncrementalCache()
    )

    first = adapter.produce_low_overlap_k5(history, 750)
    first_info = adapter.cache.cache_info
    second = adapter.produce_low_overlap_k5(history, 750)
    second_info = adapter.cache.cache_info

    assert second == first
    assert first_info.misses == 3
    assert first_info.hits == 0
    assert second_info.misses == 3
    assert second_info.hits == 3


def test_target_outcome_is_excluded_and_rng_state_is_unchanged() -> None:
    draws = _draws(751)
    alternate_draws = list(draws)
    target_draw = alternate_draws[750]
    replacement = next(number for number in range(1, 50) if number not in target_draw)
    alternate_draws[750] = cast(
        HistoryDraw,
        tuple(sorted((*target_draw[1:], replacement))),
    )
    history = _snapshot(draws)
    alternate_history = _cache.B649WalkForwardHistory.from_draws(
        "adapter-test-source-v1", alternate_draws
    )
    adapter = B649WalkForwardCachedOmissionAdapter(
        _cache.B649WalkForwardIncrementalCache()
    )
    rng_state = random.getstate()

    original = (
        _multiscale.produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
            LOW_OVERLAP_K5_CANDIDATE_ID,
            draws,
            750,
        )
    )
    assert random.getstate() == rng_state
    first = adapter.produce_low_overlap_k5(history, 750)
    assert random.getstate() == rng_state
    second = adapter.produce_low_overlap_k5(alternate_history, 750)

    assert first == original == second
    assert adapter.cache.cache_info.misses == 3
    assert adapter.cache.cache_info.hits == 3
    assert random.getstate() == rng_state
