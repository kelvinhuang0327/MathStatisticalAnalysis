"""Causal deterministic BigLotto SIGNAL_FOURIER + REGIME_STATE candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_SIGNAL_FOURIER_REGIME_STATE_WEIGHTED_SCORE_300_V1``.  The exact
W=300 parent rankings are called directly and fused with one-half plus
one-half exact rank arithmetic across all 49 legal numbers.
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
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as _regime_parent,
)

_signal_fourier_parent = (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_8d97214ab08c8169"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_SIGNAL_FOURIER_REGIME_STATE_WEIGHTED_SCORE_300_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "9cd9448c22970cd04302a9cd938345761b1877a873a5dffaf147b8cc0895cb45"
)
SOURCE_UNIVERSE_ID: Final[str] = DESIGN_ID
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"

FEATURE_1: Final[str] = "SIGNAL_FOURIER"
FEATURE_2: Final[str] = "REGIME_STATE"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 300
MINIMUM_HISTORY: Final[int] = 751

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_1_IMPLEMENTATION_COMMIT: Final[str] = (
    "7845d0296a2512ec6d8bdc82d208057c06f732c7"
)
PARENT_2_IMPLEMENTATION_COMMIT: Final[str] = (
    "68fc74e3d5b1819e3a551572cc838a32f4c66b27"
)
PARENT_1_SOURCE_BLOB_ID: Final[str] = "420ac4331386f9837cd2c7abe85ee1cec93627e9"
PARENT_2_SOURCE_BLOB_ID: Final[str] = "5211bde92af9cda38c957da018e61a2fdfc72ea5"

PARENT_COMPONENT_RULE_1: Final[str] = (
    "SPECTRAL_IPR_300(n)=IF R_300(n,0)>0 THEN "
    "SUM_{l=0}^{299}(R_300(n,l)^2)/(300*R_300(n,0)^2) ELSE 0;"
    "Y_300,n(t)=1_IF_n_IN_SIX_MAIN_NUMBERS(history[t])_ELSE_0;"
    "COUNT_300(n)=SUM_t(Y_300,n(t));MEAN_300(n)=COUNT_300(n)/300;"
    "Z_300,n(t)=Y_300,n(t)-MEAN_300(n);"
    "R_300(n,l)=SUM_{t=0}^{299}(Z_300,n(t)*Z_300,n((t+l) MOD 300));"
    "l=0..299;EXACT_RATIONAL;HIGHER_IS_BETTER;"
    "RAW_TIES_PEAK_NORMALIZED_CIRCULAR_AUTOCORR_DESCENDING_NUMBER_ASCENDING;"
    "NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "REGIME_STATE_PARENT=B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1;"
    "REGIME_DETECTOR=B649_RENYI2_COLLISION_STATE_V1;"
    "NUMBER_DOMAIN=LEGAL_NUMBERS_1_TO_49;REGIME_WINDOWS=(50,300,750);"
    "COLLISION_W=SUM_n(COUNT_W(n)^2)/(6*W)^2;EXACT_RATIONAL;"
    "REFERENCE_COLLISION=(COLLISION_300+COLLISION_750)/2;"
    "CLASSIFY=COLLISION_50>REFERENCE_COLLISION=>RECENT_CONCENTRATED_LOW_RENYI2;"
    "OTHERWISE=>RECENT_DIFFUSE_HIGH_RENYI2;TIE=>RECENT_DIFFUSE_HIGH_RENYI2;"
    "LOW_SOURCE=B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1;"
    "HIGH_SOURCE=B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1;"
    "SOURCE_CANDIDATE_TICKET_COUNT=210;"
    "REGIME_SUPPORT(n)=COUNT_OF_SELECTED_SOURCE_TICKETS_CONTAINING_n;"
    "HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];SIGNAL_FOURIER_DRAWS=history[T-300:T];"
    "W=300;COUNT_ONLY_SIX_MAIN_NUMBERS;TARGET_ROW_history[T] EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];"
    "REGIME_COLLISION_DRAWS_50=history[T-50:T];"
    "REGIME_COLLISION_DRAWS_300=history[T-300:T];"
    "REGIME_COLLISION_DRAWS_750=history[T-750:T];"
    "REGIME_SOURCE_SELECTED_FROM_PRIOR_HISTORY_ONLY;TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "Build the exact SIGNAL_FOURIER spectral IPR parent for every legal number "
        "using the fixed W300 window."
    ),
    (
        "Rank the exact SIGNAL_FOURIER raw score higher-is-better with peak "
        "normalized circular autocorrelation descending and number ascending ties, "
        "then normalize one-based position p as (49-p)/48; exact rational only."
    ),
    (
        "Build the exact REGIME_STATE parent from the frozen Rényi-2 collision "
        "state and its ordered 210-ticket source universe; score each legal number "
        "by selected-source ticket support, rank higher-is-better with number "
        "ascending ties, then normalize one-based position p as (49-p)/48; exact "
        "rational only."
    ),
    "Fuse the two exact normalized all-49 components with equal 1/2 and 1/2 weights.",
    (
        "Do not use empirical min-max scaling, z-scoring, calibration, "
        "outcome-derived normalization, historical optimization, or randomness."
    ),
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_SIGNAL_FOURIER_SPECTRAL_IPR_AND_PEAK_SCORE_FOR_ALL_49_LEGAL_NUMBERS_WINDOW_300"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_INTEGER_REGIME_STATE_SELECTED_SOURCE_SUPPORT_COUNT_FOR_ALL_49_LEGAL_NUMBERS_FROM_210_TICKETS"
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*SIGNAL_FOURIER_NORMALIZED_RANK_300(n)+"
    "1/2*REGIME_STATE_NORMALIZED_SUPPORT_RANK_300(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "SIGNAL_FOURIER normalized rank descending.",
    "REGIME_STATE normalized support rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    (
        "SIGNAL_FOURIER parent raw-score tie: peak normalized circular "
        "autocorrelation descending, then number ascending."
    ),
    "REGIME_STATE parent support-count tie: number ascending after source-state selection.",
    (
        "Final pairwise tie: minimum component rank descending, SIGNAL_FOURIER "
        "rank descending, REGIME_STATE rank descending, number ascending."
    ),
)
NUMBER_TIE_BREAK_RULE: Final[tuple[str, ...]] = NUMBER_TIE_BREAK_RULE_LINES

RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49
RANKED_POOL_RULE: Final[str] = (
    "RANK_ALL_49_LEGAL_NUMBERS_BY_FINAL_PAIRWISE_SCORE;SELECT_FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS;NO_OUTCOME_OR_FUTURE_DATA"
)
CANDIDATE_CONSTRUCTION: Final[str] = "RANKED_POOL"
CANDIDATE_CONSTRUCTION_RULE: Final[str] = RANKED_POOL_RULE
TICKET_CONSTRUCTION: Final[str] = "SINGLE_TICKET"
TICKET_CONSTRUCTION_RULE: Final[str] = (
    "TAKE_FINAL_PAIRWISE_RANK_POSITIONS_1_TO_6;"
    "SORT_SELECTED_NUMBERS_ASCENDING;RETURN_ONE_NATIVE_BIGLOTTO_TICKET"
)
TICKET_SELECTION_RULE: Final[str] = "FIRST_6_FINAL_PAIRWISE_RANKED_NUMBERS"
NATIVE_TICKET_COUNT: Final[int] = 1

CAUSAL_CUTOFF_RULE: Final[str] = (
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;"
    "FUTURE_SUFFIX NEVER_USED;SIGNAL_FOURIER_DRAWS=history[T-300:T];"
    "REGIME_COLLISION_DRAWS=(history[T-50:T],history[T-300:T],history[T-750:T]);"
    "REGIME_SOURCE_SELECTED_FROM_history[:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_SINGLE_FEATURE_DEGRADATION;NO_RANDOMNESS;ALL_49_LEGAL_NUMBERS_REQUIRED;"
    "ORDERED_210_REGIME_SOURCE_REQUIRED"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_PRE_REGISTERED;"
    "SIGNAL_FOURIER_WINDOW=300;FULL_SPECTRUM_IPR;EXACT_CIRCULAR_AUTOCORRELATION;"
    "REGIME_COLLISION_WINDOWS=(50,300,750);REGIME_REFERENCE=(COLLISION_300+COLLISION_750)/2;"
    "REGIME_SOURCE_TICKET_COUNT=210;REGIME_SUPPORT_COUNT;FRONTIER_WINDOW_LABEL=300;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "PERIODICITY_SIGNAL_PLUS_RENYI2_REGIME_CONDITIONED_SUPPORT"
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate_batch_r1"
)


class InsufficientHistoryError(_regime_parent.InsufficientHistoryError):
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
    REGIME_STATE_COMPONENT: Fraction
    SIGNAL_FOURIER_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def REGIME_STATE_RANK_300(self) -> Fraction:
        return self.REGIME_STATE_COMPONENT

    @property
    def REGIME_COMPONENT(self) -> Fraction:
        return self.REGIME_STATE_COMPONENT

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

    REGIME_STATE_COMPONENTS: Components
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

    @property
    def REGIME_COMPONENTS(self) -> Components:
        return self.REGIME_STATE_COMPONENTS

    def regime_state_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.REGIME_STATE_COMPONENTS[number - 1]

    def regime_component(self, number: int) -> Fraction:
        return self.regime_state_component(number)

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


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return a validated immutable copy of only the strictly prior history."""

    _validate_target_index(target_index)
    raw_prefix = _read_history_prefix(history, target_index)
    try:
        prior_history = _regime_parent.validate_prior_history(
            raw_prefix, len(raw_prefix)
        )
    except _regime_parent.InsufficientHistoryError as error:
        raise InsufficientHistoryError(str(error)) from error
    if len(prior_history) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(prior_history)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return prior_history


validate_history = validate_prior_history


def _regime_state_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _regime_parent.RegimeState:
    return _regime_parent.calculate_regime_state(prior_history, len(prior_history))


def calculate_regime_state(
    history: HistoryInput, target_index: int
) -> _regime_parent.RegimeState:
    """Return the exact frozen Renyi-2 state from the causal prior prefix."""

    prior_history = validate_prior_history(history, target_index)
    return _regime_state_from_prior_history(prior_history)


calculate_collision_concentration = _regime_parent.calculate_collision_concentration
calculate_collision_concentrations = _regime_parent.calculate_collision_concentrations
calculate_reference_collision = _regime_parent.calculate_reference_collision
classify_regime = _regime_parent.classify_regime
selected_source_for_regime = _regime_parent.selected_source_for_regime


def _validate_regime_source(raw_source: object) -> TicketPortfolio:
    if not isinstance(raw_source, tuple):
        raise RuntimeError("regime parent must return an ordered tuple of tickets")
    source = cast(tuple[object, ...], raw_source)
    if len(source) != 210:
        raise RuntimeError("regime parent must return exactly 210 ordered tickets")
    tickets: list[Ticket] = []
    seen: set[Ticket] = set()
    for ticket_index, raw_ticket in enumerate(source):
        if not isinstance(raw_ticket, tuple):
            raise RuntimeError(f"regime source ticket {ticket_index} must be a tuple")
        numbers = cast(tuple[object, ...], raw_ticket)
        if len(numbers) != PICK_COUNT or any(type(number) is not int for number in numbers):
            raise RuntimeError(f"regime source ticket {ticket_index} must contain six integers")
        ticket = cast(Ticket, numbers)
        if (
            ticket != tuple(sorted(ticket))
            or len(set(ticket)) != PICK_COUNT
            or not all(NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1] for number in ticket)
        ):
            raise RuntimeError(f"regime source ticket {ticket_index} must be legal and unique")
        if ticket in seen:
            raise RuntimeError("regime parent returned a duplicate source ticket")
        seen.add(ticket)
        tickets.append(ticket)
    return tuple(tickets)


def _produce_regime_source_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> TicketPortfolio:
    source = _regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(
        prior_history, len(prior_history)
    )
    return _validate_regime_source(source)


def produce_regime_source_ticket_universe(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_regime_source_from_prior_history(
        validate_prior_history(history, target_index)
    )


def _regime_state_support_counts(
    source_tickets: TicketPortfolio,
) -> tuple[int, ...]:
    counts = [0] * RANKED_POOL_CARDINALITY
    for ticket in source_tickets:
        for number in ticket:
            counts[number - NUMBER_DOMAIN[0]] += 1
    return tuple(counts)


def calculate_regime_state_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    prior_history = validate_prior_history(history, target_index)
    source = _produce_regime_source_from_prior_history(prior_history)
    return tuple(
        Fraction(count, 1)
        for count in _regime_state_support_counts(source)
    )


def calculate_regime_state_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    raw = calculate_regime_state_raw_scores(history, target_index)
    return rank_regime_state_scores(raw)


def calculate_regime_state_components(
    history: HistoryInput, target_index: int
) -> Components:
    return calculate_regime_state_ranking(history, target_index).NORMALIZED_RANKS


regime_state_components = calculate_regime_state_components
regime_state_component_300 = calculate_regime_state_components


def _signal_fourier_ranking_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> _signal_fourier_parent.WindowRanking:
    ranking = _signal_fourier_parent.calculate_window_rankings(
        prior_history, len(prior_history), WINDOW
    )
    if ranking.WINDOW != WINDOW or ranking.WINDOW_DRAW_COUNT != WINDOW:
        raise RuntimeError("SIGNAL_FOURIER parent returned the wrong frozen W300 component")
    return ranking


def calculate_signal_fourier_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return exact frozen full-spectrum spectral-IPR W300 raw scores."""

    prior_history = validate_prior_history(history, target_index)
    return _signal_fourier_ranking_from_prior_history(prior_history).SPECTRAL_IPRS


def calculate_signal_fourier_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the exact frozen SIGNAL_FOURIER W300 ranking."""

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


def calculate_signal_fourier_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return exact normalized SIGNAL_FOURIER W300 ranks."""

    return calculate_signal_fourier_ranking(history, target_index).NORMALIZED_RANKS


signal_fourier_components = calculate_signal_fourier_components
signal_fourier_component_300 = calculate_signal_fourier_components
spectral_components = calculate_signal_fourier_components


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
    tertiary_values: Sequence[object] | Mapping[int, object] | None = None,
) -> ComponentRanking:
    raw_scores = _exact_values(raw_values, name)
    secondary = (
        tuple(Fraction(0, 1) for _ in range(RANKED_POOL_CARDINALITY))
        if secondary_values is None
        else _exact_values(secondary_values, f"{name}_tie_break_1")
    )
    tertiary = (
        tuple(Fraction(0, 1) for _ in range(RANKED_POOL_CARDINALITY))
        if tertiary_values is None
        else _exact_values(tertiary_values, f"{name}_tie_break_2")
    )
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -raw_scores[number - 1],
                -secondary[number - 1],
                -tertiary[number - 1],
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


def rank_regime_state_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank exact selected-source support counts higher-is-better."""

    return _rank_raw_scores(raw_scores, "regime_state_support_scores")


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


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the causal ranking from both sealed W300 parent components."""

    prior_history = validate_prior_history(history, target_index)
    signal_fourier = calculate_signal_fourier_components(
        prior_history, len(prior_history)
    )
    regime_state = calculate_regime_state_components(
        prior_history, len(prior_history)
    )
    return rank_pairwise_scores(signal_fourier, regime_state)


def _exact_normalized_components(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    components = _exact_values(values, name)
    if any(value < 0 or value > 1 for value in components):
        raise ValueError(f"{name} must lie in [0,1]")
    return components


def rank_pairwise_scores(
    signal_fourier_components: Sequence[object] | Mapping[int, object],
    regime_state_components: Sequence[object] | Mapping[int, object],
) -> PairwiseRanking:
    """Fuse two exact normalized parent vectors and rank all 49 numbers."""

    signal_fourier = _exact_normalized_components(
        signal_fourier_components, "signal_fourier_components"
    )
    regime_state = _exact_normalized_components(
        regime_state_components, "regime_state_components"
    )
    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * signal_fourier[index]
        + FUSION_WEIGHT_2 * regime_state[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -pairwise_scores[number - 1],
                -min(signal_fourier[number - 1], regime_state[number - 1]),
                -signal_fourier[number - 1],
                -regime_state[number - 1],
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
            REGIME_STATE_COMPONENT=regime_state[number - 1],
            SIGNAL_FOURIER_COMPONENT=signal_fourier[number - 1],
            PAIRWISE_SCORE=pairwise_scores[number - 1],
            MIN_COMPONENT_RANK=min(
                signal_fourier[number - 1], regime_state[number - 1]
            ),
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
        REGIME_STATE_COMPONENTS=regime_state,
        SIGNAL_FOURIER_COMPONENTS=signal_fourier,
        PAIRWISE_SCORES=pairwise_scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores
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
produce_bmsgv1_l2_pairwise_regime_state_signal_fourier_weighted_score_300_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate = (
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


_CANONICAL_SEMANTIC_OBJECT: dict[str, object] = {
    "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
    "CANDIDATE_ID": CANDIDATE_ID,
    "CANDIDATE_CONSTRUCTION_RULE": CANDIDATE_CONSTRUCTION_RULE,
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
    "IMPLEMENTATION_READY": "YES",
    "METHOD_LEVEL": METHOD_LEVEL,
    "MINIMUM_HISTORY": MINIMUM_HISTORY,
    "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
    "NUMBER_DOMAIN": "1..49",
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
    _CANONICAL_SEMANTIC_OBJECT
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
    "PARENT_1_IMPLEMENTATION_COMMIT",
    "PARENT_1_SOURCE_BLOB_ID",
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
    "RANKED_POOL_RULE",
    "RNG",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_VERSION",
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
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "calculate_regime_state_components",
    "calculate_regime_state_ranking",
    "calculate_regime_state_raw_scores",
    "calculate_signal_fourier_components",
    "calculate_signal_fourier_ranking",
    "calculate_signal_fourier_raw_scores",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "produce_biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate",
    "produce_bmsgv1_l2_pairwise_regime_state_signal_fourier_weighted_score_300_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_pairwise_scores",
    "rank_regime_state_scores",
    "rank_signal_fourier_scores",
    "regime_state_component_300",
    "regime_state_components",
    "signal_fourier_component_300",
    "signal_fourier_components",
    "signature_hash_for_semantics",
    "spectral_components",
    "validate_history",
    "validate_prior_history",
]
