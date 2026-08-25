"""Causal deterministic BigLotto REGIME_STATE + CONSTRAINT candidate.

This research-only module implements the one candidate sealed by
``B649_PAIRWISE_REGIME_STATE_CONSTRAINT_WEIGHTED_SCORE_30_V1``.  The regime
component reuses the frozen B649 Rényi-2 source-universe producer.  The
structural constraint component is reproduced locally because the base
repository does not expose a callable with the sealed constraint-parent
identity.  The local reproduction is intentionally limited to the exact
predicate and 30-draw support count in the sealed authority.

The implementation reads only the strictly prior history prefix, uses exact
integer and rational arithmetic, has no RNG or I/O, and is not registered in
the production catalog.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, pairwise
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as _regime_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_5f0c6fb3405f7f78"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_REGIME_STATE_CONSTRAINT_WEIGHTED_SCORE_30_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "e2743bc90e913fae93ab940156b428a16b53f580f7737b7bbce47814e7853832"
)

FEATURE_1: Final[str] = "REGIME_STATE"
FEATURE_2: Final[str] = "CONSTRAINT"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
NUMBER_DOMAIN_TEXT: Final[str] = "LEGAL_NUMBERS_1_TO_49"
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 30
MINIMUM_HISTORY: Final[int] = 751
RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_CARDINALITY: Final[int] = 49

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_RENYI2_REGIME_SWITCHED_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = (
    "B649_STRUCTURAL_CONSTRAINT_SUPPORT_RANKED_POOL_30_V1"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "USE_B649_RENYI2_COLLISION_STATE_V1;COLLISION_W=SUM_n(COUNT_W(n)^2)/(6*W)^2 "
    "for W in {50,300,750};EXACT_RATIONAL;REFERENCE_COLLISION="
    "(COLLISION_300+COLLISION_750)/2;COLLISION_50>REFERENCE_COLLISION=>"
    "RECENT_CONCENTRATED_LOW_RENYI2;OTHERWISE=>RECENT_DIFFUSE_HIGH_RENYI2;LOW=>"
    "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1;HIGH=>"
    "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1;REGIME_SUPPORT_751(n)="
    "COUNT_OF_SELECTED_SOURCE_UNIVERSE_TICKETS_CONTAINING_n_OVER_EXACTLY_210_"
    "ORDERED_TICKETS;HIGHER_IS_BETTER;RAW_TIES_NUMBER_ASCENDING;NO_TARGET_OR_"
    "FUTURE_ROWS"
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "CONSTRAINT_PREDICATE(ticket)=ODD_COUNT_2_TO_4;ZONES_COVERED_AT_LEAST_3_FOR_"
    "ZONES=(1..10),(11..20),(21..30),(31..40),(41..49);SUM_120_TO_180;"
    "MAX_CONSECUTIVE_RUN_AT_MOST_2;DISTINCT_LAST_DIGITS_AT_LEAST_4;"
    "CONSTRAINT_SUPPORT_30(n)=SUM_{t=T-30}^{T-1}(1_IF_n_IN_history[t] AND "
    "CONSTRAINT_PREDICATE(history[t]));EXACT_INTEGER;HIGHER_IS_BETTER;RAW_TIES_"
    "NUMBER_ASCENDING;NO_TARGET_OR_FUTURE_ROWS"
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];RENYI2_COLLISION_WINDOWS="
    "(50,300,750);SELECTED_B649_RENYI2_SOURCE_CONSUMES_ONLY_PRIOR_PREFIX;"
    "TARGET_ROW_history[T] EXCLUDED"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "TARGET_INDEX=T;PRIOR_HISTORY=history[:T];CONSTRAINT_SUPPORT_DRAWS="
    "history[T-30:T];W=30;TARGET_ROW_history[T] EXCLUDED"
)

COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Compute the exact REGIME_STATE number support score for every legal number "
    "from the selected B649_RENYI2 source universe.",
    "Compute the exact CONSTRAINT valid-draw support count for every legal number "
    "over the prior 30 draws.",
    "Rank both component scores over all 49 legal numbers after applying their "
    "fixed number-ascending raw-score tie rules.",
    "Normalize one-based position p as (49-p)/48; best rank is 1 and worst rank "
    "is 0; exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, outcome-derived "
    "normalization, or historical optimization.",
)
COMPONENT_NORMALIZATION_RULE: Final[tuple[str, ...]] = COMPONENT_NORMALIZATION_RULE_LINES
COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_REGIME_STATE_SUPPORT_COUNT_FROM_SELECTED_B649_RENYI2_SOURCE_UNIVERSE_210_"
    "TICKETS_FOR_EACH_OF_49_LEGAL_NUMBERS"
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
    "PAIRWISE_SCORE(n)=1/2*REGIME_STATE_NORMALIZED_RANK_49(n)+1/2*"
    "CONSTRAINT_NORMALIZED_RANK_49(n);EXACT_RATIONAL"
)

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "REGIME_STATE normalized rank descending.",
    "CONSTRAINT normalized rank descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[tuple[str, ...]] = NUMBER_RANKING_RULE_LINES
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "REGIME_STATE parent support-count tie: number ascending.",
    "CONSTRAINT valid-draw support-count tie: number ascending.",
    "Final pairwise tie: minimum component rank descending, REGIME_STATE rank "
    "descending, CONSTRAINT rank descending, number ascending.",
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
    "USE_ONLY_HISTORY_PREFIX_history[:T];TARGET_ROW_history[T] NEVER_USED;FUTURE_"
    "SUFFIX NEVER_USED;REGIME_COLLISION_WINDOWS=(50,300,750);CONSTRAINT_SUPPORT_"
    "DRAWS=history[T-30:T];ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_751=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;NO_TRUNCATION;"
    "NO_PARENT_DEGRADATION;NO_RANDOMNESS;NO_VALID_CONSTRAINT_TICKET=>RAISE_"
    "EXPLICIT_CONSTRAINT_SEARCH_EXHAUSTED"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;PAIRWISE_WINDOW=30;REGIME_STATE_PARENT_WINDOWS=50,300,750;"
    "CONSTRAINT_SUPPORT_WINDOW=30;ODD_COUNT=2..4;ZONES_COVERED_AT_LEAST_3;SUM="
    "120..180;MAX_CONSECUTIVE_RUN=2;DISTINCT_TAIL_DIGITS_AT_LEAST_4;NO_TARGET_"
    "ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "REGIME_CONDITIONING_SIGNAL_PLUS_STRUCTURAL_CONSTRAINT_COMPATIBILITY"
)
FORBIDDEN_SEMANTIC_CHANGES: Final[tuple[str, ...]] = (
    "Do not substitute either parent source identity.",
    "Do not change the B649_RENYI2 collision windows (50, 300, 750), the W=30 "
    "constraint-support window, the 1/2 and 1/2 weights, or exact-rational "
    "arithmetic.",
    "Do not change the B649_RENYI2 collision formula, reference collision mean, "
    "strict greater-than regime rule, equality diffuse tie rule, or selected "
    "source identities.",
    "Do not change the structural constraint predicate: odd count 2..4, at least "
    "3 zones, sum 120..180, maximum consecutive run 2, and at least 4 distinct "
    "tail digits.",
    "Do not change the 49-number ranked domain, the (49-p)/48 normalization, final "
    "tie-break order, lexicographic first-admissible constraint search, single-"
    "ticket rule, minimum history, or fallback.",
    "Do not introduce empirical min-max scaling, z-scoring, calibration, outcome "
    "tuning, historical optimization, or randomness.",
    "Do not read target-row outcomes or any future suffix.",
    "Do not wire this candidate into the production catalog in the implementation "
    "task.",
)

IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1"
)

_LEGAL_NUMBERS: Final[tuple[int, ...]] = tuple(
    range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
)
_CONSTRAINT_ZONES: Final[tuple[tuple[int, int], ...]] = (
    (1, 10),
    (11, 20),
    (21, 30),
    (31, 40),
    (41, 49),
)
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
REGIME_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
REGIME_DETECTOR_ID: Final[str] = "B649_RENYI2_COLLISION_STATE_V1"
RECENT_CONCENTRATED_LOW_RENYI2: Final[str] = "RECENT_CONCENTRATED_LOW_RENYI2"
RECENT_DIFFUSE_HIGH_RENYI2: Final[str] = "RECENT_DIFFUSE_HIGH_RENYI2"

InsufficientHistoryError = _regime_parent.InsufficientHistoryError


class ConstraintSearchExhaustedError(ValueError):
    """Raised when no ranked six-number combination satisfies the predicate."""


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact support counts, positions, and normalized ranks for all 49 numbers."""

    RAW_SCORES: tuple[int, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]

    def raw_score(self, number: int) -> int:
        _validate_number(number)
        return self.RAW_SCORES[number - 1]

    def score(self, number: int) -> int:
        return self.raw_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    @property
    def SCORES(self) -> tuple[int, ...]:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score for one legal number."""

    NUMBER: int
    REGIME_STATE_COMPONENT: Fraction
    CONSTRAINT_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    POSITION: int

    @property
    def REGIME_STATE_RANK_49(self) -> Fraction:
        return self.REGIME_STATE_COMPONENT

    @property
    def CONSTRAINT_RANK_49(self) -> Fraction:
        return self.CONSTRAINT_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 final ranks plus exactly one constraint-admissible ticket."""

    REGIME_STATE_RANKING: ComponentRanking
    CONSTRAINT_RANKING: ComponentRanking
    REGIME_STATE_COMPONENTS: tuple[Fraction, ...]
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
    """Read only the causal prefix and do not inspect the suffix."""

    _validate_target_index(target_index)
    if isinstance(history, Sequence):
        if target_index > len(history):
            raise ValueError("target_index must not exceed history length")
        return tuple(history[:target_index])

    try:
        iterator = iter(history)
    except TypeError as error:
        raise ValueError("history must be a finite chronological sequence of draws") from error
    prefix: list[object] = []
    for _ in range(target_index):
        try:
            prefix.append(next(iterator))
        except StopIteration as error:
            raise ValueError("target_index must not exceed history length") from error
    return tuple(prefix)


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly {PICK_COUNT} integers"
        ) from error
    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers")

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
    """Validate and return exactly the strictly prior history prefix."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def calculate_regime_state(history: HistoryInput, target_index: int) -> _regime_parent.RegimeState:
    """Reuse the sealed B649 Rényi-2 regime-state parent exactly."""

    return _regime_parent.calculate_regime_state(history, target_index)


calculate_collision_concentration = _regime_parent.calculate_collision_concentration
calculate_collision_concentrations = _regime_parent.calculate_collision_concentrations
calculate_reference_collision = _regime_parent.calculate_reference_collision
classify_regime = _regime_parent.classify_regime
selected_source_for_regime = _regime_parent.selected_source_for_regime


def _produce_regime_source_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> TicketPortfolio:
    source = _regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(
        prior_history, len(prior_history)
    )
    if len(source) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError(
            "B649 Rényi-2 parent must return exactly 210 ordered source tickets"
        )
    return cast(TicketPortfolio, source)


def produce_regime_source_ticket_universe(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return the exact 210-ticket source selected by the regime parent."""

    return _produce_regime_source_from_prior_history(validate_prior_history(history, target_index))


def _support_counts_from_source(source_tickets: TicketPortfolio) -> tuple[int, ...]:
    counts = [0] * RANKED_POOL_CARDINALITY
    for ticket in source_tickets:
        for number in ticket:
            counts[number - NUMBER_DOMAIN[0]] += 1
    return tuple(counts)


def calculate_regime_state_support_scores(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Count each number's membership in the selected ordered 210-ticket source."""

    prior_history = validate_prior_history(history, target_index)
    return _support_counts_from_source(_produce_regime_source_from_prior_history(prior_history))


def constraint_predicate(ticket: Sequence[int]) -> bool:
    """Apply the frozen structural constraint predicate without randomness."""

    numbers = tuple(ticket)
    if len(numbers) != PICK_COUNT:
        return False
    if any(
        type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
        for number in numbers
    ):
        return False
    if len(set(numbers)) != PICK_COUNT:
        return False

    odd_count = sum(number % 2 == 1 for number in numbers)
    if not 2 <= odd_count <= 4:
        return False

    covered_zones = {
        zone_index
        for number in numbers
        for zone_index, (low, high) in enumerate(_CONSTRAINT_ZONES)
        if low <= number <= high
    }
    if len(covered_zones) < 3:
        return False

    if not 120 <= sum(numbers) <= 180:
        return False

    ordered = sorted(numbers)
    longest_run = 1
    current_run = 1
    for previous, current in pairwise(ordered):
        if current == previous + 1:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    if longest_run > 2:
        return False

    return len({number % 10 for number in numbers}) >= 4


def _constraint_support_counts_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> tuple[int, ...]:
    support_draws = prior_history[-WINDOW:]
    if len(support_draws) != WINDOW:
        raise InsufficientHistoryError(
            f"constraint support requires exactly {WINDOW} prior draws"
        )

    counts = [0] * RANKED_POOL_CARDINALITY
    for draw in support_draws:
        if constraint_predicate(draw):
            for number in draw:
                counts[number - NUMBER_DOMAIN[0]] += 1
    return tuple(counts)


def calculate_constraint_support_scores(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Count valid-draw support for each number over history[T-30:T]."""

    return _constraint_support_counts_from_prior_history(
        validate_prior_history(history, target_index)
    )


def _integer_scores(
    raw_scores: Sequence[object] | Mapping[int, object], name: str
) -> tuple[int, ...]:
    if isinstance(raw_scores, Mapping):
        keys = tuple(raw_scores)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(_LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        values = tuple(raw_scores[number] for number in _LEGAL_NUMBERS)
    else:
        values = tuple(raw_scores)
        if len(values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 values")

    converted: list[int] = []
    for index, value in enumerate(values, start=1):
        if type(value) is not int or value < 0:
            raise TypeError(f"{name}[{index}] must be a non-negative integer")
        converted.append(value)
    return tuple(converted)


def rank_component_scores(
    raw_scores: Sequence[object] | Mapping[int, object], name: str = "component_scores"
) -> ComponentRanking:
    """Rank one exact integer component across all 49 numbers."""

    scores = _integer_scores(raw_scores, name)
    ordered = tuple(sorted(_LEGAL_NUMBERS, key=lambda number: (-scores[number - 1], number)))
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


def rank_regime_state_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    return rank_component_scores(raw_scores, "regime_state_support_scores")


def rank_constraint_support_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    return rank_component_scores(raw_scores, "constraint_support_scores")


def _normalized_components(
    components: Sequence[object] | Mapping[int, object], name: str
) -> tuple[Fraction, ...]:
    if isinstance(components, Mapping):
        keys = tuple(components)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(_LEGAL_NUMBERS):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        values = tuple(components[number] for number in _LEGAL_NUMBERS)
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
    if len(ranking) != RANKED_POOL_CARDINALITY or set(ranking) != set(_LEGAL_NUMBERS):
        raise ValueError("ranked_numbers must be a permutation of legal numbers 1..49")

    for candidate in combinations(ranking, PICK_COUNT):
        if predicate(candidate):
            ticket = cast(Ticket, tuple(sorted(candidate)))
            return ticket
    raise ConstraintSearchExhaustedError(
        "no six-number combination in the final ranking satisfies the frozen constraint"
    )


def rank_pairwise_scores(
    regime_state_components: Sequence[object] | Mapping[int, object],
    constraint_components: Sequence[object] | Mapping[int, object],
    *,
    source_tickets: TicketPortfolio = (),
) -> PairwiseRanking:
    """Fuse two exact normalized 49-number components and select one ticket."""

    regime = _normalized_components(regime_state_components, "regime_state_components")
    constraint = _normalized_components(constraint_components, "constraint_components")
    pairwise = tuple(
        FUSION_WEIGHT_1 * regime[index] + FUSION_WEIGHT_2 * constraint[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked = tuple(
        sorted(
            _LEGAL_NUMBERS,
            key=lambda number: (
                -pairwise[number - 1],
                -min(regime[number - 1], constraint[number - 1]),
                -regime[number - 1],
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
            REGIME_STATE_COMPONENT=regime[number - 1],
            CONSTRAINT_COMPONENT=constraint[number - 1],
            PAIRWISE_SCORE=pairwise[number - 1],
            MIN_COMPONENT_RANK=min(regime[number - 1], constraint[number - 1]),
            POSITION=positions[number - 1],
        )
        for number in ranked
    )
    ticket = select_first_admissible_ticket(ranked)
    return PairwiseRanking(
        REGIME_STATE_RANKING=_ranking_from_normalized_components(regime),
        CONSTRAINT_RANKING=_ranking_from_normalized_components(constraint),
        REGIME_STATE_COMPONENTS=regime,
        CONSTRAINT_COMPONENTS=constraint,
        PAIRWISE_SCORES=pairwise,
        RANKED_NUMBERS=ranked,
        POSITIONS=tuple(positions),
        SCORES=records,
        SOURCE_TICKETS=tuple(source_tickets),
        NATIVE_TICKET=ticket,
    )


def _ranking_from_normalized_components(
    components: tuple[Fraction, ...],
) -> ComponentRanking:
    """Create a view ranking for already normalized synthetic fusion inputs."""

    ordered = tuple(sorted(_LEGAL_NUMBERS, key=lambda number: (-components[number - 1], number)))
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered, start=1):
        positions[number - 1] = position
        normalized[number - 1] = components[number - 1]
    return ComponentRanking(
        RAW_SCORES=tuple(0 for _ in _LEGAL_NUMBERS),
        ORDERED_NUMBERS=ordered,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized),
    )


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the final causal ranking from both frozen parent mechanisms."""

    prior_history = validate_prior_history(history, target_index)
    source_tickets = _produce_regime_source_from_prior_history(prior_history)
    regime_raw = _support_counts_from_source(source_tickets)
    constraint_raw = _constraint_support_counts_from_prior_history(prior_history)
    regime_ranking = rank_regime_state_scores(regime_raw)
    constraint_ranking = rank_constraint_support_scores(constraint_raw)
    ranking = rank_pairwise_scores(
        regime_ranking.NORMALIZED_RANKS,
        constraint_ranking.NORMALIZED_RANKS,
        source_tickets=source_tickets,
    )
    return PairwiseRanking(
        REGIME_STATE_RANKING=regime_ranking,
        CONSTRAINT_RANKING=constraint_ranking,
        REGIME_STATE_COMPONENTS=ranking.REGIME_STATE_COMPONENTS,
        CONSTRAINT_COMPONENTS=ranking.CONSTRAINT_COMPONENTS,
        PAIRWISE_SCORES=ranking.PAIRWISE_SCORES,
        RANKED_NUMBERS=ranking.RANKED_NUMBERS,
        POSITIONS=ranking.POSITIONS,
        SCORES=ranking.SCORES,
        SOURCE_TICKETS=source_tickets,
        NATIVE_TICKET=ranking.NATIVE_TICKET,
    )


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the sorted first admissible ticket from the fused ranking."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_bmsgv1_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate = (
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
    "LOTTERY_TYPE",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_DOMAIN_TEXT",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
    "PARENT_WINDOW_RULE_1",
    "PARENT_WINDOW_RULE_2",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RECENT_CONCENTRATED_LOW_RENYI2",
    "RECENT_DIFFUSE_HIGH_RENYI2",
    "REGIME_DETECTOR_ID",
    "REGIME_WINDOWS",
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
    "calculate_collision_concentration",
    "calculate_collision_concentrations",
    "calculate_constraint_support_scores",
    "calculate_fused_number_ranking",
    "calculate_pairwise_ranking",
    "calculate_reference_collision",
    "calculate_regime_state",
    "calculate_regime_state_support_scores",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "classify_regime",
    "constraint_predicate",
    "derive_candidate_identity",
    "produce_biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate",
    "produce_bmsgv1_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_regime_source_ticket_universe",
    "produce_ticket",
    "rank_component_scores",
    "rank_constraint_support_scores",
    "rank_pairwise_scores",
    "rank_regime_state_scores",
    "select_first_admissible_ticket",
    "selected_source_for_regime",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
