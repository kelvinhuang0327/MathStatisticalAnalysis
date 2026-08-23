"""Causal Rényi-2 regime-switched BigLotto candidate batch R1.

This module classifies the strictly prior number-distribution state with an
exact collision concentration rule, delegates the selected source universe
to one of the two frozen predecessor producers, and delegates portfolio
construction to the frozen constructor families.  It has no outcome access,
fitted parameters, randomness, I/O, or production catalog registration.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _conditional_source,
)
from lottolab.research import biglotto_multi_ticket_candidate_batch_r1 as _frequency_source
from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "REGIME_STATE"
FUSION: Final[str] = "STATE_CONDITIONED"
STRATEGY_COMBINATION: Final[str] = "REGIME_SWITCHED"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
REGIME_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
WINDOWS: Final[tuple[int, int, int]] = REGIME_WINDOWS
MINIMUM_HISTORY: Final[int] = 751
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
RNG_SEMANTICS: Final[str] = "NONE"
SOURCE_TICKET_ORDER: Final[str] = (
    "DELEGATED_SELECTED_SOURCE_PRESERVES_FROZEN_ORDER"
)

REGIME_DETECTOR_ID: Final[str] = "B649_RENYI2_COLLISION_STATE_V1"
RECENT_CONCENTRATED_LOW_RENYI2: Final[str] = (
    "RECENT_CONCENTRATED_LOW_RENYI2"
)
RECENT_DIFFUSE_HIGH_RENYI2: Final[str] = "RECENT_DIFFUSE_HIGH_RENYI2"
LOW_ENTROPY_SOURCE_ID: Final[str] = "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1"
HIGH_ENTROPY_SOURCE_ID: Final[str] = (
    "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1"
)
COLLISION_FORMULA: Final[str] = (
    "COLLISION_W=SUM_n(COUNT_W(n)^2/TOTAL_SLOTS_W^2);"
    "TOTAL_SLOTS_W=6*W;EXACT_RATIONAL"
)
REFERENCE_COLLISION_RULE: Final[str] = (
    "REFERENCE_COLLISION=(COLLISION_300+COLLISION_750)/2"
)
REGIME_CLASSIFICATION_RULE: Final[str] = (
    "COLLISION_50>REFERENCE_COLLISION=>RECENT_CONCENTRATED_LOW_RENYI2;"
    "OTHERWISE=>RECENT_DIFFUSE_HIGH_RENYI2"
)
REGIME_TIE_RULE: Final[str] = (
    "COLLISION_50==REFERENCE_COLLISION=>RECENT_DIFFUSE_HIGH_RENYI2"
)
SOURCE_SELECTION_RULE: Final[str] = (
    "RECENT_CONCENTRATED_LOW_RENYI2=>B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1;"
    "RECENT_DIFFUSE_HIGH_RENYI2=>B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1"
)
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "STATE_CONDITIONED_SOURCE_SELECTION_BY_RENYI2_REGIME"
)

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


InsufficientHistoryError = _conditional_source.InsufficientHistoryError


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable metadata for the state-conditioned source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    FUSION: str
    STRATEGY_COMBINATION: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    REGIME_WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    TOP_NUMBER_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    RNG_SEMANTICS: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    METHOD_FAMILY=METHOD_FAMILY,
    FUSION=FUSION,
    STRATEGY_COMBINATION=STRATEGY_COMBINATION,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    HISTORY_ORDER=HISTORY_ORDER,
    REGIME_WINDOWS=REGIME_WINDOWS,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    RNG_SEMANTICS=RNG_SEMANTICS,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "METHOD_FAMILY": METHOD_FAMILY,
        "FUSION": FUSION,
        "STRATEGY_COMBINATION": STRATEGY_COMBINATION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "PICK_COUNT": PICK_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "HISTORY_ORDER": HISTORY_ORDER,
        "REGIME_WINDOWS": REGIME_WINDOWS,
        "WINDOWS": REGIME_WINDOWS,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "COLLISION_FORMULA": COLLISION_FORMULA,
        "REFERENCE_COLLISION_RULE": REFERENCE_COLLISION_RULE,
        "REGIME_CLASSIFICATION_RULE": REGIME_CLASSIFICATION_RULE,
        "REGIME_TIE_RULE": REGIME_TIE_RULE,
        "LOW_ENTROPY_SOURCE_ID": LOW_ENTROPY_SOURCE_ID,
        "HIGH_ENTROPY_SOURCE_ID": HIGH_ENTROPY_SOURCE_ID,
        "SOURCE_SELECTION_RULE": SOURCE_SELECTION_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "RNG_SEMANTICS": RNG_SEMANTICS,
    }
)


@dataclass(frozen=True, slots=True)
class RegimeState:
    """Exact collision values and the frozen source-selection decision."""

    COLLISION_50: Fraction
    COLLISION_300: Fraction
    COLLISION_750: Fraction
    REFERENCE_COLLISION: Fraction
    REGIME: str
    SELECTED_SOURCE: str

    @property
    def SELECTED_SOURCE_ID(self) -> str:
        """Return the selected source identity using an explicit ID alias."""

        return self.SELECTED_SOURCE


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Delegate the shared 751-draw history contract to a frozen predecessor."""

    return _conditional_source.validate_prior_history(history, target_index)


def _collision_for_validated_history(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> Fraction:
    if type(window) is not int or window not in REGIME_WINDOWS:
        raise ValueError(f"window must be one of {REGIME_WINDOWS}")
    if len(prior_history) < window:
        raise InsufficientHistoryError(
            f"window {window} requires at least {window} prior draws"
        )

    counts = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for draw in prior_history[-window:]:
        for number in draw:
            counts[number - NUMBER_DOMAIN[0]] += 1

    total_slots = PICK_COUNT * window
    denominator = total_slots * total_slots
    return sum(
        (Fraction(count * count, denominator) for count in counts),
        Fraction(0, 1),
    )


def calculate_collision_concentration(
    history: HistoryInput, target_index: int, window: int
) -> Fraction:
    """Calculate exact collision concentration for one strictly prior window."""

    prior_history = validate_prior_history(history, target_index)
    return _collision_for_validated_history(prior_history, window)


def collision_concentration_for_window(
    history: HistoryInput, target_index: int, window: int
) -> Fraction:
    """Named alias for one-window exact collision concentration."""

    return calculate_collision_concentration(history, target_index, window)


def calculate_collision_concentrations(
    history: HistoryInput, target_index: int
) -> tuple[Fraction, Fraction, Fraction]:
    """Calculate exact C50, C300, and C750 from one validated prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    concentrations = tuple(
        _collision_for_validated_history(prior_history, window)
        for window in REGIME_WINDOWS
    )
    return cast(tuple[Fraction, Fraction, Fraction], concentrations)


calculate_window_collisions = calculate_collision_concentrations


def calculate_reference_collision(
    collision_300: Fraction, collision_750: Fraction
) -> Fraction:
    """Calculate the exact equal mean of C300 and C750."""

    return (Fraction(collision_300) + Fraction(collision_750)) / 2


def classify_regime(collision_50: Fraction, reference_collision: Fraction) -> str:
    """Apply the strict concentrated rule and diffuse equality tie rule."""

    if Fraction(collision_50) > Fraction(reference_collision):
        return RECENT_CONCENTRATED_LOW_RENYI2
    return RECENT_DIFFUSE_HIGH_RENYI2


classify_renyi2_regime = classify_regime


def selected_source_for_regime(regime: str) -> str:
    """Return the frozen source identity for one validated regime label."""

    if regime == RECENT_CONCENTRATED_LOW_RENYI2:
        return LOW_ENTROPY_SOURCE_ID
    if regime == RECENT_DIFFUSE_HIGH_RENYI2:
        return HIGH_ENTROPY_SOURCE_ID
    raise ValueError(f"unsupported Rényi-2 regime: {regime!r}")


def calculate_regime_state(history: HistoryInput, target_index: int) -> RegimeState:
    """Classify the current strictly-prior distribution state exactly."""

    collision_50, collision_300, collision_750 = calculate_collision_concentrations(
        history, target_index
    )
    reference_collision = calculate_reference_collision(collision_300, collision_750)
    regime = classify_regime(collision_50, reference_collision)
    return RegimeState(
        COLLISION_50=collision_50,
        COLLISION_300=collision_300,
        COLLISION_750=collision_750,
        REFERENCE_COLLISION=reference_collision,
        REGIME=regime,
        SELECTED_SOURCE=selected_source_for_regime(regime),
    )


detect_regime_state = calculate_regime_state
calculate_collision_state = calculate_regime_state


def _prepare_history_for_delegation(history: HistoryInput) -> HistoryInput:
    """Preserve sequences and materialize one-shot iterables once."""

    if isinstance(history, Sequence):
        return history
    return tuple(history)


def _validate_source_ticket_universe(raw_source: object) -> TicketPortfolio:
    if not isinstance(raw_source, tuple):
        raise ValueError("selected source must return an ordered tuple of tickets")

    raw_tickets = cast(tuple[object, ...], raw_source)
    if len(raw_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise ValueError(
            "selected source must return exactly "
            f"{SOURCE_CANDIDATE_TICKET_COUNT} tickets"
        )

    tickets: list[Ticket] = []
    seen: set[Ticket] = set()
    for ticket_index, raw_ticket in enumerate(raw_tickets):
        if not isinstance(raw_ticket, tuple):
            raise ValueError(f"source ticket {ticket_index} must be a tuple")
        raw_numbers = cast(tuple[object, ...], raw_ticket)
        if len(raw_numbers) != PICK_COUNT:
            raise ValueError(f"source ticket {ticket_index} must contain six numbers")

        numbers: list[int] = []
        for number_index, raw_number in enumerate(raw_numbers):
            if type(raw_number) is not int:
                raise ValueError(
                    f"source ticket {ticket_index}[{number_index}] must be an integer"
                )
            if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
                raise ValueError(
                    f"source ticket {ticket_index}[{number_index}] must be in 1..49"
                )
            numbers.append(raw_number)

        if numbers != sorted(numbers) or len(set(numbers)) != PICK_COUNT:
            raise ValueError(
                f"source ticket {ticket_index} must be strictly ascending and unique"
            )
        ticket = cast(Ticket, tuple(numbers))
        if ticket in seen:
            raise ValueError(f"selected source returned duplicate ticket {ticket!r}")
        seen.add(ticket)
        tickets.append(ticket)

    return tuple(tickets)


def produce_b649_renyi2_regime_switched_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the selected frozen 210-ticket source universe."""

    delegated_history = _prepare_history_for_delegation(history)
    state = calculate_regime_state(delegated_history, target_index)
    if state.SELECTED_SOURCE == LOW_ENTROPY_SOURCE_ID:
        source_tickets = _frequency_source.produce_b649_multiscale_frequency_ranked_pool_v1(
            delegated_history, target_index
        )
    elif state.SELECTED_SOURCE == HIGH_ENTROPY_SOURCE_ID:
        source_tickets = (
            _conditional_source.produce_b649_conditional_cooccurrence_ranked_pool_v1(
                delegated_history, target_index
            )
        )
    else:
        raise RuntimeError("regime selected an unsupported source identity")
    return _validate_source_ticket_universe(source_tickets)


produce_source_ticket_universe = produce_b649_renyi2_regime_switched_ranked_pool_v1
build_source_ticket_universe = produce_b649_renyi2_regime_switched_ranked_pool_v1


def canonicalize_semantic_record(record: object) -> bytes:
    """Reuse the predecessor's canonical sorted-key compact JSON contract."""

    return _frequency_source.canonicalize_semantic_record(record)


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    """Return canonical semantic JSON using the frozen predecessor contract."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the regime-switched candidate ID from complete semantics."""

    return f"BMSGV1_RS_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one semantic record."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive the candidate ID and complete signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_RS_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one frozen research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_renyi2_regime_switched_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COLLISION_FORMULA": COLLISION_FORMULA,
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "HIGH_ENTROPY_SOURCE_ID": HIGH_ENTROPY_SOURCE_ID,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "LOW_ENTROPY_SOURCE_ID": LOW_ENTROPY_SOURCE_ID,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PICK_COUNT": PICK_COUNT,
        "REFERENCE_COLLISION_RULE": REFERENCE_COLLISION_RULE,
        "REGIME_CLASSIFICATION_RULE": REGIME_CLASSIFICATION_RULE,
        "REGIME_DETECTOR_ID": REGIME_DETECTOR_ID,
        "REGIME_TIE_RULE": REGIME_TIE_RULE,
        "REGIME_WINDOWS": REGIME_WINDOWS,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_SELECTION_RULE": SOURCE_SELECTION_RULE,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
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
                raise RuntimeError("candidate ID collision in frozen hypothesis matrix")
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

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != expected_count:
        raise RuntimeError("candidate signature collision in frozen hypothesis matrix")
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


def produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen portfolio from the selected strictly prior source."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_multi_ticket_candidate = (
    produce_biglotto_renyi2_regime_switched_multi_ticket_candidate
)
produce_multi_ticket_candidate = (
    produce_biglotto_renyi2_regime_switched_multi_ticket_candidate
)
produce_candidate_portfolio = (
    produce_biglotto_renyi2_regime_switched_multi_ticket_candidate
)


def _produce_named_candidate(
    constructor_id: str,
    ticket_count: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    return produce_biglotto_renyi2_regime_switched_multi_ticket_candidate(
        candidate_id_for(constructor_id, ticket_count), history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 10, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 20, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 5, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 10, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 20, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 5, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 10, history, target_index
    )


def produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 20, history, target_index
    )


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "COLLISION_FORMULA",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FUSION",
    "HIGH_ENTROPY_SOURCE_ID",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "INSUFFICIENT_HISTORY_ERROR",
    "LOTTERY_TYPE",
    "LOW_ENTROPY_SOURCE_ID",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PICK_COUNT",
    "RECENT_CONCENTRATED_LOW_RENYI2",
    "RECENT_DIFFUSE_HIGH_RENYI2",
    "REFERENCE_COLLISION_RULE",
    "REGIME_CLASSIFICATION_RULE",
    "REGIME_DETECTOR_ID",
    "REGIME_TIE_RULE",
    "REGIME_WINDOWS",
    "RNG_SEMANTICS",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_SELECTION_RULE",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "STRATEGY_COMBINATION",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOWS",
    "CandidateIdentity",
    "CandidateMetadata",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "RegimeState",
    "SourceUniverseMetadata",
    "Ticket",
    "TicketPortfolio",
    "build_source_ticket_universe",
    "calculate_collision_concentration",
    "calculate_collision_concentrations",
    "calculate_collision_state",
    "calculate_reference_collision",
    "calculate_regime_state",
    "calculate_window_collisions",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "classify_regime",
    "classify_renyi2_regime",
    "collision_concentration_for_window",
    "derive_candidate_identity",
    "detect_regime_state",
    "produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k5",
    "produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k10",
    "produce_b649_renyi2_regime_switched_multiticket_exposure_balanced_v1_k20",
    "produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_renyi2_regime_switched_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k5",
    "produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k10",
    "produce_b649_renyi2_regime_switched_multiticket_low_overlap_v1_k20",
    "produce_b649_renyi2_regime_switched_ranked_pool_v1",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_renyi2_regime_switched_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "selected_source_for_regime",
    "signature_hash_for_semantics",
    "validate_prior_history",
]


# Keep the public error symbol explicit without importing a second error type.
INSUFFICIENT_HISTORY_ERROR = InsufficientHistoryError
