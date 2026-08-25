"""Causal deterministic BigLotto GRAPH + CLUSTERING candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1``.  It reuses the
exact multiscale graph/PageRank parent to form the ten-number traversal pool,
then reuses the exact multiscale temporal-profile clustering parent to assign
each graph-pool number the order of its containing cluster.  The two pool-local
rank vectors are fused with equal exact rational weights and emitted as one
native ticket.

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
from itertools import islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_parent,
)
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
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "455b9ca3a409ad39610b874c1966fa6604b77c17238e2ab194267c8ad08ad99b"
)

FEATURE_1: Final[str] = "GRAPH"
FEATURE_2: Final[str] = "CLUSTERING"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
GRAPH_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
CLUSTER_PROFILE_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
MINIMUM_HISTORY: Final[int] = 750
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = (
    "TOP_10_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1"
)
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/biglotto_graph_network_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/"
    "biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1.py"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "GRAPH_PARENT=B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;"
    "FOR_EACH_W_IN_(50,300,750),BUILD_UNDIRECTED_SAME_DRAW_COOCCURRENCE_"
    "EDGE_W(a,b)=COUNT_OF_PRIOR_DRAWS_CONTAINING_BOTH_NUMBERS;a<b;"
    "EXACT_INTEGER_EDGE_COUNTS;PAGERANK_DAMPING=17/20;PAGERANK_ITERATIONS=20;"
    "INITIAL_VECTOR=UNIFORM_1_OVER_49;DANGLING_NODES=UNIFORM_REDISTRIBUTION;"
    "EXACT_RATIONAL;PER_WINDOW_RANK=PAGERANK_DESCENDING_THEN_NUMBER_ASCENDING;"
    "WINDOW_NORMALIZED_RANK=(49-POSITION)/48;FUSED_GRAPH_RANK=MEAN_OF_"
    "NORMALIZED_RANKS_OVER_50_300_750;ROBUSTNESS_TIE=SORTED_ASCENDING("
    "MINIMUM,MEDIAN,MAXIMUM);GRAPH_POOL=FIRST_10_FUSED_GRAPH_RANKED_NUMBERS;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
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
    "CLUSTER=1;GRAPH_POOL_CLUSTER_SCORE=ORDER_OF_CONTAINING_CLUSTER;"
    "GRAPH_POOL_CLUSTER_TIE=NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_DRAWS=history[T-750:T];"
    "GRAPH_WINDOWS=(50,300,750);TARGET_ROW_history[T]_EXCLUDED;ALL_GRAPH_"
    "WINDOWS_END_AT_T"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CLUSTER_PROFILE_DRAWS_50="
    "history[T-50:T];CLUSTER_PROFILE_DRAWS_300=history[T-300:T];"
    "CLUSTER_PROFILE_DRAWS_750=history[T-750:T];ALL_CLUSTER_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact multiscale graph/PageRank ranking for all 49 legal numbers "
        "using the fixed graph parent constants and retain the first 10 graph-ranked "
        "numbers as the frozen graph traversal pool."
    ),
    (
        "Build the exact ten-cluster temporal-profile partition from all 49 legal "
        "numbers using the frozen clustering parent rules; for each graph-pool "
        "number, assign the order of its containing cluster as the CLUSTERING raw "
        "order score."
    ),
    (
        "Use graph-parent order as the GRAPH component order; rank CLUSTERING "
        "containing-cluster order higher-is-better within the same ten-number graph "
        "pool with number-ascending ties; rank both components within that same pool."
    ),
    (
        "Normalize each one-based position p within the ten-number graph pool as "
        "(10-p)/9; best rank is 1 and worst rank is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_GRAPH_FUSED_TRAVERSAL_RANK_FOR_THE_FIRST_10_OF_49_LEGAL_NUMBERS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_CLUSTER_ORDER_RANK_ASSIGNED_BY_CONTAINING_CLUSTER_FOR_EACH_OF_THE_10_GRAPH_POOL_NUMBERS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*GRAPH_NORMALIZED_TRAVERSAL_RANK_10(n)+"
    "1/2*CLUSTERING_NORMALIZED_CONTAINING_CLUSTER_RANK_10(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "GRAPH parent normalized traversal rank descending.",
    "CLUSTERING normalized containing-cluster rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "GRAPH parent PageRank tie: per-window PageRank descending, robustness tuple "
        "sorted ascending, then number ascending."
    ),
    (
        "CLUSTERING parent tie: cluster size descending, compactness ascending, "
        "medoid cost ascending, representative number ascending; graph-pool members "
        "in the same containing cluster tie by number ascending."
    ),
    (
        "Final pairwise tie: minimum component rank descending, GRAPH rank descending, "
        "CLUSTERING rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_MULTISCALE_GRAPH_PARENT_OVER_ALL_49_LEGAL_NUMBERS;"
    "RETAIN_FIRST_10_GRAPH_RANKED_NUMBERS_AS_GRAPH_TRAVERSAL_POOL;BUILD_THE_"
    "EXACT_MULTISCALE_CLUSTER_PARTITION_OVER_ALL_49_LEGAL_NUMBERS;ASSIGN_EACH_"
    "GRAPH_POOL_NUMBER_THE_ORDER_OF_ITS_CONTAINING_CLUSTER;RANK_THE_10_NUMBERS_"
    "BY_EQUAL_WEIGHT_PAIRWISE_SCORE;SELECT_FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_"
    "POOL_NUMBERS;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_POOL_NUMBERS;SORT_TICKET_NUMBERS_"
    "ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;GRAPH_PARENT_WINDOWS=(50,300,750);CLUSTER_"
    "PROFILE_WINDOWS=(50,300,750);ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;TEN_GRAPH_POOL_NUMBERS_REQUIRED;"
    "NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;GRAPH_PARENT_WINDOWS=(50,300,750);GRAPH_DAMPING=17/20;"
    "GRAPH_PAGERANK_ITERATIONS=20;GRAPH_POOL_CARDINALITY=10;CLUSTER_PROFILE_"
    "WINDOWS=(50,300,750);CLUSTER_TARGET_COUNT=10;COMPLETE_LINK;EXACT_MEAN_L1;"
    "FRONTIER_WINDOW_LABEL=100;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_NETWORK_CENTRALITY_STRUCTURE_PLUS_MULTISCALE_TEMPORAL_PROFILE_CLUSTERING"
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the graph windows (50,300,750), same-draw co-occurrence edge "
        "definition, PageRank damping 17/20, uniform initialization, uniform dangling "
        "redistribution, exact rational arithmetic, 20 PageRank iterations, graph "
        "rank ties, or first-ten graph pool."
    ),
    (
        "Do not change the clustering profile windows (50,300,750), equal one-third "
        "profile coordinates, complete-link algorithm, exact mean-L1 distance, "
        "ten-cluster target, merge tie, medoid rule, compactness rule, cluster-order "
        "rule, or containing-cluster assignment."
    ),
    (
        "Do not change ten-number pool ranking, (10-p)/9 normalization, equal 1/2 "
        "and 1/2 fusion, final tie-break order, first-six single-ticket rule, "
        "minimum history, or fallback."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, outcome "
        "tuning, historical optimization, or randomness."
    ),
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2939296ce8a4507c[B649_PAIRWISE_CLUSTERING_BAYESIAN_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_1a5809093dc8c94c[B649_PAIRWISE_CLUSTERING_COVERAGE_WEIGHTED_SCORE_100_V1;SHARED_CLUSTERING_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15[B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1[CLUSTERING_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_e9b15220e44c390fe79489370d3722f83d44c5c4[MERGED_ZONE_BALANCE_SINGLETON;NO_LEVEL2_PAIRWISE_PREDICTION_COVERAGE]",
    "PR #185[MERGED_FRONTEND_ZONE_BALANCE_SINGLETON;NO_LEVEL2_PAIRWISE_PREDICTION_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)

EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """One exact component's values and ten-number pool-local ranks."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components
    ROBUSTNESS: tuple[tuple[Fraction, Fraction, Fraction], ...] = ()
    WINDOW_RANKINGS: tuple[object, ...] = ()
    WINDOW_NORMALIZED_RANKS: tuple[Components, ...] = ()

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the ten-number graph pool") from error

    def raw_score(self, number: int) -> Fraction:
        return self.RAW_SCORES[self._pool_position(number)]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        return self.POSITIONS[self._pool_position(number)]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[self._pool_position(number)]

    def mean_rank(self, number: int) -> Fraction:
        return self.normalized_rank(number)

    def robustness(self, number: int) -> tuple[Fraction, Fraction, Fraction]:
        if not self.ROBUSTNESS:
            raise ValueError("component has no robustness tuple")
        return self.ROBUSTNESS[self._pool_position(number)]

    @property
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

    @property
    def POOL_NORMALIZED_RANKS(self) -> Components:
        return self.NORMALIZED_RANKS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent contributions."""

    NUMBER: int
    GRAPH_COMPONENT: Fraction
    CLUSTERING_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def GRAPH_RANK_10(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def CLUSTERING_RANK_10(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def GRAPH_NORMALIZED_TRAVERSAL_RANK(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def CLUSTERING_NORMALIZED_CONTAINING_CLUSTER_RANK(self) -> Fraction:
        return self.CLUSTERING_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All ten fused graph-pool ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    GRAPH_COMPONENTS: Components
    CLUSTERING_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    GRAPH_TRAVERSAL_POOL: tuple[int, ...]
    GRAPH_PARENT_RANKING: object | None = None
    CLUSTERING_PARTITION: object | None = None
    GRAPH_RANKING: ComponentRanking | None = None
    CLUSTERING_RANKING: ComponentRanking | None = None

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

    def position(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POSITIONS[number - 1]
        except IndexError as error:
            raise ValueError("number is not in the ten-number graph pool") from error

    def score(self, number: int) -> PairwiseNumberScore:
        position = self.position(number)
        if position == 0:
            raise ValueError("number is not in the ten-number graph pool")
        return self.SCORES[position - 1]


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
    """Return an immutable validated copy of only the causal history prefix."""

    _assert_parent_contracts()
    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _assert_parent_contracts() -> None:
    graph_checks = (
        _graph_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_1,
        _graph_parent.WINDOWS == WINDOWS,
        _graph_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _graph_parent.GRAPH_NODE_COUNT == 49,
        Fraction(17, 20) == _graph_parent.PAGERANK_DAMPING,
        _graph_parent.PAGERANK_ITERATIONS == 20,
        _graph_parent.PAGERANK_INITIALIZATION == "UNIFORM_1_OVER_49",
        _graph_parent.PAGERANK_DANGLING_RULE == "UNIFORM_REDISTRIBUTION",
        _graph_parent.PAGERANK_ARITHMETIC == "EXACT_RATIONAL",
        _graph_parent.PER_WINDOW_RANKING_RULE
        == "PAGERANK_DESCENDING_NUMBER_ASCENDING",
        _graph_parent.ROBUSTNESS_RULE == "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)",
    )
    cluster_checks = (
        _clustering_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_2,
        _clustering_parent.WINDOWS == WINDOWS,
        _clustering_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _clustering_parent.TEMPORAL_PROFILE_RULE
        == "EXACT_OCCURRENCE_RATE_VECTOR_50_300_750",
        _clustering_parent.PROFILE_COORDINATE_WEIGHT_RULE == "EXACT_EQUAL_ONE_THIRD",
        _clustering_parent.POINT_DISTANCE_RULE == "EXACT_MEAN_L1",
        _clustering_parent.CLUSTERING_ALGORITHM == "HIERARCHICAL_AGGLOMERATIVE",
        _clustering_parent.LINKAGE_RULE == "COMPLETE_LINK",
        _clustering_parent.INITIAL_CLUSTER_RULE == "49_SINGLETON_NUMBER_CLUSTERS",
        _clustering_parent.TARGET_CLUSTER_COUNT == 10,
        _clustering_parent.MERGE_TIE_BREAK_RULE
        == "DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC",
        _clustering_parent.MEDOID_RULE
        == "MINIMUM_TOTAL_EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING",
        _clustering_parent.CLUSTER_COMPACTNESS_RULE
        == "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE",
        _clustering_parent.CLUSTER_ORDER_RULE
        == "SIZE_DESC_COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC",
        _clustering_parent.REPRESENTATIVES_PER_CLUSTER == 1,
    )
    if not all(graph_checks):
        raise RuntimeError("graph parent semantic drifted from the sealed authority")
    if not all(cluster_checks):
        raise RuntimeError("clustering parent semantic drifted from the sealed authority")


def _graph_parent_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _graph_parent.FusedNumberRanking:
    rankings = _graph_parent.calculate_window_rankings(prior_history, len(prior_history))
    if tuple(ranking.WINDOW for ranking in rankings) != WINDOWS:
        raise RuntimeError("graph parent returned the wrong frozen windows")
    fused = _graph_parent.fuse_window_rankings(rankings)
    if len(fused.TOP_NUMBERS) != RANKED_POOL_CARDINALITY:
        raise RuntimeError("graph parent did not produce exactly ten traversal numbers")
    return fused


def calculate_graph_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_graph_parent.GraphWindow, ...]:
    """Return the exact three frozen graph parent windows."""

    prior_history = validate_prior_history(history, target_index)
    rankings = _graph_parent.calculate_window_rankings(prior_history, len(prior_history))
    return rankings


calculate_graph_rankings = calculate_graph_window_rankings
calculate_window_rankings = calculate_graph_window_rankings


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> _graph_parent.FusedNumberRanking:
    """Return the exact fused graph parent ranking over all 49 numbers."""

    return _graph_parent_from_prior_history(validate_prior_history(history, target_index))


calculate_fused_graph_ranking = calculate_graph_parent_ranking


def _build_graph_traversal_pool(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
) -> tuple[int, ...]:
    """Retain exactly the first ten frozen graph-ranked numbers."""

    pool = tuple(graph_parent_ranking.TOP_NUMBERS)
    if len(pool) != RANKED_POOL_CARDINALITY or len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise RuntimeError("graph traversal pool must contain exactly ten unique numbers")
    if not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in pool):
        raise RuntimeError("graph traversal pool contains an illegal number")
    return pool


def calculate_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return the sealed graph-traversal pool without constructing a ticket."""

    return _build_graph_traversal_pool(
        calculate_graph_parent_ranking(history, target_index)
    )


def build_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return the first ten numbers in the exact fused graph-parent order."""

    return calculate_graph_traversal_pool(history, target_index)


produce_graph_traversal_pool = build_graph_traversal_pool
produce_graph_pool = build_graph_traversal_pool
build_graph_pool = build_graph_traversal_pool


def _graph_component_from_parent(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
) -> ComponentRanking:
    pool = _build_graph_traversal_pool(graph_parent_ranking)
    positions = tuple(range(1, RANKED_POOL_CARDINALITY + 1))
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1)
        for position in positions
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=tuple(graph_parent_ranking.mean_rank(number) for number in pool),
        ORDERED_NUMBERS=pool,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        ROBUSTNESS=tuple(graph_parent_ranking.robustness(number) for number in pool),
        WINDOW_RANKINGS=tuple(graph_parent_ranking.WINDOW_RANKINGS),
        WINDOW_NORMALIZED_RANKS=tuple(
            tuple(ranking.normalized_rank(number) for number in pool)
            for ranking in graph_parent_ranking.WINDOW_RANKINGS
        ),
    )


def calculate_graph_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return graph-parent ranks restricted to the frozen ten-number pool."""

    return _graph_component_from_parent(calculate_graph_parent_ranking(history, target_index))


def calculate_graph_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_graph_ranking(history, target_index).NORMALIZED_RANKS


def calculate_temporal_profiles(
    history: HistoryInput, target_index: int
) -> _clustering_parent.TemporalProfileState:
    """Return the exact frozen temporal profile state for all 49 numbers."""

    prior_history = validate_prior_history(history, target_index)
    return _clustering_parent.calculate_temporal_profiles(prior_history, len(prior_history))


compute_point_distance = _clustering_parent.compute_point_distance
perform_hierarchical_clustering = _clustering_parent.perform_hierarchical_clustering


def _cluster_partition_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _clustering_parent.ClusterPartition:
    partition = _clustering_parent.calculate_cluster_partition(
        prior_history, len(prior_history)
    )
    if (
        len(partition.ORDERED_CLUSTERS) != RANKED_POOL_CARDINALITY
        or len(partition.ORDERED_REPRESENTATIVES) != RANKED_POOL_CARDINALITY
        or len(set(partition.ORDERED_REPRESENTATIVES)) != RANKED_POOL_CARDINALITY
    ):
        raise RuntimeError("clustering parent did not produce exactly ten ordered clusters")
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


def _containing_cluster_orders(
    partition: _clustering_parent.ClusterPartition,
) -> dict[int, int]:
    order_by_number: dict[int, int] = {}
    for order, cluster in enumerate(partition.ORDERED_CLUSTERS, start=1):
        for number in cluster:
            if number in order_by_number:
                raise RuntimeError("clustering parent assigned a number to two clusters")
            order_by_number[number] = order
    if tuple(sorted(order_by_number)) != LEGAL_NUMBERS:
        raise RuntimeError("clustering parent did not partition all legal numbers")
    return order_by_number


def _clustering_component_from_partition(
    partition: _clustering_parent.ClusterPartition,
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    order_by_number = _containing_cluster_orders(partition)
    raw_scores = tuple(Fraction(order_by_number[number], 1) for number in pool)
    ordered = tuple(sorted(pool, key=lambda number: (order_by_number[number], number)))
    position_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = tuple(position_by_number[number] for number in pool)
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position_by_number[number], RANKED_POOL_CARDINALITY - 1)
        for number in pool
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


def calculate_clustering_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Rank containing-cluster order within the graph parent's ten-number pool."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent_from_prior_history(prior_history)
    partition = _cluster_partition_from_prior_history(prior_history)
    return _clustering_component_from_partition(
        partition, _build_graph_traversal_pool(graph_parent_ranking)
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


def rank_clustering_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Rank an already normalized higher-is-better clustering vector."""

    pool = _validate_pool(pool_numbers)
    raw = _exact_pool_values(raw_scores, pool, "clustering_raw_scores")
    values_by_number = dict(zip(pool, raw, strict=True))
    ordered = tuple(sorted(pool, key=lambda number: (-values_by_number[number], number)))
    position_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position_by_number[number], RANKED_POOL_CARDINALITY - 1)
        for number in pool
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(position_by_number[number] for number in pool),
        NORMALIZED_RANKS=normalized,
    )


def rank_pairwise_scores(
    graph_components: Sequence[object] | Mapping[int, object],
    clustering_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    *,
    graph_parent_ranking: object | None = None,
    clustering_partition: object | None = None,
    graph_ranking: ComponentRanking | None = None,
    clustering_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized ten-number component vectors."""

    pool = _validate_pool(pool_numbers)
    graph = _exact_pool_values(graph_components, pool, "graph_components")
    clustering = _exact_pool_values(
        clustering_components, pool, "clustering_components"
    )
    scores = tuple(
        FUSION_WEIGHT_1 * graph[index] + FUSION_WEIGHT_2 * clustering[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, scores, strict=True))
    graph_by_number = dict(zip(pool, graph, strict=True))
    clustering_by_number = dict(zip(pool, clustering, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(graph_by_number[number], clustering_by_number[number]),
                -graph_by_number[number],
                -clustering_by_number[number],
                number,
            ),
        )
    )
    position_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for number, position in position_by_number.items():
        positions[number - 1] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            GRAPH_COMPONENT=graph_by_number[number],
            CLUSTERING_COMPONENT=clustering_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(
                graph_by_number[number], clustering_by_number[number]
            ),
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
        GRAPH_COMPONENTS=graph,
        CLUSTERING_COMPONENTS=clustering,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        SCORES=records,
        NATIVE_TICKET=ticket,
        GRAPH_TRAVERSAL_POOL=pool,
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        CLUSTERING_PARTITION=clustering_partition,
        GRAPH_RANKING=graph_ranking,
        CLUSTERING_RANKING=clustering_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal deterministic ranking from both parents."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent_from_prior_history(prior_history)
    pool = _build_graph_traversal_pool(graph_parent_ranking)
    graph_component = _graph_component_from_parent(graph_parent_ranking)
    clustering_partition = _cluster_partition_from_prior_history(prior_history)
    clustering_component = _clustering_component_from_partition(
        clustering_partition, pool
    )
    return rank_pairwise_scores(
        graph_component.NORMALIZED_RANKS,
        clustering_component.NORMALIZED_RANKS,
        pool,
        graph_parent_ranking=graph_parent_ranking,
        clustering_partition=clustering_partition,
        graph_ranking=graph_component,
        clustering_ranking=clustering_component,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first-six ticket from the final pairwise ranking."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate = (
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
    "GRAPH_WINDOWS",
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
    "RNG",
    "RNG_SEMANTICS",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "WINDOWS",
    "ComponentRanking",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "build_graph_traversal_pool",
    "build_source_ticket_universe",
    "calculate_cluster_partition",
    "calculate_clustering_components",
    "calculate_clustering_ranking",
    "calculate_clustering_raw_scores",
    "calculate_fused_graph_ranking",
    "calculate_fused_number_ranking",
    "calculate_graph_components",
    "calculate_graph_parent_ranking",
    "calculate_graph_ranking",
    "calculate_graph_rankings",
    "calculate_graph_traversal_pool",
    "calculate_graph_window_rankings",
    "calculate_pairwise_ranking",
    "calculate_temporal_profiles",
    "calculate_window_rankings",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "clustering_components",
    "compute_point_distance",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "perform_hierarchical_clustering",
    "produce_biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_pool",
    "produce_graph_traversal_pool",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_clustering_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
