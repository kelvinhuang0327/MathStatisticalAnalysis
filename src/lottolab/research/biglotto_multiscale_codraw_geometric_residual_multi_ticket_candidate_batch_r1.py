"""Causal BigLotto multiscale codraw geometric residual candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_CODRAW_DISTANCE_RESIDUAL_RANKED_POOL_V1.

Use the natural ordered number line 1..49 as the only geometry.
For every number and each fixed strictly-prior window: 50, 300, 750,
measure its observed absolute numeric distance to its five same-draw peers.
Compare observed co-draw distance with the exact symmetric 6-of-49 conditional
null expectation:
    UNIFORM_MEAN_PAIR_DISTANCE(n) = [n(n-1) + (49-n)(50-n)] / 96

Use the magnitude of the exact support-weighted relative distance residual as
the per-window geometric signal:
    GEOMETRIC_RESIDUAL_PRESSURE_W(n) = (
        (OCCURRENCE_W(n) / W) * RELATIVE_GEOMETRIC_DEVIATION_W(n)
    )
    = |ACTUAL_DISTANCE_SUM_W(n) - EXPECTED_DISTANCE_SUM_W(n)| / (
        5 * W * UNIFORM_MEAN_PAIR_DISTANCE(n)
    )

Fuse 50/300/750 rankings by exact equal rank aggregation, take the fused Top 10
numbers, generate all C(10,6) = 210 ordered source tickets, and pass the exact
210-ticket universe through the three frozen multi-ticket constructors at native
budgets 5, 10, and 20 to create exactly 9 frozen hypotheses.

The producer has no outcome access, fitted parameters, I/O, randomness, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice, pairwise
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type RobustnessTuple = tuple[Fraction, Fraction, Fraction]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = (
    "B649_MULTISCALE_CODRAW_DISTANCE_RESIDUAL_RANKED_POOL_V1"
)
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "GEOMETRY"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
FEATURE_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
WINDOWS: Final[tuple[int, int, int]] = FEATURE_WINDOWS
SOURCE_WINDOWS: Final[tuple[int, int, int]] = FEATURE_WINDOWS
MINIMUM_HISTORY: Final[int] = 750
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_NUMBER_POOL_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

GEOMETRY_DOMAIN_RULE: Final[str] = "NATURAL_ORDERED_NUMBER_LINE_1_49"
NUMBER_DISTANCE_RULE: Final[str] = "ABSOLUTE_INTEGER_DIFFERENCE"
UNIFORM_NULL_RULE: Final[str] = "SYMMETRIC_6_OF_49_CONDITIONAL_PEER_NULL"
UNIFORM_MEAN_PAIR_DISTANCE_RULE: Final[str] = (
    "UNIFORM_MEAN_PAIR_DISTANCE(n)=[n*(n-1)+(49-n)*(50-n)]/96;EXACT_RATIONAL"
)
EXPECTED_DISTANCE_RULE: Final[str] = (
    "EXPECTED_DISTANCE_SUM_W(n)=5*OCCURRENCE_W(n)*UNIFORM_MEAN_PAIR_DISTANCE(n);EXACT_RATIONAL"
)
SIGNED_DISTANCE_RESIDUAL_RULE: Final[str] = (
    "SIGNED_DISTANCE_RESIDUAL_W(n)=ACTUAL_DISTANCE_SUM_W(n)-EXPECTED_DISTANCE_SUM_W(n);EXACT_RATIONAL"
)
RELATIVE_GEOMETRIC_DEVIATION_RULE: Final[str] = (
    "RELATIVE_GEOMETRIC_DEVIATION_W(n)=|OBSERVED_MEAN_PAIR_DISTANCE_W(n)-UNIFORM_MEAN_PAIR_DISTANCE(n)|/UNIFORM_MEAN_PAIR_DISTANCE(n);ZERO_IF_OCCURRENCE_ZERO;EXACT_RATIONAL"
)
GEOMETRIC_RESIDUAL_PRESSURE_RULE: Final[str] = (
    "GEOMETRIC_RESIDUAL_PRESSURE_W(n)=(OCCURRENCE_W(n)/W)*RELATIVE_GEOMETRIC_DEVIATION_W(n)=|ACTUAL_DISTANCE_SUM_W(n)-EXPECTED_DISTANCE_SUM_W(n)|/(5*W*UNIFORM_MEAN_PAIR_DISTANCE(n));EXACT_RATIONAL"
)
PER_WINDOW_RANKING_RULE: Final[str] = (
    "GEOMETRIC_RESIDUAL_PRESSURE_DESCENDING_RELATIVE_GEOMETRIC_DEVIATION_DESCENDING_ABS_SIGNED_RESIDUAL_DESCENDING_NUMBER_ASCENDING"
)
WINDOW_NORMALIZATION_RULE: Final[str] = (
    "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
)
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+NORMALIZED_750)/3;ROBUSTNESS_TIE_BREAK"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
NATIVE_TICKET_COUNT: Final[str] = "TICKET_COUNT"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_CODRAW_GEOMETRIC_RESIDUAL_PRESSURE_STRUCTURE"
)

CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)

_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
            "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": (
                "NUMBER_EXPOSURE_DIVERSITY"
            ),
            "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
                "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
            ),
        }
    )
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the geometric residual source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    FEATURE_WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    TOP_NUMBER_COUNT: int
    SOURCE_NUMBER_POOL_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
    GEOMETRY_DOMAIN_RULE: str
    NUMBER_DISTANCE_RULE: str
    UNIFORM_NULL_RULE: str
    UNIFORM_MEAN_PAIR_DISTANCE_RULE: str
    EXPECTED_DISTANCE_RULE: str
    SIGNED_DISTANCE_RESIDUAL_RULE: str
    RELATIVE_GEOMETRIC_DEVIATION_RULE: str
    GEOMETRIC_RESIDUAL_PRESSURE_RULE: str
    PER_WINDOW_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    EXPECTED_IMPROVEMENT_CHANNEL: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    METHOD_FAMILY=METHOD_FAMILY,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    HISTORY_ORDER=HISTORY_ORDER,
    FEATURE_WINDOWS=FEATURE_WINDOWS,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_NUMBER_POOL_COUNT=SOURCE_NUMBER_POOL_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    GEOMETRY_DOMAIN_RULE=GEOMETRY_DOMAIN_RULE,
    NUMBER_DISTANCE_RULE=NUMBER_DISTANCE_RULE,
    UNIFORM_NULL_RULE=UNIFORM_NULL_RULE,
    UNIFORM_MEAN_PAIR_DISTANCE_RULE=UNIFORM_MEAN_PAIR_DISTANCE_RULE,
    EXPECTED_DISTANCE_RULE=EXPECTED_DISTANCE_RULE,
    SIGNED_DISTANCE_RESIDUAL_RULE=SIGNED_DISTANCE_RESIDUAL_RULE,
    RELATIVE_GEOMETRIC_DEVIATION_RULE=RELATIVE_GEOMETRIC_DEVIATION_RULE,
    GEOMETRIC_RESIDUAL_PRESSURE_RULE=GEOMETRIC_RESIDUAL_PRESSURE_RULE,
    PER_WINDOW_RANKING_RULE=PER_WINDOW_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_DISTANCE_RULE": EXPECTED_DISTANCE_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "GEOMETRIC_RESIDUAL_PRESSURE_RULE": GEOMETRIC_RESIDUAL_PRESSURE_RULE,
        "GEOMETRY_DOMAIN_RULE": GEOMETRY_DOMAIN_RULE,
        "HISTORY_ORDER": HISTORY_ORDER,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NUMBER_DISTANCE_RULE": NUMBER_DISTANCE_RULE,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RELATIVE_GEOMETRIC_DEVIATION_RULE": RELATIVE_GEOMETRIC_DEVIATION_RULE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SIGNED_DISTANCE_RESIDUAL_RULE": SIGNED_DISTANCE_RESIDUAL_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "UNIFORM_MEAN_PAIR_DISTANCE_RULE": UNIFORM_MEAN_PAIR_DISTANCE_RULE,
        "UNIFORM_NULL_RULE": UNIFORM_NULL_RULE,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class NumberDistanceCalculation:
    """Per-number geometric distance calculation within a fixed window."""

    NUMBER: int
    OCCURRENCE_COUNT: int
    ACTUAL_DISTANCE_SUM: int
    EXPECTED_DISTANCE_SUM: Fraction
    SIGNED_DISTANCE_RESIDUAL: Fraction
    OBSERVED_MEAN_PAIR_DISTANCE: Fraction
    UNIFORM_MEAN_PAIR_DISTANCE: Fraction
    RELATIVE_GEOMETRIC_DEVIATION: Fraction
    GEOMETRIC_RESIDUAL_PRESSURE: Fraction
    POSITION: int
    NORMALIZED_RANK: Fraction


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Window-specific geometric ranking and calculation state for numbers 1..49."""

    WINDOW: int
    WINDOW_DRAW_COUNT: int
    OCCURRENCE_COUNTS: tuple[int, ...]
    ACTUAL_DISTANCE_SUMS: tuple[int, ...]
    EXPECTED_DISTANCE_SUMS: tuple[Fraction, ...]
    SIGNED_DISTANCE_RESIDUALS: tuple[Fraction, ...]
    OBSERVED_MEAN_PAIR_DISTANCES: tuple[Fraction, ...]
    UNIFORM_MEAN_PAIR_DISTANCES: tuple[Fraction, ...]
    RELATIVE_GEOMETRIC_DEVIATIONS: tuple[Fraction, ...]
    GEOMETRIC_RESIDUAL_PRESSURES: tuple[Fraction, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]
    CALCULATIONS: tuple[NumberDistanceCalculation, ...]

    @property
    def DRAW_COUNT(self) -> int:
        return self.WINDOW_DRAW_COUNT

    def occurrence_count(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1]

    def actual_distance_sum(self, number: int) -> int:
        _validate_number(number)
        return self.ACTUAL_DISTANCE_SUMS[number - 1]

    def expected_distance_sum(self, number: int) -> Fraction:
        _validate_number(number)
        return self.EXPECTED_DISTANCE_SUMS[number - 1]

    def signed_distance_residual(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SIGNED_DISTANCE_RESIDUALS[number - 1]

    def observed_mean_pair_distance(self, number: int) -> Fraction:
        _validate_number(number)
        return self.OBSERVED_MEAN_PAIR_DISTANCES[number - 1]

    def uniform_mean_pair_distance(self, number: int) -> Fraction:
        _validate_number(number)
        return self.UNIFORM_MEAN_PAIR_DISTANCES[number - 1]

    def relative_geometric_deviation(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RELATIVE_GEOMETRIC_DEVIATIONS[number - 1]

    def geometric_residual_pressure(self, number: int) -> Fraction:
        _validate_number(number)
        return self.GEOMETRIC_RESIDUAL_PRESSURES[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    def calculation_for(self, number: int) -> NumberDistanceCalculation:
        _validate_number(number)
        return self.CALCULATIONS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedRanking:
    """Equal rank aggregation fused ranking across 50, 300, and 750 windows."""

    WINDOW_RANKINGS: tuple[WindowRanking, WindowRanking, WindowRanking]
    MEAN_RANKS: tuple[Fraction, ...]
    ROBUSTNESS_TUPLES: tuple[RobustnessTuple, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    TOP_NUMBERS: tuple[int, ...]

    def mean_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEAN_RANKS[number - 1]

    def robustness(self, number: int) -> RobustnessTuple:
        _validate_number(number)
        return self.ROBUSTNESS_TUPLES[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]


def _validate_number(number: int) -> None:
    if (
        type(number) is not int
        or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
    ):
        raise ValueError(
            f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
        )


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(
    history: HistoryInput, target_index: int
) -> tuple[object, ...]:
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
        raise ValueError(
            "history must be a finite chronological sequence of draws"
        ) from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly six integers"
        ) from error

    if len(values) != PICK_COUNT:
        raise ValueError(
            f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers"
        )

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(
                f"history[{draw_index}][{position}] must be an integer"
            )
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    sorted_numbers = tuple(sorted(numbers))
    for left, right in pairwise(sorted_numbers):
        if left == right:
            raise ValueError(
                f"history[{draw_index}] contains duplicate number {left}"
            )
    return cast(HistoryDraw, sorted_numbers)


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Validate and return the immutable strictly-prior history prefix."""

    prefix = _read_history_prefix(history, target_index)
    if len(prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index {target_index} provides {len(prefix)} draws, "
            f"which is fewer than the required minimum {MINIMUM_HISTORY}"
        )

    return tuple(
        _validate_draw(raw_draw, draw_index)
        for draw_index, raw_draw in enumerate(prefix)
    )


def uniform_mean_pair_distance(number: int) -> Fraction:
    """Calculate exact conditional uniform mean pair distance for legal number n in 1..49."""

    _validate_number(number)
    n = number
    # Exact rational formula: [n*(n-1) + (49-n)*(50-n)] / 96
    num = n * (n - 1) + (49 - n) * (50 - n)
    return Fraction(num, 96)


def calculate_window_rankings(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Calculate exact geometric co-draw distance residual rankings for a single window."""

    if window not in FEATURE_WINDOWS:
        raise ValueError(
            f"window must be one of {FEATURE_WINDOWS}, got {window}"
        )

    valid_history = validate_prior_history(history, target_index)
    window_draws = valid_history[target_index - window : target_index]

    occurrences = [0] * 49
    actual_distance_sums = [0] * 49

    for draw in window_draws:
        for num in draw:
            occurrences[num - 1] += 1
            peer_dist_sum = sum(abs(num - m) for m in draw if m != num)
            actual_distance_sums[num - 1] += peer_dist_sum

    expected_distance_sums: list[Fraction] = []
    signed_residuals: list[Fraction] = []
    observed_mean_pair_distances: list[Fraction] = []
    uniform_mean_pair_distances: list[Fraction] = []
    relative_deviations: list[Fraction] = []
    geometric_residual_pressures: list[Fraction] = []

    for num in range(1, 50):
        occ = occurrences[num - 1]
        act_sum = actual_distance_sums[num - 1]
        null_mean = uniform_mean_pair_distance(num)
        uniform_mean_pair_distances.append(null_mean)

        exp_sum = Fraction(5 * occ, 1) * null_mean
        expected_distance_sums.append(exp_sum)

        signed_res = Fraction(act_sum, 1) - exp_sum
        signed_residuals.append(signed_res)

        if occ > 0:
            obs_mean = Fraction(act_sum, 5 * occ)
            rel_dev = abs(obs_mean - null_mean) / null_mean
            pressure = Fraction(occ, window) * rel_dev
            # Exact identity check: |ACTUAL - EXPECTED| / (5 * W * NULL)
            pressure_alt = abs(Fraction(act_sum, 1) - exp_sum) / (
                Fraction(5 * window, 1) * null_mean
            )
            if pressure != pressure_alt:
                raise RuntimeError(
                    f"geometric residual pressure formula mismatch for number {num}"
                )
        else:
            obs_mean = Fraction(0, 1)
            rel_dev = Fraction(0, 1)
            pressure = Fraction(0, 1)

        observed_mean_pair_distances.append(obs_mean)
        relative_deviations.append(rel_dev)
        geometric_residual_pressures.append(pressure)

    # Per-window ranking order:
    # 1. GEOMETRIC_RESIDUAL_PRESSURE descending
    # 2. RELATIVE_GEOMETRIC_DEVIATION descending
    # 3. abs(SIGNED_DISTANCE_RESIDUAL) descending
    # 4. number ascending
    sort_keys: list[tuple[tuple[Fraction, Fraction, Fraction, int], int]] = []
    for num in range(1, 50):
        idx = num - 1
        key = (
            -geometric_residual_pressures[idx],
            -relative_deviations[idx],
            -abs(signed_residuals[idx]),
            num,
        )
        sort_keys.append((key, num))

    sort_keys.sort(key=lambda item: item[0])
    ordered_numbers = tuple(item[1] for item in sort_keys)

    positions = [0] * 49
    normalized_ranks = [Fraction(0, 1)] * 49
    for pos_zero_based, num in enumerate(ordered_numbers):
        position = pos_zero_based + 1
        positions[num - 1] = position
        normalized_ranks[num - 1] = Fraction(49 - position, 48)

    calculations: list[NumberDistanceCalculation] = []
    for num in range(1, 50):
        idx = num - 1
        calc = NumberDistanceCalculation(
            NUMBER=num,
            OCCURRENCE_COUNT=occurrences[idx],
            ACTUAL_DISTANCE_SUM=actual_distance_sums[idx],
            EXPECTED_DISTANCE_SUM=expected_distance_sums[idx],
            SIGNED_DISTANCE_RESIDUAL=signed_residuals[idx],
            OBSERVED_MEAN_PAIR_DISTANCE=observed_mean_pair_distances[idx],
            UNIFORM_MEAN_PAIR_DISTANCE=uniform_mean_pair_distances[idx],
            RELATIVE_GEOMETRIC_DEVIATION=relative_deviations[idx],
            GEOMETRIC_RESIDUAL_PRESSURE=geometric_residual_pressures[idx],
            POSITION=positions[idx],
            NORMALIZED_RANK=normalized_ranks[idx],
        )
        calculations.append(calc)

    return WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=window,
        OCCURRENCE_COUNTS=tuple(occurrences),
        ACTUAL_DISTANCE_SUMS=tuple(actual_distance_sums),
        EXPECTED_DISTANCE_SUMS=tuple(expected_distance_sums),
        SIGNED_DISTANCE_RESIDUALS=tuple(signed_residuals),
        OBSERVED_MEAN_PAIR_DISTANCES=tuple(observed_mean_pair_distances),
        UNIFORM_MEAN_PAIR_DISTANCES=tuple(uniform_mean_pair_distances),
        RELATIVE_GEOMETRIC_DEVIATIONS=tuple(relative_deviations),
        GEOMETRIC_RESIDUAL_PRESSURES=tuple(geometric_residual_pressures),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
        CALCULATIONS=tuple(calculations),
    )


rank_numbers_by_window = calculate_window_rankings


def fuse_window_rankings(
    rankings: tuple[WindowRanking, WindowRanking, WindowRanking],
) -> FusedRanking:
    """Fuse 50, 300, and 750 window rankings by exact equal rank aggregation."""

    if len(rankings) != 3:
        raise ValueError("exactly three window rankings required for fusion")

    r50, r300, r750 = rankings
    if (r50.WINDOW, r300.WINDOW, r750.WINDOW) != FEATURE_WINDOWS:
        raise ValueError(
            f"window rankings must correspond to windows {FEATURE_WINDOWS}"
        )

    mean_ranks: list[Fraction] = []
    robustness_tuples: list[RobustnessTuple] = []

    for num in range(1, 50):
        n50 = r50.normalized_rank(num)
        n300 = r300.normalized_rank(num)
        n750 = r750.normalized_rank(num)
        mean_rank = (n50 + n300 + n750) / 3
        sorted_window_ranks = tuple(sorted([n50, n300, n750]))
        robustness: RobustnessTuple = (
            sorted_window_ranks[0],
            sorted_window_ranks[1],
            sorted_window_ranks[2],
        )
        mean_ranks.append(mean_rank)
        robustness_tuples.append(robustness)

    # Final ranking sort key:
    # 1. mean rank descending
    # 2. robustness minimum descending
    # 3. robustness median descending
    # 4. robustness maximum descending
    # 5. number ascending
    fused_sort_keys: list[
        tuple[tuple[Fraction, Fraction, Fraction, Fraction, int], int]
    ] = []
    for num in range(1, 50):
        idx = num - 1
        rob = robustness_tuples[idx]
        key = (-mean_ranks[idx], -rob[0], -rob[1], -rob[2], num)
        fused_sort_keys.append((key, num))

    fused_sort_keys.sort(key=lambda item: item[0])
    ordered_numbers = tuple(item[1] for item in fused_sort_keys)

    positions = [0] * 49
    for pos_zero_based, num in enumerate(ordered_numbers):
        positions[num - 1] = pos_zero_based + 1

    top_numbers = tuple(ordered_numbers[:TOP_NUMBER_COUNT])

    return FusedRanking(
        WINDOW_RANKINGS=rankings,
        MEAN_RANKS=tuple(mean_ranks),
        ROBUSTNESS_TUPLES=tuple(robustness_tuples),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        TOP_NUMBERS=top_numbers,
    )


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedRanking:
    """Calculate the complete multiscale geometric residual fused ranking."""

    r50 = calculate_window_rankings(history, target_index, 50)
    r300 = calculate_window_rankings(history, target_index, 300)
    r750 = calculate_window_rankings(history, target_index, 750)
    return fuse_window_rankings((r50, r300, r750))


def produce_b649_multiscale_codraw_geometric_residual_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket geometric residual source universe."""

    fused = calculate_fused_number_ranking(history, target_index)
    top10 = fused.TOP_NUMBERS
    if len(top10) != TOP_NUMBER_COUNT:
        raise RuntimeError(
            f"fused ranking produced {len(top10)} top numbers, expected {TOP_NUMBER_COUNT}"
        )

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(
            Ticket,
            tuple(sorted(top10[pos] for pos in rank_positions)),
        )
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError(
            f"source universe produced {len(source_tickets)} tickets, "
            f"expected {SOURCE_CANDIDATE_TICKET_COUNT}"
        )
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = (
    produce_b649_multiscale_codraw_geometric_residual_ranked_pool_v1
)
build_source_ticket_universe = (
    produce_b649_multiscale_codraw_geometric_residual_ranked_pool_v1
)


def raw_frequency_order_for_window(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return numbers ordered by raw occurrence count descending, then number ascending."""

    valid_history = validate_prior_history(history, target_index)
    window_draws = valid_history[target_index - window : target_index]
    counts = [0] * 49
    for draw in window_draws:
        for num in draw:
            counts[num - 1] += 1
    sort_keys = [(-counts[num - 1], num) for num in range(1, 50)]
    return tuple(num for _, num in sorted(zip(sort_keys, range(1, 50), strict=True)))


def multiscale_frequency_order(
    history: HistoryInput, target_index: int
) -> tuple[int, ...]:
    """Return numbers ordered by multiscale equal rank frequency aggregation."""

    valid_history = validate_prior_history(history, target_index)
    w_ranks: list[list[Fraction]] = []
    for w in (50, 300, 750):
        window_draws = valid_history[target_index - w : target_index]
        counts = [0] * 49
        for draw in window_draws:
            for num in draw:
                counts[num - 1] += 1
        items = sorted((-counts[n - 1], n) for n in range(1, 50))
        norm = [Fraction(0, 1)] * 49
        for pos, (_, n) in enumerate(items):
            norm[n - 1] = Fraction(49 - (pos + 1), 48)
        w_ranks.append(norm)

    fused_scores = [
        (w_ranks[0][n - 1] + w_ranks[1][n - 1] + w_ranks[2][n - 1]) / 3
        for n in range(1, 50)
    ]
    sort_keys = [(-fused_scores[n - 1], n) for n in range(1, 50)]
    return tuple(num for _, num in sorted(zip(sort_keys, range(1, 50), strict=True)))


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        mapping = cast(Mapping[object, object], value)
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
    """Return sorted-key, compact UTF-8 JSON for a complete semantic record."""

    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    json_ready_record = _json_ready(cast(Mapping[object, object], record))
    return json.dumps(
        json_ready_record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    """Return canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the frozen geometric residual candidate ID."""

    return f"BMSGV1_GM_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one geometric residual hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_GM_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one frozen research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_multiscale_codraw_geometric_residual_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_DISTANCE_RULE": EXPECTED_DISTANCE_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "GEOMETRIC_RESIDUAL_PRESSURE_RULE": GEOMETRIC_RESIDUAL_PRESSURE_RULE,
        "GEOMETRY_DOMAIN_RULE": GEOMETRY_DOMAIN_RULE,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DISTANCE_RULE": NUMBER_DISTANCE_RULE,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RELATIVE_GEOMETRIC_DEVIATION_RULE": RELATIVE_GEOMETRIC_DEVIATION_RULE,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SIGNED_DISTANCE_RESIDUAL_RULE": SIGNED_DISTANCE_RESIDUAL_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "UNIFORM_MEAN_PAIR_DISTANCE_RULE": UNIFORM_MEAN_PAIR_DISTANCE_RULE,
        "UNIFORM_NULL_RULE": UNIFORM_NULL_RULE,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }


def _build_candidate_authority() -> tuple[
    tuple[CandidateMetadata, ...],
    Mapping[str, CandidateMetadata],
    Mapping[str, Mapping[str, object]],
    Mapping[tuple[str, int], str],
]:
    authorities: list[CandidateMetadata] = []
    metadata_by_id: dict[str, CandidateMetadata] = {}
    semantics_by_id: dict[str, Mapping[str, object]] = {}
    ids_by_pair: dict[tuple[str, int], str] = {}

    for constructor_id in CONSTRUCTOR_IDS:
        for ticket_count in TICKET_COUNTS:
            semantic_record = _candidate_semantic_record(
                constructor_id, ticket_count
            )
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError(
                    "candidate ID collision in frozen geometric residual hypothesis matrix"
                )
            semantic_proxy: Mapping[str, object] = MappingProxyType(
                semantic_record
            )
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(
                    constructor_id, ticket_count
                ),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(
        authorities
    ):
        raise RuntimeError(
            "candidate signature collision in frozen geometric residual matrix"
        )
    return (
        tuple(authorities),
        MappingProxyType(metadata_by_id),
        MappingProxyType(semantics_by_id),
        MappingProxyType(ids_by_pair),
    )


(
    CANDIDATE_AUTHORITIES,
    CANDIDATE_METADATA,
    CANDIDATE_SEMANTICS,
    CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT,
) = _build_candidate_authority()

CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = (
    CANDIDATE_METADATA
)
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {
        metadata.CANDIDATE_ID: metadata.SIGNATURE_HASH
        for metadata in CANDIDATE_AUTHORITIES
    }
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the candidate ID for a given constructor and native ticket count."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[
            (constructor_id, ticket_count)
        ]
    except KeyError as error:
        raise KeyError(
            f"unknown constructor/ticket_count pair: {(constructor_id, ticket_count)}"
        ) from error


def _produce_named_candidate(
    constructor_id: str,
    ticket_count: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    universe = produce_source_ticket_universe(history, target_index)
    if constructor_id == "B649_CANDIDATE_SET_LOW_OVERLAP_V1":
        return _constructors.construct_b649_candidate_set_low_overlap_v1(
            universe, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1":
        return _constructors.construct_b649_candidate_set_exposure_balanced_v1(
            universe, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1":
        return _constructors.construct_b649_candidate_set_hybrid_diversity_v1(
            universe, ticket_count
        )
    raise KeyError(f"unknown constructor ID: {constructor_id}")


def produce_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the portfolio for any of the 9 candidate IDs."""

    try:
        metadata = CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate ID: {candidate_id}") from error

    return _produce_named_candidate(
        metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT, history, target_index
    )


produce_biglotto_multi_ticket_candidate = produce_candidate_portfolio
produce_multi_ticket_candidate = produce_candidate_portfolio
produce_biglotto_codraw_geometric_residual_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_biglotto_multiscale_codraw_geometric_residual_multi_ticket_candidate = (
    produce_candidate_portfolio
)


def produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 5, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 10, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 20, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 5, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 10, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 20, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 5, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 10, history, target_index
    )


def produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 20, history, target_index
    )


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "EXPECTED_DISTANCE_RULE",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_WINDOWS",
    "GEOMETRIC_RESIDUAL_PRESSURE_RULE",
    "GEOMETRY_DOMAIN_RULE",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DISTANCE_RULE",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "RELATIVE_GEOMETRIC_DEVIATION_RULE",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SIGNED_DISTANCE_RESIDUAL_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_NUMBER_POOL_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "UNIFORM_MEAN_PAIR_DISTANCE_RULE",
    "UNIFORM_NULL_RULE",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "CandidateIdentity",
    "CandidateMetadata",
    "FusedRanking",
    "InsufficientHistoryError",
    "NumberDistanceCalculation",
    "SourceUniverseMetadata",
    "WindowRanking",
    "build_source_ticket_universe",
    "calculate_fused_number_ranking",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_window_rankings",
    "multiscale_frequency_order",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_codraw_geometric_residual_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_codraw_geometric_residual_ranked_pool_v1",
    "produce_biglotto_codraw_geometric_residual_multi_ticket_candidate",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_multiscale_codraw_geometric_residual_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "raw_frequency_order_for_window",
    "signature_hash_for_semantics",
    "uniform_mean_pair_distance",
    "validate_prior_history",
]
