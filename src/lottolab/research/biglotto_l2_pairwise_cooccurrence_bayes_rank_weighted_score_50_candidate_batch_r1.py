"""Causal deterministic BigLotto Level-2 pairwise candidate batch R1.

This module freezes exactly one candidate from the completed design authority
BMSGV1_L2_PAIRWISE_e849a4b70db5d01e.  It reuses the sealed W=50
conditional-cooccurrence and Bayesian changepoint BMA parent rankers,
normalizes both parent outputs by their exact rank positions, and fuses them
with an exact one-half plus one-half score.

The implementation ranks all 49 legal numbers and emits one sorted native
ticket.  It is history-only, exact-rational, deterministic, and research-only:
it has no outcome tuning, randomness, I/O, database access, network access,
replay, catalog registration, or registry wiring.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _cooccurrence_parent,
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as _bayes_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_e849a4b70db5d01e"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_COOCCURRENCE_BAYES_RANK_WEIGHTED_SCORE_50_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "39b160294822a552ee4e8992479d8b3cb0b56ed79fe4ff9eb4b5760e3e8ddf77"
)
SOURCE_UNIVERSE_ID: Final[str] = DESIGN_ID
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
FEATURE_1: Final[str] = "COOCCURRENCE"
FEATURE_2: Final[str] = "BAYESIAN_PROBABILISTIC"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
MINIMUM_HISTORY: Final[int] = 751

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_1_IMPLEMENTATION_COMMIT: Final[str] = (
    "89c9f2312d9cd8cf41c9573372dadf89a589366b"
)
PARENT_2_IMPLEMENTATION_COMMIT: Final[str] = (
    "7845d0296a2512ec6d8bdc82d208057c06f732c7"
)

COMPONENT_NORMALIZATION_CLASS: Final[str] = (
    "EXACT_RATIONAL_RANK_NORMALIZATION"
)
COMPONENT_NORMALIZATION_RULE: Final[str] = (
    "RANK_POSITION_NORMALIZATION_FOR_BOTH_COMPONENTS;"
    "NORMALIZED=(49-POSITION)/48;POSITION_ONE_BASED;EXACT_RATIONAL;"
    "NO_RAW_SCALE_CALIBRATION"
)
COMPONENT_NORMALIZATION: Final[str] = COMPONENT_NORMALIZATION_CLASS
FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=(COOCCURRENCE_RANK_50(n)+BAYES_RANK_50(n))/2;"
    "EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA
NUMBER_RANKING_RULE: Final[str] = "PAIRWISE_SCORE_DESC_NUMBER_ASC"
NUMBER_TIE_BREAK_RULE: Final[str] = (
    "EXACT_PAIRWISE_SCORE_TIE_THEN_NUMBER_ASCENDING"
)
RANKED_POOL_DOMAIN: Final[str] = "1..49"
RANKED_POOL_CARDINALITY: Final[int] = 49
RANKED_POOL_RULE: Final[str] = (
    "SCORE_ALL_LEGAL_NUMBERS_1_TO_49;RANK_BY_PAIRWISE_SCORE_DESC;"
    "TIES_BY_NUMBER_ASC;NO_INTERMEDIATE_TOP_K_POOL"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_SELECTION_RULE: Final[str] = (
    "TAKE_RANKED_POSITIONS_1_TO_6;MAP_TO_NUMBERS;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_COUNT: Final[int] = 1
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "NO_FUTURE_SUFFIX;ALL_PARENT_COUNTS_AND_RANKS_FROM_STRICTLY_PRIOR_HISTORY"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;"
    "EQUAL_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "BAYES_PRIOR_ALPHA=6,BETA=43_PRE_REGISTERED;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "DEPENDENCE_STRUCTURE_SIGNAL"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "COOCCURRENCE_SCORE_50(n)=SUM_{a IN ANCHOR_DRAW,a!=n}"
    "(PAIR_COUNT_50(a,n)/OCCURRENCE_50(a));ANCHOR_DRAW=history[T-1];"
    "ZERO_OCCURRENCE_CONTRIBUTION=0;RANK_SCORE_DESCENDING_NUMBER_ASCENDING;"
    "EXACT_RATIONAL"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "BMA_PREDICTIVE_50(n)=POSTERIOR_M0_50(n)*PREDICTIVE_M0_50(n)+"
    "POSTERIOR_M1_50(n)*PREDICTIVE_M1_50(n);BETA_PRIOR=(6,43);"
    "M0_AND_M1_EVIDENCE_EXACT_RATIONAL;"
    "RANK_KEYS=BMA_PREDICTIVE_DESC,POSTERIOR_M1_DESC,"
    "PREDICTIVE_M1_DESC,NUMBER_ASC"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];ANCHOR=history[T-1];"
    "ESTIMATION_DRAWS=history[T-51:T-1];W=50;"
    "ANCHOR_EXCLUDED_FROM_ESTIMATION"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];WINDOW_DRAWS=history[T-50:T];"
    "W=50;OLDER_HALF=history[T-50:T-25];RECENT_HALF=history[T-25:T];"
    "TARGET_ROW=history[T] EXCLUDED"
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_b649_l2_pairwise_conditional_cooccurrence_bayes_weighted_score_50_v1"
)


class InsufficientHistoryError(
    _cooccurrence_parent.InsufficientHistoryError
):
    """Raised when fewer than 751 strictly prior draws are available."""


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two parent rank contributions."""

    NUMBER: int
    COOCCURRENCE_COMPONENT: Fraction
    BAYES_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    POSITION: int

    @property
    def COOCCURRENCE_RANK_50(self) -> Fraction:
        return self.COOCCURRENCE_COMPONENT

    @property
    def BAYES_RANK_50(self) -> Fraction:
        return self.BAYES_COMPONENT


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 exact ranked numbers and the one native ticket."""

    COOCCURRENCE_COMPONENTS: Components
    BAYES_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket

    @property
    def ORDERED_NUMBERS(self) -> tuple[int, ...]:
        return self.RANKED_NUMBERS

    @property
    def TICKET(self) -> Ticket:
        return self.NATIVE_TICKET

    @property
    def TICKETS(self) -> TicketPortfolio:
        return (self.NATIVE_TICKET,)

    @property
    def NATIVE_TICKETS(self) -> TicketPortfolio:
        return self.TICKETS

    def cooccurrence_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.COOCCURRENCE_COMPONENTS[number - 1]

    def bayes_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.BAYES_COMPONENTS[number - 1]

    def pairwise_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAIRWISE_SCORES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def score_record(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]


def _validate_number(number: int) -> None:
    if (
        type(number) is not int
        or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
    ):
        raise ValueError("number must be an integer in 1..49")


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Validate and copy exactly the strictly prior history prefix."""

    if _cooccurrence_parent.MINIMUM_HISTORY != MINIMUM_HISTORY:
        raise RuntimeError("conditional-cooccurrence parent minimum history drifted")
    try:
        validated = _cooccurrence_parent.validate_prior_history(
            history, target_index
        )
    except _cooccurrence_parent.InsufficientHistoryError as error:
        raise InsufficientHistoryError(str(error)) from error
    return validated


validate_history = validate_prior_history


def _cooccurrence_components_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    ranking = _cooccurrence_parent.rank_numbers_by_window(
        prior_history, len(prior_history), WINDOW
    )
    if ranking.WINDOW != WINDOW:
        raise RuntimeError("cooccurrence parent returned the wrong window")
    return ranking.NORMALIZED_RANKS


def _bayes_components_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    ranking = _bayes_parent.rank_numbers_by_window(
        prior_history, len(prior_history), WINDOW
    )
    if ranking.WINDOW != WINDOW:
        raise RuntimeError("Bayesian parent returned the wrong window")
    return ranking.NORMALIZED_RANKS


def calculate_cooccurrence_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized W=50 conditional-cooccurrence ranks."""

    return _cooccurrence_components_from_prior_history(
        validate_prior_history(history, target_index)
    )


cooccurrence_components = calculate_cooccurrence_components
cooccurrence_component_50 = calculate_cooccurrence_components


def calculate_bayes_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized W=50 Bayesian changepoint BMA ranks."""

    return _bayes_components_from_prior_history(
        validate_prior_history(history, target_index)
    )


bayesian_components = calculate_bayes_components
bayes_component_50 = calculate_bayes_components


def _exact_component_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if (
            len(keys) != RANKED_POOL_CARDINALITY
            or set(keys) != set(range(1, RANKED_POOL_CARDINALITY + 1))
        ):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 components")

    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            exact = value
        elif type(value) is int:
            exact = Fraction(value, 1)
        else:
            raise TypeError(
                f"{name}[{index}] must use exact Fraction or integer arithmetic"
            )
        if not Fraction(0, 1) <= exact <= Fraction(1, 1):
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        converted.append(exact)
    return tuple(converted)


def rank_pairwise_scores(
    cooccurrence_components: Sequence[object] | Mapping[int, object],
    bayes_components: Sequence[object] | Mapping[int, object],
) -> PairwiseRanking:
    """Fuse two exact rank-normalized vectors and rank all legal numbers."""

    cooccurrence = _exact_component_values(
        cooccurrence_components, "cooccurrence_components"
    )
    bayes = _exact_component_values(bayes_components, "bayes_components")
    scores = tuple(
        FUSION_WEIGHT_1 * cooccurrence[index]
        + FUSION_WEIGHT_2 * bayes[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-scores[number - 1], number),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ranked_numbers, start=1):
        positions[number - 1] = position
    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            COOCCURRENCE_COMPONENT=cooccurrence[number - 1],
            BAYES_COMPONENT=bayes[number - 1],
            PAIRWISE_SCORE=scores[number - 1],
            POSITION=positions[number - 1],
        )
        for number in ranked_numbers
    )
    ticket = cast(Ticket, tuple(sorted(ranked_numbers[:PICK_COUNT])))
    if (
        len(ticket) != PICK_COUNT
        or len(set(ticket)) != PICK_COUNT
        or not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket)
    ):
        raise RuntimeError("pairwise native ticket must contain six legal unique numbers")
    return PairwiseRanking(
        COOCCURRENCE_COMPONENTS=cooccurrence,
        BAYES_COMPONENTS=bayes,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the causal pairwise ranking from both frozen parents."""

    prior_history = validate_prior_history(history, target_index)
    cooccurrence = calculate_cooccurrence_components(
        prior_history, len(prior_history)
    )
    bayes = calculate_bayes_components(prior_history, len(prior_history))
    return rank_pairwise_scores(cooccurrence, bayes)


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the one sorted ticket selected from ranked positions 1..6."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio

produce_b649_l2_pairwise_conditional_cooccurrence_bayes_weighted_score_50_v1 = (
    produce_candidate_portfolio
)
produce_bmsgv1_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate_batch_r1 = (
    produce_b649_l2_pairwise_conditional_cooccurrence_bayes_weighted_score_50_v1
)
produce_biglotto_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate = (
    produce_b649_l2_pairwise_conditional_cooccurrence_bayes_weighted_score_50_v1
)


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        converted: dict[str, object] = {}
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
    """Return sorted-key compact UTF-8 JSON for a semantic record."""

    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    return json.dumps(
        _json_ready(cast(Mapping[object, object], record)),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Validate and return the sealed candidate identity."""

    expected = {
        "CANDIDATE_ID": CANDIDATE_ID,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
    }
    for key, value in expected.items():
        if key in record and record[key] != value:
            raise ValueError(f"semantic record does not identify {key}")
    return CANDIDATE_ID


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """The selected-gap identity and completed-design signature."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(
    record: Mapping[str, object],
) -> CandidateIdentity:
    return CandidateIdentity(
        CANDIDATE_ID=candidate_id_for_semantics(record),
        SIGNATURE_HASH=DESIGN_SIGNATURE_SHA256,
        CANONICAL_SEMANTIC_JSON=canonical_semantic_json(record),
    )


def _semantic_record() -> dict[str, object]:
    return {
        "AUTHORITY_TYPE": "PREDICTION_PRODUCING_V1_DESIGN_AUTHORITY",
        "CANDIDATE_CONSTRUCTION": "RANKED_POOL",
        "CANDIDATE_ID": CANDIDATE_ID,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COMPONENT_NORMALIZATION_CLASS": COMPONENT_NORMALIZATION_CLASS,
        "COMPONENT_NORMALIZATION_RULE": COMPONENT_NORMALIZATION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "FUSION": FUSION,
        "FUSION_FORMULA": FUSION_FORMULA,
        "FUSION_WEIGHT_1": FUSION_WEIGHT_1_TEXT,
        "FUSION_WEIGHT_2": FUSION_WEIGHT_2_TEXT,
        "HISTORY_ORDER": HISTORY_ORDER,
        "IMPLEMENTATION_MODULE": IMPLEMENTATION_MODULE,
        "IMPLEMENTATION_SYMBOL": IMPLEMENTATION_SYMBOL,
        "IMPLEMENTATION_READY": "YES",
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_LEVEL": METHOD_LEVEL,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE,
        "NUMBER_TIE_BREAK_RULE": NUMBER_TIE_BREAK_RULE,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PARENT_COMPONENT_RULE_1": PARENT_COMPONENT_RULE_1,
        "PARENT_COMPONENT_RULE_2": PARENT_COMPONENT_RULE_2,
        "PARENT_SOURCE_UNIVERSE_ID_1": PARENT_SOURCE_UNIVERSE_ID_1,
        "PARENT_SOURCE_UNIVERSE_ID_2": PARENT_SOURCE_UNIVERSE_ID_2,
        "PARENT_SOURCE_UNIVERSE_VERSION_1": PARENT_SOURCE_UNIVERSE_VERSION_1,
        "PARENT_SOURCE_UNIVERSE_VERSION_2": PARENT_SOURCE_UNIVERSE_VERSION_2,
        "PARENT_WINDOW_RULE_1": PARENT_WINDOW_RULE_1,
        "PARENT_WINDOW_RULE_2": PARENT_WINDOW_RULE_2,
        "RANKED_POOL_CARDINALITY": RANKED_POOL_CARDINALITY,
        "RANKED_POOL_DOMAIN": RANKED_POOL_DOMAIN,
        "RANKED_POOL_RULE": RANKED_POOL_RULE,
        "RNG": RNG,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "TICKET_CONSTRUCTION": TICKET_CONSTRUCTION,
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
        "TICKET_SELECTION_RULE": TICKET_SELECTION_RULE,
        "WINDOW": WINDOW,
    }


CANDIDATE_SEMANTICS: Final[Mapping[str, object]] = MappingProxyType(
    _semantic_record()
)
CANDIDATE_SEMANTIC_RECORDS: Final[
    Mapping[str, Mapping[str, object]]
] = MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable metadata for the one frozen pairwise candidate."""

    CANDIDATE_ID: str
    SELECTED_GAP_ID: str
    DESIGN_ID: str
    DESIGN_SIGNATURE_SHA256: str
    FEATURE_1: str
    FEATURE_2: str
    WINDOW: int
    COMPONENT_NORMALIZATION_RULE: str
    FUSION_WEIGHT_1: str
    FUSION_WEIGHT_2: str
    IMPLEMENTATION_MODULE: str
    IMPLEMENTATION_SYMBOL: str
    NATIVE_TICKET_COUNT: int
    MINIMUM_HISTORY: int
    DETERMINISM_CLASS: str
    SEMANTICS: Mapping[str, object]


CANDIDATE_METADATA: Final[CandidateMetadata] = CandidateMetadata(
    CANDIDATE_ID=CANDIDATE_ID,
    SELECTED_GAP_ID=SELECTED_GAP_ID,
    DESIGN_ID=DESIGN_ID,
    DESIGN_SIGNATURE_SHA256=DESIGN_SIGNATURE_SHA256,
    FEATURE_1=FEATURE_1,
    FEATURE_2=FEATURE_2,
    WINDOW=WINDOW,
    COMPONENT_NORMALIZATION_RULE=COMPONENT_NORMALIZATION_RULE,
    FUSION_WEIGHT_1=FUSION_WEIGHT_1_TEXT,
    FUSION_WEIGHT_2=FUSION_WEIGHT_2_TEXT,
    IMPLEMENTATION_MODULE=IMPLEMENTATION_MODULE,
    IMPLEMENTATION_SYMBOL=IMPLEMENTATION_SYMBOL,
    NATIVE_TICKET_COUNT=NATIVE_TICKET_COUNT,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    SEMANTICS=CANDIDATE_SEMANTICS,
)
CANDIDATE_AUTHORITIES: Final[tuple[CandidateMetadata, ...]] = (
    CANDIDATE_METADATA,
)
CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = MappingProxyType(
    {CANDIDATE_ID: CANDIDATE_METADATA}
)
CANDIDATE_IDS: Final[tuple[str, ...]] = (CANDIDATE_ID,)
CANDIDATE_SIGNATURE_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {CANDIDATE_ID: DESIGN_SIGNATURE_SHA256}
)


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_ID",
    "CANDIDATE_IDS",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SEMANTICS_BY_ID",
    "CANDIDATE_SEMANTIC_RECORDS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "COMPONENT_NORMALIZATION",
    "COMPONENT_NORMALIZATION_CLASS",
    "COMPONENT_NORMALIZATION_RULE",
    "DESIGN_ID",
    "DESIGN_SIGNATURE_SHA256",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_1",
    "FEATURE_2",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "HISTORY_ORDER",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "METHOD_LEVEL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_TIE_BREAK_RULE",
    "OUTPUT_SHAPE",
    "PAIRWISE_SCORE_RULE",
    "PARAMETER_SELECTION_RULE",
    "PARENT_1_IMPLEMENTATION_COMMIT",
    "PARENT_2_IMPLEMENTATION_COMMIT",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "PICK_COUNT",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RANKED_POOL_RULE",
    "RNG",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "bayes_component_50",
    "bayesian_components",
    "build_source_ticket_universe",
    "calculate_bayes_components",
    "calculate_cooccurrence_components",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "cooccurrence_component_50",
    "cooccurrence_components",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "produce_b649_l2_pairwise_conditional_cooccurrence_bayes_weighted_score_50_v1",
    "produce_biglotto_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
