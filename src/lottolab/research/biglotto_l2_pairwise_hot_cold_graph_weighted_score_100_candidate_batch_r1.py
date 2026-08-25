"""Causal deterministic BigLotto HOT_COLD + GRAPH pairwise candidate.

This research-only module implements the single candidate sealed by
``B649_PAIRWISE_HOT_COLD_GRAPH_WEIGHTED_SCORE_100_V1``.  The exact graph
parent creates the ten-number traversal pool.  The exact HOT_COLD parent is
then ranked inside that same pool, the two pool-local ranks are fused with
equal rational weights, and the first six final ranks form one native ticket.

Only the strictly prior history prefix is consumed.  The module has no I/O,
database, catalog registration, randomness, outcome access, or fitted
parameters.
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

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_parent,
)
from lottolab.strategies.adapters import biglotto_wave1 as _hot_parent

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_1b75b7279a69956c"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_HOT_COLD_GRAPH_WEIGHTED_SCORE_100_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "8ac3fd953e44cb6794ebfbf9871ae7d32b4efc548e80e8d34076f9e01165d63f"
)

FEATURE_1: Final[str] = "HOT_COLD"
FEATURE_2: Final[str] = "GRAPH"
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
HOT_COLD_FREQUENCY_WINDOW: Final[int] = 50
HOT_COLD_COOCCURRENCE_WINDOW: Final[int] = 100
MINIMUM_HISTORY: Final[int] = 750
HOT_COLD_POOL_CARDINALITY: Final[int] = 20
RANKED_POOL_CARDINALITY: Final[int] = 10
RANKED_POOL_DOMAIN: Final[str] = (
    "TOP_10_MULTISCALE_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
)
PARENT_SOURCE_PATH_1: Final[str] = "src/lottolab/strategies/adapters/biglotto_wave1.py"
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/biglotto_graph_network_multi_ticket_candidate_batch_r1.py"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "HOT_COLD_PARENT=legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;HOT_FREQUENCY_WINDOW=50;"
    "HOT_FREQUENCY_ORDER=POSITIVE_COUNT_DESC_FIRST_OBSERVATION_INDEX_ASC;"
    "HOT_POOL=FIRST_MIN(20,POSITIVE_COUNT_NUMBERS);COOCCURRENCE_WINDOW=100;"
    "PAIR_COUNT_100(n,m)=NUMBER_OF_PRIOR_DRAWS_CONTAINING_BOTH;"
    "CO_100(n,m)=PAIR_COUNT_100(n,m)/100;"
    "HOT_COLD_RAW(n)=7/10*((H-i)/H)+3/10*MEAN(CO_100(n,m) for m in HOT_POOL,m!=n) "
    "for n at HOT_POOL index i;H<=1 uses cooccurrence mean 0;"
    "NON_HOT_POOL_NUMBERS_RAW_SCORE=0;EXACT_RATIONAL;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "GRAPH_PARENT=B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(50,300,750):"
    "UNDIRECTED_EDGE_W(a,b)=COUNT_PRIOR_WINDOW_DRAWS_CONTAINING_BOTH_NUMBERS_FOR_a_LESS_THAN_b;"
    "UNDECAYED_INTEGER_SAME_DRAW_COOCCURRENCE;"
    "PAGERANK_DAMPING=17/20;PAGERANK_ITERATIONS=20;INITIAL_VECTOR=UNIFORM_1_OVER_49;"
    "DANGLING_NODES=UNIFORM_REDISTRIBUTION;EXACT_RATIONAL;"
    "PER_WINDOW_ORDER=PAGERANK_DESC_NUMBER_ASC;"
    "NORMALIZED_W=(49-POSITION)/48;"
    "FUSED_GRAPH_RANK=MEAN_OF_NORMALIZED_50_300_750;"
    "FUSED_TIE=MINIMUM_MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;"
    "GRAPH_POOL=FIRST_10_FUSED_GRAPH_RANKED_NUMBERS;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];HOT_FREQUENCY_DRAWS=history[T-50:T];"
    "HOT_COLD_COOCCURRENCE_DRAWS=history[T-100:T];ALL_HOT_COLD_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_DRAWS_50=history[T-50:T];"
    "GRAPH_DRAWS_300=history[T-300:T];GRAPH_DRAWS_750=history[T-750:T];"
    "ALL_GRAPH_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)

HOT_COLD_RANK_WEIGHT: Final[Fraction] = Fraction(7, 10)
HOT_COLD_COOCCURRENCE_WEIGHT: Final[Fraction] = Fraction(3, 10)
HOT_COLD_RANK_WEIGHT_TEXT: Final[str] = "7/10"
HOT_COLD_COOCCURRENCE_WEIGHT_TEXT: Final[str] = "3/10"
HOT_COLD_SCORE_RULE: Final[str] = (
    "FREQUENCY_ORDER=positive_COUNT_50_DESCENDING_THEN_FIRST_OBSERVATION_INDEX_ASC;"
    "HOT_POOL=first_MIN(20,positive_count_numbers);"
    "PAIR_COUNT_100(n,m)=number_of_prior_draws_containing_both;"
    "CO_100(n,m)=PAIR_COUNT_100(n,m)/100;"
    "for n at hot_pool index i, HOT_COLD_RAW(n)=7/10*((H-i)/H)+"
    "3/10*mean(CO_100(n,m) for m in hot_pool,m!=n);"
    "H<=1 uses cooccurrence mean 0;non_hot_pool numbers raw score 0;EXACT_RATIONAL"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact multiscale GRAPH PageRank ranking for all 49 legal numbers "
        "using the frozen graph parent and retain the first 10 graph-ranked numbers "
        "as the traversal pool."
    ),
    (
        "Compute the exact HOT_COLD parent raw score for all 49 legal numbers using "
        "the fixed 50-draw frequency and 100-draw cooccurrence rules, then restrict "
        "that parent order to the same ten-number graph traversal pool."
    ),
    (
        "Use restricted HOT_COLD parent order as the HOT_COLD component order and "
        "graph-parent order as the GRAPH component order; rank both components "
        "within the same ten-number pool; raw HOT_COLD ties use number ascending."
    ),
    (
        "Normalize each one-based position p within the ten-number pool as (10-p)/9; "
        "best rank is 1 and worst rank is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, outcome-derived "
        "normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_HOT_COLD_SCORE_FOR_ALL_49_LEGAL_NUMBERS_RESTRICTED_TO_THE_10_NUMBER_GRAPH_TRAVERSAL_POOL"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_MULTISCALE_GRAPH_PAGERANK_FUSED_TRAVERSAL_RANK_FOR_THE_FIRST_10_OF_49_LEGAL_NUMBERS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*HOT_COLD_NORMALIZED_RANK_10(n)+"
    "1/2*GRAPH_NORMALIZED_TRAVERSAL_RANK_10(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "HOT_COLD normalized rank descending.",
    "GRAPH normalized traversal rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "HOT_COLD parent raw-score tie: number ascending; HOT_COLD frequency order "
        "itself is positive occurrence count descending then first observation index ascending."
    ),
    (
        "GRAPH parent per-window PageRank tie: PageRank descending then number ascending; "
        "graph fused tie: minimum, median, maximum normalized window rank descending then "
        "number ascending."
    ),
    (
        "Final pairwise tie: minimum component rank descending, HOT_COLD rank descending, "
        "GRAPH rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_MULTISCALE_GRAPH_PARENT_RANKING_OVER_ALL_49_LEGAL_NUMBERS;"
    "RETAIN_FIRST_10_GRAPH_RANKED_NUMBERS_AS_THE_FROZEN_TRAVERSAL_POOL;"
    "COMPUTE_THE_EXACT_HOT_COLD_PARENT_RAW_SCORE_FOR_ALL_49_LEGAL_NUMBERS;"
    "RESTRICT_HOT_COLD_PARENT_ORDER_TO_THE_SAME_10_NUMBER_GRAPH_TRAVERSAL_POOL;"
    "RANK_BOTH_COMPONENTS_WITHIN_THE_SAME_10_NUMBER_POOL;"
    "FUSE_WITH_EQUAL_EXACT_RANK_WEIGHTS;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_TRAVERSAL_POOL_NUMBERS;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;HOT_COLD_FREQUENCY_WINDOW=(50);"
    "HOT_COLD_COOCCURRENCE_WINDOW=(100);GRAPH_PARENT_WINDOWS=(50,300,750);"
    "ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;EXACTLY_10_GRAPH_TRAVERSAL_POOL_NUMBERS_REQUIRED;"
    "NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;HOT_COLD_FREQUENCY_WINDOW=50;"
    "HOT_COLD_COOCCURRENCE_WINDOW=100;HOT_COLD_RANK_WEIGHT=7/10;"
    "HOT_COLD_COOCCURRENCE_WEIGHT=3/10;PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "GRAPH_WINDOWS=(50,300,750);GRAPH_DAMPING=17/20;GRAPH_PAGERANK_ITERATIONS=20;"
    "GRAPH_INITIALIZATION=UNIFORM_1_OVER_49;GRAPH_DANGLING=UNIFORM_REDISTRIBUTION;"
    "GRAPH_POOL_CARDINALITY=10;FRONTIER_WINDOW_LABEL=100;NO_TARGET_ROW_ACCESS;"
    "NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "HOT_COLD_RECENCY_FREQUENCY_AND_LOCAL_COOCCURRENCE_STRUCTURE_PLUS_"
    "MULTISCALE_NETWORK_CENTRALITY_STRUCTURE"
)
EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/test_biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"

FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the HOT_COLD parent frequency window 50, cooccurrence window "
        "100, positive-count top-20 pool, 7/10 rank plus 3/10 cooccurrence weights, "
        "first-observation tie rule, exact rational arithmetic, or all-49 raw-score domain."
    ),
    (
        "Do not change the GRAPH parent windows (50,300,750), same-draw undirected "
        "cooccurrence edges, PageRank damping 17/20, exactly 20 iterations, uniform "
        "1/49 initialization, uniform dangling redistribution, exact rational arithmetic, "
        "per-window ordering, equal three-window rank fusion, robustness tie, or graph-derived "
        "first-10 traversal pool."
    ),
    (
        "Do not change restriction of the HOT_COLD parent order to the graph-derived "
        "ten-number pool, within-pool (10-p)/9 normalization, equal 1/2 and 1/2 fusion, "
        "final tie-break order, first-six single-ticket rule, minimum history, or fallback."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, outcome tuning, "
        "historical optimization, or randomness."
    ),
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_bb262c993f3fefee[B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_HOT_COLD_PARENT_ONLY;COVERED_EXACT;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_5b92df6e42366e6b[B649_PAIRWISE_GAP_OMISSION_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_ONLY;COVERED_EXACT;WINDOW=100;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15[B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe[B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee[LIVE_CATALOG_COMPONENT_ONLY;SINGLETON;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_cf6824201a373019f5b60f1e001a3625f40d3f47[STOCHASTIC_NUMBER_PAIRS_COOCCURRENCE_AFFINITY_SINGLETON;NO_DETERMINISTIC_HOT_COLD_GRAPH_LEVEL2_COVERAGE]",
    (
        "PR #187[OPEN_DRAFT_FRONTEND_MONTE_CARLO;FULL_CALLER_HISTORY;"
        "UNSEEDED_PROCESS_GLOBAL_RNG;NO_DETERMINISTIC_LEVEL2_PAIRWISE_COVERAGE]"
    ),
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw values and pool-local ranks for one parent component."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

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
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    HOT_COLD_COMPONENT: Fraction
    GRAPH_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def HOT_COLD_RANK_10(self) -> Fraction:
        return self.HOT_COLD_COMPONENT

    @property
    def GRAPH_RANK_10(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def HOT_COLD_NORMALIZED_RANK_10(self) -> Fraction:
        return self.HOT_COLD_COMPONENT

    @property
    def GRAPH_NORMALIZED_TRAVERSAL_RANK(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All ten fused ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    HOT_COLD_COMPONENTS: Components
    GRAPH_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    GRAPH_TRAVERSAL_POOL: tuple[int, ...]
    GRAPH_PARENT_RANKING: object | None = None
    HOT_COLD_RANKING: ComponentRanking | None = None
    GRAPH_RANKING: ComponentRanking | None = None

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
        position = self.POSITIONS[number - 1]
        if position == 0:
            raise ValueError("number is not in the ten-number graph traversal pool")
        return position

    def score(self, number: int) -> PairwiseNumberScore:
        position = self.position(number)
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


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    """Read exactly ``history[:target_index]`` without touching its suffix."""

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


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return an immutable copy of only the strictly prior validated history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _frequency_order(recent_history: tuple[HistoryDraw, ...]) -> tuple[int, ...]:
    """Return positive-frequency order with first-observation tie semantics."""

    counts = [0] * 49
    first_observation: list[int | None] = [None] * 49
    observation_index = 0
    for draw in recent_history:
        for number in draw:
            counts[number - 1] += 1
            if first_observation[number - 1] is None:
                first_observation[number - 1] = observation_index
            observation_index += 1
    observed = tuple(
        number for number in LEGAL_NUMBERS if counts[number - 1] > 0
    )
    return tuple(
        sorted(
            observed,
            key=lambda number: (
                -counts[number - 1],
                cast(int, first_observation[number - 1]),
                number,
            ),
        )
    )


def _hot_cold_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    """Calculate the sealed all-49 exact HOT_COLD raw-score vector."""

    frequency_history = prior_history[-HOT_COLD_FREQUENCY_WINDOW:]
    positive_order = _frequency_order(frequency_history)
    hot_pool = positive_order[:HOT_COLD_POOL_CARDINALITY]
    hot_pool_size = len(hot_pool)

    pair_counts = [[0] * 50 for _ in range(50)]
    for draw in prior_history[-HOT_COLD_COOCCURRENCE_WINDOW:]:
        for left, right in combinations(draw, 2):
            pair_counts[left][right] += 1
            pair_counts[right][left] += 1

    raw_scores = [Fraction(0, 1)] * 49
    for index, number in enumerate(hot_pool):
        rank_score = Fraction(hot_pool_size - index, hot_pool_size)
        if hot_pool_size <= 1:
            cooccurrence_mean = Fraction(0, 1)
        else:
            cooccurrence_mean = sum(
                (
                    Fraction(
                        pair_counts[number][other], HOT_COLD_COOCCURRENCE_WINDOW
                    )
                    for other in hot_pool
                    if other != number
                ),
                Fraction(0, 1),
            ) / (hot_pool_size - 1)
        raw_scores[number - 1] = (
            HOT_COLD_RANK_WEIGHT * rank_score
            + HOT_COLD_COOCCURRENCE_WEIGHT * cooccurrence_mean
        )
    return tuple(raw_scores)


def calculate_hot_cold_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return exact HOT_COLD raw scores for all legal numbers 1..49."""

    return _hot_cold_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


def _exact_values(values: Sequence[object] | Mapping[int, object], name: str) -> Components:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != 49 or set(keys) != set(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in LEGAL_NUMBERS)
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


def _rank_full_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> ComponentRanking:
    raw = _exact_values(values, name)
    ordered = tuple(sorted(LEGAL_NUMBERS, key=lambda number: (-raw[number - 1], number)))
    positions = [0] * 49
    normalized = [Fraction(0, 1)] * 49
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
        normalized[number - 1] = Fraction(49 - position, 48)
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized),
    )


def rank_hot_cold_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank a complete exact HOT_COLD raw-score vector over all 49 numbers."""

    return _rank_full_values(raw_scores, "hot_cold_raw_scores")


def calculate_hot_cold_parent_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return rank_hot_cold_scores(calculate_hot_cold_raw_scores(history, target_index))


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain exactly ten numbers")
    if any(type(number) is not int or number not in LEGAL_NUMBERS for number in pool):
        raise ValueError("pool_numbers must contain legal integers in 1..49")
    if len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain ten unique numbers")
    return pool


def _pool_ranking(
    pool_numbers: Sequence[int], raw_scores: Sequence[object], name: str
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    raw_values = tuple(raw_scores)
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
    raw = tuple(converted)
    values_by_number = dict(zip(pool, raw, strict=True))
    ordered = tuple(sorted(pool, key=lambda number: (-values_by_number[number], number)))
    position_by_number = {number: position for position, number in enumerate(ordered, start=1)}
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


def _assert_parent_contracts() -> None:
    graph_checks = (
        _graph_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_2,
        _graph_parent.WINDOWS == WINDOWS,
        _graph_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _graph_parent.GRAPH_NODE_COUNT == 49,
        Fraction(17, 20) == _graph_parent.PAGERANK_DAMPING,
        _graph_parent.PAGERANK_ITERATIONS == 20,
        _graph_parent.PAGERANK_INITIALIZATION == "UNIFORM_1_OVER_49",
        _graph_parent.PAGERANK_DANGLING_RULE == "UNIFORM_REDISTRIBUTION",
        _graph_parent.PAGERANK_ARITHMETIC == "EXACT_RATIONAL",
        _graph_parent.PER_WINDOW_RANKING_RULE == "PAGERANK_DESCENDING_NUMBER_ASCENDING",
        _graph_parent.ROBUSTNESS_RULE == "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)",
    )
    hot_checks = (
        _hot_parent.BigLottoHotCooccurrenceAdapter.strategy_id
        == PARENT_SOURCE_UNIVERSE_ID_1,
    )
    if not all(graph_checks) or not all(hot_checks):
        raise RuntimeError("a frozen parent semantic contract has drifted")


def _graph_parent_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _graph_parent.FusedNumberRanking:
    _assert_parent_contracts()
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
    prior_history = validate_prior_history(history, target_index)
    return _graph_parent.calculate_window_rankings(prior_history, len(prior_history))


calculate_graph_rankings = calculate_graph_window_rankings
calculate_window_rankings = calculate_graph_window_rankings


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> _graph_parent.FusedNumberRanking:
    return _graph_parent_from_prior_history(validate_prior_history(history, target_index))


calculate_fused_graph_ranking = calculate_graph_parent_ranking


def _build_graph_traversal_pool(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
) -> tuple[int, ...]:
    pool = tuple(graph_parent_ranking.TOP_NUMBERS)
    return _validate_pool(pool)


def calculate_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    return _build_graph_traversal_pool(calculate_graph_parent_ranking(history, target_index))


build_graph_traversal_pool = calculate_graph_traversal_pool
produce_graph_traversal_pool = calculate_graph_traversal_pool


def _graph_component_from_parent(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
) -> ComponentRanking:
    pool = _build_graph_traversal_pool(graph_parent_ranking)
    raw = tuple(graph_parent_ranking.mean_rank(number) for number in pool)
    ordered = pool
    positions = tuple(range(1, RANKED_POOL_CARDINALITY + 1))
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1)
        for position in positions
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=ordered,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
    )


def calculate_graph_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return _graph_component_from_parent(calculate_graph_parent_ranking(history, target_index))


def calculate_graph_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_graph_ranking(history, target_index).RAW_SCORES


def calculate_graph_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_graph_ranking(history, target_index).NORMALIZED_RANKS


graph_components = calculate_graph_components


def _hot_cold_pool_ranking(
    prior_history: tuple[HistoryDraw, ...], pool: Sequence[int]
) -> ComponentRanking:
    raw_all = _hot_cold_raw_scores_from_prior_history(prior_history)
    pool_tuple = _validate_pool(pool)
    return _pool_ranking(
        pool_tuple,
        tuple(raw_all[number - 1] for number in pool_tuple),
        "hot_cold_pool_raw_scores",
    )


def calculate_hot_cold_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent_from_prior_history(prior_history)
    return _hot_cold_pool_ranking(
        prior_history, _build_graph_traversal_pool(graph_parent_ranking)
    )


def calculate_hot_cold_pool_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return calculate_hot_cold_ranking(history, target_index)


def calculate_hot_cold_pool_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_hot_cold_ranking(history, target_index).RAW_SCORES


def calculate_hot_cold_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_hot_cold_ranking(history, target_index).NORMALIZED_RANKS


hot_cold_components = calculate_hot_cold_components


def _exact_pool_values(
    values: Sequence[object] | Mapping[int, object], pool: tuple[int, ...], name: str
) -> Components:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != len(pool) or set(keys) != set(pool):
            raise ValueError(f"{name} mapping must contain exactly the ten pool numbers")
        raw = tuple(values[number] for number in pool)
    else:
        raw = tuple(values)
        if len(raw) != len(pool):
            raise ValueError(f"{name} must contain exactly ten values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw, start=1):
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


def rank_pairwise_scores(
    hot_cold_components: Sequence[object] | Mapping[int, object],
    graph_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    *,
    graph_parent_ranking: object | None = None,
    hot_cold_ranking: ComponentRanking | None = None,
    graph_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized ten-number component vectors."""

    pool = _validate_pool(pool_numbers)
    hot_cold = _exact_pool_values(hot_cold_components, pool, "hot_cold_components")
    graph = _exact_pool_values(graph_components, pool, "graph_components")
    scores = tuple(
        FUSION_WEIGHT_1 * hot_cold[index] + FUSION_WEIGHT_2 * graph[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, scores, strict=True))
    hot_by_number = dict(zip(pool, hot_cold, strict=True))
    graph_by_number = dict(zip(pool, graph, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(hot_by_number[number], graph_by_number[number]),
                -hot_by_number[number],
                -graph_by_number[number],
                number,
            ),
        )
    )
    position_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = [0] * 49
    for number, position in position_by_number.items():
        positions[number - 1] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            HOT_COLD_COMPONENT=hot_by_number[number],
            GRAPH_COMPONENT=graph_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(hot_by_number[number], graph_by_number[number]),
            POSITION=position_by_number[number],
        )
        for number in ordered
    )
    ticket = cast(Ticket, tuple(sorted(ordered[:PICK_COUNT])))
    if len(ticket) != PICK_COUNT or len(set(ticket)) != PICK_COUNT:
        raise RuntimeError("pairwise native ticket must contain six unique numbers")
    return PairwiseRanking(
        POOL_NUMBERS=pool,
        HOT_COLD_COMPONENTS=hot_cold,
        GRAPH_COMPONENTS=graph,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        SCORES=records,
        NATIVE_TICKET=ticket,
        GRAPH_TRAVERSAL_POOL=pool,
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        HOT_COLD_RANKING=hot_cold_ranking,
        GRAPH_RANKING=graph_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both sealed parent components."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent_from_prior_history(prior_history)
    pool = _build_graph_traversal_pool(graph_parent_ranking)
    graph_ranking = _graph_component_from_parent(graph_parent_ranking)
    hot_cold_ranking = _hot_cold_pool_ranking(prior_history, pool)
    return rank_pairwise_scores(
        hot_cold_ranking.NORMALIZED_RANKS,
        graph_ranking.NORMALIZED_RANKS,
        pool,
        graph_parent_ranking=graph_parent_ranking,
        hot_cold_ranking=hot_cold_ranking,
        graph_ranking=graph_ranking,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate = (
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


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    return CandidateIdentity(
        CANDIDATE_ID=candidate_id_for_semantics(record),
        SIGNATURE_HASH=DESIGN_SIGNATURE_SHA256,
        CANONICAL_SEMANTIC_JSON=canonical_semantic_json(record),
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
    "HOT_COLD_COOCCURRENCE_WINDOW",
    "HOT_COLD_FREQUENCY_WINDOW",
    "HOT_COLD_POOL_CARDINALITY",
    "HOT_COLD_SCORE_RULE",
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
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "WINDOWS",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "build_graph_traversal_pool",
    "build_source_ticket_universe",
    "calculate_fused_graph_ranking",
    "calculate_fused_number_ranking",
    "calculate_graph_components",
    "calculate_graph_parent_ranking",
    "calculate_graph_ranking",
    "calculate_graph_rankings",
    "calculate_graph_traversal_pool",
    "calculate_graph_window_rankings",
    "calculate_hot_cold_components",
    "calculate_hot_cold_parent_ranking",
    "calculate_hot_cold_pool_ranking",
    "calculate_hot_cold_pool_raw_scores",
    "calculate_hot_cold_ranking",
    "calculate_hot_cold_raw_scores",
    "calculate_pairwise_ranking",
    "calculate_window_rankings",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "graph_components",
    "hot_cold_components",
    "produce_biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate",
    "produce_bmsgv1_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_traversal_pool",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_hot_cold_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
