"""Causal deterministic BigLotto GRAPH + SIGNAL_FOURIER pairwise candidate.

This research-only module implements the single candidate sealed by
``B649_PAIRWISE_GRAPH_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1``.  The exact graph
parent creates the ten-number traversal pool.  The exact signal_fourier parent is
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
from itertools import islice, pairwise
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_parent,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as _signal_fourier_parent,  # noqa: E501
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_ab2b557ca7671da8"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_GRAPH_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "897432010d0e6382c69fd69ea35bdabc5bf82151d0b9898f1e2f2d59c9a732ba"
)

FEATURE_1: Final[str] = "GRAPH"
FEATURE_2: Final[str] = "SIGNAL_FOURIER"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 300
GRAPH_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
SIGNAL_FOURIER_WINDOW: Final[int] = 300
MINIMUM_HISTORY: Final[int] = 750
RANKED_POOL_DOMAIN: Final[str] = (
    "TOP_10_MULTISCALE_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
)
RANKED_POOL_CARDINALITY: Final[int] = 10
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "GRAPH_TRAVERSAL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/biglotto_graph_network_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_SYMBOL_1: Final[str] = "fuse_window_rankings"
PARENT_SOURCE_SYMBOL_2: Final[str] = "calculate_window_rankings"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "GRAPH_PARENT=B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;FOR_EACH_W_IN_(50,300,750):"
    "UNDIRECTED_EDGE_W(a,b)=COUNT_PRIOR_WINDOW_DRAWS_CONTAINING_BOTH_NUMBERS_FOR_a_LESS_THAN_b;"
    "UNDECAYED_INTEGER_SAME_DRAW_COOCCURRENCE;PAGERANK_DAMPING=17/20;"
    "PAGERANK_ITERATIONS=20;INITIAL_VECTOR=UNIFORM_1_OVER_49;"
    "DANGLING_NODES=UNIFORM_REDISTRIBUTION;EXACT_RATIONAL;"
    "PER_WINDOW_ORDER=PAGERANK_DESC_NUMBER_ASC;NORMALIZED_W=(49-POSITION)/48;"
    "FUSED_GRAPH_RANK=MEAN_OF_NORMALIZED_50_300_750;"
    "FUSED_TIE=MINIMUM_MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;"
    "GRAPH_POOL=FIRST_10_FUSED_GRAPH_RANKED_NUMBERS;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "SIGNAL_FOURIER_PARENT=B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;Y_300,n(t)=1_IF_NUMBER_N_APPEARS_IN_SIX_MAIN_NUMBERS(history[t])_ELSE_0;"
    "COUNT_300(n)=SUM_t(Y_300,n(t));MEAN_300(n)=COUNT_300(n)/300;"
    "Z_300,n(t)=Y_300,n(t)-MEAN_300(n);"
    "R_300,n(l)=SUM_{t=0}^{299}(Z_300,n(t)*Z_300,n((t+l) MOD 300));"
    "l=0..299;EXACT_RATIONAL;"
    "SPECTRAL_IPR_300(n)=IF R_300,n(0)>0 THEN "
    "SUM_{l=0}^{299}(R_300,n(l)^2)/(300*R_300,n(0)^2) ELSE 0;"
    "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_300(n)=IF R_300,n(0)>0 THEN "
    "MAX_{l=1..150}(ABS(R_300,n(l))/R_300,n(0)) ELSE 0;"
    "HIGHER_IS_BETTER;PER_WINDOW_ORDER=SPECTRAL_IPR_DESCENDING_PEAK_NORMALIZED_CIRCULAR_AUTOCORR_DESCENDING_NUMBER_ASCENDING;"
    "NO_FLOATING_FFT;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];GRAPH_DRAWS_50=history[T-50:T];"
    "GRAPH_DRAWS_300=history[T-300:T];GRAPH_DRAWS_750=history[T-750:T];"
    "ALL_GRAPH_WINDOWS_END_AT_T;TARGET_ROW_history[T] EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];SIGNAL_FOURIER_DRAWS="
    "history[T-300:T];W=300;COUNT_ONLY_SIX_MAIN_NUMBERS;"
    "TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build the exact multiscale GRAPH PageRank ranking for all 49 legal numbers "
    "using the frozen graph parent and retain the first 10 graph-ranked numbers "
    "as the traversal pool.",
    "Compute the exact SIGNAL_FOURIER spectral IPR and peak normalized circular "
    "autocorrelation raw scores for all 49 legal numbers using the fixed W300 "
    "parent rule, then restrict that parent order to the same ten-number graph "
    "traversal pool.",
    "Use graph-parent order as the GRAPH component order; rank the restricted "
    "SIGNAL_FOURIER parent order as the SIGNAL_FOURIER component within the same "
    "ten-number pool; SIGNAL_FOURIER raw-score ties use peak normalized circular "
    "autocorrelation descending and number ascending.",
    "Normalize each one-based position p within the ten-number pool as "
    "(10-p)/9; best rank is 1 and worst rank is 0; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, "
    "outcome-derived normalization, historical optimization, or randomness.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_GRAPH_PAGERANK_FUSED_TRAVERSAL_RANK_FOR_THE_FIRST_10_OF_49_LEGAL_NUMBERS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RATIONAL_SIGNAL_FOURIER_SPECTRAL_IPR_AND_PEAK_SCORE_FOR_ALL_49_LEGAL_NUMBERS_RESTRICTED_TO_THE_10_NUMBER_GRAPH_TRAVERSAL_POOL"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*GRAPH_NORMALIZED_TRAVERSAL_RANK_10(n)+"
    "1/2*SIGNAL_FOURIER_NORMALIZED_RANK_10(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "GRAPH normalized traversal rank descending.",
    "SIGNAL_FOURIER normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "GRAPH parent per-window PageRank tie: PageRank descending then number "
    "ascending; graph fused tie: minimum, median, maximum normalized window "
    "rank descending then number ascending.",
    "SIGNAL_FOURIER parent raw-score tie: peak normalized circular "
    "autocorrelation descending, then number ascending.",
    "Final pairwise tie: minimum component rank descending, GRAPH rank "
    "descending, SIGNAL_FOURIER rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "BUILD_THE_EXACT_MULTISCALE_GRAPH_PARENT_RANKING_OVER_ALL_49_LEGAL_NUMBERS;"
    "RETAIN_FIRST_10_GRAPH_RANKED_NUMBERS_AS_THE_FROZEN_TRAVERSAL_POOL;"
    "COMPUTE_THE_EXACT_SIGNAL_FOURIER_PARENT_RAW_SCORES_FOR_ALL_49_LEGAL_NUMBERS;"
    "RESTRICT_SIGNAL_FOURIER_PARENT_ORDER_TO_THE_SAME_10_NUMBER_GRAPH_TRAVERSAL_POOL;"
    "RANK_BOTH_COMPONENTS_WITHIN_THE_SAME_10_NUMBER_POOL;"
    "FUSE_WITH_EQUAL_EXACT_RANK_WEIGHTS;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_TRAVERSAL_POOL_NUMBERS"
)
TICKET_CONSTRUCTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_GRAPH_TRAVERSAL_POOL_NUMBERS;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;GRAPH_PARENT_WINDOWS=(50,300,750);"
    "SIGNAL_FOURIER_WINDOW=300;ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;EXACTLY_10_GRAPH_TRAVERSAL_POOL_NUMBERS_REQUIRED;"
    "NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;GRAPH_WINDOWS=(50,300,750);"
    "GRAPH_DAMPING=17/20;GRAPH_PAGERANK_ITERATIONS=20;"
    "GRAPH_INITIALIZATION=UNIFORM_1_OVER_49;GRAPH_DANGLING=UNIFORM_REDISTRIBUTION;"
    "GRAPH_POOL_CARDINALITY=10;SIGNAL_FOURIER_WINDOW=300;FULL_SPECTRUM_IPR;"
    "EXACT_CIRCULAR_AUTOCORRELATION;PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "FRONTIER_WINDOW_LABEL=300;NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_NETWORK_CENTRALITY_STRUCTURE_PLUS_PERIODICITY_SIGNAL"
)

FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change the GRAPH parent windows (50,300,750), same-draw "
    "undirected cooccurrence edges, PageRank damping 17/20, exactly 20 "
    "iterations, uniform 1/49 initialization, uniform dangling redistribution, "
    "exact rational arithmetic, per-window ordering, equal three-window rank "
    "fusion, robustness tie, or graph-derived first-10 traversal pool.",
    "Do not change the signal_fourier parent identity, 50-draw count window, expected "
    "count 300/49, epsilon 1/10, exact rational score, or higher-is-better "
    "rule.",
    "Do not change restriction of the SIGNAL_FOURIER parent order to the graph-derived "
    "ten-number pool, within-pool (10-p)/9 normalization, equal 1/2 and 1/2 "
    "fusion, final tie-break order, first-six single-ticket rule, minimum "
    "history, or fallback.",
    "Do not introduce empirical min-max scaling, z-scoring, calibration, "
    "outcome tuning, historical optimization, or randomness.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_1b75b7279a69956c[B649_PAIRWISE_HOT_COLD_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_5b92df6e42366e6b[B649_PAIRWISE_GAP_OMISSION_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_AND_GRAPH_TRAVERSAL_POOL_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15[B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe[B649_PAIRWISE_GRAPH_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_GRAPH_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800[B649_PAIRWISE_FREQUENCY_SIGNAL_FOURIER_WEIGHTED_SCORE_50_V1;SHARED_SIGNAL_FOURIER_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_8e17e64bb96c93de[B649_PAIRWISE_SIGNAL_FOURIER_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1;SHARED_SIGNAL_FOURIER_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1[GRAPH_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e[SIGNAL_FOURIER_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0[MERGED_PR187_STOCHASTIC_FRONTEND_MONTE_CARLO;NO_DETERMINISTIC_GRAPH_SIGNAL_FOURIER_LEVEL2_COVERAGE]",
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
            raise ValueError("number is not in the ten-number graph traversal pool") from error

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


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    GRAPH_COMPONENT: Fraction
    SIGNAL_FOURIER_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def GRAPH_RANK_10(self) -> Fraction:
        return self.GRAPH_COMPONENT

    @property
    def SIGNAL_FOURIER_RANK_10(self) -> Fraction:
        return self.SIGNAL_FOURIER_COMPONENT

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
    GRAPH_COMPONENTS: Components
    SIGNAL_FOURIER_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    GRAPH_TRAVERSAL_POOL: tuple[int, ...]
    GRAPH_PARENT_RANKING: object | None = None
    GRAPH_RANKING: ComponentRanking | None = None
    SIGNAL_FOURIER_RANKING: ComponentRanking | None = None

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
        return self.SCORES[self.position(number) - 1]


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


EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"


def _validate_number(number: int) -> None:
    if type(number) is not int or number not in LEGAL_NUMBERS:
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
        values = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly six integers"
        ) from error
    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly six numbers")
    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        _validate_number(raw_number)
        numbers.append(raw_number)
    sorted_numbers = tuple(sorted(numbers))
    for left, right in pairwise(sorted_numbers):
        if left == right:
            raise ValueError(f"history[{draw_index}] contains duplicate number {left}")
    return cast(HistoryDraw, sorted_numbers)


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Validate and return only the strictly prior history prefix."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index {target_index} provides {len(raw_prefix)} draws, "
            f"which is fewer than the required minimum {MINIMUM_HISTORY}"
        )
    return tuple(
        _validate_draw(raw_draw, draw_index)
        for draw_index, raw_draw in enumerate(raw_prefix)
    )


validate_history = validate_prior_history


def _assert_graph_parent_contract() -> None:
    checks = (
        _graph_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_1,
        tuple(_graph_parent.WINDOWS) == GRAPH_WINDOWS,
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
    if not all(checks):
        raise RuntimeError("the frozen graph parent semantic contract has drifted")


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if len(pool) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain exactly ten numbers")
    for number in pool:
        _validate_number(number)
    if len(set(pool)) != RANKED_POOL_CARDINALITY:
        raise ValueError("pool_numbers must contain ten unique numbers")
    return pool


def _graph_parent_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _graph_parent.FusedNumberRanking:
    _assert_graph_parent_contract()
    rankings = _graph_parent.calculate_window_rankings(prior_history, len(prior_history))
    if tuple(ranking.WINDOW for ranking in rankings) != GRAPH_WINDOWS:
        raise RuntimeError("graph parent returned the wrong frozen windows")
    fused = _graph_parent.fuse_window_rankings(rankings)
    if len(fused.TOP_NUMBERS) != RANKED_POOL_CARDINALITY:
        raise RuntimeError("graph parent did not produce exactly ten traversal numbers")
    return fused


def calculate_graph_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_graph_parent.GraphWindow, ...]:
    prior_history = validate_prior_history(history, target_index)
    _assert_graph_parent_contract()
    return _graph_parent.calculate_window_rankings(prior_history, len(prior_history))


calculate_window_rankings = calculate_graph_window_rankings
calculate_graph_rankings = calculate_graph_window_rankings


def calculate_graph_parent_ranking(
    history: HistoryInput, target_index: int
) -> _graph_parent.FusedNumberRanking:
    prior_history = validate_prior_history(history, target_index)
    return _graph_parent_from_prior_history(prior_history)


calculate_fused_graph_ranking = calculate_graph_parent_ranking


def calculate_graph_traversal_pool(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    return _validate_pool(calculate_graph_parent_ranking(history, target_index).TOP_NUMBERS)


build_graph_traversal_pool = calculate_graph_traversal_pool
produce_graph_traversal_pool = calculate_graph_traversal_pool


def _graph_component_from_parent(
    graph_parent_ranking: _graph_parent.FusedNumberRanking,
) -> ComponentRanking:
    pool = _validate_pool(graph_parent_ranking.TOP_NUMBERS)
    raw = tuple(graph_parent_ranking.mean_rank(number) for number in pool)
    positions = tuple(range(1, RANKED_POOL_CARDINALITY + 1))
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - position, RANKED_POOL_CARDINALITY - 1)
        for position in positions
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=pool,
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


SIGNAL_FOURIER_SCORE_RULE: Final[str] = PARENT_COMPONENT_RULE_2


def _assert_signal_fourier_parent_contract() -> None:
    checks = (
        _signal_fourier_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_2,
        _signal_fourier_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _signal_fourier_parent.NUMBER_DOMAIN == NUMBER_DOMAIN,
        SIGNAL_FOURIER_WINDOW in _signal_fourier_parent.FEATURE_WINDOWS,
        _signal_fourier_parent.PER_WINDOW_RANKING_RULE
        == "SPECTRAL_IPR_DESCENDING_PEAK_NORMALIZED_CIRCULAR_AUTOCORR_DESCENDING_NUMBER_ASCENDING",
    )
    if not all(checks):
        raise RuntimeError("the frozen SIGNAL_FOURIER parent semantic contract has drifted")


def _signal_fourier_parent_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _signal_fourier_parent.WindowRanking:
    _assert_signal_fourier_parent_contract()
    ranking = _signal_fourier_parent.calculate_window_rankings(
        prior_history, len(prior_history), SIGNAL_FOURIER_WINDOW
    )
    if (
        ranking.WINDOW != SIGNAL_FOURIER_WINDOW
        or ranking.WINDOW_DRAW_COUNT != SIGNAL_FOURIER_WINDOW
    ):
        raise RuntimeError("SIGNAL_FOURIER parent returned the wrong frozen window")
    return ranking


def calculate_signal_fourier_statistics(
    history: HistoryInput, target_index: int
) -> _signal_fourier_parent.WindowRanking:
    """Calculate the exact W300 SIGNAL_FOURIER parent ranking."""

    prior_history = validate_prior_history(history, target_index)
    return _signal_fourier_parent_from_prior_history(prior_history)


def _exact_pool_values(
    values: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
    *,
    require_unit_interval: bool = True,
) -> Components:
    if isinstance(values, Mapping):
        if set(values) != set(pool) or len(values) != len(pool):
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
        if exact < Fraction(0, 1) or (
            require_unit_interval and exact > Fraction(1, 1)
        ):
            if require_unit_interval:
                raise ValueError(f"{name}[{index}] must lie in [0,1]")
            raise ValueError(f"{name}[{index}] must be non-negative")
        converted.append(exact)
    return tuple(converted)


def calculate_signal_fourier_parent_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    ranking = calculate_signal_fourier_statistics(history, target_index)
    return tuple(ranking.spectral_ipr(number) for number in LEGAL_NUMBERS)


def _rank_signal_fourier_pool(
    parent_ranking: _signal_fourier_parent.WindowRanking,
    pool_numbers: Sequence[int],
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -parent_ranking.spectral_ipr(number),
                -parent_ranking.peak_normalized_circular_autocorr(number),
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=tuple(parent_ranking.spectral_ipr(number) for number in pool),
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions_by_number[number] for number in pool),
        NORMALIZED_RANKS=tuple(
            Fraction(RANKED_POOL_CARDINALITY - positions_by_number[number], 9)
            for number in pool
        ),
    )


def calculate_signal_fourier_pool_ranking(
    history: HistoryInput,
    target_index: int,
    pool_numbers: Sequence[int] | None = None,
) -> ComponentRanking:
    prior_history = validate_prior_history(history, target_index)
    graph_pool = (
        _validate_pool(pool_numbers)
        if pool_numbers is not None
        else _validate_pool(_graph_parent_from_prior_history(prior_history).TOP_NUMBERS)
    )
    return _rank_signal_fourier_pool(
        _signal_fourier_parent_from_prior_history(prior_history), graph_pool
    )


def calculate_signal_fourier_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return calculate_signal_fourier_pool_ranking(history, target_index)


def calculate_signal_fourier_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_signal_fourier_pool_ranking(history, target_index).RAW_SCORES


def calculate_signal_fourier_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_signal_fourier_pool_ranking(history, target_index).NORMALIZED_RANKS


signal_fourier_components = calculate_signal_fourier_components


def rank_pairwise_scores(
    graph_components: Sequence[object] | Mapping[int, object],
    signal_fourier_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    *,
    graph_parent_ranking: object | None = None,
    graph_ranking: ComponentRanking | None = None,
    signal_fourier_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized ten-number component vectors."""

    pool = _validate_pool(pool_numbers)
    graph = _exact_pool_values(graph_components, pool, "graph_components")
    signal_fourier = _exact_pool_values(
        signal_fourier_components, pool, "signal_fourier_components"
    )
    scores = tuple(
        FUSION_WEIGHT_1 * graph[index] + FUSION_WEIGHT_2 * signal_fourier[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, scores, strict=True))
    graph_by_number = dict(zip(pool, graph, strict=True))
    signal_fourier_by_number = dict(zip(pool, signal_fourier, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(graph_by_number[number], signal_fourier_by_number[number]),
                -graph_by_number[number],
                -signal_fourier_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = [0] * 49
    for number, position in positions_by_number.items():
        positions[number - 1] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            GRAPH_COMPONENT=graph_by_number[number],
            SIGNAL_FOURIER_COMPONENT=signal_fourier_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(graph_by_number[number], signal_fourier_by_number[number]),
            POSITION=positions_by_number[number],
        )
        for number in ordered
    )
    ticket = cast(Ticket, tuple(sorted(ordered[:PICK_COUNT])))
    if (
        len(ticket) != PICK_COUNT
        or len(set(ticket)) != PICK_COUNT
        or not all(number in LEGAL_NUMBERS for number in ticket)
    ):
        raise RuntimeError("pairwise native ticket must contain six legal unique numbers")
    return PairwiseRanking(
        POOL_NUMBERS=pool,
        GRAPH_COMPONENTS=graph,
        SIGNAL_FOURIER_COMPONENTS=signal_fourier,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        SCORES=records,
        NATIVE_TICKET=ticket,
        GRAPH_TRAVERSAL_POOL=pool,
        GRAPH_PARENT_RANKING=graph_parent_ranking,
        GRAPH_RANKING=graph_ranking,
        SIGNAL_FOURIER_RANKING=signal_fourier_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent components."""

    prior_history = validate_prior_history(history, target_index)
    graph_parent_ranking = _graph_parent_from_prior_history(prior_history)
    graph_ranking = _graph_component_from_parent(graph_parent_ranking)
    signal_fourier_ranking = calculate_signal_fourier_pool_ranking(
        prior_history,
        len(prior_history),
        graph_ranking.POOL_NUMBERS,
    )
    return rank_pairwise_scores(
        graph_ranking.NORMALIZED_RANKS,
        signal_fourier_ranking.NORMALIZED_RANKS,
        graph_ranking.POOL_NUMBERS,
        graph_parent_ranking=graph_parent_ranking,
        graph_ranking=graph_ranking,
        signal_fourier_ranking=signal_fourier_ranking,
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
produce_bmsgv1_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate = (
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
        "FUSION": FUSION,
        "FUSION_FORMULA": FUSION_FORMULA,
        "FUSION_WEIGHT_1": FUSION_WEIGHT_1_TEXT,
        "FUSION_WEIGHT_2": FUSION_WEIGHT_2_TEXT,
        "HISTORY_ORDER": HISTORY_ORDER,
        "IMPLEMENTATION_READY": IMPLEMENTATION_READY,
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
        "PARENT_SOURCE_UNIVERSE_VERSION_1": PARENT_SOURCE_UNIVERSE_VERSION_1,
        "PARENT_SOURCE_UNIVERSE_VERSION_2": PARENT_SOURCE_UNIVERSE_VERSION_2,
        "PARENT_WINDOW_RULE_1": PARENT_WINDOW_RULE_1,
        "PARENT_WINDOW_RULE_2": PARENT_WINDOW_RULE_2,
        "RANKED_POOL_CARDINALITY": RANKED_POOL_CARDINALITY,
        "RANKED_POOL_DOMAIN": RANKED_POOL_DOMAIN,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "TICKET_CONSTRUCTION": TICKET_CONSTRUCTION,
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
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
    "PARENT_SOURCE_SYMBOL_1",
    "PARENT_SOURCE_SYMBOL_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_SOURCE_UNIVERSE_VERSION_1",
    "PARENT_SOURCE_UNIVERSE_VERSION_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RNG",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SIGNAL_FOURIER_SCORE_RULE",
    "SIGNAL_FOURIER_WINDOW",
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
    "calculate_pairwise_ranking",
    "calculate_signal_fourier_components",
    "calculate_signal_fourier_parent_raw_scores",
    "calculate_signal_fourier_pool_ranking",
    "calculate_signal_fourier_ranking",
    "calculate_signal_fourier_raw_scores",
    "calculate_signal_fourier_statistics",
    "calculate_window_rankings",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "graph_components",
    "produce_biglotto_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate",
    "produce_bmsgv1_l2_pairwise_graph_signal_fourier_weighted_score_300_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_graph_traversal_pool",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_pairwise_scores",
    "signal_fourier_components",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
