"""Causal deterministic BigLotto ENTROPY + CONSTRAINT candidate.

This research-only module implements the frozen
``B649_PAIRWISE_ENTROPY_CONSTRAINT_WEIGHTED_SCORE_50_V1`` design.  The
entropy component is the exact Level-1 fifty-draw distribution score over all
49 legal numbers.  The second component reuses the sealed structural
constraint-support parent over the prior thirty draws.  Exact normalized
component ranks are fused with equal weights, and the first admissible
six-number combination in final-rank order is emitted as one native ticket.

Only the strictly prior history prefix is read.  There is no outcome access,
I/O, randomness, calibration, replay, or production catalog integration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice
from types import MappingProxyType
from typing import Final, cast

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
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_c4232a31c03ee3c1"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_ENTROPY_CONSTRAINT_WEIGHTED_SCORE_50_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "653474493d892c72476d574e50afeeb82daf09af71018b446f5826dd5809ec6f"
)

FEATURE_1: Final[str] = "ENTROPY"
FEATURE_2: Final[str] = "CONSTRAINT"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
ENTROPY_WINDOW: Final[int] = 50
CONSTRAINT_SUPPORT_WINDOW: Final[int] = 30
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_CARDINALITY: Final[int] = 49
RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_SOURCE_PATH_1: Final[str] = "src/lottolab/strategies/adapters/biglotto_wave4.py"
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1.py"
)
PARENT_SOURCE_SYMBOL_1: Final[str] = "_entropy_scores"
PARENT_SOURCE_SYMBOL_2: Final[str] = "calculate_constraint_support_scores"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "ENTROPY_PARENT=BMSGV1_L1_FEATURE_65309ef7bca9f40e;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;ENTROPY_SCORE_50(n)="
    "1/(abs(COUNT_50(n)-300/49)+1/10);COUNT_50="
    "APPEARANCES_IN_SIX_MAIN_NUMBERS_OF_history[T-50:T];EXACT_RATIONAL;"
    "HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "CONSTRAINT_PREDICATE(ticket)=ODD_COUNT_2_TO_4;ZONES_COVERED_AT_LEAST_3_FOR_ZONES="
    "(1..10),(11..20),(21..30),(31..40),(41..49);SUM_120_TO_180;"
    "MAX_CONSECUTIVE_RUN_AT_MOST_2;DISTINCT_LAST_DIGITS_AT_LEAST_4;"
    "CONSTRAINT_SUPPORT_30(n)=SUM_{t=T-30}^{T-1}(1_IF_n_IN_history[t] AND "
    "CONSTRAINT_PREDICATE(history[t]));EXACT_INTEGER;HIGHER_IS_BETTER;RAW_TIES_"
    "NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];ENTROPY_DRAWS_50="
    "history[T-50:T];ALL_ENTROPY_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CONSTRAINT_SUPPORT_DRAWS="
    "history[T-30:T];W=30;TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Compute the exact ENTROPY parent raw score for every legal number "
        "using the fixed 50-draw count rule."
    ),
    (
        "Compute the exact CONSTRAINT valid-draw support count for every legal "
        "number over the prior 30 draws."
    ),
    (
        "Rank both component scores over all 49 legal numbers after applying "
        "their fixed number-ascending raw-score tie rules."
    ),
    (
        "Normalize one-based position p as (49-p)/48; best rank is 1 and worst "
        "rank is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_ENTROPY_SCORE_FOR_ALL_49_LEGAL_NUMBERS_WINDOW_50"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_CONSTRAINT_VALID_DRAW_SUPPORT_COUNT_OVER_HISTORY_T_MINUS_30_TO_T_MINUS_1_"
    "FOR_EACH_OF_49_LEGAL_NUMBERS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*ENTROPY_NORMALIZED_RANK_49(n)+1/2*"
    "CONSTRAINT_NORMALIZED_RANK_49(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "ENTROPY normalized rank descending.",
    "CONSTRAINT normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "ENTROPY parent raw-score tie: number ascending.",
    "CONSTRAINT valid-draw support-count tie: number ascending.",
    (
        "Final pairwise tie: minimum component rank descending, ENTROPY rank "
        "descending, CONSTRAINT rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION: Final[str] = "CONSTRAINT_SEARCH"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "RANK_ALL_49_LEGAL_NUMBERS_BY_FINAL_PAIRWISE_SCORE;ENUMERATE_6_NUMBER_"
    "COMBINATIONS_IN_LEXICOGRAPHIC_INDEX_ORDER_OVER_FINAL_RANKING;SELECT_FIRST_"
    "TICKET_SATISFYING_FIXED_CONSTRAINT_PREDICATE;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_LEXICOGRAPHIC_ADMISSIBLE_6_COMBINATION_IN_FINAL_PAIRWISE_RANK_ORDER;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;ENTROPY_WINDOW=(50);CONSTRAINT_SUPPORT_DRAWS="
    "history[T-30:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;NO_VALID_CONSTRAINT_TICKET=>RAISE_"
    "EXPLICIT_CONSTRAINT_SEARCH_EXHAUSTED"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;ENTROPY_WINDOW=50;ENTROPY_EXPECTED_COUNT=300/49;"
    "ENTROPY_EPSILON=1/10;CONSTRAINT_SUPPORT_WINDOW=30;ODD_COUNT=2..4;"
    "ZONES_COVERED_AT_LEAST_3;SUM=120..180;MAX_CONSECUTIVE_RUN=2;"
    "DISTINCT_TAIL_DIGITS_AT_LEAST_4;FRONTIER_WINDOW_LABEL=50;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "ENTROPY_DISTRIBUTION_SIGNAL_PLUS_STRUCTURAL_CONSTRAINT_COMPATIBILITY"
)

KNOWN_SEMANTIC_NEIGHBORS: Final[tuple[str, ...]] = (
    "BMSGV1_L2_PAIRWISE_d8cd36c68f156ea5[B649_PAIRWISE_ENTROPY_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_e121053c05d1fdfa[B649_PAIRWISE_TRANSITION_MARKOV_ENTROPY_WEIGHTED_SCORE_30_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=30;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7ded44c3d9017c19[B649_PAIRWISE_GRAPH_ENTROPY_WEIGHTED_SCORE_100_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800[B649_PAIRWISE_FREQUENCY_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_0ef39f92e3a20b8c[B649_PAIRWISE_COOCCURRENCE_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2507681ad9ef073c[B649_PAIRWISE_GAP_OMISSION_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_bb262c993f3fefee[B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_7434ffb53674510d[B649_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_V1;SHARED_CONSTRAINT_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_5f0c6fb3405f7f78[B649_PAIRWISE_REGIME_STATE_CONSTRAINT_WEIGHTED_SCORE_30_V1;SHARED_CONSTRAINT_PARENT_ONLY;WINDOW=30;NOT_EQUIVALENT]",
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e[ENTROPY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1[CONSTRAINT_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0[MERGED_PR187_STOCHASTIC_FRONTEND_MONTE_CARLO;NO_DETERMINISTIC_ENTROPY_CONSTRAINT_LEVEL2_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the entropy parent identity, 50-draw count window, "
        "expected count 300/49, epsilon 1/10, exact rational score, raw-score "
        "tie rule, or no-target/future rule."
    ),
    (
        "Do not change the structural constraint predicate: odd count 2..4, "
        "at least 3 zones, sum 120..180, maximum consecutive run 2, at least 4 "
        "distinct tail digits, or the W=30 support window."
    ),
    (
        "Do not change the 49-number ranked domain, the (49-p)/48 normalization, "
        "equal 1/2 and 1/2 fusion, final tie-break order, lexicographic "
        "first-admissible constraint search, single-ticket rule, minimum history, "
        "or fallback."
    ),
    (
        "Do not introduce empirical min-max scaling, z-scoring, calibration, "
        "outcome tuning, historical optimization, or randomness."
    ),
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)

EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 751 prior draws are available."""


class ConstraintSearchExhaustedError(ValueError):
    """Raised when no ranked six-number combination satisfies the predicate."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores, positions, and normalized ranks for all 49 numbers."""

    RAW_SCORES: tuple[ComponentValue, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def raw_score(self, number: int) -> ComponentValue:
        _validate_number(number)
        return self.RAW_SCORES[number - 1]

    def score(self, number: int) -> ComponentValue:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    @property
    def SCORES(self) -> tuple[ComponentValue, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class EntropyStatistics:
    """Exact fifty-draw counts and entropy-parent scores for all numbers."""

    POOL_NUMBERS: tuple[int, ...]
    COUNTS_50: tuple[int, ...]
    RAW_SCORES: Components


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent contributions."""

    NUMBER: int
    ENTROPY_COMPONENT: Fraction
    CONSTRAINT_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def ENTROPY_RANK_49(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def CONSTRAINT_RANK_49(self) -> Fraction:
        return self.CONSTRAINT_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 final ranks plus exactly one constraint-admissible ticket."""

    ENTROPY_RANKING: ComponentRanking
    CONSTRAINT_RANKING: ComponentRanking
    ENTROPY_COMPONENTS: Components
    CONSTRAINT_COMPONENTS: Components
    PAIRWISE_SCORES: Components
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

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def score(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]

    def entropy_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.ENTROPY_COMPONENTS[number - 1]

    def constraint_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.CONSTRAINT_COMPONENTS[number - 1]

    def pairwise_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAIRWISE_SCORES[number - 1]


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
    """Read exactly the causal prefix and never inspect the suffix."""

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

    if _constraint_parent.MINIMUM_HISTORY != MINIMUM_HISTORY:
        raise RuntimeError("constraint parent minimum history drifted")
    raw_prefix = _read_history_prefix(history, target_index)
    try:
        return _constraint_parent.validate_prior_history(raw_prefix, len(raw_prefix))
    except _constraint_parent.InsufficientHistoryError as error:
        raise InsufficientHistoryError(str(error)) from error


validate_history = validate_prior_history


ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=APPEARANCES_IN_SIX_MAIN_NUMBERS_OF_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING"
)


def calculate_entropy_statistics(
    history: HistoryInput, target_index: int
) -> EntropyStatistics:
    """Calculate the exact Level-1 entropy score over all legal numbers."""

    prior_history = validate_prior_history(history, target_index)
    draws = prior_history[-ENTROPY_WINDOW:]
    if len(draws) != ENTROPY_WINDOW:
        raise RuntimeError("entropy window is shorter than the sealed window")
    counts = tuple(sum(number in draw for draw in draws) for number in LEGAL_NUMBERS)
    raw_scores = tuple(
        Fraction(1, 1)
        / (abs(Fraction(count, 1) - ENTROPY_EXPECTED_COUNT) + ENTROPY_EPSILON)
        for count in counts
    )
    return EntropyStatistics(
        POOL_NUMBERS=LEGAL_NUMBERS,
        COUNTS_50=counts,
        RAW_SCORES=raw_scores,
    )


def calculate_entropy_parent_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_statistics(history, target_index).RAW_SCORES


calculate_entropy_raw_scores = calculate_entropy_parent_raw_scores


def calculate_constraint_support_scores(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Reuse the exact structural-constraint support parent over all 49 numbers."""

    prior_history = validate_prior_history(history, target_index)
    return _constraint_parent.calculate_constraint_support_scores(
        prior_history, len(prior_history)
    )


constraint_predicate = _constraint_parent.constraint_predicate


def _raw_component_values(
    raw_scores: Sequence[object] | Mapping[int, object], name: str
) -> tuple[ComponentValue, ...]:
    if isinstance(raw_scores, Mapping):
        keys = tuple(raw_scores)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        values = tuple(raw_scores[number] for number in LEGAL_NUMBERS)
    else:
        values = tuple(raw_scores)
        if len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 values")

    converted: list[ComponentValue] = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, Fraction):
            exact: ComponentValue = value
        elif type(value) is int:
            exact = value
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
        if exact < 0:
            raise ValueError(f"{name}[{index}] must be non-negative")
        converted.append(exact)
    return tuple(converted)


def rank_component_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    name: str = "component_scores",
) -> ComponentRanking:
    """Rank one exact component higher-is-better with number-ascending ties."""

    scores = _raw_component_values(raw_scores, name)
    ordered = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (-scores[number - 1], number),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
        normalized[number - 1] = Fraction(
            RANKED_POOL_CARDINALITY - position,
            RANKED_POOL_CARDINALITY - 1,
        )
    return ComponentRanking(
        RAW_SCORES=scores,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized),
    )


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    return rank_component_scores(raw_scores, "entropy_raw_scores")


def rank_constraint_support_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    return rank_component_scores(raw_scores, "constraint_support_scores")


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return rank_entropy_scores(calculate_entropy_parent_raw_scores(history, target_index))


def calculate_constraint_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return rank_constraint_support_scores(
        calculate_constraint_support_scores(history, target_index)
    )


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


def calculate_constraint_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_constraint_ranking(history, target_index).NORMALIZED_RANKS


entropy_components = calculate_entropy_components
constraint_components = calculate_constraint_components


def _normalized_components(
    components: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(components, Mapping):
        keys = tuple(components)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        values = tuple(components[number] for number in LEGAL_NUMBERS)
    else:
        values = tuple(components)
        if len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 values")

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


def select_first_admissible_ticket(
    ranked_numbers: Sequence[int],
    predicate: Callable[[Sequence[int]], bool] = constraint_predicate,
) -> Ticket:
    """Search six-number combinations in final-rank lexicographic order."""

    ranking = tuple(ranked_numbers)
    if len(ranking) != RANKED_POOL_CARDINALITY or set(ranking) != set(LEGAL_NUMBERS):
        raise ValueError("ranked_numbers must be a permutation of legal numbers 1..49")
    for candidate in combinations(ranking, PICK_COUNT):
        if predicate(candidate):
            return cast(Ticket, tuple(sorted(candidate)))
    raise ConstraintSearchExhaustedError(
        "no six-number combination in the final ranking satisfies the frozen constraint"
    )


def _ranking_from_normalized_components(components: Components) -> ComponentRanking:
    """Create a deterministic view for synthetic normalized fusion inputs."""

    ordered = tuple(sorted(LEGAL_NUMBERS, key=lambda number: (-components[number - 1], number)))
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
    return ComponentRanking(
        RAW_SCORES=tuple(0 for _ in LEGAL_NUMBERS),
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=components,
    )


def rank_pairwise_scores(
    entropy_components: Sequence[object] | Mapping[int, object],
    constraint_components: Sequence[object] | Mapping[int, object],
    *,
    source_tickets: TicketPortfolio = (),
) -> PairwiseRanking:
    """Fuse two exact normalized 49-number components and select one ticket."""

    entropy = _normalized_components(entropy_components, "entropy_components")
    constraint = _normalized_components(constraint_components, "constraint_components")
    pairwise = tuple(
        FUSION_WEIGHT_1 * entropy[index] + FUSION_WEIGHT_2 * constraint[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (
                -pairwise[number - 1],
                -min(entropy[number - 1], constraint[number - 1]),
                -entropy[number - 1],
                -constraint[number - 1],
                number,
            ),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ranked, start=1):
        positions[number - 1] = position
    records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            ENTROPY_COMPONENT=entropy[number - 1],
            CONSTRAINT_COMPONENT=constraint[number - 1],
            PAIRWISE_SCORE=pairwise[number - 1],
            MIN_COMPONENT_RANK=min(entropy[number - 1], constraint[number - 1]),
            POSITION=positions[number - 1],
        )
        for number in ranked
    )
    return PairwiseRanking(
        ENTROPY_RANKING=_ranking_from_normalized_components(entropy),
        CONSTRAINT_RANKING=_ranking_from_normalized_components(constraint),
        ENTROPY_COMPONENTS=entropy,
        CONSTRAINT_COMPONENTS=constraint,
        PAIRWISE_SCORES=pairwise,
        RANKED_NUMBERS=ranked,
        POSITIONS=tuple(positions),
        SCORES=records,
        SOURCE_TICKETS=tuple(source_tickets),
        NATIVE_TICKET=select_first_admissible_ticket(ranked),
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent mechanisms."""

    prior_history = validate_prior_history(history, target_index)
    entropy = calculate_entropy_components(prior_history, len(prior_history))
    constraint = calculate_constraint_components(prior_history, len(prior_history))
    return rank_pairwise_scores(entropy, constraint)


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate = (
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
    "CONSTRAINT_SUPPORT_WINDOW",
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
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "EXPECTED_SOURCE_PATH",
    "FALLBACK_RULE",
    "FEATURE_1",
    "FEATURE_2",
    "FUSION",
    "FUSION_FORMULA",
    "FUSION_WEIGHT_1",
    "FUSION_WEIGHT_2",
    "HISTORY_ORDER",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_READY",
    "IMPLEMENTATION_SYMBOL",
    "LEGAL_NUMBERS",
    "LOTTERY_TYPE",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_DOMAIN_TEXT",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
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
    "ConstraintSearchExhaustedError",
    "EntropyStatistics",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "Ticket",
    "TicketPortfolio",
    "calculate_constraint_components",
    "calculate_constraint_ranking",
    "calculate_constraint_support_scores",
    "calculate_entropy_components",
    "calculate_entropy_parent_raw_scores",
    "calculate_entropy_ranking",
    "calculate_entropy_raw_scores",
    "calculate_entropy_statistics",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "constraint_components",
    "constraint_predicate",
    "derive_candidate_identity",
    "entropy_components",
    "fuse_pairwise_scores",
    "produce_biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_component_scores",
    "rank_constraint_support_scores",
    "rank_entropy_scores",
    "rank_pairwise_scores",
    "select_first_admissible_ticket",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
