"""Causal deterministic BigLotto ENTROPY + SIGNAL_FOURIER candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_ENTROPY_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1``.  The entropy
parent is reproduced from its sealed exact-rational rule.  The SIGNAL_FOURIER
parent is reused directly from the frozen spectral-IPR implementation.  Both
components rank all 49 legal numbers, and their exact one-half rank fusion
produces one sorted six-number native ticket.
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
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as _signal_fourier_parent,  # noqa: E501
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_8e17e64bb96c93de"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_ENTROPY_SIGNAL_FOURIER_WEIGHTED_SCORE_300_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "65520ea1f4ceab88c2f0cb2ef0157eddeb732cdb007b5d6c09096c1dd1a17c7b"
)

FEATURE_1: Final[str] = "ENTROPY"
FEATURE_2: Final[str] = "SIGNAL_FOURIER"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 300
MINIMUM_HISTORY: Final[int] = 751
IMPLEMENTATION_READY: Final[str] = "YES"

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"

# The second parent is reused from this exact frozen implementation surface.
PARENT_2_IMPLEMENTATION_COMMIT: Final[str] = (
    "68fc74e3d5b1819e3a551572cc838a32f4c66b27"
)
PARENT_2_SOURCE_BLOB_ID: Final[str] = "5211bde92af9cda38c957da018e61a2fdfc72ea5"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "ENTROPY_SCORE_300(n)=1/(ABS(COUNT_300(n)-1800/49)+1/10);"
    "COUNT_300(n)=SUM_{t=T-300}^{T-1}(1_IF_n_IN_SIX_MAIN_NUMBERS(history[t]));"
    "EXACT_RATIONAL;HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "Y_300,n(t)=1_IF_NUMBER_N_APPEARS_IN_SIX_MAIN_NUMBERS(history[t])_ELSE_0;"
    "COUNT_300(n)=SUM_{t=T-300}^{T-1}(Y_300,n(t));"
    "MEAN_300(n)=COUNT_300(n)/300;"
    "Z_300,n(t)=Y_300,n(t)-MEAN_300(n);"
    "R_300,n(l)=SUM_{t=0}^{299}(Z_300,n(t)*Z_300,n((t+l) MOD 300));"
    "l=0..299;EXACT_RATIONAL;"
    "SPECTRAL_IPR_300(n)=IF R_300,n(0)>0 THEN "
    "SUM_{l=0}^{299}(R_300,n(l)^2)/(300*R_300,n(0)^2) ELSE 0;"
    "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_300(n)=IF R_300,n(0)>0 THEN "
    "MAX_{l=1..150}(ABS(R_300,n(l))/R_300,n(0)) ELSE 0;"
    "HIGHER_IS_BETTER;NO_FLOATING_FFT;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "ENTROPY_DRAWS=history[T-300:T];W=300;COUNT_ONLY_SIX_MAIN_NUMBERS;"
    "TARGET_ROW_history[T] EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "SPECTRAL_DRAWS=history[T-300:T];W=300;COUNT_ONLY_SIX_MAIN_NUMBERS;"
    "TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build one complete exact raw score for every legal number 1..49 "
    "for each parent component.",
    "Rank each parent higher-is-better; exact raw-score ties use the fully "
    "specified parent tie-break rule.",
    "Normalize one-based position p as (49-p)/48; best rank is 1 and worst "
    "rank is 0; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, or "
    "outcome-derived normalization.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_NORMALIZATION: Final[str] = "EXACT_RATIONAL_RANK_NORMALIZATION"
COMPONENT_NORMALIZATION_CLASS: Final[str] = COMPONENT_NORMALIZATION
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RAW_SCORE_FOR_EVERY_LEGAL_NUMBER_1_TO_49"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RAW_SCORE_FOR_EVERY_LEGAL_NUMBER_1_TO_49"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*ENTROPY_NORMALIZED_RANK_300(n)+"
    "1/2*SIGNAL_FOURIER_NORMALIZED_RANK_300(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "ENTROPY normalized rank descending.",
    "SIGNAL_FOURIER normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "ENTROPY parent raw-score tie: number ascending.",
    "SIGNAL_FOURIER parent raw-score tie: peak normalized circular "
    "autocorrelation descending, then number ascending.",
    "Final pairwise tie: minimum component rank descending, ENTROPY rank "
    "descending, SIGNAL_FOURIER rank descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS_WITH_FUSED_PAIRWISE_SCORE;"
    "NO_INTERMEDIATE_TOP_K_POOL"
)
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_CONSTRUCTION_RULE: Final[str] = (
    "TAKE_FINAL_PAIRWISE_RANK_POSITIONS_1_TO_6;"
    "SORT_SELECTED_NUMBERS_ASCENDING;RETURN_ONE_NATIVE_BIGLOTTO_TICKET"
)
TICKET_SELECTION_RULE: Final[str] = "FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS"
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;ENTROPY_DRAWS=history[T-300:T];"
    "SIGNAL_FOURIER_DRAWS=history[T-300:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;"
    "NO_TRUNCATION;NO_SINGLE_FEATURE_DEGRADATION;NO_RANDOMNESS"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;"
    "PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "ENTROPY_WINDOW=300_PARENT_CONSTANT;ENTROPY_EXPECTED_COUNT=1800/49;"
    "ENTROPY_EPSILON=1/10_PARENT_CONSTANT;"
    "SIGNAL_FOURIER_WINDOW=300_PARENT_CONSTANT;SPECTRAL_ARITHMETIC=EXACT_RATIONAL;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "PERIODICITY_SIGNAL"
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"

FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change W=300, the 1/2 and 1/2 weights, or exact-rational arithmetic.",
    "Do not change entropy expectation 1800/49, epsilon 1/10, or spectral IPR and peak tie rules.",
    "Do not introduce min-max scaling, z-scoring, calibration, outcome tuning, "
    "or historical optimization.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not change the all-49 pool, final tie-break order, first-6 "
    "single-ticket rule, minimum history, or fallback.",
    "Do not wire this candidate into the production catalog in the implementation task.",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than 751 strictly prior draws are available."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores, ranks, and positions for one parent component."""

    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components

    def raw_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RAW_SCORES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

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
    ENTROPY_COMPONENT: Fraction
    SIGNAL_FOURIER_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def ENTROPY_RANK_300(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def SIGNAL_FOURIER_RANK_300(self) -> Fraction:
        return self.SIGNAL_FOURIER_COMPONENT

    @property
    def SPECTRAL_IPR_RANK_300(self) -> Fraction:
        return self.SIGNAL_FOURIER_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 exact fused ranks and exactly one native ticket."""

    ENTROPY_COMPONENTS: Components
    SIGNAL_FOURIER_COMPONENTS: Components
    PAIRWISE_SCORES: Components
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

    def entropy_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.ENTROPY_COMPONENTS[number - 1]

    def signal_fourier_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SIGNAL_FOURIER_COMPONENTS[number - 1]

    def spectral_component(self, number: int) -> Fraction:
        return self.signal_fourier_component(number)

    def pairwise_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAIRWISE_SCORES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def score_record(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """The selected-gap identity and sealed design signature."""

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
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError("number must be an integer in 1..49")


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    """Read exactly ``history[:target_index]`` without touching the suffix."""

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
    return cast(HistoryDraw, tuple(sorted(numbers)))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return a validated immutable copy of only the strictly prior history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _entropy_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    """Calculate the sealed exact-rational ENTROPY W=300 raw scores."""

    counts = [0] * RANKED_POOL_CARDINALITY
    for draw in prior_history[-WINDOW:]:
        for number in draw:
            counts[number - 1] += 1

    expected_count = Fraction(1800, 49)
    epsilon = Fraction(1, 10)
    return tuple(
        Fraction(1, 1)
        / (abs(Fraction(counts[number - 1], 1) - expected_count) + epsilon)
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )


def _signal_fourier_ranking_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _signal_fourier_parent.WindowRanking:
    ranking = _signal_fourier_parent.calculate_window_rankings(
        prior_history, len(prior_history), WINDOW
    )
    if ranking.WINDOW != WINDOW or ranking.WINDOW_DRAW_COUNT != WINDOW:
        raise RuntimeError("SIGNAL_FOURIER parent returned the wrong frozen W300 component")
    return ranking


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact sealed ENTROPY W=300 raw score vector for 1..49."""

    return _entropy_raw_scores_from_prior_history(
        validate_prior_history(history, target_index)
    )


def calculate_signal_fourier_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact frozen full-spectrum spectral-IPR W=300 raw scores."""

    prior_history = validate_prior_history(history, target_index)
    return _signal_fourier_ranking_from_prior_history(prior_history).SPECTRAL_IPRS


def _exact_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(range(1, 50)):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
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
    raw_values: Sequence[object] | Mapping[int, object],
    name: str,
    secondary_values: Sequence[object] | Mapping[int, object] | None = None,
) -> ComponentRanking:
    raw_scores = _exact_values(raw_values, name)
    secondary = (
        tuple(Fraction(0, 1) for _ in range(RANKED_POOL_CARDINALITY))
        if secondary_values is None
        else _exact_values(secondary_values, f"{name}_tie_break")
    )
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -raw_scores[number - 1],
                -secondary[number - 1],
                number,
            ),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized_ranks = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)
    return ComponentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank a complete exact ENTROPY raw score vector."""

    return _rank_raw_scores(raw_scores, "entropy_raw_scores")


def rank_signal_fourier_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
    peak_normalized_circular_autocorrelations: Sequence[object]
    | Mapping[int, object]
    | None = None,
) -> ComponentRanking:
    """Rank spectral-IPR raw scores with the frozen peak tie-break."""

    return _rank_raw_scores(
        raw_scores,
        "signal_fourier_raw_scores",
        peak_normalized_circular_autocorrelations,
    )


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the exact normalized ENTROPY W=300 ranking."""

    return rank_entropy_scores(calculate_entropy_raw_scores(history, target_index))


def calculate_signal_fourier_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the exact normalized SIGNAL_FOURIER W=300 ranking."""

    parent_ranking = _signal_fourier_ranking_from_prior_history(
        validate_prior_history(history, target_index)
    )
    ranking = rank_signal_fourier_scores(
        parent_ranking.SPECTRAL_IPRS,
        parent_ranking.PEAK_NORMALIZED_CIRCULAR_AUTOCORRS,
    )
    if (
        ranking.ORDERED_NUMBERS != parent_ranking.ORDERED_NUMBERS
        or ranking.NORMALIZED_RANKS != parent_ranking.NORMALIZED_RANKS
    ):
        raise RuntimeError("SIGNAL_FOURIER parent ranking parity failed")
    return ranking


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return exact normalized ENTROPY W=300 ranks."""

    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


def calculate_signal_fourier_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return exact normalized SIGNAL_FOURIER W=300 ranks."""

    return calculate_signal_fourier_ranking(history, target_index).NORMALIZED_RANKS


entropy_components = calculate_entropy_components
entropy_component_300 = calculate_entropy_components
signal_fourier_components = calculate_signal_fourier_components
signal_fourier_component_300 = calculate_signal_fourier_components
spectral_components = calculate_signal_fourier_components


def _exact_normalized_components(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    components = _exact_values(values, name)
    if any(value < 0 or value > 1 for value in components):
        raise ValueError(f"{name} must lie in [0,1]")
    return components


def rank_pairwise_scores(
    entropy_components: Sequence[object] | Mapping[int, object],
    signal_fourier_components: Sequence[object] | Mapping[int, object],
) -> PairwiseRanking:
    """Fuse two exact normalized parent vectors and rank all 49 numbers."""

    entropy = _exact_normalized_components(entropy_components, "entropy_components")
    signal_fourier = _exact_normalized_components(
        signal_fourier_components, "signal_fourier_components"
    )
    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * entropy[index]
        + FUSION_WEIGHT_2 * signal_fourier[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -pairwise_scores[number - 1],
                -min(entropy[number - 1], signal_fourier[number - 1]),
                -entropy[number - 1],
                -signal_fourier[number - 1],
                number,
            ),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ranked_numbers, start=1):
        positions[number - 1] = position

    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            ENTROPY_COMPONENT=entropy[number - 1],
            SIGNAL_FOURIER_COMPONENT=signal_fourier[number - 1],
            PAIRWISE_SCORE=pairwise_scores[number - 1],
            MIN_COMPONENT_RANK=min(entropy[number - 1], signal_fourier[number - 1]),
            POSITION=positions[number - 1],
        )
        for number in ranked_numbers
    )
    ticket = cast(Ticket, tuple(sorted(ranked_numbers[:PICK_COUNT])))
    if (
        len(ticket) != PICK_COUNT
        or len(set(ticket)) != PICK_COUNT
        or not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket)
    ):
        raise RuntimeError("pairwise native ticket must contain six legal unique numbers")
    return PairwiseRanking(
        ENTROPY_COMPONENTS=entropy,
        SIGNAL_FOURIER_COMPONENTS=signal_fourier,
        PAIRWISE_SCORES=pairwise_scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the causal ranking from both sealed W300 parent components."""

    prior_history = validate_prior_history(history, target_index)
    entropy = calculate_entropy_components(prior_history, len(prior_history))
    signal_fourier = calculate_signal_fourier_components(
        prior_history, len(prior_history)
    )
    return rank_pairwise_scores(entropy, signal_fourier)


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the one sorted ticket from final pairwise positions 1..6."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate = (
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


_DESIGN_SIGNATURE_OBJECT: dict[str, object] = {
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
    "LOTTERY_TYPE": LOTTERY_TYPE,
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
    _DESIGN_SIGNATURE_OBJECT
)
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS
if signature_hash_for_semantics(CANDIDATE_SEMANTICS) != DESIGN_SIGNATURE_SHA256:
    raise RuntimeError("sealed candidate semantic signature mismatch")

CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = (
    MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
)
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS
CANDIDATE_METADATA: Final[CandidateMetadata] = CandidateMetadata(
    CANDIDATE_ID=CANDIDATE_ID,
    SELECTED_GAP_ID=SELECTED_GAP_ID,
    DESIGN_ID=DESIGN_ID,
    DESIGN_SIGNATURE_SHA256=DESIGN_SIGNATURE_SHA256,
    FEATURE_1=FEATURE_1,
    FEATURE_2=FEATURE_2,
    WINDOW=WINDOW,
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
    "COMPONENT_NORMALIZATION",
    "COMPONENT_NORMALIZATION_CLASS",
    "COMPONENT_NORMALIZATION_RULE",
    "COMPONENT_NORMALIZATION_RULE_LINES",
    "COMPONENT_SCORE_DOMAIN_1",
    "COMPONENT_SCORE_DOMAIN_2",
    "DESIGN_ID",
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
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_READY",
    "IMPLEMENTATION_SYMBOL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "OUTPUT_SHAPE",
    "PAIRWISE_SCORE_RULE",
    "PARAMETER_SELECTION_RULE",
    "PARENT_2_IMPLEMENTATION_COMMIT",
    "PARENT_2_SOURCE_BLOB_ID",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_SOURCE_UNIVERSE_VERSION_1",
    "PARENT_SOURCE_UNIVERSE_VERSION_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "PICK_COUNT",
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
    "calculate_entropy_components",
    "calculate_entropy_ranking",
    "calculate_entropy_raw_scores",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "calculate_signal_fourier_components",
    "calculate_signal_fourier_ranking",
    "calculate_signal_fourier_raw_scores",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_component_300",
    "entropy_components",
    "fuse_pairwise_scores",
    "produce_biglotto_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate",
    "produce_bmsgv1_l2_pairwise_entropy_signal_fourier_weighted_score_300_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_entropy_scores",
    "rank_pairwise_scores",
    "rank_signal_fourier_scores",
    "signal_fourier_component_300",
    "signal_fourier_components",
    "signature_hash_for_semantics",
    "spectral_components",
    "validate_history",
    "validate_prior_history",
]
