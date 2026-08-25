"""Causal deterministic BigLotto TRANSITION_MARKOV + ENTROPY candidate.

This research-only module implements the single candidate sealed by
``B649_PAIRWISE_TRANSITION_MARKOV_ENTROPY_WEIGHTED_SCORE_30_V1``.  The exact
multiscale transition-Markov parent fuses W50, W300, and W750 normalized
ranks using the latest prior draw as its anchor.  The exact entropy parent is
ranked over the same all-49 domain, the two normalized ranks are fused
equally, and the first six final ranks form one native ticket.

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
from itertools import islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as _markov_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_e121053c05d1fdfa"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_TRANSITION_MARKOV_ENTROPY_WEIGHTED_SCORE_30_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "4c7fb915fc4ed594191ac7a904b52dac9a036ed9101ac698a41fc7fc171fe90f"
)

FEATURE_1: Final[str] = "TRANSITION_MARKOV"
FEATURE_2: Final[str] = "ENTROPY"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 30
TRANSITION_MARKOV_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
TRANSITION_MARKOV_WINDOW: Final[int] = TRANSITION_MARKOV_WINDOWS[0]
ENTROPY_WINDOW: Final[int] = 50
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/"
    "biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = "src/lottolab/strategies/adapters/biglotto_wave4.py"
PARENT_SOURCE_SYMBOL_1: Final[str] = "fuse_window_rankings"
PARENT_SOURCE_SYMBOL_2: Final[str] = "_entropy_scores"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "TRANSITION_MARKOV_PARENT=B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;"
    "FOR_EACH_W_IN_(50,300,750);WINDOW_DRAWS_W=history[T-(W+1):T];"
    "W_ADJACENT_TRANSITIONS;FINAL_DESTINATION_IS_ANCHOR;"
    "TRANSITION_COUNT_W(a,n)=COUNT_PAIRS(D_j_CONTAINS_a,D_(j+1)_CONTAINS_n);"
    "OUTGOING_COUNT_W(a)=SUM_N(TRANSITION_COUNT_W(a,n));"
    "P_W(n|a)=TRANSITION_COUNT_W(a,n)/OUTGOING_COUNT_W(a);"
    "EXACT_RATIONAL;ZERO_IF_OUTGOING_ZERO;ANCHOR_DRAW=history[T-1];"
    "MARKOV_SCORE_W(n)=SUM_A_IN_ANCHOR(P_W(n|a))/6;"
    "PER_WINDOW_ORDER=MARKOV_SCORE_DESC_NUMBER_ASC;"
    "NORMALIZED_W=(49-POSITION)/48;"
    "FUSED_MARKOV_RANK=MEAN_OF_NORMALIZED_50_300_750;"
    "FUSED_TIE=MINIMUM_MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "ENTROPY_PARENT=BMSGV1_L1_FEATURE_65309ef7bca9f40e;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;"
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=APPEARANCES_IN_SIX_MAIN_NUMBERS_OF_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "TRANSITION_DRAWS_50=history[T-51:T];"
    "TRANSITION_DRAWS_300=history[T-301:T];"
    "TRANSITION_DRAWS_750=history[T-751:T];ANCHOR_DRAW=history[T-1];"
    "ALL_TRANSITION_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "ENTROPY_DRAWS_50=history[T-50:T];ALL_ENTROPY_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build the exact multiscale TRANSITION_MARKOV parent for every legal number "
    "using W50, W300, and W750 adjacent-transition windows and the latest-anchor rule.",
    "Use the parent mean of the three exact normalized per-window ranks as the "
    "TRANSITION_MARKOV component; retain its minimum/median/maximum tie rule.",
    "Build one complete exact ENTROPY parent raw score for every legal number "
    "1..49 using the fixed 50-draw count rule.",
    "Rank the fused TRANSITION_MARKOV component and ENTROPY component "
    "higher-is-better; parent raw-score ties use number ascending.",
    "Each per-window and entropy one-based position p is normalized as (49-p)/48; "
    "the multiscale Markov component is the exact mean of its three normalized "
    "ranks; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, "
    "outcome-derived normalization, historical optimization, or randomness.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_TRANSITION_MARKOV_FUSED_NORMALIZED_RANK_FOR_ALL_49_LEGAL_NUMBERS_WINDOWS_50_300_750"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RATIONAL_ENTROPY_SCORE_FOR_ALL_49_LEGAL_NUMBERS_WINDOW_50"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*TRANSITION_MARKOV_FUSED_NORMALIZED_RANK_50_300_750(n)+"
    "1/2*ENTROPY_NORMALIZED_RANK_50(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "TRANSITION_MARKOV normalized rank descending.",
    "ENTROPY normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "TRANSITION_MARKOV per-window raw-score tie: number ascending; fused "
    "robustness tie: minimum/median/maximum normalized rank descending, number ascending.",
    "ENTROPY parent raw-score tie: number ascending.",
    "Final pairwise tie: minimum component rank descending, TRANSITION_MARKOV "
    "rank descending, ENTROPY rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS_WITH_FUSED_PAIRWISE_SCORE;"
    "NO_INTERMEDIATE_TOP_K_POOL;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;ENTROPY_WINDOW=(50);"
    "TRANSITION_MARKOV_WINDOWS=(50,300,750);"
    "TRANSITION_MARKOV_DRAWS_W=history[T-(W+1):T];"
    "TRANSITION_MARKOV_ANCHOR=history[T-1];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;"
    "NO_TRUNCATION;NO_PARENT_DEGRADATION;NO_RANDOMNESS;"
    "ALL_49_LEGAL_NUMBERS_REQUIRED;NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;TRANSITION_MARKOV_WINDOWS=(50,300,750);"
    "TRANSITION_WINDOW_USES_W_PLUS_1_PRIOR_DRAWS;"
    "TRANSITION_INITIAL_ANCHOR=LATEST_PRIOR_DRAW;"
    "UNSMOOTHED_CONDITIONAL_PROBABILITIES;ENTROPY_WINDOW=50;"
    "ENTROPY_EXPECTED_COUNT=300/49;ENTROPY_EPSILON=1/10;"
    "PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;FRONTIER_WINDOW_LABEL=30;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_DIRECTIONAL_TRANSITION_STRUCTURE_PLUS_ENTROPY_DISTRIBUTION_SIGNAL"
)

FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change the TRANSITION_MARKOV parent identity, W50/W300/W750 "
    "transition windows, adjacent-draw transition definition, latest-anchor rule, "
    "unsmoothed exact conditional probabilities, score mass rule, exact "
    "arithmetic, raw-score tie-break, or no-target/future rule.",
    "Do not change the entropy parent identity, 50-draw count window, expected "
    "count 300/49, epsilon 1/10, exact rational score, or higher-is-better "
    "rule.",
    "Do not change all-49 ranking, per-window and fused (49-p)/48 normalization, equal 1/2 and 1/2 "
    "fusion, final tie-break order, first-six single-ticket rule, minimum "
    "history, or fallback.",
    "Do not introduce empirical min-max scaling, z-scoring, calibration, "
    "outcome tuning, historical optimization, or randomness.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)
KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_d9930aebfbbee697[B649_PAIRWISE_MARKOV_TRANSITION_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_TRANSITION_MARKOV_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_0ef39f92e3a20b8c[B649_PAIRWISE_COOCCURRENCE_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2507681ad9ef073c[B649_PAIRWISE_GAP_OMISSION_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_bb262c993f3fefee[B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_8e17e64bb96c93de[B649_PAIRWISE_ENTROPY_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800[B649_PAIRWISE_FREQUENCY_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7ded44c3d9017c19[B649_PAIRWISE_GRAPH_ENTROPY_WEIGHTED_SCORE_100_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_e849a4b70db5d01e[B649_PAIRWISE_COOCCURRENCE_BAYES_RANK_WEIGHTED_SCORE_50_V1;NO_SHARED_FEATURE;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_04da0231c3998f63[B649_PAIRWISE_BAYESIAN_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1;NO_SHARED_FEATURE;COVERED_EXACT;NOT_EQUIVALENT]",
    "B649_MULTISCALE_MARKOV_TRANSITION_RANKED_POOL_V1[TRANSITION_MARKOV_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e[ENTROPY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0[MERGED_PR187_STOCHASTIC_FRONTEND_MONTE_CARLO;NO_DETERMINISTIC_TRANSITION_MARKOV_ENTROPY_LEVEL2_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 751 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw values and all-49 normalized ranks for one parent."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def raw_score(self, number: int) -> Fraction:
        return self.RAW_SCORES[_number_index(number)]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        return self.POSITIONS[_number_index(number)]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[_number_index(number)]

    @property
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class EntropyStatistics:
    """Exact fifty-draw entropy-parent statistics for all legal numbers."""

    COUNTS_50: tuple[int, ...]
    RAW_SCORES: Components

    @property
    def POOL_NUMBERS(self) -> tuple[int, ...]:
        return LEGAL_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    TRANSITION_MARKOV_COMPONENT: Fraction
    ENTROPY_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def MARKOV_COMPONENT(self) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENT

    @property
    def TRANSITION_COMPONENT(self) -> Fraction:
        return self.TRANSITION_MARKOV_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 fused ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    TRANSITION_MARKOV_COMPONENTS: Components
    ENTROPY_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    TRANSITION_MARKOV_PARENT_RANKING: object | None = None
    TRANSITION_MARKOV_RANKING: ComponentRanking | None = None
    ENTROPY_RANKING: ComponentRanking | None = None

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
    def MARKOV_COMPONENTS(self) -> Components:
        return self.TRANSITION_MARKOV_COMPONENTS

    def position(self, number: int) -> int:
        return self.POSITIONS[_number_index(number)]

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
    "biglotto_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"


def _validate_number(number: int) -> None:
    if type(number) is not int or number not in LEGAL_NUMBERS:
        raise ValueError("number must be an integer in 1..49")


def _number_index(number: int) -> int:
    _validate_number(number)
    return number - 1


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
    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] contains duplicate number")
    return cast(HistoryDraw, tuple(sorted(numbers)))


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


def _assert_markov_parent_contract() -> None:
    checks = (
        _markov_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_1,
        tuple(_markov_parent.WINDOWS) == TRANSITION_MARKOV_WINDOWS,
        _markov_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        _markov_parent.PICK_COUNT == PICK_COUNT,
        _markov_parent.TRANSITION_WINDOW_RULE
        == "WINDOW_DRAWS_W=HISTORY[TARGET_INDEX-(W+1):TARGET_INDEX];"
        "W_ADJACENT_TRANSITIONS;FINAL_DESTINATION_IS_ANCHOR",
        _markov_parent.TRANSITION_COUNT_RULE
        == "TRANSITION_COUNT_W(a,n)=COUNT_PAIRS(D_j_CONTAINS_a,D_(j+1)_CONTAINS_n)",
        _markov_parent.ZERO_OUTGOING_RULE == "ZERO_CONTRIBUTION_NO_FALLBACK",
        _markov_parent.ANCHOR_WEIGHT_RULE == "EXACT_EQUAL_ONE_SIXTH",
        _markov_parent.MARKOV_SCORE_RULE
        == "MARKOV_SCORE_W(n)=SUM_A_IN_ANCHOR(P_W(n|a))/6;EXACT_RATIONAL",
        _markov_parent.PER_WINDOW_RANKING_RULE
        == "MARKOV_SCORE_DESCENDING_NUMBER_ASCENDING",
        _markov_parent.WINDOW_NORMALIZATION_RULE == "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL",
        _markov_parent.WINDOW_FUSION_RULE
        == "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+"
        "NORMALIZED_750)/3;ROBUSTNESS_TIE_BREAK",
    )
    if not all(checks):
        raise RuntimeError("the frozen transition-Markov parent contract has drifted")


def calculate_markov_window_ranking(
    history: HistoryInput, target_index: int, window: int = TRANSITION_MARKOV_WINDOW
) -> _markov_parent.WindowRanking:
    """Calculate one exact transition-Markov window from the frozen parent."""

    prior_history = validate_prior_history(history, target_index)
    _assert_markov_parent_contract()
    if window not in TRANSITION_MARKOV_WINDOWS:
        raise ValueError(
            "the frozen pairwise transition windows are "
            f"{TRANSITION_MARKOV_WINDOWS}"
        )
    return _markov_parent.rank_numbers_by_window(
        prior_history, len(prior_history), window
    )


rank_numbers_by_window = calculate_markov_window_ranking
calculate_transition_window = calculate_markov_window_ranking
calculate_markov_window = calculate_markov_window_ranking


def calculate_markov_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_markov_ranking(history, target_index).RAW_SCORES


def calculate_markov_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_markov_parent.WindowRanking, ...]:
    """Calculate all exact W50/W300/W750 transition-Markov windows."""

    prior_history = validate_prior_history(history, target_index)
    _assert_markov_parent_contract()
    rankings = _markov_parent.calculate_window_rankings(
        prior_history, len(prior_history)
    )
    if tuple(ranking.WINDOW for ranking in rankings) != TRANSITION_MARKOV_WINDOWS:
        raise RuntimeError("the frozen transition-Markov parent returned wrong windows")
    return rankings


calculate_window_rankings = calculate_markov_window_rankings


def calculate_fused_markov_ranking(
    history: HistoryInput, target_index: int
) -> _markov_parent.FusedNumberRanking:
    """Fuse the exact parent normalized ranks over W50, W300, and W750."""

    return _markov_parent.fuse_window_rankings(
        calculate_markov_window_rankings(history, target_index)
    )


calculate_markov_parent_ranking = calculate_fused_markov_ranking


def _component_ranking_from_fused_parent(
    fused: _markov_parent.FusedNumberRanking,
) -> ComponentRanking:
    positions = [0] * len(LEGAL_NUMBERS)
    for position, number in enumerate(fused.ORDERED_NUMBERS, start=1):
        positions[number - 1] = position
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=fused.MEAN_RANKS,
        ORDERED_NUMBERS=fused.ORDERED_NUMBERS,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=fused.MEAN_RANKS,
    )


def calculate_markov_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return _component_ranking_from_fused_parent(
        calculate_fused_markov_ranking(history, target_index)
    )


calculate_transition_markov_ranking = calculate_markov_ranking


def calculate_transition_markov_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_markov_ranking(history, target_index).NORMALIZED_RANKS


markov_components = calculate_transition_markov_components


ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=appearances_in_six_main_numbers_of_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER"
)


def _entropy_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> tuple[tuple[int, ...], Components]:
    draws = prior_history[-ENTROPY_WINDOW:]
    counts = tuple(
        sum(number in draw for draw in draws) for number in LEGAL_NUMBERS
    )
    scores = tuple(
        Fraction(1, 1)
        / (abs(Fraction(count, 1) - ENTROPY_EXPECTED_COUNT) + ENTROPY_EPSILON)
        for count in counts
    )
    return counts, scores


def calculate_entropy_statistics(
    history: HistoryInput, target_index: int
) -> EntropyStatistics:
    """Calculate the exact entropy-parent score for every legal number."""

    prior_history = validate_prior_history(history, target_index)
    counts, scores = _entropy_scores_from_prior_history(prior_history)
    return EntropyStatistics(COUNTS_50=counts, RAW_SCORES=scores)


def _ranking_from_raw_scores(
    raw_scores: Components,
) -> ComponentRanking:
    ordered = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (-raw_scores[number - 1], number),
        )
    )
    positions = [0] * len(LEGAL_NUMBERS)
    normalized = [Fraction(0, 1)] * len(LEGAL_NUMBERS)
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
        normalized[number - 1] = Fraction(49 - position, 48)
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized),
    )


def calculate_entropy_parent_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_statistics(history, target_index).RAW_SCORES


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return _ranking_from_raw_scores(
        calculate_entropy_statistics(history, target_index).RAW_SCORES
    )


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).RAW_SCORES


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


entropy_components = calculate_entropy_components


def _exact_all49_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(values, Mapping):
        if set(values) != set(LEGAL_NUMBERS) or len(values) != len(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly 49 numbers")
        raw = tuple(values[number] for number in LEGAL_NUMBERS)
    else:
        raw = tuple(values)
        if len(raw) != len(LEGAL_NUMBERS):
            raise ValueError(f"{name} must contain exactly 49 values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw, start=1):
        if isinstance(value, Fraction):
            exact = value
        elif type(value) is int:
            exact = Fraction(value, 1)
        else:
            raise TypeError(
                f"{name}[{index}] must use exact Fraction or integer arithmetic"
            )
        if exact < Fraction(0, 1) or exact > Fraction(1, 1):
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        converted.append(exact)
    return tuple(converted)


def rank_pairwise_scores(
    transition_markov_components: Sequence[object] | Mapping[int, object],
    entropy_components: Sequence[object] | Mapping[int, object],
    *,
    transition_markov_parent_ranking: object | None = None,
    transition_markov_ranking: ComponentRanking | None = None,
    entropy_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized all-49 component vectors."""

    markov = _exact_all49_values(
        transition_markov_components, "transition_markov_components"
    )
    entropy = _exact_all49_values(entropy_components, "entropy_components")
    scores = tuple(
        FUSION_WEIGHT_1 * markov[index] + FUSION_WEIGHT_2 * entropy[index]
        for index in range(len(LEGAL_NUMBERS))
    )
    score_by_number = dict(zip(LEGAL_NUMBERS, scores, strict=True))
    markov_by_number = dict(zip(LEGAL_NUMBERS, markov, strict=True))
    entropy_by_number = dict(zip(LEGAL_NUMBERS, entropy, strict=True))
    ordered = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (
                -score_by_number[number],
                -min(markov_by_number[number], entropy_by_number[number]),
                -markov_by_number[number],
                -entropy_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    positions = tuple(positions_by_number[number] for number in LEGAL_NUMBERS)
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            TRANSITION_MARKOV_COMPONENT=markov_by_number[number],
            ENTROPY_COMPONENT=entropy_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(
                markov_by_number[number], entropy_by_number[number]
            ),
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
        POOL_NUMBERS=LEGAL_NUMBERS,
        TRANSITION_MARKOV_COMPONENTS=markov,
        ENTROPY_COMPONENTS=entropy,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=positions,
        SCORES=records,
        NATIVE_TICKET=ticket,
        TRANSITION_MARKOV_PARENT_RANKING=transition_markov_parent_ranking,
        TRANSITION_MARKOV_RANKING=transition_markov_ranking,
        ENTROPY_RANKING=entropy_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent components."""

    prior_history = validate_prior_history(history, target_index)
    parent_ranking = _markov_parent.fuse_window_rankings(
        _markov_parent.calculate_window_rankings(prior_history, len(prior_history))
    )
    markov_ranking = _component_ranking_from_fused_parent(parent_ranking)
    _, entropy_raw = _entropy_scores_from_prior_history(prior_history)
    entropy_ranking = _ranking_from_raw_scores(entropy_raw)
    return rank_pairwise_scores(
        markov_ranking.NORMALIZED_RANKS,
        entropy_ranking.NORMALIZED_RANKS,
        transition_markov_parent_ranking=parent_ranking,
        transition_markov_ranking=markov_ranking,
        entropy_ranking=entropy_ranking,
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
produce_bmsgv1_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate = (
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
    "ENTROPY_EPSILON",
    "ENTROPY_EXPECTED_COUNT",
    "ENTROPY_SCORE_RULE",
    "ENTROPY_WINDOW",
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
    "SOURCE_UNIVERSE_CONTRACT",
    "TICKET_CONSTRUCTION",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "TRANSITION_MARKOV_WINDOW",
    "TRANSITION_MARKOV_WINDOWS",
    "WINDOW",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "EntropyStatistics",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "calculate_entropy_components",
    "calculate_entropy_parent_raw_scores",
    "calculate_entropy_ranking",
    "calculate_entropy_raw_scores",
    "calculate_entropy_statistics",
    "calculate_fused_markov_ranking",
    "calculate_fused_number_ranking",
    "calculate_markov_parent_ranking",
    "calculate_markov_ranking",
    "calculate_markov_raw_scores",
    "calculate_markov_window",
    "calculate_markov_window_ranking",
    "calculate_markov_window_rankings",
    "calculate_pairwise_ranking",
    "calculate_transition_markov_ranking",
    "calculate_transition_window",
    "calculate_window_rankings",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_components",
    "fuse_pairwise_scores",
    "markov_components",
    "produce_biglotto_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate",
    "produce_bmsgv1_l2_pairwise_transition_markov_entropy_weighted_score_30_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_numbers_by_window",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
