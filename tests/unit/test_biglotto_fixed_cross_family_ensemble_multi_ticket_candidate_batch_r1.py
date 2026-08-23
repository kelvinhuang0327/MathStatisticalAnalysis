"""Focused tests for the fixed cross-family BigLotto rank ensemble batch."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from fractions import Fraction
from itertools import combinations, islice
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence_batch,
)
from lottolab.research import (
    biglotto_fixed_cross_family_ensemble_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_batch
from lottolab.research import biglotto_multi_ticket_candidate_batch_r1 as frequency_batch
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _draw(index: int, offset: int = 0) -> Ticket:
    values = tuple(((index * 11 + offset + position * 7) % 49) + 1 for position in range(6))
    return cast(Ticket, values)


def _history(length: int = 751) -> tuple[Ticket, ...]:
    return tuple(_draw(index) for index in range(length))


_HISTORY = _history()
_TICKETS = tuple(cast(Ticket, ticket) for ticket in islice(combinations(range(1, 30), 6), 630))


def _parent_fixture() -> dict[str, tuple[Ticket, ...]]:
    return {
        source_id: tuple(_TICKETS[offset : offset + 210])
        for source_id, offset in zip(batch.PARENT_SOURCE_IDS, (0, 3, 6), strict=True)
    }


def _universes_for_rank_vectors(
    vectors: Mapping[Ticket, tuple[int | None, int | None, int | None]],
) -> dict[str, tuple[Ticket, ...]]:
    """Build valid 210-ticket universes with selected tickets at exact ranks."""

    targets = set(vectors)
    result: dict[str, tuple[Ticket, ...]] = {}
    for parent_index, source_id in enumerate(batch.PARENT_SOURCE_IDS):
        slots: list[Ticket | None] = [None] * batch.PARENT_SOURCE_TICKET_COUNT
        present = {
            ticket
            for ticket, ranks in vectors.items()
            if ranks[parent_index] is not None
        }
        for ticket, ranks in vectors.items():
            rank = ranks[parent_index]
            if rank is None:
                continue
            if not 1 <= rank <= batch.PARENT_SOURCE_TICKET_COUNT:
                raise AssertionError("test rank outside frozen parent universe")
            if slots[rank - 1] is not None:
                raise AssertionError("test fixture assigned two tickets to one rank")
            slots[rank - 1] = ticket

        filler = iter(
            ticket
            for ticket in _TICKETS
            if ticket not in targets and ticket not in present
        )
        for position, ticket in enumerate(slots):
            if ticket is None:
                slots[position] = next(filler)
        result[source_id] = cast(tuple[Ticket, ...], tuple(slots))
    return result


def _details_by_ticket(
    ranked: tuple[batch.TicketRankAggregation, ...],
) -> dict[Ticket, batch.TicketRankAggregation]:
    return {item.TICKET: item for item in ranked}


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    values = cast(tuple[int, int, int, int, int, int], ticket)
    if len(values) != 6:
        return False
    return (
        all(type(number) is int and 1 <= number <= 49 for number in values)
        and len(set(values)) == 6
        and tuple(sorted(values)) == values
    )


def test_fewer_than_751_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.produce_source_ticket_universe(_HISTORY[:750], 750)


def test_exactly_751_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 751)) == 210


def test_target_row_is_excluded() -> None:
    history_with_target: tuple[object, ...] = (*_HISTORY, object())
    assert batch.produce_source_ticket_universe(history_with_target, 751) == (
        batch.produce_source_ticket_universe(_HISTORY, 751)
    )


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


def test_all_three_frozen_parent_sources_are_delegated_identical_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    universes = _parent_fixture()
    calls: list[tuple[str, object, int]] = []
    for source_id in batch.PARENT_SOURCE_IDS:
        module = batch.PARENT_SOURCE_MODULES[source_id]
        symbol = batch.PARENT_SOURCE_PRODUCER_SYMBOLS[source_id]

        def fake_producer(
            history: batch.HistoryInput,
            target_index: int,
            *,
            _source_id: str = source_id,
        ) -> batch.SourceUniverse:
            calls.append((_source_id, history, target_index))
            return universes[_source_id]

        monkeypatch.setattr(module, symbol, fake_producer)

    history = list(_HISTORY)
    result = batch.produce_source_ticket_universe(history, 751)
    assert len(result) == batch.ENSEMBLE_SOURCE_TICKET_COUNT
    assert {source_id for source_id, _, _ in calls} == set(batch.PARENT_SOURCE_IDS)
    assert all(call_history is history for _, call_history, _ in calls)
    assert all(target_index == 751 for _, _, target_index in calls)


def test_malformed_parent_universe_fails_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    source_id = batch.PARENT_SOURCE_IDS[0]
    module = batch.PARENT_SOURCE_MODULES[source_id]
    symbol = batch.PARENT_SOURCE_PRODUCER_SYMBOLS[source_id]

    def malformed(_history: batch.HistoryInput, _target_index: int) -> tuple[Ticket, ...]:
        return _TICKETS[:209]

    monkeypatch.setattr(module, symbol, malformed)
    with pytest.raises(ValueError, match="exactly 210 tickets"):
        batch.produce_source_ticket_universe(_HISTORY, 751)


def test_parent_producer_symbols_and_source_ids_are_exactly_frozen() -> None:
    assert tuple(sorted(batch.PARENT_SOURCE_IDS)) == batch.PARENT_SOURCE_IDS
    assert set(batch.PARENT_SOURCE_PRODUCER_SYMBOLS) == set(batch.PARENT_SOURCE_IDS)
    assert batch.PARENT_SOURCE_PRODUCER_SYMBOLS[
        "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1"
    ] == "produce_b649_multiscale_frequency_ranked_pool_v1"
    assert batch.PARENT_SOURCE_PRODUCER_SYMBOLS[
        "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1"
    ] == "produce_b649_conditional_cooccurrence_ranked_pool_v1"
    assert batch.PARENT_SOURCE_PRODUCER_SYMBOLS[
        "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
    ] == "produce_b649_multiscale_graph_pagerank_ranked_pool_v1"


def test_parent_rank_normalization_is_exact() -> None:
    assert batch.normalize_parent_rank(1) == Fraction(1, 1)
    assert batch.normalize_parent_rank(210) == Fraction(1, 210)
    assert batch.normalize_parent_rank(211) == Fraction(0, 1)
    assert all(
        isinstance(batch.normalize_parent_rank(rank), Fraction) for rank in (1, 210, 211)
    )


def test_rank_aggregation_uses_exact_equal_one_third_and_support_count() -> None:
    ticket = _TICKETS[0]
    universes = _universes_for_rank_vectors({ticket: (1, 210, None)})
    details = _details_by_ticket(batch.rank_parent_universes(universes))[ticket]
    assert details.EFFECTIVE_RANKS == (1, 210, 211)
    assert (
        (
        Fraction(1, 1),
        Fraction(1, 210),
        Fraction(0, 1),
        )
        == details.NORMALIZED_PARENT_RANKS
    )
    assert Fraction(211, 630) == details.ENSEMBLE_SCORE
    assert details.SUPPORT_COUNT == 2
    assert details.BEST_EFFECTIVE_RANK == 1
    assert details.MEDIAN_EFFECTIVE_RANK == 210
    assert details.WORST_EFFECTIVE_RANK == 211


def test_ensemble_score_precedes_support_count() -> None:
    high_score = _TICKETS[0]
    lower_score_more_support = _TICKETS[1]
    universes = _universes_for_rank_vectors(
        {
            high_score: (1, None, None),
            lower_score_more_support: (210, 210, 210),
        }
    )
    ranked = batch.rank_parent_universes(universes)
    order = [item.TICKET for item in ranked]
    assert order.index(high_score) < order.index(lower_score_more_support)


def test_support_count_is_the_second_tie_break() -> None:
    support_one = _TICKETS[0]
    support_two = _TICKETS[1]
    universes = _universes_for_rank_vectors(
        {
            support_one: (1, None, None),
            support_two: (106, 106, None),
        }
    )
    details = _details_by_ticket(batch.rank_parent_universes(universes))
    assert details[support_one].ENSEMBLE_SCORE == details[support_two].ENSEMBLE_SCORE
    assert details[support_one].SUPPORT_COUNT == 1
    assert details[support_two].SUPPORT_COUNT == 2
    assert [item.TICKET for item in batch.rank_parent_universes(universes)].index(
        support_two
    ) < [item.TICKET for item in batch.rank_parent_universes(universes)].index(support_one)


def test_robust_effective_rank_tie_breaks_are_worst_then_median() -> None:
    worse_worst = _TICKETS[0]
    better_worst = _TICKETS[1]
    universes = _universes_for_rank_vectors(
        {
            worse_worst: (1, 150, 200),
            better_worst: (50, 200, 101),
        }
    )
    details = _details_by_ticket(batch.rank_parent_universes(universes))
    assert details[worse_worst].ENSEMBLE_SCORE == details[better_worst].ENSEMBLE_SCORE
    assert details[worse_worst].WORST_EFFECTIVE_RANK == details[better_worst].WORST_EFFECTIVE_RANK
    assert details[better_worst].MEDIAN_EFFECTIVE_RANK < details[worse_worst].MEDIAN_EFFECTIVE_RANK
    ranked_tickets = [item.TICKET for item in batch.rank_parent_universes(universes)]
    assert ranked_tickets.index(better_worst) < ranked_tickets.index(worse_worst)


def test_numeric_ticket_tuple_is_the_final_tie_break() -> None:
    first_ticket = _TICKETS[0]
    second_ticket = _TICKETS[1]
    universes = _universes_for_rank_vectors(
        {
            first_ticket: (1, 2, 3),
            second_ticket: (2, 3, 1),
        }
    )
    details = _details_by_ticket(batch.rank_parent_universes(universes))
    assert details[first_ticket].EFFECTIVE_RANKS != details[second_ticket].EFFECTIVE_RANKS
    assert details[first_ticket].ENSEMBLE_SCORE == details[second_ticket].ENSEMBLE_SCORE
    assert (
        details[first_ticket].BEST_EFFECTIVE_RANK,
        details[first_ticket].MEDIAN_EFFECTIVE_RANK,
        details[first_ticket].WORST_EFFECTIVE_RANK,
    ) == (
        details[second_ticket].BEST_EFFECTIVE_RANK,
        details[second_ticket].MEDIAN_EFFECTIVE_RANK,
        details[second_ticket].WORST_EFFECTIVE_RANK,
    )
    ranked_tickets = [item.TICKET for item in batch.rank_parent_universes(universes)]
    assert ranked_tickets.index(first_ticket) < ranked_tickets.index(second_ticket)


def test_parent_argument_order_does_not_change_ensemble_ranking() -> None:
    universes = _parent_fixture()
    reversed_universes = dict(reversed(tuple(universes.items())))
    assert batch.aggregate_parent_universes(universes) == batch.aggregate_parent_universes(
        reversed_universes
    )
    assert batch.rank_parent_universes(universes) == batch.rank_parent_universes(
        reversed_universes
    )


def test_ensemble_is_not_simple_concatenation_or_parent_clone() -> None:
    universes = _parent_fixture()
    result = batch.aggregate_parent_universes(universes)
    assert result != universes[batch.PARENT_SOURCE_IDS[0]]
    assert result != universes[batch.PARENT_SOURCE_IDS[1]]
    assert result != universes[batch.PARENT_SOURCE_IDS[2]]
    assert result != tuple(
        ticket
        for source_id in batch.PARENT_SOURCE_IDS
        for ticket in universes[source_id]
    )[:210]
    assert len(result) == 210
    assert len(set(result)) == 210


def test_ensemble_source_universe_is_legal_unique_and_deterministic() -> None:
    first = batch.produce_source_ticket_universe(_HISTORY, 751)
    second = batch.produce_source_ticket_universe(_HISTORY, 751)
    assert first == second
    assert len(first) == 210
    assert len(set(first)) == 210
    assert all(_legal_ticket(ticket) for ticket in first)


def test_candidate_authority_is_exactly_three_by_three_and_unique() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert isinstance(batch.CANDIDATE_METADATA, MappingProxyType)
    assert {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT)
        for metadata in batch.CANDIDATE_AUTHORITIES
    } == {
        (constructor_id, ticket_count)
        for constructor_id in batch.CONSTRUCTOR_IDS
        for ticket_count in batch.TICKET_COUNTS
    }


def test_candidate_semantics_include_the_complete_frozen_contract() -> None:
    required = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "FUSION",
        "INNER_FUSION",
        "STRATEGY_COMBINATION",
        "PARENT_SOURCE_IDS",
        "PARENT_SOURCE_COUNT",
        "PARENT_SOURCE_TICKET_COUNT",
        "ABSENT_PARENT_RANK",
        "NORMALIZED_PARENT_RANK_RULE",
        "PARENT_WEIGHT_RULE",
        "ENSEMBLE_SCORE_RULE",
        "SUPPORT_COUNT_RULE",
        "ROBUST_EFFECTIVE_RANK_RULE",
        "FINAL_TICKET_RANKING_RULE",
        "ENSEMBLE_SOURCE_TICKET_COUNT",
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
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required <= semantics.keys()
        assert semantics["SOURCE_UNIVERSE_ID"] == batch.SOURCE_UNIVERSE_ID
        assert semantics["PARENT_SOURCE_IDS"] == batch.PARENT_SOURCE_IDS
        assert semantics["PARENT_WEIGHT_RULE"] == "EXACT_EQUAL_ONE_THIRD"
        assert semantics["MINIMUM_HISTORY"] == 751
        assert semantics["NATIVE_TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["RNG_SEED"] is None


def test_candidate_identity_hashes_regenerate_and_use_xf_prefix() -> None:
    for metadata in batch.CANDIDATE_AUTHORITIES:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert batch.candidate_id_for_semantics(metadata.SEMANTICS) == metadata.CANDIDATE_ID
        assert metadata.CANDIDATE_ID.startswith("BMSGV1_XF_")


def test_candidate_identity_does_not_collide_with_four_predecessor_batches() -> None:
    previous_ids = set(frequency_batch.CANDIDATE_IDS)
    previous_ids.update(cooccurrence_batch.CANDIDATE_IDS)
    previous_ids.update(renyi2_batch.CANDIDATE_IDS)
    previous_ids.update(graph_batch.CANDIDATE_IDS)
    previous_hashes = set(frequency_batch.CANDIDATE_SIGNATURE_HASHES)
    previous_hashes.update(cooccurrence_batch.CANDIDATE_SIGNATURE_HASHES)
    previous_hashes.update(renyi2_batch.CANDIDATE_SIGNATURE_HASHES)
    previous_hashes.update(graph_batch.CANDIDATE_SIGNATURE_HASHES)
    assert previous_ids.isdisjoint(batch.CANDIDATE_IDS)
    assert previous_hashes.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


def test_canonical_semantic_json_is_sorted_compact_utf8_with_nulls() -> None:
    assert batch.canonicalize_semantic_record({"b": None, "a": (1, 2)}) == (
        b'{"a":[1,2],"b":null}'
    )
    assert batch.canonicalize_semantic_record({"value": Fraction(1, 2)}) == (
        b'{"value":"1/2"}'
    )


@pytest.mark.parametrize(
    "metadata", batch.CANDIDATE_AUTHORITIES, ids=lambda item: item.CANDIDATE_ID
)
def test_all_candidate_portfolios_are_legal_and_deterministic(
    metadata: batch.CandidateMetadata,
) -> None:
    first = batch.produce_candidate_portfolio(metadata.CANDIDATE_ID, _HISTORY, 751)
    second = batch.produce_candidate_portfolio(metadata.CANDIDATE_ID, _HISTORY, 751)
    assert len(first) == metadata.TICKET_COUNT
    assert len(set(first)) == metadata.TICKET_COUNT
    assert all(_legal_ticket(ticket) for ticket in first)
    assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        count: batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, count), _HISTORY, 751
        )
        for count in batch.TICKET_COUNTS
    }
    assert outputs[5] == outputs[10][:5]
    assert outputs[10] == outputs[20][:10]


def test_frozen_constructor_module_is_invoked_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    source = tuple(tuple(sorted(numbers)) for numbers in combinations(range(1, 11), 6))
    calls: list[tuple[tuple[Ticket, ...], int]] = []

    def fake_constructor(
        candidate_tickets: Iterable[object], ticket_count: int
    ) -> batch.TicketPortfolio:
        ordered = tuple(cast(Iterable[Ticket], candidate_tickets))
        calls.append((ordered, ticket_count))
        return ordered[:ticket_count]

    constructor_id = batch.CONSTRUCTOR_IDS[0]
    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({constructor_id: fake_constructor}),
    )

    def fake_source(_history: batch.HistoryInput, _target_index: int) -> batch.SourceUniverse:
        return cast(batch.SourceUniverse, source)

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(constructor_id, 5), _HISTORY, 751
    )
    assert result == source[:5]
    assert calls == [(cast(tuple[Ticket, ...], source), 5)]


def test_parent_source_algorithms_and_constructors_are_not_copied() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.CONSTRUCTORS" in source
    assert "def _select_low_overlap" not in source
    assert "def _select_exposure_balanced" not in source
    assert "def _select_hybrid_diversity" not in source
    assert "calculate_page_rank" not in source
    assert "build_cooccurrence_edge_counts" not in source
    assert "import random" not in source
    assert "import sqlite" not in source
    assert "import requests" not in source
    assert "import urllib" not in source


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


def test_no_production_catalog_or_external_runtime_registration_is_imported() -> None:
    imported_names = set(batch.__dict__)
    assert not any(name.startswith("lottolab.strategies") for name in imported_names)
    assert not any(
        forbidden in imported_names
        for forbidden in ("random", "socket", "sqlite3", "requests", "datetime", "time", "os")
    )
    assert not Path(batch.__file__).read_text(encoding="utf-8").count("register")
