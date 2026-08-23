from __future__ import annotations

import inspect
from collections.abc import Callable
from fractions import Fraction
from types import MappingProxyType
from typing import cast

import pytest

from lottolab.research import biglotto_multi_ticket_candidate_batch_r1 as batch
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _varied_history(count: int = 750) -> tuple[Ticket, ...]:
    draws: list[Ticket] = []
    for index in range(count):
        start = (index % 49) + 1
        values = tuple(((start + offset - 1) % 49) + 1 for offset in range(6))
        draws.append(values)  # type: ignore[arg-type]
    return tuple(draws)


_CONSTANT_DRAW: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY = _repeat(_CONSTANT_DRAW, 750)


def _manual_ranking(
    window: int, normalized_ranks: tuple[Fraction, ...]
) -> batch.WindowRanking:
    return batch.WindowRanking(
        WINDOW=window,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        FREQUENCIES=(0,) * 49,
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized_ranks,
    )


def _all_zero_ranking(window: int) -> batch.WindowRanking:
    return _manual_ranking(window, (Fraction(0, 1),) * 49)


def test_insufficient_history_is_rejected_explicitly() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.produce_source_ticket_universe(_HISTORY[:749], 749)


def test_exactly_minimum_history_is_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 750)) == 210


def test_target_row_is_excluded() -> None:
    future_target = object()
    history_with_target: tuple[object, ...] = (*_HISTORY, future_target)
    assert batch.produce_source_ticket_universe(history_with_target, 750) == (
        batch.produce_source_ticket_universe(_HISTORY, 750)
    )


def test_future_suffix_invariance_includes_unreadable_future_rows() -> None:
    history_with_future: tuple[object, ...] = (*_HISTORY, object(), ("invalid",))
    assert batch.produce_source_ticket_universe(history_with_future, 750) == (
        batch.produce_source_ticket_universe(_HISTORY, 750)
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


def test_50_window_frequency_ranking_uses_immediately_prior_draws() -> None:
    history = (*_varied_history(700), *_repeat(_CONSTANT_DRAW, 50))
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.ORDERED_NUMBERS[:6] == (1, 2, 3, 4, 5, 6)
    assert ranking.frequency(1) == 50
    assert ranking.frequency(7) == 0


def test_300_window_frequency_ranking_uses_immediately_prior_draws() -> None:
    history = (
        *_varied_history(400),
        *_repeat((7, 8, 9, 10, 11, 12), 300),
        *_repeat(_CONSTANT_DRAW, 50),
    )
    ranking = batch.rank_numbers_by_window(history, 750, 300)
    assert ranking.ORDERED_NUMBERS[:6] == (7, 8, 9, 10, 11, 12)
    assert ranking.frequency(7) == 250
    assert ranking.frequency(1) == 50


def test_750_window_frequency_ranking_uses_full_minimum_history() -> None:
    history = _repeat((13, 14, 15, 16, 17, 18), 750)
    ranking = batch.rank_numbers_by_window(history, 750, 750)
    assert ranking.ORDERED_NUMBERS[:6] == (13, 14, 15, 16, 17, 18)
    assert ranking.frequency(13) == 750


def test_raw_frequency_ties_use_ascending_number() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, 50)
    assert ranking.ORDERED_NUMBERS[:10] == tuple(range(1, 11))


def test_normalized_ranks_are_exact() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, 50)
    assert ranking.normalized_rank(1) == Fraction(1, 1)
    assert ranking.normalized_rank(7) == Fraction(7, 8)
    assert ranking.normalized_rank(49) == Fraction(0, 1)
    assert all(isinstance(rank, Fraction) for rank in ranking.NORMALIZED_RANKS)


def test_three_window_fusion_uses_equal_weight_exact_mean() -> None:
    fused = batch.calculate_fused_number_ranking(_HISTORY, 750)
    for number in (1, 7, 49):
        source_rank = fused.WINDOW_RANKINGS[0].normalized_rank(number)
        assert fused.mean_rank(number) == source_rank
        assert fused.robustness(number) == (source_rank, source_rank, source_rank)


def test_robustness_orders_minimum_then_median_then_maximum_descending() -> None:
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


def test_final_number_fallback_tie_uses_ascending_number() -> None:
    fused = batch.fuse_window_rankings(
        (_all_zero_ranking(50), _all_zero_ranking(300), _all_zero_ranking(750))
    )
    assert tuple(range(1, 50)) == fused.ORDERED_NUMBERS


def test_source_top_number_pool_has_exactly_ten_numbers() -> None:
    fused = batch.calculate_fused_number_ranking(_HISTORY, 750)
    assert len(fused.TOP_NUMBERS) == 10
    assert tuple(range(1, 11)) == fused.TOP_NUMBERS


def test_source_ticket_universe_has_210_unique_legal_tickets() -> None:
    source = batch.produce_source_ticket_universe(_HISTORY, 750)
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
    source = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert source[:3] == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 7),
        (1, 2, 3, 4, 5, 8),
    )


def test_repeated_source_universe_generation_is_structure_equivalent() -> None:
    first = batch.produce_source_ticket_universe(_HISTORY, 750)
    second = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert first == second


def test_candidate_authority_has_exactly_nine_unique_identities() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(batch.CANDIDATE_IDS) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert set(batch.CANDIDATE_METADATA) == set(batch.CANDIDATE_IDS)
    assert isinstance(batch.CANDIDATE_METADATA, MappingProxyType)


def test_candidate_identity_hashes_regenerate_deterministically() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert batch.candidate_id_for_semantics(metadata.SEMANTICS) == metadata.CANDIDATE_ID


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


def test_candidate_semantics_freeze_required_contract_fields() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert semantics["HYPOTHESIS_VERSION"] == "V1"
        assert semantics["SOURCE_UNIVERSE_ID"] == batch.SOURCE_UNIVERSE_ID
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["SOURCE_WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 750
        assert semantics["TOP_NUMBER_COUNT"] == 10
        assert semantics["SOURCE_CANDIDATE_TICKET_COUNT"] == 210
        assert semantics["OUTPUT_SHAPE"] == "PORTFOLIO"
        assert semantics["NATIVE_TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["CAUSAL_CUTOFF_RULE"] == (
            "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
        )
        assert semantics["PARAMETER_SELECTION_RULE"] == (
            "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
        )
        assert semantics["DETERMINISM_CLASS"] == "PURE_DETERMINISTIC_NO_RNG"


def test_canonical_semantic_json_is_sorted_compact_utf8_with_nulls() -> None:
    assert batch.canonicalize_semantic_record({"b": None, "a": (1, 2)}) == (
        b'{"a":[1,2],"b":null}'
    )


def test_all_portfolios_have_native_budget_legal_distinct_tickets() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        portfolio = batch.produce_biglotto_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _HISTORY, 750
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
        first = batch.produce_biglotto_multi_ticket_candidate(metadata.CANDIDATE_ID, _HISTORY, 750)
        second = batch.produce_biglotto_multi_ticket_candidate(metadata.CANDIDATE_ID, _HISTORY, 750)
        assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        ticket_count: batch.produce_biglotto_multi_ticket_candidate(
            batch.candidate_id_for(constructor_id, ticket_count), _HISTORY, 750
        )
        for ticket_count in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_generic_producer_does_not_mutate_source_ticket_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = batch.produce_source_ticket_universe(_HISTORY, 750)
    snapshot = source

    def fake_source(history: batch.HistoryInput, target_index: int) -> batch.TicketPortfolio:
        return source

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    candidate_id = batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5)
    batch.produce_biglotto_multi_ticket_candidate(candidate_id, _HISTORY, 750)
    assert source == snapshot


def test_constructors_are_called_through_prerequisite_module() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.CONSTRUCTORS" in source
    assert "_select_low_overlap" not in source
    assert "_select_exposure_balanced" not in source
    assert "_select_hybrid_diversity" not in source
    assert batch.__dict__["_constructors"] is constructors


def test_no_production_catalog_or_external_runtime_registration_is_imported() -> None:
    imported_modules = set(batch.__dict__)
    assert not any(name.startswith("lottolab.strategies") for name in imported_modules)
    assert not any(
        forbidden in imported_modules
        for forbidden in ("random", "socket", "sqlite3", "requests", "datetime", "time")
    )


def test_no_rng_is_used_and_source_metadata_declares_none() -> None:
    assert batch.RNG_SEMANTICS == "NONE"
    assert all(metadata.SEMANTICS["RNG_SEED"] is None for metadata in batch.CANDIDATE_AUTHORITIES)
    source = inspect.getsource(batch)
    assert "import random" not in source
    assert "random." not in source


def test_named_producers_cover_all_nine_candidates() -> None:
    symbols = {
        metadata.IMPLEMENTATION_SYMBOL
        for metadata in batch.CANDIDATE_AUTHORITIES
    }
    assert len(symbols) == 9
    for symbol in symbols:
        producer = cast(
            Callable[[batch.HistoryInput, int], batch.TicketPortfolio], getattr(batch, symbol)
        )
        assert callable(producer)
        metadata = next(
            item for item in batch.CANDIDATE_AUTHORITIES if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_HISTORY, 750)) == metadata.TICKET_COUNT
