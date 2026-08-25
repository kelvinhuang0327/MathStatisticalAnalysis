"""Causal deterministic BigLotto Level-2 ENTROPY + BAYESIAN candidate.

This research-only module implements the candidate sealed by
B649_PAIRWISE_ENTROPY_BAYESIAN_PROBABILISTIC_WEIGHTED_SCORE_50_V1.  It combines
the fixed W50 entropy count-balance parent with the fixed multiscale Bayesian
changepoint-BMA parent.  Both components rank all 49 legal numbers with exact
normalized ranks, which are fused equally into one native six-number ticket.

Only the strictly prior history prefix is consumed.  The module has no I/O,
outcome access, fitted parameters, catalog integration, or randomness.
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
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as _bayesian_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_378b7fc29066cbc8"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = (
    "B649_PAIRWISE_ENTROPY_BAYESIAN_PROBABILISTIC_WEIGHTED_SCORE_50_V1"
)
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "60d925ebad4528856691a1de64cfebba7e67541276a40e0d58acfe189fabf0e3"
)

FEATURE_1: Final[str] = "ENTROPY"
FEATURE_2: Final[str] = "BAYESIAN_PROBABILISTIC"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 50))
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
ENTROPY_WINDOW: Final[int] = 50
BAYESIAN_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
BAYES_WINDOWS: Final[tuple[int, int, int]] = BAYESIAN_WINDOWS
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
NATIVE_TICKET_COUNT: Final[int] = 1
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_SOURCE_PATH_1: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1.py"
)
PARENT_SOURCE_PATH_2: Final[str] = (
    "src/lottolab/research/"
    "biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1.py"
)
PARENT_SOURCE_SYMBOL_1: Final[str] = "calculate_entropy_raw_scores"
PARENT_SOURCE_SYMBOL_2: Final[str] = "calculate_fused_number_ranking"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "ENTROPY_PARENT=BMSGV1_L1_FEATURE_65309ef7bca9f40e;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;"
    "COUNT_50(n)=appearances_in_six_main_numbers_of_history[T-50:T];"
    "ENTROPY_EXPECTED_COUNT=300/49;ENTROPY_EPSILON=1/10;"
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "EXACT_RATIONAL;HIGHER_IS_BETTER;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "BAYESIAN_PARENT=B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;"
    "FOR_EACH_W_IN_(50,300,750);WINDOW_DRAWS_W=history[T-W:T];"
    "MODEL_M0=STABLE_SINGLE_BERNOULLI_RATE_OVER_FULL_WINDOW;"
    "MODEL_M1=TWO_REGIME_INDEPENDENT_BERNOULLI_RATES_OLDER_VS_RECENT_HALVES;"
    "PRIOR=BETA(6,43);MODEL_PRIORS=EXACT_EQUAL_ONE_HALF_EACH;"
    "BMA_PREDICTIVE_W(n)=POSTERIOR_MODEL_AVERAGE_OF_M0_AND_M1_PREDICTIVES;"
    "EXACT_RATIONAL;"
    "PER_WINDOW_ORDER=BMA_PREDICTIVE_DESCENDING_POSTERIOR_M1_DESCENDING_"
    "PREDICTIVE_M1_DESCENDING_NUMBER_ASCENDING;"
    "NORMALIZED_W=(49-POSITION)/48;"
    "FUSED_BAYES_RANK=MEAN_OF_NORMALIZED_50_300_750;"
    "FUSED_TIE=MINIMUM_MEDIAN_MAXIMUM_NORMALIZED_RANK_DESC_THEN_NUMBER_ASC;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "ENTROPY_HISTORY=history[T-50:T];"
    "ALL_ENTROPY_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "BAYES_DRAWS_50=history[T-50:T];"
    "BAYES_DRAWS_300=history[T-300:T];"
    "BAYES_DRAWS_750=history[T-750:T];"
    "ALL_BAYES_WINDOWS_END_AT_T;TARGET_ROW_history[T]_EXCLUDED"
)

ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=appearances_in_six_main_numbers_of_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER"
)

COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_ENTROPY_RAW_AND_NORMALIZED_RANK_FOR_ALL_49_"
    "LEGAL_NUMBERS_WINDOW_50"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_MULTISCALE_BAYES_CHANGEPOINT_BMA_PREDICTIVE_RANK_FOR_ALL_49_"
    "LEGAL_NUMBERS_WINDOWS_50_300_750"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact ENTROPY parent for every legal number using the W50 "
        "count-balance score."
    ),
    (
        "Rank the exact ENTROPY raw score for every legal number higher-is-better "
        "with raw ties resolved by number ascending, then normalize one-based "
        "position p as (49-p)/48; exact rational only."
    ),
    (
        "Build the exact multiscale BAYESIAN_PROBABILISTIC change-point BMA "
        "predictive parent for every legal number using fixed W50, W300, and W750 "
        "windows."
    ),
    (
        "Rank the fused BAYESIAN_PROBABILISTIC component higher-is-better with its "
        "parent raw/fused tie rule, then normalize one-based position p as "
        "(49-p)/48; exact rational only."
    ),
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*ENTROPY_NORMALIZED_RANK_50(n)+"
    "1/2*BAYESIAN_BMA_FUSED_NORMALIZED_RANK_50_300_750(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "ENTROPY normalized rank descending.",
    "BAYESIAN_PROBABILISTIC fused normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "ENTROPY raw-score tie: number ascending; BAYESIAN_PROBABILISTIC "
        "per-window BMA predictive tie: posterior model M1 descending, "
        "predictive M1 descending, number ascending; fused Bayesian robustness "
        "tie: minimum/median/maximum normalized rank descending, number ascending."
    ),
    (
        "ENTROPY raw score is reciprocal absolute deviation from 300/49 with "
        "epsilon 1/10; BAYESIAN_PROBABILISTIC uses its exact per-window and "
        "fused tie rules."
    ),
    (
        "Final pairwise tie: minimum component rank descending, ENTROPY rank "
        "descending, BAYESIAN_PROBABILISTIC rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "RANK_ALL_49_LEGAL_NUMBERS_BY_FINAL_PAIRWISE_SCORE;"
    "SELECT_FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS;NO_OUTCOME_OR_FUTURE_DATA"
)
TICKET_SELECTION_RULE: Final[str] = (
    "FIRST_LEXICOGRAPHIC_ADMISSIBLE_6_COMBINATION_IN_FINAL_PAIRWISE_RANK_ORDER;"
    "SORT_TICKET_NUMBERS_ASCENDING;EMIT_ONE_NATIVE_TICKET"
)
TICKET_CONSTRUCTION_RULE: Final[str] = TICKET_SELECTION_RULE
CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;ENTROPY_WINDOW=history[T-50:T];"
    "BAYES_WINDOWS=(50,300,750);ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;"
    "NO_TRUNCATION;NO_PARENT_DEGRADATION;NO_RANDOMNESS;"
    "ALL_49_LEGAL_NUMBERS_REQUIRED;NO_ALTERNATE_CONSTRUCTOR"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;"
    "ENTROPY_WINDOW=50;ENTROPY_EXPECTED_COUNT=300/49;"
    "ENTROPY_EPSILON=1/10;BAYES_WINDOWS=(50,300,750);"
    "BAYES_PRIOR=BETA(6,43);BAYES_MODEL_PRIORS=1/2,1/2;"
    "BAYES_M0_STABLE_BERNOULLI;BAYES_M1_OLDER_RECENT_TWO_REGIME;"
    "PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;FRONTIER_WINDOW_LABEL=50;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "ENTROPY_COUNT_BALANCE_STRUCTURE_PLUS_"
    "BAYESIAN_RATE_CHANGE_MODEL_AVERAGING"
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    (
        "Do not change the ENTROPY parent identity, W50 history, expected count "
        "300/49, epsilon 1/10, reciprocal absolute-deviation score, exact "
        "arithmetic, raw-score ties, or no-target/future rule."
    ),
    (
        "Do not change the BAYESIAN_PROBABILISTIC parent identity, W50/W300/W750 "
        "windows, Beta(6,43) prior, equal model priors, stable-vs-two-regime "
        "model definitions, exact evidence, BMA predictive rule, fused tie-break, "
        "or no-target/future rule."
    ),
    (
        "Do not change all-49 ranking, per-parent (49-p)/48 normalization, equal "
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
    "BMSGV1_L2_PAIRWISE_e88b3b2ac2603902[B649_PAIRWISE_HOT_COLD_BAYESIAN_PROBABILISTIC_WEIGHTED_SCORE_50_V1;SHARED_BAYESIAN_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_bb262c993f3fefee[B649_PAIRWISE_HOT_COLD_ENTROPY_WEIGHTED_SCORE_50_V1;SHARED_ENTROPY_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_e00095f81602a581[B649_PAIRWISE_GAP_OMISSION_BAYESIAN_PROBABILISTIC_WEIGHTED_SCORE_50_V1;SHARED_BAYESIAN_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_90f234ae973ba1a9[B649_PAIRWISE_TRANSITION_MARKOV_BAYESIAN_PROBABILISTIC_WEIGHTED_SCORE_30_V1;SHARED_BAYESIAN_PARENT_ONLY;WINDOW=30;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_e849a4b70db5d01e[B649_PAIRWISE_COOCCURRENCE_BAYES_RANK_WEIGHTED_SCORE_50_V1;SHARED_BAYESIAN_PARENT_ONLY;WINDOW=50;NOT_EQUIVALENT]",
    "BMSGV1_L2_PAIRWISE_2939296ce8a4507c[B649_PAIRWISE_CLUSTERING_BAYESIAN_WEIGHTED_SCORE_100_V1;SHARED_BAYESIAN_PARENT_ONLY;WINDOW=100;NOT_EQUIVALENT]",
    "B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1[BAYESIAN_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e[ENTROPY_PARENT_ONLY;NOT_PAIRWISE_EQUIVALENT]",
    "ORIGIN_MAIN_39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0[MERGED_PR187_STOCHASTIC_FRONTEND_MONTE_CARLO;NO_DETERMINISTIC_ENTROPY_BAYESIAN_LEVEL2_COVERAGE]",
    "PR #164[OPEN_DRAFT_OPERATIONAL_TOOLING_ONLY;NO_PAIRWISE_PREDICTION_COMPONENT]",
)

EXPECTED_IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1"
)
EXPECTED_IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_MODULE: Final[str] = EXPECTED_IMPLEMENTATION_MODULE
IMPLEMENTATION_SYMBOL: Final[str] = EXPECTED_IMPLEMENTATION_SYMBOL
EXPECTED_SOURCE_PATH: Final[str] = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1.py"
)
EXPECTED_FOCUSED_TEST_MODULE: Final[str] = (
    "tests/unit/"
    "test_biglotto_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1.py"
)
IMPLEMENTATION_READY: Final[str] = "YES"


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
    ROBUSTNESS: tuple[tuple[Fraction, Fraction, Fraction], ...] = ()
    WINDOW_RANKINGS: tuple[object, ...] = ()

    def raw_score(self, number: int) -> Fraction:
        return self.RAW_SCORES[_number_index(number)]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        return self.POSITIONS[_number_index(number)]

    def normalized_rank(self, number: int) -> Fraction:
        return self.NORMALIZED_RANKS[_number_index(number)]

    def mean_rank(self, number: int) -> Fraction:
        return self.normalized_rank(number)

    def robustness(self, number: int) -> tuple[Fraction, Fraction, Fraction]:
        return self.ROBUSTNESS[_number_index(number)]

    @property
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent contributions."""

    NUMBER: int
    ENTROPY_COMPONENT: Fraction
    BAYESIAN_PROBABILISTIC_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def ENTROPY_RANK_50(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def BAYESIAN_PROBABILISTIC_RANK(self) -> Fraction:
        return self.BAYESIAN_PROBABILISTIC_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 fused ranks and exactly one native ticket."""

    POOL_NUMBERS: tuple[int, ...]
    ENTROPY_COMPONENTS: Components
    BAYESIAN_PROBABILISTIC_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket
    ENTROPY_RANKING: ComponentRanking | None = None
    BAYESIAN_RANKING: ComponentRanking | None = None
    BAYESIAN_PARENT_RANKING: object | None = None

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
    def ENTROPY_RANKS(self) -> Components:
        return self.ENTROPY_COMPONENTS

    @property
    def BAYESIAN_COMPONENTS(self) -> Components:
        return self.BAYESIAN_PROBABILISTIC_COMPONENTS

    def position(self, number: int) -> int:
        return self.POSITIONS[_number_index(number)]

    def score(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]

    def entropy_component(self, number: int) -> Fraction:
        return self.ENTROPY_COMPONENTS[_number_index(number)]

    def bayesian_probabilistic_component(self, number: int) -> Fraction:
        return self.BAYESIAN_PROBABILISTIC_COMPONENTS[_number_index(number)]

    def bayesian_component(self, number: int) -> Fraction:
        return self.bayesian_probabilistic_component(number)

    def pairwise_score(self, number: int) -> Fraction:
        return self.PAIRWISE_SCORES[_number_index(number)]


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
    return cast(HistoryDraw, tuple(numbers))


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


def _entropy_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    """Calculate the sealed exact-rational W=50 entropy-parent scores."""

    counts = [0] * RANKED_POOL_CARDINALITY
    for draw in prior_history[-ENTROPY_WINDOW:]:
        for number in draw:
            counts[number - 1] += 1
    return tuple(
        Fraction(1, 1)
        / (
            abs(Fraction(counts[number - 1], 1) - ENTROPY_EXPECTED_COUNT)
            + ENTROPY_EPSILON
        )
        for number in LEGAL_NUMBERS
    )


def _exact_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> tuple[Fraction, ...]:
    if isinstance(values, Mapping):
        if set(values) != set(LEGAL_NUMBERS) or len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in LEGAL_NUMBERS)
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 values")
    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            converted.append(value)
        elif type(value) is int:
            converted.append(Fraction(value, 1))
        else:
            raise TypeError(
                f"{name}[{index}] must use exact Fraction or integer arithmetic"
            )
    return tuple(converted)


def _rank_raw_scores(
    values: Sequence[object] | Mapping[int, object], name: str
) -> ComponentRanking:
    raw_scores = _exact_values(values, name)
    ordered_numbers = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (-raw_scores[number - 1], number),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized_ranks = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact sealed ENTROPY raw score vector for 1..49."""

    return _entropy_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    return _rank_raw_scores(raw_scores, "entropy_raw_scores")


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return rank_entropy_scores(calculate_entropy_raw_scores(history, target_index))


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


calculate_entropy_raw = calculate_entropy_raw_scores
calculate_fused_entropy_ranking = calculate_entropy_ranking
entropy_components = calculate_entropy_components
entropy_component_50 = calculate_entropy_components


def _assert_bayesian_parent_contract() -> None:
    checks = (
        _bayesian_parent.SOURCE_UNIVERSE_ID == PARENT_SOURCE_UNIVERSE_ID_2,
        tuple(_bayesian_parent.BAYES_WINDOWS) == BAYESIAN_WINDOWS,
        tuple(_bayesian_parent.WINDOWS) == BAYESIAN_WINDOWS,
        _bayesian_parent.MINIMUM_HISTORY == 750,
        _bayesian_parent.PICK_COUNT == PICK_COUNT,
        _bayesian_parent.PRIOR_ALPHA == 6,
        _bayesian_parent.PRIOR_BETA == 43,
        Fraction(1, 2) == _bayesian_parent.MODEL_PRIOR_M0,
        Fraction(1, 2) == _bayesian_parent.MODEL_PRIOR_M1,
        _bayesian_parent.PER_WINDOW_RANKING_RULE
        == "BMA_PREDICTIVE_DESCENDING_POSTERIOR_M1_DESCENDING_"
        "PREDICTIVE_M1_DESCENDING_NUMBER_ASCENDING",
        _bayesian_parent.WINDOW_NORMALIZATION_RULE
        == "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL",
        _bayesian_parent.WINDOW_FUSION_RULE
        == "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+"
        "NORMALIZED_750)/3;ROBUSTNESS_TIE_BREAK",
    )
    if not all(checks):
        raise RuntimeError("the frozen Bayesian parent contract has drifted")


def calculate_bayesian_window_ranking(
    history: HistoryInput,
    target_index: int,
    window: int = BAYESIAN_WINDOWS[0],
) -> _bayesian_parent.WindowRanking:
    """Calculate one exact Bayesian changepoint-BMA window."""

    prior_history = validate_prior_history(history, target_index)
    _assert_bayesian_parent_contract()
    if window not in BAYESIAN_WINDOWS:
        raise ValueError(f"the frozen Bayesian windows are {BAYESIAN_WINDOWS}")
    return _bayesian_parent.rank_numbers_by_window(
        prior_history, len(prior_history), window
    )


rank_bayesian_numbers_by_window = calculate_bayesian_window_ranking
calculate_bayes_window = calculate_bayesian_window_ranking


def calculate_bayesian_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[_bayesian_parent.WindowRanking, ...]:
    """Calculate all exact Bayesian W50/W300/W750 windows."""

    prior_history = validate_prior_history(history, target_index)
    _assert_bayesian_parent_contract()
    rankings = _bayesian_parent.calculate_window_rankings(
        prior_history, len(prior_history)
    )
    if tuple(ranking.WINDOW for ranking in rankings) != BAYESIAN_WINDOWS:
        raise RuntimeError("the frozen Bayesian parent returned wrong windows")
    return rankings


def calculate_fused_bayesian_ranking(
    history: HistoryInput, target_index: int
) -> _bayesian_parent.FusedNumberRanking:
    """Fuse exact Bayesian normalized ranks over the three windows."""

    _assert_bayesian_parent_contract()
    return _bayesian_parent.fuse_window_rankings(
        calculate_bayesian_window_rankings(history, target_index)
    )


calculate_bayesian_parent_ranking = calculate_fused_bayesian_ranking


def _component_ranking_from_fused_bayesian_parent(
    fused: _bayesian_parent.FusedNumberRanking,
) -> ComponentRanking:
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(fused.ORDERED_NUMBERS, start=1):
        positions[number - 1] = position
    return ComponentRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        RAW_SCORES=fused.MEAN_RANKS,
        ORDERED_NUMBERS=fused.ORDERED_NUMBERS,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=fused.MEAN_RANKS,
        ROBUSTNESS=fused.ROBUSTNESS,
        WINDOW_RANKINGS=fused.WINDOW_RANKINGS,
    )


def calculate_bayesian_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return _component_ranking_from_fused_bayesian_parent(
        calculate_fused_bayesian_ranking(history, target_index)
    )


calculate_bayesian_probabilistic_ranking = calculate_bayesian_ranking


def calculate_bayesian_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_bayesian_ranking(history, target_index).NORMALIZED_RANKS


def calculate_bayesian_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_bayesian_ranking(history, target_index).RAW_SCORES


bayesian_components = calculate_bayesian_components
bayesian_probabilistic_components = calculate_bayesian_components


def _exact_all49_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(values, Mapping):
        if set(values) != set(LEGAL_NUMBERS) or len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} mapping must contain exactly 49 numbers")
        raw = tuple(values[number] for number in LEGAL_NUMBERS)
    else:
        raw = tuple(values)
        if len(raw) != RANKED_POOL_CARDINALITY:
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
    entropy_components: Sequence[object] | Mapping[int, object],
    bayesian_probabilistic_components: Sequence[object] | Mapping[int, object],
    *,
    entropy_ranking: ComponentRanking | None = None,
    bayesian_parent_ranking: object | None = None,
    bayesian_ranking: ComponentRanking | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized all-49 component vectors."""

    entropy = _exact_all49_values(entropy_components, "entropy_components")
    bayesian = _exact_all49_values(
        bayesian_probabilistic_components,
        "bayesian_probabilistic_components",
    )
    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * entropy[index]
        + FUSION_WEIGHT_2 * bayesian[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    entropy_by_number = dict(zip(LEGAL_NUMBERS, entropy, strict=True))
    bayesian_by_number = dict(zip(LEGAL_NUMBERS, bayesian, strict=True))
    score_by_number = dict(zip(LEGAL_NUMBERS, pairwise_scores, strict=True))
    ranked_numbers = tuple(
        sorted(
            LEGAL_NUMBERS,
            key=lambda number: (
                -score_by_number[number],
                -min(entropy_by_number[number], bayesian_by_number[number]),
                -entropy_by_number[number],
                -bayesian_by_number[number],
                number,
            ),
        )
    )
    positions_by_number = {
        number: position
        for position, number in enumerate(ranked_numbers, start=1)
    }
    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            ENTROPY_COMPONENT=entropy_by_number[number],
            BAYESIAN_PROBABILISTIC_COMPONENT=bayesian_by_number[number],
            PAIRWISE_SCORE=score_by_number[number],
            MIN_COMPONENT_RANK=min(
                entropy_by_number[number],
                bayesian_by_number[number],
            ),
            POSITION=positions_by_number[number],
        )
        for number in ranked_numbers
    )
    ticket = cast(Ticket, tuple(sorted(ranked_numbers[:PICK_COUNT])))
    if (
        len(ticket) != PICK_COUNT
        or len(set(ticket)) != PICK_COUNT
        or not all(number in LEGAL_NUMBERS for number in ticket)
    ):
        raise RuntimeError("pairwise native ticket must contain six legal unique numbers")
    return PairwiseRanking(
        POOL_NUMBERS=LEGAL_NUMBERS,
        ENTROPY_COMPONENTS=entropy,
        BAYESIAN_PROBABILISTIC_COMPONENTS=bayesian,
        PAIRWISE_SCORES=pairwise_scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions_by_number[number] for number in LEGAL_NUMBERS),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
        ENTROPY_RANKING=entropy_ranking,
        BAYESIAN_RANKING=bayesian_ranking,
        BAYESIAN_PARENT_RANKING=bayesian_parent_ranking,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent components."""

    prior_history = validate_prior_history(history, target_index)
    _assert_bayesian_parent_contract()
    entropy_ranking = rank_entropy_scores(
        _entropy_raw_scores_from_prior_history(prior_history)
    )
    bayesian_parent_ranking = _bayesian_parent.fuse_window_rankings(
        _bayesian_parent.calculate_window_rankings(prior_history, len(prior_history))
    )
    bayesian_ranking = _component_ranking_from_fused_bayesian_parent(
        bayesian_parent_ranking
    )
    return rank_pairwise_scores(
        entropy_ranking.NORMALIZED_RANKS,
        bayesian_ranking.NORMALIZED_RANKS,
        entropy_ranking=entropy_ranking,
        bayesian_parent_ranking=bayesian_parent_ranking,
        bayesian_ranking=bayesian_ranking,
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
produce_bmsgv1_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate = (
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
    "BAYESIAN_WINDOWS",
    "BAYES_WINDOWS",
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
    "EXPECTED_IMPROVEMENT_CHANNEL",
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
    "HistoryDraw",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "bayesian_components",
    "bayesian_probabilistic_components",
    "calculate_bayes_window",
    "calculate_bayesian_components",
    "calculate_bayesian_parent_ranking",
    "calculate_bayesian_probabilistic_ranking",
    "calculate_bayesian_ranking",
    "calculate_bayesian_raw_scores",
    "calculate_bayesian_window_ranking",
    "calculate_bayesian_window_rankings",
    "calculate_entropy_components",
    "calculate_entropy_ranking",
    "calculate_entropy_raw",
    "calculate_entropy_raw_scores",
    "calculate_fused_bayesian_ranking",
    "calculate_fused_entropy_ranking",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_component_50",
    "entropy_components",
    "fuse_pairwise_scores",
    "produce_biglotto_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_entropy_bayesian_probabilistic_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_bayesian_numbers_by_window",
    "rank_entropy_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
