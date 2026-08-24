"""Causal BigLotto multiscale official-null surprise candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_OFFICIAL_NULL_Z2_RANKED_POOL_V1.

For every legal number and each fixed strictly-prior window, the number of
draws containing it is compared with the exact symmetric BigLotto 6-of-49
marginal null.  The two-sided standardized residual is ranked by magnitude,
then the three fixed-window rankings are fused by exact equal rank
aggregation.  The top 10 numbers generate exactly 210 ordered source tickets
and are passed directly to the three frozen portfolio constructors.

The producer has no outcome access, fitted parameters, I/O, randomness, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type RationalRanks = tuple[Fraction, ...]
type RobustnessTuple = tuple[Fraction, Fraction, Fraction]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_MULTISCALE_OFFICIAL_NULL_Z2_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "NULL_BASELINE"
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

OFFICIAL_NULL_P0: Final[Fraction] = Fraction(6, 49)
P0: Final[Fraction] = OFFICIAL_NULL_P0
EXPECTED_COUNT_RULE: Final[str] = "EXPECTED_COUNT_W=W*6/49;EXACT_RATIONAL"
NULL_VARIANCE_RULE: Final[str] = "NULL_VARIANCE_W=258W/2401;EXACT_RATIONAL"
SIGNED_NULL_RESIDUAL_RULE: Final[str] = (
    "SIGNED_NULL_RESIDUAL_W(n)=49*COUNT_W(n)-6*W;INTEGER_SCALED"
)
OFFICIAL_NULL_Z2_RULE: Final[str] = (
    "OFFICIAL_NULL_Z2_W(n)=(49*COUNT_W(n)-6*W)^2/(258*W);EXACT_RATIONAL"
)
PRIMARY_SCORE: Final[str] = "OFFICIAL_NULL_Z2"
PRIMARY_SCORE_ARITHMETIC: Final[str] = "EXACT_RATIONAL"
NULL_DIRECTION_RULE: Final[str] = "SIGNED_RESIDUAL_GT0_HOT_LT0_COLD_EQ0_NEUTRAL"
SIGN_DIRECTION_USED_FOR_RANKING: Final[str] = "NO"
TEMPORAL_ORDER_USED_WITHIN_WINDOW: Final[str] = "NO"
LAST_HIT_GAP_USED: Final[str] = "NO"
PER_WINDOW_RANKING_RULE: Final[str] = (
    "OFFICIAL_NULL_Z2_DESCENDING_NUMBER_ASCENDING"
)
WINDOW_NORMALIZATION_RULE: Final[str] = (
    "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
)
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+NORMALIZED_750)/3;"
    "ROBUSTNESS_TIE_BREAK"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_PERSISTENT_MARGINAL_DEVIATION_FROM_OFFICIAL_6_OF_49_NULL"
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
            "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "NUMBER_EXPOSURE_DIVERSITY",
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
    """Immutable authority metadata for the official-null source universe."""

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
    OFFICIAL_NULL_P0: Fraction
    EXPECTED_COUNT_RULE: str
    NULL_VARIANCE_RULE: str
    SIGNED_NULL_RESIDUAL_RULE: str
    OFFICIAL_NULL_Z2_RULE: str
    PRIMARY_SCORE: str
    PRIMARY_SCORE_ARITHMETIC: str
    NULL_DIRECTION_RULE: str
    SIGN_DIRECTION_USED_FOR_RANKING: str
    TEMPORAL_ORDER_USED_WITHIN_WINDOW: str
    LAST_HIT_GAP_USED: str
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
    OFFICIAL_NULL_P0=OFFICIAL_NULL_P0,
    EXPECTED_COUNT_RULE=EXPECTED_COUNT_RULE,
    NULL_VARIANCE_RULE=NULL_VARIANCE_RULE,
    SIGNED_NULL_RESIDUAL_RULE=SIGNED_NULL_RESIDUAL_RULE,
    OFFICIAL_NULL_Z2_RULE=OFFICIAL_NULL_Z2_RULE,
    PRIMARY_SCORE=PRIMARY_SCORE,
    PRIMARY_SCORE_ARITHMETIC=PRIMARY_SCORE_ARITHMETIC,
    NULL_DIRECTION_RULE=NULL_DIRECTION_RULE,
    SIGN_DIRECTION_USED_FOR_RANKING=SIGN_DIRECTION_USED_FOR_RANKING,
    TEMPORAL_ORDER_USED_WITHIN_WINDOW=TEMPORAL_ORDER_USED_WITHIN_WINDOW,
    LAST_HIT_GAP_USED=LAST_HIT_GAP_USED,
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
        "EXPECTED_COUNT_RULE": EXPECTED_COUNT_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "HISTORY_ORDER": HISTORY_ORDER,
        "LAST_HIT_GAP_USED": LAST_HIT_GAP_USED,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NULL_DIRECTION_RULE": NULL_DIRECTION_RULE,
        "NULL_VARIANCE_RULE": NULL_VARIANCE_RULE,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OFFICIAL_NULL_P0": OFFICIAL_NULL_P0,
        "OFFICIAL_NULL_Z2_RULE": OFFICIAL_NULL_Z2_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "PRIMARY_SCORE": PRIMARY_SCORE,
        "PRIMARY_SCORE_ARITHMETIC": PRIMARY_SCORE_ARITHMETIC,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SIGN_DIRECTION_USED_FOR_RANKING": SIGN_DIRECTION_USED_FOR_RANKING,
        "SIGNED_NULL_RESIDUAL_RULE": SIGNED_NULL_RESIDUAL_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TEMPORAL_ORDER_USED_WITHIN_WINDOW": TEMPORAL_ORDER_USED_WITHIN_WINDOW,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class NumberNullCalculation:
    """Exact official-null state for one number in one fixed window."""

    NUMBER: int
    WINDOW: int
    OCCURRENCE_COUNT: int
    EXPECTED_COUNT: Fraction
    NULL_VARIANCE: Fraction
    SIGNED_NULL_RESIDUAL: int
    OFFICIAL_NULL_Z2: Fraction
    NULL_DIRECTION: str
    POSITION: int
    NORMALIZED_RANK: Fraction

    @property
    def COUNT_W(self) -> int:
        return self.OCCURRENCE_COUNT

    @property
    def SIGNED_RESIDUAL(self) -> int:
        return self.SIGNED_NULL_RESIDUAL

    @property
    def Z2(self) -> Fraction:
        return self.OFFICIAL_NULL_Z2

    @property
    def SCORE(self) -> Fraction:
        return self.OFFICIAL_NULL_Z2

    @property
    def DIRECTION(self) -> str:
        return self.NULL_DIRECTION


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Exact counts, official-null residuals, surprise scores, and ranks."""

    WINDOW: int
    WINDOW_DRAW_COUNT: int
    OCCURRENCE_COUNTS: tuple[int, ...]
    EXPECTED_COUNTS: RationalRanks
    NULL_VARIANCES: RationalRanks
    SIGNED_NULL_RESIDUALS: tuple[int, ...]
    OFFICIAL_NULL_Z2S: RationalRanks
    NULL_DIRECTIONS: tuple[str, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: RationalRanks
    CALCULATIONS: tuple[NumberNullCalculation, ...]

    @property
    def DRAW_COUNT(self) -> int:
        return self.WINDOW_DRAW_COUNT

    @property
    def COUNTS(self) -> tuple[int, ...]:
        return self.OCCURRENCE_COUNTS

    @property
    def SCORES(self) -> RationalRanks:
        return self.OFFICIAL_NULL_Z2S

    @property
    def OFFICIAL_NULL_Z2(self) -> RationalRanks:
        return self.OFFICIAL_NULL_Z2S

    @property
    def NULL_Z2S(self) -> RationalRanks:
        return self.OFFICIAL_NULL_Z2S

    @property
    def EXPECTED_COUNT(self) -> Fraction:
        return self.EXPECTED_COUNTS[0]

    @property
    def NULL_VARIANCE(self) -> Fraction:
        return self.NULL_VARIANCES[0]

    def occurrence_count(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1]

    def count(self, number: int) -> int:
        return self.occurrence_count(number)

    def expected_count(self, number: int) -> Fraction:
        _validate_number(number)
        return self.EXPECTED_COUNTS[number - 1]

    def null_variance(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NULL_VARIANCES[number - 1]

    def signed_null_residual(self, number: int) -> int:
        _validate_number(number)
        return self.SIGNED_NULL_RESIDUALS[number - 1]

    def signed_residual(self, number: int) -> int:
        return self.signed_null_residual(number)

    def official_null_z2(self, number: int) -> Fraction:
        _validate_number(number)
        return self.OFFICIAL_NULL_Z2S[number - 1]

    def z2(self, number: int) -> Fraction:
        return self.official_null_z2(number)

    def score(self, number: int) -> Fraction:
        return self.official_null_z2(number)

    def null_direction(self, number: int) -> str:
        _validate_number(number)
        return self.NULL_DIRECTIONS[number - 1]

    def direction(self, number: int) -> str:
        return self.null_direction(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    def calculation_for(self, number: int) -> NumberNullCalculation:
        _validate_number(number)
        return self.CALCULATIONS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Three-window exact equal-rank fusion with deterministic tie-breaks."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_RANKS: RationalRanks
    ROBUSTNESS: tuple[RobustnessTuple, ...]
    WINDOW_RANKINGS: tuple[WindowRanking, WindowRanking, WindowRanking]

    @property
    def TOP_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS[:TOP_NUMBER_COUNT]

    @property
    def MEAN_NULL_SURPRISE_RANKS(self) -> RationalRanks:
        return self.MEAN_RANKS

    @property
    def ROBUSTNESS_TUPLES(self) -> tuple[RobustnessTuple, ...]:
        return self.ROBUSTNESS

    def mean_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEAN_RANKS[number - 1]

    def mean_null_surprise_rank(self, number: int) -> Fraction:
        return self.mean_rank(number)

    def robustness(self, number: int) -> RobustnessTuple:
        _validate_number(number)
        return self.ROBUSTNESS[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.ORDERED_NUMBERS.index(number) + 1


FusedRanking = FusedNumberRanking


def _validate_number(number: int) -> None:
    if (
        type(number) is not int
        or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
    ):
        raise ValueError(
            f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
        )


def _validate_positive_window(window: int) -> None:
    if type(window) is not int or window <= 0:
        raise ValueError("window must be a positive integer")


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in FEATURE_WINDOWS:
        raise ValueError(f"window must be one of {FEATURE_WINDOWS}")


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
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(sorted(numbers)))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return an immutable copy of only the strictly-prior validated history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"required minimum {MINIMUM_HISTORY}"
        )
    return tuple(
        _validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix)
    )


def expected_count(window: int) -> Fraction:
    """Return the exact official-null expected inclusion count for ``window``."""

    _validate_positive_window(window)
    return Fraction(window * 6, 49)


calculate_expected_count = expected_count
official_null_expected_count = expected_count


def null_variance(window: int) -> Fraction:
    """Return the frozen independent-draw official-null marginal variance."""

    _validate_positive_window(window)
    return Fraction(258 * window, 2401)


calculate_null_variance = null_variance
official_null_variance = null_variance


def signed_null_residual(count: int, window: int) -> int:
    """Return the integer-scaled signed residual ``49*count - 6*window``."""

    _validate_positive_window(window)
    if type(count) is not int or not 0 <= count <= window:
        raise ValueError("count must be an integer between zero and window")
    return 49 * count - 6 * window


calculate_signed_null_residual = signed_null_residual
official_null_signed_residual = signed_null_residual


def official_null_z2(count: int, window: int) -> Fraction:
    """Return the exact two-sided standardized residual statistic."""

    residual = signed_null_residual(count, window)
    return Fraction(residual * residual, 258 * window)


calculate_official_null_z2 = official_null_z2
official_null_surprise_z2 = official_null_z2


def null_direction(signed_residual_value: int) -> str:
    """Return the diagnostic HOT/COLD/NEUTRAL label for a signed residual."""

    if type(signed_residual_value) is not int:
        raise ValueError("signed residual must be an integer")
    if signed_residual_value > 0:
        return "HOT"
    if signed_residual_value < 0:
        return "COLD"
    return "NEUTRAL"


def direction_for_count(count: int, window: int) -> str:
    return null_direction(signed_null_residual(count, window))


calculate_null_direction = direction_for_count


def calculate_occurrences(draws: Sequence[HistoryDraw]) -> tuple[int, ...]:
    """Count appearances for every number in the supplied draws."""

    counts = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for draw in draws:
        for number in draw:
            counts[number - 1] += 1
    return tuple(counts)


def calculate_window_counts(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return exact counts from ``history[target_index-window:target_index]``."""

    _validate_window(window)
    valid_history = validate_prior_history(history, target_index)
    if len(valid_history) < window:
        raise InsufficientHistoryError(f"window {window} requires at least {window} prior draws")
    return calculate_occurrences(valid_history[-window:])


def _rank_validated_window(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> WindowRanking:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(f"window {window} requires at least {window} prior draws")

    window_draws = prior_history[-window:]
    occurrences = calculate_occurrences(window_draws)
    expected = expected_count(window)
    variance = null_variance(window)
    expected_counts = (expected,) * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    variances = (variance,) * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    residuals = tuple(
        signed_null_residual(count, window) for count in occurrences
    )
    scores = tuple(official_null_z2(count, window) for count in occurrences)
    directions = tuple(null_direction(residual) for residual in residuals)

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-scores[number - 1], number),
        )
    )
    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    normalized_ranks = [Fraction(0, 1)] * len(positions)
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    calculations = tuple(
        NumberNullCalculation(
            NUMBER=number,
            WINDOW=window,
            OCCURRENCE_COUNT=occurrences[number - 1],
            EXPECTED_COUNT=expected,
            NULL_VARIANCE=variance,
            SIGNED_NULL_RESIDUAL=residuals[number - 1],
            OFFICIAL_NULL_Z2=scores[number - 1],
            NULL_DIRECTION=directions[number - 1],
            POSITION=positions[number - 1],
            NORMALIZED_RANK=normalized_ranks[number - 1],
        )
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )

    return WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=len(window_draws),
        OCCURRENCE_COUNTS=occurrences,
        EXPECTED_COUNTS=expected_counts,
        NULL_VARIANCES=variances,
        SIGNED_NULL_RESIDUALS=residuals,
        OFFICIAL_NULL_Z2S=scores,
        NULL_DIRECTIONS=directions,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
        CALCULATIONS=calculations,
    )


def rank_numbers_by_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Rank all numbers by exact two-sided official-null surprise in one window."""

    return _rank_validated_window(validate_prior_history(history, target_index), window)


def calculate_window_ranking(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    return rank_numbers_by_window(history, target_index, window)


def calculate_window_rankings(
    history: HistoryInput, target_index: int, window: int | None = None
) -> WindowRanking | tuple[WindowRanking, WindowRanking, WindowRanking]:
    """Return one requested ranking or all three frozen window rankings."""

    if window is not None:
        return rank_numbers_by_window(history, target_index, window)
    prior_history = validate_prior_history(history, target_index)
    return tuple(_rank_validated_window(prior_history, current) for current in FEATURE_WINDOWS)  # type: ignore[return-value]


def fuse_window_rankings(
    rankings: tuple[WindowRanking, WindowRanking, WindowRanking]
) -> FusedNumberRanking:
    """Fuse the fixed windows by exact equal rank aggregation."""

    if len(rankings) != 3:
        raise ValueError("exactly three window rankings required for fusion")
    if tuple(ranking.WINDOW for ranking in rankings) != FEATURE_WINDOWS:
        raise ValueError(f"window rankings must correspond to windows {FEATURE_WINDOWS}")

    mean_ranks: list[Fraction] = []
    robustness: list[RobustnessTuple] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = tuple(
            ranking.normalized_rank(number) for ranking in rankings
        )
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / 3)
        ordered = tuple(sorted(normalized))
        robustness.append(cast(RobustnessTuple, ordered))

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -mean_ranks[number - 1],
                -robustness[number - 1][0],
                -robustness[number - 1][1],
                -robustness[number - 1][2],
                number,
            ),
        )
    )
    return FusedNumberRanking(
        ORDERED_NUMBERS=ordered_numbers,
        MEAN_RANKS=tuple(mean_ranks),
        ROBUSTNESS=tuple(robustness),
        WINDOW_RANKINGS=rankings,
    )


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedNumberRanking:
    """Calculate the complete causal multiscale official-null ranking."""

    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _rank_validated_window(prior_history, window) for window in FEATURE_WINDOWS
    )
    return fuse_window_rankings(cast(tuple[WindowRanking, WindowRanking, WindowRanking], rankings))


def produce_b649_multiscale_official_null_z2_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket official-null source universe."""

    fused = calculate_fused_number_ranking(history, target_index)
    top10 = fused.TOP_NUMBERS
    if len(top10) != TOP_NUMBER_COUNT:
        raise RuntimeError("fused ranking did not produce exactly ten top numbers")

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(Ticket, tuple(sorted(top10[position] for position in rank_positions)))
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError(
            f"source universe produced {len(source_tickets)} tickets, expected "
            f"{SOURCE_CANDIDATE_TICKET_COUNT}"
        )
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = produce_b649_multiscale_official_null_z2_ranked_pool_v1
build_source_ticket_universe = produce_b649_multiscale_official_null_z2_ranked_pool_v1
produce_b649_multiscale_official_null_surprise_ranked_pool_v1 = (
    produce_b649_multiscale_official_null_z2_ranked_pool_v1
)


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
    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    return f"BMSGV1_NB_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one official-null hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_NB_{signature_hash[:16]}",
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
        "produce_b649_multiscale_official_null_surprise_multiticket_"
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
        "EXPECTED_COUNT_RULE": EXPECTED_COUNT_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LAST_HIT_GAP_USED": LAST_HIT_GAP_USED,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NULL_DIRECTION_RULE": NULL_DIRECTION_RULE,
        "NULL_VARIANCE_RULE": NULL_VARIANCE_RULE,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OFFICIAL_NULL_P0": OFFICIAL_NULL_P0,
        "OFFICIAL_NULL_Z2_RULE": OFFICIAL_NULL_Z2_RULE,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "PRIMARY_SCORE": PRIMARY_SCORE,
        "PRIMARY_SCORE_ARITHMETIC": PRIMARY_SCORE_ARITHMETIC,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SIGN_DIRECTION_USED_FOR_RANKING": SIGN_DIRECTION_USED_FOR_RANKING,
        "SIGNED_NULL_RESIDUAL_RULE": SIGNED_NULL_RESIDUAL_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TICKET_COUNT": ticket_count,
        "TEMPORAL_ORDER_USED_WITHIN_WINDOW": TEMPORAL_ORDER_USED_WITHIN_WINDOW,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
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
            semantic_record = _candidate_semantic_record(constructor_id, ticket_count)
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError("candidate ID collision in frozen null hypothesis matrix")
            semantic_proxy: Mapping[str, object] = MappingProxyType(semantic_record)
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(constructor_id, ticket_count),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(authorities):
        raise RuntimeError("candidate signature collision in frozen null matrix")
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

CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = CANDIDATE_METADATA
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
    """Return the candidate ID for one frozen constructor/budget pair."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[(constructor_id, ticket_count)]
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
    source_tickets = produce_source_ticket_universe(history, target_index)
    if constructor_id == "B649_CANDIDATE_SET_LOW_OVERLAP_V1":
        return _constructors.construct_b649_candidate_set_low_overlap_v1(
            source_tickets, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1":
        return _constructors.construct_b649_candidate_set_exposure_balanced_v1(
            source_tickets, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1":
        return _constructors.construct_b649_candidate_set_hybrid_diversity_v1(
            source_tickets, ticket_count
        )
    raise KeyError(f"unknown constructor ID: {constructor_id}")


def produce_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one of the nine frozen official-null candidate portfolios."""

    try:
        metadata = CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate ID: {candidate_id}") from error
    return _produce_named_candidate(
        metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT, history, target_index
    )


produce_biglotto_multi_ticket_candidate = produce_candidate_portfolio
produce_multi_ticket_candidate = produce_candidate_portfolio
produce_biglotto_multiscale_official_null_surprise_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_biglotto_multiscale_official_null_z2_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_b649_multiscale_official_null_z2_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_b649_multiscale_official_null_surprise_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_b649_multi_ticket_candidate = produce_candidate_portfolio


def produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


# The explicit Z2 spellings are aliases, not alternate candidate behavior.
produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k5 = (
    produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k5
)
produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k10 = (
    produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k10
)
produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k20 = (
    produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k20
)
produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k5 = (
    produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k5
)
produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k10 = (
    produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k10
)
produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k20 = (
    produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k20
)
produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k5 = (
    produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k5
)
produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k10 = (
    produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k10
)
produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k20 = (
    produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k20
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
    "EXPECTED_COUNT_RULE",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_WINDOWS",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LAST_HIT_GAP_USED",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NULL_DIRECTION_RULE",
    "NULL_VARIANCE_RULE",
    "NUMBER_DOMAIN",
    "OFFICIAL_NULL_P0",
    "OFFICIAL_NULL_Z2_RULE",
    "OUTPUT_SHAPE",
    "P0",
    "PARAMETER_SELECTION_RULE",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "PRIMARY_SCORE",
    "PRIMARY_SCORE_ARITHMETIC",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SIGNED_NULL_RESIDUAL_RULE",
    "SIGN_DIRECTION_USED_FOR_RANKING",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_NUMBER_POOL_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TEMPORAL_ORDER_USED_WITHIN_WINDOW",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "CandidateIdentity",
    "CandidateMetadata",
    "FusedNumberRanking",
    "FusedRanking",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "NumberNullCalculation",
    "RationalRanks",
    "Ticket",
    "TicketPortfolio",
    "WindowRanking",
    "build_source_ticket_universe",
    "calculate_expected_count",
    "calculate_fused_number_ranking",
    "calculate_null_direction",
    "calculate_null_variance",
    "calculate_occurrences",
    "calculate_official_null_z2",
    "calculate_signed_null_residual",
    "calculate_window_counts",
    "calculate_window_ranking",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "direction_for_count",
    "expected_count",
    "fuse_window_rankings",
    "null_direction",
    "null_variance",
    "official_null_expected_count",
    "official_null_signed_residual",
    "official_null_surprise_z2",
    "official_null_variance",
    "official_null_z2",
    "produce_b649_multi_ticket_candidate",
    "produce_b649_multiscale_official_null_surprise_multi_ticket_candidate",
    "produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_official_null_surprise_ranked_pool_v1",
    "produce_b649_multiscale_official_null_z2_multi_ticket_candidate",
    "produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_official_null_z2_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_official_null_z2_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_official_null_z2_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_official_null_z2_ranked_pool_v1",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "signature_hash_for_semantics",
    "signed_null_residual",
    "validate_prior_history",
]
