"""Causal BigLotto multiscale omission-pressure candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1.

For every number, its current trailing omission gap is measured relative to
its own boundary-stabilized recurrence cycle separately over fixed 50, 300,
and 750 strictly-prior windows using exact rational arithmetic.

The three independent omission-pressure rankings are fused with fixed equal
rank aggregation.  The top 10 numbers generate exactly C(10, 6) = 210 ordered
source tickets, which are passed directly to the three frozen portfolio
constructors at native budgets 5, 10, and 20 to produce exactly 9 frozen
hypotheses.

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
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "GAP_OMISSION"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
OMISSION_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
WINDOWS: Final[tuple[int, int, int]] = OMISSION_WINDOWS
SOURCE_WINDOWS: Final[tuple[int, int, int]] = OMISSION_WINDOWS
MINIMUM_HISTORY: Final[int] = 750
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

OCCURRENCE_COUNT_RULE: Final[str] = (
    "OCCURRENCE_W(n)=COUNT_DRAWS_IN_WINDOW_CONTAINING_n;0<=OCCURRENCE<=W;EXACT_INTEGER"
)
CURRENT_GAP_RULE: Final[str] = (
    "CURRENT_GAP_W(n)=TRAILING_DRAWS_SINCE_MOST_RECENT_OCCURRENCE;0<=CURRENT_GAP<=W;W_IF_ABSENT"
)
RECURRENCE_CYCLE_RULE: Final[str] = (
    "RECURRENCE_CYCLE_W(n)=(W+1)/(OCCURRENCE_W(n)+1);EXACT_RATIONAL"
)
BOUNDARY_CORRECTION_RULE: Final[str] = "FIXED_ADD_ONE_WINDOW_AND_OCCURRENCE"
OMISSION_PRESSURE_RULE: Final[str] = (
    "OMISSION_PRESSURE_W(n)=CURRENT_GAP_W(n)/RECURRENCE_CYCLE_W(n)="
    "CURRENT_GAP_W(n)*(OCCURRENCE_W(n)+1)/(W+1);EXACT_RATIONAL;ZERO_IF_GAP_ZERO"
)
PER_WINDOW_RANKING_RULE: Final[str] = (
    "OMISSION_PRESSURE_DESCENDING_CURRENT_GAP_DESCENDING_"
    "OCCURRENCE_DESCENDING_NUMBER_ASCENDING"
)
WINDOW_NORMALIZATION_RULE: Final[str] = "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+"
    "NORMALIZED_750)/3;ROBUSTNESS_TIE_BREAK"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_RECURRENCE_GAP_PRESSURE_STRUCTURE"
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
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "NUMBER_EXPOSURE_DIVERSITY",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
            "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
        ),
    }
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the omission pressure source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    OMISSION_WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    OCCURRENCE_COUNT_RULE: str
    CURRENT_GAP_RULE: str
    RECURRENCE_CYCLE_RULE: str
    BOUNDARY_CORRECTION_RULE: str
    OMISSION_PRESSURE_RULE: str
    PER_WINDOW_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    TOP_NUMBER_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
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
    OMISSION_WINDOWS=OMISSION_WINDOWS,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    OCCURRENCE_COUNT_RULE=OCCURRENCE_COUNT_RULE,
    CURRENT_GAP_RULE=CURRENT_GAP_RULE,
    RECURRENCE_CYCLE_RULE=RECURRENCE_CYCLE_RULE,
    BOUNDARY_CORRECTION_RULE=BOUNDARY_CORRECTION_RULE,
    OMISSION_PRESSURE_RULE=OMISSION_PRESSURE_RULE,
    PER_WINDOW_RANKING_RULE=PER_WINDOW_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "BOUNDARY_CORRECTION_RULE": BOUNDARY_CORRECTION_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CURRENT_GAP_RULE": CURRENT_GAP_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "HISTORY_ORDER": HISTORY_ORDER,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OCCURRENCE_COUNT_RULE": OCCURRENCE_COUNT_RULE,
        "OMISSION_PRESSURE_RULE": OMISSION_PRESSURE_RULE,
        "OMISSION_WINDOWS": OMISSION_WINDOWS,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RECURRENCE_CYCLE_RULE": RECURRENCE_CYCLE_RULE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Exact counts, gaps, cycles, omission pressures, and ranks for one window."""

    WINDOW: int
    WINDOW_DRAW_COUNT: int
    OCCURRENCE_COUNTS: tuple[int, ...]
    CURRENT_GAPS: tuple[int, ...]
    RECURRENCE_CYCLES: tuple[Fraction, ...]
    OMISSION_PRESSURES: RationalRanks
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: RationalRanks

    @property
    def SCORES(self) -> RationalRanks:
        """Compatibility alias for exact omission pressure scores."""

        return self.OMISSION_PRESSURES

    @property
    def DRAW_COUNT(self) -> int:
        """Return the W strictly prior draws used by this window."""

        return self.WINDOW_DRAW_COUNT

    def occurrence_count(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1]

    def current_gap(self, number: int) -> int:
        _validate_number(number)
        return self.CURRENT_GAPS[number - 1]

    def recurrence_cycle(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RECURRENCE_CYCLES[number - 1]

    def omission_pressure(self, number: int) -> Fraction:
        _validate_number(number)
        return self.OMISSION_PRESSURES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.omission_pressure(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Three-window fusion with exact rational rank means and robustness."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_RANKS: RationalRanks
    ROBUSTNESS: tuple[tuple[Fraction, Fraction, Fraction], ...]
    WINDOW_RANKINGS: tuple[WindowRanking, ...]

    @property
    def TOP_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS[:TOP_NUMBER_COUNT]

    def mean_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEAN_RANKS[number - 1]

    def robustness(self, number: int) -> tuple[Fraction, Fraction, Fraction]:
        _validate_number(number)
        return self.ROBUSTNESS[number - 1]


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
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
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return an immutable copy of only the strictly prior validated history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(
        _validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix)
    )


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in OMISSION_WINDOWS:
        raise ValueError(f"window must be one of {OMISSION_WINDOWS}")


def calculate_occurrences(
    window_draws: Sequence[HistoryDraw],
) -> tuple[int, ...]:
    """Count occurrences of each number in 1..49 across the window draws."""

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    counts = [0] * domain_size
    for draw in window_draws:
        for number in draw:
            counts[number - 1] += 1
    return tuple(counts)


def calculate_current_gaps(
    window_draws: Sequence[HistoryDraw],
) -> tuple[int, ...]:
    """Calculate the trailing omission gap for each number in 1..49 in the window.

    Scans from newest (draw -1) to oldest (draw 0).
    If a number appears at draw -1 (the latest completed draw), current gap is 0.
    If a number last appeared k draws before the latest, current gap is k.
    If a number does not appear anywhere in the window of length W, current gap is W.
    """

    window_len = len(window_draws)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    gaps = [window_len] * domain_size
    seen: set[int] = set()

    for gap_index, draw in enumerate(reversed(window_draws)):
        for number in draw:
            if number not in seen:
                gaps[number - 1] = gap_index
                seen.add(number)
        if len(seen) == domain_size:
            break

    return tuple(gaps)


def calculate_recurrence_cycles(
    occurrences: Sequence[int], window: int
) -> tuple[Fraction, ...]:
    """Calculate the boundary-stabilized recurrence cycle for each number.

    RECURRENCE_CYCLE_W(n) = (W + 1) / (OCCURRENCE_W(n) + 1) using exact rational arithmetic.
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(occurrences) != domain_size:
        raise ValueError(f"occurrences must contain exactly {domain_size} values")

    return tuple(
        Fraction(window + 1, occ + 1) for occ in occurrences
    )


def calculate_omission_pressures(
    current_gaps: Sequence[int], occurrences: Sequence[int], window: int
) -> RationalRanks:
    """Calculate exact omission pressure for each number.

    OMISSION_PRESSURE_W(n) = CURRENT_GAP_W(n) / RECURRENCE_CYCLE_W(n)
                           = CURRENT_GAP_W(n) * (OCCURRENCE_W(n) + 1) / (W + 1)
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(current_gaps) != domain_size:
        raise ValueError(f"current_gaps must contain exactly {domain_size} values")
    if len(occurrences) != domain_size:
        raise ValueError(f"occurrences must contain exactly {domain_size} values")

    return tuple(
        Fraction(gap * (occ + 1), window + 1)
        for gap, occ in zip(current_gaps, occurrences, strict=True)
    )


def _rank_validated_window(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> WindowRanking:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(
            f"window {window} requires at least {window} prior draws"
        )

    window_draws = prior_history[-window:]
    occurrences = calculate_occurrences(window_draws)
    current_gaps = calculate_current_gaps(window_draws)
    recurrence_cycles = calculate_recurrence_cycles(occurrences, window)
    omission_pressures = calculate_omission_pressures(
        current_gaps, occurrences, window
    )

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -omission_pressures[number - 1],
                -current_gaps[number - 1],
                -occurrences[number - 1],
                number,
            ),
        )
    )

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    positions = [0] * domain_size
    normalized_ranks: list[Fraction] = [Fraction(0, 1)] * domain_size
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    return WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=len(window_draws),
        OCCURRENCE_COUNTS=occurrences,
        CURRENT_GAPS=current_gaps,
        RECURRENCE_CYCLES=recurrence_cycles,
        OMISSION_PRESSURES=omission_pressures,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def rank_numbers_by_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Rank numbers using one exact omission pressure window."""

    return _rank_validated_window(
        validate_prior_history(history, target_index), window
    )


def calculate_omission_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Compatibility alias for rank_numbers_by_window."""

    return rank_numbers_by_window(history, target_index, window)


def calculate_omission_scores(
    history: HistoryInput, target_index: int, window: int
) -> RationalRanks:
    """Return the exact omission pressure score vector for one window."""

    return rank_numbers_by_window(history, target_index, window).OMISSION_PRESSURES


def raw_frequency_order_for_window(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return raw frequency order for specificity fixtures."""

    prior_history = validate_prior_history(history, target_index)
    _validate_window(window)
    window_draws = prior_history[-window:]
    occurrences = calculate_occurrences(window_draws)
    return tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-occurrences[number - 1], number),
        )
    )


def raw_gap_order_for_window(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return raw trailing gap order for specificity fixtures."""

    prior_history = validate_prior_history(history, target_index)
    _validate_window(window)
    window_draws = prior_history[-window:]
    gaps = calculate_current_gaps(window_draws)
    return tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-gaps[number - 1], number),
        )
    )


def calculate_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[WindowRanking, WindowRanking, WindowRanking]:
    """Calculate the exact 50/300/750 omission pressure rankings."""

    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _rank_validated_window(prior_history, window) for window in OMISSION_WINDOWS
    )
    return cast(tuple[WindowRanking, WindowRanking, WindowRanking], rankings)


calculate_omission_rankings = calculate_window_rankings


def fuse_window_rankings(
    window_rankings: Sequence[WindowRanking],
) -> FusedNumberRanking:
    """Fuse three window rankings with equal exact rational rank aggregation."""

    if tuple(ranking.WINDOW for ranking in window_rankings) != OMISSION_WINDOWS:
        raise ValueError(
            f"window_rankings must contain windows in order {OMISSION_WINDOWS}"
        )

    mean_ranks: list[Fraction] = []
    robustness: list[tuple[Fraction, Fraction, Fraction]] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = tuple(
            ranking.normalized_rank(number) for ranking in window_rankings
        )
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / len(normalized))
        sorted_ranks = tuple(sorted(normalized))
        robustness.append(cast(tuple[Fraction, Fraction, Fraction], sorted_ranks))

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
        WINDOW_RANKINGS=tuple(window_rankings),
    )


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedNumberRanking:
    """Calculate the final fused number ranking from strictly prior history."""

    return fuse_window_rankings(calculate_window_rankings(history, target_index))


def produce_b649_multiscale_omission_pressure_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket omission-pressure source universe."""

    fused_ranking = calculate_fused_number_ranking(history, target_index)
    top_numbers = fused_ranking.TOP_NUMBERS
    if len(top_numbers) != TOP_NUMBER_COUNT:
        raise RuntimeError(
            "fused ranking did not produce the configured top-number pool"
        )

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(
            Ticket,
            tuple(sorted(top_numbers[position] for position in rank_positions)),
        )
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("source universe did not produce exactly 210 tickets")
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = (
    produce_b649_multiscale_omission_pressure_ranked_pool_v1
)
build_source_ticket_universe = (
    produce_b649_multiscale_omission_pressure_ranked_pool_v1
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
    """Return canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the frozen omission-pressure candidate ID."""

    return f"BMSGV1_OM_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one omission-pressure hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_OM_{signature_hash[:16]}",
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
        "produce_b649_multiscale_omission_pressure_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "BOUNDARY_CORRECTION_RULE": BOUNDARY_CORRECTION_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "CURRENT_GAP_RULE": CURRENT_GAP_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OCCURRENCE_COUNT_RULE": OCCURRENCE_COUNT_RULE,
        "OMISSION_PRESSURE_RULE": OMISSION_PRESSURE_RULE,
        "OMISSION_WINDOWS": OMISSION_WINDOWS,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RECURRENCE_CYCLE_RULE": RECURRENCE_CYCLE_RULE,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
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
                raise RuntimeError(
                    "candidate ID collision in frozen omission pressure hypothesis matrix"
                )
            semantic_proxy: Mapping[str, object] = MappingProxyType(semantic_record)
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
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(authorities):
        raise RuntimeError(
            "candidate signature collision in frozen omission pressure matrix"
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
CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = CANDIDATE_METADATA
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[tuple[str, ...]] = tuple(
    metadata.SIGNATURE_HASH for metadata in CANDIDATE_AUTHORITIES
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the frozen candidate ID for one constructor/budget pair."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[
            (constructor_id, ticket_count)
        ]
    except KeyError as error:
        raise KeyError(
            f"unsupported constructor/budget pair: {constructor_id!r}, {ticket_count!r}"
        ) from error


def _metadata_for_candidate(candidate_id: str) -> CandidateMetadata:
    try:
        return CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate_id: {candidate_id!r}") from error


def produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen omission-pressure portfolio from strictly prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_omission_pressure_multi_ticket_candidate = (
    produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate
)
produce_biglotto_multi_ticket_candidate = (
    produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate
)
produce_multi_ticket_candidate = (
    produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate
)
produce_candidate_portfolio = (
    produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate
)


def _produce_named_candidate(
    constructor_id: str, ticket_count: int, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
        candidate_id_for(constructor_id, ticket_count), history, target_index
    )


def produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


__all__ = [
    "BOUNDARY_CORRECTION_RULE",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "CURRENT_GAP_RULE",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NUMBER_DOMAIN",
    "OCCURRENCE_COUNT_RULE",
    "OMISSION_PRESSURE_RULE",
    "OMISSION_WINDOWS",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "RECURRENCE_CYCLE_RULE",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "FusedNumberRanking",
    "InsufficientHistoryError",
    "WindowRanking",
    "build_source_ticket_universe",
    "calculate_current_gaps",
    "calculate_fused_number_ranking",
    "calculate_occurrences",
    "calculate_omission_pressures",
    "calculate_omission_rankings",
    "calculate_omission_scores",
    "calculate_omission_window",
    "calculate_recurrence_cycles",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_window_rankings",
    "produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_omission_pressure_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_omission_pressure_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_omission_pressure_ranked_pool_v1",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate",
    "produce_biglotto_omission_pressure_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "raw_frequency_order_for_window",
    "raw_gap_order_for_window",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
