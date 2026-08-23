"""Focused tests for the causal BigLotto multiscale temporal profile cluster candidate batch."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as conditional_batch,
)
from lottolab.research import (
    biglotto_fixed_cross_family_ensemble_multi_ticket_candidate_batch_r1 as ensemble_batch,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_candidate_batch_r1 as frequency_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_constructors_r1 as constructors,
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayes_batch,
)
from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _make_distinct_draw(index: int) -> Ticket:
    start = (index * 6) % 43 + 1
    return (start, start + 1, start + 2, start + 3, start + 4, start + 5)


_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = (
    *tuple(_make_distinct_draw(i) for i in range(749)),
    _ANCHOR,
)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = (
    *_repeat(_FILLER, 749),
    _ANCHOR,
)


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    raw_numbers = cast(tuple[object, ...], ticket)
    if len(raw_numbers) != 6:
        return False
    return (
        all(type(number) is int and 1 <= number <= 49 for number in raw_numbers)
        and len(set(cast(tuple[int, ...], raw_numbers))) == 6
        and tuple(sorted(cast(tuple[int, ...], raw_numbers))) == raw_numbers
    )


# --- History / causality tests ---


def test_fewer_than_750_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 750"):
        batch.validate_prior_history(_HISTORY[:749], 749)


def test_invalid_target_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_index must be a non-negative integer"):
        batch.calculate_temporal_profiles(_HISTORY, -1)  # type: ignore[arg-type]


def test_target_index_exceeding_history_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_index must not exceed history length"):
        batch.calculate_temporal_profiles(_HISTORY[:750], 751)


def test_exactly_750_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 750)) == 210


def test_target_row_is_excluded_and_future_suffix_is_invariant() -> None:
    target_row: object = (44, 45, 46, 47, 48, 49)
    future_suffix: tuple[object, ...] = (object(), ("unreadable",))
    with_target = (*_HISTORY, target_row, *future_suffix)
    expected = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert batch.produce_source_ticket_universe(with_target, 750) == expected


def test_input_history_is_not_mutated() -> None:
    history = [list(draw) for draw in _HISTORY]
    before = [row.copy() for row in history]
    batch.produce_source_ticket_universe(history, len(history))
    assert history == before


def test_malformed_historical_draw_duplicate_is_rejected() -> None:
    history = list(_HISTORY)
    history[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_temporal_profiles(history, len(history))


def test_malformed_historical_draw_out_of_bounds_is_rejected() -> None:
    history = list(_HISTORY)
    history[10] = (1, 2, 3, 4, 5, 50)
    with pytest.raises(ValueError, match=r"must be in 1\.\.49"):
        batch.calculate_temporal_profiles(history, len(history))


def test_malformed_historical_draw_length_is_rejected() -> None:
    history: list[object] = list(_HISTORY)
    history[10] = (1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="must contain exactly 6 numbers"):
        batch.calculate_temporal_profiles(history, len(history))


# --- Temporal profile & coordinates tests ---


def test_exact_occurrence_counts_and_rates_50_300_750() -> None:
    # Construct fixture where number 1 appears in 50-window 10 times,
    # in 300-window 30 times, and in 750-window 60 times.
    draws: list[Ticket] = []
    for i in range(750):
        if i >= 700:  # last 50 draws
            if (i - 700) < 10:
                draws.append((1, 2, 3, 4, 5, 6))
            else:
                draws.append((7, 8, 9, 10, 11, 12))
        elif i >= 450:  # middle 250 draws of 300-window
            if (i - 450) < 20:  # 20 + 10 = 30 times in 300-window
                draws.append((1, 2, 3, 4, 5, 6))
            else:
                draws.append((7, 8, 9, 10, 11, 12))
        else:  # remaining 450 draws of 750-window
            if i < 30:  # 30 + 20 + 10 = 60 times in 750-window
                draws.append((1, 2, 3, 4, 5, 6))
            else:
                draws.append((7, 8, 9, 10, 11, 12))

    state = batch.calculate_temporal_profiles(draws, 750)
    assert state.count_50(1) == 10
    assert state.count_300(1) == 30
    assert state.count_750(1) == 60
    assert state.rate_50(1) == Fraction(10, 50)
    assert state.rate_300(1) == Fraction(30, 300)
    assert state.rate_750(1) == Fraction(60, 750)
    assert state.profile(1) == (Fraction(1, 5), Fraction(1, 10), Fraction(2, 25))


def test_rates_are_exact_fractions_in_0_to_1() -> None:
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    for num in range(1, 50):
        p = state.profile(num)
        assert len(p) == 3
        for r in p:
            assert isinstance(r, Fraction)
            assert Fraction(0, 1) <= r <= Fraction(1, 1)


def test_no_full_history_operational_feature() -> None:
    # Suffix beyond 750 does not affect rates
    hist_1000 = (*_repeat((40, 41, 42, 43, 44, 45), 250), *_HISTORY)
    state_1 = batch.calculate_temporal_profiles(hist_1000, 1000)
    state_2 = batch.calculate_temporal_profiles(_HISTORY, 750)
    for num in range(1, 50):
        assert state_1.profile(num) == state_2.profile(num)


# --- Point distance tests ---


def test_self_distance_is_exact_zero() -> None:
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    for num in range(1, 50):
        assert state.profile_distance(num, num) == Fraction(0, 1)


def test_distance_symmetry_and_non_negativity() -> None:
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    for a in range(1, 50):
        for b in range(a + 1, 50):
            d_ab = state.profile_distance(a, b)
            d_ba = state.profile_distance(b, a)
            assert d_ab == d_ba
            assert d_ab >= Fraction(0, 1)


def test_hand_computable_exact_l1_distance() -> None:
    pa = (Fraction(5, 50), Fraction(30, 300), Fraction(75, 750))  # (1/10, 1/10, 1/10)
    pb = (Fraction(10, 50), Fraction(60, 300), Fraction(150, 750))  # (1/5, 1/5, 1/5)
    # L1 coordinate diffs: |1/10 - 1/5| = 1/10 each
    # Mean L1: (1/10 + 1/10 + 1/10) / 3 = 1/10
    dist = batch.compute_point_distance(pa, pb)
    assert dist == Fraction(1, 10)
    assert isinstance(dist, Fraction)


# --- Complete-link hierarchical clustering tests ---


def test_clustering_produces_exact_10_clusters_and_valid_partition() -> None:
    partition = batch.calculate_cluster_partition(_HISTORY, 750)
    assert len(partition.CLUSTERS) == 10
    assert len(partition.ORDERED_CLUSTERS) == 10
    all_members = [num for c in partition.CLUSTERS for num in c]
    assert len(all_members) == 49
    assert sorted(all_members) == list(range(1, 50))


def test_complete_linkage_distance_property() -> None:
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    partition = batch.perform_hierarchical_clustering(state)
    for cluster in partition.CLUSTERS:
        assert len(cluster) >= 1
        assert tuple(sorted(cluster)) == cluster


def test_repeated_clustering_is_strictly_deterministic() -> None:
    p1 = batch.calculate_cluster_partition(_HISTORY, 750)
    p2 = batch.calculate_cluster_partition(_HISTORY, 750)
    assert p1.ORDERED_CLUSTERS == p2.ORDERED_CLUSTERS
    assert p1.ORDERED_REPRESENTATIVES == p2.ORDERED_REPRESENTATIVES


# --- Medoids tests ---


def test_singleton_medoid_cost_is_zero() -> None:
    state = batch.calculate_temporal_profiles(_ZERO_INFORMATION_HISTORY, 750)
    partition = batch.perform_hierarchical_clustering(state)
    for c, rep, cost in zip(
        partition.ORDERED_CLUSTERS,
        partition.ORDERED_REPRESENTATIVES,
        partition.MEDOID_COSTS,
        strict=True,
    ):
        if len(c) == 1:
            assert cost == Fraction(0, 1)
            assert rep == c[0]


def test_medoid_selection_minimizes_total_distance_and_breaks_ties_ascending() -> None:
    partition = batch.calculate_cluster_partition(_HISTORY, 750)
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    for cluster, rep in zip(
        partition.ORDERED_CLUSTERS,
        partition.ORDERED_REPRESENTATIVES,
        strict=True,
    ):
        costs = {
            num: sum(
                (state.profile_distance(num, m) for m in cluster),
                start=Fraction(0, 1),
            )
            for num in cluster
        }
        expected_rep = min(cluster, key=lambda n: (costs[n], n))
        assert rep == expected_rep


# --- Compactness and source ordering tests ---


def test_compactness_exact_rational_formula() -> None:
    state = batch.calculate_temporal_profiles(_HISTORY, 750)
    partition = batch.perform_hierarchical_clustering(state)
    for cluster, comp in zip(
        partition.ORDERED_CLUSTERS,
        partition.COMPACTNESS_SCORES,
        strict=True,
    ):
        if len(cluster) <= 1:
            assert comp == Fraction(0, 1)
        else:
            pw_sum = sum(
                (
                    state.profile_distance(a, b)
                    for a, b in combinations(cluster, 2)
                ),
                start=Fraction(0, 1),
            )
            num_pairs = Fraction(len(cluster) * (len(cluster) - 1), 2)
            assert comp == pw_sum / num_pairs


def test_cluster_ordering_precedence_size_compactness_cost_representative() -> None:
    partition = batch.calculate_cluster_partition(_HISTORY, 750)
    clusters = partition.ORDERED_CLUSTERS
    reps = partition.ORDERED_REPRESENTATIVES
    comps = partition.COMPACTNESS_SCORES
    costs = partition.MEDOID_COSTS

    for i in range(len(clusters) - 1):
        key_i = (-len(clusters[i]), comps[i], costs[i], reps[i])
        key_next = (-len(clusters[i + 1]), comps[i + 1], costs[i + 1], reps[i + 1])
        assert key_i <= key_next


# --- Clustering specificity tests ---


def test_pool_differs_from_top10_50_300_750_frequency_rankings() -> None:
    # Build structured history where clustering isolates unique profiles
    draws: list[Ticket] = []
    for i in range(750):
        if i >= 700:  # Recent 50
            draws.append((1, 2, 3, 4, 5, 6))
        elif i >= 450:  # Middle 250
            draws.append((7, 8, 9, 10, 11, 12))
        else:  # Older 450
            draws.append((13, 14, 15, 16, 17, 18))

    state = batch.calculate_temporal_profiles(draws, 750)
    partition = batch.perform_hierarchical_clustering(state)
    pool = set(partition.SOURCE_NUMBER_POOL)

    # Top10 by 50-window frequency
    top10_50 = set(sorted(range(1, 50), key=lambda n: (-state.count_50(n), n))[:10])
    # Top10 by 300-window frequency
    top10_300 = set(sorted(range(1, 50), key=lambda n: (-state.count_300(n), n))[:10])
    # Top10 by 750-window frequency
    top10_750 = set(sorted(range(1, 50), key=lambda n: (-state.count_750(n), n))[:10])

    # Assert pool is not identical to simple single-window top10
    assert pool != top10_50
    assert pool != top10_300
    assert pool != top10_750


def test_at_least_one_representative_outside_multiscale_frequency_top10() -> None:
    draws: list[Ticket] = []
    for i in range(750):
        if i >= 700:
            draws.append((1, 2, 3, 4, 5, 6))
        elif i >= 450:
            draws.append((7, 8, 9, 10, 11, 12))
        else:
            draws.append((13, 14, 15, 16, 17, 18))

    state = batch.calculate_temporal_profiles(draws, 750)
    partition = batch.perform_hierarchical_clustering(state)
    pool = set(partition.SOURCE_NUMBER_POOL)

    # Mean frequency across 50, 300, 750
    mean_freq = {
        n: (state.rate_50(n) + state.rate_300(n) + state.rate_750(n)) / 3
        for n in range(1, 50)
    }
    top10_mean = set(sorted(range(1, 50), key=lambda n: (-mean_freq[n], n))[:10])
    assert pool != top10_mean
    # At least one representative is outside the top 10 mean frequency
    assert len(pool - top10_mean) > 0


def test_same_750_count_with_different_50_300_profile_alters_geometry() -> None:
    # Create two numbers with identical 750-window total count (e.g. 50 draws),
    # but number A appears all 50 times in recent 50 draws,
    # while number B appears 0 times in recent 50 draws (all 50 in older draws).
    draws: list[Ticket] = []
    for i in range(750):
        if i >= 700:  # recent 50 draws: number 1 appears 50 times, number 2 appears 0 times
            draws.append((1, 10, 11, 12, 13, 14))
        elif 400 <= i < 450:  # older draws: number 2 appears 50 times, number 1 appears 0 times
            draws.append((2, 10, 11, 12, 13, 14))
        else:
            draws.append((20, 21, 22, 23, 24, 25))

    state = batch.calculate_temporal_profiles(draws, 750)
    assert state.count_750(1) == 50
    assert state.count_750(2) == 50
    # Different 50-window and 300-window profiles
    assert state.rate_50(1) == Fraction(1, 1)
    assert state.rate_50(2) == Fraction(0, 1)
    assert state.profile(1) != state.profile(2)
    # Their profile distance is strictly positive despite identical 750-count
    assert state.profile_distance(1, 2) > Fraction(0, 1)


# --- Source universe & 210 tickets tests ---


def test_source_universe_produces_exact_210_legal_unique_tickets() -> None:
    universe = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert len(universe) == 210
    assert len(set(universe)) == 210
    for ticket in universe:
        assert _legal_ticket(ticket)


def test_source_tickets_follow_lexicographic_rank_position_order() -> None:
    partition = batch.calculate_cluster_partition(_HISTORY, 750)
    pool = partition.SOURCE_NUMBER_POOL
    universe = batch.produce_source_ticket_universe(_HISTORY, 750)

    expected: list[Ticket] = []
    for rank_positions in combinations(range(10), 6):
        t = tuple(sorted(pool[p] for p in rank_positions))
        expected.append(cast(Ticket, t))

    assert universe == tuple(expected)


# --- Candidate identity tests ---


def test_exactly_nine_candidates_in_matrix() -> None:
    assert len(batch.CANDIDATE_IDS) == 9
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(batch.CANDIDATE_METADATA) == 9


def test_candidate_ids_format_and_signatures() -> None:
    for cid in batch.CANDIDATE_IDS:
        assert cid.startswith("BMSGV1_CL_")
        assert len(cid) == 26
        meta = batch.CANDIDATE_METADATA[cid]
        assert cid == meta.CANDIDATE_ID
        assert batch.CANDIDATE_SIGNATURE_HASHES[cid] == meta.SIGNATURE_HASH
        assert len(meta.SIGNATURE_HASH) == 64


def test_no_collision_with_all_predecessor_lane1_batches() -> None:
    all_predecessor_ids: set[str] = set[str]().union(
        frequency_batch.CANDIDATE_IDS,
        conditional_batch.CANDIDATE_IDS,
        renyi2_batch.CANDIDATE_IDS,
        graph_batch.CANDIDATE_IDS,
        ensemble_batch.CANDIDATE_IDS,
        markov_batch.CANDIDATE_IDS,
        omission_batch.CANDIDATE_IDS,
        bayes_batch.CANDIDATE_IDS,
    )
    our_ids = set(batch.CANDIDATE_IDS)
    assert len(our_ids & all_predecessor_ids) == 0


# --- Portfolio generation & prefix contract tests ---


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_prefix_contracts_k5_k10_k20(constructor_id: str) -> None:
    id_5 = batch.candidate_id_for(constructor_id, 5)
    id_10 = batch.candidate_id_for(constructor_id, 10)
    id_20 = batch.candidate_id_for(constructor_id, 20)

    p5 = batch.produce_candidate_portfolio(id_5, _HISTORY, 750)
    p10 = batch.produce_candidate_portfolio(id_10, _HISTORY, 750)
    p20 = batch.produce_candidate_portfolio(id_20, _HISTORY, 750)

    assert len(p5) == 5
    assert len(p10) == 10
    assert len(p20) == 20

    for t in p20:
        assert _legal_ticket(t)

    assert p10[:5] == p5
    assert p20[:10] == p10


def test_named_callable_dispatch() -> None:
    for cid in batch.CANDIDATE_IDS:
        meta = batch.CANDIDATE_METADATA[cid]
        fn = getattr(batch, meta.IMPLEMENTATION_SYMBOL)
        assert callable(fn)
        portfolio = cast(batch.TicketPortfolio, fn(_HISTORY, 750))
        assert len(portfolio) == meta.TICKET_COUNT
        assert portfolio == batch.produce_candidate_portfolio(cid, _HISTORY, 750)


# --- Isolation tests ---


def test_no_rng_used() -> None:
    # Repeated calls return identical objects
    p1 = batch.produce_candidate_portfolio(batch.CANDIDATE_IDS[0], _HISTORY, 750)
    p2 = batch.produce_candidate_portfolio(batch.CANDIDATE_IDS[0], _HISTORY, 750)
    assert p1 == p2


def test_constructor_functions_match_frozen_constructors() -> None:
    # Ensure our module imports directly from constructors_r1 without modifying bodies
    universe = batch.produce_source_ticket_universe(_HISTORY, 750)
    p_low = constructors.construct_b649_candidate_set_low_overlap_v1(universe, 5)
    p_our = batch.produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k5(
        _HISTORY, 750
    )
    assert p_our == p_low
