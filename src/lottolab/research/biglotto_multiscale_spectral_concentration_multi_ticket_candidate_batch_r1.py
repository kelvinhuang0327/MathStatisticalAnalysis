"""Causal BigLotto multiscale spectral-concentration candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1.

For every legal number and each fixed strictly-prior window, its binary
appearance series is mean-centered exactly.  Spectral concentration is the
full-spectrum inverse-participation ratio, calculated from the exact circular
autocorrelation identity rather than numerical transform output.  Equal rank
aggregation across the 50, 300, and 750 windows produces the top-number pool;
the pool is expanded into all 210 six-number source tickets and passed to the
three frozen multi-ticket constructors.

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
type ExactSeries = tuple[Fraction, ...]
type RobustnessTuple = tuple[Fraction, Fraction, Fraction]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "SIGNAL_FOURIER"
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

BINARY_APPEARANCE_RULE: Final[str] = (
    "Y_W,n(t)=1_IF_NUMBER_N_APPEARS_IN_WINDOW_DRAW_T_ELSE_0;"
    "T_CHRONOLOGICAL_OLDEST_TO_NEWEST"
)
MEAN_CENTERING_RULE: Final[str] = (
    "COUNT_W(n)=SUM_t(Y_W,n(t));MEAN_W(n)=COUNT_W(n)/W;"
    "Z_W,n(t)=Y_W,n(t)-MEAN_W(n);EXACT_FRACTION"
)
CENTERING_RULE: Final[str] = "EXACT_MEAN_CENTERED_BINARY_APPEARANCE"
CIRCULAR_AUTOCORRELATION_RULE: Final[str] = (
    "R_W,n(l)=SUM_t(Z_W,n(t)*Z_W,n((t+l)MOD_W));"
    "l=0..W-1;EXACT_RATIONAL"
)
SPECTRAL_MEASURE: Final[str] = "FULL_SPECTRUM_INVERSE_PARTICIPATION_RATIO"
AUTHORITATIVE_COMPUTATION: Final[str] = (
    "EXACT_CIRCULAR_AUTOCORRELATION_PARSEVAL_WIENER_KHINCHIN_IDENTITY"
)
SPECTRAL_IPR_RULE: Final[str] = (
    "R(0)>0=>SUM_l(R(l)^2)/(W*R(0)^2);R(0)=0=>0;EXACT_RATIONAL"
)
PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE: Final[str] = (
    "R(0)>0=>MAX_l=1..FLOOR(W/2)(ABS(R(l))/R(0));R(0)=0=>0;EXACT_RATIONAL"
)
PER_WINDOW_RANKING_RULE: Final[str] = (
    "SPECTRAL_IPR_DESCENDING_PEAK_NORMALIZED_CIRCULAR_AUTOCORR_DESCENDING_NUMBER_ASCENDING"
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
NATIVE_TICKET_COUNT: Final[str] = "TICKET_COUNT"
FLOATING_FFT_USED_FOR_RANKING: Final[str] = "NO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_FULL_SPECTRUM_PERIODIC_STRUCTURE_CONCENTRATION"
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
    """Immutable authority metadata for the spectral source universe."""

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
    BINARY_APPEARANCE_RULE: str
    MEAN_CENTERING_RULE: str
    CENTERING_RULE: str
    CIRCULAR_AUTOCORRELATION_RULE: str
    SPECTRAL_MEASURE: str
    AUTHORITATIVE_COMPUTATION: str
    SPECTRAL_IPR_RULE: str
    PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE: str
    PER_WINDOW_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    FLOATING_FFT_USED_FOR_RANKING: str
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
    BINARY_APPEARANCE_RULE=BINARY_APPEARANCE_RULE,
    MEAN_CENTERING_RULE=MEAN_CENTERING_RULE,
    CENTERING_RULE=CENTERING_RULE,
    CIRCULAR_AUTOCORRELATION_RULE=CIRCULAR_AUTOCORRELATION_RULE,
    SPECTRAL_MEASURE=SPECTRAL_MEASURE,
    AUTHORITATIVE_COMPUTATION=AUTHORITATIVE_COMPUTATION,
    SPECTRAL_IPR_RULE=SPECTRAL_IPR_RULE,
    PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE=PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE,
    PER_WINDOW_RANKING_RULE=PER_WINDOW_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    FLOATING_FFT_USED_FOR_RANKING=FLOATING_FFT_USED_FOR_RANKING,
    EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "AUTHORITATIVE_COMPUTATION": AUTHORITATIVE_COMPUTATION,
        "BINARY_APPEARANCE_RULE": BINARY_APPEARANCE_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CENTERING_RULE": CENTERING_RULE,
        "CIRCULAR_AUTOCORRELATION_RULE": CIRCULAR_AUTOCORRELATION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "FLOATING_FFT_USED_FOR_RANKING": FLOATING_FFT_USED_FOR_RANKING,
        "HISTORY_ORDER": HISTORY_ORDER,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MEAN_CENTERING_RULE": MEAN_CENTERING_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE": (
            PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE
        ),
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "SPECTRAL_IPR_RULE": SPECTRAL_IPR_RULE,
        "SPECTRAL_MEASURE": SPECTRAL_MEASURE,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class NumberSpectralCalculation:
    """Exact observable signal state for one number in one fixed window."""

    NUMBER: int
    WINDOW: int
    OCCURRENCE_COUNT: int
    MEAN: Fraction
    APPEARANCE_SERIES: tuple[int, ...]
    CENTERED_SERIES: ExactSeries
    CIRCULAR_AUTOCORRELATIONS: ExactSeries
    R0: Fraction
    SPECTRAL_IPR: Fraction
    PEAK_NORMALIZED_CIRCULAR_AUTOCORR: Fraction
    POSITION: int
    NORMALIZED_RANK: Fraction

    @property
    def MEAN_FRACTION(self) -> Fraction:
        return self.MEAN

    @property
    def R_ZERO(self) -> Fraction:
        return self.R0

    @property
    def SPECTRAL_IPR_SCORE(self) -> Fraction:
        return self.SPECTRAL_IPR

    @property
    def PEAK_NORMALIZED_CIRCULAR_AUTOCORRELATION(self) -> Fraction:
        return self.PEAK_NORMALIZED_CIRCULAR_AUTOCORR


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Window-specific exact spectral ranking for numbers 1..49."""

    WINDOW: int
    WINDOW_DRAW_COUNT: int
    OCCURRENCE_COUNTS: tuple[int, ...]
    MEANS: tuple[Fraction, ...]
    SPECTRAL_IPRS: tuple[Fraction, ...]
    PEAK_NORMALIZED_CIRCULAR_AUTOCORRS: tuple[Fraction, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]
    CALCULATIONS: tuple[NumberSpectralCalculation, ...]

    @property
    def DRAW_COUNT(self) -> int:
        return self.WINDOW_DRAW_COUNT

    @property
    def SPECTRAL_IPR_SCORES(self) -> tuple[Fraction, ...]:
        return self.SPECTRAL_IPRS

    @property
    def PEAK_NORMALIZED_CIRCULAR_AUTOCORRELATIONS(self) -> tuple[Fraction, ...]:
        return self.PEAK_NORMALIZED_CIRCULAR_AUTOCORRS

    def occurrence_count(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1]

    def mean(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEANS[number - 1]

    def spectral_ipr(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SPECTRAL_IPRS[number - 1]

    def peak_normalized_circular_autocorr(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PEAK_NORMALIZED_CIRCULAR_AUTOCORRS[number - 1]

    def peak_normalized_circular_autocorrelation(self, number: int) -> Fraction:
        return self.peak_normalized_circular_autocorr(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    def calculation_for(self, number: int) -> NumberSpectralCalculation:
        _validate_number(number)
        return self.CALCULATIONS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedRanking:
    """Equal rank aggregation across the three preregistered windows."""

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


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in FEATURE_WINDOWS:
        raise ValueError(f"window must be one of {FEATURE_WINDOWS}, got {window}")


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

    sorted_numbers = tuple(sorted(numbers))
    for left, right in pairwise(sorted_numbers):
        if left == right:
            raise ValueError(f"history[{draw_index}] contains duplicate number {left}")
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
        _validate_draw(raw_draw, draw_index) for draw_index, raw_draw in enumerate(prefix)
    )


def _window_draws(
    valid_history: tuple[HistoryDraw, ...], target_index: int, window: int
) -> tuple[HistoryDraw, ...]:
    _validate_window(window)
    return valid_history[target_index - window : target_index]


def _binary_appearance_series(
    window_draws: Sequence[HistoryDraw], number: int
) -> tuple[int, ...]:
    _validate_number(number)
    return tuple(1 if number in draw else 0 for draw in window_draws)


def binary_appearance_series(
    history: HistoryInput, target_index: int, window: int, number: int
) -> tuple[int, ...]:
    """Return the exact chronological binary appearance series for one number."""

    valid_history = validate_prior_history(history, target_index)
    return _binary_appearance_series(_window_draws(valid_history, target_index, window), number)


appearance_series_for_number = binary_appearance_series


def _exact_fraction(value: object) -> Fraction:
    if type(value) is int:
        return Fraction(value, 1)
    if isinstance(value, Fraction):
        return value
    raise TypeError("exact series values must be integers or fractions.Fraction")


def mean_centered_binary_series(series: Iterable[int]) -> ExactSeries:
    """Mean-center a non-empty binary series using exact rational arithmetic."""

    values = tuple(series)
    if not values:
        raise ValueError("binary appearance series must not be empty")
    if any(type(value) is not int or value not in (0, 1) for value in values):
        raise ValueError("binary appearance series must contain only 0 and 1")

    mean = Fraction(sum(values), len(values))
    centered = tuple(Fraction(value, 1) - mean for value in values)
    if sum(centered, Fraction(0, 1)) != 0:
        raise RuntimeError("exact mean-centered series does not sum to zero")
    return centered


mean_center_binary_series = mean_centered_binary_series


def circular_autocorrelation(series: Iterable[object]) -> ExactSeries:
    """Return exact circular autocorrelation for every lag of an exact series."""

    values = tuple(_exact_fraction(value) for value in series)
    if not values:
        raise ValueError("series must not be empty")

    length = len(values)
    result = tuple(
        sum(
            (values[index] * values[(index + lag) % length] for index in range(length)),
            Fraction(0, 1),
        )
        for lag in range(length)
    )
    if result[0] < 0:
        raise RuntimeError("circular autocorrelation R(0) must be non-negative")
    for lag in range(1, length):
        if result[lag] != result[(length - lag) % length]:
            raise RuntimeError("circular autocorrelation must be symmetric")
    return result


def _binary_circular_autocorrelation(
    appearance_series: tuple[int, ...], occurrence_count: int
) -> ExactSeries:
    """Calculate centered circular autocorrelation with exact integer lag counts."""

    length = len(appearance_series)
    if length == 0:
        raise ValueError("binary appearance series must not be empty")
    positions = tuple(
        index for index, value in enumerate(appearance_series) if value == 1
    )
    lag_counts = [0] * length
    for left in positions:
        for right in positions:
            lag_counts[(right - left) % length] += 1

    centered_offset = Fraction(occurrence_count * occurrence_count, length)
    result = tuple(Fraction(count, 1) - centered_offset for count in lag_counts)
    if result[0] < 0:
        raise RuntimeError("circular autocorrelation R(0) must be non-negative")
    for lag in range(1, length):
        if result[lag] != result[(length - lag) % length]:
            raise RuntimeError("circular autocorrelation must be symmetric")
    return result


def spectral_ipr_from_circular_autocorrelation(
    autocorrelations: Iterable[object],
) -> Fraction:
    """Calculate full-spectrum IPR from exact circular autocorrelation values."""

    values = tuple(_exact_fraction(value) for value in autocorrelations)
    if not values:
        raise ValueError("autocorrelation series must not be empty")
    r0 = values[0]
    if r0 < 0:
        raise ValueError("autocorrelation R(0) must be non-negative")
    if r0 == 0:
        return Fraction(0, 1)

    numerator = sum((value * value for value in values), Fraction(0, 1))
    denominator = len(values) * r0 * r0
    return numerator / denominator


spectral_ipr = spectral_ipr_from_circular_autocorrelation


def peak_normalized_circular_autocorrelation(
    autocorrelations: Iterable[object],
) -> Fraction:
    """Return the exact positive-lag peak normalized circular autocorrelation."""

    values = tuple(_exact_fraction(value) for value in autocorrelations)
    if not values:
        raise ValueError("autocorrelation series must not be empty")
    r0 = values[0]
    if r0 < 0:
        raise ValueError("autocorrelation R(0) must be non-negative")
    if r0 == 0:
        return Fraction(0, 1)

    peak = max(
        (abs(values[lag]) / r0 for lag in range(1, len(values) // 2 + 1)),
        default=Fraction(0, 1),
    )
    return peak


peak_normalized_circular_autocorr = peak_normalized_circular_autocorrelation


def calculate_window_rankings(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Calculate exact full-spectrum concentration rankings for one window."""

    _validate_window(window)
    valid_history = validate_prior_history(history, target_index)
    window_draws = _window_draws(valid_history, target_index, window)

    occurrences: list[int] = []
    means: list[Fraction] = []
    iprs: list[Fraction] = []
    peaks: list[Fraction] = []
    raw_calculations: list[NumberSpectralCalculation] = []

    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        appearance = _binary_appearance_series(window_draws, number)
        occurrence_count = sum(appearance)
        mean = Fraction(occurrence_count, window)
        centered = mean_centered_binary_series(appearance)
        autocorrelations = _binary_circular_autocorrelation(appearance, occurrence_count)
        direct_autocorrelations = circular_autocorrelation(centered) if window <= 16 else ()
        if direct_autocorrelations and autocorrelations != direct_autocorrelations:
            raise RuntimeError("binary autocorrelation shortcut disagrees with exact definition")
        if sum(centered, Fraction(0, 1)) != 0:
            raise RuntimeError("centered binary series does not sum to zero")

        ipr = spectral_ipr_from_circular_autocorrelation(autocorrelations)
        peak = peak_normalized_circular_autocorrelation(autocorrelations)
        occurrences.append(occurrence_count)
        means.append(mean)
        iprs.append(ipr)
        peaks.append(peak)
        raw_calculations.append(
            NumberSpectralCalculation(
                NUMBER=number,
                WINDOW=window,
                OCCURRENCE_COUNT=occurrence_count,
                MEAN=mean,
                APPEARANCE_SERIES=appearance,
                CENTERED_SERIES=centered,
                CIRCULAR_AUTOCORRELATIONS=autocorrelations,
                R0=autocorrelations[0],
                SPECTRAL_IPR=ipr,
                PEAK_NORMALIZED_CIRCULAR_AUTOCORR=peak,
                POSITION=0,
                NORMALIZED_RANK=Fraction(0, 1),
            )
        )

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-iprs[number - 1], -peaks[number - 1], number),
        )
    )
    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    normalized_ranks = [Fraction(0, 1)] * len(positions)
    for position_zero_based, number in enumerate(ordered_numbers):
        position = position_zero_based + 1
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    calculations = tuple(
        NumberSpectralCalculation(
            NUMBER=calculation.NUMBER,
            WINDOW=calculation.WINDOW,
            OCCURRENCE_COUNT=calculation.OCCURRENCE_COUNT,
            MEAN=calculation.MEAN,
            APPEARANCE_SERIES=calculation.APPEARANCE_SERIES,
            CENTERED_SERIES=calculation.CENTERED_SERIES,
            CIRCULAR_AUTOCORRELATIONS=calculation.CIRCULAR_AUTOCORRELATIONS,
            R0=calculation.R0,
            SPECTRAL_IPR=calculation.SPECTRAL_IPR,
            PEAK_NORMALIZED_CIRCULAR_AUTOCORR=calculation.PEAK_NORMALIZED_CIRCULAR_AUTOCORR,
            POSITION=positions[calculation.NUMBER - 1],
            NORMALIZED_RANK=normalized_ranks[calculation.NUMBER - 1],
        )
        for calculation in raw_calculations
    )

    return WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=window,
        OCCURRENCE_COUNTS=tuple(occurrences),
        MEANS=tuple(means),
        SPECTRAL_IPRS=tuple(iprs),
        PEAK_NORMALIZED_CIRCULAR_AUTOCORRS=tuple(peaks),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
        CALCULATIONS=calculations,
    )


rank_numbers_by_window = calculate_window_rankings


def fuse_window_rankings(
    rankings: tuple[WindowRanking, WindowRanking, WindowRanking],
) -> FusedRanking:
    """Fuse the three exact window rankings by equal rank aggregation."""

    if len(rankings) != 3:
        raise ValueError("exactly three window rankings required for fusion")
    r50, r300, r750 = rankings
    if (r50.WINDOW, r300.WINDOW, r750.WINDOW) != FEATURE_WINDOWS:
        raise ValueError(f"window rankings must correspond to windows {FEATURE_WINDOWS}")

    mean_ranks: list[Fraction] = []
    robustness_tuples: list[RobustnessTuple] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = (
            r50.normalized_rank(number),
            r300.normalized_rank(number),
            r750.normalized_rank(number),
        )
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / 3)
        ordered = tuple(sorted(normalized))
        robustness_tuples.append((ordered[0], ordered[1], ordered[2]))

    fused_sort_keys: list[
        tuple[tuple[Fraction, Fraction, Fraction, Fraction, int], int]
    ] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        robustness = robustness_tuples[number - 1]
        key = (
            -mean_ranks[number - 1],
            -robustness[0],
            -robustness[1],
            -robustness[2],
            number,
        )
        fused_sort_keys.append((key, number))
    fused_sort_keys.sort(key=lambda item: item[0])
    ordered_numbers = tuple(number for _, number in fused_sort_keys)

    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for position_zero_based, number in enumerate(ordered_numbers):
        positions[number - 1] = position_zero_based + 1

    return FusedRanking(
        WINDOW_RANKINGS=rankings,
        MEAN_RANKS=tuple(mean_ranks),
        ROBUSTNESS_TUPLES=tuple(robustness_tuples),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        TOP_NUMBERS=ordered_numbers[:TOP_NUMBER_COUNT],
    )


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedRanking:
    """Calculate the complete causal multiscale spectral ranking."""

    ranking_50 = calculate_window_rankings(history, target_index, 50)
    ranking_300 = calculate_window_rankings(history, target_index, 300)
    ranking_750 = calculate_window_rankings(history, target_index, 750)
    return fuse_window_rankings((ranking_50, ranking_300, ranking_750))


def produce_b649_multiscale_spectral_ipr_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket spectral source universe."""

    fused = calculate_fused_number_ranking(history, target_index)
    top10 = fused.TOP_NUMBERS
    if len(top10) != TOP_NUMBER_COUNT:
        raise RuntimeError(
            f"fused ranking produced {len(top10)} top numbers, expected {TOP_NUMBER_COUNT}"
        )

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(Ticket, tuple(sorted(top10[position] for position in rank_positions)))
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


produce_source_ticket_universe = produce_b649_multiscale_spectral_ipr_ranked_pool_v1
build_source_ticket_universe = produce_b649_multiscale_spectral_ipr_ranked_pool_v1


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
    """Derive the frozen spectral candidate ID."""

    return f"BMSGV1_SP_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one spectral hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_SP_{signature_hash[:16]}",
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
        "produce_b649_multiscale_spectral_concentration_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "AUTHORITATIVE_COMPUTATION": AUTHORITATIVE_COMPUTATION,
        "BINARY_APPEARANCE_RULE": BINARY_APPEARANCE_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CENTERING_RULE": CENTERING_RULE,
        "CIRCULAR_AUTOCORRELATION_RULE": CIRCULAR_AUTOCORRELATION_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "FLOATING_FFT_USED_FOR_RANKING": FLOATING_FFT_USED_FOR_RANKING,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MEAN_CENTERING_RULE": MEAN_CENTERING_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE": (
            PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE
        ),
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "SPECTRAL_IPR_RULE": SPECTRAL_IPR_RULE,
        "SPECTRAL_MEASURE": SPECTRAL_MEASURE,
        "TICKET_COUNT": ticket_count,
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
                raise RuntimeError("candidate ID collision in frozen spectral hypothesis matrix")
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
        raise RuntimeError("candidate signature collision in frozen spectral matrix")
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
    """Return the candidate ID for a constructor and native ticket count."""

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
    universe = produce_source_ticket_universe(history, target_index)
    if constructor_id == "B649_CANDIDATE_SET_LOW_OVERLAP_V1":
        return _constructors.construct_b649_candidate_set_low_overlap_v1(universe, ticket_count)
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
    """Produce the portfolio for any of the nine spectral candidate IDs."""

    try:
        metadata = CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate ID: {candidate_id}") from error
    return _produce_named_candidate(
        metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT, history, target_index
    )


produce_biglotto_multi_ticket_candidate = produce_candidate_portfolio
produce_multi_ticket_candidate = produce_candidate_portfolio
produce_biglotto_multiscale_spectral_concentration_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_biglotto_multiscale_spectral_ipr_multi_ticket_candidate = (
    produce_candidate_portfolio
)


def produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


__all__ = [
    "AUTHORITATIVE_COMPUTATION",
    "BINARY_APPEARANCE_RULE",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CENTERING_RULE",
    "CIRCULAR_AUTOCORRELATION_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_WINDOWS",
    "FLOATING_FFT_USED_FOR_RANKING",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "MEAN_CENTERING_RULE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_NUMBER_POOL_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "SPECTRAL_IPR_RULE",
    "SPECTRAL_MEASURE",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "CandidateIdentity",
    "CandidateMetadata",
    "ExactSeries",
    "FusedRanking",
    "InsufficientHistoryError",
    "NumberSpectralCalculation",
    "SourceUniverseMetadata",
    "WindowRanking",
    "appearance_series_for_number",
    "binary_appearance_series",
    "build_source_ticket_universe",
    "calculate_fused_number_ranking",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "circular_autocorrelation",
    "derive_candidate_identity",
    "fuse_window_rankings",
    "mean_center_binary_series",
    "mean_centered_binary_series",
    "peak_normalized_circular_autocorr",
    "peak_normalized_circular_autocorrelation",
    "produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_spectral_ipr_ranked_pool_v1",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_multiscale_spectral_concentration_multi_ticket_candidate",
    "produce_biglotto_multiscale_spectral_ipr_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "signature_hash_for_semantics",
    "spectral_ipr",
    "spectral_ipr_from_circular_autocorrelation",
    "validate_prior_history",
]
