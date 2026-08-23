"""Causal fixed cross-family BigLotto rank-ensemble candidate batch R1.

This module adds one deterministic hierarchical layer over three already
frozen 210-ticket source universes.  Each parent keeps its own source
semantics and ticket order; this module only validates the common causal
history prefix, aggregates effective ticket ranks with exact rational
arithmetic, and passes the fused ordered pool to the frozen constructors.

The producer has no outcome access, fitted parameters, randomness, I/O, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice, pairwise
from types import MappingProxyType, ModuleType
from typing import Final, cast

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _cooccurrence,
)
from lottolab.research import biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph
from lottolab.research import biglotto_multi_ticket_candidate_batch_r1 as _frequency
from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TicketPortfolio = tuple[Ticket, ...]
type SourceUniverse = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_FIXED_CROSS_FAMILY_TICKET_RANK_ENSEMBLE_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "ENSEMBLE_PORTFOLIO"
FUSION: Final[str] = "HIERARCHICAL"
INNER_FUSION: Final[str] = "RANK_AGGREGATION"
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
STRATEGY_COMBINATION: Final[str] = "FIXED_ENSEMBLE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
MINIMUM_HISTORY: Final[int] = 751

PARENT_SOURCE_IDS: Final[tuple[str, str, str]] = (
    "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1",
    "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1",
)
PARENT_SOURCE_COUNT: Final[int] = 3
PARENT_SOURCE_TICKET_COUNT: Final[int] = 210
ENSEMBLE_SOURCE_TICKET_COUNT: Final[int] = 210
ABSENT_PARENT_RANK: Final[int] = 211
PARENT_WEIGHT_RULE: Final[str] = "EXACT_EQUAL_ONE_THIRD"
NORMALIZED_PARENT_RANK_RULE: Final[str] = "NORMALIZED=(211-RANK)/210;EXACT_RATIONAL"
ENSEMBLE_SCORE_RULE: Final[str] = (
    "ENSEMBLE_SCORE=(NORMALIZED_PARENT_1+NORMALIZED_PARENT_2+NORMALIZED_PARENT_3)"
    "/3;EXACT_RATIONAL"
)
SUPPORT_COUNT_RULE: Final[str] = "COUNT_PARENT_UNIVERSES_CONTAINING_TICKET"
ROBUST_EFFECTIVE_RANK_RULE: Final[str] = (
    "SORTED_ASCENDING=(BEST_EFFECTIVE_RANK,MEDIAN_EFFECTIVE_RANK,WORST_EFFECTIVE_RANK)"
)
FINAL_TICKET_RANKING_RULE: Final[str] = (
    "ENSEMBLE_SCORE_DESC,SUPPORT_COUNT_DESC,WORST_EFFECTIVE_RANK_ASC,"
    "MEDIAN_EFFECTIVE_RANK_ASC,BEST_EFFECTIVE_RANK_ASC,TICKET_NUMERIC_ASC"
)
PARENT_SOURCE_ORDER_RULE: Final[str] = (
    "SOURCE_ID_ASCENDING_FOR_SEMANTICS;AGGREGATION_PARENT_ORDER_INVARIANT"
)
SOURCE_TICKET_ORDER: Final[str] = "FROZEN_PARENT_ORDER_PRESERVED_BEFORE_RANK_AGGREGATION"

CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "CROSS_FAMILY_CONSENSUS_AND_COMPLEMENTARITY"

CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)

_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "NUMBER_EXPOSURE_DIVERSITY",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
            "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
        ),
    }
)

_PARENT_MODULES: Final[Mapping[str, ModuleType]] = MappingProxyType(
    {
        "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1": _cooccurrence,
        "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1": _frequency,
        "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1": _graph,
    }
)
PARENT_SOURCE_MODULES: Final[Mapping[str, ModuleType]] = _PARENT_MODULES
PARENT_SOURCE_PRODUCER_SYMBOLS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1": (
            "produce_b649_conditional_cooccurrence_ranked_pool_v1"
        ),
        "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1": (
            "produce_b649_multiscale_frequency_ranked_pool_v1"
        ),
        "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1": (
            "produce_b649_multiscale_graph_pagerank_ranked_pool_v1"
        ),
    }
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than 751 strictly prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the fixed ensemble source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    FUSION: str
    INNER_FUSION: str
    CANDIDATE_CONSTRUCTION: str
    STRATEGY_COMBINATION: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    MINIMUM_HISTORY: int
    PARENT_SOURCE_IDS: tuple[str, str, str]
    PARENT_SOURCE_COUNT: int
    PARENT_SOURCE_TICKET_COUNT: int
    ENSEMBLE_SOURCE_TICKET_COUNT: int
    ABSENT_PARENT_RANK: int
    PARENT_WEIGHT_RULE: str
    NORMALIZED_PARENT_RANK_RULE: str
    ENSEMBLE_SCORE_RULE: str
    SUPPORT_COUNT_RULE: str
    ROBUST_EFFECTIVE_RANK_RULE: str
    FINAL_TICKET_RANKING_RULE: str
    SOURCE_TICKET_ORDER: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    EXPECTED_IMPROVEMENT_CHANNEL: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    METHOD_FAMILY=METHOD_FAMILY,
    FUSION=FUSION,
    INNER_FUSION=INNER_FUSION,
    CANDIDATE_CONSTRUCTION=CANDIDATE_CONSTRUCTION,
    STRATEGY_COMBINATION=STRATEGY_COMBINATION,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    PARENT_SOURCE_IDS=PARENT_SOURCE_IDS,
    PARENT_SOURCE_COUNT=PARENT_SOURCE_COUNT,
    PARENT_SOURCE_TICKET_COUNT=PARENT_SOURCE_TICKET_COUNT,
    ENSEMBLE_SOURCE_TICKET_COUNT=ENSEMBLE_SOURCE_TICKET_COUNT,
    ABSENT_PARENT_RANK=ABSENT_PARENT_RANK,
    PARENT_WEIGHT_RULE=PARENT_WEIGHT_RULE,
    NORMALIZED_PARENT_RANK_RULE=NORMALIZED_PARENT_RANK_RULE,
    ENSEMBLE_SCORE_RULE=ENSEMBLE_SCORE_RULE,
    SUPPORT_COUNT_RULE=SUPPORT_COUNT_RULE,
    ROBUST_EFFECTIVE_RANK_RULE=ROBUST_EFFECTIVE_RANK_RULE,
    FINAL_TICKET_RANKING_RULE=FINAL_TICKET_RANKING_RULE,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "METHOD_FAMILY": METHOD_FAMILY,
        "FUSION": FUSION,
        "INNER_FUSION": INNER_FUSION,
        "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
        "STRATEGY_COMBINATION": STRATEGY_COMBINATION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "PICK_COUNT": PICK_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "HISTORY_ORDER": HISTORY_ORDER,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "PARENT_SOURCE_IDS": PARENT_SOURCE_IDS,
        "PARENT_SOURCE_COUNT": PARENT_SOURCE_COUNT,
        "PARENT_SOURCE_TICKET_COUNT": PARENT_SOURCE_TICKET_COUNT,
        "ENSEMBLE_SOURCE_TICKET_COUNT": ENSEMBLE_SOURCE_TICKET_COUNT,
        "ABSENT_PARENT_RANK": ABSENT_PARENT_RANK,
        "PARENT_WEIGHT_RULE": PARENT_WEIGHT_RULE,
        "NORMALIZED_PARENT_RANK_RULE": NORMALIZED_PARENT_RANK_RULE,
        "ENSEMBLE_SCORE_RULE": ENSEMBLE_SCORE_RULE,
        "SUPPORT_COUNT_RULE": SUPPORT_COUNT_RULE,
        "ROBUST_EFFECTIVE_RANK_RULE": ROBUST_EFFECTIVE_RANK_RULE,
        "FINAL_TICKET_RANKING_RULE": FINAL_TICKET_RANKING_RULE,
        "PARENT_SOURCE_ORDER_RULE": PARENT_SOURCE_ORDER_RULE,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "PARENT_SOURCE_PRODUCER_SYMBOLS": PARENT_SOURCE_PRODUCER_SYMBOLS,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "PRODUCER_MODULE": (
            "lottolab.research."
            "biglotto_fixed_cross_family_ensemble_multi_ticket_candidate_batch_r1"
        ),
        "PRODUCER_SYMBOL": "produce_b649_fixed_cross_family_ticket_rank_ensemble_v1",
    }
)


@dataclass(frozen=True, slots=True)
class TicketRankAggregation:
    """Exact rank evidence and final tie-break fields for one union ticket."""

    TICKET: Ticket
    EFFECTIVE_RANKS: tuple[int, int, int]
    NORMALIZED_PARENT_RANKS: tuple[Fraction, Fraction, Fraction]
    ENSEMBLE_SCORE: Fraction
    SUPPORT_COUNT: int
    BEST_EFFECTIVE_RANK: int
    MEDIAN_EFFECTIVE_RANK: int
    WORST_EFFECTIVE_RANK: int


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    _validate_target_index(target_index)
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            return tuple(history[:target_index])

        prefix = tuple(islice(iter(history), target_index))
        if len(prefix) != target_index:
            raise ValueError("target_index must not exceed history length")
        return prefix
    except ValueError:
        raise
    except (TypeError, IndexError) as error:
        raise ValueError("history must be a finite chronological sequence of draws") from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(f"history[{draw_index}] must contain exactly six integers") from error

    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers")

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return an immutable validated copy of only the strictly prior history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def _validate_ticket(raw_ticket: object, location: str) -> Ticket:
    if not isinstance(raw_ticket, tuple):
        raise ValueError(f"{location} must be an immutable tuple of six integers")
    values = cast(tuple[object, ...], raw_ticket)
    if len(values) != PICK_COUNT:
        raise ValueError(f"{location} must contain exactly {PICK_COUNT} numbers")

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"{location}[{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"{location}[{position}] must be in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    ticket = cast(Ticket, tuple(numbers))
    if any(left >= right for left, right in pairwise(ticket)):
        raise ValueError(f"{location} must be strictly ascending with no duplicates")
    return ticket


def _validate_parent_universe(
    raw_universe: object, source_id: str, expected_ticket_count: int = PARENT_SOURCE_TICKET_COUNT
) -> SourceUniverse:
    if type(expected_ticket_count) is not int or expected_ticket_count <= 0:
        raise ValueError("expected_ticket_count must be a positive integer")
    try:
        raw_tickets = tuple(cast(Iterable[object], raw_universe))
    except TypeError as error:
        raise ValueError(f"parent {source_id} did not emit an ordered ticket universe") from error

    if len(raw_tickets) != expected_ticket_count:
        raise ValueError(
            f"parent {source_id} must emit exactly {expected_ticket_count} tickets; "
            f"received {len(raw_tickets)}"
        )

    tickets: list[Ticket] = []
    seen: set[Ticket] = set()
    for position, raw_ticket in enumerate(raw_tickets):
        ticket = _validate_ticket(raw_ticket, f"parent {source_id}[{position}]")
        if ticket in seen:
            raise ValueError(f"parent {source_id} emitted duplicate ticket {ticket!r}")
        seen.add(ticket)
        tickets.append(ticket)
    return tuple(tickets)


def _delegated_history(
    history: HistoryInput, prior_history: tuple[HistoryDraw, ...]
) -> HistoryInput:
    """Reuse sequences; cache one-shot iterables without reading their suffix."""

    if isinstance(history, Sequence):
        return history
    return prior_history


def _produce_parent_universes(
    history: HistoryInput, target_index: int, prior_history: tuple[HistoryDraw, ...]
) -> Mapping[str, SourceUniverse]:
    delegated_history = _delegated_history(history, prior_history)
    parent_universes: dict[str, SourceUniverse] = {}
    for source_id in PARENT_SOURCE_IDS:
        module = _PARENT_MODULES[source_id]
        producer_object = getattr(module, PARENT_SOURCE_PRODUCER_SYMBOLS[source_id], None)
        if not callable(producer_object):
            raise RuntimeError(
                f"frozen parent source {source_id} does not expose its required producer"
            )
        producer = cast(Callable[[HistoryInput, int], object], producer_object)
        raw_universe = producer(delegated_history, target_index)
        parent_universes[source_id] = _validate_parent_universe(raw_universe, source_id)
    return MappingProxyType(parent_universes)


def normalize_parent_rank(rank: int) -> Fraction:
    """Normalize one effective parent rank with the frozen exact formula."""

    if type(rank) is not int or not 1 <= rank <= ABSENT_PARENT_RANK:
        raise ValueError(f"rank must be an integer in 1..{ABSENT_PARENT_RANK}")
    return Fraction(ABSENT_PARENT_RANK - rank, PARENT_SOURCE_TICKET_COUNT)


def _ranked_ticket_key(item: TicketRankAggregation) -> tuple[object, ...]:
    return (
        -item.ENSEMBLE_SCORE,
        -item.SUPPORT_COUNT,
        item.WORST_EFFECTIVE_RANK,
        item.MEDIAN_EFFECTIVE_RANK,
        item.BEST_EFFECTIVE_RANK,
        item.TICKET,
    )


def rank_parent_universes(
    parent_universes: Mapping[str, object],
    *,
    expected_ticket_count: int = PARENT_SOURCE_TICKET_COUNT,
) -> tuple[TicketRankAggregation, ...]:
    """Return every union ticket in the frozen exact final ranking order."""

    if set(parent_universes) != set(PARENT_SOURCE_IDS):
        raise ValueError(
            "parent_universes must contain exactly the three frozen parent source IDs"
        )

    validated: dict[str, SourceUniverse] = {}
    for source_id in PARENT_SOURCE_IDS:
        validated[source_id] = _validate_parent_universe(
            parent_universes[source_id], source_id, expected_ticket_count
        )

    union: set[Ticket] = set()
    rank_maps: dict[str, Mapping[Ticket, int]] = {}
    for source_id in PARENT_SOURCE_IDS:
        universe = validated[source_id]
        union.update(universe)
        rank_maps[source_id] = MappingProxyType(
            {ticket: position for position, ticket in enumerate(universe, start=1)}
        )

    if not expected_ticket_count <= len(union) <= expected_ticket_count * PARENT_SOURCE_COUNT:
        raise ValueError(
            "parent ticket union must contain between one and three parent universe sizes"
        )

    ranked: list[TicketRankAggregation] = []
    for ticket in union:
        effective_ranks = cast(
            tuple[int, int, int],
            tuple(
                rank_maps[source_id].get(ticket, ABSENT_PARENT_RANK)
                for source_id in PARENT_SOURCE_IDS
            ),
        )
        normalized_ranks = cast(
            tuple[Fraction, Fraction, Fraction],
            tuple(normalize_parent_rank(rank) for rank in effective_ranks),
        )
        ensemble_score = sum(normalized_ranks, Fraction(0, 1)) / PARENT_SOURCE_COUNT
        robust_ranks = tuple(sorted(effective_ranks))
        best, median, worst = robust_ranks
        ranked.append(
            TicketRankAggregation(
                TICKET=ticket,
                EFFECTIVE_RANKS=effective_ranks,
                NORMALIZED_PARENT_RANKS=normalized_ranks,
                ENSEMBLE_SCORE=ensemble_score,
                SUPPORT_COUNT=sum(rank != ABSENT_PARENT_RANK for rank in effective_ranks),
                BEST_EFFECTIVE_RANK=best,
                MEDIAN_EFFECTIVE_RANK=median,
                WORST_EFFECTIVE_RANK=worst,
            )
        )
    return tuple(sorted(ranked, key=_ranked_ticket_key))


def aggregate_parent_universes(parent_universes: Mapping[str, object]) -> SourceUniverse:
    """Take the frozen top-210 tickets from an exact parent-rank aggregation."""

    ranked = rank_parent_universes(parent_universes)
    if len(ranked) < ENSEMBLE_SOURCE_TICKET_COUNT:
        raise RuntimeError("ranked parent union cannot provide the ensemble top 210 tickets")
    source_universe = tuple(item.TICKET for item in ranked[:ENSEMBLE_SOURCE_TICKET_COUNT])
    if len(source_universe) != ENSEMBLE_SOURCE_TICKET_COUNT:
        raise RuntimeError("ensemble source universe did not contain exactly 210 tickets")
    if len(set(source_universe)) != ENSEMBLE_SOURCE_TICKET_COUNT:
        raise RuntimeError("ensemble source universe contained duplicate tickets")
    return source_universe


def produce_b649_fixed_cross_family_ticket_rank_ensemble_v1(
    history: HistoryInput, target_index: int
) -> SourceUniverse:
    """Produce the ordered 210-ticket fixed cross-family ensemble universe."""

    prior_history = validate_prior_history(history, target_index)
    parent_universes = _produce_parent_universes(history, target_index, prior_history)
    return aggregate_parent_universes(parent_universes)


produce_source_ticket_universe = produce_b649_fixed_cross_family_ticket_rank_ensemble_v1
build_source_ticket_universe = produce_b649_fixed_cross_family_ticket_rank_ensemble_v1


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("semantic-record keys must be strings")
            converted[key] = _json_ready(item)
        return converted
    if isinstance(value, tuple):
        return [_json_ready(item) for item in cast(tuple[object, ...], value)]
    if isinstance(value, list):
        return [_json_ready(item) for item in cast(list[object], value)]
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return value


def canonicalize_semantic_record(record: object) -> bytes:
    """Return sorted-key, compact UTF-8 JSON for a complete semantic record."""

    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    json_ready_record = _json_ready(cast(Mapping[object, object], record))
    return json.dumps(
        json_ready_record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    """Return canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return SHA-256 of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Return the fixed cross-family candidate ID for one semantic record."""

    return f"BMSGV1_XF_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one ensemble hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_XF_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one ensemble research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_fixed_cross_family_ensemble_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(constructor_id: str, ticket_count: int) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "ABSENT_PARENT_RANK": ABSENT_PARENT_RANK,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "ENSEMBLE_SCORE_RULE": ENSEMBLE_SCORE_RULE,
        "ENSEMBLE_SOURCE_TICKET_COUNT": ENSEMBLE_SOURCE_TICKET_COUNT,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FINAL_TICKET_RANKING_RULE": FINAL_TICKET_RANKING_RULE,
        "FUSION": FUSION,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "INNER_FUSION": INNER_FUSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NORMALIZED_PARENT_RANK_RULE": NORMALIZED_PARENT_RANK_RULE,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PARENT_SOURCE_COUNT": PARENT_SOURCE_COUNT,
        "PARENT_SOURCE_IDS": PARENT_SOURCE_IDS,
        "PARENT_SOURCE_ORDER_RULE": PARENT_SOURCE_ORDER_RULE,
        "PARENT_SOURCE_TICKET_COUNT": PARENT_SOURCE_TICKET_COUNT,
        "PARENT_WEIGHT_RULE": PARENT_WEIGHT_RULE,
        "ROBUST_EFFECTIVE_RANK_RULE": ROBUST_EFFECTIVE_RANK_RULE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "RNG_SEED": None,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "STRATEGY_COMBINATION": STRATEGY_COMBINATION,
        "SUPPORT_COUNT_RULE": SUPPORT_COUNT_RULE,
        "TICKET_COUNT": ticket_count,
    }


def _build_candidate_authority() -> tuple[
    tuple[CandidateMetadata, ...],
    Mapping[str, CandidateMetadata],
    Mapping[str, Mapping[str, object]],
    Mapping[tuple[str, int], str],
]:
    authorities: list[CandidateMetadata] = []
    metadata_by_id: dict[str, CandidateMetadata] = {}
    semantics_by_id: dict[str, Mapping[str, object]] = {}
    ids_by_pair: dict[tuple[str, int], str] = {}

    for constructor_id in CONSTRUCTOR_IDS:
        for ticket_count in TICKET_COUNTS:
            semantic_record = _candidate_semantic_record(constructor_id, ticket_count)
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError("candidate ID collision in frozen ensemble hypothesis matrix")
            semantic_proxy: Mapping[str, object] = MappingProxyType(semantic_record)
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(constructor_id, ticket_count),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    if len(authorities) != len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS):
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(authorities):
        raise RuntimeError("candidate signature collision in frozen ensemble hypothesis matrix")
    return (
        tuple(authorities),
        MappingProxyType(metadata_by_id),
        MappingProxyType(semantics_by_id),
        MappingProxyType(ids_by_pair),
    )


(
    CANDIDATE_AUTHORITIES,
    CANDIDATE_METADATA,
    CANDIDATE_SEMANTICS,
    CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT,
) = _build_candidate_authority()
CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = CANDIDATE_METADATA
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[tuple[str, ...]] = tuple(
    metadata.SIGNATURE_HASH for metadata in CANDIDATE_AUTHORITIES
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the frozen candidate ID for one constructor/budget pair."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[(constructor_id, ticket_count)]
    except KeyError as error:
        raise KeyError(
            f"unsupported constructor/budget pair: {constructor_id!r}, {ticket_count!r}"
        ) from error


def _metadata_for_candidate(candidate_id: str) -> CandidateMetadata:
    try:
        return CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate_id: {candidate_id!r}") from error


def produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen ensemble portfolio from strictly prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_multi_ticket_candidate = (
    produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate
)
produce_b649_fixed_cross_family_ensemble_multi_ticket_candidate = (
    produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate
)
produce_fixed_cross_family_ensemble_candidate = (
    produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate
)
produce_multi_ticket_candidate = produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate
produce_candidate_portfolio = produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate


def _produce_named_candidate(
    constructor_id: str, ticket_count: int, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate(
        candidate_id_for(constructor_id, ticket_count), history, target_index
    )


def produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


__all__ = [
    "ABSENT_PARENT_RANK",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_CONSTRUCTION",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "ENSEMBLE_SCORE_RULE",
    "ENSEMBLE_SOURCE_TICKET_COUNT",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FINAL_TICKET_RANKING_RULE",
    "FUSION",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "INNER_FUSION",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NORMALIZED_PARENT_RANK_RULE",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PARENT_SOURCE_COUNT",
    "PARENT_SOURCE_IDS",
    "PARENT_SOURCE_MODULES",
    "PARENT_SOURCE_ORDER_RULE",
    "PARENT_SOURCE_PRODUCER_SYMBOLS",
    "PARENT_SOURCE_TICKET_COUNT",
    "PARENT_WEIGHT_RULE",
    "PICK_COUNT",
    "RNG_SEMANTICS",
    "ROBUST_EFFECTIVE_RANK_RULE",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "STRATEGY_COMBINATION",
    "SUPPORT_COUNT_RULE",
    "TICKET_COUNTS",
    "CandidateIdentity",
    "CandidateMetadata",
    "HistoryInput",
    "InsufficientHistoryError",
    "SourceUniverse",
    "Ticket",
    "TicketPortfolio",
    "TicketRankAggregation",
    "aggregate_parent_universes",
    "build_source_ticket_universe",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "normalize_parent_rank",
    "produce_b649_fixed_cross_family_ensemble_multi_ticket_candidate",
    "produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k5",
    "produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k10",
    "produce_b649_fixed_cross_family_ensemble_multiticket_exposure_balanced_v1_k20",
    "produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_fixed_cross_family_ensemble_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k5",
    "produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k10",
    "produce_b649_fixed_cross_family_ensemble_multiticket_low_overlap_v1_k20",
    "produce_b649_fixed_cross_family_ticket_rank_ensemble_v1",
    "produce_biglotto_fixed_cross_family_ensemble_multi_ticket_candidate",
    "produce_biglotto_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_fixed_cross_family_ensemble_candidate",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_parent_universes",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
