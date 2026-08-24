"""Focused tests for the causal BigLotto multiscale codraw geometric residual candidate batch."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
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
    biglotto_multiscale_codraw_geometric_residual_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster_batch,
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
_HISTORY: tuple[Ticket, ...] = (*tuple(_make_distinct_draw(i) for i in range(749)), _ANCHOR)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = (*_repeat(_FILLER, 749), _ANCHOR)


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


# --- History and causality tests ---


def test_fewer_than_750_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 750"):
        batch.validate_prior_history(_HISTORY[:749], 749)


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


def test_malformed_historical_draw_is_rejected() -> None:
    history = list(_HISTORY)
    history[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_window_rankings(history, len(history), 50)


# --- Exact symmetric conditional null tests ---


def test_exact_uniform_mean_pair_distance_invariants() -> None:
    assert batch.uniform_mean_pair_distance(1) == Fraction(49, 2)
    assert batch.uniform_mean_pair_distance(49) == Fraction(49, 2)
    assert batch.uniform_mean_pair_distance(25) == Fraction(25, 2)

    for n in range(1, 50):
        val = batch.uniform_mean_pair_distance(n)
        sym_val = batch.uniform_mean_pair_distance(50 - n)
        assert val == sym_val
        # Direct summation check: sum_{m != n} |n-m| / 48
        direct_sum = sum(abs(n - m) for m in range(1, 50) if m != n)
        assert val == Fraction(direct_sum, 48)


def test_uniform_mean_pair_distance_rejects_out_of_domain() -> None:
    with pytest.raises(ValueError, match="number must be an integer"):
        batch.uniform_mean_pair_distance(0)
    with pytest.raises(ValueError, match="number must be an integer"):
        batch.uniform_mean_pair_distance(50)


# --- Window calculations and exact arithmetic ---


@pytest.mark.parametrize("window", batch.FEATURE_WINDOWS)
def test_each_window_uses_exactly_w_draws(window: int) -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, window)
    assert window == ranking.WINDOW
    assert window == ranking.WINDOW_DRAW_COUNT
    assert window == ranking.DRAW_COUNT


def test_window_ranking_rejects_unsupported_window() -> None:
    with pytest.raises(ValueError, match="window must be one of"):
        batch.rank_numbers_by_window(_HISTORY, 750, 100)


def test_geometric_distance_calculation_zero_information() -> None:
    # Filler is (30, 31, 32, 33, 34, 35) repeated 749 times + Anchor (1, 2, 3, 4, 5, 6)
    ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 750, 50)
    # Number 49 never appeared in the 50 draws: occ=0, act=0, exp=0, pressure=0
    calc_49 = ranking.calculation_for(49)
    assert calc_49.OCCURRENCE_COUNT == 0
    assert calc_49.ACTUAL_DISTANCE_SUM == 0
    assert Fraction(0, 1) == calc_49.EXPECTED_DISTANCE_SUM
    assert Fraction(0, 1) == calc_49.SIGNED_DISTANCE_RESIDUAL
    assert Fraction(0, 1) == calc_49.OBSERVED_MEAN_PAIR_DISTANCE
    assert Fraction(0, 1) == calc_49.RELATIVE_GEOMETRIC_DEVIATION
    assert Fraction(0, 1) == calc_49.GEOMETRIC_RESIDUAL_PRESSURE


def test_geometric_pressure_two_formula_equivalence() -> None:
    # On a diverse history, ensure all calculations satisfy both algebraic forms
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, 50)
    for n in range(1, 50):
        calc = ranking.calculation_for(n)
        if calc.OCCURRENCE_COUNT > 0:
            form1 = Fraction(calc.OCCURRENCE_COUNT, 50) * calc.RELATIVE_GEOMETRIC_DEVIATION
            form2 = abs(Fraction(calc.ACTUAL_DISTANCE_SUM, 1) - calc.EXPECTED_DISTANCE_SUM) / (
                Fraction(5 * 50, 1) * calc.UNIFORM_MEAN_PAIR_DISTANCE
            )
            assert form1 == form2 == calc.GEOMETRIC_RESIDUAL_PRESSURE


# --- Geometry specificity gate tests ---


def test_geometry_specificity_same_occurrences_different_co_draw_distances() -> None:
    near_draw: Ticket = (8, 9, 10, 11, 12, 13)
    far_draw_11: Ticket = (1, 2, 11, 47, 48, 49)
    filler_other: Ticket = (20, 21, 22, 23, 24, 25)

    history_eq = [
        *_repeat(_FILLER, 700),
        *_repeat(filler_other, 39),
        (10, 8, 9, 12, 13, 14),
        *_repeat(near_draw, 9),
        far_draw_11,
    ]
    ranking_eq = batch.rank_numbers_by_window(history_eq, 750, 50)
    assert ranking_eq.occurrence_count(10) == 10
    assert ranking_eq.occurrence_count(11) == 10
    assert ranking_eq.actual_distance_sum(10) != ranking_eq.actual_distance_sum(11)
    assert ranking_eq.geometric_residual_pressure(10) != ranking_eq.geometric_residual_pressure(11)
    assert ranking_eq.position(10) != ranking_eq.position(11)


def test_geometry_specificity_can_reverse_raw_frequency_ordering() -> None:
    history = [
        *_repeat(_FILLER, 700),
        *_repeat((1, 10, 20, 30, 40, 48), 25),
        *_repeat((2, 45, 46, 47, 48, 49), 10),
        *_repeat((20, 21, 22, 23, 24, 25), 15),
    ]
    assert len(history) == 750
    raw_freq = batch.raw_frequency_order_for_window(history, 750, 50)
    geom_ranking = batch.rank_numbers_by_window(history, 750, 50)
    geom_order = geom_ranking.ORDERED_NUMBERS

    assert raw_freq.index(1) < raw_freq.index(2)
    assert geom_ranking.geometric_residual_pressure(2) > geom_ranking.geometric_residual_pressure(1)
    assert geom_order.index(2) < geom_order.index(1)


def test_geometry_specificity_differs_from_multiscale_frequency() -> None:
    geom_fused = batch.calculate_fused_number_ranking(_HISTORY, 750)
    ms_freq_order = batch.multiscale_frequency_order(_HISTORY, 750)
    assert ms_freq_order != geom_fused.ORDERED_NUMBERS


def test_geometry_specificity_near_peer_vs_far_peer_residual_sensitivity() -> None:
    # Number 25 appearing 10 times with immediate neighbors (23, 24, 25, 26, 27, 28)
    # vs Number 3 appearing 10 times with extreme far peers (1, 2, 3, 47, 48, 49).
    # Near-peers produce small actual distance sum -> negative residual.
    # Far-peers produce large actual distance sum -> positive residual.
    # Both produce non-zero geometric residual pressure.
    history = [
        *_repeat(_FILLER, 700),
        *_repeat((23, 24, 25, 26, 27, 28), 10),
        *_repeat((1, 2, 3, 47, 48, 49), 10),
        *_repeat((10, 11, 12, 13, 14, 15), 30),
    ]
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    calc_25 = ranking.calculation_for(25)
    calc_3 = ranking.calculation_for(3)

    assert calc_25.SIGNED_DISTANCE_RESIDUAL < 0
    assert calc_3.SIGNED_DISTANCE_RESIDUAL > 0
    assert calc_25.GEOMETRIC_RESIDUAL_PRESSURE > 0
    assert calc_3.GEOMETRIC_RESIDUAL_PRESSURE > 0


def test_geometry_specificity_edge_number_null_correction_prevents_structural_bias() -> None:
    null_1 = batch.uniform_mean_pair_distance(1)
    null_25 = batch.uniform_mean_pair_distance(25)
    null_49 = batch.uniform_mean_pair_distance(49)

    assert null_1 == Fraction(49, 2)
    assert null_49 == Fraction(49, 2)
    assert null_25 == Fraction(25, 2)
    assert null_1 > null_25


# --- Per-window ranking & fusion tests ---


def test_per_window_tie_breaks_and_normalization() -> None:
    ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 750, 50)
    assert ranking.position(ranking.ORDERED_NUMBERS[0]) == 1
    assert ranking.normalized_rank(ranking.ORDERED_NUMBERS[0]) == Fraction(1, 1)
    assert ranking.position(ranking.ORDERED_NUMBERS[-1]) == 49
    assert ranking.normalized_rank(ranking.ORDERED_NUMBERS[-1]) == Fraction(0, 1)


def test_three_window_fusion_exact_rational_mean_and_robustness() -> None:
    def _manual_ranking(window: int, normalized: tuple[Fraction, ...]) -> batch.WindowRanking:
        return batch.WindowRanking(
            WINDOW=window,
            WINDOW_DRAW_COUNT=window,
            OCCURRENCE_COUNTS=(0,) * 49,
            ACTUAL_DISTANCE_SUMS=(0,) * 49,
            EXPECTED_DISTANCE_SUMS=(Fraction(0, 1),) * 49,
            SIGNED_DISTANCE_RESIDUALS=(Fraction(0, 1),) * 49,
            OBSERVED_MEAN_PAIR_DISTANCES=(Fraction(0, 1),) * 49,
            UNIFORM_MEAN_PAIR_DISTANCES=(Fraction(49, 2),) * 49,
            RELATIVE_GEOMETRIC_DEVIATIONS=(Fraction(0, 1),) * 49,
            GEOMETRIC_RESIDUAL_PRESSURES=(Fraction(0, 1),) * 49,
            ORDERED_NUMBERS=tuple(range(1, 50)),
            POSITIONS=tuple(range(1, 50)),
            NORMALIZED_RANKS=normalized,
            CALCULATIONS=(),
        )

    r50 = [Fraction(0, 1)] * 49
    r300 = [Fraction(0, 1)] * 49
    r750 = [Fraction(0, 1)] * 49

    r50[0], r50[1], r50[2] = Fraction(1, 1), Fraction(2, 3), Fraction(1, 2)
    r300[0], r300[1], r300[2] = Fraction(0, 1), Fraction(1, 3), Fraction(1, 3)
    r750[0], r750[1], r750[2] = Fraction(0, 1), Fraction(0, 1), Fraction(1, 6)

    fused = batch.fuse_window_rankings(
        (
            _manual_ranking(50, tuple(r50)),
            _manual_ranking(300, tuple(r300)),
            _manual_ranking(750, tuple(r750)),
        )
    )
    assert fused.mean_rank(1) == fused.mean_rank(2) == fused.mean_rank(3) == Fraction(1, 3)
    assert fused.robustness(3) == (Fraction(1, 6), Fraction(1, 3), Fraction(1, 2))
    assert fused.robustness(2) == (Fraction(0, 1), Fraction(1, 3), Fraction(2, 3))
    assert fused.robustness(1) == (Fraction(0, 1), Fraction(0, 1), Fraction(1, 1))
    assert fused.ORDERED_NUMBERS[:3] == (3, 2, 1)


# --- Source universe tests ---


def test_source_universe_top10_and_210_ordered_tickets() -> None:
    fused = batch.calculate_fused_number_ranking(_ZERO_INFORMATION_HISTORY, 750)
    source = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[pos] for pos in combo))
        for combo in combinations(range(10), 6)
    )
    assert len(fused.TOP_NUMBERS) == 10
    assert len(source) == 210
    assert source == expected
    assert len(set(source)) == 210
    assert all(_legal_ticket(ticket) for ticket in source)


# --- Candidate identities & matrix tests ---


def test_candidate_authority_is_exact_three_by_three() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert all(cid.startswith("BMSGV1_GM_") for cid in batch.CANDIDATE_IDS)
    assert {
        (meta.CONSTRUCTOR_ID, meta.TICKET_COUNT) for meta in batch.CANDIDATE_AUTHORITIES
    } == {
        (cid, tc) for cid in batch.CONSTRUCTOR_IDS for tc in batch.TICKET_COUNTS
    }
    assert sum(meta.TICKET_COUNT == 5 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 10 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 20 for meta in batch.CANDIDATE_AUTHORITIES) == 3


def test_candidate_semantics_contract_keys() -> None:
    required_keys = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "WINDOWS",
        "FEATURE_WINDOWS",
        "SOURCE_WINDOWS",
        "GEOMETRY_DOMAIN_RULE",
        "NUMBER_DISTANCE_RULE",
        "UNIFORM_NULL_RULE",
        "UNIFORM_MEAN_PAIR_DISTANCE_RULE",
        "EXPECTED_DISTANCE_RULE",
        "SIGNED_DISTANCE_RESIDUAL_RULE",
        "RELATIVE_GEOMETRIC_DEVIATION_RULE",
        "GEOMETRIC_RESIDUAL_PRESSURE_RULE",
        "PER_WINDOW_RANKING_RULE",
        "WINDOW_NORMALIZATION_RULE",
        "WINDOW_FUSION_RULE",
        "ROBUSTNESS_RULE",
        "TOP_NUMBER_COUNT",
        "SOURCE_NUMBER_POOL_COUNT",
        "SOURCE_CANDIDATE_TICKET_COUNT",
        "SOURCE_TICKET_ORDER",
        "CONSTRUCTOR_ID",
        "CONSTRUCTOR_VERSION",
        "TICKET_COUNT",
        "NATIVE_TICKET_COUNT",
        "OUTPUT_SHAPE",
        "MINIMUM_HISTORY",
        "CAUSAL_CUTOFF_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "EXPECTED_IMPROVEMENT_CHANNEL",
    }
    for meta in batch.CANDIDATE_AUTHORITIES:
        semantics = meta.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["METHOD_FAMILY"] == "GEOMETRY"
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 750
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == meta.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == meta.SIGNATURE_HASH


def test_no_collision_with_all_predecessor_lane1_batches() -> None:
    all_predecessor_batches = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
        markov_batch,
        omission_batch,
        bayes_batch,
        cluster_batch,
    )
    all_predecessor_ids: set[str] = set()
    all_predecessor_signatures: set[str] = set()
    for prev in all_predecessor_batches:
        all_predecessor_ids.update(prev.CANDIDATE_IDS)
        raw_sigs: object = prev.CANDIDATE_SIGNATURE_HASHES
        if isinstance(raw_sigs, Mapping):
            mapping = cast(Mapping[str, str], raw_sigs)
            for v in mapping.values():
                all_predecessor_signatures.add(v)
        elif isinstance(raw_sigs, (tuple, list, set)):
            seq = tuple(cast(Iterable[str], raw_sigs))
            for v in seq:
                all_predecessor_signatures.add(v)

    our_ids = set(batch.CANDIDATE_IDS)
    our_signatures = set(batch.CANDIDATE_SIGNATURE_HASHES.values())

    assert our_ids.isdisjoint(all_predecessor_ids)
    assert our_signatures.isdisjoint(all_predecessor_signatures)


# --- Portfolio tests & prefix contracts ---


@pytest.mark.parametrize(
    "metadata", batch.CANDIDATE_AUTHORITIES, ids=lambda item: item.CANDIDATE_ID
)
def test_all_candidate_portfolios_are_legal_distinct_and_deterministic(
    metadata: batch.CandidateMetadata,
) -> None:
    first = batch.produce_candidate_portfolio(
        metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 750
    )
    second = batch.produce_candidate_portfolio(
        metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 750
    )
    assert len(first) == metadata.TICKET_COUNT
    assert len(set(first)) == metadata.TICKET_COUNT
    assert all(_legal_ticket(ticket) for ticket in first)
    assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(
    constructor_id: str,
) -> None:
    outputs = {
        tc: batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, tc),
            _ZERO_INFORMATION_HISTORY,
            750,
        )
        for tc in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_constructor_functions_match_frozen_constructors() -> None:
    universe = batch.produce_source_ticket_universe(_HISTORY, 750)
    p_low_5 = constructors.construct_b649_candidate_set_low_overlap_v1(universe, 5)
    p_our_low_5 = (
        batch.produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k5(
            _HISTORY, 750
        )
    )
    assert p_our_low_5 == p_low_5

    p_exp_10 = constructors.construct_b649_candidate_set_exposure_balanced_v1(universe, 10)
    p_our_exp_10 = (
        batch.produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k10(
            _HISTORY, 750
        )
    )
    assert p_our_exp_10 == p_exp_10

    p_hyb_20 = constructors.construct_b649_candidate_set_hybrid_diversity_v1(universe, 20)
    p_our_hyb_20 = (
        batch.produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k20(
            _HISTORY, 750
        )
    )
    assert p_our_hyb_20 == p_hyb_20


def test_no_constructor_copy_catalog_registration_io_or_rng() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.construct_" in source or "_constructors.CONSTRUCTORS" in source
    assert "def _select_low_overlap" not in source
    assert "def _select_exposure_balanced" not in source
    assert "def _select_hybrid_diversity" not in source
    assert "production_catalog" not in source
    assert "import os" not in source
    assert "import pathlib" not in source
    assert "import random" not in source
    assert "import sqlite" not in source
    assert "import requests" not in source
    assert "import socket" not in source
    assert "import time" not in source


def test_named_producers_cover_all_nine_candidates() -> None:
    symbols = {
        metadata.IMPLEMENTATION_SYMBOL for metadata in batch.CANDIDATE_AUTHORITIES
    }
    assert len(symbols) == 9
    for symbol in symbols:
        producer = cast(
            Callable[[batch.HistoryInput, int], batch.TicketPortfolio],
            getattr(batch, symbol),
        )
        metadata = next(
            item
            for item in batch.CANDIDATE_AUTHORITIES
            if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_ZERO_INFORMATION_HISTORY, 750)) == metadata.TICKET_COUNT
