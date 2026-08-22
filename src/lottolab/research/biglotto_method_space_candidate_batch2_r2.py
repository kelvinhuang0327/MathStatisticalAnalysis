"""Frozen V2 BigLotto method-space candidates for offline research only.

The two producers in this module complete immutable ``BIGLOTTO_MSG_V1``
Level-2 parents with the preregistered ``PAIRWISE_RANK_MEAN_V1`` template.
They are deliberately absent from the production strategy catalog.  Callers
provide chronological ``CausalDrawRow`` history plus an ISO target cutoff;
the producers retain only rows strictly before that cutoff and perform no
file, database, network, clock, environment, or RNG access.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Final, cast

from lottolab.strategies.adapters.base import CausalDrawRow, validated_history
from lottolab.strategies.adapters.biglotto_batch15 import _gap_pressure_scores
from lottolab.strategies.adapters.biglotto_selected import _historical_frequency
from lottolab.strategies.adapters.biglotto_wave4 import _entropy_scores

_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_NORMALIZED_RANK_DENOMINATOR: Final = 48
_PARENT_WINDOW: Final = 50
_NUMBER_DOMAIN: Final = tuple(range(_MIN_NUMBER, _MAX_NUMBER + 1))
_NUMBER_DOMAIN_SET: Final = frozenset(_NUMBER_DOMAIN)

HYPOTHESIS_VERSION: Final = "V2"
SEMANTICS_COMPLETION_TEMPLATE: Final = "PAIRWISE_RANK_MEAN_V1"

PARENT_GAP_ENTROPY_ID: Final = "BMSGV1_L2_PAIRWISE_2507681ad9ef073c"
PARENT_GAP_ENTROPY_SIGNATURE_HASH: Final = (
    "2507681ad9ef073cffba9e28c284f300a106c005f3380864ea999d24e7e65edf"
)
GAP_ENTROPY_CANDIDATE_ID: Final = "BMSGV1_V2_56c0dd23fb5f07c8"
GAP_ENTROPY_SIGNATURE_HASH: Final = (
    "56c0dd23fb5f07c81c6913f5923b977a183b52f66f6bf0047747f226bf157d5c"
)

PARENT_FREQUENCY_ENTROPY_ID: Final = "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800"
PARENT_FREQUENCY_ENTROPY_SIGNATURE_HASH: Final = (
    "4dc9ff4fd526d8002cb072a2d717ce30286ed2843da3d2b2e6c5230c28f16f72"
)
FREQUENCY_ENTROPY_CANDIDATE_ID: Final = "BMSGV1_V2_43db6a589650e5b9"
FREQUENCY_ENTROPY_SIGNATURE_HASH: Final = (
    "43db6a589650e5b953dd7d4743f1663bb4ac913e4b497a14bf6814be38c73a5e"
)

type Ticket = tuple[int, ...]
type TicketPortfolio = tuple[Ticket, ...]
type SemanticRecord = dict[str, object]
type CandidateProducer = Callable[[tuple[CausalDrawRow, ...], str], TicketPortfolio]


class BigLottoMethodSpaceCandidateError(ValueError):
    """Base class for explicit candidate-domain failures."""


class CandidateInputError(BigLottoMethodSpaceCandidateError):
    """Caller history or target-cutoff input is invalid."""


class InsufficientCandidateHistory(BigLottoMethodSpaceCandidateError):
    """Strictly prior history is below the frozen candidate minimum."""


class ComponentScoreUnavailable(BigLottoMethodSpaceCandidateError):
    """A selected feature failed to emit one finite score for every number."""


class CandidateOutputError(BigLottoMethodSpaceCandidateError):
    """The fused candidate violated its frozen one-ticket output contract."""


@dataclass(frozen=True, slots=True)
class CandidateDefinition:
    """Immutable identity, lineage, and canonical semantic payload."""

    candidate_id: str
    signature_hash: str
    parent_candidate_id: str
    parent_signature_hash: str
    hypothesis_version: str
    semantics_completion_template: str
    minimum_history: int
    implementation_symbol: str
    canonical_semantic_json: str

    def semantic_record(self) -> SemanticRecord:
        """Return a detached reconstruction of the hashed semantic record."""

        value = json.loads(self.canonical_semantic_json)
        if type(value) is not dict:
            raise RuntimeError("candidate semantic JSON must decode to an object")
        return cast(SemanticRecord, value)


_ENTROPY_FEATURE: Final[dict[str, object]] = {
    "FEATURE_ID": "ENTROPY",
    "SOURCE_MODULE": "lottolab.strategies.adapters.biglotto_wave4",
    "SOURCE_SYMBOL": "_entropy_scores",
    "SCORE_DEFINITION": (
        "1 / (abs(trailing_window_frequency - "
        "(observed_window_length * 6 / 49)) + 0.1)"
    ),
    "DESIRABILITY_DIRECTION": "HIGHER_IS_BETTER",
    "WINDOW": _PARENT_WINDOW,
    "MINIMUM_HISTORY": 1,
    "REQUIRED_SCORE_DOMAIN": "EXACT_KEYS_1_TO_49",
    "SOURCE_INPUT_ORDER_ADAPTATION": None,
}

_GAP_OMISSION_FEATURE: Final[dict[str, object]] = {
    "FEATURE_ID": "GAP_OMISSION",
    "SOURCE_MODULE": "lottolab.strategies.adapters.biglotto_batch15",
    "SOURCE_SYMBOL": "_gap_pressure_scores",
    "SCORE_DEFINITION": (
        "2.0_IF_NEVER_SEEN_ELSE_2.0_TIMES_SIGMOID_STEEPNESS_3_OF_"
        "CURRENT_GAP_DIVIDED_BY_AVERAGE_INTERVAL_MINUS_1"
    ),
    "DESIRABILITY_DIRECTION": "HIGHER_IS_BETTER",
    "WINDOW": _PARENT_WINDOW,
    "MINIMUM_HISTORY": 1,
    "REQUIRED_SCORE_DOMAIN": "EXACT_KEYS_1_TO_49",
    "SOURCE_INPUT_ORDER_ADAPTATION": None,
}

_FREQUENCY_FEATURE: Final[dict[str, object]] = {
    "FEATURE_ID": "FREQUENCY",
    "SOURCE_MODULE": "lottolab.strategies.adapters.biglotto_selected",
    "SOURCE_SYMBOL": "_historical_frequency",
    "SCORE_DEFINITION": (
        "trailing_window_appearance_count / total_appearances_in_observed_window"
    ),
    "DESIRABILITY_DIRECTION": "HIGHER_IS_BETTER",
    "WINDOW": _PARENT_WINDOW,
    "MINIMUM_HISTORY": 1,
    "REQUIRED_SCORE_DOMAIN": "EXACT_KEYS_1_TO_49",
    "SOURCE_INPUT_ORDER_ADAPTATION": "REVERSE_CHRONOLOGICAL_WINDOW_TO_NEWEST_FIRST",
}


def canonical_semantic_json(semantic_record: Mapping[str, object]) -> str:
    """Canonical UTF-8 JSON text used for every V2 identity derivation."""

    return json.dumps(
        semantic_record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def derive_signature_hash(semantic_record: Mapping[str, object]) -> str:
    """Derive the full lowercase SHA-256 V2 semantic signature."""

    canonical = canonical_semantic_json(semantic_record)
    return sha256(canonical.encode("utf-8")).hexdigest()


def derive_candidate_id(semantic_record: Mapping[str, object]) -> str:
    """Derive ``BMSGV1_V2_<first 16 signature hex>`` from frozen semantics."""

    return f"BMSGV1_V2_{derive_signature_hash(semantic_record)[:16]}"


def _semantic_record(
    *,
    parent_candidate_id: str,
    parent_signature_hash: str,
    features: list[dict[str, object]],
    expected_improvement_channel: str,
) -> SemanticRecord:
    feature_ids = [cast(str, feature["FEATURE_ID"]) for feature in features]
    if feature_ids != sorted(feature_ids) or len(feature_ids) != 2:
        raise RuntimeError(
            "PAIRWISE_RANK_MEAN_V1 features must be two lexicographically sorted IDs"
        )
    return {
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "PARENT_CANDIDATE_ID": parent_candidate_id,
        "PARENT_SIGNATURE_HASH": parent_signature_hash,
        "METHOD_SPACE_GRAMMAR_VERSION": "BIGLOTTO_MSG_V1",
        "SEMANTICS_COMPLETION_TEMPLATE": SEMANTICS_COMPLETION_TEMPLATE,
        "METHOD_FAMILY": "METHOD_SPACE_GAP_CANDIDATE",
        "FEATURES": features,
        "WINDOWS": dict.fromkeys(feature_ids, _PARENT_WINDOW),
        "FUSION": {
            "FORMULA": "0.5 * A_NORMALIZED_RANK + 0.5 * B_NORMALIZED_RANK",
            "NAME": "PAIRWISE_NORMALIZED_RANK_ARITHMETIC_MEAN",
            "WEIGHTS": {"A": 0.5, "B": 0.5},
        },
        "FEATURE_NORMALIZATION": {
            "BEST": 1.0,
            "FORMULA": "1 - (p - 1) / 48",
            "NAME": "NORMALIZED_RANK_49_V1",
            "WORST": 0.0,
        },
        "FIXED_WEIGHTS": {"A": 0.5, "B": 0.5},
        "CANDIDATE_CONSTRUCTION": "FIRST_SIX_NUMBERS_FROM_FINAL_RANKING",
        "TICKET_CONSTRUCTION": (
            "ONE_TICKET;SIX_UNIQUE_BUILTIN_INTEGERS;DOMAIN_1_TO_49;"
            "FINAL_ASCENDING_NUMERIC"
        ),
        "STRATEGY_COMBINATION": "SINGLE_STRATEGY",
        "MINIMUM_HISTORY": 1,
        "FIXED_PARAMETERS": {
            "FEATURE_ORDER": "LEXICOGRAPHIC_FEATURE_ID_ASCENDING_AS_A_THEN_B",
            "NUMBER_DOMAIN": [1, 49],
            "PARENT_WINDOW": _PARENT_WINDOW,
            "PICK_COUNT": _PICK_COUNT,
            "TICKET_ORDER": "ASCENDING_NUMERIC",
        },
        "CAUSAL_CUTOFF_RULE": (
            "PARSE_ISO_DATES;FILTER_ROWS_STRICTLY_BEFORE_TARGET_CUTOFF;"
            "THEN_APPLY_TRAILING_PARENT_WINDOW;TARGET_AND_FUTURE_ROWS_EXCLUDED"
        ),
        "PARAMETER_SELECTION_RULE": (
            "FIXED_PREREGISTERED_PAIRWISE_RANK_MEAN_V1;"
            "FIXED_SOURCE_PRIMITIVE_SEMANTICS;NO_OUTCOME_DERIVED_VALUES"
        ),
        "RANKING_RULE": [
            "FUSED_SCORE_DESCENDING",
            "MIN_A_B_NORMALIZED_RANK_DESCENDING",
            "A_NORMALIZED_RANK_DESCENDING",
            "B_NORMALIZED_RANK_DESCENDING",
            "NUMBER_ASCENDING",
        ],
        "TIE_BREAK_RULE": {
            "COMPONENT_RAW_SCORE_TIES": "NUMBER_ASCENDING",
            "FINAL_RANK_TIES": [
                "MIN_A_B_NORMALIZED_RANK_DESCENDING",
                "A_NORMALIZED_RANK_DESCENDING",
                "B_NORMALIZED_RANK_DESCENDING",
                "NUMBER_ASCENDING",
            ],
        },
        "FALLBACK_RULE": (
            "NONE;RAISE_EXPLICITLY;NO_PADDING;NO_SINGLE_FEATURE_DEGRADATION"
        ),
        "MISSING_FEATURE_RULE": (
            "REQUIRE_EXACT_SCORE_KEYS_1_TO_49_AND_FINITE_REAL_VALUES;"
            "RAISE_COMPONENT_SCORE_UNAVAILABLE;NO_IMPUTATION"
        ),
        "OUTPUT_SHAPE": "SINGLE_TICKET",
        "NATIVE_TICKET_COUNT": 1,
        "DETERMINISM_CLASS": "PURE_DETERMINISTIC_NO_RNG",
        "RNG_SOURCE_AND_SEED_SEMANTICS": {
            "RANDOM_VALUES_CONSUMED": False,
            "RNG_SOURCE": "NONE",
            "SEED": None,
        },
        "REQUIRED_DATA": [
            "BIG_LOTTO_PRIMARY_DRAW_HISTORY",
            "DERIVED_FEATURES_FROM_CAUSAL_HISTORY",
        ],
        "EXPECTED_IMPROVEMENT_CHANNEL": expected_improvement_channel,
        "VALIDATION_CONTRACT_REF": "BIGLOTTO_MSG_V1_CAUSAL_TRAIN_VALIDATE_R1",
    }


def _build_definition(
    *,
    expected_candidate_id: str,
    expected_signature_hash: str,
    parent_candidate_id: str,
    parent_signature_hash: str,
    features: list[dict[str, object]],
    expected_improvement_channel: str,
    implementation_symbol: str,
) -> CandidateDefinition:
    semantic_record = _semantic_record(
        parent_candidate_id=parent_candidate_id,
        parent_signature_hash=parent_signature_hash,
        features=features,
        expected_improvement_channel=expected_improvement_channel,
    )
    signature_hash = derive_signature_hash(semantic_record)
    candidate_id = derive_candidate_id(semantic_record)
    if signature_hash != expected_signature_hash or candidate_id != expected_candidate_id:
        raise RuntimeError("frozen V2 candidate identity does not match its semantic record")
    return CandidateDefinition(
        candidate_id=candidate_id,
        signature_hash=signature_hash,
        parent_candidate_id=parent_candidate_id,
        parent_signature_hash=parent_signature_hash,
        hypothesis_version=HYPOTHESIS_VERSION,
        semantics_completion_template=SEMANTICS_COMPLETION_TEMPLATE,
        minimum_history=1,
        implementation_symbol=implementation_symbol,
        canonical_semantic_json=canonical_semantic_json(semantic_record),
    )


_GAP_ENTROPY_DEFINITION: Final = _build_definition(
    expected_candidate_id=GAP_ENTROPY_CANDIDATE_ID,
    expected_signature_hash=GAP_ENTROPY_SIGNATURE_HASH,
    parent_candidate_id=PARENT_GAP_ENTROPY_ID,
    parent_signature_hash=PARENT_GAP_ENTROPY_SIGNATURE_HASH,
    features=[_ENTROPY_FEATURE, _GAP_OMISSION_FEATURE],
    expected_improvement_channel="OMISSION_OR_REVERSION_SIGNAL",
    implementation_symbol="produce_bmsgv1_v2_56c0dd23fb5f07c8",
)

_FREQUENCY_ENTROPY_DEFINITION: Final = _build_definition(
    expected_candidate_id=FREQUENCY_ENTROPY_CANDIDATE_ID,
    expected_signature_hash=FREQUENCY_ENTROPY_SIGNATURE_HASH,
    parent_candidate_id=PARENT_FREQUENCY_ENTROPY_ID,
    parent_signature_hash=PARENT_FREQUENCY_ENTROPY_SIGNATURE_HASH,
    features=[_ENTROPY_FEATURE, _FREQUENCY_FEATURE],
    expected_improvement_channel="RECENCY_OR_FREQUENCY_SIGNAL",
    implementation_symbol="produce_bmsgv1_v2_43db6a589650e5b9",
)

CANDIDATE_DEFINITIONS: Final[Mapping[str, CandidateDefinition]] = MappingProxyType(
    {
        definition.candidate_id: definition
        for definition in (_GAP_ENTROPY_DEFINITION, _FREQUENCY_ENTROPY_DEFINITION)
    }
)


def _parsed_iso_date(value: object, *, label: str) -> date:
    if type(value) is not str:
        raise CandidateInputError(f"{label} must be an exact ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CandidateInputError(f"{label} must use YYYY-MM-DD ISO format") from exc


def _strictly_prior_history(
    history: object,
    target_cutoff: object,
    definition: CandidateDefinition,
) -> tuple[CausalDrawRow, ...]:
    cutoff = _parsed_iso_date(target_cutoff, label="target_cutoff")
    canonical = validated_history(history, definition.candidate_id)

    parsed_rows: list[tuple[CausalDrawRow, date]] = []
    previous_date: date | None = None
    for index, row in enumerate(canonical):
        row_date = _parsed_iso_date(row.date, label=f"history row {index} date")
        if previous_date is not None and row_date < previous_date:
            raise CandidateInputError("history must be chronological by nondecreasing ISO date")
        parsed_rows.append((row, row_date))
        previous_date = row_date

    causal = tuple(row for row, row_date in parsed_rows if row_date < cutoff)
    if len(causal) < definition.minimum_history:
        raise InsufficientCandidateHistory(
            f"{definition.candidate_id}: needs {definition.minimum_history} strictly prior "
            f"draws, got {len(causal)}"
        )
    return causal[-_PARENT_WINDOW:]


def _raw_feature_scores(
    feature_id: str,
    history_window: tuple[CausalDrawRow, ...],
) -> object:
    try:
        if feature_id == "ENTROPY":
            return _entropy_scores(history_window)
        if feature_id == "GAP_OMISSION":
            return _gap_pressure_scores(history_window)
        if feature_id == "FREQUENCY":
            newest_first = tuple(reversed(history_window))
            scores = _historical_frequency(newest_first)
            return {number: scores[number - _MIN_NUMBER] for number in _NUMBER_DOMAIN}
    except Exception as exc:
        raise ComponentScoreUnavailable(f"{feature_id}: component scoring failed") from exc
    raise ComponentScoreUnavailable(f"{feature_id}: no frozen component scorer")


def _validated_feature_scores(
    feature_id: str,
    history_window: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    raw_scores = _raw_feature_scores(feature_id, history_window)
    if not isinstance(raw_scores, Mapping):
        raise ComponentScoreUnavailable(f"{feature_id}: scores must be a mapping")
    raw_mapping = cast(Mapping[object, object], raw_scores)
    if frozenset(raw_mapping) != _NUMBER_DOMAIN_SET:
        raise ComponentScoreUnavailable(f"{feature_id}: scores must contain exactly numbers 1..49")

    validated: dict[int, float] = {}
    for number in _NUMBER_DOMAIN:
        value = raw_mapping[number]
        if type(value) is int:
            score = float(value)
        elif type(value) is float:
            score = value
        else:
            raise ComponentScoreUnavailable(
                f"{feature_id}: score for number {number} must be a finite real value"
            )
        if not isfinite(score):
            raise ComponentScoreUnavailable(
                f"{feature_id}: score for number {number} must be a finite real value"
            )
        validated[number] = score
    return validated


def _normalized_ranks(scores: Mapping[int, float]) -> dict[int, Fraction]:
    ranked = sorted(_NUMBER_DOMAIN, key=lambda number: (-scores[number], number))
    return {
        number: Fraction(
            _NORMALIZED_RANK_DENOMINATOR - (position - 1),
            _NORMALIZED_RANK_DENOMINATOR,
        )
        for position, number in enumerate(ranked, start=1)
    }


def _pairwise_ticket(
    feature_ids: tuple[str, str],
    history_window: tuple[CausalDrawRow, ...],
) -> Ticket:
    if feature_ids != tuple(sorted(feature_ids)):
        raise RuntimeError("feature IDs must be lexicographically ordered")
    a_scores = _validated_feature_scores(feature_ids[0], history_window)
    b_scores = _validated_feature_scores(feature_ids[1], history_window)
    a_ranks = _normalized_ranks(a_scores)
    b_ranks = _normalized_ranks(b_scores)
    fused = {
        number: Fraction(1, 2) * a_ranks[number] + Fraction(1, 2) * b_ranks[number]
        for number in _NUMBER_DOMAIN
    }
    ranked = sorted(
        _NUMBER_DOMAIN,
        key=lambda number: (
            -fused[number],
            -min(a_ranks[number], b_ranks[number]),
            -a_ranks[number],
            -b_ranks[number],
            number,
        ),
    )
    ticket = tuple(sorted(ranked[:_PICK_COUNT]))
    if (
        len(ticket) != _PICK_COUNT
        or len(set(ticket)) != _PICK_COUNT
        or any(number not in _NUMBER_DOMAIN_SET for number in ticket)
    ):
        raise CandidateOutputError("PAIRWISE_RANK_MEAN_V1 produced an illegal ticket")
    return ticket


def _feature_ids(definition: CandidateDefinition) -> tuple[str, str]:
    record = definition.semantic_record()
    raw_features = record["FEATURES"]
    if type(raw_features) is not list:
        raise RuntimeError("candidate FEATURES must be a list")
    features = cast(list[object], raw_features)
    feature_ids: list[str] = []
    for feature in features:
        if type(feature) is not dict:
            raise RuntimeError("candidate feature must be an object")
        feature_record = cast(dict[str, object], feature)
        feature_id = feature_record.get("FEATURE_ID")
        if type(feature_id) is not str:
            raise RuntimeError("candidate feature ID must be a string")
        feature_ids.append(feature_id)
    if len(feature_ids) != 2:
        raise RuntimeError("candidate must contain exactly two feature IDs")
    return feature_ids[0], feature_ids[1]


def _produce_candidate(
    definition: CandidateDefinition,
    history: object,
    target_cutoff: object,
) -> TicketPortfolio:
    history_window = _strictly_prior_history(history, target_cutoff, definition)
    ticket = _pairwise_ticket(_feature_ids(definition), history_window)
    return (ticket,)


def produce_bmsgv1_v2_56c0dd23fb5f07c8(
    history: tuple[CausalDrawRow, ...],
    target_cutoff: str,
) -> TicketPortfolio:
    """Produce the frozen GAP_OMISSION + ENTROPY V2 candidate."""

    return _produce_candidate(_GAP_ENTROPY_DEFINITION, history, target_cutoff)


def produce_bmsgv1_v2_43db6a589650e5b9(
    history: tuple[CausalDrawRow, ...],
    target_cutoff: str,
) -> TicketPortfolio:
    """Produce the frozen FREQUENCY + ENTROPY V2 candidate."""

    return _produce_candidate(_FREQUENCY_ENTROPY_DEFINITION, history, target_cutoff)


CANDIDATE_PRODUCERS: Final[Mapping[str, CandidateProducer]] = MappingProxyType(
    {
        GAP_ENTROPY_CANDIDATE_ID: produce_bmsgv1_v2_56c0dd23fb5f07c8,
        FREQUENCY_ENTROPY_CANDIDATE_ID: produce_bmsgv1_v2_43db6a589650e5b9,
    }
)


__all__ = [
    "CANDIDATE_DEFINITIONS",
    "CANDIDATE_PRODUCERS",
    "FREQUENCY_ENTROPY_CANDIDATE_ID",
    "FREQUENCY_ENTROPY_SIGNATURE_HASH",
    "GAP_ENTROPY_CANDIDATE_ID",
    "GAP_ENTROPY_SIGNATURE_HASH",
    "HYPOTHESIS_VERSION",
    "PARENT_FREQUENCY_ENTROPY_ID",
    "PARENT_FREQUENCY_ENTROPY_SIGNATURE_HASH",
    "PARENT_GAP_ENTROPY_ID",
    "PARENT_GAP_ENTROPY_SIGNATURE_HASH",
    "SEMANTICS_COMPLETION_TEMPLATE",
    "BigLottoMethodSpaceCandidateError",
    "CandidateDefinition",
    "CandidateInputError",
    "CandidateOutputError",
    "ComponentScoreUnavailable",
    "InsufficientCandidateHistory",
    "canonical_semantic_json",
    "derive_candidate_id",
    "derive_signature_hash",
    "produce_bmsgv1_v2_43db6a589650e5b9",
    "produce_bmsgv1_v2_56c0dd23fb5f07c8",
]
