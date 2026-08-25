"""Causal deterministic BigLotto TRANSITION_MARKOV + GRAPH candidate.

This research-only module implements the single candidate sealed by
``B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_WEIGHTED_SCORE_100_V1``.  The two
parent components are reproduced locally because this design freezes parent
windows of ``(30, 100, 300)`` and one hundred exact PageRank iterations,
which are not the parameters of the existing standalone source universes.

The producer consumes only the strictly prior history prefix.  It has no
outcome access, I/O, randomness, empirical tuning, catalog registration, or
runtime wiring.
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
type EdgeMatrix = tuple[tuple[int, ...], ...]
type EdgeScoreMatrix = tuple[tuple[Fraction, ...], ...]
type ProbabilityMatrix = tuple[tuple[Fraction, ...], ...]
type ScoreVector = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "b601749713b825538e0eb8befaa1bd0e6029bf2c473cd00583e87c453da36c8b"
)

FEATURE_1: Final[str] = "TRANSITION_MARKOV"
FEATURE_2: Final[str] = "GRAPH"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
WINDOWS: Final[tuple[int, int, int]] = (30, 100, 300)
TRANSITION_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
GRAPH_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
MINIMUM_HISTORY: Final[int] = 300
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = (
    "TEN_NUMBERS_VISITED_BY_FROZEN_GRAPH_TRAVERSAL_FROM_LEGAL_NUMBERS_1_TO_49"
)
NATIVE_TICKET_COUNT: Final[int] = 1
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PAGERANK_DAMPING: Final[Fraction] = Fraction(17, 20)
PAGERANK_TELEPORT: Final[Fraction] = Fraction(1, 49)
PAGERANK_INITIALIZATION: Final[str] = "UNIFORM_1/49"
PAGERANK_DANGLING_RULE: Final[str] = "UNIFORM_REDISTRIBUTION"
PAGERANK_ARITHMETIC: Final[str] = "EXACT_RATIONAL"
PAGERANK_POWER_ITERATIONS: Final[int] = 100
PAGERANK_ITERATIONS: Final[int] = PAGERANK_POWER_ITERATIONS
GRAPH_NODE_COUNT: Final[int] = 49
GRAPH_NODE_DOMAIN: Final[tuple[int, int]] = NUMBER_DOMAIN
GRAPH_EDGE_DEFINITION: Final[str] = (
    "UNDIRECTED_EDGE_WEIGHT_FOR_EACH_UNORDERED_PAIR_IN_EACH_DRAW"
)
GRAPH_EDGE_WEIGHT_RULE: Final[str] = "INTEGER_SAME_DRAW_COOCCURRENCE"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "MARKOV_PARENT=B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(30,100,300);"
    "WINDOW_DRAWS=history[T-W:T];FOR_EACH_ADJACENT_DRAW_PAIR_(D_t,D_{t+1})_IN_WINDOW_"
    "ADD_ONE_DIRECTED_COUNT_FOR_EVERY_ORDERED(i,j)_WHERE_i_IN_D_t_AND_j_IN_D_{t+1};"
    "P_W(i,j)=COUNT_W(i,j)/SUM_j_COUNT_W(i,j);ZERO_DENOMINATOR_P_W(i,j)=0;"
    "SOURCE_STATE=UNIQUE_SORTED_NUMBERS_IN_history[T-1];"
    "MARKOV_SCORE_W(j)=MEAN_EXACT_RATIONAL(P_W(i,j)_FOR_i_IN_SOURCE_STATE);"
    "MARKOV_SCORE(j)=MEAN_EXACT_RATIONAL_OF_MARKOV_SCORE_W(j)_OVER_W_IN_(30,100,300);"
    "MARKOV_RANK=SCORE_DESC_NUMBER_ASC;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "GRAPH_PARENT=B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(30,100,300);"
    "WINDOW_DRAWS=history[T-W:T];VERTICES=1..49;"
    "ADD_ONE_UNDIRECTED_EDGE_WEIGHT_FOR_EACH_UNORDERED_PAIR_(i,j)_IN_EACH_DRAW;"
    "NO_SELF_EDGES;PAGERANK_DAMPING=17/20;TELEPORT=1/49;"
    "DANGLING_MASS_REDISTRIBUTED_UNIFORMLY;INITIAL_VECTOR=UNIFORM_1/49;"
    "POWER_ITERATIONS=100_EXACT;GRAPH_SCORE(n)=MEAN_EXACT_RATIONAL_OF_"
    "PAGERANK_W(n)_OVER_W_IN_(30,100,300);GRAPH_RANK=SCORE_DESC_WEIGHTED_DEGREE_DESC_"
    "NUMBER_ASC;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];MARKOV_WINDOWS=(30,100,300);"
    "MARKOV_DRAWS_W=history[T-W:T]_FOR_EACH_W;ALL_MARKOV_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_WINDOWS=(30,100,300);"
    "GRAPH_DRAWS_W=history[T-W:T]_FOR_EACH_W;ALL_GRAPH_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, str]] = (
    "MARKOV_SCORE_SORTED_DESC_THEN_NUMBER_ASC;ORDINAL_POSITION_P_IN_1..49;"
    "NORMALIZED_MARKOV=(49-P)/48;EXACT_RATIONAL",
    "GRAPH_PAGERANK_SCORE_SORTED_DESC_THEN_WEIGHTED_DEGREE_DESC_THEN_NUMBER_ASC;"
    "ORDINAL_POSITION_P_IN_1..49;NORMALIZED_GRAPH=(49-P)/48;EXACT_RATIONAL",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, str]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_MULTISCALE_MARKOV_NEXT_NUMBER_SCORE_OVER_LEGAL_NUMBERS_1_TO_49"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RATIONAL_MULTISCALE_WEIGHTED_UNDIRECTED_PAGERANK_SCORE_OVER_LEGAL_NUMBERS_1_TO_49"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*MARKOV_NORMALIZED_TRANSITION_RANK(n)+"
    "1/2*GRAPH_NORMALIZED_PAGERANK_RANK(n);EXACT_RATIONAL"
)

NUMBER_RANKING_RULE_LINES: Final[tuple[str, str, str]] = (
    "Use fused pairwise score descending for the traversal seed and every disconnected restart.",
    "Within the graph traversal, use edge score descending, fused pairwise score "
    "descending, then number ascending.",
    "The final ten-number pool is the exact traversal order; select its first six "
    "numbers and sort those six ascending for the native ticket.",
)
NUMBER_RANKING_RULE: Final[tuple[str, str, str]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, str, str, str]] = (
    "Markov parent tie: exact multiscale Markov score descending, then number ascending.",
    "Graph parent tie: exact multiscale PageRank descending, weighted graph degree "
    "descending, then number ascending.",
    "Traversal frontier tie: aggregate edge score descending, fused score descending, "
    "then number ascending; restart seed tie uses fused score descending then number ascending.",
    "Final ticket tie: traversal visit order ascending, Markov normalized rank descending, "
    "Graph normalized rank descending, then number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, str, str, str]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_AGGREGATE_UNDIRECTED_GRAPH_WITH_EDGE_SCORE(i,j)=MEAN_EXACT_RATIONAL_OF_"
    "[COOCCURRENCE_COUNT_W(i,j)/W_FOR_W_IN_(30,100,300)];START_AT_THE_UNVISITED_"
    "NUMBER_WITH_HIGHEST_FUSED_SCORE_THEN_NUMBER_ASC;VISIT_CURRENT_NODE;"
    "APPEND_UNVISITED_NEIGHBORS_SORTED_BY_EDGE_SCORE_DESC_THEN_FUSED_SCORE_DESC_"
    "THEN_NUMBER_ASC;WHEN_FRONTIER_IS_EMPTY_RESTART_AT_HIGHEST_FUSED_SCORE_"
    "UNVISITED_NUMBER;STOP_AFTER_EXACTLY_10_VISITED_NUMBERS;TRAVERSAL_ORDER_IS_"
    "THE_RANKED_POOL_ORDER"
)
TICKET_SELECTION_RULE: Final[str] = (
    "TAKE_FIRST_6_NUMBERS_IN_EXACT_TRAVERSAL_POOL_ORDER;"
    "SORT_SELECTED_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_RULE: Final[str] = TICKET_SELECTION_RULE

CAUSAL_CUTOFF_RULE: Final[str] = (
    "TARGET_INDEX=T;USE_ONLY_history[:T];ALL_MARKOV_AND_GRAPH_WINDOWS_END_AT_T;"
    "history[T]AND_EVERY_LATER_ROW_EXCLUDED_FROM_TRANSITIONS_GRAPH_EDGES_PAGERANK_"
    "FUSION_TRAVERSAL_AND_TICKET"
)
FALLBACK_RULE: Final[str] = (
    "IF_len(history)<300_RAISE_VALUE_ERROR_MINIMUM_HISTORY_300;"
    "NO_SYNTHETIC_NUMBERS_NO_TARGET_OR_FUTURE_ROWS_NO_RANDOM_FALLBACK;"
    "OTHERWISE_APPLY_THE_FROZEN_RULES_EXACTLY"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;PARENT_WINDOWS=(30,100,300);MARKOV_SOURCE_STATE=UNIQUE_SORTED_"
    "NUMBERS_IN_history[T-1];GRAPH_DAMPING=17/20;GRAPH_TELEPORT=1/49;"
    "GRAPH_DANGLING_MASS_UNIFORM;PAGERANK_POWER_ITERATIONS=100_EXACT;"
    "TRAVERSAL_POOL=10;TICKET_SIZE=6;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "LAG_DEPENDENCE_SIGNAL"
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, str, str, str]] = (
    "Do not change the parent window tuple (30,100,300), target cutoff, target-row "
    "exclusion, or minimum history.",
    "Do not change the directed transition definition, source state, weighted graph "
    "edge definition, PageRank damping 17/20, uniform teleport, or exactly 100 power iterations.",
    "Do not change ordinal rank normalization, symmetric 1/2 and 1/2 fusion, ten-node "
    "traversal pool, first-six ticket selection, one native ticket, or ascending ticket sort.",
    "Do not add RNG, target outcomes, historical or performance tuning, multi-ticket output, "
    "catalog wiring, or future-row access.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_TRANSITION_MARKOV_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;WINDOW=100;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe[B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;WINDOW=100;PARTIALLY_COVERED;NOT_EQUIVALENT]",
    "B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1[TRANSITION_MARKOV_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074[LIVE_FOURIER30_MARKOV30_TWO_TICKET;NOT_THIS_SINGLE_TICKET_GRAPH_TRAVERSAL]",
    "ORIGIN_MAIN_e9b15220e44c390fe79489370d3722f83d44c5c4[MERGED_ZONE_BALANCE_SINGLETON;NO_LEVEL2_PAIRWISE_PREDICTION_COVERAGE]",
    "PR #185[MERGED;FRONTEND_ZONE_BALANCE_SINGLETON;NO_LEVEL2_PAIRWISE_PREDICTION_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 300 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores and ordinal normalization for one number pool."""

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
            raise ValueError("number is not in the component pool") from error

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
class MarkovWindow:
    """Exact directed transition state and rank vector for one frozen window."""

    WINDOW: int
    SOURCE_STATE: tuple[int, ...]
    WINDOW_DRAW_COUNT: int
    TRANSITION_COUNT: int
    TRANSITION_COUNTS: TransitionMatrix
    OUTGOING_COUNTS: tuple[int, ...]
    CONDITIONAL_PROBABILITIES: ProbabilityMatrix
    SCORES: ScoreVector
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: ScoreVector

    @property
    def ANCHOR_DRAW(self) -> tuple[int, ...]:
        return self.SOURCE_STATE

    @property
    def TRANSITION_MATRIX(self) -> TransitionMatrix:
        return self.TRANSITION_COUNTS

    @property
    def COUNTS(self) -> TransitionMatrix:
        return self.TRANSITION_COUNTS

    @property
    def OUTGOING_COUNT_VECTOR(self) -> tuple[int, ...]:
        return self.OUTGOING_COUNTS

    @property
    def PROBABILITIES(self) -> ProbabilityMatrix:
        return self.CONDITIONAL_PROBABILITIES

    @property
    def RANKS(self) -> ScoreVector:
        return self.SCORES

    def score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SCORES[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]


WindowRanking = MarkovWindow
TransitionWindow = MarkovWindow


@dataclass(frozen=True, slots=True)
class GraphWindow:
    """Exact weighted co-occurrence graph and PageRank for one window."""

    WINDOW: int
    EDGE_COUNTS: EdgeMatrix
    NODE_STRENGTHS: tuple[int, ...]
    PAGERANKS: ScoreVector
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: ScoreVector

    @property
    def EDGE_MATRIX(self) -> EdgeMatrix:
        return self.EDGE_COUNTS

    @property
    def STRENGTHS(self) -> tuple[int, ...]:
        return self.NODE_STRENGTHS

    @property
    def RANKS(self) -> ScoreVector:
        return self.PAGERANKS

    def edge(self, left: int, right: int) -> int:
        _validate_number(left)
        _validate_number(right)
        return self.EDGE_COUNTS[left - 1][right - 1]

    def strength(self, number: int) -> int:
        _validate_number(number)
        return self.NODE_STRENGTHS[number - 1]

    def pagerank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAGERANKS[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedParentRanking:
    """Exact mean score and rank vector for one multiscale parent."""

    RAW_SCORES: ScoreVector
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: ScoreVector
    WINDOW_RANKINGS: tuple[MarkovWindow | GraphWindow, ...]
    WEIGHTED_DEGREES: tuple[int, ...]

    @property
    def SCORES(self) -> ScoreVector:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

    @property
    def TOP_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS[:RANKED_POOL_CARDINALITY]

    def score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RAW_SCORES[number - 1]

    def mean_score(self, number: int) -> Fraction:
        return self.score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    def weighted_degree(self, number: int) -> int:
        _validate_number(number)
        return self.WEIGHTED_DEGREES[number - 1]


FusedNumberRanking = FusedParentRanking


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score in the traversal pool."""

    NUMBER: int
    TRANSITION_MARKOV_COMPONENT: Fraction
    GRAPH_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    POSITION: int

    @property
    def TRANSITION_MARKOV_RANK(self) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENT

    @property
    def GRAPH_RANK(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """The exact ten-number traversal pool and one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    TRANSITION_MARKOV_COMPONENTS: ScoreVector
    GRAPH_COMPONENTS: ScoreVector
    PAIRWISE_SCORES: ScoreVector
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    FUSED_RANKED_NUMBERS: tuple[int, ...] = ()
    ALL_TRANSITION_MARKOV_COMPONENTS: ScoreVector = ()
    ALL_GRAPH_COMPONENTS: ScoreVector = ()
    ALL_PAIRWISE_SCORES: ScoreVector = ()
    MARKOV_PARENT_RANKING: FusedParentRanking | None = None
    GRAPH_PARENT_RANKING: FusedParentRanking | None = None
    EDGE_SCORES: EdgeScoreMatrix | None = None

    @property
    def ORDERED_NUMBERS(self) -> tuple[int, ...]:
        return self.RANKED_NUMBERS

    @property
    def GRAPH_POOL(self) -> tuple[int, ...]:
        return self.POOL_NUMBERS

    @property
    def GRAPH_TRAVERSAL_POOL(self) -> tuple[int, ...]:
        return self.POOL_NUMBERS

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
            raise ValueError("number is not in the traversal pool") from error

    def transition_markov_component(self, number: int) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENTS[self._pool_position(number)]

    def markov_component(self, number: int) -> Fraction:
        return self.transition_markov_component(number)

    def graph_component(self, number: int) -> Fraction:
        return self.GRAPH_COMPONENTS[self._pool_position(number)]

    def pairwise_score(self, number: int) -> Fraction:
        return self.PAIRWISE_SCORES[self._pool_position(number)]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - NUMBER_DOMAIN[0]]

    def score_record(self, number: int) -> PairwiseNumberScore:
        position = self.position(number)
        if position == 0:
            raise ValueError("number is not in the traversal pool")
        return self.SCORES[position - 1]


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """The selected candidate identity and sealed design signature."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for the one frozen candidate."""

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


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return an immutable validated copy of only ``history[:target_index]``."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in WINDOWS:
        raise ValueError(f"window must be one of {WINDOWS}")


def _validate_transition_matrix(
    raw_counts: Sequence[Sequence[object]],
) -> TransitionMatrix:
    if len(raw_counts) != GRAPH_NODE_COUNT:
        raise ValueError("transition_counts must contain exactly 49 rows")
    rows: list[tuple[int, ...]] = []
    for row_index, raw_row in enumerate(raw_counts):
        if len(raw_row) != GRAPH_NODE_COUNT:
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
    mutable_counts = [[0] * GRAPH_NODE_COUNT for _ in range(GRAPH_NODE_COUNT)]
    for source_draw, destination_draw in pairwise(validated_draws):
        for source_number in source_draw:
            for destination_number in destination_draw:
                mutable_counts[source_number - 1][destination_number - 1] += 1
    counts = _validate_transition_matrix(tuple(tuple(row) for row in mutable_counts))
    expected_total = max(0, len(validated_draws) - 1) * PICK_COUNT * PICK_COUNT
    if sum(map(sum, counts)) != expected_total:
        raise RuntimeError("each adjacent draw pair must contribute exactly 36 transitions")
    return counts


build_transition_matrix = build_transition_counts
calculate_transition_counts = build_transition_counts


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
        if len(outgoing_counts) != GRAPH_NODE_COUNT:
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
            probabilities.append((Fraction(0, 1),) * GRAPH_NODE_COUNT)
        else:
            probabilities.append(tuple(Fraction(value, denominator) for value in row))
    return tuple(probabilities)


calculate_transition_probabilities = calculate_conditional_transition_probabilities
calculate_exact_conditional_probabilities = calculate_conditional_transition_probabilities


def _rank_full_scores(
    raw_scores: ScoreVector,
    *,
    weighted_degrees: tuple[int, ...] | None = None,
) -> tuple[tuple[int, ...], tuple[int, ...], ScoreVector]:
    if len(raw_scores) != GRAPH_NODE_COUNT:
        raise ValueError("raw_scores must contain exactly 49 values")
    if weighted_degrees is not None and len(weighted_degrees) != GRAPH_NODE_COUNT:
        raise ValueError("weighted_degrees must contain exactly 49 values")
    ordered = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (
                -raw_scores[number - 1],
                -(weighted_degrees[number - 1] if weighted_degrees is not None else 0),
                number,
            ),
        )
    )
    positions = [0] * GRAPH_NODE_COUNT
    normalized = [Fraction(0, 1)] * GRAPH_NODE_COUNT
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
        normalized[number - 1] = Fraction(GRAPH_NODE_COUNT - position, GRAPH_NODE_COUNT - 1)
    return ordered, tuple(positions), tuple(normalized)


def _markov_window_from_prior_history(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> MarkovWindow:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(
            f"window {window} requires at least {window} prior draws"
        )
    window_draws = prior_history[-window:]
    source_state = tuple(sorted(set(prior_history[-1])))
    transition_counts = build_transition_counts(window_draws)
    outgoing_counts = calculate_outgoing_counts(transition_counts)
    probabilities = calculate_conditional_transition_probabilities(
        transition_counts, outgoing_counts
    )
    scores = [Fraction(0, 1)] * GRAPH_NODE_COUNT
    for source_number in source_state:
        for candidate_number, probability in enumerate(
            probabilities[source_number - 1], start=NUMBER_DOMAIN[0]
        ):
            scores[candidate_number - 1] += probability / len(source_state)
    expected_mass = Fraction(
        sum(outgoing_counts[number - 1] > 0 for number in source_state),
        len(source_state),
    )
    if sum(scores, Fraction(0, 1)) != expected_mass:
        raise RuntimeError("transition probability mass invariant failed")
    score_vector = tuple(scores)
    ordered, positions, normalized = _rank_full_scores(score_vector)
    return MarkovWindow(
        WINDOW=window,
        SOURCE_STATE=source_state,
        WINDOW_DRAW_COUNT=len(window_draws),
        TRANSITION_COUNT=max(0, len(window_draws) - 1),
        TRANSITION_COUNTS=transition_counts,
        OUTGOING_COUNTS=outgoing_counts,
        CONDITIONAL_PROBABILITIES=probabilities,
        SCORES=score_vector,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


def rank_numbers_by_window(
    history: HistoryInput, target_index: int, window: int
) -> MarkovWindow:
    """Rank legal numbers using one exact frozen transition window."""

    return _markov_window_from_prior_history(
        validate_prior_history(history, target_index), window
    )


build_transition_window = rank_numbers_by_window
calculate_transition_window = rank_numbers_by_window
calculate_markov_window = rank_numbers_by_window


def calculate_markov_window_scores(
    history: HistoryInput, target_index: int, window: int
) -> ScoreVector:
    return rank_numbers_by_window(history, target_index, window).SCORES


def calculate_markov_raw_scores(
    history: HistoryInput, target_index: int, window: int | None = None
) -> ScoreVector:
    """Return one window's or the sealed multiscale Markov raw scores."""

    if window is not None:
        return calculate_markov_window_scores(history, target_index, window)
    return calculate_markov_parent_ranking(history, target_index).RAW_SCORES


calculate_transition_markov_raw_scores = calculate_markov_raw_scores
calculate_markov_scores = calculate_markov_raw_scores
calculate_transition_scores = calculate_markov_raw_scores


def calculate_markov_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[MarkovWindow, MarkovWindow, MarkovWindow]:
    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _markov_window_from_prior_history(prior_history, window) for window in WINDOWS
    )
    return cast(tuple[MarkovWindow, MarkovWindow, MarkovWindow], rankings)


calculate_window_rankings = calculate_markov_window_rankings
calculate_markov_rankings = calculate_markov_window_rankings
calculate_transition_rankings = calculate_markov_window_rankings


def rank_markov_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank exact Markov scores over all 49 legal numbers."""

    scores = _full_fraction_scores(raw_scores, "markov_raw_scores")
    ordered, positions, normalized = _rank_full_scores(scores)
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


rank_transition_markov_scores = rank_markov_scores


def _fuse_markov_window_rankings(
    window_rankings: Sequence[MarkovWindow],
) -> FusedParentRanking:
    if tuple(ranking.WINDOW for ranking in window_rankings) != WINDOWS:
        raise ValueError(f"window_rankings must contain windows in order {WINDOWS}")
    raw_scores = tuple(
        sum((ranking.SCORES[number - 1] for ranking in window_rankings), Fraction(0, 1))
        / len(window_rankings)
        for number in LEGAL_NUMBERS
    )
    ordered, positions, normalized = _rank_full_scores(raw_scores)
    return FusedParentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        WINDOW_RANKINGS=tuple(window_rankings),
        WEIGHTED_DEGREES=(0,) * GRAPH_NODE_COUNT,
    )


fuse_markov_window_rankings = _fuse_markov_window_rankings
fuse_transition_markov_rankings = _fuse_markov_window_rankings


def calculate_markov_parent_ranking(
    history: HistoryInput, target_index: int
) -> FusedParentRanking:
    return _fuse_markov_window_rankings(calculate_markov_window_rankings(history, target_index))


calculate_fused_markov_parent_ranking = calculate_markov_parent_ranking
calculate_fused_markov_number_ranking = calculate_markov_parent_ranking
calculate_markov_fused_ranking = calculate_markov_parent_ranking


def calculate_transition_markov_components(
    history: HistoryInput, target_index: int
) -> ScoreVector:
    return calculate_markov_parent_ranking(history, target_index).NORMALIZED_RANKS


transition_markov_components = calculate_transition_markov_components
markov_components = calculate_transition_markov_components


def _validate_edge_matrix(raw_edges: Sequence[Sequence[object]]) -> EdgeMatrix:
    if len(raw_edges) != GRAPH_NODE_COUNT:
        raise ValueError("edge_counts must contain exactly 49 rows")
    rows: list[tuple[int, ...]] = []
    for row_index, raw_row in enumerate(raw_edges):
        if len(raw_row) != GRAPH_NODE_COUNT:
            raise ValueError(
                f"edge_counts[{row_index}] must contain exactly 49 columns"
            )
        row: list[int] = []
        for column_index, raw_value in enumerate(raw_row):
            if type(raw_value) is not int or raw_value < 0:
                raise ValueError(
                    f"edge_counts[{row_index}][{column_index}] must be a non-negative integer"
                )
            row.append(raw_value)
        rows.append(tuple(row))
    matrix = tuple(rows)
    for number in range(GRAPH_NODE_COUNT):
        if matrix[number][number] != 0:
            raise ValueError("edge_counts must have zero self-edges")
        for other in range(number + 1, GRAPH_NODE_COUNT):
            if matrix[number][other] != matrix[other][number]:
                raise ValueError("edge_counts must be symmetric")
    return matrix


def _node_strengths(edge_counts: EdgeMatrix) -> tuple[int, ...]:
    return tuple(sum(row) for row in edge_counts)


def build_cooccurrence_edge_counts(draws: Iterable[HistoryDraw]) -> EdgeMatrix:
    """Build exact undirected same-draw co-occurrence edge counts."""

    mutable_edges = [[0] * GRAPH_NODE_COUNT for _ in range(GRAPH_NODE_COUNT)]
    draw_count = 0
    for draw_count, raw_draw in enumerate(draws, start=1):
        draw = _validate_draw(raw_draw, draw_count - 1)
        for left, right in combinations(sorted(draw), 2):
            mutable_edges[left - 1][right - 1] += 1
            mutable_edges[right - 1][left - 1] += 1
    edge_counts = _validate_edge_matrix(tuple(tuple(row) for row in mutable_edges))
    if sum(map(sum, edge_counts)) != draw_count * 2 * (PICK_COUNT * (PICK_COUNT - 1) // 2):
        raise RuntimeError("each historical draw must contribute exactly 30 directed edges")
    return edge_counts


build_graph_edge_counts = build_cooccurrence_edge_counts


def _validate_page_rank_state(ranks: ScoreVector) -> None:
    if len(ranks) != GRAPH_NODE_COUNT:
        raise RuntimeError("PageRank state has the wrong node count")
    if any(rank < 0 for rank in ranks):
        raise RuntimeError("PageRank state contains a negative rank")
    if sum(ranks, Fraction(0, 1)) != Fraction(1, 1):
        raise RuntimeError("PageRank state does not sum to one exactly")


def calculate_page_rank(
    edge_counts: Sequence[Sequence[object]],
    node_strengths: Sequence[object] | None = None,
) -> ScoreVector:
    """Run exactly 100 iterations of exact-rational PageRank."""

    matrix = _validate_edge_matrix(edge_counts)
    expected_strengths = _node_strengths(matrix)
    if node_strengths is None:
        strengths = expected_strengths
    else:
        raw_strengths = tuple(node_strengths)
        if len(raw_strengths) != GRAPH_NODE_COUNT or any(
            type(value) is not int or value < 0 for value in raw_strengths
        ):
            raise ValueError("node_strengths must contain 49 non-negative integers")
        strengths = cast(tuple[int, ...], raw_strengths)
        if strengths != expected_strengths:
            raise ValueError("node_strengths must equal the exact edge-row sums")

    ranks: ScoreVector = (PAGERANK_TELEPORT,) * GRAPH_NODE_COUNT
    _validate_page_rank_state(ranks)
    teleport_mass = (Fraction(1, 1) - PAGERANK_DAMPING) * PAGERANK_TELEPORT
    for _ in range(PAGERANK_POWER_ITERATIONS):
        dangling_mass = sum(
            (ranks[index] for index, strength in enumerate(strengths) if strength == 0),
            Fraction(0, 1),
        )
        next_ranks: list[Fraction] = []
        for target_index in range(GRAPH_NODE_COUNT):
            incoming = sum(
                (
                    ranks[source_index]
                    * matrix[source_index][target_index]
                    / strengths[source_index]
                    for source_index, strength in enumerate(strengths)
                    if strength > 0
                ),
                Fraction(0, 1),
            )
            next_ranks.append(
                teleport_mass
                + PAGERANK_DAMPING
                * (incoming + dangling_mass * PAGERANK_TELEPORT)
            )
        ranks = tuple(next_ranks)
        _validate_page_rank_state(ranks)
    return ranks


exact_pagerank = calculate_page_rank
calculate_exact_pagerank = calculate_page_rank


def _graph_window_from_prior_history(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> GraphWindow:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(
            f"window {window} requires at least {window} prior draws"
        )
    window_draws = prior_history[-window:]
    edge_counts = build_cooccurrence_edge_counts(window_draws)
    strengths = _node_strengths(edge_counts)
    ranks = calculate_page_rank(edge_counts, strengths)
    ordered, positions, normalized = _rank_full_scores(ranks, weighted_degrees=strengths)
    return GraphWindow(
        WINDOW=window,
        EDGE_COUNTS=edge_counts,
        NODE_STRENGTHS=strengths,
        PAGERANKS=ranks,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


def build_graph_for_window(
    history: HistoryInput, target_index: int, window: int
) -> GraphWindow:
    """Build one exact graph window from the strictly prior history."""

    return _graph_window_from_prior_history(
        validate_prior_history(history, target_index), window
    )


build_graph_window = build_graph_for_window
calculate_graph_window = build_graph_for_window


def calculate_graph_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[GraphWindow, GraphWindow, GraphWindow]:
    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _graph_window_from_prior_history(prior_history, window) for window in WINDOWS
    )
    return cast(tuple[GraphWindow, GraphWindow, GraphWindow], rankings)


calculate_window_graph_rankings = calculate_graph_window_rankings
calculate_graph_rankings = calculate_graph_window_rankings


def _fuse_graph_window_rankings(
    window_rankings: Sequence[GraphWindow],
) -> FusedParentRanking:
    if tuple(ranking.WINDOW for ranking in window_rankings) != WINDOWS:
        raise ValueError(f"window_rankings must contain windows in order {WINDOWS}")
    raw_scores = tuple(
        sum((ranking.PAGERANKS[number - 1] for ranking in window_rankings), Fraction(0, 1))
        / len(window_rankings)
        for number in LEGAL_NUMBERS
    )
    weighted_degrees = tuple(
        sum((ranking.NODE_STRENGTHS[number - 1] for ranking in window_rankings), 0)
        for number in LEGAL_NUMBERS
    )
    ordered, positions, normalized = _rank_full_scores(
        raw_scores, weighted_degrees=weighted_degrees
    )
    return FusedParentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        WINDOW_RANKINGS=tuple(window_rankings),
        WEIGHTED_DEGREES=weighted_degrees,
    )


fuse_graph_window_rankings = _fuse_graph_window_rankings


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> FusedParentRanking:
    return _fuse_graph_window_rankings(calculate_graph_window_rankings(history, target_index))


calculate_fused_graph_parent_ranking = calculate_graph_parent_ranking
calculate_graph_fused_ranking = calculate_graph_parent_ranking
calculate_fused_graph_number_ranking = calculate_graph_parent_ranking


def calculate_graph_raw_scores(
    history: HistoryInput, target_index: int
) -> ScoreVector:
    return calculate_graph_parent_ranking(history, target_index).RAW_SCORES


calculate_graph_scores = calculate_graph_raw_scores


def rank_graph_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    weighted_degrees: Sequence[object] | None = None,
) -> ComponentRanking:
    """Rank exact PageRank scores using weighted-degree and number ties."""

    scores = _full_fraction_scores(raw_scores, "graph_raw_scores")
    if weighted_degrees is None:
        degrees = (0,) * GRAPH_NODE_COUNT
    else:
        raw_degrees = tuple(weighted_degrees)
        if len(raw_degrees) != GRAPH_NODE_COUNT or any(
            type(value) is not int or value < 0 for value in raw_degrees
        ):
            raise ValueError("weighted_degrees must contain 49 non-negative integers")
        degrees = cast(tuple[int, ...], raw_degrees)
    ordered, positions, normalized = _rank_full_scores(scores, weighted_degrees=degrees)
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


rank_graph_parent_scores = rank_graph_scores


def calculate_graph_components(
    history: HistoryInput, target_index: int
) -> ScoreVector:
    return calculate_graph_parent_ranking(history, target_index).NORMALIZED_RANKS


graph_components = calculate_graph_components


def _validate_edge_score_matrix(raw_edges: Sequence[Sequence[object]]) -> EdgeScoreMatrix:
    if len(raw_edges) != GRAPH_NODE_COUNT:
        raise ValueError("edge_scores must contain exactly 49 rows")
    rows: list[tuple[Fraction, ...]] = []
    for row_index, raw_row in enumerate(raw_edges):
        if len(raw_row) != GRAPH_NODE_COUNT:
            raise ValueError(
                f"edge_scores[{row_index}] must contain exactly 49 columns"
            )
        row: list[Fraction] = []
        for column_index, raw_value in enumerate(raw_row):
            if isinstance(raw_value, Fraction):
                value = raw_value
            elif type(raw_value) is int:
                value = Fraction(raw_value, 1)
            else:
                raise TypeError(
                    f"edge_scores[{row_index}][{column_index}] must use exact arithmetic"
                )
            if value < 0:
                raise ValueError("edge_scores must be non-negative")
            row.append(value)
        rows.append(tuple(row))
    matrix = tuple(rows)
    for number in range(GRAPH_NODE_COUNT):
        if matrix[number][number] != 0:
            raise ValueError("edge_scores must have zero self-edges")
        for other in range(number + 1, GRAPH_NODE_COUNT):
            if matrix[number][other] != matrix[other][number]:
                raise ValueError("edge_scores must be symmetric")
    return matrix


def _aggregate_edge_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> EdgeScoreMatrix:
    windows = tuple(
        build_cooccurrence_edge_counts(prior_history[-window:]) for window in WINDOWS
    )
    values: list[list[Fraction]] = [
        [Fraction(0, 1)] * GRAPH_NODE_COUNT for _ in range(GRAPH_NODE_COUNT)
    ]
    for left in range(GRAPH_NODE_COUNT):
        for right in range(GRAPH_NODE_COUNT):
            values[left][right] = sum(
                (
                    Fraction(edges[left][right], window)
                    for edges, window in zip(windows, WINDOWS, strict=True)
                ),
                Fraction(0, 1),
            ) / len(WINDOWS)
    return _validate_edge_score_matrix(tuple(tuple(row) for row in values))


def build_aggregate_graph_edge_scores(
    history: HistoryInput, target_index: int
) -> EdgeScoreMatrix:
    """Return the exact mean of per-window co-occurrence rates."""

    return _aggregate_edge_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


build_aggregate_edge_matrix = build_aggregate_graph_edge_scores
calculate_aggregate_edge_scores = build_aggregate_graph_edge_scores


def _full_fraction_scores(
    values: Sequence[object] | Mapping[int, object], name: str
) -> ScoreVector:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != GRAPH_NODE_COUNT or set(keys) != set(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in LEGAL_NUMBERS)
    else:
        raw_values = tuple(values)
        if len(raw_values) != GRAPH_NODE_COUNT:
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


def _pool_numbers(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) < PICK_COUNT:
        raise ValueError("pool must contain at least six legal numbers")
    if any(type(number) is not int or number not in LEGAL_NUMBERS for number in pool):
        raise ValueError("pool must contain legal integer numbers")
    if len(set(pool)) != len(pool):
        raise ValueError("pool must contain unique numbers")
    return pool


def _component_values(
    values: Sequence[object] | Mapping[int, object], pool: tuple[int, ...], name: str
) -> ScoreVector:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if set(keys) != set(pool) and set(keys) != set(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain the pool or keys 1..49")
        raw_values = tuple(values[number] for number in pool)
    else:
        raw_values = tuple(values)
        if len(raw_values) == len(pool):
            pass
        elif len(raw_values) == GRAPH_NODE_COUNT:
            raw_values = tuple(raw_values[number - 1] for number in pool)
        else:
            raise ValueError(f"{name} must contain exactly {len(pool)} or 49 values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            fraction = value
        elif type(value) is int:
            fraction = Fraction(value, 1)
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
        if not 0 <= fraction <= 1:
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        converted.append(fraction)
    return tuple(converted)


def _infer_pool(
    first: Sequence[object] | Mapping[int, object],
    second: Sequence[object] | Mapping[int, object],
) -> tuple[int, ...]:
    if isinstance(first, Mapping):
        keys = tuple(first)
        if set(keys) == set(LEGAL_NUMBERS):
            return LEGAL_NUMBERS
        return _pool_numbers(cast(Sequence[int], keys))
    first_values = tuple(first)
    if len(first_values) == GRAPH_NODE_COUNT:
        return LEGAL_NUMBERS
    if len(first_values) >= PICK_COUNT and len(first_values) == RANKED_POOL_CARDINALITY:
        return tuple(range(1, RANKED_POOL_CARDINALITY + 1))
    raise ValueError("pool_numbers is required for non-49 component sequences")


def rank_pairwise_scores(
    transition_markov_components: Sequence[object] | Mapping[int, object],
    graph_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int] | None = None,
    *,
    traversal_order: Sequence[int] | None = None,
    fused_ranked_numbers: Sequence[int] | None = None,
    edge_scores: EdgeScoreMatrix | None = None,
    markov_parent_ranking: FusedParentRanking | None = None,
    graph_parent_ranking: FusedParentRanking | None = None,
    all_transition_markov_components: ScoreVector = (),
    all_graph_components: ScoreVector = (),
    all_pairwise_scores: ScoreVector = (),
) -> PairwiseRanking:
    """Fuse two exact normalized components with the sealed one-half weights."""

    pool = _pool_numbers(pool_numbers) if pool_numbers is not None else _infer_pool(
        transition_markov_components, graph_components
    )
    markov = _component_values(transition_markov_components, pool, "transition_markov_components")
    graph = _component_values(graph_components, pool, "graph_components")
    pairwise = tuple(
        FUSION_WEIGHT_1 * markov[index] + FUSION_WEIGHT_2 * graph[index]
        for index in range(len(pool))
    )
    by_number = {
        number: (markov[index], graph[index], pairwise[index])
        for index, number in enumerate(pool)
    }
    fused_order = tuple(
        sorted(
            pool,
            key=lambda number: (
                -by_number[number][2],
                -by_number[number][0],
                -by_number[number][1],
                number,
            ),
        )
    )
    if fused_ranked_numbers is not None:
        candidate_fused_order = tuple(fused_ranked_numbers)
        if (
            len(candidate_fused_order) == len(pool)
            and set(candidate_fused_order) == set(pool)
        ) or (
            len(candidate_fused_order) == GRAPH_NODE_COUNT
            and set(candidate_fused_order) == set(LEGAL_NUMBERS)
            and set(pool).issubset(set(candidate_fused_order))
        ):
            fused_order = candidate_fused_order
        else:
            raise ValueError("fused_ranked_numbers must contain exactly the pool")
    final_order = fused_order if traversal_order is None else tuple(traversal_order)
    if len(final_order) < PICK_COUNT or any(number not in by_number for number in final_order):
        raise ValueError("traversal_order must contain at least six pool numbers")
    if len(set(final_order)) != len(final_order):
        raise ValueError("traversal_order must contain unique numbers")
    positions = [0] * GRAPH_NODE_COUNT
    for position, number in enumerate(final_order, start=1):
        positions[number - NUMBER_DOMAIN[0]] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            TRANSITION_MARKOV_COMPONENT=by_number[number][0],
            GRAPH_COMPONENT=by_number[number][1],
            PAIRWISE_SCORE=by_number[number][2],
            POSITION=positions[number - NUMBER_DOMAIN[0]],
        )
        for number in final_order
    )
    ticket = cast(Ticket, tuple(sorted(final_order[:PICK_COUNT])))
    if len(ticket) != PICK_COUNT or len(set(ticket)) != PICK_COUNT:
        raise RuntimeError("pairwise native ticket must contain six unique numbers")
    if not all(number in LEGAL_NUMBERS for number in ticket):
        raise RuntimeError("pairwise native ticket must contain legal numbers")
    return PairwiseRanking(
        POOL_NUMBERS=tuple(final_order),
        TRANSITION_MARKOV_COMPONENTS=tuple(by_number[number][0] for number in final_order),
        GRAPH_COMPONENTS=tuple(by_number[number][1] for number in final_order),
        PAIRWISE_SCORES=tuple(by_number[number][2] for number in final_order),
        RANKED_NUMBERS=tuple(final_order),
        POSITIONS=tuple(positions),
        SCORES=records,
        NATIVE_TICKET=ticket,
        FUSED_RANKED_NUMBERS=fused_order,
        ALL_TRANSITION_MARKOV_COMPONENTS=all_transition_markov_components,
        ALL_GRAPH_COMPONENTS=all_graph_components,
        ALL_PAIRWISE_SCORES=all_pairwise_scores,
        MARKOV_PARENT_RANKING=markov_parent_ranking,
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        EDGE_SCORES=edge_scores,
    )


fuse_pairwise_scores = rank_pairwise_scores


def _traverse_graph(
    edge_scores: EdgeScoreMatrix,
    fused_scores: ScoreVector,
) -> tuple[int, ...]:
    matrix = _validate_edge_score_matrix(edge_scores)
    if len(fused_scores) != GRAPH_NODE_COUNT:
        raise ValueError("fused_scores must contain exactly 49 values")
    visited: list[int] = []
    visited_set: set[int] = set()
    frontier: list[int] = []

    def next_seed() -> int:
        return min(
            (number for number in LEGAL_NUMBERS if number not in visited_set),
            key=lambda number: (-fused_scores[number - 1], number),
        )

    while len(visited) < RANKED_POOL_CARDINALITY:
        if frontier:
            current = frontier.pop(0)
            if current in visited_set:
                continue
        else:
            current = next_seed()
        visited.append(current)
        visited_set.add(current)
        neighbors = sorted(
            (
                number
                for number in LEGAL_NUMBERS
                if number not in visited_set
                and number not in frontier
                and matrix[current - 1][number - 1] > 0
            ),
            key=lambda number: (
                -matrix[current - 1][number - 1],
                -fused_scores[number - 1],
                number,
            ),
        )
        frontier.extend(neighbors)
    return tuple(visited)


traverse_graph = _traverse_graph


def produce_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return the exact ten-number graph traversal pool."""

    ranking = calculate_pairwise_ranking(history, target_index)
    return ranking.GRAPH_TRAVERSAL_POOL


produce_graph_pool = produce_graph_traversal_pool
build_graph_traversal_pool = produce_graph_traversal_pool
build_graph_pool = produce_graph_traversal_pool


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal traversal ranking from both frozen parents."""

    prior_history = validate_prior_history(history, target_index)
    markov_parent = _fuse_markov_window_rankings(
        tuple(_markov_window_from_prior_history(prior_history, window) for window in WINDOWS)
    )
    graph_parent = _fuse_graph_window_rankings(
        tuple(_graph_window_from_prior_history(prior_history, window) for window in WINDOWS)
    )
    markov_components = markov_parent.NORMALIZED_RANKS
    graph_components = graph_parent.NORMALIZED_RANKS
    all_pairwise_scores = tuple(
        FUSION_WEIGHT_1 * markov_components[number - 1]
        + FUSION_WEIGHT_2 * graph_components[number - 1]
        for number in LEGAL_NUMBERS
    )
    fused_order = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (
                -all_pairwise_scores[number - 1],
                -markov_components[number - 1],
                -graph_components[number - 1],
                number,
            ),
        )
    )
    edge_scores = _aggregate_edge_scores_from_prior_history(prior_history)
    traversal_pool = _traverse_graph(edge_scores, all_pairwise_scores)
    return rank_pairwise_scores(
        markov_components,
        graph_components,
        pool_numbers=traversal_pool,
        traversal_order=traversal_pool,
        fused_ranked_numbers=fused_order,
        edge_scores=edge_scores,
        markov_parent_ranking=markov_parent,
        graph_parent_ranking=graph_parent,
        all_transition_markov_components=markov_components,
        all_graph_components=graph_components,
        all_pairwise_scores=all_pairwise_scores,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking
calculate_fused_pairwise_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first-six ticket from the traversal pool."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate = (
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
    "GRAPH_EDGE_DEFINITION",
    "GRAPH_EDGE_WEIGHT_RULE",
    "GRAPH_NODE_COUNT",
    "GRAPH_NODE_DOMAIN",
    "GRAPH_WINDOWS",
    "HISTORY_ORDER",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "KNOWN_SEMANTIC_NEIGHBORS",
    "LEGAL_NUMBERS",
    "LEGAL_NUMBERS",
    "LOTTERY_TYPE",
    "METHOD_LEVEL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_DOMAIN_TEXT",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "OUTPUT_SHAPE",
    "PAGERANK_ARITHMETIC",
    "PAGERANK_DAMPING",
    "PAGERANK_DANGLING_RULE",
    "PAGERANK_INITIALIZATION",
    "PAGERANK_ITERATIONS",
    "PAGERANK_POWER_ITERATIONS",
    "PAGERANK_TELEPORT",
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
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "TRANSITION_WINDOWS",
    "WINDOW",
    "WINDOWS",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "EdgeScoreMatrix",
    "FusedNumberRanking",
    "FusedParentRanking",
    "GraphWindow",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "MarkovWindow",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "ProbabilityMatrix",
    "Ticket",
    "TicketPortfolio",
    "TransitionMatrix",
    "TransitionWindow",
    "WindowRanking",
    "build_aggregate_edge_matrix",
    "build_aggregate_graph_edge_scores",
    "build_cooccurrence_edge_counts",
    "build_graph_edge_counts",
    "build_graph_for_window",
    "build_graph_pool",
    "build_graph_traversal_pool",
    "build_source_ticket_universe",
    "build_transition_counts",
    "build_transition_matrix",
    "build_transition_window",
    "calculate_aggregate_edge_scores",
    "calculate_conditional_transition_probabilities",
    "calculate_exact_conditional_probabilities",
    "calculate_exact_pagerank",
    "calculate_fused_graph_number_ranking",
    "calculate_fused_graph_parent_ranking",
    "calculate_fused_markov_number_ranking",
    "calculate_fused_markov_parent_ranking",
    "calculate_fused_number_ranking",
    "calculate_fused_pairwise_ranking",
    "calculate_graph_components",
    "calculate_graph_fused_ranking",
    "calculate_graph_parent_ranking",
    "calculate_graph_raw_scores",
    "calculate_graph_scores",
    "calculate_graph_window",
    "calculate_graph_window_rankings",
    "calculate_markov_fused_ranking",
    "calculate_markov_parent_ranking",
    "calculate_markov_raw_scores",
    "calculate_markov_scores",
    "calculate_markov_window",
    "calculate_markov_window_rankings",
    "calculate_markov_window_scores",
    "calculate_outgoing_counts",
    "calculate_page_rank",
    "calculate_pairwise_ranking",
    "calculate_transition_counts",
    "calculate_transition_markov_components",
    "calculate_transition_markov_raw_scores",
    "calculate_transition_probabilities",
    "calculate_transition_rankings",
    "calculate_transition_scores",
    "calculate_transition_window",
    "calculate_window_graph_rankings",
    "calculate_window_rankings",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "exact_pagerank",
    "fuse_graph_window_rankings",
    "fuse_markov_window_rankings",
    "fuse_pairwise_scores",
    "fuse_transition_markov_rankings",
    "graph_components",
    "markov_components",
    "produce_biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_pool",
    "produce_graph_traversal_pool",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_graph_parent_scores",
    "rank_graph_scores",
    "rank_markov_scores",
    "rank_pairwise_scores",
    "rank_transition_markov_scores",
    "signature_hash_for_semantics",
    "traverse_graph",
    "validate_prior_history",
]
