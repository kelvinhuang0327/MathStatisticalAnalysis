from __future__ import annotations

import inspect
from collections.abc import Callable
from fractions import Fraction
from itertools import combinations
from types import MappingProxyType
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as conditional_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_candidate_batch_r1 as frequency_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_constructors_r1 as constructors,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _varied_history(count: int) -> tuple[Ticket, ...]:
    draws: list[Ticket] = []
    for index in range(count):
        start = (index % 49) + 1
        values = tuple(((start + offset - 1) % 49) + 1 for offset in range(6))
        draws.append(cast(Ticket, values))
    return tuple(draws)


_DRAW_A: Ticket = (1, 2, 3, 4, 5, 6)
_DRAW_B: Ticket = (7, 8, 9, 10, 11, 12)
_DRAW_C: Ticket = (13, 14, 15, 16, 17, 18)
_CONCENTRATED_HISTORY: tuple[Ticket, ...] = (
    *_repeat(_DRAW_C, 451),
    *_repeat(_DRAW_B, 250),
    *_repeat(_DRAW_A, 50),
)
_DIFFUSE_HISTORY: tuple[Ticket, ...] = (
    *_repeat(_DRAW_A, 701),
    *_varied_history(50),
)
_SOURCE_TICKETS: tuple[Ticket, ...] = cast(
    tuple[Ticket, ...], tuple(combinations(range(1, 11), 6))
)


def test_fewer_than_751_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.produce_source_ticket_universe(_CONCENTRATED_HISTORY[:750], 750)


def test_exactly_751_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_CONCENTRATED_HISTORY, 751)) == 210


def test_target_row_is_excluded() -> None:
    future_target: object = (19, 20, 21, 22, 23, 24)
    history_with_target: tuple[object, ...] = (*_CONCENTRATED_HISTORY, future_target)
    assert batch.produce_source_ticket_universe(history_with_target, 751) == (
        batch.produce_source_ticket_universe(_CONCENTRATED_HISTORY, 751)
    )


def test_future_suffix_invariance_ignores_unreadable_future_rows() -> None:
    history_with_future: tuple[object, ...] = (*_CONCENTRATED_HISTORY, object(), ("invalid",))
    assert batch.produce_source_ticket_universe(history_with_future, 751) == (
        batch.produce_source_ticket_universe(_CONCENTRATED_HISTORY, 751)
    )


def test_input_history_is_not_mutated() -> None:
    history = list(_CONCENTRATED_HISTORY)
    snapshot = history.copy()
    batch.produce_source_ticket_universe(history, len(history))
    assert history == snapshot


def test_malformed_prior_draw_is_rejected() -> None:
    malformed = list(_CONCENTRATED_HISTORY)
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.produce_source_ticket_universe(malformed, len(malformed))


def test_exact_collision_values_and_reference_mean() -> None:
    state = batch.calculate_regime_state(_CONCENTRATED_HISTORY, 751)
    assert Fraction(1, 6) == state.COLLISION_50
    assert Fraction(13, 108) == state.COLLISION_300
    assert Fraction(107, 1350) == state.COLLISION_750
    assert Fraction(539, 5400) == state.REFERENCE_COLLISION
    assert all(
        isinstance(value, Fraction)
        for value in (
            state.COLLISION_50,
            state.COLLISION_300,
            state.COLLISION_750,
            state.REFERENCE_COLLISION,
        )
    )


def test_collision_helpers_return_the_three_exact_windows() -> None:
    assert batch.calculate_collision_concentrations(_CONCENTRATED_HISTORY, 751) == (
        Fraction(1, 6),
        Fraction(13, 108),
        Fraction(107, 1350),
    )
    assert batch.calculate_collision_concentration(_CONCENTRATED_HISTORY, 751, 50) == (
        Fraction(1, 6)
    )


def test_concentrated_regime_uses_low_renyi2_source() -> None:
    state = batch.calculate_regime_state(_CONCENTRATED_HISTORY, 751)
    assert state.COLLISION_50 > state.REFERENCE_COLLISION
    assert state.REGIME == batch.RECENT_CONCENTRATED_LOW_RENYI2
    assert state.SELECTED_SOURCE == batch.LOW_ENTROPY_SOURCE_ID


def test_diffuse_regime_uses_high_renyi2_source() -> None:
    state = batch.calculate_regime_state(_DIFFUSE_HISTORY, 751)
    assert state.COLLISION_50 < state.REFERENCE_COLLISION
    assert state.REGIME == batch.RECENT_DIFFUSE_HIGH_RENYI2
    assert state.SELECTED_SOURCE == batch.HIGH_ENTROPY_SOURCE_ID


def test_exact_collision_tie_is_diffuse() -> None:
    collision = Fraction(7, 31)
    assert batch.classify_regime(collision, collision) == (
        batch.RECENT_DIFFUSE_HIGH_RENYI2
    )
    assert batch.calculate_reference_collision(collision, collision) == collision


def test_regime_rule_has_no_float_or_log_threshold_dependence() -> None:
    source = inspect.getsource(batch)
    assert "float(" not in source
    assert "log(" not in source
    assert "Fraction" in source


def test_repeated_identical_input_keeps_the_same_source_family() -> None:
    first = batch.calculate_regime_state(_CONCENTRATED_HISTORY, 751)
    second = batch.calculate_regime_state(_CONCENTRATED_HISTORY, 751)
    assert first == second
    assert first.SELECTED_SOURCE == second.SELECTED_SOURCE


def test_concentrated_source_delegation_receives_exact_history_and_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, int]] = []

    def fake_frequency(history: object, target_index: int) -> batch.TicketPortfolio:
        calls.append((history, target_index))
        return _SOURCE_TICKETS

    monkeypatch.setattr(
        frequency_batch,
        "produce_b649_multiscale_frequency_ranked_pool_v1",
        fake_frequency,
    )
    result = batch.produce_source_ticket_universe(_CONCENTRATED_HISTORY, 751)
    assert result == _SOURCE_TICKETS
    assert calls == [(_CONCENTRATED_HISTORY, 751)]
    assert calls[0][0] is _CONCENTRATED_HISTORY


def test_diffuse_source_delegation_receives_exact_history_and_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, int]] = []

    def fake_conditional(history: object, target_index: int) -> batch.TicketPortfolio:
        calls.append((history, target_index))
        return _SOURCE_TICKETS

    monkeypatch.setattr(
        conditional_batch,
        "produce_b649_conditional_cooccurrence_ranked_pool_v1",
        fake_conditional,
    )
    result = batch.produce_source_ticket_universe(_DIFFUSE_HISTORY, 751)
    assert result == _SOURCE_TICKETS
    assert calls == [(_DIFFUSE_HISTORY, 751)]
    assert calls[0][0] is _DIFFUSE_HISTORY


def test_selected_source_has_exactly_210_legal_unique_tickets() -> None:
    for history in (_CONCENTRATED_HISTORY, _DIFFUSE_HISTORY):
        source = batch.produce_source_ticket_universe(history, 751)
        assert len(source) == 210
        assert len(set(source)) == 210
        assert all(
            len(ticket) == 6
            and ticket == tuple(sorted(ticket))
            and len(set(ticket)) == 6
            and all(type(number) is int and 1 <= number <= 49 for number in ticket)
            for ticket in source
        )


def test_candidate_authority_has_exactly_nine_unique_regime_identities() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert all(candidate_id.startswith("BMSGV1_RS_") for candidate_id in batch.CANDIDATE_IDS)
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


def test_candidate_semantics_include_the_frozen_regime_contract() -> None:
    required_fields = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "REGIME_DETECTOR_ID",
        "REGIME_WINDOWS",
        "COLLISION_FORMULA",
        "REFERENCE_COLLISION_RULE",
        "REGIME_CLASSIFICATION_RULE",
        "REGIME_TIE_RULE",
        "LOW_ENTROPY_SOURCE_ID",
        "HIGH_ENTROPY_SOURCE_ID",
        "SOURCE_SELECTION_RULE",
        "TOP_NUMBER_COUNT",
        "SOURCE_CANDIDATE_TICKET_COUNT",
        "CONSTRUCTOR_ID",
        "CONSTRUCTOR_VERSION",
        "TICKET_COUNT",
        "NATIVE_TICKET_COUNT",
        "OUTPUT_SHAPE",
        "CAUSAL_CUTOFF_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "EXPECTED_IMPROVEMENT_CHANNEL",
    }
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required_fields <= set(semantics)
        assert semantics["HYPOTHESIS_VERSION"] == "V1"
        assert semantics["SOURCE_UNIVERSE_ID"] == batch.SOURCE_UNIVERSE_ID
        assert semantics["SOURCE_UNIVERSE_VERSION"] == "v1"
        assert semantics["REGIME_DETECTOR_ID"] == batch.REGIME_DETECTOR_ID
        assert semantics["REGIME_WINDOWS"] == (50, 300, 750)
        assert semantics["LOW_ENTROPY_SOURCE_ID"] == batch.LOW_ENTROPY_SOURCE_ID
        assert semantics["HIGH_ENTROPY_SOURCE_ID"] == batch.HIGH_ENTROPY_SOURCE_ID
        assert semantics["TOP_NUMBER_COUNT"] == 10
        assert semantics["SOURCE_CANDIDATE_TICKET_COUNT"] == 210
        assert semantics["TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["NATIVE_TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["MINIMUM_HISTORY"] == 751
        assert semantics["OUTPUT_SHAPE"] == "PORTFOLIO"
        assert semantics["CAUSAL_CUTOFF_RULE"] == (
            "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
        )
        assert semantics["PARAMETER_SELECTION_RULE"] == (
            "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
        )
        assert semantics["DETERMINISM_CLASS"] == "PURE_DETERMINISTIC_NO_RNG"
        assert semantics["RNG_SEMANTICS"] == "NONE"
        assert semantics["RNG_SEED"] is None
        assert semantics["EXPECTED_IMPROVEMENT_CHANNEL"] == (
            "STATE_CONDITIONED_SOURCE_SELECTION_BY_RENYI2_REGIME"
        )


def test_candidate_identity_hashes_regenerate_deterministically() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert batch.candidate_id_for_semantics(metadata.SEMANTICS) == metadata.CANDIDATE_ID


def test_candidate_identities_do_not_collide_with_either_predecessor_batch() -> None:
    assert set(batch.CANDIDATE_IDS).isdisjoint(frequency_batch.CANDIDATE_IDS)
    assert set(batch.CANDIDATE_IDS).isdisjoint(conditional_batch.CANDIDATE_IDS)
    assert set(batch.CANDIDATE_SIGNATURE_HASHES).isdisjoint(
        frequency_batch.CANDIDATE_SIGNATURE_HASHES
    )
    assert set(batch.CANDIDATE_SIGNATURE_HASHES).isdisjoint(
        conditional_batch.CANDIDATE_SIGNATURE_HASHES
    )


def test_canonical_semantic_json_is_sorted_compact_utf8_with_nulls() -> None:
    assert batch.canonicalize_semantic_record({"b": None, "a": (1, 2)}) == (
        b'{"a":[1,2],"b":null}'
    )


def test_all_portfolios_have_native_budget_legal_distinct_tickets() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        portfolio = batch.produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _CONCENTRATED_HISTORY, 751
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
        first = batch.produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _DIFFUSE_HISTORY, 751
        )
        second = batch.produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
            metadata.CANDIDATE_ID, _DIFFUSE_HISTORY, 751
        )
        assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        ticket_count: batch.produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
            batch.candidate_id_for(constructor_id, ticket_count), _CONCENTRATED_HISTORY, 751
        )
        for ticket_count in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_frozen_constructor_module_is_invoked_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, int]] = []

    def fake_constructor(candidate_tickets: object, ticket_count: int) -> batch.TicketPortfolio:
        calls.append((candidate_tickets, ticket_count))
        ordered = cast(tuple[batch.Ticket, ...], candidate_tickets)
        return ordered[:ticket_count]

    def fake_source(
        history: batch.HistoryInput, target_index: int
    ) -> batch.TicketPortfolio:
        return _SOURCE_TICKETS

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({batch.CONSTRUCTOR_IDS[0]: fake_constructor}),
    )
    candidate_id = batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5)
    result = batch.produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
        candidate_id, _CONCENTRATED_HISTORY, 751
    )
    assert result == _SOURCE_TICKETS[:5]
    assert calls == [(_SOURCE_TICKETS, 5)]


def test_source_and_constructor_algorithm_bodies_are_not_copied() -> None:
    source = inspect.getsource(batch)
    assert "_frequency_source.produce_b649_multiscale_frequency_ranked_pool_v1" in source
    assert "_conditional_source.produce_b649_conditional_cooccurrence_ranked_pool_v1" in source
    assert "_constructors.CONSTRUCTORS" in source
    assert "_select_low_overlap" not in source
    assert "_select_exposure_balanced" not in source
    assert "_select_hybrid_diversity" not in source
    assert "combinations(" not in source


def test_no_catalog_external_runtime_registration_or_rng_is_imported() -> None:
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
    assert "random." not in source


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
        assert len(producer(_CONCENTRATED_HISTORY, 751)) == metadata.TICKET_COUNT


def test_constructor_reference_is_the_frozen_constructor_module() -> None:
    assert batch.__dict__["_constructors"] is constructors
    assert batch.__dict__["_frequency_source"] is frequency_batch
    assert batch.__dict__["_conditional_source"] is conditional_batch
