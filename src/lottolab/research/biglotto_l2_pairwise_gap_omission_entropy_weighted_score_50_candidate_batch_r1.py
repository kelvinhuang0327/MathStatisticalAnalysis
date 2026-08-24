"""Causal deterministic BigLotto GAP_OMISSION + ENTROPY candidate.

This research-only module implements the one candidate frozen by
``B649_PAIRWISE_GAP_OMISSION_ENTROPY_WEIGHTED_SCORE_50_V1``.  The omission
parent is reused from its frozen multiscale source module.  The sealed
entropy definition is reproduced locally with exact rational arithmetic so
that no floating-point value can influence a rank or a ticket.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _omission,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]
type Robustness = tuple[tuple[Fraction, Fraction, Fraction], ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_2507681ad9ef073c"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_GAP_OMISSION_ENTROPY_WEIGHTED_SCORE_50_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "a39593a347a12e72939dca2e425ecfaed2bd46dc8883bbbf0530c865654839a2"
)
SOURCE_UNIVERSE_ID: Final[str] = DESIGN_ID
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"

FEATURE_1: Final[str] = "GAP_OMISSION"
FEATURE_2: Final[str] = "ENTROPY"
METHOD_LEVEL: Final[str] = "LEVEL_2_PAIRWISE"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
RANKED_POOL_CARDINALITY: Final[int] = 49
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 50
OMISSION_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
MINIMUM_HISTORY: Final[int] = 750

PARENT_SOURCE_UNIVERSE_ID_1: Final[str] = (
    "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1"
)
PARENT_SOURCE_UNIVERSE_ID_2: Final[str] = "BMSGV1_L1_FEATURE_65309ef7bca9f40e"
PARENT_SOURCE_UNIVERSE_VERSION_1: Final[str] = "v1"
PARENT_SOURCE_UNIVERSE_VERSION_2: Final[str] = "v1"
PARENT_1_IMPLEMENTATION_COMMIT: Final[str] = (
    "50e3843f10894853e95ccd1a4abd38d8691dc942"
)
PARENT_1_SOURCE_BLOB_ID: Final[str] = (
    "614aa434cea189b1cc4f58d8ad4ea106ed82e00e"
)
PARENT_2_IMPLEMENTATION_COMMIT: Final[str] = (
    "621bfac61cb8591ea5e367272a5170dce50a65a2"
)
PARENT_2_SOURCE_BLOB_ID: Final[str] = (
    "a494ac5a4cfa6e3e6f35a95f160ba3bc92897df4"
)

PARENT_COMPONENT_RULE_1: Final[str] = (
    "Use B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1. For each W in "
    "{50,300,750}, count prior-window draws containing n; compute "
    "CURRENT_GAP_W(n) as trailing prior draws since the most recent "
    "occurrence, using W if absent; compute "
    "OMISSION_PRESSURE_W(n)=CURRENT_GAP_W(n)*(OCCURRENCE_W(n)+1)/(W+1) "
    "exactly. Rank all 49 numbers by pressure descending, current gap "
    "descending, occurrence descending, number ascending; normalize position "
    "p as (49-p)/48. Define GAP_OMISSION_COMPONENT(n) as the exact mean of "
    "the three normalized ranks; on equal means use the sorted (minimum, "
    "median, maximum) normalized-rank robustness tuple descending, then "
    "number ascending."
)
PARENT_COMPONENT_RULE_2: Final[str] = (
    "Use the frozen entropy parent identity BMSGV1_L1_FEATURE_65309ef7bca9f40e. "
    "COUNT_50(n) is appearances in the six main numbers over history[T-50:T]; "
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10), exact rational and "
    "higher-is-better; raw ties use number ascending; no target or future rows."
)
PARENT_WINDOW_RULE_1: Final[str] = (
    "OMISSION_HISTORY_WINDOWS=history[T-50:T],history[T-300:T],"
    "history[T-750:T];TARGET_INDEX=T;ALL_DRAWS_STRICTLY_PRIOR;"
    "WINDOWS_ARE_EXACTLY_50_300_750;NO_TARGET_ROW_ACCESS"
)
PARENT_WINDOW_RULE_2: Final[str] = (
    "ENTROPY_HISTORY=history[T-50:T];TARGET_INDEX=T;ALL_DRAWS_STRICTLY_PRIOR;"
    "COUNT_ONLY_SIX_MAIN_NUMBERS;NO_TARGET_ROW_ACCESS"
)

COMPONENT_SCORE_DOMAIN_1: Final[str] = (
    "EXACT_RATIONAL_MULTISCALE_OMISSION_PRESSURE_MEAN_RANK_FOR_1_TO_49;"
    "RANGE_0_TO_1"
)
COMPONENT_SCORE_DOMAIN_2: Final[str] = (
    "EXACT_RATIONAL_ENTROPY_SCORE_FOR_1_TO_49;POSITIVE"
)
COMPONENT_NORMALIZATION: Final[str] = "NORMALIZED_RANK_49_V1"
COMPONENT_NORMALIZATION_CLASS: Final[str] = COMPONENT_NORMALIZATION
COMPONENT_NORMALIZATION_RULE_LINES: Final[tuple[str, ...]] = (
    "Build one complete raw or fused score for every legal number 1..49 for each parent component.",
    "Rank each component higher-is-better; exact component-score ties use the fully "
    "specified parent robustness tuple when present, then number ascending.",
    "Normalize one-based position p as (49-p)/48; best rank is 1 and worst rank is 0; "
    "exact rational only.",
    "Do not use empirical min-max scaling, z-scoring, calibration, or "
    "outcome-derived normalization.",
)
COMPONENT_NORMALIZATION_RULE: Final[str] = ";".join(
    COMPONENT_NORMALIZATION_RULE_LINES
)

FUSION: Final[str] = "WEIGHTED_SCORE"
FUSION_WEIGHT_1: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_2: Final[Fraction] = Fraction(1, 2)
FUSION_WEIGHT_1_TEXT: Final[str] = "1/2"
FUSION_WEIGHT_2_TEXT: Final[str] = "1/2"
FUSION_FORMULA: Final[str] = (
    "PAIRWISE_SCORE(n)=1/2*GAP_OMISSION_NORMALIZED_RANK_50(n)+"
    "1/2*ENTROPY_NORMALIZED_RANK_50(n);EXACT_RATIONAL"
)
PAIRWISE_SCORE_RULE: Final[str] = FUSION_FORMULA

NUMBER_RANKING_RULE_LINES: Final[tuple[str, ...]] = (
    "Fused pairwise score descending.",
    "Minimum of the two normalized component ranks descending.",
    "GAP_OMISSION normalized rank descending.",
    "ENTROPY normalized rank descending.",
    "GAP_OMISSION robustness tuple (minimum, median, maximum) descending.",
    "Number ascending.",
)
NUMBER_RANKING_RULE: Final[str] = ";".join(NUMBER_RANKING_RULE_LINES)
NUMBER_TIE_BREAK_RULE_LINES: Final[tuple[str, ...]] = (
    "Each omission-window raw-score tie: omission pressure descending, current gap "
    "descending, occurrence count descending, number ascending.",
    "Omission multiscale mean-rank tie: minimum, median, maximum normalized rank "
    "descending, then number ascending.",
    "Entropy parent raw-score tie: number ascending.",
    "Final pairwise tie: minimum component rank descending, GAP_OMISSION rank "
    "descending, ENTROPY rank descending, GAP_OMISSION robustness "
    "minimum/median/maximum descending, number ascending.",
)
NUMBER_TIE_BREAK_RULE: Final[str] = ";".join(NUMBER_TIE_BREAK_RULE_LINES)

RANKED_POOL_DOMAIN: Final[str] = "ALL_LEGAL_NUMBERS_1_TO_49"
RANKED_POOL_RULE: Final[str] = (
    "SCORE_ALL_49_LEGAL_NUMBERS;NO_INTERMEDIATE_TOP6_OR_TOP10_OR_TOP20_POOL"
)
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
    "FUTURE_SUFFIX NEVER_USED;ALL_PARENT_WINDOWS_END_AT_T"
)
FALLBACK_RULE: Final[str] = (
    "T_BELOW_750=>RAISE_EXPLICIT_INSUFFICIENT_HISTORY;NO_PADDING;"
    "NO_TRUNCATION;NO_SINGLE_FEATURE_DEGRADATION;NO_RANDOMNESS"
)
PARAMETER_SELECTION_RULE: Final[str] = (
    "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING;PAIRWISE_WEIGHTS_1_OVER_2_"
    "PRE_REGISTERED;OMISSION_WINDOWS=50,300,750_PARENT_CONSTANT;"
    "ENTROPY_WINDOW=50_PARENT_CONSTANT;ENTROPY_EPSILON=1/10_PARENT_CONSTANT;"
    "NO_TARGET_ROW_ACCESS;NO_HISTORICAL_OPTIMIZATION"
)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_OMISSION_PRESSURE_PLUS_DISTRIBUTION_BALANCE_STRUCTURE"
)
IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1"
)


# The omission parent owns the exact minimum-history exception and history
# validation semantics.  Re-exporting the class keeps the public contract
# explicit without creating a second validation path.
InsufficientHistoryError = _omission.InsufficientHistoryError


@dataclass(frozen=True, slots=True)
class ComponentRanking:
    """Exact raw scores, parent order, positions, and normalized ranks."""

    RAW_SCORES: Components
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: Components
    ROBUSTNESS: Robustness

    @property
    def SCORES(self) -> Components:
        return self.RAW_SCORES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

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

    def robustness(self, number: int) -> tuple[Fraction, Fraction, Fraction]:
        _validate_number(number)
        return self.ROBUSTNESS[number - 1]


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two normalized parent ranks."""

    NUMBER: int
    GAP_OMISSION_COMPONENT: Fraction
    ENTROPY_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    MIN_COMPONENT_RANK: Fraction
    GAP_OMISSION_ROBUSTNESS: tuple[Fraction, Fraction, Fraction]
    POSITION: int

    @property
    def GAP_OMISSION_RANK_50(self) -> Fraction:
        return self.GAP_OMISSION_COMPONENT

    @property
    def ENTROPY_RANK_50(self) -> Fraction:
        return self.ENTROPY_COMPONENT

    @property
    def SCORE(self) -> Fraction:
        return self.PAIRWISE_SCORE


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 exact fused ranks and exactly one native ticket."""

    GAP_OMISSION_COMPONENTS: Components
    ENTROPY_COMPONENTS: Components
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

    def gap_omission_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.GAP_OMISSION_COMPONENTS[number - 1]

    def omission_component(self, number: int) -> Fraction:
        return self.gap_omission_component(number)

    def entropy_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.ENTROPY_COMPONENTS[number - 1]

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


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Use the frozen omission-parent validator on only the prior prefix."""

    # The parent validator performs the exact 750-draw gate and six-number
    # validation, reading only the requested prefix.
    return _omission.validate_prior_history(history, target_index)


validate_history = validate_prior_history


def _normalized_ranks_for_order(
    ordered_numbers: Sequence[int],
) -> tuple[tuple[int, ...], Components]:
    if len(ordered_numbers) != RANKED_POOL_CARDINALITY:
        raise ValueError("ordered_numbers must contain exactly 49 numbers")
    if set(ordered_numbers) != set(range(1, 50)):
        raise ValueError("ordered_numbers must contain every legal number exactly once")
    positions = [0] * RANKED_POOL_CARDINALITY
    normalized = [Fraction(0, 1)] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized[number - 1] = Fraction(49 - position, 48)
    return tuple(positions), tuple(normalized)


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


def _repeated_robustness(values: Components) -> Robustness:
    return tuple((value, value, value) for value in values)


def _rank_raw_scores(
    values: Sequence[object] | Mapping[int, object],
    name: str,
    robustness: Robustness | None = None,
) -> ComponentRanking:
    raw_scores = _exact_values(values, name)
    if robustness is None:
        robustness = _repeated_robustness(raw_scores)
    if len(robustness) != RANKED_POOL_CARDINALITY:
        raise ValueError("robustness must contain exactly 49 values")
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -raw_scores[number - 1],
                -robustness[number - 1][0],
                -robustness[number - 1][1],
                -robustness[number - 1][2],
                number,
            ),
        )
    )
    positions, normalized = _normalized_ranks_for_order(ordered_numbers)
    return ComponentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        ROBUSTNESS=robustness,
    )


def _gap_omission_parent_ranking(
    prior_history: tuple[HistoryDraw, ...],
) -> _omission.FusedNumberRanking:
    """Call the frozen omission parent with the already validated prefix."""

    return _omission.calculate_fused_number_ranking(
        prior_history, len(prior_history)
    )


def _component_ranking_from_omission_parent(
    parent_ranking: _omission.FusedNumberRanking,
) -> ComponentRanking:
    raw_scores = tuple(parent_ranking.MEAN_RANKS)
    robustness = tuple(parent_ranking.ROBUSTNESS)
    positions, normalized = _normalized_ranks_for_order(
        parent_ranking.ORDERED_NUMBERS
    )
    return ComponentRanking(
        RAW_SCORES=raw_scores,
        ORDERED_NUMBERS=parent_ranking.ORDERED_NUMBERS,
        POSITIONS=positions,
        NORMALIZED_RANKS=normalized,
        ROBUSTNESS=robustness,
    )


def calculate_gap_omission_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the sealed multiscale omission mean-rank score vector."""

    prior_history = validate_prior_history(history, target_index)
    return _component_ranking_from_omission_parent(
        _gap_omission_parent_ranking(prior_history)
    ).RAW_SCORES


def calculate_gap_omission_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    """Return the parent-exact omission order and rank-normalized vector."""

    prior_history = validate_prior_history(history, target_index)
    return _component_ranking_from_omission_parent(
        _gap_omission_parent_ranking(prior_history)
    )


def calculate_gap_omission_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized GAP_OMISSION parent ranks."""

    return calculate_gap_omission_ranking(history, target_index).NORMALIZED_RANKS


calculate_omission_raw_scores = calculate_gap_omission_raw_scores
calculate_omission_ranking = calculate_gap_omission_ranking
calculate_gap_omission_component_50 = calculate_gap_omission_components
gap_omission_components = calculate_gap_omission_components


ENTROPY_EXPECTED_COUNT: Final[Fraction] = Fraction(300, 49)
ENTROPY_EPSILON: Final[Fraction] = Fraction(1, 10)
ENTROPY_SCORE_RULE: Final[str] = (
    "ENTROPY_SCORE_50(n)=1/(abs(COUNT_50(n)-300/49)+1/10);"
    "COUNT_50=appearances_in_six_main_numbers_of_history[T-50:T];"
    "EXACT_RATIONAL;HIGHER_IS_BETTER"
)


def _entropy_raw_scores_from_prior_history(
    prior_history: tuple[HistoryDraw, ...],
) -> Components:
    counts = [0] * RANKED_POOL_CARDINALITY
    for draw in prior_history[-WINDOW:]:
        for number in draw:
            counts[number - 1] += 1
    return tuple(
        Fraction(1, 1)
        / (
            abs(Fraction(counts[number - 1], 1) - ENTROPY_EXPECTED_COUNT)
            + ENTROPY_EPSILON
        )
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )


def calculate_entropy_raw_scores(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the sealed exact-rational W50 entropy-parent scores."""

    prior_history = validate_prior_history(history, target_index)
    return _entropy_raw_scores_from_prior_history(prior_history)


def rank_entropy_scores(
    raw_scores: Sequence[object] | Mapping[int, object],
) -> ComponentRanking:
    """Rank all entropy scores with the frozen number-ascending tie break."""

    return _rank_raw_scores(raw_scores, "entropy_raw_scores")


def calculate_entropy_ranking(
    history: HistoryInput, target_index: int
) -> ComponentRanking:
    return rank_entropy_scores(calculate_entropy_raw_scores(history, target_index))


def calculate_entropy_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return the exact normalized ENTROPY W50 ranks."""

    return calculate_entropy_ranking(history, target_index).NORMALIZED_RANKS


entropy_components = calculate_entropy_components
entropy_component_50 = calculate_entropy_components


def _exact_normalized_components(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    components = _exact_values(values, name)
    if any(value < 0 or value > 1 for value in components):
        raise ValueError(f"{name} must lie in [0,1]")
    return components


def _exact_robustness(
    values: Sequence[object] | Mapping[int, object],
) -> Robustness:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(range(1, 50)):
            raise ValueError("gap_omission_robustness mapping must contain keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
    else:
        raw_values = tuple(values)
    if len(raw_values) != RANKED_POOL_CARDINALITY:
        raise ValueError("gap_omission_robustness must contain exactly 49 values")

    result: list[tuple[Fraction, Fraction, Fraction]] = []
    for index, value in enumerate(raw_values, start=1):
        try:
            parts = tuple(cast(Iterable[object], value))
        except TypeError as error:
            raise TypeError(f"gap_omission_robustness[{index}] must be a triple") from error
        if len(parts) != 3:
            raise ValueError(f"gap_omission_robustness[{index}] must be a triple")
        exact_parts: list[Fraction] = []
        for part_index, part in enumerate(parts, start=1):
            if isinstance(part, Fraction):
                exact_parts.append(part)
            elif type(part) is int:
                exact_parts.append(Fraction(part, 1))
            else:
                raise TypeError(
                    f"gap_omission_robustness[{index}][{part_index}] must use "
                    "exact Fraction or integer arithmetic"
                )
        exact = tuple(exact_parts)
        if any(item < 0 or item > 1 for item in exact):
            raise ValueError(
                f"gap_omission_robustness[{index}] must contain values in [0,1]"
            )
        result.append(cast(tuple[Fraction, Fraction, Fraction], exact))
    return tuple(result)


def rank_pairwise_scores(
    gap_omission_components: Sequence[object] | Mapping[int, object],
    entropy_components: Sequence[object] | Mapping[int, object],
    gap_omission_robustness: Sequence[object] | Mapping[int, object] | None = None,
) -> PairwiseRanking:
    """Fuse two exact normalized parent vectors and rank all 49 numbers."""

    gap = _exact_normalized_components(
        gap_omission_components, "gap_omission_components"
    )
    entropy = _exact_normalized_components(entropy_components, "entropy_components")
    if gap_omission_robustness is None:
        robustness = _repeated_robustness(gap)
    else:
        robustness = _exact_robustness(gap_omission_robustness)

    pairwise_scores = tuple(
        FUSION_WEIGHT_1 * gap[index] + FUSION_WEIGHT_2 * entropy[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -pairwise_scores[number - 1],
                -min(gap[number - 1], entropy[number - 1]),
                -gap[number - 1],
                -entropy[number - 1],
                -robustness[number - 1][0],
                -robustness[number - 1][1],
                -robustness[number - 1][2],
                number,
            ),
        )
    )
    positions, _normalized = _normalized_ranks_for_order(ranked_numbers)
    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            GAP_OMISSION_COMPONENT=gap[number - 1],
            ENTROPY_COMPONENT=entropy[number - 1],
            PAIRWISE_SCORE=pairwise_scores[number - 1],
            MIN_COMPONENT_RANK=min(gap[number - 1], entropy[number - 1]),
            GAP_OMISSION_ROBUSTNESS=robustness[number - 1],
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
        GAP_OMISSION_COMPONENTS=gap,
        ENTROPY_COMPONENTS=entropy,
        PAIRWISE_SCORES=pairwise_scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=positions,
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(
    history: HistoryInput, target_index: int
) -> PairwiseRanking:
    """Calculate the causal fused ranking from both sealed parent components."""

    prior_history = validate_prior_history(history, target_index)
    gap = calculate_gap_omission_components(prior_history, len(prior_history))
    entropy = calculate_entropy_components(prior_history, len(prior_history))
    robustness = calculate_gap_omission_ranking(
        prior_history, len(prior_history)
    ).ROBUSTNESS
    return rank_pairwise_scores(gap, entropy, robustness)


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
produce_bmsgv1_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1 = (
    produce_candidate_portfolio
)
produce_biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate = (
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


def _semantic_record() -> dict[str, object]:
    return {
        "AUTHORITY_TYPE": "PREDICTION_PRODUCING_V1_DESIGN_AUTHORITY",
        "CANDIDATE_CONSTRUCTION": CANDIDATE_CONSTRUCTION,
        "CANDIDATE_CONSTRUCTION_RULE": CANDIDATE_CONSTRUCTION_RULE,
        "CANDIDATE_ID": CANDIDATE_ID,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COMPONENT_NORMALIZATION": COMPONENT_NORMALIZATION,
        "COMPONENT_NORMALIZATION_CLASS": COMPONENT_NORMALIZATION_CLASS,
        "COMPONENT_NORMALIZATION_RULE": COMPONENT_NORMALIZATION_RULE_LINES,
        "COMPONENT_SCORE_DOMAIN_1": COMPONENT_SCORE_DOMAIN_1,
        "COMPONENT_SCORE_DOMAIN_2": COMPONENT_SCORE_DOMAIN_2,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "ENTROPY_EXPECTED_COUNT": "300/49",
        "ENTROPY_EPSILON": "1/10",
        "ENTROPY_SCORE_RULE": ENTROPY_SCORE_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FALLBACK_RULE": FALLBACK_RULE,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "FUSION": FUSION,
        "FUSION_FORMULA": FUSION_FORMULA,
        "FUSION_WEIGHT_1": FUSION_WEIGHT_1_TEXT,
        "FUSION_WEIGHT_2": FUSION_WEIGHT_2_TEXT,
        "HISTORY_ORDER": HISTORY_ORDER,
        "IMPLEMENTATION_MODULE": IMPLEMENTATION_MODULE,
        "IMPLEMENTATION_READY": "YES",
        "IMPLEMENTATION_SYMBOL": IMPLEMENTATION_SYMBOL,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_LEVEL": METHOD_LEVEL,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
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
        "RANKED_POOL_RULE": RANKED_POOL_RULE,
        "RNG": RNG,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "TICKET_CONSTRUCTION": TICKET_CONSTRUCTION,
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
        "TICKET_SELECTION_RULE": TICKET_SELECTION_RULE,
        "WINDOW": WINDOW,
    }


CANDIDATE_SEMANTICS: Final[Mapping[str, object]] = MappingProxyType(
    _semantic_record()
)
CANDIDATE_SEMANTIC_RECORDS: Final[Mapping[str, Mapping[str, object]]] = (
    MappingProxyType({CANDIDATE_ID: CANDIDATE_SEMANTICS})
)
CANDIDATE_SEMANTICS_BY_ID = CANDIDATE_SEMANTIC_RECORDS
SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = CANDIDATE_SEMANTICS

CANDIDATE_METADATA: Final[CandidateMetadata] = CandidateMetadata(
    CANDIDATE_ID=CANDIDATE_ID,
    SELECTED_GAP_ID=SELECTED_GAP_ID,
    DESIGN_ID=DESIGN_ID,
    DESIGN_SIGNATURE_SHA256=DESIGN_SIGNATURE_SHA256,
    FEATURE_1=FEATURE_1,
    FEATURE_2=FEATURE_2,
    WINDOW=WINDOW,
    COMPONENT_NORMALIZATION_RULE=COMPONENT_NORMALIZATION_RULE,
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
    "ENTROPY_EPSILON",
    "ENTROPY_EXPECTED_COUNT",
    "ENTROPY_SCORE_RULE",
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
    "METHOD_LEVEL",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "NUMBER_RANKING_RULE_LINES",
    "NUMBER_TIE_BREAK_RULE",
    "NUMBER_TIE_BREAK_RULE_LINES",
    "OMISSION_WINDOWS",
    "OUTPUT_SHAPE",
    "PAIRWISE_SCORE_RULE",
    "PARAMETER_SELECTION_RULE",
    "PARENT_COMPONENT_RULE_1",
    "PARENT_COMPONENT_RULE_2",
    "PARENT_SOURCE_UNIVERSE_ID_1",
    "PARENT_SOURCE_UNIVERSE_ID_2",
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
    "calculate_gap_omission_component_50",
    "calculate_gap_omission_components",
    "calculate_gap_omission_ranking",
    "calculate_gap_omission_raw_scores",
    "calculate_omission_ranking",
    "calculate_omission_raw_scores",
    "calculate_pairwise_ranking",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "entropy_component_50",
    "entropy_components",
    "fuse_pairwise_scores",
    "gap_omission_components",
    "produce_biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate",
    "produce_bmsgv1_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_entropy_scores",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "validate_history",
    "validate_prior_history",
]
