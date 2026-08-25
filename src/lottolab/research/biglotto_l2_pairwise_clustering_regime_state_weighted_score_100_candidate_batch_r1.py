"""Causal deterministic BigLotto CLUSTERING + REGIME_STATE candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_CLUSTERING_REGIME_STATE_WEIGHTED_SCORE_100_V1``.  The
clustering parent builds the exact ordered ten-medoid pool.  The Rényi-2
regime parent selects its exact 210-ticket source universe, whose support
counts are ranked only inside that same ten-medoid pool.  Both pool-local
rank vectors are normalized and fused with equal exact rational weights.

The producer consumes only ``history[:target_index]``.  It has no outcome
access, I/O, randomness, empirical tuning, catalog registration, or runtime
wiring.
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
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as _regime_parent,
)

_clustering_parent = biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_950aa3b890915ed7"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_CLUSTERING_REGIME_STATE_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "1b48b84fa01bc5f692edbddcef9629d283acaea747df4b0a88544df322f12958"
)
DESIGN_AUTHORITY_SHA256: Final[str] = (
    "398dce94c7832e807f0a731fed47de6876cf5ed960175610ae0432e46acc3aec"
)

FEATURE_1: Final[str] = "CLUSTERING"
FEATURE_2: Final[str] = "REGIME_STATE"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
CLUSTER_PROFILE_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
REGIME_COLLISION_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = (
    "TEN_MULTISCALE_CLUSTER_MEDOIDS_SELECTED_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "CLUSTER_SELECTION"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1"
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1"
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/"
    "biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1.py"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "CLUSTER_PARENT=B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;TEMPORAL_PROFILE(n)="
    "(OCCURRENCE_RATE_50,OCCURRENCE_RATE_300,OCCURRENCE_RATE_750);"
    "PROFILE_COORDINATE_WEIGHT=EXACT_EQUAL_ONE_THIRD;POINT_DISTANCE=EXACT_MEAN_L1;"
    "INITIAL_CLUSTERS=49_SINGLETON_NUMBER_CLUSTERS;ALGORITHM=HIERARCHICAL_"
    "AGGLOMERATIVE;LINKAGE=COMPLETE_LINK;STOP_AT_EXACTLY_10_CLUSTERS;"
    "MERGE_TIE=DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC;MEDOID="
    "MINIMUM_TOTAL_EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING;CLUSTER_COMPACTNESS="
    "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE;CLUSTER_ORDER=SIZE_DESC_"
    "COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC;REPRESENTATIVES_PER_"
    "CLUSTER=1;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "USE_B649_RENYI2_COLLISION_STATE_V1;COLLISION_W=SUM_n(COUNT_W(n)^2)/(6*W)^2 "
    "for W in {50,300,750};EXACT_RATIONAL;REFERENCE_COLLISION="
    "(COLLISION_300+COLLISION_750)/2;COLLISION_50>REFERENCE_COLLISION=>"
    "RECENT_CONCENTRATED_LOW_RENYI2;OTHERWISE=>RECENT_DIFFUSE_HIGH_RENYI2;LOW=>"
    "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1;HIGH=>"
    "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1;REGIME_SUPPORT_751(n)="
    "COUNT_OF_SELECTED_SOURCE_UNIVERSE_TICKETS_CONTAINING_n_OVER_EXACTLY_210_"
    "ORDERED_TICKETS;HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING;NO_TARGET_OR_"
    "FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CLUSTER_PROFILE_DRAWS_50="
    "history[T-50:T];CLUSTER_PROFILE_DRAWS_300=history[T-300:T];"
    "CLUSTER_PROFILE_DRAWS_750=history[T-750:T];ALL_CLUSTER_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];RENYI2_COLLISION_WINDOWS="
    "(50,300,750);SELECTED_B649_RENYI2_SOURCE_CONSUMES_ONLY_PRIOR_PREFIX;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact ten-medoid pool from all 49 legal numbers using the "
        "frozen multiscale CLUSTERING parent rules."
    ),
    (
        "Compute the exact REGIME_STATE support score from the selected "
        "B649_RENYI2 source universe for each of those ten medoids."
    ),
    (
        "Use frozen ordered-cluster position as the CLUSTERING component order "
        "and support-count descending with number-ascending ties as the "
        "REGIME_STATE component order; rank both components within the same "
        "ten-medoid pool."
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
    "EXACT_MULTISCALE_CLUSTER_ORDER_SCORE_FOR_EACH_OF_10_CLUSTER_MEDOIDS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_REGIME_STATE_SUPPORT_COUNT_FROM_SELECTED_B649_RENYI2_SOURCE_UNIVERSE_"
    "210_ORDERED_TICKETS_FOR_EACH_OF_10_CLUSTER_MEDOIDS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(m)=1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m)+"
    "1/2*REGIME_STATE_NORMALIZED_SUPPORT_RANK_10(m);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "CLUSTERING normalized cluster-order rank descending.",
    "REGIME_STATE normalized support rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "CLUSTERING parent tie: cluster size descending, compactness ascending, "
        "medoid cost ascending, representative number ascending."
    ),
    "REGIME_STATE parent support-count tie: number ascending.",
    (
        "Final pairwise tie: minimum component rank descending, CLUSTERING rank "
        "descending, REGIME_STATE rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_10_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOIDS_FROM_ALL_49_"
    "LEGAL_NUMBERS_USING_THE_FROZEN_CLUSTERING_PARENT;RETAIN_EXACTLY_ONE_MEDOID_"
    "PER_ORDERED_CLUSTER_AS_THE_FIXED_POOL;COMPUTE_THE_FROZEN_RENYI2_REGIME_"
    "SUPPORT_SCORE_FOR_EACH_MEDOID;RANK_THE_10_MEDOIDS_BY_EQUAL_WEIGHT_PAIRWISE_"
    "SCORE;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_CLUSTER_MEDOIDS;SORT_TICKET_NUMBERS_ASCENDING;"
    "EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;FUTURE_"
    "SUFFIX NEVER_USED;CLUSTER_PROFILE_WINDOWS=(50,300,750);REGIME_COLLISION_"
    "WINDOWS=(50,300,750);SELECTED_REGIME_SOURCE_UNIVERSE_CONSUMES_ONLY_THE_SAME_"
    "PRIOR_PREFIX;ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;EXACTLY_10_CLUSTER_MEDOIDS_AND_210_"
    "ORDERED_REGIME_SOURCE_TICKETS_REQUIRED;NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;CLUSTER_PROFILE_WINDOWS=(50,300,750);PROFILE_COORDINATE_"
    "WEIGHTS=(1/3,1/3,1/3);CLUSTER_TARGET_COUNT=10;COMPLETE_LINK;EXACT_MEAN_L1;"
    "REGIME_COLLISION_WINDOWS=(50,300,750);REGIME_REFERENCE=(COLLISION_300+"
    "COLLISION_750)/2;STRICT_GREATER_THAN_SELECTS_CONCENTRATED;EQUALITY_SELECTS_"
    "DIFFUSE;REGIME_SOURCE_TICKET_COUNT=210;FRONTIER_WINDOW_LABEL=100;NO_TARGET_"
    "ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_TEMPORAL_PROFILE_CLUSTER_DIVERSITY_PLUS_RENYI2_REGIME_CONDITIONING_SIGNAL"
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the clustering profile windows (50,300,750), equal "
        "one-third profile coordinates, complete-link algorithm, exact mean-L1 "
        "distance, ten-cluster target, merge tie, medoid rule, compactness rule, "
        "cluster-order rule, or one-medoid-per-cluster pool."
    ),
    (
        "Do not change the B649_RENYI2 collision windows (50,300,750), collision "
        "formula, reference-collision mean, strict greater-than concentrated-"
        "regime rule, equality diffuse-regime rule, selected source identities, "
        "or exactly-210-ticket support count."
    ),
    (
        "Do not change ten-medoid pool ranking, (10-p)/9 normalization, equal "
        "1/2 and 1/2 fusion, final tie-break order, first-six single-ticket rule, "
        "minimum history, or fallback."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, "
        "outcome tuning, historical optimization, or randomness."
    ),
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_5f0c6fb3405f7f78[B649_PAIRWISE_REGIME_STATE_CONSTRAINT_WEIGHTED_SCORE_30_V1;SHARED_REGIME_STATE_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2939296ce8a4507c[B649_PAIRWISE_CLUSTERING_BAYESIAN_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_1a5809093dc8c94c[B649_PAIRWISE_CLUSTERING_COVERAGE_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_cca5660423304b0b[B649_PAIRWISE_FREQUENCY_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe[B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_8d97214ab08c8169[SIGNAL_FOURIER+REGIME_STATE;SHARED_REGIME_STATE_PARENT_ONLY;PARTIALLY_COVERED;NOT_EQUIVALENT]",
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1[CLUSTERING_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1[REGIME_STATE_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_cf6824201a373019f5b60f1e001a3625f40d3f47[STOCHASTIC_NUMBER_PAIRS_COOCCURRENCE_AFFINITY_SINGLETON;NO_DETERMINISTIC_LEVEL2_CLUSTERING_REGIME_STATE_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)

EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_"
    "candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_clustering_regime_state_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_"
    "candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_"
    "candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"

InsufficientHistoryError = _regime_parent.InsufficientHistoryError


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """One component's exact values and ten-medoid pool-local ranks."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: tuple[int, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the ten-medoid pool") from error

    def raw_score(self, number: int) -> int:
        return self.RAW_SCORES[self._pool_position(number)]

    def score(self, number: int) -> int:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        return self.POSITIONS[self._pool_position(number)]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[self._pool_position(number)]

    @property
    def SCORES(self) -> tuple[int, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and both normalized parent contributions."""

    NUMBER: int
    CLUSTERING_COMPONENT: Fraction
    REGIME_STATE_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def CLUSTERING_RANK_10(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def REGIME_STATE_RANK_10(self) -> Fraction:
        return self.REGIME_STATE_COMPONENT

    @property
    def CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def REGIME_STATE_NORMALIZED_SUPPORT_RANK(self) -> Fraction:
        return self.REGIME_STATE_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All ten fused medoid ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    CLUSTERING_COMPONENTS: Components
    REGIME_STATE_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    CLUSTER_MEDOID_POOL: tuple[int, ...]
    REGIME_SOURCE_TICKETS: TicketPortfolio = ()
    CLUSTERING_PARTITION: object | None = None
    REGIME_STATE: object | None = None
    CLUSTERING_RANKING: ComponentRanking | None = None
    REGIME_STATE_RANKING: ComponentRanking | None = None

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

    @property
    def POOL(self) -> tuple[int, ...]:
        return self.POOL_NUMBERS

    @property
    def SOURCE_TICKETS(self) -> TicketPortfolio:
        return self.REGIME_SOURCE_TICKETS

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def score(self, number: int) -> PairwiseNumberScore:
        position = self.position(number)
        if position == 0:
            raise ValueError("number is not in the ten-medoid pool")
        return self.SCORES[position - 1]


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
    PARENT_SOURCE_UNIVERSE_ID_1: str
    PARENT_SOURCE_UNIVERSE_ID_2: str
    RANKED_POOL_DOMAIN: str
    RANKED_POOL_CARDINALITY: int
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


def _assert_parent_contracts() -> None:
    clustering_checks = (
        _clustering_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_1,
        _clustering_parent.WINDOWS == WINDOWS,
        _clustering_parent.MINIMUM_HISTORY == 750,
        _clustering_parent.TEMPORAL_PROFILE_RULE == "EXACT_OCCURRENCE_RATE_VECTOR_50_300_750",
        _clustering_parent.PROFILE_COORDINATE_WEIGHT_RULE == "EXACT_EQUAL_ONE_THIRD",
        _clustering_parent.POINT_DISTANCE_RULE == "EXACT_MEAN_L1",
        _clustering_parent.CLUSTERING_ALGORITHM == "HIERARCHICAL_AGGLOMERATIVE",
        _clustering_parent.LINKAGE_RULE == "COMPLETE_LINK",
        _clustering_parent.INITIAL_CLUSTER_RULE == "49_SINGLETON_NUMBER_CLUSTERS",
        _clustering_parent.TARGET_CLUSTER_COUNT == RANKED_POOL_CARDINALITY,
        _clustering_parent.MERGE_TIE_BREAK_RULE
        == "DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC",
        _clustering_parent.MEDOID_RULE == "MINIMUM_TOTAL_EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING",
        _clustering_parent.CLUSTER_COMPACTNESS_RULE == "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE",
        _clustering_parent.CLUSTER_ORDER_RULE
        == "SIZE_DESC_COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC",
        _clustering_parent.REPRESENTATIVES_PER_CLUSTER == 1,
        _clustering_parent.SOURCE_NUMBER_POOL_COUNT == RANKED_POOL_CARDINALITY,
    )
    regime_checks = (
        _regime_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_2,
        _regime_parent.REGIME_WINDOWS == WINDOWS,
        _regime_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _regime_parent.SOURCE_CANDIDATE_TICKET_COUNT == SOURCE_CANDIDATE_TICKET_COUNT,
        _regime_parent.REGIME_DETECTOR_ID == "B649_RENYI2_COLLISION_STATE_V1",
        _regime_parent.REFERENCE_COLLISION_RULE
        == "REFERENCE_COLLISION=(COLLISION_300+COLLISION_750)/2",
        _regime_parent.REGIME_TIE_RULE
        == "COLLISION_50==REFERENCE_COLLISION=>RECENT_DIFFUSE_HIGH_RENYI2",
        _regime_parent.LOW_ENTROPY_SOURCE_ID == "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1",
        _regime_parent.HIGH_ENTROPY_SOURCE_ID == "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1",
        _regime_parent.DETERMINISM_CLASS == DETERMINISM_CLASS,
        _regime_parent.RNG_SEMANTICS == RNG_SEMANTICS,
    )
    if not all(clustering_checks):
        raise RuntimeError("clustering parent semantic drifted from sealed authority")
    if not all(regime_checks):
        raise RuntimeError("regime-state parent semantic drifted from sealed authority")


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return the exact immutable strictly-prior prefix under the 751-draw gate."""

    _assert_parent_contracts()
    return _regime_parent.validate_prior_history(history, target_index)


validate_history = validate_prior_history


def calculate_temporal_profiles(
    history: HistoryInput, target_index: int
) -> _clustering_parent.TemporalProfileState:
    """Return the exact frozen clustering-parent temporal profiles."""

    prior_history = validate_prior_history(history, target_index)
    return _clustering_parent.calculate_temporal_profiles(prior_history, len(prior_history))


compute_point_distance = _clustering_parent.compute_point_distance
perform_hierarchical_clustering = _clustering_parent.perform_hierarchical_clustering


def _cluster_partition_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _clustering_parent.ClusterPartition:
    partition = _clustering_parent.calculate_cluster_partition(prior_history, len(prior_history))
    if (
        len(partition.ORDERED_CLUSTERS) != RANKED_POOL_CARDINALITY
        or len(partition.ORDERED_REPRESENTATIVES) != RANKED_POOL_CARDINALITY
        or len(set(partition.ORDERED_REPRESENTATIVES)) != RANKED_POOL_CARDINALITY
    ):
        raise RuntimeError("clustering parent must produce ten ordered clusters and medoids")
    all_members = tuple(
        sorted(number for cluster in partition.ORDERED_CLUSTERS for number in cluster)
    )
    if all_members != LEGAL_NUMBERS:
        raise RuntimeError("clustering parent must partition all 49 legal numbers")
    return partition


def calculate_cluster_partition(
    history: HistoryInput, target_index: int
) -> _clustering_parent.ClusterPartition:
    """Return the exact frozen ten-cluster partition from prior history."""

    return _cluster_partition_from_prior_history(validate_prior_history(history, target_index))


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain exactly ten numbers")
    for number in pool:
        _validate_number(number)
    if len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain ten unique numbers")
    return pool


def _build_cluster_medoid_pool(
    partition: _clustering_parent.ClusterPartition,
) -> tuple[int, ...]:
    pool = _validate_pool(partition.ORDERED_REPRESENTATIVES)
    for cluster, medoid in zip(partition.ORDERED_CLUSTERS, pool, strict=True):
        if medoid not in cluster:
            raise RuntimeError("clustering parent medoid must belong to its cluster")
    return pool


def calculate_cluster_medoid_pool(history: HistoryInput, target_index: int) -> tuple[int, ...]:
    """Return one medoid per ordered parent cluster as the fixed pool."""

    return _build_cluster_medoid_pool(calculate_cluster_partition(history, target_index))


build_cluster_medoid_pool = calculate_cluster_medoid_pool
produce_cluster_medoid_pool = calculate_cluster_medoid_pool


def _clustering_component_from_partition(
    partition: _clustering_parent.ClusterPartition,
) -> ComponentRanking:
    pool = _build_cluster_medoid_pool(partition)
    positions = tuple(range(1, RANKED_POOL_CARDINALITY + 1))
    normalized = tuple(
        Fraction(
            RANKED_POOL_CARDINALITY - position,
            RANKED_POOL_CARDINALITY - 1,
        )
        for position in positions
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=positions,
        ORDERED_NUMBERS=pool,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


def calculate_clustering_ranking(history: HistoryInput, target_index: int) -> ComponentRanking:
    """Rank the ten medoids by the parent's frozen ordered-cluster position."""

    return _clustering_component_from_partition(calculate_cluster_partition(history, target_index))


def calculate_clustering_order_scores(history: HistoryInput, target_index: int) -> tuple[int, ...]:
    return calculate_clustering_ranking(history, target_index).RAW_SCORES


def calculate_clustering_components(history: HistoryInput, target_index: int) -> Components:
    return calculate_clustering_ranking(history, target_index).NORMALIZED_RANKS


clustering_components = calculate_clustering_components


def calculate_regime_state(history: HistoryInput, target_index: int) -> _regime_parent.RegimeState:
    """Return the exact frozen Rényi-2 state from the same causal prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _regime_parent.calculate_regime_state(prior_history, len(prior_history))


calculate_collision_concentration = _regime_parent.calculate_collision_concentration
calculate_collision_concentrations = _regime_parent.calculate_collision_concentrations
calculate_reference_collision = _regime_parent.calculate_reference_collision
classify_regime = _regime_parent.classify_regime
selected_source_for_regime = _regime_parent.selected_source_for_regime


def _validate_regime_source(raw_source: object) -> TicketPortfolio:
    if not isinstance(raw_source, tuple):
        raise RuntimeError("regime parent must return an ordered tuple of tickets")
    source = cast(tuple[object, ...], raw_source)
    if len(source) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("regime parent must return exactly 210 ordered tickets")

    tickets: list[Ticket] = []
    seen: set[Ticket] = set()
    for ticket_index, raw_ticket in enumerate(source):
        if not isinstance(raw_ticket, tuple):
            raise RuntimeError(f"regime source ticket {ticket_index} must be a tuple")
        numbers = cast(tuple[object, ...], raw_ticket)
        if len(numbers) != PICK_COUNT or any(type(number) is not int for number in numbers):
            raise RuntimeError(f"regime source ticket {ticket_index} must contain six integers")
        ticket = cast(Ticket, numbers)
        if (
            ticket != tuple(sorted(ticket))
            or len(set(ticket)) != PICK_COUNT
            or not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket)
        ):
            raise RuntimeError(f"regime source ticket {ticket_index} must be legal and unique")
        if ticket in seen:
            raise RuntimeError("regime parent returned a duplicate source ticket")
        seen.add(ticket)
        tickets.append(ticket)
    return tuple(tickets)


def _produce_regime_source_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> TicketPortfolio:
    source = _regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(
        prior_history, len(prior_history)
    )
    return _validate_regime_source(source)


def produce_regime_source_ticket_universe(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return the exact ordered 210-ticket source selected by the regime parent."""

    return _produce_regime_source_from_prior_history(validate_prior_history(history, target_index))


def _support_counts_for_pool(
    source_tickets: TicketPortfolio,
    pool_numbers: Sequence[int],
) -> tuple[int, ...]:
    """Count support directly inside the fixed medoid universe."""

    pool = _validate_pool(pool_numbers)
    counts = {number: 0 for number in pool}
    for ticket in source_tickets:
        for number in ticket:
            if number in counts:
                counts[number] += 1
    return tuple(counts[number] for number in pool)


def _integer_pool_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: tuple[int, ...],
    name: str,
) -> tuple[int, ...]:
    if isinstance(raw_scores, Mapping):
        keys = tuple(raw_scores)
        if set(keys) != set(pool_numbers) or len(keys) != len(pool_numbers):
            raise ValueError(f"{name} mapping must contain exactly the ten pool numbers")
        values = tuple(raw_scores[number] for number in pool_numbers)
    else:
        values = tuple(raw_scores)
        if len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly ten values")

    converted: list[int] = []
    for index, value in enumerate(values, start=1):
        if type(value) is not int or value < 0:
            raise TypeError(f"{name}[{index}] must be a non-negative integer")
        converted.append(value)
    return tuple(converted)


def rank_regime_state_support_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank exact support counts only within the same ten-medoid pool."""

    pool = _validate_pool(pool_numbers)
    scores = _integer_pool_scores(raw_scores, pool, "regime_state_support_scores")
    scores_by_number = dict(zip(pool, scores, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (-scores_by_number[number], number),
        )
    )
    position_by_number = {number: position for position, number in enumerate(ordered, start=1)}
    positions = tuple(position_by_number[number] for number in pool)
    normalized = tuple(
        Fraction(
            RANKED_POOL_CARDINALITY - position_by_number[number],
            RANKED_POOL_CARDINALITY - 1,
        )
        for number in pool
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


rank_regime_state_scores = rank_regime_state_support_scores


def calculate_regime_state_support_scores(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return support counts aligned to the ordered ten-medoid pool."""

    prior_history = validate_prior_history(history, target_index)
    partition = _cluster_partition_from_prior_history(prior_history)
    pool = _build_cluster_medoid_pool(partition)
    source = _produce_regime_source_from_prior_history(prior_history)
    return _support_counts_for_pool(source, pool)


def calculate_regime_state_ranking(history: HistoryInput, target_index: int) -> ComponentRanking:
    """Rank selected-source support within the ordered ten-medoid pool."""

    prior_history = validate_prior_history(history, target_index)
    partition = _cluster_partition_from_prior_history(prior_history)
    pool = _build_cluster_medoid_pool(partition)
    source = _produce_regime_source_from_prior_history(prior_history)
    return rank_regime_state_support_scores(_support_counts_for_pool(source, pool), pool)


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


def _ranking_from_normalized_components(
    components: Components,
    pool_numbers: tuple[int, ...],
) -> ComponentRanking:
    values_by_number = dict(zip(pool_numbers, components, strict=True))
    ordered = tuple(
        sorted(
            pool_numbers,
            key=lambda number: (-values_by_number[number], number),
        )
    )
    position_by_number = {number: position for position, number in enumerate(ordered, start=1)}
    return ComponentRanking(
        POOL_NUMBERS=pool_numbers,
        RAW_SCORES=(0,) * RANKED_POOL_CARDINALITY,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(position_by_number[number] for number in pool_numbers),
        NORMALIZED_RANKS=components,
    )


def rank_pairwise_scores(
    clustering_components: Sequence[object] | Mapping[int, object],
    regime_state_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    *,
    clustering_partition: object | None = None,
    regime_state: object | None = None,
    regime_source_tickets: TicketPortfolio = (),
    clustering_ranking: ComponentRanking | None = None,
    regime_state_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized vectors over one identical ten-medoid pool."""

    pool = _validate_pool(pool_numbers)
    clustering = _exact_pool_values(clustering_components, pool, "clustering_components")
    regime = _exact_pool_values(regime_state_components, pool, "regime_state_components")
    pairwise = tuple(
        FUSION_WEIGHT_1 * clustering[index] + FUSION_WEIGHT_2 * regime[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    clustering_by_number = dict(zip(pool, clustering, strict=True))
    regime_by_number = dict(zip(pool, regime, strict=True))
    pairwise_by_number = dict(zip(pool, pairwise, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -pairwise_by_number[number],
                -min(
                    clustering_by_number[number],
                    regime_by_number[number],
                ),
                -clustering_by_number[number],
                -regime_by_number[number],
                number,
            ),
        )
    )
    position_by_number = {number: position for position, number in enumerate(ordered, start=1)}
    positions = [0] * len(LEGAL_NUMBERS)
    for number, position in position_by_number.items():
        positions[number - 1] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            CLUSTERING_COMPONENT=clustering_by_number[number],
            REGIME_STATE_COMPONENT=regime_by_number[number],
            PAIRWISE_SCORE=pairwise_by_number[number],
            MIN_COMPONENT_RANK=min(clustering_by_number[number], regime_by_number[number]),
            POSITION=position_by_number[number],
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
        CLUSTERING_COMPONENTS=clustering,
        REGIME_STATE_COMPONENTS=regime,
        PAIRWISE_SCORES=pairwise,
        RANKED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        SCORES=records,
        NATIVE_TICKET=ticket,
        CLUSTER_MEDOID_POOL=pool,
        REGIME_SOURCE_TICKETS=tuple(regime_source_tickets),
        CLUSTERING_PARTITION=clustering_partition,
        REGIME_STATE=regime_state,
        CLUSTERING_RANKING=clustering_ranking
        or _ranking_from_normalized_components(clustering, pool),
        REGIME_STATE_RANKING=regime_state_ranking
        or _ranking_from_normalized_components(regime, pool),
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(history: HistoryInput, target_index: int) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent mechanisms."""

    prior_history = validate_prior_history(history, target_index)
    partition = _cluster_partition_from_prior_history(prior_history)
    pool = _build_cluster_medoid_pool(partition)
    clustering_ranking = _clustering_component_from_partition(partition)
    regime_state = _regime_parent.calculate_regime_state(prior_history, len(prior_history))
    source = _produce_regime_source_from_prior_history(prior_history)
    regime_ranking = rank_regime_state_support_scores(_support_counts_for_pool(source, pool), pool)
    return rank_pairwise_scores(
        clustering_ranking.NORMALIZED_RANKS,
        regime_ranking.NORMALIZED_RANKS,
        pool,
        clustering_partition=partition,
        regime_state=regime_state,
        regime_source_tickets=source,
        clustering_ranking=clustering_ranking,
        regime_state_ranking=regime_ranking,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first-six ticket from the final pairwise ranking."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(history: HistoryInput, target_index: int) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_clustering_regime_state_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_candidate = (
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


def derive_candidate_identity(
    record: Mapping[str, object],
) -> CandidateIdentity:
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
        "KNOWN_SEMANTIC_NEIGHBORS": KNOWN_SEMANTIC_NEIGHBORS,
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


CANDIDATE_SEMANTICS: Final[Mapping[str, object]] = MappingProxyType(_design_signature_object())
DESIGN_SIGNATURE_OBJECT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS
CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = MappingProxyType(
    {CANDIDATE_ID: CANDIDATE_SEMANTICS}
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
    PARENT_SOURCE_UNIVERSE_ID_1=PARENT_SOURCE_UNIVERSE_ID_1,
    PARENT_SOURCE_UNIVERSE_ID_2=PARENT_SOURCE_UNIVERSE_ID_2,
    RANKED_POOL_DOMAIN=RANKED_POOL_DOMAIN,
    RANKED_POOL_CARDINALITY=RANKED_POOL_CARDINALITY,
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
    "CAUSAL_CUTOFF_RULE",
    "CLUSTER_PROFILE_WINDOWS",
    "COMPONENT_NORMALIZATION_RULE",
    "COMPONENT_SCORE_DOMAIN_1",
    "COMPONENT_SCORE_DOMAIN_2",
    "DESIGN_AUTHORITY_SHA256",
    "DESIGN_ID",
    "DESIGN_SIGNATURE_OBJECT",
    "DESIGN_SIGNATURE_SHA256",
    "DETERMINISM_CLASS",
    "EXPECTED_FOCUSED_TEST_MODULE",
    "EXPECTED_IMPLEMENTATION_MODULE",
    "EXPECTED_IMPLEMENTATION_SYMBOL",
    "EXPECTED_SOURCE_PATH",
    "FALLBACK_RULE",
    "FEATURE_1",
    "FEATURE_2",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_READY",
    "IMPLEMENTATION_SYMBOL",
    "LEGAL_NUMBERS",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_TIE_BREAK_RULE",
    "PAIRWISE_SCORE_RULE",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_PATH_1",
    "PARENT_SOURCE_PATH_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "REGIME_COLLISION_WINDOWS",
    "RNG",
    "RNG_SEMANTICS",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "WINDOWS",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "Ticket",
    "TicketPortfolio",
    "build_cluster_medoid_pool",
    "build_source_ticket_universe",
    "calculate_cluster_medoid_pool",
    "calculate_cluster_partition",
    "calculate_clustering_components",
    "calculate_clustering_order_scores",
    "calculate_clustering_ranking",
    "calculate_collision_concentration",
    "calculate_collision_concentrations",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "calculate_reference_collision",
    "calculate_regime_state",
    "calculate_regime_state_ranking",
    "calculate_regime_state_support_scores",
    "calculate_temporal_profiles",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "classify_regime",
    "clustering_components",
    "compute_point_distance",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "perform_hierarchical_clustering",
    "produce_biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_clustering_regime_state_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_cluster_medoid_pool",
    "produce_regime_source_ticket_universe",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_pairwise_scores",
    "rank_regime_state_scores",
    "rank_regime_state_support_scores",
    "selected_source_for_regime",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
