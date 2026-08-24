"""Causal deterministic BigLotto Level-2 HOT_COLD + ENTROPY candidate.

This module implements exactly one candidate from the completed design
authority ``B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1``.  The
implementation is research-only: it has no catalog registration, database,
network, clock, replay, outcome, or random-number dependency.

Both parent components are calculated from the strictly prior history prefix
using exact integer and ``Fraction`` arithmetic.  Every legal number is
scored, rank-normalized, fused with the sealed one-half plus one-half rule,
and the first six final ranks form the one native ticket.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice
from types import MappingProxyType
from typing import Final, cast

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_bb262c993f3fefee"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "07614efe3fb6e0ee39253b15012da2d4cacff0bfe47dcdd12936ac69aa96aab7"
)
SOURCE_UNIVERSE_ID: Final[str] = DESIGN_ID
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"

FEATURE_1: Final[str] = "HOT_COLD"
FEATURE_2: Final[str] = "ENTROPY"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
MINIMUM_HISTORY: Final[int] = 100

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_1_IMPLEMENTATION_COMMIT: Final[str] = (
    "621bfac61cb8591ea5e367272a5170dce50a65a2"
)
PARENT_2_IMPLEMENTATION_COMMIT: Final[str] = (
    "621bfac61cb8591ea5e367272a5170dce50a65a2"
)
PARENT_1_SOURCE_BLOB_ID: Final[str] = "c79e1f547a8221552d755aa284c76de9c6edeaa7"
PARENT_2_SOURCE_BLOB_ID: Final[str] = "a494ac5a4cfa6e3e6f35a95f160ba3bc92897df4"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "Use the live Hot Co-occurrence Analyzer primitive from "
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee;derive a "
    "complete 1..49 exact-rational score vector by the fixed "
    "HOT_COLD_SCORE_RULE; no target or future rows."
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "Use the entropy parent identity BMSGV1_L1_FEATURE_65309ef7bca9f40e "
    "with the fixed ENTROPY_SCORE_RULE; no target or future rows."
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "HOT_FREQUENCY_HISTORY=history[T-50:T];COOCCURRENCE_HISTORY="
    "history[T-100:T];TARGET_INDEX=T;ALL_DRAWS_STRICTLY_PRIOR"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "ENTROPY_HISTORY=history[T-50:T];TARGET_INDEX=T;ALL_DRAWS_STRICTLY_PRIOR"
)

HOT_COLD_POOL_CARDINALITY: Final[int] = 20
HOT_COLD_WEIGHT: Final[Fraction] = Fraction(3, 10)
HOT_COLD_RANK_WEIGHT: Final[Fraction] = Fraction(7, 10)
HOT_COLD_SCORE_RULE: Final[str] = (
    "FREQUENCY_ORDER=positive_COUNT_50_DESCENDING_THEN_FIRST_OBSERVATION_INDEX_ASCENDING;"
    "HOT_POOL=first_MIN(20,positive_count_numbers);"
    "PAIR_COUNT_100(n,m)=number_of_prior_draws_containing_both;"
    "CO_100(n,m)=PAIR_COUNT_100(n,m)/100;"
    "for n at hot_pool index i, HOT_COLD_RAW(n)=7/10*((H-i)/H)+"
    "3/10*mean(CO_100(n,m) for m in hot_pool,m!=n);"
    "H<=1 uses cooccurrence mean 0;non_hot_pool numbers raw score 0;EXACT_RATIONAL"
)
ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=appearances_in_six_main_numbers_of_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER"
)

COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_HOT_COLD_SCORE_FOR_1_TO_49;RANGE_0_TO_1"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RATIONAL_ENTROPY_SCORE_FOR_1_TO_49;POSITIVE"
)
COMPONENT_NORMALIZATION: Final[str] = "NORMALIZED_RANK_49_V1"
COMPONENT_NORMALIZATION_CLASS: Final[str] = COMPONENT_NORMALIZATION
COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build one complete raw score for every legal number 1..49 for each parent component.",
    "Rank each component higher-is-better; exact raw-score ties use number ascending.",
    "Normalize one-based position p as (49-p)/48; best rank is 1 and worst rank is 0; "
    "exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, or "
    "outcome-derived normalization.",
)
COMPONENT_NORMALIZATION_RULE: Final[str] = ";".join(
    COMPONENT_NORMALIZATION_RULE_LINES
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*HOT_COLD_NORMALIZED_RANK_50(n)+"
    "1/2*ENTROPY_NORMALIZED_RANK_50(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "HOT_COLD normalized rank descending.",
    "ENTROPY normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[str] = ";".join(NUMBER_RANKING_RULE_LINES)
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "Raw parent component score ties: number ascending.",
    "Final pairwise ties: minimum component rank descending, HOT_COLD rank "
    "descending, ENTROPY rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[str] = ";".join(NUMBER_TIE_BREAK_RULE_LINES)

RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
RANKED_POOL_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS;NO_INTERMEDIATE_TOP6_OR_TOP20_POOL"
)
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS_WITH_FUSED_PAIRWISE_SCORE;"
    "NO_INTERMEDIATE_TOP_K_POOL"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_CONSTRUCTION_RULE: Final[str] = (
    "TAKE_FINAL_PAIRWISE_RANK_POSITIONS_1_TO_6;"
    "SORT_SELECTED_NUMBERS_ASCENDING;RETURN_ONE_NATIVE_BIGLOTTO_TICKET"
)
TICKET_SELECTION_RULE: Final[str] = "FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS"
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_100=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;"
    "NO_TRUNCATION;NO_SINGLE_FEATURE_DEGRADATION;NO_RANDOMNESS"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;"
    "PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "HOT_COLD_CO_OCCURRENCE_WEIGHT=3/10_PARENT_CONSTANT;"
    "ENTROPY_EPSILON=1/10_PARENT_CONSTANT;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "RECENCY_OR_FREQUENCY_SIGNAL"
IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than 100 strictly prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores, ranks, and positions for one parent component."""

    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def raw_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RAW_SCORES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    @property
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    HOT_COLD_COMPONENT: Fraction
    ENTROPY_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def HOT_COLD_RANK_50(self) -> Fraction:
        return self.HOT_COLD_COMPONENT

    @property
    def ENTROPY_RANK_50(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 exact fused ranks and exactly one native ticket."""

    HOT_COLD_COMPONENTS: Components
    ENTROPY_COMPONENTS: Components
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

    def hot_cold_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.HOT_COLD_COMPONENTS[number - 1]

    def entropy_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.ENTROPY_COMPONENTS[number - 1]

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


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """The selected-gap identity and sealed design signature."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


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


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError("number must be an integer in 1..49")


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    """Read exactly ``history[:target_index]`` without touching the suffix."""

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


def _raw_draw_values(raw_draw: object, draw_index: int) -> tuple[object, ...]:
    """Extract tuple-like rows and the native ``.numbers`` row shape."""

    numbers = getattr(raw_draw, "numbers", None)
    candidate = numbers if numbers is not None else raw_draw
    try:
        return tuple(cast(Iterable[object], candidate))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly six integers"
        ) from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    values = _raw_draw_values(raw_draw, draw_index)
    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly six numbers")

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in 1..49"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return a validated immutable copy of only the strictly prior history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _frequency_order(recent_history: tuple[HistoryDraw, ...]) -> tuple[int, ...]:
    """Match the parent Counter order: count descending, first observation ascending."""

    counts = [0] * RANKED_POOL_CARDINALITY
    first_observation: list[int | None] = [None] * RANKED_POOL_CARDINALITY
    observation_index = 0
    for draw in recent_history:
        for number in draw:
            counts[number - 1] += 1
            if first_observation[number - 1] is None:
                first_observation[number - 1] = observation_index
            observation_index += 1

    observed_numbers = tuple(
        number
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
        if counts[number - 1] > 0
    )
    return tuple(
        sorted(
            observed_numbers,
            key=lambda number: (
                -counts[number - 1],
                cast(int, first_observation[number - 1]),
            ),
        )
    )


def _hot_cold_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    """Reproduce the sealed Hot Co-occurrence Analyzer primitive exactly."""

    frequency_history = prior_history[-WINDOW:]
    ordered_positive_numbers = _frequency_order(frequency_history)
    hot_pool = ordered_positive_numbers[:HOT_COLD_POOL_CARDINALITY]
    hot_pool_size = len(hot_pool)

    pair_counts = [
        [0] * (RANKED_POOL_CARDINALITY + 1)
        for _ in range(RANKED_POOL_CARDINALITY + 1)
    ]
    for draw in prior_history[-2 * WINDOW :]:
        for left, right in combinations(draw, 2):
            pair_counts[left][right] += 1
            pair_counts[right][left] += 1

    raw_scores = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for index, number in enumerate(hot_pool):
        rank_score = Fraction(hot_pool_size - index, hot_pool_size)
        if hot_pool_size <= 1:
            cooccurrence_mean = Fraction(0, 1)
        else:
            cooccurrence_mean = sum(
                (
                    Fraction(pair_counts[number][other], 2 * WINDOW)
                    for other in hot_pool
                    if other != number
                ),
                Fraction(0, 1),
            ) / (hot_pool_size - 1)
        raw_scores[number - 1] = (
            HOT_COLD_RANK_WEIGHT * rank_score
            + HOT_COLD_WEIGHT * cooccurrence_mean
        )
    return tuple(raw_scores)


def _entropy_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    """Calculate the sealed exact-rational W=50 entropy-parent scores."""

    counts = [0] * RANKED_POOL_CARDINALITY
    for draw in prior_history[-WINDOW:]:
        for number in draw:
            counts[number - 1] += 1

    return tuple(
        Fraction(1, 1)
        / (
            abs(Fraction(counts[number - 1], 1) - ENTROPY_EXPECTED_COUNT)
            + ENTROPY_EPSILON
        )
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )


def _exact_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> tuple[Fraction, ...]:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if (
            len(keys) != RANKED_POOL_CARDINALITY
            or set(keys) != set(range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1))
        ):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 values")

    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            converted.append(value)
        elif type(value) is int:
            converted.append(Fraction(value, 1))
        else:
            raise TypeError(
                f"{name}[{index}] must use exact Fraction or integer arithmetic"
            )
    return tuple(converted)


def _rank_raw_scores(
    values: Sequence[object] | Mapping[int, object], name: str
) -> ComponentRanking:
    raw_scores = _exact_values(values, name)
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-raw_scores[number - 1], number),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized_ranks = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)
    return ComponentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def calculate_hot_cold_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact sealed HOT_COLD raw score vector for 1..49."""

    return _hot_cold_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact sealed ENTROPY raw score vector for 1..49."""

    return _entropy_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


def rank_hot_cold_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank a complete exact HOT_COLD raw score vector."""

    return _rank_raw_scores(raw_scores, "hot_cold_raw_scores")


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank a complete exact ENTROPY raw score vector."""

    return _rank_raw_scores(raw_scores, "entropy_raw_scores")


def calculate_hot_cold_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the exact normalized HOT_COLD W=50 ranking."""

    return rank_hot_cold_scores(calculate_hot_cold_raw_scores(history, target_index))


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the exact normalized ENTROPY W=50 ranking."""

    return rank_entropy_scores(calculate_entropy_raw_scores(history, target_index))


def calculate_hot_cold_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized HOT_COLD W=50 ranks."""

    return calculate_hot_cold_ranking(history, target_index).NORMALIZED_RANKS


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized ENTROPY W=50 ranks."""

    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


hot_cold_components = calculate_hot_cold_components
hot_cold_component_50 = calculate_hot_cold_components
entropy_components = calculate_entropy_components
entropy_component_50 = calculate_entropy_components


def _exact_normalized_components(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    components = _exact_values(values, name)
    if any(value < 0 or value > 1 for value in components):
        raise ValueError(f"{name} must lie in [0,1]")
    return components


def rank_pairwise_scores(
    hot_cold_components: Sequence[object] | Mapping[int, object],
    entropy_components: Sequence[object] | Mapping[int, object],
) -> PairwiseRanking:
    """Fuse two exact normalized parent vectors and rank all 49 numbers."""

    hot_cold = _exact_normalized_components(
        hot_cold_components, "hot_cold_components"
    )
    entropy = _exact_normalized_components(
        entropy_components, "entropy_components"
    )
    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * hot_cold[index]
        + FUSION_WEIGHT_2 * entropy[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -pairwise_scores[number - 1],
                -min(hot_cold[number - 1], entropy[number - 1]),
                -hot_cold[number - 1],
                -entropy[number - 1],
                number,
            ),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ranked_numbers, start=1):
        positions[number - 1] = position

    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            HOT_COLD_COMPONENT=hot_cold[number - 1],
            ENTROPY_COMPONENT=entropy[number - 1],
            PAIRWISE_SCORE=pairwise_scores[number - 1],
            MIN_COMPONENT_RANK=min(hot_cold[number - 1], entropy[number - 1]),
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
        HOT_COLD_COMPONENTS=hot_cold,
        ENTROPY_COMPONENTS=entropy,
        PAIRWISE_SCORES=pairwise_scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the causal ranking from both sealed parent components."""

    prior_history = validate_prior_history(history, target_index)
    hot_cold = calculate_hot_cold_components(prior_history, len(prior_history))
    entropy = calculate_entropy_components(prior_history, len(prior_history))
    return rank_pairwise_scores(hot_cold, entropy)


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the one sorted ticket from final pairwise positions 1..6."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate = (
    produce_candidate_portfolio
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
    """Validate the identity layers present in a semantic record."""

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


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    return CandidateIdentity(
        CANDIDATE_ID=candidate_id_for_semantics(record),
        SIGNATURE_HASH=DESIGN_SIGNATURE_SHA256,
        CANONICAL_SEMANTIC_JSON=canonical_semantic_json(record),
    )


def _semantic_record() -> dict[str, object]:
    return {
        "AUTHORITY_TYPE": "PREDICTION_PRODUCING_V1_DESIGN_AUTHORITY",
        "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
        "CANDIDATE_CONSTRUCTION_RULE": CANDIDATE_CONSTRUCTION_RULE,
        "CANDIDATE_ID": CANDIDATE_ID,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COMPONENT_NORMALIZATION": COMPONENT_NORMALIZATION,
        "COMPONENT_NORMALIZATION_CLASS": COMPONENT_NORMALIZATION_CLASS,
        "COMPONENT_NORMALIZATION_RULE": COMPONENT_NORMALIZATION_RULE_LINES,
        "COMPONENT_SCORE_DOMAIN_1": COMPONENT_SCORE_DOMAIN_1,
        "COMPONENT_SCORE_DOMAIN_2": COMPONENT_SCORE_DOMAIN_2,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "ENTROPY_EXPECTED_COUNT": "300/49",
        "ENTROPY_SCORE_RULE": ENTROPY_SCORE_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "FUSION": FUSION,
        "FUSION_FORMULA": FUSION_FORMULA,
        "FUSION_WEIGHT_1": FUSION_WEIGHT_1_TEXT,
        "FUSION_WEIGHT_2": FUSION_WEIGHT_2_TEXT,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HOT_COLD_POOL_CARDINALITY": HOT_COLD_POOL_CARDINALITY,
        "HOT_COLD_SCORE_RULE": HOT_COLD_SCORE_RULE,
        "IMPLEMENTATION_MODULE": IMPLEMENTATION_MODULE,
        "IMPLEMENTATION_READY": "YES",
        "IMPLEMENTATION_SYMBOL": IMPLEMENTATION_SYMBOL,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_LEVEL": METHOD_LEVEL,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE_LINES,
        "NUMBER_TIE_BREAK_RULE": NUMBER_TIE_BREAK_RULE_LINES,
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
CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = (
    MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
)
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS

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
CANDIDATE_AUTHORITIES: Final[tuple[CandidateMetadata, ...]] = (CANDIDATE_METADATA,)
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
    "CANDIDATE_CONSTRUCTION",
    "CANDIDATE_CONSTRUCTION_RULE",
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
    "COMPONENT_NORMALIZATION_RULE_LINES",
    "COMPONENT_SCORE_DOMAIN_1",
    "COMPONENT_SCORE_DOMAIN_2",
    "DESIGN_ID",
    "DESIGN_SIGNATURE_SHA256",
    "DETERMINISM_CLASS",
    "ENTROPY_SCORE_RULE",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FALLBACK_RULE",
    "FEATURE_1",
    "FEATURE_2",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "HISTORY_ORDER",
    "HOT_COLD_POOL_CARDINALITY",
    "HOT_COLD_SCORE_RULE",
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
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "calculate_entropy_components",
    "calculate_entropy_ranking",
    "calculate_entropy_raw_scores",
    "calculate_fused_number_ranking",
    "calculate_hot_cold_components",
    "calculate_hot_cold_ranking",
    "calculate_hot_cold_raw_scores",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_component_50",
    "entropy_components",
    "fuse_pairwise_scores",
    "hot_cold_component_50",
    "hot_cold_components",
    "produce_biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_entropy_scores",
    "rank_hot_cold_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
