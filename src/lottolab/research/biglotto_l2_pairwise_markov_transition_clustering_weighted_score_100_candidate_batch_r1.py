"""Causal deterministic BigLotto TRANSITION_MARKOV + CLUSTERING candidate.

This research-only module implements the single candidate sealed by
``B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1``.

The frozen candidate first builds a ten-number pool from a scalar W=100
temporal-profile clustering of all legal numbers.  It then ranks those ten
medoids by an exact W=100 anchor-conditioned transition score and fuses the
two exact rank vectors with equal weights.  The module has no outcome access,
I/O, randomness, historical execution path, or production-catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice, pairwise
from types import MappingProxyType
from typing import Final, cast

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TransitionMatrix = tuple[tuple[int, ...], ...]
type ProbabilityMatrix = tuple[tuple[Fraction, ...], ...]
type Profile = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_d9930aebfbbee697"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "a52bd1796db0ede5f57c5032b05a52b3f0624ea5c51b4f2ac54cf11dd42448ff"
)

FEATURE_1: Final[str] = "TRANSITION_MARKOV"
FEATURE_2: Final[str] = "CLUSTERING"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = "TEN_CLUSTER_MEDOIDS_SELECTED_FROM_ALL_LEGAL_NUMBERS_1_TO_49"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "ANCHOR_DRAW=history[T-1];TRANSITION_COUNT_100(a,n)="
    "COUNT_PAIRS(D_j_CONTAINS_a,D_(j+1)_CONTAINS_n) over DRAWS_100="
    "history[T-101:T];OUTGOING_COUNT_100(a)=SUM_n(TRANSITION_COUNT_100(a,n));"
    "P_100(n|a)=TRANSITION_COUNT_100(a,n)/OUTGOING_COUNT_100(a);EXACT_RATIONAL;"
    "ZERO_IF_OUTGOING_ZERO;MARKOV_SCORE_100(n)=SUM_{a_IN_ANCHOR}(P_100(n|a))/6;"
    "NO_GLOBAL_RENORMALIZATION;HIGHER_IS_BETTER;RAW_TIES_MARKOV_SCORE_DESCENDING"
    "_THEN_NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "PROFILE_100(n)=COUNT_100(n)/100;COUNT_100(n)="
    "SUM_{t=T-100}^{T-1}(1_IF_n_IN_SIX_MAIN_NUMBERS(history[t]));EXACT_RATIONAL;"
    "49_SINGLETON_NUMBER_CLUSTERS;HIERARCHICAL_AGGLOMERATIVE_COMPLETE_LINK_UNTIL_10"
    "_CLUSTERS;POINT_DISTANCE=EXACT_MEAN_L1;MERGE_TIE="
    "DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC;MEDOID=MINIMUM_TOTAL_"
    "EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING;CLUSTER_COMPACTNESS="
    "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE;CLUSTER_ORDER="
    "SIZE_DESC_COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC;"
    "ONE_MEDOID_PER_CLUSTER;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];MARKOV_TRANSITION_DRAWS="
    "history[T-101:T];W=100;100_ADJACENT_TRANSITIONS;FINAL_DESTINATION="
    "history[T-1];TARGET_ROW_history[T] EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CLUSTER_PROFILE_DRAWS="
    "history[T-100:T];W=100;EXACT_OCCURRENCE_RATE_VECTOR_100;TARGET_ROW_"
    "history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the deterministic ten-medoid pool from all legal numbers 1..49 using "
        "the frozen CLUSTERING parent rules."
    ),
    "Compute the exact TRANSITION_MARKOV raw score for every medoid in that ten-number pool.",
    (
        "Use the frozen cluster order as the CLUSTERING component order for the same "
        "ten medoids; rank both components within the ten-medoid pool."
    ),
    (
        "Normalize one-based position p as (10-p)/9; best rank is 1 and worst rank "
        "is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, or "
        "outcome-derived normalization."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MARKOV_RAW_SCORE_FOR_EACH_OF_10_CLUSTER_MEDOIDS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = "EXACT_CLUSTER_ORDER_SCORE_FOR_EACH_OF_10_CLUSTER_MEDOIDS"

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(m)=1/2*TRANSITION_MARKOV_NORMALIZED_RANK_10(m)+"
    "1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m);EXACT_RATIONAL"
)

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "TRANSITION_MARKOV normalized rank descending.",
    "CLUSTERING normalized cluster-order rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "TRANSITION_MARKOV parent raw-score tie: Markov score descending, then number ascending.",
    (
        "CLUSTERING parent tie: cluster size descending, compactness ascending, "
        "medoid cost ascending, representative number ascending."
    ),
    (
        "Final pairwise tie: minimum component rank descending, TRANSITION_MARKOV "
        "rank descending, CLUSTERING rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "CLUSTER_SELECTION"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_10_DETERMINISTIC_CLUSTER_MEDOIDS_FROM_ALL_49_LEGAL_NUMBERS_USING_PARENT"
    "_CLUSTERING_RULES;USE_ONLY_ONE_MEDOID_PER_CLUSTER_AS_FROZEN_POOL;APPLY_PAIRWISE"
    "_SCORE_TO_THE_10_MEDOIDS;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_CLUSTER_MEDOIDS;SORT_TICKET_NUMBERS_ASCENDING;"
    "EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;MARKOV_TRANSITION_DRAWS=history[T-101:T];"
    "CLUSTER_PROFILE_DRAWS=history[T-100:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;PAIRWISE_WINDOW=100_PARENT_CONSTANT;MARKOV_ANCHOR=HISTORY[T-1];"
    "MARKOV_TRANSITION_WINDOW=100;CLUSTER_PROFILE_WINDOW=100;CLUSTER_TARGET_COUNT=10;"
    "COMPLETE_LINK;EXACT_MEAN_L1;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "LAG_DEPENDENCE_SIGNAL"
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change W=100, the 1/2 and 1/2 weights, or exact-rational arithmetic.",
    (
        "Do not change the Markov anchor, 100 adjacent-transition window, "
        "zero-outgoing rule, or no-global-renormalization rule."
    ),
    (
        "Do not change the clustering profile, complete-link algorithm, exact "
        "mean-L1 distance, 10-cluster target, medoid rule, cluster-order rule, "
        "or one-medoid-per-cluster pool."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, "
        "outcome tuning, or historical optimization."
    ),
    "Do not read target-row outcomes or any future suffix.",
    (
        "Do not change the ten-medoid pool, final tie-break order, first-6 "
        "single-ticket rule, minimum history, or fallback."
    ),
    "Do not wire this candidate into the production catalog in the implementation task.",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 751 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores and rank normalization for one ten-number component."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: tuple[Fraction, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the ten-medoid pool") from error

    def raw_score(self, number: int) -> Fraction:
        return self.RAW_SCORES[self._pool_position(number)]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        return self.POSITIONS[self._pool_position(number)]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[self._pool_position(number)]

    @property
    def SCORES(self) -> tuple[Fraction, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

    @property
    def POOL_NORMALIZED_RANKS(self) -> tuple[Fraction, ...]:
        return self.NORMALIZED_RANKS


@dataclass(frozen=True, slots=True)
class TemporalProfileState:
    """Exact scalar W=100 occurrence profiles and mean-L1 distances."""

    OCCURRENCE_COUNTS: tuple[int, ...]
    PROFILES: tuple[Profile, ...]
    PAIRWISE_DISTANCES: tuple[tuple[Fraction, ...], ...]

    def count_100(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1]

    def profile(self, number: int) -> Profile:
        _validate_number(number)
        return self.PROFILES[number - 1]

    def profile_distance(self, number_a: int, number_b: int) -> Fraction:
        _validate_number(number_a)
        _validate_number(number_b)
        return self.PAIRWISE_DISTANCES[number_a - 1][number_b - 1]


@dataclass(frozen=True, slots=True)
class ClusterPartition:
    """Deterministic complete-link partition and ordered ten-medoid pool."""

    PROFILES: tuple[Profile, ...]
    PAIRWISE_DISTANCES: tuple[tuple[Fraction, ...], ...]
    CLUSTERS: tuple[tuple[int, ...], ...]
    REPRESENTATIVES: tuple[int, ...]
    MEDOID_COSTS: tuple[Fraction, ...]
    COMPACTNESS_SCORES: tuple[Fraction, ...]
    ORDERED_CLUSTERS: tuple[tuple[int, ...], ...]
    ORDERED_REPRESENTATIVES: tuple[int, ...]

    @property
    def SOURCE_NUMBER_POOL(self) -> tuple[int, ...]:
        return self.ORDERED_REPRESENTATIVES

    def cluster_size(self, cluster_index: int) -> int:
        return len(self.ORDERED_CLUSTERS[cluster_index])

    def representative(self, cluster_index: int) -> int:
        return self.ORDERED_REPRESENTATIVES[cluster_index]


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score for one of the ten medoids."""

    NUMBER: int
    TRANSITION_MARKOV_COMPONENT: Fraction
    CLUSTERING_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def TRANSITION_MARKOV_RANK_100(self) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENT

    @property
    def CLUSTERING_RANK_100(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def MARKOV_COMPONENT(self) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All ten fused medoid ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    TRANSITION_MARKOV_COMPONENTS: tuple[Fraction, ...]
    CLUSTERING_COMPONENTS: tuple[Fraction, ...]
    PAIRWISE_SCORES: tuple[Fraction, ...]
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

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the ten-medoid pool") from error

    def transition_markov_component(self, number: int) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENTS[self._pool_position(number)]

    def markov_component(self, number: int) -> Fraction:
        return self.transition_markov_component(number)

    def clustering_component(self, number: int) -> Fraction:
        return self.CLUSTERING_COMPONENTS[self._pool_position(number)]

    def pairwise_score(self, number: int) -> Fraction:
        return self.PAIRWISE_SCORES[self._pool_position(number)]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        if number not in self.POOL_NUMBERS:
            raise ValueError("number is not in the ten-medoid pool")
        return self.POSITIONS[number - 1]

    def score_record(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError("number must be an integer in 1..49")


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    """Read exactly the causal prefix and leave the suffix untouched."""

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
            raise ValueError(f"history[{draw_index}][{position}] must be in 1..49")
        numbers.append(raw_number)
    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return an immutable validated copy of only the strictly prior prefix."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _validate_transition_matrix(
    raw_counts: Sequence[Sequence[object]],
) -> TransitionMatrix:
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(raw_counts) != domain_size:
        raise ValueError("transition_counts must contain exactly 49 rows")
    rows: list[tuple[int, ...]] = []
    for row_index, raw_row in enumerate(raw_counts):
        if len(raw_row) != domain_size:
            raise ValueError(
                f"transition_counts[{row_index}] must contain exactly 49 columns"
            )
        row: list[int] = []
        for column_index, raw_value in enumerate(raw_row):
            if type(raw_value) is not int or raw_value < 0:
                raise ValueError(
                    f"transition_counts[{row_index}][{column_index}] must be a non-negative integer"
                )
            row.append(raw_value)
        rows.append(tuple(row))
    return tuple(rows)


def build_transition_counts(draws: Iterable[HistoryDraw]) -> TransitionMatrix:
    """Count every ordered pair across adjacent draws exactly once."""

    validated_draws = tuple(
        _validate_draw(raw_draw, draw_index) for draw_index, raw_draw in enumerate(draws)
    )
    mutable_counts = [[0] * 49 for _ in range(49)]
    for source_draw, destination_draw in pairwise(validated_draws):
        for source_number in source_draw:
            for destination_number in destination_draw:
                mutable_counts[source_number - 1][destination_number - 1] += 1
    counts = _validate_transition_matrix(tuple(tuple(row) for row in mutable_counts))
    expected_total = max(0, len(validated_draws) - 1) * PICK_COUNT * PICK_COUNT
    if sum(map(sum, counts)) != expected_total:
        raise RuntimeError("each adjacent draw pair must contribute exactly 36 transitions")
    return counts


def calculate_outgoing_counts(
    transition_counts: Sequence[Sequence[object]],
) -> tuple[int, ...]:
    counts = _validate_transition_matrix(transition_counts)
    return tuple(sum(row) for row in counts)


def calculate_conditional_transition_probabilities(
    transition_counts: Sequence[Sequence[object]],
    outgoing_counts: Sequence[object] | None = None,
) -> ProbabilityMatrix:
    """Return unsmoothed exact conditional probabilities, including zero rows."""

    counts = _validate_transition_matrix(transition_counts)
    expected_outgoing = calculate_outgoing_counts(counts)
    if outgoing_counts is None:
        denominators = expected_outgoing
    else:
        if len(outgoing_counts) != 49:
            raise ValueError("outgoing_counts must contain exactly 49 values")
        raw_denominators = tuple(outgoing_counts)
        if any(type(value) is not int or value < 0 for value in raw_denominators):
            raise ValueError("outgoing_counts must contain non-negative integers")
        denominators = cast(tuple[int, ...], raw_denominators)
        if denominators != expected_outgoing:
            raise ValueError("outgoing_counts must equal exact transition row sums")

    probabilities: list[tuple[Fraction, ...]] = []
    for row, denominator in zip(counts, denominators, strict=True):
        if denominator == 0:
            probabilities.append((Fraction(0, 1),) * 49)
        else:
            probabilities.append(tuple(Fraction(value, denominator) for value in row))
    return tuple(probabilities)


calculate_transition_probabilities = calculate_conditional_transition_probabilities


def _markov_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> tuple[Fraction, ...]:
    if len(prior_history) < WINDOW + 1:
        raise InsufficientHistoryError(
            f"window {WINDOW} requires at least {WINDOW + 1} prior draws"
        )
    window_draws = prior_history[-(WINDOW + 1) :]
    anchor_draw = window_draws[-1]
    transition_counts = build_transition_counts(window_draws)
    outgoing_counts = calculate_outgoing_counts(transition_counts)
    probabilities = calculate_conditional_transition_probabilities(
        transition_counts, outgoing_counts
    )
    scores = [Fraction(0, 1)] * 49
    for anchor_number in anchor_draw:
        row = probabilities[anchor_number - 1]
        for candidate_number, probability in enumerate(row, start=1):
            scores[candidate_number - 1] += probability / PICK_COUNT
    expected_mass = Fraction(
        sum(outgoing_counts[number - 1] > 0 for number in anchor_draw), PICK_COUNT
    )
    if sum(scores, Fraction(0, 1)) != expected_mass:
        raise RuntimeError("anchor-conditioned transition probability mass invariant failed")
    return tuple(scores)


def calculate_markov_raw_scores(
    history: HistoryInput, target_index: int
) -> tuple[Fraction, ...]:
    """Return the exact anchor-conditioned W=100 score for every legal number."""

    return _markov_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


calculate_transition_markov_raw_scores = calculate_markov_raw_scores
calculate_markov_scores = calculate_markov_raw_scores


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain exactly 10 legal numbers")
    for number in pool:
        _validate_number(number)
    if len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain ten unique legal numbers")
    return pool


def _exact_number_scores(
    values: Sequence[object] | Mapping[int, object], name: str
) -> tuple[Fraction, ...]:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != 49 or set(keys) != set(range(1, 50)):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
    else:
        raw_values = tuple(values)
        if len(raw_values) != 49:
            raise ValueError(f"{name} must contain exactly 49 values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            converted.append(value)
        elif type(value) is int:
            converted.append(Fraction(value, 1))
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
    return tuple(converted)


def _rank_pool_raw_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    name: str,
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    scores = _exact_number_scores(raw_scores, name)
    ordered_numbers = tuple(sorted(pool, key=lambda number: (-scores[number - 1], number)))
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized_ranks = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered_numbers, start=1):
        pool_position = pool.index(number)
        positions[pool_position] = position
        normalized_ranks[pool_position] = Fraction(
            RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1
        )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=tuple(scores[number - 1] for number in pool),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def rank_markov_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank exact Markov raw scores only within the frozen ten-number pool."""

    return _rank_pool_raw_scores(raw_scores, pool_numbers, "markov_raw_scores")


rank_transition_markov_scores = rank_markov_scores


def _profiles_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> TemporalProfileState:
    if len(prior_history) < WINDOW:
        raise InsufficientHistoryError(
            f"window {WINDOW} requires at least {WINDOW} prior draws"
        )
    profile_draws = prior_history[-WINDOW:]
    counts = [0] * 49
    for draw in profile_draws:
        for number in draw:
            counts[number - 1] += 1
    profiles: tuple[Profile, ...] = tuple(
        (Fraction(counts[number - 1], WINDOW),) for number in range(1, 50)
    )
    distances: list[tuple[Fraction, ...]] = []
    for number_a in range(1, 50):
        row: list[Fraction] = []
        for number_b in range(1, 50):
            if number_a == number_b:
                row.append(Fraction(0, 1))
            elif number_b < number_a:
                row.append(distances[number_b - 1][number_a - 1])
            else:
                row.append(compute_point_distance(profiles[number_a - 1], profiles[number_b - 1]))
        distances.append(tuple(row))
    return TemporalProfileState(
        OCCURRENCE_COUNTS=tuple(counts),
        PROFILES=profiles,
        PAIRWISE_DISTANCES=tuple(distances),
    )


def calculate_temporal_profiles(
    history: HistoryInput, target_index: int
) -> TemporalProfileState:
    """Calculate the exact scalar occurrence-rate profile over history[T-100:T]."""

    return _profiles_from_prior_history(validate_prior_history(history, target_index))


def compute_point_distance(profile_a: Profile, profile_b: Profile) -> Fraction:
    """Return exact mean L1 distance between equal-dimensional profiles."""

    if len(profile_a) == 0 or len(profile_a) != len(profile_b):
        raise ValueError("profiles must have the same non-zero dimension")
    return sum(
        (abs(a - b) for a, b in zip(profile_a, profile_b, strict=True)),
        Fraction(0, 1),
    ) / len(profile_a)


def perform_hierarchical_clustering(
    profile_state: TemporalProfileState,
) -> ClusterPartition:
    """Perform deterministic complete-link clustering until ten clusters remain."""

    clusters: list[tuple[int, ...]] = [(number,) for number in range(1, 50)]
    pair_distances = profile_state.PAIRWISE_DISTANCES
    while len(clusters) > RANKED_POOL_CARDINALITY:
        best_candidate: (
            tuple[tuple[Fraction, tuple[int, ...], tuple[int, ...]], int, int] | None
        ) = None
        for index_a in range(len(clusters)):
            for index_b in range(index_a + 1, len(clusters)):
                cluster_a = clusters[index_a]
                cluster_b = clusters[index_b]
                complete_distance = max(
                    pair_distances[number_a - 1][number_b - 1]
                    for number_a in cluster_a
                    for number_b in cluster_b
                )
                left = min(cluster_a, cluster_b)
                right = max(cluster_a, cluster_b)
                key = (complete_distance, left, right)
                if best_candidate is None or key < best_candidate[0]:
                    best_candidate = (key, index_a, index_b)
        if best_candidate is None:
            raise RuntimeError("clustering failed to find valid merge pair")
        _, index_a, index_b = best_candidate
        merged = tuple(sorted(set(clusters[index_a]) | set(clusters[index_b])))
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in (index_a, index_b)
        ] + [merged]

    if len(clusters) != RANKED_POOL_CARDINALITY:
        raise RuntimeError("clustering did not produce exactly ten clusters")
    if sorted(number for cluster in clusters for number in cluster) != list(range(1, 50)):
        raise RuntimeError("cluster partition does not cover legal numbers 1..49")

    cluster_records: list[dict[str, object]] = []
    for cluster in clusters:
        medoid_costs_by_number: dict[int, Fraction] = {
            number: sum(
                (pair_distances[number - 1][member - 1] for member in cluster),
                Fraction(0, 1),
            )
            for number in cluster
        }
        representative = min(
            cluster, key=lambda number: (medoid_costs_by_number[number], number)
        )
        medoid_cost = medoid_costs_by_number[representative]
        if len(cluster) <= 1:
            compactness = Fraction(0, 1)
        else:
            pairwise_sum = sum(
                (
                    pair_distances[number_a - 1][number_b - 1]
                    for number_a, number_b in combinations(cluster, 2)
                ),
                Fraction(0, 1),
            )
            pair_count = Fraction(len(cluster) * (len(cluster) - 1), 2)
            compactness = pairwise_sum / pair_count
        cluster_records.append(
            {
                "cluster": cluster,
                "representative": representative,
                "medoid_cost": medoid_cost,
                "compactness": compactness,
                "sort_key": (-len(cluster), compactness, medoid_cost, representative),
            }
        )
    cluster_records.sort(key=lambda record: cast(tuple[object, ...], record["sort_key"]))
    ordered_clusters = tuple(
        cast(tuple[int, ...], record["cluster"]) for record in cluster_records
    )
    ordered_representatives = tuple(
        cast(int, record["representative"]) for record in cluster_records
    )
    ordered_medoid_costs = tuple(
        cast(Fraction, record["medoid_cost"]) for record in cluster_records
    )
    compactness_scores = tuple(
        cast(Fraction, record["compactness"]) for record in cluster_records
    )
    if len(set(ordered_representatives)) != RANKED_POOL_CARDINALITY:
        raise RuntimeError("cluster representatives contain duplicates")
    return ClusterPartition(
        PROFILES=profile_state.PROFILES,
        PAIRWISE_DISTANCES=pair_distances,
        CLUSTERS=tuple(clusters),
        REPRESENTATIVES=ordered_representatives,
        MEDOID_COSTS=ordered_medoid_costs,
        COMPACTNESS_SCORES=compactness_scores,
        ORDERED_CLUSTERS=ordered_clusters,
        ORDERED_REPRESENTATIVES=ordered_representatives,
    )


def _cluster_partition_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> ClusterPartition:
    return perform_hierarchical_clustering(_profiles_from_prior_history(prior_history))


def calculate_cluster_partition(
    history: HistoryInput, target_index: int
) -> ClusterPartition:
    """Calculate the causal W=100 complete-link ten-cluster partition."""

    return _cluster_partition_from_prior_history(validate_prior_history(history, target_index))


def _clustering_raw_scores_from_partition(
    partition: ClusterPartition,
) -> tuple[Fraction, ...]:
    raw_scores = [Fraction(0, 1)] * 49
    for position, number in enumerate(partition.ORDERED_REPRESENTATIVES, start=1):
        raw_scores[number - 1] = Fraction(
            RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1
        )
    return tuple(raw_scores)


def rank_clustering_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank the frozen cluster-order scores inside the ten-medoid pool."""

    return _rank_pool_raw_scores(raw_scores, pool_numbers, "clustering_raw_scores")


def _clustering_ranking_from_partition(partition: ClusterPartition) -> ComponentRanking:
    return rank_clustering_scores(
        _clustering_raw_scores_from_partition(partition),
        partition.ORDERED_REPRESENTATIVES,
    )


def calculate_clustering_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return _clustering_ranking_from_partition(
        calculate_cluster_partition(history, target_index)
    )


def calculate_clustering_components(
    history: HistoryInput, target_index: int
) -> tuple[Fraction, ...]:
    return calculate_clustering_ranking(history, target_index).POOL_NORMALIZED_RANKS


clustering_components = calculate_clustering_components


def _markov_ranking_from_prior_history(
    prior_history: tuple[HistoryDraw, ...], pool_numbers: Sequence[int]
) -> ComponentRanking:
    return rank_markov_scores(
        _markov_raw_scores_from_prior_history(prior_history), pool_numbers
    )


def calculate_markov_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    prior_history = validate_prior_history(history, target_index)
    partition = _cluster_partition_from_prior_history(prior_history)
    return _markov_ranking_from_prior_history(
        prior_history, partition.ORDERED_REPRESENTATIVES
    )


def calculate_transition_markov_components(
    history: HistoryInput, target_index: int
) -> tuple[Fraction, ...]:
    return calculate_markov_ranking(history, target_index).POOL_NORMALIZED_RANKS


transition_markov_components = calculate_transition_markov_components
markov_components = calculate_transition_markov_components


def _exact_pool_components(
    values: Sequence[object] | Mapping[int, object],
    pool_numbers: tuple[int, ...],
    name: str,
) -> tuple[Fraction, ...]:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if set(keys) != set(pool_numbers) or len(keys) != len(pool_numbers):
            raise ValueError(f"{name} mapping must contain exactly the ten pool numbers")
        raw_values = tuple(values[number] for number in pool_numbers)
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly ten values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            converted.append(value)
        elif type(value) is int:
            converted.append(Fraction(value, 1))
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
    result = tuple(converted)
    if any(value < 0 or value > 1 for value in result):
        raise ValueError(f"{name} must lie in [0,1]")
    return result


def rank_pairwise_scores(
    transition_markov_components: Sequence[object] | Mapping[int, object],
    clustering_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> PairwiseRanking:
    """Fuse two exact normalized ten-medoid components and rank the pool."""

    pool = _validate_pool(pool_numbers)
    markov = _exact_pool_components(
        transition_markov_components, pool, "transition_markov_components"
    )
    clustering = _exact_pool_components(
        clustering_components, pool, "clustering_components"
    )
    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * markov[index] + FUSION_WEIGHT_2 * clustering[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, pairwise_scores, strict=True))
    markov_by_number = dict(zip(pool, markov, strict=True))
    clustering_by_number = dict(zip(pool, clustering, strict=True))
    ranked_numbers = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(markov_by_number[number], clustering_by_number[number]),
                -markov_by_number[number],
                -clustering_by_number[number],
                number,
            ),
        )
    )
    positions = [0] * 49
    for position, number in enumerate(ranked_numbers, start=1):
        positions[number - 1] = position
    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            TRANSITION_MARKOV_COMPONENT=markov_by_number[number],
            CLUSTERING_COMPONENT=clustering_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(markov_by_number[number], clustering_by_number[number]),
            POSITION=positions[number - 1],
        )
        for number in ranked_numbers
    )
    ticket = cast(Ticket, tuple(sorted(ranked_numbers[:PICK_COUNT])))
    if len(ticket) != PICK_COUNT or len(set(ticket)) != PICK_COUNT:
        raise RuntimeError("pairwise native ticket must contain six unique numbers")
    if not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket):
        raise RuntimeError("pairwise native ticket must contain legal numbers")
    return PairwiseRanking(
        POOL_NUMBERS=pool,
        TRANSITION_MARKOV_COMPONENTS=markov,
        CLUSTERING_COMPONENTS=clustering,
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
    """Calculate the final causal ranking from both sealed components."""

    prior_history = validate_prior_history(history, target_index)
    partition = _cluster_partition_from_prior_history(prior_history)
    pool = partition.ORDERED_REPRESENTATIVES
    markov_ranking = _markov_ranking_from_prior_history(prior_history, pool)
    clustering_ranking = _clustering_ranking_from_partition(partition)
    return rank_pairwise_scores(
        markov_ranking.POOL_NORMALIZED_RANKS,
        clustering_ranking.POOL_NORMALIZED_RANKS,
        pool,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first-six ticket from the final medoid ranking."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate = (
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
    """The selected candidate identity and sealed signature."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable metadata for the single frozen candidate."""

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


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    return CandidateIdentity(
        CANDIDATE_ID=candidate_id_for_semantics(record),
        SIGNATURE_HASH=DESIGN_SIGNATURE_SHA256,
        CANONICAL_SEMANTIC_JSON=canonical_semantic_json(record),
    )


def _design_signature_object() -> dict[str, object]:
    return {
        "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
        "CANDIDATE_CONSTRUCTION_RULE": CANDIDATE_CONSTRUCTION_RULE,
        "CANDIDATE_ID": CANDIDATE_ID,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COMPONENT_NORMALIZATION_RULE": COMPONENT_NORMALIZATION_RULE_LINES,
        "COMPONENT_SCORE_DOMAIN_1": COMPONENT_SCORE_DOMAIN_1,
        "COMPONENT_SCORE_DOMAIN_2": COMPONENT_SCORE_DOMAIN_2,
        "DESIGN_ID": DESIGN_ID,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FALLBACK_RULE": FALLBACK_RULE,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "FORBIDDEN_SEMANTIC_CHANGES": FORBIDDEN_SEMANTIC_CHANGES,
        "FUSION": FUSION,
        "FUSION_FORMULA": FUSION_FORMULA,
        "FUSION_WEIGHT_1": FUSION_WEIGHT_1_TEXT,
        "FUSION_WEIGHT_2": FUSION_WEIGHT_2_TEXT,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_LEVEL": METHOD_LEVEL,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN_TEXT,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE_LINES,
        "NUMBER_TIE_BREAK_RULE": NUMBER_TIE_BREAK_RULE_LINES,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PARENT_COMPONENT_RULE_1": PARENT_COMPONENT_RULE_1,
        "PARENT_COMPONENT_RULE_2": PARENT_COMPONENT_RULE_2,
        "PARENT_SOURCE_UNIVERSE_ID_1": PARENT_SOURCE_UNIVERSE_ID_1,
        "PARENT_SOURCE_UNIVERSE_ID_2": PARENT_SOURCE_UNIVERSE_ID_2,
        "PARENT_WINDOW_RULE_1": PARENT_WINDOW_RULE_1,
        "PARENT_WINDOW_RULE_2": PARENT_WINDOW_RULE_2,
        "RANKED_POOL_CARDINALITY": RANKED_POOL_CARDINALITY,
        "RANKED_POOL_DOMAIN": RANKED_POOL_DOMAIN,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "TICKET_CONSTRUCTION": TICKET_CONSTRUCTION,
        "TICKET_SELECTION_RULE": TICKET_SELECTION_RULE,
        "WINDOW": WINDOW,
    }


CANDIDATE_SEMANTICS: Final[Mapping[str, object]] = MappingProxyType(
    _design_signature_object()
)
DESIGN_SIGNATURE_OBJECT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS
CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = (
    MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
)
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS

if signature_hash_for_semantics(CANDIDATE_SEMANTICS) != DESIGN_SIGNATURE_SHA256:
    raise RuntimeError("sealed design signature does not match candidate semantics")

CANDIDATE_METADATA: Final[CandidateMetadata] = CandidateMetadata(
    CANDIDATE_ID=CANDIDATE_ID,
    SELECTED_GAP_ID=SELECTED_GAP_ID,
    DESIGN_ID=DESIGN_ID,
    DESIGN_SIGNATURE_SHA256=DESIGN_SIGNATURE_SHA256,
    FEATURE_1=FEATURE_1,
    FEATURE_2=FEATURE_2,
    WINDOW=WINDOW,
    COMPONENT_NORMALIZATION_RULE=";".join(COMPONENT_NORMALIZATION_RULE_LINES),
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
    "COMPONENT_NORMALIZATION_RULE",
    "COMPONENT_NORMALIZATION_RULE_LINES",
    "COMPONENT_SCORE_DOMAIN_1",
    "COMPONENT_SCORE_DOMAIN_2",
    "DESIGN_ID",
    "DESIGN_SIGNATURE_OBJECT",
    "DESIGN_SIGNATURE_SHA256",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FALLBACK_RULE",
    "FEATURE_1",
    "FEATURE_2",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "ClusterPartition",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "TemporalProfileState",
    "build_source_ticket_universe",
    "build_transition_counts",
    "calculate_cluster_partition",
    "calculate_clustering_components",
    "calculate_clustering_ranking",
    "calculate_conditional_transition_probabilities",
    "calculate_fused_number_ranking",
    "calculate_markov_ranking",
    "calculate_markov_raw_scores",
    "calculate_outgoing_counts",
    "calculate_pairwise_ranking",
    "calculate_temporal_profiles",
    "calculate_transition_markov_components",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "clustering_components",
    "compute_point_distance",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "perform_hierarchical_clustering",
    "produce_biglotto_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_clustering_scores",
    "rank_markov_scores",
    "rank_pairwise_scores",
    "rank_transition_markov_scores",
    "signature_hash_for_semantics",
    "transition_markov_components",
    "validate_history",
    "validate_prior_history",
]
