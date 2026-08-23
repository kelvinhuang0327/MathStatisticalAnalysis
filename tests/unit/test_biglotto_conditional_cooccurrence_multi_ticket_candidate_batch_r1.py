from __future__ import annotations

import inspect
from collections.abc import Callable
from fractions import Fraction
from types import MappingProxyType
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR_DRAW: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY = (*_repeat(_FILLER, 750), _ANCHOR_DRAW)


def _window_fixture() -> tuple[Ticket, ...]:
    return (
        *_repeat(_FILLER, 450),
        *_repeat((1, 7, 13, 14, 15, 16), 250),
        *_repeat((1, 2, 8, 17, 18, 19), 50),
        _ANCHOR_DRAW,
    )


def _manual_ranking(
    window: int,
    normalized_ranks: tuple[Fraction, ...],
) -> batch.WindowRanking:
    zeros = tuple(tuple(0 for _ in range(49)) for _ in range(49))
    zero_fractions = tuple(tuple(Fraction(0, 1) for _ in range(49)) for _ in range(49))
    return batch.WindowRanking(
        WINDOW=window,
        ANCHOR_DRAW=_ANCHOR_DRAW,
        ESTIMATION_DRAW_COUNT=window,
        OCCURRENCES=(0,) * 49,
        PAIR_COUNTS=zeros,
        CONTRIBUTIONS=zero_fractions,
        SCORES=(Fraction(0, 1),) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized_ranks,
    )


def _all_zero_ranking(window: int) -> batch.WindowRanking:
    return _manual_ranking(window, (Fraction(0, 1),) * 49)


def test_fewer_than_751_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.produce_source_ticket_universe(_HISTORY[:750], 750)


def test_exactly_751_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 751)) == 210


def test_target_draw_is_excluded() -> None:
    future_target: object = (7, 8, 9, 10, 11, 12)
    history_with_target: tuple[object, ...] = (*_HISTORY, future_target)
    assert batch.produce_source_ticket_universe(history_with_target, 751) == (
        batch.produce_source_ticket_universe(_HISTORY, 751)
    )


def test_anchor_draw_is_exactly_target_index_minus_one() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 751, 50)
    assert ranking.ANCHOR_DRAW == _ANCHOR_DRAW


def test_anchor_draw_is_excluded_from_estimation_windows() -> None:
    history = (*_repeat((1, 7, 8, 9, 10, 11), 750), _ANCHOR_DRAW)
    ranking = batch.rank_numbers_by_window(history, 751, 750)
    assert ranking.ESTIMATION_DRAW_COUNT == 750
    assert ranking.occurrence(2) == 0
    assert ranking.pair_count(1, 2) == 0


def test_future_suffix_invariance_ignores_unreadable_future_rows() -> None:
    history_with_future: tuple[object, ...] = (*_HISTORY, object(), ("invalid",))
    assert batch.produce_source_ticket_universe(history_with_future, 751) == (
        batch.produce_source_ticket_universe(_HISTORY, 751)
    )


def test_caller_history_is_not_mutated() -> None:
    history = list(_HISTORY)
    snapshot = history.copy()
    batch.produce_source_ticket_universe(history, len(history))
    assert history == snapshot


def test_malformed_historical_draw_is_rejected() -> None:
    malformed = list(_HISTORY)
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.produce_source_ticket_universe(malformed, len(malformed))


def test_50_window_pair_counts_and_denominators_are_exact() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 50)
    assert ranking.occurrence(1) == 50
    assert ranking.pair_count(1, 8) == 50
    assert ranking.contribution(1, 8) == Fraction(1, 1)
    assert ranking.occurrence(2) == 50
    assert ranking.pair_count(2, 8) == 50
    assert ranking.occurrence(3) == 0
    assert ranking.contribution(3, 8) == Fraction(0, 1)


def test_300_window_pair_counts_are_exact() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 300)
    assert ranking.occurrence(1) == 300
    assert ranking.pair_count(1, 7) == 250
    assert ranking.contribution(1, 7) == Fraction(5, 6)
    assert ranking.occurrence(2) == 50
    assert ranking.pair_count(2, 8) == 50


def test_750_window_pair_counts_are_exact() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 750)
    assert ranking.occurrence(1) == 300
    assert ranking.pair_count(1, 7) == 250
    assert ranking.contribution(1, 7) == Fraction(5, 6)
    assert ranking.occurrence(2) == 50
    assert ranking.pair_count(2, 8) == 50


def test_zero_anchor_occurrence_contributes_exact_zero() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 50)
    assert ranking.occurrence(3) == 0
    assert ranking.contribution(3, 7) == Fraction(0, 1)


def test_self_anchor_contribution_is_excluded() -> None:
    history = (*_repeat((1, 2, 7, 8, 9, 10), 750), _ANCHOR_DRAW)
    ranking = batch.rank_numbers_by_window(history, 751, 50)
    assert ranking.pair_count(1, 1) == 0
    assert ranking.contribution(1, 1) == Fraction(0, 1)
    assert ranking.score(1) == Fraction(1, 1)


def test_anchor_numbers_can_score_without_forced_include_or_exclude() -> None:
    history = (*_repeat((1, 2, 7, 8, 9, 10), 750), _ANCHOR_DRAW)
    ranking = batch.rank_numbers_by_window(history, 751, 50)
    assert ranking.score(1) > 0
    assert ranking.score(2) > 0
    assert 1 in ranking.ORDERED_NUMBERS
    assert 2 in ranking.ORDERED_NUMBERS


def test_conditional_score_uses_exact_rational_arithmetic() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 50)
    assert ranking.score(8) == Fraction(2, 1)
    assert isinstance(ranking.score(8), Fraction)
    assert all(isinstance(score, Fraction) for score in ranking.SCORES)


def test_conditional_score_differs_from_plain_raw_frequency() -> None:
    history = (
        *_repeat(_FILLER, 690),
        *_repeat((1, 7, 8, 9, 10, 11), 20),
        *_repeat((7, 13, 14, 15, 16, 17), 30),
        *_repeat((2, 8, 18, 19, 20, 21), 10),
        _ANCHOR_DRAW,
    )
    ranking = batch.rank_numbers_by_window(history, 751, 50)
    raw_frequency_7 = 50
    raw_frequency_8 = 30
    assert raw_frequency_7 > raw_frequency_8
    assert ranking.score(8) > ranking.score(7)


def test_per_window_ranking_is_score_descending() -> None:
    ranking = batch.rank_numbers_by_window(_window_fixture(), 751, 50)
    assert ranking.score(ranking.ORDERED_NUMBERS[0]) >= ranking.score(
        ranking.ORDERED_NUMBERS[1]
    )
    assert ranking.ORDERED_NUMBERS[0] == 8


def test_score_ties_use_ascending_number() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 751, 50)
    assert tuple(range(1, 50)) == ranking.ORDERED_NUMBERS


def test_normalized_rank_is_exact() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 751, 50)
    assert ranking.normalized_rank(1) == Fraction(1, 1)
    assert ranking.normalized_rank(7) == Fraction(7, 8)
    assert ranking.normalized_rank(49) == Fraction(0, 1)


def test_three_window_fusion_uses_equal_exact_mean() -> None:
    fused = batch.calculate_fused_number_ranking(_HISTORY, 751)
    for number in (1, 7, 49):
        source_rank = fused.WINDOW_RANKINGS[0].normalized_rank(number)
        assert fused.mean_rank(number) == source_rank
        assert fused.robustness(number) == (source_rank, source_rank, source_rank)


def test_robustness_tie_breaks_use_minimum_then_median_then_maximum() -> None:
    ranking_a = [Fraction(0, 1)] * 49
    ranking_b = [Fraction(0, 1)] * 49
    ranking_c = [Fraction(0, 1)] * 49
    ranking_a[0] = Fraction(1, 1)
    ranking_a[1] = Fraction(2, 3)
    ranking_a[2] = Fraction(1, 2)
    ranking_b[0] = Fraction(0, 1)
    ranking_b[1] = Fraction(1, 3)
    ranking_b[2] = Fraction(1, 3)
    ranking_c[0] = Fraction(0, 1)
    ranking_c[1] = Fraction(0, 1)
    ranking_c[2] = Fraction(1, 6)
    fused = batch.fuse_window_rankings(
        (
            _manual_ranking(50, tuple(ranking_a)),
            _manual_ranking(300, tuple(ranking_b)),
            _manual_ranking(750, tuple(ranking_c)),
        )
    )
    assert fused.mean_rank(1) == fused.mean_rank(2) == fused.mean_rank(3)
    assert fused.robustness(3) > fused.robustness(2) > fused.robustness(1)
    assert fused.ORDERED_NUMBERS[:3] == (3, 2, 1)


def test_final_fusion_fallback_uses_ascending_number() -> None:
    fused = batch.fuse_window_rankings(
        (_all_zero_ranking(50), _all_zero_ranking(300), _all_zero_ranking(750))
    )
    assert tuple(range(1, 50)) == fused.ORDERED_NUMBERS


def test_source_top_pool_has_exactly_ten_numbers() -> None:
    fused = batch.calculate_fused_number_ranking(_HISTORY, 751)
    assert tuple(range(1, 11)) == fused.TOP_NUMBERS
    assert len(fused.TOP_NUMBERS) == 10


def test_source_ticket_universe_has_210_unique_legal_tickets() -> None:
    source = batch.produce_source_ticket_universe(_HISTORY, 751)
    assert len(source) == 210
    assert len(set(source)) == 210
    assert all(
        len(ticket) == 6
        and ticket == tuple(sorted(ticket))
        and len(set(ticket)) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in ticket)
        for ticket in source
    )


def test_source_ticket_order_follows_rank_position_combinations() -> None:
    source = batch.produce_source_ticket_universe(_HISTORY, 751)
    assert source[:3] == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 7),
        (1, 2, 3, 4, 5, 8),
    )


def test_repeated_source_generation_is_identical() -> None:
    assert batch.produce_source_ticket_universe(_HISTORY, 751) == (
        batch.produce_source_ticket_universe(_HISTORY, 751)
    )


_PREVIOUS_IDS = frozenset(
    {
        "BMSGV1_MT_ea27525f53ff8f0b",
        "BMSGV1_MT_2628ecfd1a1c8044",
        "BMSGV1_MT_fb5e3a301b9a42bf",
        "BMSGV1_MT_8221579815eb8982",
        "BMSGV1_MT_d528de4632bce527",
        "BMSGV1_MT_fe63f7109add79a9",
        "BMSGV1_MT_f7f1618b418c3ead",
        "BMSGV1_MT_7725361d25dac185",
        "BMSGV1_MT_d5f89c30bc23d082",
    }
)
_PREVIOUS_HASHES = frozenset(
    {
        "ea27525f53ff8f0ba3bd7664d5cab7b3a33bac8b2251e0251453138a52d2e803",
        "2628ecfd1a1c8044d65730410f4c8681c169373aea15abd12b4cefcf91f5521f",
        "fb5e3a301b9a42bf5ce6a32fef83d258bbe34bd2828f563e33902cf6d195276e",
        "8221579815eb898217ab0f4cbedd8f762f92510fb541f1ca012a820d77b975b5",
        "d528de4632bce5274c90c9723e3222fbaa741fe425b44869d5c8e7de0d4bc2d9",
        "fe63f7109add79a94848c276cf16cec524f75f0c6336d72dc698722707e0ae1e",
        "f7f1618b418c3ead34991b02e64f405b5810ad71a90c48e4be82da218422219a",
        "7725361d25dac1853387941193452c269f18b4bd74fa3796db91eb55d9c46e67",
        "d5f89c30bc23d0826c1621b351d78d2dc9a73108c7ea9ff2955fbfe825fb2308",
    }
)


def test_candidate_authority_has_exactly_nine_unique_identities() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert set(batch.CANDIDATE_METADATA) == set(batch.CANDIDATE_IDS)
    assert isinstance(batch.CANDIDATE_METADATA, MappingProxyType)


def test_candidate_matrix_is_exactly_three_constructors_by_three_budgets() -> None:
    pairs = {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT)
        for metadata in batch.CANDIDATE_AUTHORITIES
    }
    assert pairs == {
        (constructor_id, ticket_count)
        for constructor_id in batch.CONSTRUCTOR_IDS
        for ticket_count in batch.TICKET_COUNTS
    }
    assert {metadata.TICKET_COUNT for metadata in batch.CANDIDATE_AUTHORITIES} == {5, 10, 20}


def test_candidate_ids_and_hashes_do_not_collide_with_predecessor() -> None:
    assert _PREVIOUS_IDS.isdisjoint(batch.CANDIDATE_IDS)
    assert _PREVIOUS_HASHES.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


def test_candidate_identity_hashes_regenerate_deterministically() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert batch.candidate_id_for_semantics(metadata.SEMANTICS) == metadata.CANDIDATE_ID


def test_candidate_semantics_freeze_required_contract_fields() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert semantics["HYPOTHESIS_VERSION"] == "V1"
        assert semantics["SOURCE_UNIVERSE_ID"] == batch.SOURCE_UNIVERSE_ID
        assert semantics["SOURCE_WINDOWS"] == (50, 300, 750)
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 751
        assert semantics["TOP_NUMBER_COUNT"] == 10
        assert semantics["SOURCE_CANDIDATE_TICKET_COUNT"] == 210
        assert semantics["OUTPUT_SHAPE"] == "PORTFOLIO"
        assert semantics["NATIVE_TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["CAUSAL_CUTOFF_RULE"] == (
            "STRICTLY_PRIOR_ESTIMATION_PLUS_LAST_COMPLETED_DRAW_ANCHOR"
        )
        assert semantics["PARAMETER_SELECTION_RULE"] == (
            "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
        )
        assert semantics["DETERMINISM_CLASS"] == "PURE_DETERMINISTIC_NO_RNG"
        assert semantics["SOURCE_EXPECTED_IMPROVEMENT_CHANNEL"] == (
            "LAST_DRAW_CONDITIONAL_COOCCURRENCE_STRUCTURE"
        )
        assert semantics["CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL"] == (
            "TICKET_PAIRWISE_DIVERSITY"
            if metadata.CONSTRUCTOR_ID == "B649_CANDIDATE_SET_LOW_OVERLAP_V1"
            else "NUMBER_EXPOSURE_DIVERSITY"
            if metadata.CONSTRUCTOR_ID == "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1"
            else "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
        )


def test_canonical_semantic_json_is_sorted_compact_utf8_with_nulls() -> None:
    assert batch.canonicalize_semantic_record({"b": None, "a": (1, 2)}) == (
        b'{"a":[1,2],"b":null}'
    )


def test_all_portfolios_have_native_budget_legal_distinct_tickets() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        portfolio = batch.produce_biglotto_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _HISTORY, 751
        )
        assert len(portfolio) == metadata.TICKET_COUNT
        assert len(set(portfolio)) == metadata.TICKET_COUNT
        assert all(
            len(ticket) == 6
            and ticket == tuple(sorted(ticket))
            and len(set(ticket)) == 6
            and all(1 <= number <= 49 for number in ticket)
            for ticket in portfolio
        )


def test_all_portfolios_are_deterministic() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        first = batch.produce_biglotto_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _HISTORY, 751
        )
        second = batch.produce_biglotto_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _HISTORY, 751
        )
        assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        ticket_count: batch.produce_biglotto_multi_ticket_candidate(
            batch.candidate_id_for(constructor_id, ticket_count), _HISTORY, 751
        )
        for ticket_count in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_frozen_constructor_module_is_invoked_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = batch.produce_source_ticket_universe(_HISTORY, 751)
    calls: list[tuple[tuple[batch.Ticket, ...], int]] = []

    def fake_constructor(candidate_tickets: object, ticket_count: int) -> batch.TicketPortfolio:
        ordered = tuple(cast(tuple[batch.Ticket, ...], candidate_tickets))
        calls.append((ordered, ticket_count))
        return ordered[:ticket_count]

    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({batch.CONSTRUCTOR_IDS[0]: fake_constructor}),
    )
    candidate_id = batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5)
    result = batch.produce_biglotto_multi_ticket_candidate(candidate_id, _HISTORY, 751)
    assert result == source[:5]
    assert calls == [(source, 5)]


def test_constructors_are_referenced_through_prerequisite_module() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.CONSTRUCTORS" in source
    assert "_select_low_overlap" not in source
    assert "_select_exposure_balanced" not in source
    assert "_select_hybrid_diversity" not in source
    assert batch.__dict__["_constructors"] is constructors


def test_no_catalog_external_runtime_or_rng_registration_is_imported() -> None:
    imported_modules = set(batch.__dict__)
    assert not any(name.startswith("lottolab.strategies") for name in imported_modules)
    assert not any(
        forbidden in imported_modules
        for forbidden in (
            "random",
            "socket",
            "sqlite3",
            "requests",
            "datetime",
            "time",
            "os",
            "pathlib",
        )
    )
    source = inspect.getsource(batch)
    assert "import random" not in source
    assert "import sqlite3" not in source
    assert "import socket" not in source


def test_no_rng_is_used_and_source_metadata_declares_none() -> None:
    assert batch.RNG_SEMANTICS == "NONE"
    assert all(metadata.SEMANTICS["RNG_SEED"] is None for metadata in batch.CANDIDATE_AUTHORITIES)


def test_named_producers_cover_all_nine_candidates() -> None:
    symbols = {metadata.IMPLEMENTATION_SYMBOL for metadata in batch.CANDIDATE_AUTHORITIES}
    assert len(symbols) == 9
    for symbol in symbols:
        producer = cast(
            Callable[[batch.HistoryInput, int], batch.TicketPortfolio], getattr(batch, symbol)
        )
        metadata = next(
            item for item in batch.CANDIDATE_AUTHORITIES if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_HISTORY, 751)) == metadata.TICKET_COUNT
