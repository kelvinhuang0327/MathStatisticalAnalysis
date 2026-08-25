"""Causal deterministic BigLotto GAP_OMISSION + GRAPH candidate.

This research-only module implements the one candidate frozen by
``B649_PAIRWISE_GAP_OMISSION_GRAPH_WEIGHTED_SCORE_100_V1``.  The two parent
rankings are reused directly from their sealed source modules.  The graph
parent establishes the ten-number traversal pool; both parent orders are
then ranked within that same pool and fused with exact equal weights.

The producer has no outcome access, I/O, randomness, or production wiring.
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
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_parent,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _gap_omission_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type ComponentValue = Fraction
type Robustness = tuple[Fraction, Fraction, Fraction]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_5b92df6e42366e6b"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_GAP_OMISSION_GRAPH_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "63567de8daf58459c10ee7c1e513f6a8bf046df961c76a54a26ff1d64fd84d25"
)
DESIGN_AUTHORITY_SHA256: Final[str] = (
    "4dc52b00b57b665320cb0cc333d7272d6aafd2e7488485a1a044fddef4999075"
)

FEATURE_1: Final[str] = "GAP_OMISSION"
FEATURE_2: Final[str] = "GRAPH"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
OMISSION_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
GRAPH_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
MINIMUM_HISTORY: Final[int] = 750
RANKED_POOL_DOMAIN: Final[str] = (
    "TOP_10_MULTISCALE_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
RANKED_POOL_CARDINALITY: Final[int] = 10

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
)
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/"
    "biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/"
    "biglotto_graph_network_multi_ticket_candidate_batch_r1.py"
)
PARENT_1_SOURCE_BLOB_ID: Final[str] = (
    "614aa434cea189b1cc4f58d8ad4ea106ed82e00e"
)
PARENT_2_SOURCE_BLOB_ID: Final[str] = (
    "54f1b12ba5e0829e09306cc84abfa50b075ca918"
)
PARENT_1_SOURCE_SHA256: Final[str] = (
    "1da8b5384830f94a7846b3db56b106d1722d75cf386d0c4f75e4d1ce93a7dc4c"
)
PARENT_2_SOURCE_SHA256: Final[str] = (
    "252ac7a477bc10455932da07541d2aa22153d879673d9f5abfa1ccf1df60f005"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "OMISSION_PARENT=B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(50,300,750):"
    "OCCURRENCE_W(n)=COUNT_PRIOR_WINDOW_DRAWS_CONTAINING_n;CURRENT_GAP_W(n)="
    "TRAILING_DRAWS_SINCE_MOST_RECENT_OCCURRENCE_WITH_W_IF_ABSENT;"
    "RECURRENCE_CYCLE_W(n)=(W+1)/(OCCURRENCE_W(n)+1);"
    "OMISSION_PRESSURE_W(n)=CURRENT_GAP_W(n)*(OCCURRENCE_W(n)+1)/(W+1);"
    "EXACT_RATIONAL;PER_WINDOW_ORDER=PRESSURE_DESC_CURRENT_GAP_DESC_"
    "OCCURRENCE_DESC_NUMBER_ASC;NORMALIZED_W=(49-POSITION)/48;"
    "FUSED_OMISSION_RANK=MEAN_OF_NORMALIZED_50_300_750;FUSED_TIE=MINIMUM_"
    "MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;NO_TARGET_OR_"
    "FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "GRAPH_PARENT=B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(50,300,750):"
    "UNDIRECTED_EDGE_W(a,b)=COUNT_PRIOR_WINDOW_DRAWS_CONTAINING_BOTH_"
    "NUMBERS_FOR_a_LESS_THAN_b;UNDECAYED_INTEGER_SAME_DRAW_COOCCURRENCE;"
    "PAGERANK_DAMPING=17/20;PAGERANK_ITERATIONS=20;INITIAL_VECTOR=UNIFORM_"
    "1_OVER_49;DANGLING_NODES=UNIFORM_REDISTRIBUTION;EXACT_RATIONAL;"
    "PER_WINDOW_ORDER=PAGERANK_DESC_NUMBER_ASC;NORMALIZED_W=(49-POSITION)/"
    "48;FUSED_GRAPH_RANK=MEAN_OF_NORMALIZED_50_300_750;FUSED_TIE=MINIMUM_"
    "MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;GRAPH_POOL=FIRST_"
    "10_FUSED_GRAPH_RANKED_NUMBERS;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];OMISSION_DRAWS_50=history[T-50:T];"
    "OMISSION_DRAWS_300=history[T-300:T];OMISSION_DRAWS_750=history[T-750:T];"
    "ALL_OMISSION_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_DRAWS_50=history[T-50:T];"
    "GRAPH_DRAWS_300=history[T-300:T];GRAPH_DRAWS_750=history[T-750:T];"
    "ALL_GRAPH_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build the exact multiscale GRAPH PageRank ranking for all 49 legal numbers "
    "using the frozen graph parent and retain the first 10 graph-ranked numbers "
    "as the traversal pool.",
    "Compute the exact multiscale GAP_OMISSION fused mean rank and robustness "
    "tuple for all 49 legal numbers using the frozen omission parent, then "
    "restrict that parent order to the same ten-number graph traversal pool.",
    "Use restricted omission-parent order as the GAP_OMISSION component order "
    "and graph-parent order as the GRAPH component order; rank both components "
    "within the same ten-number pool.",
    "Normalize each one-based position p within the ten-number pool as (10-p)/9; "
    "best rank is 1 and worst rank is 0; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, "
    "outcome-derived normalization, historical optimization, or randomness.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_OMISSION_PRESSURE_FUSED_MEAN_RANK_AND_ROBUSTNESS_"
    "FOR_EACH_OF_THE_10_GRAPH_TRAVERSAL_POOL_NUMBERS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_MULTISCALE_GRAPH_PAGERANK_FUSED_TRAVERSAL_RANK_FOR_THE_FIRST_10_"
    "OF_49_LEGAL_NUMBERS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*GAP_OMISSION_NORMALIZED_RANK_10(n)+1/2*"
    "GRAPH_NORMALIZED_TRAVERSAL_RANK_10(n);EXACT_RATIONAL"
)

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "GAP_OMISSION normalized within-pool rank descending.",
    "GRAPH normalized traversal rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "GAP_OMISSION parent per-window tie: omission pressure descending, current "
    "gap descending, occurrence count descending, number ascending.",
    "GAP_OMISSION parent fused-mean tie: minimum, median, maximum normalized "
    "window rank descending, then number ascending.",
    "GRAPH parent per-window tie: PageRank descending, then number ascending.",
    "GRAPH parent fused-mean tie: minimum, median, maximum normalized window "
    "rank descending, then number ascending.",
    "Final pairwise tie: minimum component rank descending, GAP_OMISSION rank "
    "descending, GRAPH rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_MULTISCALE_GRAPH_PARENT_RANKING_OVER_ALL_49_LEGAL_"
    "NUMBERS;RETAIN_FIRST_10_GRAPH_RANKED_NUMBERS_AS_THE_FROZEN_TRAVERSAL_"
    "POOL;COMPUTE_THE_EXACT_MULTISCALE_GAP_OMISSION_PARENT_FUSED_RANK_FOR_"
    "EACH_OF_THOSE_10_NUMBERS;RANK_BOTH_COMPONENTS_WITHIN_THE_SAME_10_"
    "NUMBER_POOL;FUSE_WITH_EQUAL_EXACT_RANK_WEIGHTS;NO_OUTCOME_OR_FUTURE_"
    "DATA"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_TRAVERSAL_POOL_NUMBERS;SORT_TICKET_"
    "NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;OMISSION_PARENT_WINDOWS=(50,300,750);"
    "GRAPH_PARENT_WINDOWS=(50,300,750);ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_"
    "TRUNCATION;NO_PARENT_DEGRADATION;NO_RANDOMNESS;EXACTLY_10_GRAPH_"
    "TRAVERSAL_POOL_NUMBERS_REQUIRED;NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;OMISSION_WINDOWS=(50,300,750);OMISSION_RECURRENCE=(W+1)/"
    "(OCCURRENCE+1);OMISSION_PRESSURE=CURRENT_GAP*(OCCURRENCE+1)/(W+1);"
    "GRAPH_WINDOWS=(50,300,750);GRAPH_DAMPING=17/20;GRAPH_PAGERANK_"
    "ITERATIONS=20;GRAPH_INITIALIZATION=UNIFORM_1_OVER_49;GRAPH_DANGLING="
    "UNIFORM_REDISTRIBUTION;GRAPH_POOL_CARDINALITY=10;FRONTIER_WINDOW_LABEL="
    "100;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_RECURRENCE_GAP_PRESSURE_STRUCTURE_PLUS_MULTISCALE_NETWORK_"
    "CENTRALITY_STRUCTURE"
)

KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_2507681ad9ef073c[B649_PAIRWISE_GAP_OMISSION_"
    "ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_GAP_OMISSION_PARENT_ONLY;"
    "COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_"
    "WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_"
    "ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15[B649_PAIRWISE_TRANSITION_MARKOV_"
    "GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;"
    "NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe[B649_PAIRWISE_GRAPH_CLUSTERING_"
    "WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;"
    "NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_950aa3b890915ed7[B649_PAIRWISE_CLUSTERING_REGIME_"
    "STATE_WEIGHTED_SCORE_100_V1;NO_SHARED_FEATURE;COVERED_EXACT;"
    "NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_1b75b7279a69956c[HOT_COLD+GRAPH;SHARED_GRAPH_"
    "PARENT_ONLY;PARTIALLY_COVERED;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7ded44c3d9017c19[GRAPH+ENTROPY;SHARED_GRAPH_PARENT_"
    "ONLY;PARTIALLY_COVERED;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_ab2b557ca7671da8[GRAPH+SIGNAL_FOURIER;SHARED_GRAPH_"
    "PARENT_ONLY;PARTIALLY_COVERED;NOT_EQUIVALENT]",
    "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1[GAP_OMISSION_PARENT_"
    "ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_"
    "PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_cf6824201a373019f5b60f1e001a3625f40d3f47[STOCHASTIC_NUMBER_"
    "PAIRS_COOCCURRENCE_AFFINITY_SINGLETON;NO_DETERMINISTIC_GAP_OMISSION_"
    "GRAPH_LEVEL2_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_"
    "COMPONENT]",
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change the omission parent windows (50,300,750), boundary-stabilized "
    "recurrence formula, omission-pressure formula, exact rational arithmetic, "
    "per-window ordering, equal three-window rank fusion, robustness tie, or "
    "all-49 parent domain.",
    "Do not change the graph parent windows (50,300,750), same-draw undirected "
    "cooccurrence edges, PageRank damping 17/20, exactly 20 iterations, "
    "uniform 1/49 initialization, uniform dangling redistribution, exact "
    "rational arithmetic, per-window ordering, equal three-window rank fusion, "
    "robustness tie, or graph-derived first-10 traversal pool.",
    "Do not change restriction of the omission parent order to the graph-derived "
    "ten-number pool, within-pool (10-p)/9 normalization, equal 1/2 and 1/2 "
    "fusion, final tie-break order, first-six single-ticket rule, minimum "
    "history, or fallback.",
    "Do not introduce empirical min-max scaling, z-scoring, calibration, "
    "outcome tuning, historical optimization, or randomness.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1"
)

_LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(
    range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
)

InsufficientHistoryError = _gap_omission_parent.InsufficientHistoryError


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """One exact component ranking over the frozen ten-number pool."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: tuple[ComponentValue, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]
    ROBUSTNESS: tuple[Robustness, ...]

    def _index(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the frozen graph pool") from error

    def raw_score(self, number: int) -> Fraction:
        return self.RAW_SCORES[self._index(number)]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - NUMBER_DOMAIN[0]]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[self._index(number)]

    def robustness(self, number: int) -> Robustness:
        return self.ROBUSTNESS[self._index(number)]

    @property
    def SCORES(self) -> tuple[Fraction, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score for one number in the graph pool."""

    NUMBER: int
    GAP_OMISSION_COMPONENT: Fraction
    GRAPH_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def GAP_OMISSION_RANK_10(self) -> Fraction:
        return self.GAP_OMISSION_COMPONENT

    @property
    def GRAPH_RANK_10(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """The ten-number fused ranking and exactly one native ticket."""

    GAP_OMISSION_PARENT_RANKING: _gap_omission_parent.FusedNumberRanking | None
    GRAPH_PARENT_RANKING: _graph_parent.FusedNumberRanking | None
    GRAPH_POOL: tuple[int, ...]
    GAP_OMISSION_RANKING: ComponentRanking
    GRAPH_RANKING: ComponentRanking
    GAP_OMISSION_COMPONENTS: tuple[Fraction, ...]
    GRAPH_COMPONENTS: tuple[Fraction, ...]
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

    @property
    def POOL_NUMBERS(self) -> tuple[int, ...]:
        return self.GRAPH_POOL

    @property
    def GRAPH_TRAVERSAL_POOL(self) -> tuple[int, ...]:
        return self.GRAPH_POOL

    def gap_omission_component(self, number: int) -> Fraction:
        return self.GAP_OMISSION_RANKING.normalized_rank(number)

    def omission_component(self, number: int) -> Fraction:
        return self.gap_omission_component(number)

    def graph_component(self, number: int) -> Fraction:
        return self.GRAPH_RANKING.normalized_rank(number)

    def pairwise_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAIRWISE_SCORES[self.GRAPH_POOL.index(number)]

    def score(self, number: int) -> PairwiseNumberScore:
        _validate_number(number)
        position = self.POSITIONS[number - NUMBER_DOMAIN[0]]
        if position == 0:
            raise ValueError("number is not in the frozen graph pool")
        return self.SCORES[position - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - NUMBER_DOMAIN[0]]


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
    COMPONENT_NORMALIZATION_RULE: tuple[str, ...]
    FUSION_WEIGHT_1: str
    FUSION_WEIGHT_2: str
    IMPLEMENTATION_MODULE: str
    IMPLEMENTATION_SYMBOL: str
    NATIVE_TICKET_COUNT: int
    MINIMUM_HISTORY: int
    DETERMINISM_CLASS: str
    SEMANTICS: Mapping[str, object]


def _validate_number(number: int) -> None:
    if type(number) is not int or number not in _LEGAL_NUMBERS:
        raise ValueError("number must be an integer in 1..49")


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return only the validated, strictly prior prefix required by both parents."""

    return _gap_omission_parent.validate_prior_history(history, target_index)


validate_history = validate_prior_history


def calculate_gap_omission_parent_ranking(
    history: HistoryInput, target_index: int
) -> _gap_omission_parent.FusedNumberRanking:
    """Reuse the exact omission parent from the immutable prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _gap_omission_parent.calculate_fused_number_ranking(
        prior_history, len(prior_history)
    )


def calculate_gap_omission_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_gap_omission_parent.WindowRanking, ...]:
    """Return the exact omission parent windows."""

    prior_history = validate_prior_history(history, target_index)
    return _gap_omission_parent.calculate_window_rankings(
        prior_history, len(prior_history)
    )


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> _graph_parent.FusedNumberRanking:
    """Reuse the exact graph/PageRank parent from the immutable prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _graph_parent.calculate_fused_number_ranking(
        prior_history, len(prior_history)
    )


def calculate_graph_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_graph_parent.GraphWindow, ...]:
    """Return the exact graph parent windows."""

    prior_history = validate_prior_history(history, target_index)
    return _graph_parent.calculate_window_rankings(prior_history, len(prior_history))


calculate_fused_gap_omission_parent_ranking = calculate_gap_omission_parent_ranking
calculate_fused_graph_parent_ranking = calculate_graph_parent_ranking
calculate_graph_fused_ranking = calculate_graph_parent_ranking


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError(
            f"graph pool must contain exactly {RANKED_POOL_CARDINALITY} numbers"
        )
    if len(set(pool)) != len(pool) or any(number not in _LEGAL_NUMBERS for number in pool):
        raise ValueError("graph pool must be ten unique legal numbers")
    return pool


def produce_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return the first ten numbers from the exact fused graph parent order."""

    return _validate_pool(calculate_graph_parent_ranking(history, target_index).TOP_NUMBERS)


produce_graph_pool = produce_graph_traversal_pool
build_graph_traversal_pool = produce_graph_traversal_pool
build_graph_pool = produce_graph_traversal_pool


def _fraction_value(value: object, name: str, index: int) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value, 1)
    raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")


def _exact_values(
    values: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
) -> tuple[Fraction, ...]:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != len(pool) or set(keys) != set(pool):
            raise ValueError(f"{name} mapping must contain exactly the graph-pool numbers")
        raw_values = tuple(values[number] for number in pool)
    else:
        raw_values = tuple(values)
        if len(raw_values) != len(pool):
            raise ValueError(f"{name} must contain exactly {len(pool)} values")
    converted = tuple(
        _fraction_value(value, name, index)
        for index, value in enumerate(raw_values, start=1)
    )
    if any(not 0 <= value <= 1 for value in converted):
        raise ValueError(f"{name} values must lie in [0,1]")
    return converted


def _exact_robustness(
    values: Sequence[Sequence[object]] | None,
    raw_scores: tuple[Fraction, ...],
    name: str,
) -> tuple[Robustness, ...]:
    if values is None:
        return tuple((value, value, value) for value in raw_scores)
    if len(values) != len(raw_scores):
        raise ValueError(f"{name} must contain exactly {len(raw_scores)} values")
    converted: list[Robustness] = []
    for index, raw_value in enumerate(values, start=1):
        if len(raw_value) != 3:
            raise ValueError(f"{name}[{index}] must contain exactly three values")
        tuple_value = tuple(
            _fraction_value(value, name, index) for value in raw_value
        )
        converted.append(cast(Robustness, tuple_value))
    return tuple(converted)


def _positions_for_pool(
    pool: tuple[int, ...], ordered: tuple[int, ...]
) -> tuple[int, ...]:
    if len(ordered) != len(pool) or set(ordered) != set(pool):
        raise ValueError("component order must contain exactly the graph-pool numbers")
    positions = [0] * len(_LEGAL_NUMBERS)
    for position, number in enumerate(ordered, start=1):
        positions[number - NUMBER_DOMAIN[0]] = position
    return tuple(positions)


def _component_ranking_from_order(
    pool: tuple[int, ...],
    raw_scores: tuple[Fraction, ...],
    ordered: tuple[int, ...],
    robustness: tuple[Robustness, ...],
) -> ComponentRanking:
    positions = _positions_for_pool(pool, ordered)
    normalized_by_number = {
        number: Fraction(RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1)
        for position, number in enumerate(ordered, start=1)
    }
    normalized = tuple(normalized_by_number[number] for number in pool)
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        ROBUSTNESS=robustness,
    )


def _parent_component_ranking(
    pool: tuple[int, ...],
    raw_scores: tuple[Fraction, ...],
    parent_order: Sequence[int],
    parent_robustness: Sequence[Robustness],
) -> ComponentRanking:
    pool_set = set(pool)
    ordered = tuple(number for number in parent_order if number in pool_set)
    robustness_by_number = {
        number: parent_robustness[number - NUMBER_DOMAIN[0]] for number in pool
    }
    robustness = tuple(robustness_by_number[number] for number in pool)
    return _component_ranking_from_order(pool, raw_scores, ordered, robustness)


def _gap_omission_component_ranking(
    parent_ranking: _gap_omission_parent.FusedNumberRanking,
    pool: tuple[int, ...],
) -> ComponentRanking:
    raw_scores = tuple(parent_ranking.mean_rank(number) for number in pool)
    return _parent_component_ranking(
        pool,
        raw_scores,
        parent_ranking.ORDERED_NUMBERS,
        parent_ranking.ROBUSTNESS,
    )


def _graph_component_ranking(
    parent_ranking: _graph_parent.FusedNumberRanking,
    pool: tuple[int, ...],
) -> ComponentRanking:
    raw_scores = tuple(parent_ranking.mean_rank(number) for number in pool)
    return _parent_component_ranking(
        pool,
        raw_scores,
        pool,
        parent_ranking.ROBUSTNESS,
    )


def calculate_gap_omission_ranking(
    history: HistoryInput,
    target_index: int,
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    """Return the omission-parent order restricted to a supplied graph pool."""

    pool = _validate_pool(pool_numbers)
    parent_ranking = calculate_gap_omission_parent_ranking(history, target_index)
    return _gap_omission_component_ranking(parent_ranking, pool)


def calculate_graph_ranking(
    history: HistoryInput,
    target_index: int,
) -> ComponentRanking:
    """Return the graph parent order normalized within its frozen top ten."""

    parent_ranking = calculate_graph_parent_ranking(history, target_index)
    pool = _validate_pool(parent_ranking.TOP_NUMBERS)
    return _graph_component_ranking(parent_ranking, pool)


def rank_pool_component_scores(
    pool_numbers: Sequence[int],
    raw_scores: Sequence[object] | Mapping[int, object],
    robustness: Sequence[Sequence[object]] | None = None,
    name: str = "component_scores",
) -> ComponentRanking:
    """Rank exact component values within the frozen graph pool."""

    pool = _validate_pool(pool_numbers)
    values = _exact_values(raw_scores, pool, name)
    exact_robustness = _exact_robustness(robustness, values, f"{name}_robustness")
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -values[pool.index(number)],
                -exact_robustness[pool.index(number)][0],
                -exact_robustness[pool.index(number)][1],
                -exact_robustness[pool.index(number)][2],
                number,
            ),
        )
    )
    return _component_ranking_from_order(pool, values, ordered, exact_robustness)


rank_component_scores = rank_pool_component_scores


def _normalized_values(
    values: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
) -> tuple[Fraction, ...]:
    return _exact_values(values, pool, name)


def _ranking_from_normalized_components(
    pool: tuple[int, ...], components: tuple[Fraction, ...]
) -> ComponentRanking:
    return rank_pool_component_scores(pool, components)


def rank_pairwise_scores(
    gap_omission_components: Sequence[object] | Mapping[int, object],
    graph_components: Sequence[object] | Mapping[int, object],
    *,
    pool_numbers: Sequence[int] | None = None,
    gap_omission_ranking: ComponentRanking | None = None,
    graph_ranking: ComponentRanking | None = None,
    gap_omission_parent_ranking: _gap_omission_parent.FusedNumberRanking | None = None,
    graph_parent_ranking: _graph_parent.FusedNumberRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized components with fixed one-half weights."""

    if pool_numbers is None:
        if isinstance(gap_omission_components, Mapping):
            pool = _validate_pool(tuple(gap_omission_components))
        else:
            values = tuple(gap_omission_components)
            if len(values) != RANKED_POOL_CARDINALITY:
                raise ValueError("pool_numbers is required for component sequences")
            pool = _validate_pool(tuple(range(1, RANKED_POOL_CARDINALITY + 1)))
    else:
        pool = _validate_pool(pool_numbers)

    gap = _normalized_values(gap_omission_components, pool, "gap_omission_components")
    graph = _normalized_values(graph_components, pool, "graph_components")
    pairwise = tuple(
        FUSION_WEIGHT_1 * gap[index] + FUSION_WEIGHT_2 * graph[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked = tuple(
        sorted(
            pool,
            key=lambda number: (
                -pairwise[pool.index(number)],
                -min(gap[pool.index(number)], graph[pool.index(number)]),
                -gap[pool.index(number)],
                -graph[pool.index(number)],
                number,
            ),
        )
    )
    positions = _positions_for_pool(pool, ranked)
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            GAP_OMISSION_COMPONENT=gap[pool.index(number)],
            GRAPH_COMPONENT=graph[pool.index(number)],
            PAIRWISE_SCORE=pairwise[pool.index(number)],
            MIN_COMPONENT_RANK=min(gap[pool.index(number)], graph[pool.index(number)]),
            POSITION=positions[number - NUMBER_DOMAIN[0]],
        )
        for number in ranked
    )
    ticket = cast(Ticket, tuple(sorted(ranked[:PICK_COUNT])))
    return PairwiseRanking(
        GAP_OMISSION_PARENT_RANKING=gap_omission_parent_ranking,
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        GRAPH_POOL=pool,
        GAP_OMISSION_RANKING=gap_omission_ranking
        or _ranking_from_normalized_components(pool, gap),
        GRAPH_RANKING=graph_ranking or _ranking_from_normalized_components(pool, graph),
        GAP_OMISSION_COMPONENTS=gap,
        GRAPH_COMPONENTS=graph,
        PAIRWISE_SCORES=pairwise,
        RANKED_NUMBERS=ranked,
        POSITIONS=positions,
        SCORES=records,
        NATIVE_TICKET=ticket,
    )


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ten-number ranking from both parents."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = calculate_graph_parent_ranking(
        prior_history, len(prior_history)
    )
    pool = _validate_pool(graph_parent_ranking.TOP_NUMBERS)
    graph_ranking = _graph_component_ranking(graph_parent_ranking, pool)
    gap_parent_ranking = calculate_gap_omission_parent_ranking(
        prior_history, len(prior_history)
    )
    gap_ranking = _gap_omission_component_ranking(gap_parent_ranking, pool)
    return rank_pairwise_scores(
        gap_ranking.NORMALIZED_RANKS,
        graph_ranking.NORMALIZED_RANKS,
        pool_numbers=pool,
        gap_omission_ranking=gap_ranking,
        graph_ranking=graph_ranking,
        gap_omission_parent_ranking=gap_parent_ranking,
        graph_parent_ranking=graph_parent_ranking,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking
calculate_fused_pairwise_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first six numbers in final pairwise rank order."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate = (
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
CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = (
    MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
)
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS

if signature_hash_for_semantics(CANDIDATE_SEMANTICS) != DESIGN_SIGNATURE_SHA256:
    raise RuntimeError("sealed design signature does not match candidate semantics")

_CONTRACT = dict(CANDIDATE_SEMANTICS)
_CONTRACT.update(
    {
        "IMPLEMENTATION_MODULE": IMPLEMENTATION_MODULE,
        "IMPLEMENTATION_SYMBOL": IMPLEMENTATION_SYMBOL,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "DESIGN_AUTHORITY_SHA256": DESIGN_AUTHORITY_SHA256,
        "PARENT_SOURCE_PATH_1": PARENT_SOURCE_PATH_1,
        "PARENT_SOURCE_PATH_2": PARENT_SOURCE_PATH_2,
        "PARENT_1_SOURCE_BLOB_ID": PARENT_1_SOURCE_BLOB_ID,
        "PARENT_2_SOURCE_BLOB_ID": PARENT_2_SOURCE_BLOB_ID,
        "PARENT_1_SOURCE_SHA256": PARENT_1_SOURCE_SHA256,
        "PARENT_2_SOURCE_SHA256": PARENT_2_SOURCE_SHA256,
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
    }
)
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(_CONTRACT)

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
    COMPONENT_NORMALIZATION_RULE=COMPONENT_NORMALIZATION_RULE_LINES,
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
    "DESIGN_AUTHORITY_SHA256",
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
    "GRAPH_WINDOWS",
    "HISTORY_ORDER",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "KNOWN_SEMANTIC_NEIGHBORS",
    "LOTTERY_TYPE",
    "METHOD_LEVEL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "OMISSION_WINDOWS",
    "OUTPUT_SHAPE",
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
    "HistoryInput",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "Ticket",
    "TicketPortfolio",
    "build_graph_pool",
    "build_graph_traversal_pool",
    "calculate_fused_gap_omission_parent_ranking",
    "calculate_fused_graph_parent_ranking",
    "calculate_fused_number_ranking",
    "calculate_fused_pairwise_ranking",
    "calculate_gap_omission_parent_ranking",
    "calculate_gap_omission_ranking",
    "calculate_gap_omission_window_rankings",
    "calculate_graph_fused_ranking",
    "calculate_graph_parent_ranking",
    "calculate_graph_ranking",
    "calculate_graph_window_rankings",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "produce_biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_pool",
    "produce_graph_traversal_pool",
    "produce_ticket",
    "rank_component_scores",
    "rank_pairwise_scores",
    "rank_pool_component_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
