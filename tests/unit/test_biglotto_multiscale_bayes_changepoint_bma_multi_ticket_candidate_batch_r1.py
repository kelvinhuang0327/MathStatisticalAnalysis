"""Focused tests for the causal BigLotto multiscale Bayesian changepoint BMA candidate batch."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from fractions import Fraction
from itertools import combinations
from types import MappingProxyType
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
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
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
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
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
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_window_rankings(history, len(history))


# --- Window splits & semantics tests ---


@pytest.mark.parametrize("window", batch.BAYES_WINDOWS)
def test_each_window_uses_exactly_w_draws_and_equal_halves(window: int) -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, window)
    assert window == ranking.WINDOW
    assert window == ranking.WINDOW_DRAW_COUNT
    assert window == ranking.DRAW_COUNT
    assert window // 2 == ranking.OLDER_DRAW_COUNT
    assert window // 2 == ranking.RECENT_DRAW_COUNT


def test_window_ranking_rejects_unsupported_window() -> None:
    with pytest.raises(ValueError, match="window must be one of"):
        batch.rank_numbers_by_window(_HISTORY, 750, 100)


def test_window_splits_chronology() -> None:
    # Build a 50-draw window where older 25 contains draw (1,2,3,4,5,6)
    # and recent 25 contains draw (7,8,9,10,11,12)
    history = [
        *_repeat(_FILLER, 700),
        *_repeat((1, 2, 3, 4, 5, 6), 25),
        *_repeat((7, 8, 9, 10, 11, 12), 25),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.k_old(1) == 25
    assert ranking.k_recent(1) == 0
    assert ranking.k_total(1) == 25

    assert ranking.k_old(7) == 0
    assert ranking.k_recent(7) == 25
    assert ranking.k_total(7) == 25


# --- Prior tests ---


def test_prior_constants_and_properties() -> None:
    assert batch.PRIOR_ALPHA == 6
    assert batch.PRIOR_BETA == 43
    assert Fraction(6, 49) == batch.PRIOR_MEAN
    assert batch.PRIOR_STRENGTH == 49
    assert Fraction(1, 2) == batch.MODEL_PRIOR_M0
    assert Fraction(1, 2) == batch.MODEL_PRIOR_M1


# --- Rising factorial & Beta evidence tests ---


def test_rising_factorial_semantics() -> None:
    assert batch.rising_factorial(6, 0) == 1
    assert batch.rising_factorial(43, 0) == 1
    assert batch.rising_factorial(6, 1) == 6
    assert batch.rising_factorial(6, 2) == 6 * 7
    assert batch.rising_factorial(6, 3) == 6 * 7 * 8
    with pytest.raises(ValueError, match="positive"):
        batch.rising_factorial(0, 1)
    with pytest.raises(ValueError, match="non-negative"):
        batch.rising_factorial(6, -1)


def test_beta_evidence_exact_cases_and_rationality() -> None:
    # N = 1, k = 1 => 6/49
    assert batch.beta_evidence(6, 43, 1, 1) == Fraction(6, 49)
    # N = 1, k = 0 => 43/49
    assert batch.beta_evidence(6, 43, 0, 1) == Fraction(43, 49)
    # N = 2, k = 1 => (6 * 43) / (49 * 50) = 258 / 2450 = 129 / 1225
    assert batch.beta_evidence(6, 43, 1, 2) == Fraction(129, 1225)
    # N = 0, k = 0 => 1
    assert batch.beta_evidence(6, 43, 0, 0) == Fraction(1, 1)
    # Evidence must always be positive
    assert batch.beta_evidence(6, 43, 5, 25) > 0
    assert batch.beta_evidence(6, 43, 0, 25) > 0


# --- M0 / M1 and Posterior model probabilities tests ---


def test_m0_and_m1_evidence_and_posterior() -> None:
    # Window W = 50, HALF_W = 25
    # Suppose number 1 has k_old = 10, k_recent = 10 -> k_total = 20
    # M0 evidence = BETA_EVIDENCE(6, 43, 20, 50)
    # M1 evidence = BETA_EVIDENCE(6, 43, 10, 25) * BETA_EVIDENCE(6, 43, 10, 25)
    m0_ev = batch.beta_evidence(6, 43, 20, 50)
    m1_ev = batch.beta_evidence(6, 43, 10, 25) * batch.beta_evidence(6, 43, 10, 25)
    post_m0, post_m1 = batch.calculate_posterior_model_probabilities(
        (m0_ev,) * 49, (m1_ev,) * 49
    )
    assert post_m1[0] == m1_ev / (m0_ev + m1_ev)
    assert post_m0[0] == m0_ev / (m0_ev + m1_ev)
    assert post_m0[0] + post_m1[0] == Fraction(1, 1)
    assert Fraction(0, 1) <= post_m1[0] <= Fraction(1, 1)
    assert Fraction(0, 1) <= post_m0[0] <= Fraction(1, 1)


# --- Predictive probabilities tests ---


def test_predictive_probabilities_exact_formula() -> None:
    # W = 50, HALF_W = 25
    # k_total = 20, k_recent = 10
    # PREDICTIVE_M0 = (6 + 20) / (49 + 50) = 26 / 99
    # PREDICTIVE_M1 = (6 + 10) / (49 + 25) = 16 / 74 = 8 / 37
    pred_m0 = batch.calculate_predictive_m0((20,) * 49, 50)
    pred_m1 = batch.calculate_predictive_m1((10,) * 49, 50)
    assert pred_m0[0] == Fraction(26, 99)
    assert pred_m1[0] == Fraction(16, 74)

    # BMA predictive
    p0 = Fraction(1, 3)
    p1 = Fraction(2, 3)
    bma = batch.calculate_bma_predictive((p0,) * 49, (p1,) * 49, pred_m0, pred_m1)
    expected = Fraction(1, 3) * Fraction(26, 99) + Fraction(2, 3) * Fraction(16, 74)
    assert bma[0] == expected
    assert isinstance(bma[0], Fraction)


# --- Bayesian specificity gate tests ---


def test_bayesian_specificity_case_a_equal_total_different_splits() -> None:
    # Two numbers with equal total count but different older/recent splits receive
    # different BMA predictive scores.
    # W = 50:
    # Number 1: 10 older, 0 recent (k_total = 10)
    # Number 2: 5 older, 5 recent (k_total = 10)
    history = [
        *_repeat(_FILLER, 700),
        # Older 25 (draws 0..24 of W50):
        *_repeat((1, 2, 20, 21, 22, 23), 5),
        *_repeat((1, 20, 21, 22, 23, 24), 5),
        *_repeat((20, 21, 22, 23, 24, 25), 15),
        # Recent 25 (draws 25..49 of W50):
        *_repeat((20, 21, 22, 23, 24, 25), 20),
        *_repeat((2, 20, 21, 22, 23, 24), 5),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.k_total(1) == ranking.k_total(2) == 10
    assert ranking.k_old(1) == 10 and ranking.k_recent(1) == 0
    assert ranking.k_old(2) == 5 and ranking.k_recent(2) == 5

    assert ranking.bma_predictive(1) != ranking.bma_predictive(2)
    assert ranking.predictive_m1(2) > ranking.predictive_m1(1)
    assert ranking.bma_predictive(2) > ranking.bma_predictive(1)


def test_bayesian_specificity_case_b_equal_recent_different_older_evidence() -> None:
    # Two numbers with equal recent count but different older evidence alter
    # posterior model probability.
    # Number 1: 0 older, 5 recent (k_total = 5)
    # Number 2: 15 older, 5 recent (k_total = 20)
    history = [
        *_repeat(_FILLER, 700),
        # Older 25:
        *_repeat((2, 20, 21, 22, 23, 24), 15),
        *_repeat((20, 21, 22, 23, 24, 25), 10),
        # Recent 25:
        *_repeat((1, 2, 20, 21, 22, 23), 5),
        *_repeat((20, 21, 22, 23, 24, 25), 20),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.k_recent(1) == ranking.k_recent(2) == 5
    assert ranking.k_old(1) == 0
    assert ranking.k_old(2) == 15

    assert ranking.posterior_m1(1) != ranking.posterior_m1(2)
    assert ranking.m0_evidence(1) != ranking.m0_evidence(2)


def test_bayesian_specificity_case_c_differs_from_full_window_frequency() -> None:
    # Number A: high total frequency (12 occurrences), but all in older half (0 recent)
    # Number B: moderate total frequency (10 occurrences), but all in recent half (10 recent)
    # Full window frequency: A (12) > B (10)
    # Bayesian BMA predictive: B > A because recent regime dominates B's prediction
    history = [
        *_repeat(_FILLER, 700),
        # Older 25:
        *_repeat((1, 20, 21, 22, 23, 24), 12),
        *_repeat((20, 21, 22, 23, 24, 25), 13),
        # Recent 25:
        *_repeat((2, 20, 21, 22, 23, 24), 10),
        *_repeat((20, 21, 22, 23, 24, 25), 15),
    ]
    assert len(history) == 750
    raw_freq_order = batch.raw_full_window_frequency_order(history, 750, 50)
    bma_order = batch.rank_numbers_by_window(history, 750, 50).ORDERED_NUMBERS

    assert raw_freq_order != bma_order
    assert raw_freq_order.index(1) < raw_freq_order.index(2)
    assert bma_order.index(2) < bma_order.index(1)


def test_bayesian_specificity_case_d_differs_from_recent_half_frequency() -> None:
    # Number A: stable high rate: 12 in older half, 6 in recent half (k_total = 18)
    # Number B: recent burst: 0 in older half, 7 in recent half (k_total = 7)
    # Recent half frequency: B (7) > A (6)
    # Under BMA: A has high M0 predictive (24/99) and moderate M1 predictive (12/74),
    # while B has low M0 predictive (13/99) and M1 predictive (13/74).
    # A's BMA predictive exceeds B's, reversing recent-half ordering!
    history = [
        *_repeat(_FILLER, 700),
        # Older 25:
        *_repeat((1, 20, 21, 22, 23, 24), 12),
        *_repeat((20, 21, 22, 23, 24, 25), 13),
        # Recent 25:
        *_repeat((1, 20, 21, 22, 23, 24), 6),
        *_repeat((2, 20, 21, 22, 23, 24), 7),
        *_repeat((20, 21, 22, 23, 24, 25), 12),
    ]
    assert len(history) == 750
    raw_recent_order = batch.raw_recent_half_frequency_order(history, 750, 50)
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    bma_order = ranking.ORDERED_NUMBERS

    assert raw_recent_order != bma_order
    assert raw_recent_order.index(2) < raw_recent_order.index(1)
    assert bma_order.index(1) < bma_order.index(2)
    assert ranking.bma_predictive(1) > ranking.bma_predictive(2)


def test_novelty_neighbor_semantic_non_equivalence() -> None:
    source = inspect.getsource(batch)
    assert batch.METHOD_FAMILY == "BAYESIAN_PROBABILISTIC"
    assert batch.SOURCE_UNIVERSE_ID == "B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1"
    assert "Orthogonal" not in source
    assert "Radical" not in source
    assert "ColdPool" not in source


# --- Per-window ranking and fusion tests ---


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
            OLDER_DRAW_COUNT=window // 2,
            RECENT_DRAW_COUNT=window // 2,
            K_OLD_COUNTS=(0,) * 49,
            K_RECENT_COUNTS=(0,) * 49,
            K_TOTAL_COUNTS=(0,) * 49,
            M0_EVIDENCE=(Fraction(0, 1),) * 49,
            M1_EVIDENCE=(Fraction(0, 1),) * 49,
            POSTERIOR_M0=(Fraction(1, 2),) * 49,
            POSTERIOR_M1=(Fraction(1, 2),) * 49,
            PREDICTIVE_M0=(Fraction(6, 49 + window),) * 49,
            PREDICTIVE_M1=(Fraction(6, 49 + window // 2),) * 49,
            BMA_PREDICTIVE=(Fraction(0, 1),) * 49,
            ORDERED_NUMBERS=tuple(range(1, 50)),
            POSITIONS=tuple(range(1, 50)),
            NORMALIZED_RANKS=normalized,
        )

    # Number 1: 1, 0, 0 -> mean = 1/3, sorted = (0, 0, 1)
    # Number 2: 2/3, 1/3, 0 -> mean = 1/3, sorted = (0, 1/3, 2/3)
    # Number 3: 1/2, 1/3, 1/6 -> mean = 1/3, sorted = (1/6, 1/3, 1/2)
    # Means are equal. Robustness min: Number 3 (1/6) > Number 2 (0) == Number 1 (0).
    # Robustness median: Number 2 (1/3) > Number 1 (0).
    # Order must be 3, 2, 1!
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
    assert source == batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)


# --- Candidate identities tests ---


def test_candidate_authority_is_exact_three_by_three() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert all(cid.startswith("BMSGV1_BY_") for cid in batch.CANDIDATE_IDS)
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
        "WINDOW_SPLIT_RULE",
        "PRIOR_FAMILY",
        "PRIOR_ALPHA",
        "PRIOR_BETA",
        "PRIOR_SOURCE",
        "MODEL_M0",
        "MODEL_M1",
        "MODEL_PRIOR_RULE",
        "BETA_EVIDENCE_RULE",
        "M0_EVIDENCE_RULE",
        "M1_EVIDENCE_RULE",
        "POSTERIOR_MODEL_RULE",
        "M0_PREDICTIVE_RULE",
        "M1_PREDICTIVE_RULE",
        "BMA_PREDICTIVE_RULE",
        "GLOBAL_RENORMALIZATION_RULE",
        "PER_WINDOW_RANKING_RULE",
        "WINDOW_NORMALIZATION_RULE",
        "WINDOW_FUSION_RULE",
        "ROBUSTNESS_RULE",
        "TOP_NUMBER_COUNT",
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
        assert semantics["METHOD_FAMILY"] == "BAYESIAN_PROBABILISTIC"
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 750
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == meta.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == meta.SIGNATURE_HASH


def test_no_collision_with_predecessors() -> None:
    previous_batches = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
        markov_batch,
        omission_batch,
    )
    previous_ids = {
        cid for prev in previous_batches for cid in prev.CANDIDATE_IDS
    }
    previous_signatures = {
        sig for prev in previous_batches for sig in prev.CANDIDATE_SIGNATURE_HASHES
    }
    assert previous_ids.isdisjoint(batch.CANDIDATE_IDS)
    assert previous_signatures.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


# --- Portfolio tests ---


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


def test_frozen_constructor_module_is_invoked_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(tuple(sorted(numbers)) for numbers in combinations(range(1, 11), 6))
    calls: list[tuple[tuple[object, ...], int]] = []

    def fake_constructor(
        candidate_tickets: Iterable[object], ticket_count: int
    ) -> batch.TicketPortfolio:
        candidate_tuple = tuple(candidate_tickets)
        calls.append((candidate_tuple, ticket_count))
        return cast(batch.TicketPortfolio, candidate_tuple[:ticket_count])

    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({batch.CONSTRUCTOR_IDS[0]: fake_constructor}),
    )

    def fake_source(
        _history: batch.HistoryInput, _target_index: int
    ) -> batch.TicketPortfolio:
        return cast(batch.TicketPortfolio, source)

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5), _HISTORY, 750
    )
    assert result == source[:5]
    assert calls == [(source, 5)]


def test_no_constructor_copy_catalog_registration_io_or_rng() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.CONSTRUCTORS" in source
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
    assert "import math" not in source
    assert "import scipy" not in source
    assert "import numpy" not in source


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
