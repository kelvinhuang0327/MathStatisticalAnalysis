from __future__ import annotations

from datetime import date, timedelta
from random import Random

import pytest

from lottolab.research import (
    biglotto_multi_ticket_constructors_r1 as _constructors,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _baseline,
)
from lottolab.research.b649_walkforward_incremental_cache_r1 import (
    B649WalkForwardCacheError,
    B649WalkForwardHistory,
    B649WalkForwardIncrementalCache,
    calculate_window_rankings_cached,
    produce_source_ticket_universe_cached,
)
from lottolab.research.base_method_evaluation import (
    BIG_LOTTO_MATCH_CONTRACT,
    ExposureKind,
    MethodDrawObservation,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    evaluate_method,
)


def _draws(count: int, *, seed: int = 1028) -> tuple[tuple[int, ...], ...]:
    rng = Random(seed)
    return tuple(
        tuple(sorted(rng.sample(range(1, 50), 6))) for _ in range(count)
    )


def _portfolio(
    history: tuple[tuple[int, ...], ...], target_index: int
) -> tuple[tuple[int, ...], ...]:
    source_tickets = _baseline.produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS["B649_CANDIDATE_SET_LOW_OVERLAP_V1"]
    return constructor(source_tickets, 5)


def _observation(
    target_index: int,
    winning_numbers: tuple[int, ...],
    portfolio: tuple[tuple[int, ...], ...],
) -> MethodDrawObservation:
    draw_date = date(2020, 1, 1) + timedelta(days=target_index)
    winning_set = set(winning_numbers)
    return MethodDrawObservation(
        draw_id=str(target_index),
        draw_date=draw_date.isoformat(),
        native_ticket_count=len(portfolio),
        distinct_ticket_count=len(set(portfolio)),
        main_hit_counts=tuple(
            len(set(ticket) & winning_set) for ticket in portfolio
        ),
    )


def _evaluation_identity(target_indices: range) -> MethodIdentity:
    return MethodIdentity(
        method_id="fixed_multiscale_low_overlap_k5",
        method_version="1",
        method_family="GAP_OMISSION",
        output_shape=OutputShape.PORTFOLIO,
        exposure=MethodExposure(ExposureKind.FIXED, 5, 5),
        target_coverage=MethodTargetCoverage(
            eligible_draw_count=len(target_indices),
            first_draw_id=str(target_indices.start),
            last_draw_id=str(target_indices.stop - 1),
        ),
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )


def test_cached_rankings_tickets_and_evaluation_match_baseline() -> None:
    draws = _draws(780)
    history = B649WalkForwardHistory.from_draws("synthetic-dataset:v1", draws)
    cache = B649WalkForwardIncrementalCache()
    target_indices = range(750, 780)
    baseline_observations: list[MethodDrawObservation] = []
    cached_observations: list[MethodDrawObservation] = []

    for target_index in target_indices:
        expected_rankings = _baseline.calculate_window_rankings(draws, target_index)
        actual_rankings = calculate_window_rankings_cached(
            history, target_index, cache
        )
        assert actual_rankings == expected_rankings

        expected_portfolio = _portfolio(draws, target_index)
        actual_tickets = produce_source_ticket_universe_cached(
            history, target_index, cache
        )
        assert actual_tickets == _baseline.produce_source_ticket_universe(
            draws, target_index
        )
        constructor = _constructors.CONSTRUCTORS[
            "B649_CANDIDATE_SET_LOW_OVERLAP_V1"
        ]
        actual_portfolio = constructor(actual_tickets, 5)
        assert actual_portfolio == expected_portfolio

        baseline_observations.append(
            _observation(target_index, draws[target_index], expected_portfolio)
        )
        cached_observations.append(
            _observation(target_index, draws[target_index], actual_portfolio)
        )

    # A second candidate branch can reuse the same source statistics while
    # retaining its own unchanged portfolio constructor.
    second_constructor = _constructors.CONSTRUCTORS[
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1"
    ]
    for target_index in target_indices:
        expected_source = _baseline.produce_source_ticket_universe(
            draws, target_index
        )
        cached_source = produce_source_ticket_universe_cached(
            history, target_index, cache
        )
        assert cached_source == expected_source
        assert second_constructor(cached_source, 5) == second_constructor(
            expected_source, 5
        )

    identity = _evaluation_identity(target_indices)
    assert evaluate_method(
        BIG_LOTTO_MATCH_CONTRACT, identity, tuple(cached_observations)
    ) == evaluate_method(
        BIG_LOTTO_MATCH_CONTRACT, identity, tuple(baseline_observations)
    )
    assert cache.cache_info.hits == 6 * len(target_indices)
    assert cache.cache_info.misses == 3 * len(target_indices)


def test_cache_key_tracks_source_window_cutoff_and_prefix_content() -> None:
    draws = _draws(780)
    cache = B649WalkForwardIncrementalCache(max_entries=8)
    first = B649WalkForwardHistory.from_draws("dataset-a:v1", draws)
    first_stat = cache.get_window_statistics(first, 750, 50)
    assert cache.get_window_statistics(first, 750, 50) is first_stat
    assert cache.cache_info.hits == 1

    cache.get_window_statistics(first, 751, 50)
    cache.get_window_statistics(first, 751, 300)
    different_source = B649WalkForwardHistory.from_draws("dataset-b:v1", draws)
    cache.get_window_statistics(different_source, 751, 50)
    changed_draws = (*draws[:749], (1, 2, 3, 4, 5, 6), *draws[750:])
    changed_prefix = B649WalkForwardHistory.from_draws("dataset-a:v1", changed_draws)
    changed_stat = cache.get_window_statistics(changed_prefix, 750, 50)

    assert changed_stat != first_stat
    assert cache.cache_info.misses == 5
    assert cache.cache_info.entries <= 8


def test_appended_draw_advances_state_without_reusing_old_cutoff_result() -> None:
    draws = ((1, 2, 3, 4, 5, 6), *_draws(749))
    history = B649WalkForwardHistory.from_draws("dataset:v1", draws)
    cache = B649WalkForwardIncrementalCache()
    old_stats = cache.get_window_statistics(history, 750, 750)

    appended = (*draws, (7, 8, 9, 10, 11, 12))
    updated_history = B649WalkForwardHistory.from_draws("dataset:v1", appended)
    updated_stats = cache.get_window_statistics(updated_history, 751, 750)
    uncached_updated = cache.get_window_statistics(
        updated_history, 751, 750, use_cache=False
    )

    assert updated_stats == uncached_updated
    assert updated_stats.occurrence_counts[1] == old_stats.occurrence_counts[1] - 1
    assert updated_stats.cutoff_index == 751
    assert cache.cache_info.misses == 2
    assert cache.cache_info.incremental_draw_updates == 1


def test_result_lru_stays_within_its_configured_bound() -> None:
    history = B649WalkForwardHistory.from_draws("bounded:v1", _draws(780))
    cache = B649WalkForwardIncrementalCache(max_entries=2)

    expected = cache.get_window_statistics(history, 750, 50)
    cache.get_window_statistics(history, 751, 50)
    cache.get_window_statistics(history, 752, 50)
    assert cache.cache_info.entries == 2

    assert cache.get_window_statistics(history, 750, 50) == expected
    assert cache.cache_info.entries == 2
    assert cache.cache_info.misses == 4


def test_future_draw_changes_do_not_affect_an_earlier_cutoff() -> None:
    draws = _draws(752)
    changed_future = (*draws[:750], (1, 2, 3, 4, 5, 6), *draws[751:])
    first = B649WalkForwardHistory.from_draws("dataset:v1", draws)
    second = B649WalkForwardHistory.from_draws("dataset:v1", changed_future)
    cache = B649WalkForwardIncrementalCache()

    expected = cache.get_window_statistics(first, 750, 300)
    actual = cache.get_window_statistics(second, 750, 300)

    assert actual == expected
    assert cache.cache_info.hits == 1
    assert cache.cache_info.misses == 1


def test_uncached_or_incompatible_history_uses_the_original_safe_path() -> None:
    draws = _draws(780)
    history = B649WalkForwardHistory.from_draws("dataset:v1", draws)
    cache = B649WalkForwardIncrementalCache()

    expected = _baseline.calculate_window_rankings(draws, 750)
    bypassed = calculate_window_rankings_cached(
        history, 750, cache, use_cache=False
    )
    raw_sequence = [list(draw) for draw in draws]
    incompatible = calculate_window_rankings_cached(raw_sequence, 750, cache)

    assert bypassed == expected
    assert incompatible == expected
    assert cache.cache_info.hits == 0
    assert cache.cache_info.misses == 0

    with pytest.raises(_baseline.InsufficientHistoryError) as baseline_error:
        _baseline.calculate_window_rankings(draws[:749], 749)
    with pytest.raises(type(baseline_error.value)) as candidate_error:
        calculate_window_rankings_cached(
            B649WalkForwardHistory.from_draws("short:v1", draws[:749]),
            749,
            cache,
        )
    assert str(candidate_error.value) == str(baseline_error.value)


def test_cache_does_not_change_rng_events() -> None:
    draws = _draws(780)
    history = B649WalkForwardHistory.from_draws("dataset:v1", draws)

    baseline_rng = Random(219)
    baseline_rng_events: list[int] = []
    for target_index in (750, 751, 752):
        _baseline.calculate_window_rankings(draws, target_index)
        baseline_rng_events.append(baseline_rng.randrange(1, 10_000))

    cached_rng = Random(219)
    cached_rng_events: list[int] = []
    cache = B649WalkForwardIncrementalCache()
    for target_index in (750, 751, 752):
        calculate_window_rankings_cached(history, target_index, cache)
        cached_rng_events.append(cached_rng.randrange(1, 10_000))

    assert cached_rng_events == baseline_rng_events
    assert cached_rng.getstate() == baseline_rng.getstate()


def test_history_snapshot_rejects_invalid_main_draws() -> None:
    with pytest.raises(B649WalkForwardCacheError, match="six unique numbers"):
        B649WalkForwardHistory.from_draws("invalid:v1", ((1, 2, 3, 4, 5, 5),))
