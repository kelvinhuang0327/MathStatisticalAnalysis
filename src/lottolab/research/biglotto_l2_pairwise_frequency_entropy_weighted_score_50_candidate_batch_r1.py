"""Causal deterministic BigLotto FREQUENCY + ENTROPY pairwise candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_FREQUENCY_ENTROPY_WEIGHTED_SCORE_50_V1``.  It computes the
exact multiscale occurrence-frequency parent and the exact fifty-draw entropy
parent over all 49 legal numbers, fuses their normalized ranks equally, and
emits the first six final ranks as one native ticket.

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
    biglotto_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1,
)

_frequency_parent = (
    biglotto_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_4dc9ff4fd526d800"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_FREQUENCY_ENTROPY_WEIGHTED_SCORE_50_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "3d3fe8562c581522fb26059a09b4e074e9704a4e8b4e697f19734a8a5ff317eb"
)

FEATURE_1: Final[str] = "FREQUENCY"
FEATURE_2: Final[str] = "ENTROPY"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
FREQUENCY_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
ENTROPY_WINDOW: Final[int] = 50
MINIMUM_HISTORY: Final[int] = 750
RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_frequency_clustering_weighted_score_100_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = "src/lottolab/strategies/adapters/biglotto_wave4.py"
PARENT_SOURCE_SYMBOL_1: Final[str] = "calculate_frequency_statistics"
PARENT_SOURCE_SYMBOL_2: Final[str] = "_entropy_scores"

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
    "ENTROPY_PARENT=BMSGV1_L1_FEATURE_65309ef7bca9f40e;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;ENTROPY_SCORE_50(n)="
    "1/(abs(COUNT_50(n)-300/49)+1/10);COUNT_50="
    "APPEARANCES_IN_SIX_MAIN_NUMBERS_OF_history[T-50:T];EXACT_RATIONAL;"
    "HIGHER_IS_BETTER;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];FREQUENCY_DRAWS_50="
    "history[T-50:T];FREQUENCY_DRAWS_300=history[T-300:T];"
    "FREQUENCY_DRAWS_750=history[T-750:T];ALL_FREQUENCY_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];ENTROPY_DRAWS_50="
    "history[T-50:T];ALL_ENTROPY_WINDOWS_END_AT_T;"
    "TARGET_ROW_history[T]_EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build one complete raw score for every legal number 1..49 for each parent component.",
    (
        "Rank each component higher-is-better; exact raw-score ties use number ascending, "
        "with the FREQUENCY parent using total occurrence count descending before number ascending."
    ),
    (
        "Normalize one-based position p as (49-p)/48; best rank is 1 and worst rank "
        "is 0; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, "
        "historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_MULTISCALE_OCCURRENCE_FREQUENCY_SCORE_FOR_ALL_49_LEGAL_NUMBERS"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = "EXACT_RATIONAL_ENTROPY_SCORE_FOR_ALL_49_LEGAL_NUMBERS"

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*FREQUENCY_NORMALIZED_MULTISCALE_OCCURRENCE_RANK_49(n)+"
    "1/2*ENTROPY_NORMALIZED_RANK_49(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "FREQUENCY normalized multiscale occurrence rank descending.",
    "ENTROPY normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "FREQUENCY parent tie: multiscale frequency score descending, total occurrence "
        "count descending, number ascending."
    ),
    "ENTROPY parent raw-score tie: number ascending.",
    (
        "Final pairwise tie: minimum component rank descending, FREQUENCY rank descending, "
        "ENTROPY rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS_WITH_FUSED_PAIRWISE_SCORE;"
    "NO_INTERMEDIATE_TOP_K_POOL;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS;SORT_TICKET_NUMBERS_ASCENDING;"
    "EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;FREQUENCY_WINDOWS=(50,300,750);ENTROPY_WINDOW=(50);"
    "ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;ALL_49_LEGAL_NUMBERS_REQUIRED;"
    "NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;FREQUENCY_WINDOWS=(50,300,750);"
    "FREQUENCY_SCORE=MEAN_EXACT_OCCURRENCE_RATE;FREQUENCY_TIE_TOTAL_OCCURRENCE_COUNT;"
    "ENTROPY_WINDOW=50;ENTROPY_EXPECTED_COUNT=300/49;ENTROPY_EPSILON=1/10;"
    "PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;FRONTIER_WINDOW_LABEL=50;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_OCCURRENCE_FREQUENCY_PLUS_ENTROPY_DISTRIBUTION_SIGNAL"
)

FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the frequency windows (50,300,750), occurrence-rate definition, "
        "exact multiscale mean, frequency tie-break order, or no-target/future rule."
    ),
    (
        "Do not change the entropy parent identity, 50-draw count window, expected count "
        "300/49, epsilon 1/10, exact rational score, or higher-is-better rule."
    ),
    (
        "Do not change all-49 ranking, (49-p)/48 normalization, equal 1/2 and 1/2 fusion, "
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
    "BMSGV1_L2_PAIRWISE_cca5660423304b0b[B649_PAIRWISE_FREQUENCY_CLUSTERING_WEIGHTED_SCORE_100_V1;SHARED_FREQUENCY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_0ef39f92e3a20b8c[B649_PAIRWISE_COOCCURRENCE_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2507681ad9ef073c[B649_PAIRWISE_GAP_OMISSION_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_bb262c993f3fefee[B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_8e17e64bb96c93de[B649_PAIRWISE_ENTROPY_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1;SHARED_ENTROPY_PARENT_ONLY;COVERED_EXACT;NOT_EQUIVALENT]",
    "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1[FREQUENCY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e[ENTROPY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0[MERGED_PR187_STOCHASTIC_FRONTEND_MONTE_CARLO;NO_DETERMINISTIC_FREQUENCY_ENTROPY_LEVEL2_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the sealed 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw values and all-49 normalized ranks for one component."""

    POOL_NUMBERS: tuple[int, ...]
    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components
    SECONDARY_SCORES: tuple[int, ...] = ()

    def _pool_position(self, number: int) -> int:
        _validate_number(number)
        return self.POOL_NUMBERS.index(number)

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
class FrequencyStatistics:
    """Exact multiscale occurrence-frequency statistics for all legal numbers."""

    POOL_NUMBERS: tuple[int, ...]
    WINDOW_FREQUENCY_RATES: tuple[Components, ...]
    WINDOW_OCCURRENCE_COUNTS: tuple[tuple[int, ...], ...]
    MULTISCALE_FREQUENCY_SCORES: Components
    TOTAL_OCCURRENCE_COUNTS: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EntropyStatistics:
    """Exact fifty-draw entropy-parent statistics."""

    POOL_NUMBERS: tuple[int, ...]
    COUNTS_50: tuple[int, ...]
    RAW_SCORES: Components


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    FREQUENCY_COMPONENT: Fraction
    ENTROPY_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def FREQUENCY_RANK_49(self) -> Fraction:
        return self.FREQUENCY_COMPONENT

    @property
    def ENTROPY_RANK_49(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 fused ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    FREQUENCY_COMPONENTS: Components
    ENTROPY_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    FREQUENCY_RANKING: ComponentRanking | None = None
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

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

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
    "biglotto_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1.py"
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


def _validate_pool(pool_numbers: Sequence[int]) -> tuple[int, ...]:
    pool = tuple(pool_numbers)
    if pool != LEGAL_NUMBERS:
        raise ValueError("pool_numbers must contain all legal numbers 1..49 in order")
    return pool


def _assert_frequency_parent_contract() -> None:
    checks = (
        _frequency_parent.PARENT_SOURCE_UNIVERSE_ID_1 == PARENT_SOURCE_UNIVERSE_ID_1,
        tuple(_frequency_parent.FREQUENCY_WINDOWS) == FREQUENCY_WINDOWS,
        _frequency_parent.MINIMUM_HISTORY == MINIMUM_HISTORY,
        tuple(_frequency_parent.NUMBER_DOMAIN) == NUMBER_DOMAIN,
    )
    if not all(checks):
        raise RuntimeError("the frozen frequency parent semantic contract has drifted")


def _window_frequency_metrics(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> tuple[Components, tuple[int, ...]]:
    draws = prior_history[-window:]
    if len(draws) != window:
        raise RuntimeError("frequency window is shorter than the sealed window")
    counts = tuple(
        sum(number in draw for draw in draws) for number in LEGAL_NUMBERS
    )
    rates = tuple(Fraction(count, window) for count in counts)
    return rates, counts


def calculate_frequency_statistics(
    history: HistoryInput,
    target_index: int,
    pool_numbers: Sequence[int] | None = None,
) -> FrequencyStatistics:
    """Calculate exact multiscale occurrence-frequency metrics for all 49 numbers."""

    _assert_frequency_parent_contract()
    prior_history = validate_prior_history(history, target_index)
    pool = LEGAL_NUMBERS if pool_numbers is None else _validate_pool(pool_numbers)
    window_rates: list[Components] = []
    window_counts: list[tuple[int, ...]] = []
    for window in FREQUENCY_WINDOWS:
        rates, counts = _window_frequency_metrics(prior_history, window)
        window_rates.append(tuple(rates[index - 1] for index in pool))
        window_counts.append(tuple(counts[index - 1] for index in pool))
    multiscale_scores = tuple(
        sum(
            (window_rates[index][number_index] for index in range(len(FREQUENCY_WINDOWS))),
            Fraction(0, 1),
        )
        / len(FREQUENCY_WINDOWS)
        for number_index in range(RANKED_POOL_CARDINALITY)
    )
    total_counts = tuple(
        sum(window_counts[index][number_index] for index in range(len(FREQUENCY_WINDOWS)))
        for number_index in range(RANKED_POOL_CARDINALITY)
    )
    return FrequencyStatistics(
        POOL_NUMBERS=pool,
        WINDOW_FREQUENCY_RATES=tuple(window_rates),
        WINDOW_OCCURRENCE_COUNTS=tuple(window_counts),
        MULTISCALE_FREQUENCY_SCORES=multiscale_scores,
        TOTAL_OCCURRENCE_COUNTS=total_counts,
    )


def _exact_values(
    values: Sequence[object] | Mapping[int, object],
    pool: tuple[int, ...],
    name: str,
    *,
    require_unit_interval: bool = True,
) -> Components:
    if isinstance(values, Mapping):
        if tuple(values) != pool and set(values) != set(pool):
            raise ValueError(f"{name} mapping must contain exactly all legal numbers")
        raw = tuple(values[number] for number in pool)
    else:
        raw = tuple(values)
        if len(raw) != len(pool):
            raise ValueError(f"{name} must contain exactly {len(pool)} values")
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


def _rank_raw_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int],
    name: str,
    secondary_scores: Sequence[int] | Mapping[int, int] | None = None,
) -> ComponentRanking:
    pool = _validate_pool(pool_numbers)
    raw = _exact_values(raw_scores, pool, name, require_unit_interval=False)
    if secondary_scores is None:
        secondary = (0,) * RANKED_POOL_CARDINALITY
    elif isinstance(secondary_scores, Mapping):
        if set(secondary_scores) != set(pool):
            raise ValueError(f"{name} secondary mapping must contain all legal numbers")
        secondary = tuple(secondary_scores[number] for number in pool)
    else:
        secondary = tuple(secondary_scores)
        if len(secondary) != len(pool):
            raise ValueError(f"{name} secondary scores must contain 49 values")
    if any(type(value) is not int or value < 0 for value in secondary):
        raise TypeError(f"{name} secondary scores must be non-negative integers")
    by_number = dict(zip(pool, raw, strict=True))
    secondary_by_number = dict(zip(pool, secondary, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -by_number[number],
                -secondary_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position for position, number in enumerate(ordered, start=1)
    }
    normalized = tuple(
        Fraction(RANKED_POOL_CARDINALITY - positions_by_number[number], 48)
        for number in pool
    )
    return ComponentRanking(
        POOL_NUMBERS=pool,
        RAW_SCORES=raw,
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions_by_number[number] for number in pool),
        NORMALIZED_RANKS=normalized,
        SECONDARY_SCORES=secondary,
    )


def rank_frequency_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    total_occurrence_counts: Sequence[int] | Mapping[int, int],
    pool_numbers: Sequence[int] = LEGAL_NUMBERS,
) -> ComponentRanking:
    """Rank frequency scores with total-occurrence tie-breaking."""

    return _rank_raw_scores(
        raw_scores,
        pool_numbers,
        "frequency_raw_scores",
        total_occurrence_counts,
    )


def calculate_frequency_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    statistics = calculate_frequency_statistics(history, target_index)
    return rank_frequency_scores(
        statistics.MULTISCALE_FREQUENCY_SCORES,
        statistics.TOTAL_OCCURRENCE_COUNTS,
        statistics.POOL_NUMBERS,
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


ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=appearances_in_six_main_numbers_of_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER"
)


def calculate_entropy_statistics(
    history: HistoryInput, target_index: int
) -> EntropyStatistics:
    """Calculate the exact entropy-parent score for every legal number."""

    prior_history = validate_prior_history(history, target_index)
    draws = prior_history[-ENTROPY_WINDOW:]
    if len(draws) != ENTROPY_WINDOW:
        raise RuntimeError("entropy window is shorter than the sealed window")
    counts = tuple(
        sum(number in draw for draw in draws) for number in LEGAL_NUMBERS
    )
    scores = tuple(
        Fraction(1, 1)
        / (abs(Fraction(count, 1) - ENTROPY_EXPECTED_COUNT) + ENTROPY_EPSILON)
        for count in counts
    )
    return EntropyStatistics(
        POOL_NUMBERS=LEGAL_NUMBERS,
        COUNTS_50=counts,
        RAW_SCORES=scores,
    )


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int] = LEGAL_NUMBERS,
) -> ComponentRanking:
    """Rank entropy scores higher-is-better with number-ascending ties."""

    return _rank_raw_scores(raw_scores, pool_numbers, "entropy_raw_scores")


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    statistics = calculate_entropy_statistics(history, target_index)
    return rank_entropy_scores(statistics.RAW_SCORES, statistics.POOL_NUMBERS)


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).RAW_SCORES


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


entropy_components = calculate_entropy_components


def rank_pairwise_scores(
    frequency_components: Sequence[object] | Mapping[int, object],
    entropy_components: Sequence[object] | Mapping[int, object],
    pool_numbers: Sequence[int] = LEGAL_NUMBERS,
    *,
    frequency_ranking: ComponentRanking | None = None,
    entropy_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized all-49 component vectors."""

    pool = _validate_pool(pool_numbers)
    frequency = _exact_values(frequency_components, pool, "frequency_components")
    entropy = _exact_values(entropy_components, pool, "entropy_components")
    scores = tuple(
        FUSION_WEIGHT_1 * frequency[index] + FUSION_WEIGHT_2 * entropy[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    score_by_number = dict(zip(pool, scores, strict=True))
    frequency_by_number = dict(zip(pool, frequency, strict=True))
    entropy_by_number = dict(zip(pool, entropy, strict=True))
    ordered = tuple(
        sorted(
            pool,
            key=lambda number: (
                -score_by_number[number],
                -min(frequency_by_number[number], entropy_by_number[number]),
                -frequency_by_number[number],
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
            FREQUENCY_COMPONENT=frequency_by_number[number],
            ENTROPY_COMPONENT=entropy_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(
                frequency_by_number[number], entropy_by_number[number]
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
        POOL_NUMBERS=pool,
        FREQUENCY_COMPONENTS=frequency,
        ENTROPY_COMPONENTS=entropy,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ordered,
        POSITIONS=positions,
        SCORES=records,
        NATIVE_TICKET=ticket,
        FREQUENCY_RANKING=frequency_ranking,
        ENTROPY_RANKING=entropy_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent components."""

    prior_history = validate_prior_history(history, target_index)
    frequency_ranking = calculate_frequency_ranking(prior_history, len(prior_history))
    entropy_ranking = calculate_entropy_ranking(prior_history, len(prior_history))
    return rank_pairwise_scores(
        frequency_ranking.NORMALIZED_RANKS,
        entropy_ranking.NORMALIZED_RANKS,
        LEGAL_NUMBERS,
        frequency_ranking=frequency_ranking,
        entropy_ranking=entropy_ranking,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first-six ticket from the final all-49 ranking."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_frequency_entropy_weighted_score_50_candidate = (
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
    "FREQUENCY_WINDOWS",
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
    "WINDOW",
    "CandidateIdentity",
    "CandidateMetadata",
    "ComponentRanking",
    "EntropyStatistics",
    "FrequencyStatistics",
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "calculate_entropy_components",
    "calculate_entropy_ranking",
    "calculate_entropy_raw_scores",
    "calculate_entropy_statistics",
    "calculate_frequency_components",
    "calculate_frequency_ranking",
    "calculate_frequency_raw_scores",
    "calculate_frequency_statistics",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_components",
    "frequency_components",
    "fuse_pairwise_scores",
    "produce_biglotto_l2_pairwise_frequency_entropy_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_frequency_entropy_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_entropy_scores",
    "rank_frequency_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
