"""Causal deterministic BigLotto FREQUENCY + CLUSTERING candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_FREQUENCY_CLUSTERING_WEIGHTED_SCORE_100_V1``.  It reuses the
sealed multiscale temporal-profile clustering parent for the ten-medoid pool
and reproduces the frozen multiscale occurrence-frequency component locally.
Both pool-local rank vectors are fused with equal exact rational weights.

The producer reads only the strictly prior history prefix.  It has no outcome
access, I/O, randomness, empirical calibration, or production catalog
integration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1,
)

_clustering_parent = biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_cca5660423304b0b"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_FREQUENCY_CLUSTERING_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "1b1b37dce223f79f46e0930e9df27547ebe8daa9741e068729b5636bb9686399"
)

FEATURE_1: Final[str] = "FREQUENCY"
FEATURE_2: Final[str] = "CLUSTERING"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
COMPONENT_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
FREQUENCY_WINDOWS: Final[tuple[int, int, int]] = COMPONENT_WINDOWS
CLUSTER_PROFILE_WINDOWS: Final[tuple[int, int, int]] = COMPONENT_WINDOWS
MINIMUM_HISTORY: Final[int] = 750
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = (
    "TEN_CLUSTER_MEDOIDS_SELECTED_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1"
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "FREQUENCY_PARENT=B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(50,300,750);"
    "WINDOW_DRAWS=history[T-W:T];OCCURRENCE_COUNT(n,W)="
    "SUM(1_IF_n_OCCURS_IN_DRAW_ELSE_0);OCCURRENCE_RATE(n,W)="
    "OCCURRENCE_COUNT(n,W)/W;MULTISCALE_FREQUENCY_SCORE="
    "MEAN_EXACT_RATIONAL_OF_WINDOW_OCCURRENCE_RATES;FREQUENCY_RANK="
    "MULTISCALE_FREQUENCY_SCORE_DESC_TOTAL_OCCURRENCE_COUNT_DESC_NUMBER_ASC;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "CLUSTER_PARENT=B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;TEMPORAL_PROFILE(n)="
    "(OCCURRENCE_RATE_50,OCCURRENCE_RATE_300,OCCURRENCE_RATE_750);"
    "PROFILE_COORDINATE_WEIGHT=EXACT_EQUAL_ONE_THIRD;POINT_DISTANCE=EXACT_MEAN_L1;"
    "INITIAL_CLUSTERS=49_SINGLETON_NUMBER_CLUSTERS;ALGORITHM=HIERARCHICAL_AGGLOMERATIVE;"
    "LINKAGE=COMPLETE_LINK;STOP_AT_EXACTLY_10_CLUSTERS;MERGE_TIE="
    "DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC;MEDOID=MINIMUM_TOTAL_"
    "EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING;CLUSTER_COMPACTNESS="
    "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE;CLUSTER_ORDER="
    "SIZE_DESC_COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC;"
    "REPRESENTATIVES_PER_CLUSTER=1;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];FREQUENCY_DRAWS_50="
    "history[T-50:T];FREQUENCY_DRAWS_300=history[T-300:T];"
    "FREQUENCY_DRAWS_750=history[T-750:T];ALL_FREQUENCY_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CLUSTER_PROFILE_DRAWS_50="
    "history[T-50:T];CLUSTER_PROFILE_DRAWS_300=history[T-300:T];"
    "CLUSTER_PROFILE_DRAWS_750=history[T-750:T];ALL_CLUSTER_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact ten-medoid CLUSTERING pool from all 49 legal numbers "
        "using the frozen multiscale temporal-profile parent rules."
    ),
    (
        "Compute the exact multiscale occurrence-frequency score for each of "
        "the ten cluster medoids using the fixed 50, 300, and 750 draw windows."
    ),
    (
        "Use frozen cluster order as the CLUSTERING component order; rank "
        "FREQUENCY scores higher-is-better within the same ten-medoid pool "
        "using multiscale frequency score, total occurrence count, then "
        "number-ascending ties."
    ),
    (
        "Normalize each one-based position p within the ten-medoid pool as "
        "(10-p)/9; best rank is 1 and worst rank is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_OCCURRENCE_FREQUENCY_SCORE_FOR_EACH_OF_10_CLUSTER_MEDOIDS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = "EXACT_CLUSTER_ORDER_SCORE_FOR_EACH_OF_10_CLUSTER_MEDOIDS"

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(m)=1/2*FREQUENCY_NORMALIZED_MULTISCALE_OCCURRENCE_RANK_10(m)+"
    "1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "FREQUENCY normalized multiscale occurrence rank descending.",
    "CLUSTERING normalized cluster-order rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "FREQUENCY parent tie: multiscale frequency score descending, total "
        "occurrence count descending, number ascending."
    ),
    (
        "CLUSTERING parent tie: cluster size descending, compactness ascending, "
        "medoid cost ascending, representative number ascending."
    ),
    (
        "Final pairwise tie: minimum component rank descending, FREQUENCY rank "
        "descending, CLUSTERING rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "CLUSTER_SELECTION"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_10_DETERMINISTIC_CLUSTER_MEDOIDS_FROM_ALL_49_LEGAL_NUMBERS_USING_PARENT_CLUSTERING_RULES;"
    "COMPUTE_MULTISCALE_OCCURRENCE_FREQUENCY_SCORES_FOR_THE_10_MEDOIDS;"
    "RANK_BOTH_COMPONENTS_WITHIN_THE_SAME_10_MEDOID_POOL;FUSE_EQUAL_EXACT_RANKS;"
    "SELECT_FIRST_6_FINAL_PAIRWISE_RANKED_CLUSTER_MEDOIDS;NO_OUTCOME_OR_FUTURE_DATA"
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
    "FUTURE_SUFFIX NEVER_USED;CLUSTER_PROFILE_WINDOWS=(50,300,750);"
    "FREQUENCY_WINDOWS=(50,300,750);ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;TEN_MEDOIDS_REQUIRED;NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "FREQUENCY_WINDOWS=(50,300,750);FREQUENCY_SCORE=MEAN_EXACT_OCCURRENCE_RATE;"
    "CLUSTER_PROFILE_WINDOWS=(50,300,750);CLUSTER_TARGET_COUNT=10;COMPLETE_LINK;"
    "EXACT_MEAN_L1;FRONTIER_WINDOW_LABEL=100;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_OCCURRENCE_FREQUENCY_PLUS_TEMPORAL_PROFILE_DIVERSITY"
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the frequency windows (50,300,750), occurrence-rate definition, "
        "exact multiscale mean, frequency tie-break order, or no-target/future rule."
    ),
    (
        "Do not change the clustering profile windows (50,300,750), equal one-third "
        "profile coordinates, complete-link algorithm, exact mean-L1 distance, "
        "ten-cluster target, merge tie, medoid rule, compactness rule, cluster-order "
        "rule, or one-medoid pool."
    ),
    (
        "Do not change the ten-medoid pool, (10-p)/9 normalization, equal 1/2 and 1/2 "
        "fusion, final tie-break order, first-six single-ticket rule, minimum history, "
        "or fallback."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, outcome "
        "tuning, historical optimization, or randomness."
    ),
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores and normalized ranks for one ten-medoid component."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components
    SECONDARY_SCORES: tuple[int, ...] = ()
    WINDOW_RANKINGS: tuple[object, ...] = ()
    WINDOW_FREQUENCY_RATES: tuple[Components, ...] = ()
    WINDOW_OCCURRENCE_COUNTS: tuple[tuple[int, ...], ...] = ()

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
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

    @property
    def POOL_NORMALIZED_RANKS(self) -> Components:
        return self.NORMALIZED_RANKS


FrequencyRanking = ComponentRanking


@dataclass(frozen=True, slots=True)
class FrequencyWindowRanking:
    """Exact occurrence-frequency statistics and rank order for one window."""

    WINDOW: int
    POOL_NUMBERS: tuple[int, ...]
    OCCURRENCE_RATES: Components
    OCCURRENCE_COUNTS: tuple[int, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def occurrence_rate(self, number: int) -> Fraction:
        return self.OCCURRENCE_RATES[self.POOL_NUMBERS.index(number)]


@dataclass(frozen=True, slots=True)
class FrequencyStatistics:
    """The exact multiscale occurrence-frequency values for one fixed pool."""

    POOL_NUMBERS: tuple[int, ...]
    WINDOW_FREQUENCY_RATES: tuple[Components, ...]
    WINDOW_OCCURRENCE_COUNTS: tuple[tuple[int, ...], ...]
    MULTISCALE_FREQUENCY_SCORES: Components
    TOTAL_OCCURRENCE_COUNTS: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent contributions."""

    NUMBER: int
    FREQUENCY_COMPONENT: Fraction
    CLUSTERING_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def FREQUENCY_RANK_10(self) -> Fraction:
        return self.FREQUENCY_COMPONENT

    @property
    def CLUSTERING_RANK_10(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All ten fused medoid ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    FREQUENCY_COMPONENTS: Components
    CLUSTERING_COMPONENTS: Components
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

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the ten-medoid pool") from error

    def frequency_component(self, number: int) -> Fraction:
        return self.FREQUENCY_COMPONENTS[self._pool_position(number)]

    def clustering_component(self, number: int) -> Fraction:
        return self.CLUSTERING_COMPONENTS[self._pool_position(number)]

    def pairwise_score(self, number: int) -> Fraction:
        return self.PAIRWISE_SCORES[self._pool_position(number)]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.SCORES[self.RANKED_NUMBERS.index(number)].POSITION

    def score_record(self, number: int) -> PairwiseNumberScore:
        _validate_number(number)
        return self.SCORES[self.RANKED_NUMBERS.index(number)]


TemporalProfileState = _clustering_parent.TemporalProfileState
ClusterPartition = _clustering_parent.ClusterPartition
compute_point_distance = _clustering_parent.compute_point_distance
perform_hierarchical_clustering = _clustering_parent.perform_hierarchical_clustering


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError("number must be an integer in 1..49")


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


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return only the strictly prior validated history prefix."""

    if _clustering_parent.MINIMUM_HISTORY != MINIMUM_HISTORY:
        raise RuntimeError("clustering parent minimum history drifted")
    raw_prefix = _read_history_prefix(history, target_index)
    try:
        return _clustering_parent.validate_prior_history(raw_prefix, len(raw_prefix))
    except _clustering_parent.InsufficientHistoryError as error:
        raise InsufficientHistoryError(str(error)) from error


validate_history = validate_prior_history


def calculate_temporal_profiles(
    history: HistoryInput, target_index: int
) -> TemporalProfileState:
    """Call the exact sealed clustering parent on the prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _clustering_parent.calculate_temporal_profiles(
        prior_history, len(prior_history)
    )


def _cluster_partition_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> ClusterPartition:
    partition = _clustering_parent.calculate_cluster_partition(
        prior_history, len(prior_history)
    )
    if (
        len(partition.ORDERED_CLUSTERS) != RANKED_POOL_CARDINALITY
        or len(partition.ORDERED_REPRESENTATIVES) != RANKED_POOL_CARDINALITY
        or len(set(partition.ORDERED_REPRESENTATIVES)) != RANKED_POOL_CARDINALITY
    ):
        raise RuntimeError("clustering parent did not produce exactly ten medoids")
    return partition


def calculate_cluster_partition(
    history: HistoryInput, target_index: int
) -> ClusterPartition:
    """Return the exact sealed ten-cluster partition from prior history."""

    return _cluster_partition_from_prior_history(
        validate_prior_history(history, target_index)
    )


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain exactly ten numbers")
    for number in pool:
        _validate_number(number)
    if len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain ten unique numbers")
    return pool


def _exact_pool_values(
    values: Sequence[object] | Mapping[int, object],
    pool_numbers: tuple[int, ...],
    name: str,
) -> Components:
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
            exact = value
        elif type(value) is int:
            exact = Fraction(value, 1)
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
        if not Fraction(0, 1) <= exact <= Fraction(1, 1):
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        converted.append(exact)
    return tuple(converted)


def _exact_integer_pool_values(
    values: Sequence[int] | Mapping[int, int],
    pool_numbers: tuple[int, ...],
    name: str,
) -> tuple[int, ...]:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if set(keys) != set(pool_numbers) or len(keys) != len(pool_numbers):
            raise ValueError(f"{name} mapping must contain exactly the ten pool numbers")
        raw_values = tuple(values[number] for number in pool_numbers)
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly ten values")
    if any(type(value) is not int or value < 0 for value in raw_values):
        raise TypeError(f"{name} must contain non-negative integers")
    return cast(tuple[int, ...], raw_values)


def _rank_pool_raw_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    name: str,
    secondary_scores: Sequence[int] | Mapping[int, int] | None = None,
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    raw = _exact_pool_values(raw_scores, pool, name)
    secondary = (
        (0,) * RANKED_POOL_CARDINALITY
        if secondary_scores is None
        else _exact_integer_pool_values(secondary_scores, pool, f"{name}_tie_break_1")
    )
    values_by_number = dict(zip(pool, raw, strict=True))
    secondary_by_number = dict(zip(pool, secondary, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -values_by_number[number],
                -secondary_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions_by_number[number] for number in pool),
        NORMALIZED_RANKS=tuple(
            Fraction(
                RANKED_POOL_CARDINALITY - positions_by_number[number],
                RANKED_POOL_CARDINALITY - 1,
            )
            for number in pool
        ),
        SECONDARY_SCORES=secondary,
    )


def _clustering_ranking_from_partition(
    partition: ClusterPartition,
) -> ComponentRanking:
    pool = _validate_pool(partition.ORDERED_REPRESENTATIVES)
    raw = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1)
        for position in range(1, RANKED_POOL_CARDINALITY + 1)
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=pool,
        POSITIONS=tuple(range(1, RANKED_POOL_CARDINALITY + 1)),
        NORMALIZED_RANKS=raw,
    )


def rank_clustering_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank exact clustering scores inside the ten-medoid pool."""

    return _rank_pool_raw_scores(raw_scores, pool_numbers, "clustering_raw_scores")


def calculate_clustering_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    prior_history = validate_prior_history(history, target_index)
    return _clustering_ranking_from_partition(
        _cluster_partition_from_prior_history(prior_history)
    )


def calculate_clustering_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_clustering_ranking(history, target_index).RAW_SCORES


def calculate_clustering_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_clustering_ranking(history, target_index).NORMALIZED_RANKS


clustering_components = calculate_clustering_components


def _frequency_window_metrics(
    prior_history: tuple[HistoryDraw, ...],
    pool_numbers: tuple[int, ...],
    window: int,
) -> tuple[Components, tuple[int, ...]]:
    draws = prior_history[-window:]
    if len(draws) != window:
        raise RuntimeError("frequency window is shorter than the sealed window")
    occurrence_counts = tuple(
        sum(number in draw for draw in draws) for number in pool_numbers
    )
    rates = tuple(Fraction(count, window) for count in occurrence_counts)
    return rates, occurrence_counts


def calculate_frequency_statistics(
    history: HistoryInput,
    target_index: int,
    pool_numbers: Sequence[int] | None = None,
) -> FrequencyStatistics:
    """Calculate exact multiscale occurrence-frequency metrics for a pool."""

    prior_history = validate_prior_history(history, target_index)
    pool = (
        _validate_pool(pool_numbers)
        if pool_numbers is not None
        else _cluster_partition_from_prior_history(prior_history).ORDERED_REPRESENTATIVES
    )
    window_rates: list[Components] = []
    window_counts: list[tuple[int, ...]] = []
    for window in FREQUENCY_WINDOWS:
        rates, counts = _frequency_window_metrics(prior_history, pool, window)
        window_rates.append(rates)
        window_counts.append(counts)
    multiscale_scores = tuple(
        sum(
            (window_rates[window_index][pool_index] for window_index in range(3)),
            Fraction(0, 1),
        )
        / len(FREQUENCY_WINDOWS)
        for pool_index in range(RANKED_POOL_CARDINALITY)
    )
    total_counts = tuple(
        sum(window_counts[window_index][pool_index] for window_index in range(3))
        for pool_index in range(RANKED_POOL_CARDINALITY)
    )
    return FrequencyStatistics(
        POOL_NUMBERS=pool,
        WINDOW_FREQUENCY_RATES=tuple(window_rates),
        WINDOW_OCCURRENCE_COUNTS=tuple(window_counts),
        MULTISCALE_FREQUENCY_SCORES=multiscale_scores,
        TOTAL_OCCURRENCE_COUNTS=total_counts,
    )


def _frequency_window_ranking(
    window: int,
    pool: tuple[int, ...],
    rates: Components,
    counts: tuple[int, ...],
) -> FrequencyWindowRanking:
    by_number = {
        number: (rates[index], counts[index]) for index, number in enumerate(pool)
    }
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -by_number[number][0],
                -by_number[number][1],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    return FrequencyWindowRanking(
        WINDOW=window,
        POOL_NUMBERS=pool,
        OCCURRENCE_RATES=rates,
        OCCURRENCE_COUNTS=counts,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions_by_number[number] for number in pool),
        NORMALIZED_RANKS=tuple(
            Fraction(
                RANKED_POOL_CARDINALITY - positions_by_number[number],
                RANKED_POOL_CARDINALITY - 1,
            )
            for number in pool
        ),
    )


def rank_frequency_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    total_occurrence_counts: Sequence[int] | Mapping[int, int],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank frequency scores with the sealed occurrence-count tie-break."""

    return _rank_pool_raw_scores(
        raw_scores,
        pool_numbers,
        "frequency_raw_scores",
        total_occurrence_counts,
    )


def _frequency_ranking_from_statistics(
    statistics: FrequencyStatistics,
) -> ComponentRanking:
    window_rankings = tuple(
        _frequency_window_ranking(
            window,
            statistics.POOL_NUMBERS,
            statistics.WINDOW_FREQUENCY_RATES[index],
            statistics.WINDOW_OCCURRENCE_COUNTS[index],
        )
        for index, window in enumerate(FREQUENCY_WINDOWS)
    )
    ranking = rank_frequency_scores(
        statistics.MULTISCALE_FREQUENCY_SCORES,
        statistics.TOTAL_OCCURRENCE_COUNTS,
        statistics.POOL_NUMBERS,
    )
    return ComponentRanking(
        POOL_NUMBERS=ranking.POOL_NUMBERS,
        RAW_SCORES=ranking.RAW_SCORES,
        ORDERED_NUMBERS=ranking.ORDERED_NUMBERS,
        POSITIONS=ranking.POSITIONS,
        NORMALIZED_RANKS=ranking.NORMALIZED_RANKS,
        SECONDARY_SCORES=ranking.SECONDARY_SCORES,
        WINDOW_RANKINGS=window_rankings,
        WINDOW_FREQUENCY_RATES=statistics.WINDOW_FREQUENCY_RATES,
        WINDOW_OCCURRENCE_COUNTS=statistics.WINDOW_OCCURRENCE_COUNTS,
    )


def calculate_frequency_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    prior_history = validate_prior_history(history, target_index)
    pool = _cluster_partition_from_prior_history(prior_history).ORDERED_REPRESENTATIVES
    return _frequency_ranking_from_statistics(
        calculate_frequency_statistics(prior_history, len(prior_history), pool)
    )


def calculate_frequency_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_frequency_ranking(history, target_index).RAW_SCORES


def calculate_frequency_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_frequency_ranking(history, target_index).NORMALIZED_RANKS


frequency_components = calculate_frequency_components


def rank_pairwise_scores(
    frequency_components: Sequence[object] | Mapping[int, object],
    clustering_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> PairwiseRanking:
    """Fuse two exact normalized ten-medoid components and rank the pool."""

    pool = _validate_pool(pool_numbers)
    frequency = _exact_pool_values(frequency_components, pool, "frequency_components")
    clustering = _exact_pool_values(
        clustering_components, pool, "clustering_components"
    )
    scores = tuple(
        FUSION_WEIGHT_1 * frequency[index] + FUSION_WEIGHT_2 * clustering[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, scores, strict=True))
    frequency_by_number = dict(zip(pool, frequency, strict=True))
    clustering_by_number = dict(zip(pool, clustering, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(frequency_by_number[number], clustering_by_number[number]),
                -frequency_by_number[number],
                -clustering_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = tuple(
        positions_by_number.get(number, 0)
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            FREQUENCY_COMPONENT=frequency_by_number[number],
            CLUSTERING_COMPONENT=clustering_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(
                frequency_by_number[number], clustering_by_number[number]
            ),
            POSITION=positions_by_number[number],
        )
        for number in ordered
    )
    ticket = cast(Ticket, tuple(sorted(ordered[:PICK_COUNT])))
    if (
        len(ticket) != PICK_COUNT
        or len(set(ticket)) != PICK_COUNT
        or not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket)
    ):
        raise RuntimeError("pairwise native ticket must contain six legal unique numbers")
    return PairwiseRanking(
        POOL_NUMBERS=pool,
        FREQUENCY_COMPONENTS=frequency,
        CLUSTERING_COMPONENTS=clustering,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=positions,
        SCORES=records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent components."""

    prior_history = validate_prior_history(history, target_index)
    frequency = calculate_frequency_components(prior_history, len(prior_history))
    clustering = calculate_clustering_components(prior_history, len(prior_history))
    partition = _cluster_partition_from_prior_history(prior_history)
    return rank_pairwise_scores(
        frequency,
        clustering,
        partition.ORDERED_REPRESENTATIVES,
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
produce_bmsgv1_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_frequency_clustering_weighted_score_100_candidate = (
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
    """The selected candidate identity and sealed design signature."""

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
        "KNOWN_SEMANTIC_NEIGHBORS": (
            "BMSGV1_L2_PAIRWISE_1a5809093dc8c94c[B649_PAIRWISE_CLUSTERING_COVERAGE_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
            "BMSGV1_L2_PAIRWISE_2939296ce8a4507c[B649_PAIRWISE_CLUSTERING_BAYESIAN_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
            "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
            "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800[B649_PAIRWISE_FREQUENCY_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_FREQUENCY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
            "BMSGV1_L2_PAIRWISE_d8cd36c68f156ea5[B649_PAIRWISE_ENTROPY_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
            "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1[FREQUENCY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
            "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1[CLUSTERING_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
            "ORIGIN_MAIN_6e39a4802524386810767290fa59756194934078[SUM_RANGE_AC_ALREADY_REVIEWED;NO_FREQUENCY_CLUSTERING_PAIRWISE_FUSION]",
            "PR #164[OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
        ),
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
    "FALLBACK_RULE",
    "FEATURE_1",
    "FEATURE_2",
    "FREQUENCY_WINDOWS",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "MINIMUM_HISTORY",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "PAIRWISE_SCORE_RULE",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RNG",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "ClusterPartition",
    "ComponentRanking",
    "FrequencyRanking",
    "FrequencyStatistics",
    "FrequencyWindowRanking",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "TemporalProfileState",
    "calculate_cluster_partition",
    "calculate_clustering_components",
    "calculate_clustering_ranking",
    "calculate_clustering_raw_scores",
    "calculate_frequency_components",
    "calculate_frequency_ranking",
    "calculate_frequency_raw_scores",
    "calculate_frequency_statistics",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "calculate_temporal_profiles",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "clustering_components",
    "compute_point_distance",
    "derive_candidate_identity",
    "frequency_components",
    "fuse_pairwise_scores",
    "perform_hierarchical_clustering",
    "produce_bmsgv1_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_clustering_scores",
    "rank_frequency_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
