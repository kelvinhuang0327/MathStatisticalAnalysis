"""First bounded BIG_LOTTO method-space candidate batch.

This module contains three offline research producers selected from the
``BIGLOTTO_MSG_V1`` gap ledger.  Each producer is a fixed-window frequency
ranker derived from the explicitly referenced ``MustHitTop6`` source.  The
window is the only changed method-space dimension; minimum history, ranking,
tie handling, and failure behavior remain frozen and explicit here.

The caller supplies chronological ``CausalDrawRow`` values.  When
``target_cutoff`` is supplied, it is the exclusive index of the prediction
target in that supplied sequence, so only the strict prefix before the target
is validated and used.  With no cutoff, the caller contract is that every
supplied row is already strictly prior to the prediction target.

No file, network, database, clock, environment, outcome, replay, or ranking
artifact is consulted by any producer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypedDict

from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    validated_history,
)

LOTTERY_TYPE = "BIG_LOTTO"
METHOD_SPACE_GRAMMAR_VERSION = "BIGLOTTO_MSG_V1"
HYPOTHESIS_VERSION = "BIGLOTTO_MSG_V1_R1"
METHOD_FAMILY = "METHOD_SPACE_GAP_CANDIDATE"
MINIMUM_HISTORY = 50
PICK_COUNT = 6
NUMBER_MIN = 1
NUMBER_MAX = 49

_CANDIDATE_30 = "BMSGV1_L1_WINDOW_0020015a3ded8fa2"
_CANDIDATE_20 = "BMSGV1_L1_WINDOW_0cd43605af011f7f"
_CANDIDATE_750 = "BMSGV1_L1_WINDOW_657395aa27e25467"


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    """Frozen authority and implementation semantics for one candidate."""

    candidate_id: str
    hypothesis_version: str
    signature_hash: str
    method_space_grammar_version: str
    method_family: str
    features: str
    windows: str
    window: int
    fusion: str
    candidate_construction: str
    ticket_construction: str
    strategy_combination: str
    minimum_history: int
    fixed_parameters: str
    causal_cutoff_rule: str
    parameter_selection_rule: str
    ranking_rule: str
    tie_break_rule: str
    fallback_rule: str
    output_shape: str
    native_ticket_count: int
    determinism_class: str
    rng_source_and_seed_semantics: str
    required_data: str
    expected_improvement_channel: str
    validation_contract_ref: str


class _CommonSemantics(TypedDict):
    hypothesis_version: str
    method_space_grammar_version: str
    method_family: str
    features: str
    fusion: str
    candidate_construction: str
    ticket_construction: str
    strategy_combination: str
    minimum_history: int
    causal_cutoff_rule: str
    parameter_selection_rule: str
    ranking_rule: str
    tie_break_rule: str
    fallback_rule: str
    output_shape: str
    native_ticket_count: int
    determinism_class: str
    rng_source_and_seed_semantics: str
    required_data: str
    expected_improvement_channel: str
    validation_contract_ref: str


_COMMON_SEMANTICS: _CommonSemantics = {
    "hypothesis_version": HYPOTHESIS_VERSION,
    "method_space_grammar_version": METHOD_SPACE_GRAMMAR_VERSION,
    "method_family": METHOD_FAMILY,
    "features": "FREQUENCY",
    "fusion": "SINGLE",
    "candidate_construction": "RANKED_POOL",
    "ticket_construction": "SINGLE_TICKET",
    "strategy_combination": "SINGLE_STRATEGY",
    "minimum_history": MINIMUM_HISTORY,
    "causal_cutoff_rule": (
        "USE_ONLY_DRAWS_STRICTLY_BEFORE_TARGET_CUTOFF;"
        "TARGET_ROW_EXCLUDED_FROM_FEATURES_AND_SELECTION"
    ),
    "parameter_selection_rule": "FIXED_PREREGISTERED_PARAMETERS;NO_TARGET_ROW_ACCESS",
    "ranking_rule": "DESCENDING_FREQUENCY_OVER_TRAILING_WINDOW",
    "tie_break_rule": (
        "EARLIEST_FIRST_APPEARANCE_IN_CHRONOLOGICAL_WINDOW;"
        "THEN_ASCENDING_NUMBER"
    ),
    "fallback_rule": "RAISE_INSUFFICIENT_HISTORY_BELOW_50;NO_NUMBER_PADDING",
    "output_shape": "SINGLE_TICKET",
    "native_ticket_count": 1,
    "determinism_class": "PURE_DETERMINISTIC_NO_RNG",
    "rng_source_and_seed_semantics": "NONE;NO_RANDOM_VALUES_CONSUMED",
    "required_data": "BIG_LOTTO_PRIMARY_DRAW_HISTORY|DERIVED_FEATURES_FROM_CAUSAL_HISTORY",
    "expected_improvement_channel": "RECENCY_OR_FREQUENCY_SIGNAL",
    "validation_contract_ref": "BIGLOTTO_MSG_V1_CAUSAL_TRAIN_VALIDATE_R1",
}


CANDIDATE_SPECS: Mapping[str, CandidateSpec] = MappingProxyType(
    {
        _CANDIDATE_30: CandidateSpec(
            candidate_id=_CANDIDATE_30,
            signature_hash="0020015a3ded8fa2fc63abd6a2475d2630b83457c0f392880dbf34d6ffbfc422",
            windows="30",
            window=30,
            fixed_parameters=(
                "window=30;pick_count=6;number_domain=1..49;"
                "minimum_history=50;ticket_order=ASCENDING_NUMERIC"
            ),
            **_COMMON_SEMANTICS,
        ),
        _CANDIDATE_20: CandidateSpec(
            candidate_id=_CANDIDATE_20,
            signature_hash="0cd43605af011f7fdd6b96bf3b9fdfa5fe0512e22094fd651770e647d8e94633",
            windows="20",
            window=20,
            fixed_parameters=(
                "window=20;pick_count=6;number_domain=1..49;"
                "minimum_history=50;ticket_order=ASCENDING_NUMERIC"
            ),
            **_COMMON_SEMANTICS,
        ),
        _CANDIDATE_750: CandidateSpec(
            candidate_id=_CANDIDATE_750,
            signature_hash="657395aa27e25467e18a0475a96bf12a881fa55068906d6bb447b623778930ed",
            windows="750",
            window=750,
            fixed_parameters=(
                "window=750;pick_count=6;number_domain=1..49;"
                "minimum_history=50;ticket_order=ASCENDING_NUMERIC"
            ),
            **_COMMON_SEMANTICS,
        ),
    }
)


def candidate_spec(candidate_id: str) -> CandidateSpec:
    """Return the frozen metadata for one selected candidate."""

    try:
        return CANDIDATE_SPECS[candidate_id]
    except KeyError as exc:
        raise KeyError(f"unknown BIG_LOTTO candidate: {candidate_id}") from exc


def _causal_history(
    candidate_id: str,
    history: Sequence[CausalDrawRow],
    target_cutoff: int | None,
) -> tuple[CausalDrawRow, ...]:
    """Copy and validate only the strict pre-target history prefix."""

    try:
        supplied = tuple(history)
    except TypeError as exc:
        raise InvalidOutput(f"{candidate_id}: history must be iterable") from exc

    if target_cutoff is None:
        prefix = supplied
    else:
        if type(target_cutoff) is not int:
            raise InvalidOutput(f"{candidate_id}: target_cutoff must be an integer index")
        if not 0 <= target_cutoff <= len(supplied):
            raise InvalidOutput(
                f"{candidate_id}: target_cutoff must lie in [0, {len(supplied)}]"
            )
        prefix = supplied[:target_cutoff]

    canonical = validated_history(prefix, candidate_id)
    draw_ids = tuple(row.draw for row in canonical)
    if len(draw_ids) != len(set(draw_ids)):
        raise InvalidOutput(f"{candidate_id}: causal draw identities must be unique")
    return canonical


def _ranked_frequency_ticket(
    candidate_id: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    """Apply the nearest-method frequency ranker with explicit tie ordering."""

    spec = candidate_spec(candidate_id)
    recent = history[-spec.window:] if len(history) > spec.window else history
    frequencies: Counter[int] = Counter()
    first_seen: dict[int, int] = {}
    encounter_index = 0
    for row in recent:
        for number in row.numbers:
            frequencies[number] += 1
            first_seen.setdefault(number, encounter_index)
            encounter_index += 1

    ranked_numbers = sorted(
        frequencies,
        key=lambda number: (-frequencies[number], first_seen[number], number),
    )
    ticket = tuple(sorted(ranked_numbers[:PICK_COUNT]))
    if len(ticket) != PICK_COUNT or len(set(ticket)) != PICK_COUNT:
        raise InvalidOutput(f"{candidate_id}: frequency ranker did not produce six numbers")
    if any(number < NUMBER_MIN or number > NUMBER_MAX for number in ticket):
        raise InvalidOutput(f"{candidate_id}: frequency ranker produced an illegal number")
    return ticket


def produce_candidate(
    candidate_id: str,
    history: Sequence[CausalDrawRow],
    *,
    target_cutoff: int | None = None,
) -> tuple[int, ...]:
    """Produce one legal BIG_LOTTO ticket for a selected candidate.

    ``target_cutoff`` is an exclusive index into the caller's chronological
    sequence.  Rows at that index and after it are never validated or used.
    Without it, the caller must supply only strictly-prior rows.
    """

    spec = candidate_spec(candidate_id)
    causal_history = _causal_history(candidate_id, history, target_cutoff)
    if len(causal_history) < spec.minimum_history:
        raise InsufficientHistory(
            f"{candidate_id}: needs {spec.minimum_history} causal draws, "
            f"got {len(causal_history)}"
        )
    return _ranked_frequency_ticket(candidate_id, causal_history)


def produce_bmsgv1_l1_window_0020015a3ded8fa2(
    history: Sequence[CausalDrawRow], *, target_cutoff: int | None = None
) -> tuple[int, ...]:
    """Produce candidate BMSGV1_L1_WINDOW_0020015a3ded8fa2."""

    return produce_candidate(_CANDIDATE_30, history, target_cutoff=target_cutoff)


def produce_bmsgv1_l1_window_0cd43605af011f7f(
    history: Sequence[CausalDrawRow], *, target_cutoff: int | None = None
) -> tuple[int, ...]:
    """Produce candidate BMSGV1_L1_WINDOW_0cd43605af011f7f."""

    return produce_candidate(_CANDIDATE_20, history, target_cutoff=target_cutoff)


def produce_bmsgv1_l1_window_657395aa27e25467(
    history: Sequence[CausalDrawRow], *, target_cutoff: int | None = None
) -> tuple[int, ...]:
    """Produce candidate BMSGV1_L1_WINDOW_657395aa27e25467."""

    return produce_candidate(_CANDIDATE_750, history, target_cutoff=target_cutoff)


SELECTED_CANDIDATE_IDS: tuple[str, ...] = (_CANDIDATE_30, _CANDIDATE_20, _CANDIDATE_750)


__all__ = [
    "CANDIDATE_SPECS",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "METHOD_SPACE_GRAMMAR_VERSION",
    "SELECTED_CANDIDATE_IDS",
    "CandidateSpec",
    "candidate_spec",
    "produce_bmsgv1_l1_window_0cd43605af011f7f",
    "produce_bmsgv1_l1_window_0020015a3ded8fa2",
    "produce_bmsgv1_l1_window_657395aa27e25467",
    "produce_candidate",
]
