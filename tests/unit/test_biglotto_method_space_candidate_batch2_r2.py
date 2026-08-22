"""Contract tests for the frozen BigLotto method-space V2 candidate batch R2."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import random
import socket
import sqlite3
import time
from collections.abc import Callable
from datetime import date, timedelta
from hashlib import sha256

import pytest

import lottolab.research.biglotto_method_space_candidate_batch2_r2 as candidate_module
from lottolab.research.biglotto_method_space_candidate_batch2_r2 import (
    CANDIDATE_DEFINITIONS,
    CANDIDATE_PRODUCERS,
    FREQUENCY_ENTROPY_CANDIDATE_ID,
    FREQUENCY_ENTROPY_SIGNATURE_HASH,
    GAP_ENTROPY_CANDIDATE_ID,
    GAP_ENTROPY_SIGNATURE_HASH,
    HYPOTHESIS_VERSION,
    PARENT_FREQUENCY_ENTROPY_ID,
    PARENT_FREQUENCY_ENTROPY_SIGNATURE_HASH,
    PARENT_GAP_ENTROPY_ID,
    PARENT_GAP_ENTROPY_SIGNATURE_HASH,
    SEMANTICS_COMPLETION_TEMPLATE,
    ComponentScoreUnavailable,
    InsufficientCandidateHistory,
    canonical_semantic_json,
    derive_candidate_id,
    derive_signature_hash,
    produce_bmsgv1_v2_43db6a589650e5b9,
    produce_bmsgv1_v2_56c0dd23fb5f07c8,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import production_catalog

TicketPortfolio = tuple[tuple[int, ...], ...]
Producer = Callable[[tuple[CausalDrawRow, ...], str], TicketPortfolio]

_CANDIDATE_CASES: tuple[tuple[str, str, str, str, Producer], ...] = (
    (
        GAP_ENTROPY_CANDIDATE_ID,
        GAP_ENTROPY_SIGNATURE_HASH,
        PARENT_GAP_ENTROPY_ID,
        PARENT_GAP_ENTROPY_SIGNATURE_HASH,
        produce_bmsgv1_v2_56c0dd23fb5f07c8,
    ),
    (
        FREQUENCY_ENTROPY_CANDIDATE_ID,
        FREQUENCY_ENTROPY_SIGNATURE_HASH,
        PARENT_FREQUENCY_ENTROPY_ID,
        PARENT_FREQUENCY_ENTROPY_SIGNATURE_HASH,
        produce_bmsgv1_v2_43db6a589650e5b9,
    ),
)

_BATCH1_IDS = frozenset(
    {
        "BMSGV1_L1_WINDOW_0020015a3ded8fa2",
        "BMSGV1_L1_WINDOW_0cd43605af011f7f",
        "BMSGV1_L1_WINDOW_657395aa27e25467",
    }
)
_BATCH1_SIGNATURES = frozenset(
    {
        "0020015a3ded8fa2fc63abd6a2475d2630b83457c0f392880dbf34d6ffbfc422",
        "0cd43605af011f7fdd6b96bf3b9fdfa5fe0512e22094fd651770e647d8e94633",
        "657395aa27e25467e18a0475a96bf12a881fa55068906d6bb447b623778930ed",
    }
)

_REQUIRED_SEMANTIC_FIELDS = frozenset(
    {
        "HYPOTHESIS_VERSION",
        "PARENT_CANDIDATE_ID",
        "PARENT_SIGNATURE_HASH",
        "METHOD_SPACE_GRAMMAR_VERSION",
        "SEMANTICS_COMPLETION_TEMPLATE",
        "METHOD_FAMILY",
        "FEATURES",
        "WINDOWS",
        "FUSION",
        "FEATURE_NORMALIZATION",
        "FIXED_WEIGHTS",
        "CANDIDATE_CONSTRUCTION",
        "TICKET_CONSTRUCTION",
        "STRATEGY_COMBINATION",
        "MINIMUM_HISTORY",
        "FIXED_PARAMETERS",
        "CAUSAL_CUTOFF_RULE",
        "PARAMETER_SELECTION_RULE",
        "RANKING_RULE",
        "TIE_BREAK_RULE",
        "FALLBACK_RULE",
        "MISSING_FEATURE_RULE",
        "OUTPUT_SHAPE",
        "NATIVE_TICKET_COUNT",
        "DETERMINISM_CLASS",
        "RNG_SOURCE_AND_SEED_SEMANTICS",
        "REQUIRED_DATA",
        "EXPECTED_IMPROVEMENT_CHANNEL",
        "VALIDATION_CONTRACT_REF",
    }
)


def _row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index * 3 + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"synthetic-{index:04d}",
        date=(date(2025, 1, 1) + timedelta(days=index)).isoformat(),
        numbers=numbers,
    )


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index) for index in range(length))


def _complete_scores(value: float) -> dict[int, float]:
    return {number: value for number in range(1, 50)}


def _tied_mapping(_history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    return _complete_scores(1.0)


def _tied_frequency(_history: tuple[CausalDrawRow, ...]) -> tuple[float, ...]:
    return (1.0,) * 49


@pytest.mark.parametrize(
    ("candidate_id", "signature_hash", "_parent_id", "_parent_hash", "_producer"),
    _CANDIDATE_CASES,
)
def test_v2_identity_and_full_signature_are_reproducible(
    candidate_id: str,
    signature_hash: str,
    _parent_id: str,
    _parent_hash: str,
    _producer: Producer,
) -> None:
    definition = CANDIDATE_DEFINITIONS[candidate_id]
    record = definition.semantic_record()

    assert canonical_semantic_json(record) == definition.canonical_semantic_json
    assert sha256(definition.canonical_semantic_json.encode("utf-8")).hexdigest() == signature_hash
    assert derive_signature_hash(record) == signature_hash
    assert derive_candidate_id(record) == candidate_id


@pytest.mark.parametrize(
    ("candidate_id", "signature_hash", "parent_id", "parent_hash", "_producer"),
    _CANDIDATE_CASES,
)
def test_parent_child_lineage_and_semantics_are_complete(
    candidate_id: str,
    signature_hash: str,
    parent_id: str,
    parent_hash: str,
    _producer: Producer,
) -> None:
    definition = CANDIDATE_DEFINITIONS[candidate_id]
    record = definition.semantic_record()

    assert definition.signature_hash == signature_hash
    assert definition.parent_candidate_id == parent_id
    assert definition.parent_signature_hash == parent_hash
    assert candidate_id != parent_id
    assert signature_hash != parent_hash
    assert definition.hypothesis_version == HYPOTHESIS_VERSION == "V2"
    assert definition.semantics_completion_template == SEMANTICS_COMPLETION_TEMPLATE
    assert frozenset(record) == _REQUIRED_SEMANTIC_FIELDS
    assert record["PARENT_CANDIDATE_ID"] == parent_id
    assert record["PARENT_SIGNATURE_HASH"] == parent_hash


@pytest.mark.parametrize(
    ("candidate_id", "signature_hash", "_parent_id", "_parent_hash", "_producer"),
    _CANDIDATE_CASES,
)
def test_batch1_and_live_novelty_guards(
    candidate_id: str,
    signature_hash: str,
    _parent_id: str,
    _parent_hash: str,
    _producer: Producer,
) -> None:
    catalog_ids = {descriptor.strategy_id for descriptor in production_catalog().list()}

    assert candidate_id not in _BATCH1_IDS
    assert signature_hash not in _BATCH1_SIGNATURES
    assert candidate_id not in catalog_ids
    assert candidate_id.startswith("BMSGV1_V2_")


def test_selected_candidate_ids_and_signatures_are_mutually_unique() -> None:
    definitions = tuple(CANDIDATE_DEFINITIONS.values())

    assert len(definitions) == 2
    assert len({definition.candidate_id for definition in definitions}) == len(definitions)
    assert len({definition.signature_hash for definition in definitions}) == len(definitions)
    assert frozenset(CANDIDATE_PRODUCERS) == frozenset(CANDIDATE_DEFINITIONS)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_minimum_history_boundary_accepts_one_strictly_prior_draw(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    portfolio = producer(_history(1), "2025-01-02")

    assert len(portfolio) == 1


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_insufficient_strictly_prior_history_raises_candidate_error(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    with pytest.raises(InsufficientCandidateHistory, match="needs 1 strictly prior draws"):
        producer(_history(1), "2025-01-01")


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_ordinary_chronological_history_produces_one_legal_sorted_ticket(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    portfolio = producer(_history(60), "2025-03-02")

    assert type(portfolio) is tuple
    assert len(portfolio) == 1
    ticket = portfolio[0]
    assert type(ticket) is tuple
    assert len(ticket) == 6
    assert len(set(ticket)) == 6
    assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
    assert ticket == tuple(sorted(ticket))


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_target_cutoff_row_is_strictly_excluded(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    cutoff = "2025-02-20"

    assert producer(_history(50), cutoff) == producer(_history(51), cutoff)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_future_suffix_invariance(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    cutoff = "2025-02-20"

    assert producer(_history(51), cutoff) == producer(_history(80), cutoff)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_repeated_invocation_is_deterministic_and_does_not_mutate_input(
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    history = _history(65)
    snapshot = tuple(
        CausalDrawRow(draw=row.draw, date=row.date, numbers=tuple(row.numbers)) for row in history
    )

    first = producer(history, "2025-03-07")
    second = producer(history, "2025-03-07")

    assert first == second
    assert history == snapshot


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_raw_score_ties_resolve_by_ascending_number(
    monkeypatch: pytest.MonkeyPatch,
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    monkeypatch.setattr(candidate_module, "_entropy_scores", _tied_mapping)
    monkeypatch.setattr(candidate_module, "_gap_pressure_scores", _tied_mapping)
    monkeypatch.setattr(candidate_module, "_historical_frequency", _tied_frequency)

    assert producer(_history(1), "2025-01-02") == ((1, 2, 3, 4, 5, 6),)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_fused_score_ties_use_the_frozen_secondary_order(
    monkeypatch: pytest.MonkeyPatch,
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    increasing = {number: float(number) for number in range(1, 50)}
    decreasing = {number: float(50 - number) for number in range(1, 50)}

    def increasing_mapping(_history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
        return increasing

    def decreasing_mapping(_history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
        return decreasing

    def decreasing_frequency(_history: tuple[CausalDrawRow, ...]) -> tuple[float, ...]:
        return tuple(decreasing[number] for number in range(1, 50))

    monkeypatch.setattr(candidate_module, "_entropy_scores", increasing_mapping)
    monkeypatch.setattr(candidate_module, "_gap_pressure_scores", decreasing_mapping)
    monkeypatch.setattr(candidate_module, "_historical_frequency", decreasing_frequency)

    assert producer(_history(1), "2025-01-02") == ((23, 24, 25, 26, 27, 28),)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_missing_component_scores_fail_without_imputation_or_fallback(
    monkeypatch: pytest.MonkeyPatch,
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    def incomplete_scores(_history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
        return {number: 1.0 for number in range(1, 49)}

    monkeypatch.setattr(candidate_module, "_entropy_scores", incomplete_scores)

    with pytest.raises(ComponentScoreUnavailable, match=r"exactly numbers 1\.\.49"):
        producer(_history(1), "2025-01-02")


def test_candidates_remain_absent_from_production_catalog() -> None:
    catalog_ids = {descriptor.strategy_id for descriptor in production_catalog().list()}

    assert frozenset(CANDIDATE_DEFINITIONS).isdisjoint(catalog_ids)


@pytest.mark.parametrize(
    "_candidate_id, _signature, _parent, _parent_hash, producer",
    _CANDIDATE_CASES,
)
def test_producer_performs_no_file_db_network_clock_environment_or_rng_access(
    monkeypatch: pytest.MonkeyPatch,
    _candidate_id: str,
    _signature: str,
    _parent: str,
    _parent_hash: str,
    producer: Producer,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("forbidden external access")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(time, "time", forbidden)
        patch.setattr(os, "getenv", forbidden)
        patch.setattr(random, "random", forbidden)
        result = producer(_history(10), "2025-01-11")

    assert len(result) == 1
