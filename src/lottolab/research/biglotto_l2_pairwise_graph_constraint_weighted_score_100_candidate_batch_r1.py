"""Causal deterministic BigLotto GRAPH + CONSTRAINT candidate.

The candidate reuses the sealed multiscale graph/PageRank parent to establish
a ten-number traversal pool, then reuses the sealed structural-constraint
predicate and support parent over that pool.  Both components are normalized
by exact rank, fused with fixed one-half weights, and searched in final-rank
lexicographic order for one admissible ticket.

This is research-only code.  It has no outcome access, I/O, randomness, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1,
)

_constraint_parent = (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type ComponentValue = int | Fraction

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_7434ffb53674510d"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "5632f1560a51433024e7d335eb3bb6a27c7137a1e50f288913b674e0fcd12b8b"
)

FEATURE_1: Final[str] = "GRAPH"
FEATURE_2: Final[str] = "CONSTRAINT"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 100
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_DOMAIN: Final[str] = (
    "TOP_10_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
RANKED_POOL_CARDINALITY: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1"
)
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/biglotto_graph_network_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1.py"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "GRAPH_PARENT= B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;FOR EACH W IN "
    "(50,300,750), BUILD UNDIRECTED SAME_DRAW_COOCCURRENCE "
    "EDGE_W(a,b)=COUNT_OF_PRIOR_DRAWS_CONTAINING_BOTH_NUMBERS;EXACT_INTEGER_"
    "EDGE_COUNTS;PAGERANK_DAMPING=17/20;PAGERANK_ITERATIONS=20;INITIAL_VECTOR="
    "UNIFORM_1_OVER_49;DANGLING_NODES=UNIFORM_REDISTRIBUTION;EXACT_RATIONAL;"
    "PER_WINDOW_RANK=PAGERANK_DESCENDING_THEN_NUMBER_ASCENDING;WINDOW_"
    "NORMALIZED_RANK=(49-POSITION)/48;FUSED_GRAPH_RANK=MEAN_OF_NORMALIZED_"
    "RANKS_OVER_50_300_750;ROBUSTNESS_TIE=SORTED_ASCENDING(MINIMUM,MEDIAN,"
    "MAXIMUM);GRAPH_POOL=FIRST_10_FUSED_GRAPH_RANKED_NUMBERS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "CONSTRAINT_PARENT=B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1;"
    "CONSTRAINT_PREDICATE(ticket)=ODD_COUNT_2_TO_4;ZONES_COVERED_AT_LEAST_3_"
    "FOR_ZONES=(1..10),(11..20),(21..30),(31..40),(41..49);SUM_120_TO_180;"
    "MAX_CONSECUTIVE_RUN_AT_MOST_2;DISTINCT_LAST_DIGITS_AT_LEAST_4;"
    "CONSTRAINT_SUPPORT_30(n)=SUM_{t=T-30}^{T-1}(1_IF_n_IN_history[t] AND "
    "CONSTRAINT_PREDICATE(history[t]));EXACT_INTEGER;HIGHER_IS_BETTER;RAW_"
    "TIES_NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_DRAWS=history[T-750:T];"
    "GRAPH_WINDOWS=(50,300,750);TARGET_ROW_history[T] EXCLUDED;ALL_GRAPH_"
    "WINDOWS_END_AT_T"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CONSTRAINT_SUPPORT_DRAWS="
    "history[T-30:T];W=30;TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build the exact multiscale graph/PageRank ranking for all 49 legal numbers "
    "using the fixed graph parent constants and retain the first 10 graph-ranked "
    "numbers as the frozen traversal pool.",
    "Compute the exact structural-constraint support count over history[T-30:T] "
    "for each number in the frozen 10-number graph pool.",
    "Use graph-parent order as the GRAPH component order and rank constraint "
    "support counts higher-is-better with number-ascending raw ties; rank both "
    "components within the same 10-number pool.",
    "Normalize one-based position p as (10-p)/9; best rank is 1 and worst rank "
    "is 0; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, outcome-derived "
    "normalization, historical optimization, or randomness.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_GRAPH_FUSED_TRAVERSAL_RANK_FOR_THE_FIRST_10_OF_49_LEGAL_NUMBERS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_CONSTRAINT_VALID_DRAW_SUPPORT_COUNT_OVER_HISTORY_T_MINUS_30_TO_T_MINUS_1_"
    "FOR_EACH_OF_THE_10_GRAPH_POOL_NUMBERS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*GRAPH_NORMALIZED_TRAVERSAL_RANK_10(n)+1/2*"
    "CONSTRAINT_NORMALIZED_RANK_10(n);EXACT_RATIONAL"
)

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "GRAPH parent normalized traversal rank descending.",
    "CONSTRAINT normalized support rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "GRAPH parent PageRank tie: per-window PageRank descending, robustness tuple "
    "sorted ascending, then number ascending.",
    "CONSTRAINT parent support-count tie: number ascending.",
    "Final pairwise tie: minimum component rank descending, GRAPH rank descending, "
    "CONSTRAINT rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_MULTISCALE_GRAPH_PARENT_OVER_ALL_49_LEGAL_NUMBERS;RETAIN_"
    "FIRST_10_GRAPH_RANKED_NUMBERS_AS_TRAVERSAL_POOL;COMPUTE_CONSTRAINT_"
    "SUPPORT_30_FOR_THOSE_10_NUMBERS;RANK_THE_10_NUMBERS_BY_EQUAL_WEIGHT_"
    "PAIRWISE_SCORE;ENUMERATE_6_NUMBER_COMBINATIONS_IN_LEXICOGRAPHIC_INDEX_"
    "ORDER_OVER_FINAL_RANKING;SELECT_FIRST_TICKET_SATISFYING_FIXED_"
    "CONSTRAINT_PREDICATE;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_LEXICOGRAPHIC_ADMISSIBLE_6_COMBINATION_IN_FINAL_PAIRWISE_GRAPH_POOL_"
    "RANK_ORDER;SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;FUTURE_"
    "SUFFIX NEVER_USED;GRAPH_PARENT_WINDOWS=(50,300,750);CONSTRAINT_SUPPORT_"
    "DRAWS=history[T-30:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;NO_VALID_CONSTRAINT_TICKET=>RAISE_"
    "EXPLICIT_CONSTRAINT_SEARCH_EXHAUSTED"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;GRAPH_PARENT_WINDOWS=50,300,750;GRAPH_DAMPING=17/20;"
    "GRAPH_PAGERANK_ITERATIONS=20;GRAPH_POOL_CARDINALITY=10;CONSTRAINT_SUPPORT_"
    "WINDOW=30;ODD_COUNT=2..4;ZONES_COVERED_AT_LEAST_3;SUM=120..180;MAX_"
    "CONSECUTIVE_RUN=2;DISTINCT_TAIL_DIGITS_AT_LEAST_4;FRONTIER_WINDOW_LABEL="
    "100;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_NETWORK_CENTRALITY_STRUCTURE_PLUS_STRUCTURAL_CONSTRAINT_COMPATIBILITY"
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_5f0c6fb3405f7f78[B649_PAIRWISE_REGIME_STATE_"
    "CONSTRAINT_WEIGHTED_SCORE_30_V1;SHARED_CONSTRAINT_PARENT_ONLY;WINDOW=30;"
    "NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_798bb953e431872b[B649_PAIRWISE_SPECTRAL_ML_WEIGHTED_"
    "SCORE_300_V1;NO_SHARED_FEATURE;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_"
    "CLUSTERING_WEIGHTED_SCORE_100_V1;NO_SHARED_FEATURE;NOT_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_"
    "PAIRWISE_EQUIVALENT]",
    "B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1[CONSTRAINT_PARENT_"
    "ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "legacy_biglotto__constraint_filter_predictor__3a85b3995002[SEEDED_TWO_"
    "TICKET;NOT_EQUIVALENT]",
    "PR #164[OPERATIONAL_TOOLS_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
    "PR #183[ODD_EVEN_SINGLETON_ONLY;NO_FRONTIER_FEATURE_MATCH]",
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change the graph parent windows (50,300,750), same-draw edge "
    "definition, PageRank damping 17/20, 20 iterations, uniform initialization, "
    "uniform dangling rule, exact rational arithmetic, or graph top-10 pool.",
    "Do not change the structural constraint predicate, the W=30 support window, "
    "higher-is-better support ranking, or number-ascending raw ties.",
    "Do not change the 10-number normalization (10-p)/9, equal 1/2 and 1/2 "
    "fusion, final tie-break order, lexicographic first-admissible search, "
    "single-ticket rule, minimum history, or fallback.",
    "Do not introduce empirical min-max scaling, z-scoring, calibration, outcome "
    "tuning, historical optimization, or randomness.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation "
    "task.",
)
IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1"
)

_LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(
    range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
)

InsufficientHistoryError = _constraint_parent.InsufficientHistoryError


class ConstraintSearchExhaustedError(ValueError):
    """Raised when no ranked six-number combination satisfies the predicate."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """One exact component ranking over the frozen ten-number pool."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: tuple[ComponentValue, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]

    def _index(self, number: int) -> int:
        _validate_number(number)
        try:
            return self.POOL_NUMBERS.index(number)
        except ValueError as error:
            raise ValueError("number is not in the frozen graph pool") from error

    def raw_score(self, number: int) -> ComponentValue:
        return self.RAW_SCORES[self._index(number)]

    def score(self, number: int) -> ComponentValue:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - NUMBER_DOMAIN[0]]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[self._index(number)]

    @property
    def SCORES(self) -> tuple[ComponentValue, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score for one number in the graph pool."""

    NUMBER: int
    GRAPH_COMPONENT: Fraction
    CONSTRAINT_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def GRAPH_RANK_10(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def CONSTRAINT_RANK_10(self) -> Fraction:
        return self.CONSTRAINT_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """The ten-number fused ranking and exactly one admissible ticket."""

    GRAPH_PARENT_RANKING: object | None
    GRAPH_POOL: tuple[int, ...]
    GRAPH_RANKING: ComponentRanking
    CONSTRAINT_RANKING: ComponentRanking
    GRAPH_COMPONENTS: tuple[Fraction, ...]
    CONSTRAINT_COMPONENTS: tuple[Fraction, ...]
    PAIRWISE_SCORES: tuple[Fraction, ...]
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    SOURCE_TICKETS: TicketPortfolio
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

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - NUMBER_DOMAIN[0]]

    def score(self, number: int) -> PairwiseNumberScore:
        position = self.position(number)
        if position == 0:
            raise ValueError("number is not in the frozen graph pool")
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


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return the validated strictly prior prefix required by the design."""

    _validate_target_index(target_index)
    return _constraint_parent.validate_prior_history(history, target_index)


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> _graph_parent.FusedNumberRanking:
    """Reuse the exact graph parent from the immutable prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _graph_parent.calculate_fused_number_ranking(prior_history, len(prior_history))


calculate_fused_graph_parent_ranking = calculate_graph_parent_ranking
calculate_graph_fused_ranking = calculate_graph_parent_ranking


def calculate_graph_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_graph_parent.GraphWindow, ...]:
    """Return the exact 50/300/750 graph parent windows."""

    prior_history = validate_prior_history(history, target_index)
    return _graph_parent.calculate_window_rankings(prior_history, len(prior_history))


def produce_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return the first ten numbers in the exact fused graph-parent order."""

    pool = calculate_graph_parent_ranking(history, target_index).TOP_NUMBERS
    return _validate_pool(pool)


produce_graph_pool = produce_graph_traversal_pool
build_graph_traversal_pool = produce_graph_traversal_pool
build_graph_pool = produce_graph_traversal_pool


def _source_tickets_from_pool(pool_numbers: Sequence[int]) -> TicketPortfolio:
    pool = _validate_pool(pool_numbers)
    tickets = tuple(
        cast(Ticket, tuple(sorted(pool[position] for position in positions)))
        for positions in combinations(range(RANKED_POOL_CARDINALITY), PICK_COUNT)
    )
    if len(tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("graph source universe did not produce exactly 210 tickets")
    if len(set(tickets)) != len(tickets):
        raise RuntimeError("graph source universe produced duplicate tickets")
    return tickets


def produce_graph_source_ticket_universe(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return the graph parent 210-ticket universe for the frozen top ten."""

    return _source_tickets_from_pool(produce_graph_traversal_pool(history, target_index))


produce_source_ticket_universe = produce_graph_source_ticket_universe
build_source_ticket_universe = produce_graph_source_ticket_universe
build_graph_source_ticket_universe = produce_graph_source_ticket_universe


def calculate_constraint_support_scores(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Reuse the exact structural-constraint support parent over legal numbers."""

    prior_history = validate_prior_history(history, target_index)
    return _constraint_parent.calculate_constraint_support_scores(
        prior_history, len(prior_history)
    )


constraint_predicate = _constraint_parent.constraint_predicate


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError(f"graph pool must contain exactly {RANKED_POOL_CARDINALITY} numbers")
    if len(set(pool)) != len(pool) or any(
        type(number) is not int or number not in _LEGAL_NUMBERS for number in pool
    ):
        raise ValueError("graph pool must be ten unique legal numbers")
    return pool


def _component_values(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
) -> tuple[ComponentValue, ...]:
    if isinstance(raw_scores, Mapping):
        keys = tuple(raw_scores)
        if len(keys) != len(pool) or set(keys) != set(pool):
            raise ValueError(f"{name} mapping must contain exactly the graph-pool numbers")
        values = tuple(raw_scores[number] for number in pool)
    else:
        values = tuple(raw_scores)
        if len(values) != len(pool):
            raise ValueError(f"{name} must contain exactly {len(pool)} values")

    converted: list[ComponentValue] = []
    for index, value in enumerate(values, start=1):
        if (type(value) is int and value >= 0) or (isinstance(value, Fraction) and value >= 0):
            converted.append(value)
        else:
            raise TypeError(f"{name}[{index}] must be a non-negative integer or Fraction")
    return tuple(converted)


def _normalized_values(
    components: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
) -> tuple[Fraction, ...]:
    if isinstance(components, Mapping):
        keys = tuple(components)
        if len(keys) != len(pool) or set(keys) != set(pool):
            raise ValueError(f"{name} mapping must contain exactly the graph-pool numbers")
        values = tuple(components[number] for number in pool)
    else:
        values = tuple(components)
        if len(values) != len(pool):
            raise ValueError(f"{name} must contain exactly {len(pool)} values")

    normalized: list[Fraction] = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, Fraction):
            fraction = value
        elif type(value) is int:
            fraction = Fraction(value, 1)
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
        if not 0 <= fraction <= 1:
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        normalized.append(fraction)
    return tuple(normalized)


def _positions_for_pool(
    pool: tuple[int, ...], ordered: tuple[int, ...]
) -> tuple[int, ...]:
    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for position, number in enumerate(ordered, start=1):
        positions[number - NUMBER_DOMAIN[0]] = position
    if {
        number
        for number, position in zip(_LEGAL_NUMBERS, positions, strict=True)
        if position
    } != set(pool):
        raise RuntimeError("component positions escaped the graph pool")
    return tuple(positions)


def _component_ranking_from_order(
    pool: tuple[int, ...],
    raw_scores: tuple[ComponentValue, ...],
    ordered: tuple[int, ...],
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
    )


def rank_component_scores(
    pool_or_scores: Sequence[object] | Mapping[int, object],
    raw_scores: Sequence[object] | Mapping[int, object] | None = None,
    name: str = "component_scores",
) -> ComponentRanking:
    """Rank exact raw component scores, using number-ascending raw ties."""

    if raw_scores is None:
        if isinstance(pool_or_scores, Mapping):
            keys = tuple(pool_or_scores)
            if set(keys) == set(_LEGAL_NUMBERS):
                pool = _validate_pool(tuple(keys)[-RANKED_POOL_CARDINALITY:])
                raw = tuple(pool_or_scores[number] for number in pool)
            else:
                pool = _validate_pool(tuple(keys))
                raw = pool_or_scores
        else:
            values = tuple(pool_or_scores)
            if len(values) == len(_LEGAL_NUMBERS):
                pool = _validate_pool(_LEGAL_NUMBERS[-RANKED_POOL_CARDINALITY:])
                raw = tuple(values[number - NUMBER_DOMAIN[0]] for number in pool)
            elif len(values) == RANKED_POOL_CARDINALITY:
                pool = _validate_pool(tuple(range(1, RANKED_POOL_CARDINALITY + 1)))
                raw = values
            else:
                raise ValueError("component scores must contain 10 or 49 values")
    else:
        pool = _validate_pool(cast(Sequence[int], pool_or_scores))
        raw = raw_scores

    values = _component_values(raw, pool, name)
    ordered = tuple(sorted(pool, key=lambda number: (-values[pool.index(number)], number)))
    return _component_ranking_from_order(pool, values, ordered)


def rank_pool_component_scores(
    pool_numbers: Sequence[int],
    raw_scores: Sequence[object] | Mapping[int, object],
    name: str = "component_scores",
) -> ComponentRanking:
    """Rank one component explicitly over the frozen graph pool."""

    return rank_component_scores(pool_numbers, raw_scores, name)


def rank_constraint_support_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int] | None = None,
) -> ComponentRanking:
    """Rank structural-constraint support higher-is-better over the pool."""

    if pool_numbers is None:
        return rank_component_scores(raw_scores, name="constraint_support_scores")
    return rank_pool_component_scores(
        pool_numbers, raw_scores, name="constraint_support_scores"
    )


def _graph_component_ranking(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
    pool: tuple[int, ...],
) -> ComponentRanking:
    raw_scores = tuple(graph_parent_ranking.mean_rank(number) for number in pool)
    return _component_ranking_from_order(pool, raw_scores, pool)


def select_first_admissible_ticket(
    ranked_numbers: Sequence[int],
    predicate: Callable[[Sequence[int]], bool] = constraint_predicate,
) -> Ticket:
    """Search six-number combinations in final graph-pool rank order."""

    ranking = _validate_pool(ranked_numbers)
    for candidate in combinations(ranking, PICK_COUNT):
        if predicate(candidate):
            return cast(Ticket, tuple(sorted(candidate)))
    raise ConstraintSearchExhaustedError(
        "no six-number combination in the final graph pool satisfies the frozen constraint"
    )


def _ranking_from_normalized_components(
    pool: tuple[int, ...], components: tuple[Fraction, ...]
) -> ComponentRanking:
    ordered = tuple(
        sorted(pool, key=lambda number: (-components[pool.index(number)], number))
    )
    return _component_ranking_from_order(pool, components, ordered)


def rank_pairwise_scores(
    graph_components: Sequence[object] | Mapping[int, object],
    constraint_components: Sequence[object] | Mapping[int, object],
    *,
    pool_numbers: Sequence[int] | None = None,
    source_tickets: TicketPortfolio = (),
    graph_ranking: ComponentRanking | None = None,
    constraint_ranking: ComponentRanking | None = None,
    graph_parent_ranking: object | None = None,
    predicate: Callable[[Sequence[int]], bool] = constraint_predicate,
) -> PairwiseRanking:
    """Fuse two exact normalized components with fixed one-half weights."""

    if pool_numbers is None:
        if isinstance(graph_components, Mapping):
            pool = _validate_pool(tuple(graph_components))
        elif len(tuple(graph_components)) == RANKED_POOL_CARDINALITY:
            pool = _validate_pool(tuple(range(1, RANKED_POOL_CARDINALITY + 1)))
        else:
            raise ValueError("pool_numbers is required for non-ten component sequences")
    else:
        pool = _validate_pool(pool_numbers)

    graph = _normalized_values(graph_components, pool, "graph_components")
    constraint = _normalized_values(
        constraint_components, pool, "constraint_components"
    )
    pairwise = tuple(
        FUSION_WEIGHT_1 * graph[index] + FUSION_WEIGHT_2 * constraint[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked = tuple(
        sorted(
            pool,
            key=lambda number: (
                -pairwise[pool.index(number)],
                -min(graph[pool.index(number)], constraint[pool.index(number)]),
                -graph[pool.index(number)],
                -constraint[pool.index(number)],
                number,
            ),
        )
    )
    positions = _positions_for_pool(pool, ranked)
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            GRAPH_COMPONENT=graph[pool.index(number)],
            CONSTRAINT_COMPONENT=constraint[pool.index(number)],
            PAIRWISE_SCORE=pairwise[pool.index(number)],
            MIN_COMPONENT_RANK=min(graph[pool.index(number)], constraint[pool.index(number)]),
            POSITION=positions[number - NUMBER_DOMAIN[0]],
        )
        for number in ranked
    )
    ticket = select_first_admissible_ticket(ranked, predicate)
    return PairwiseRanking(
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        GRAPH_POOL=pool,
        GRAPH_RANKING=graph_ranking or _ranking_from_normalized_components(pool, graph),
        CONSTRAINT_RANKING=constraint_ranking
        or _ranking_from_normalized_components(pool, constraint),
        GRAPH_COMPONENTS=graph,
        CONSTRAINT_COMPONENTS=constraint,
        PAIRWISE_SCORES=pairwise,
        RANKED_NUMBERS=ranked,
        POSITIONS=positions,
        SCORES=records,
        SOURCE_TICKETS=tuple(source_tickets),
        NATIVE_TICKET=ticket,
    )


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ten-number ranking from both parents."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent.calculate_fused_number_ranking(
        prior_history, len(prior_history)
    )
    pool = _validate_pool(graph_parent_ranking.TOP_NUMBERS)
    graph_ranking = _graph_component_ranking(graph_parent_ranking, pool)
    constraint_raw_all = _constraint_parent.calculate_constraint_support_scores(
        prior_history, len(prior_history)
    )
    constraint_raw_pool = tuple(constraint_raw_all[number - NUMBER_DOMAIN[0]] for number in pool)
    constraint_ranking = rank_pool_component_scores(
        pool, constraint_raw_pool, name="constraint_support_scores"
    )
    return rank_pairwise_scores(
        graph_ranking.NORMALIZED_RANKS,
        constraint_ranking.NORMALIZED_RANKS,
        pool_numbers=pool,
        source_tickets=_source_tickets_from_pool(pool),
        graph_ranking=graph_ranking,
        constraint_ranking=constraint_ranking,
        graph_parent_ranking=graph_parent_ranking,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking
calculate_fused_pairwise_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first admissible ticket from the fused pool."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate = (
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
    "HISTORY_ORDER",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "KNOWN_SEMANTIC_NEIGHBORS",
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
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "ConstraintSearchExhaustedError",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "Ticket",
    "TicketPortfolio",
    "build_graph_pool",
    "build_graph_source_ticket_universe",
    "build_graph_traversal_pool",
    "build_source_ticket_universe",
    "calculate_constraint_support_scores",
    "calculate_fused_graph_parent_ranking",
    "calculate_fused_number_ranking",
    "calculate_fused_pairwise_ranking",
    "calculate_graph_fused_ranking",
    "calculate_graph_parent_ranking",
    "calculate_graph_window_rankings",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "constraint_predicate",
    "derive_candidate_identity",
    "produce_biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_pool",
    "produce_graph_source_ticket_universe",
    "produce_graph_traversal_pool",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_component_scores",
    "rank_constraint_support_scores",
    "rank_pairwise_scores",
    "rank_pool_component_scores",
    "select_first_admissible_ticket",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
