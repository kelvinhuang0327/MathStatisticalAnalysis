"""Frozen NF05 checkerboard recurrence-copula constructor for BIG LOTTO.

The module is a standalone exact research computation.  It reads only a
caller-owned causal window of completed six-number draws, builds capped
recurrence ages, and measures each unordered pair with the squared distance
between its empirical checkerboard copula and the independence copula.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Sized
from dataclasses import dataclass, field
from fractions import Fraction
from json import dumps
from types import MappingProxyType
from typing import TypeGuard, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_NF05_CHECKERBOARD_RECURRENCE_COPULA_V1"
DESIGN_NAME = "BIGLOTTO_L2_PAIRWISE_NF05_CHECKERBOARD_RECURRENCE_COPULA_V1"
SEMANTIC_SIGNATURE = "949ab011357554942d530666465765446a782526decaee900a00254f801ec96f"

NUMBER_MIN = 1
NUMBER_MAX = 49
NUMBER_DOMAIN: tuple[int, ...] = tuple(range(NUMBER_MIN, NUMBER_MAX + 1))
DRAW_SIZE = 6
MIN_HISTORY = 256
WINDOW_SIZE = 256
RECURRENCE_CAP = 16
SENTINEL_AGE = 17
RANK_LEVELS = SENTINEL_AGE + 1
PAIR_COUNT = (NUMBER_MAX * (NUMBER_MAX - 1)) // 2
TICKET_COUNT = 13_983_816
PAIR_QUANTUM_SCALE = 1_000_000_000_000_000_000_000_000_000_000

COMPLETE_STATUS = "COMPLETE"
FALLBACK_STATUS = "FALLBACK_INSUFFICIENT_HISTORY"
FAIL_CLOSED_STATUS = "FAIL_CLOSED_NO_TICKET"
FAIL_CLOSED_NO_TICKET = FAIL_CLOSED_STATUS

type Pair = tuple[int, int]
type Draw = tuple[int, ...]
type AgeStream = tuple[int, ...]
type RationalValue = int | Fraction


class BigLottoL2PairwiseCheckerboardError(ValueError):
    """Base class for exact NF05 contract failures."""


class InvalidInputError(BigLottoL2PairwiseCheckerboardError):
    """The cutoff, history, draw, or standalone stream is invalid."""


class NumericInvariantError(BigLottoL2PairwiseCheckerboardError):
    """A frozen exact arithmetic or cardinality invariant failed."""


def _is_non_boolean_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_exact_fraction(value: object, *, label: str) -> Fraction:
    if isinstance(value, bool):
        raise NumericInvariantError(f"{label} must be an exact integer or Fraction")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    raise NumericInvariantError(f"{label} must be an exact integer or Fraction")


def _as_nonnegative_integer(value: object, *, label: str) -> int:
    if not _is_non_boolean_integer(value) or value < 0:
        raise NumericInvariantError(f"{label} must be a non-negative integer")
    return value


def _pair_keys() -> tuple[Pair, ...]:
    return tuple(
        (left, right)
        for left in NUMBER_DOMAIN
        for right in NUMBER_DOMAIN
        if left < right
    )


PAIR_KEYS: tuple[Pair, ...] = _pair_keys()


def _pair_from_object(key: object) -> Pair:
    if not isinstance(key, tuple):
        raise NumericInvariantError("pair keys must be 2-tuples")
    key_values = cast(tuple[object, ...], key)
    if len(key_values) != 2:
        raise NumericInvariantError("pair keys must be 2-tuples")
    left_object, right_object = key_values
    if not _is_non_boolean_integer(left_object) or not _is_non_boolean_integer(right_object):
        raise NumericInvariantError("pair keys must contain non-boolean integers")
    left, right = left_object, right_object
    if left < NUMBER_MIN or right > NUMBER_MAX or left >= right:
        raise NumericInvariantError("pair keys must satisfy 1 <= i < j <= 49")
    return left, right


def _validate_integer_stream(stream: object, *, label: str) -> tuple[int, ...]:
    try:
        values = tuple(cast(Iterable[object], stream))
    except Exception as exc:
        raise InvalidInputError(f"{label} must be an iterable integer stream") from exc
    if not values or any(not _is_non_boolean_integer(value) for value in values):
        raise InvalidInputError(f"{label} must contain at least one non-boolean integer")
    return cast(tuple[int, ...], values)


def _validate_draw(raw_draw: object, *, index: int) -> Draw:
    try:
        raw_values = tuple(cast(Iterable[object], raw_draw))
    except Exception as exc:
        raise InvalidInputError(f"history[{index}] is not an iterable draw") from exc
    if len(raw_values) != DRAW_SIZE:
        raise InvalidInputError(f"history[{index}] must contain exactly six values")
    if any(not _is_non_boolean_integer(value) for value in raw_values):
        raise InvalidInputError(
            f"history[{index}] values must be distinct non-boolean integers in 1..49"
        )
    values = cast(tuple[int, ...], raw_values)
    if len(set(values)) != DRAW_SIZE:
        raise InvalidInputError(f"history[{index}] values must be distinct")
    if any(value < NUMBER_MIN or value > NUMBER_MAX for value in values):
        raise InvalidInputError(f"history[{index}] values must lie in 1..49")
    return tuple(sorted(values))


def _history_length(history: object) -> int:
    try:
        length = len(cast(Sized, history))
    except Exception as exc:
        raise InvalidInputError("history must be a finite indexable sequence") from exc
    if length < 0:
        raise NumericInvariantError("history length must be non-negative")
    return length


def _validated_cutoff(cutoff: object, history_length: int) -> int:
    if not _is_non_boolean_integer(cutoff):
        raise InvalidInputError("cutoff must be a non-boolean integer")
    if cutoff < 0 or cutoff > history_length:
        raise InvalidInputError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return cutoff


def _read_causal_window(history: object, cutoff: int) -> tuple[Draw, ...]:
    indexed_history = cast(Sequence[object], history)
    draws: list[Draw] = []
    for index in range(cutoff - WINDOW_SIZE, cutoff):
        try:
            raw_draw = indexed_history[index]
        except Exception as exc:
            raise InvalidInputError(f"history[{index}] could not be read") from exc
        draws.append(_validate_draw(raw_draw, index=index))
    if len(draws) != WINDOW_SIZE:
        raise NumericInvariantError("causal window length is not 256")
    return tuple(draws)


def _zero_pair_scores() -> dict[Pair, Fraction]:
    return {pair: Fraction(0) for pair in PAIR_KEYS}


def _zero_pair_weights() -> dict[Pair, int]:
    return {pair: 0 for pair in PAIR_KEYS}


def _zero_number_aggregates() -> dict[int, int]:
    return {number: 0 for number in NUMBER_DOMAIN}


def zero_pair_scores() -> Mapping[Pair, Fraction]:
    """Return a fresh canonical all-zero raw pair-score matrix."""

    return MappingProxyType(_zero_pair_scores())


def zero_pair_weights() -> Mapping[Pair, int]:
    """Return a fresh canonical all-zero quantized pair matrix."""

    return MappingProxyType(_zero_pair_weights())


def _age_stream_for_number(draws: Sequence[Draw], number: int) -> AgeStream:
    last_occurrence: int | None = None
    ages: list[int] = []
    for local_time, draw in enumerate(draws):
        if number in draw:
            ages.append(0)
            last_occurrence = local_time
        elif last_occurrence is None:
            ages.append(SENTINEL_AGE)
        else:
            ages.append(min(RECURRENCE_CAP, local_time - last_occurrence))
    return tuple(ages)


def build_recurrence_age_stream(
    draws: Sequence[object], number: object
) -> AgeStream:
    """Build one 0..16/sentinel-17 recurrence-age stream."""

    if not _is_non_boolean_integer(number) or number not in NUMBER_DOMAIN:
        raise InvalidInputError("number must be a non-boolean integer in 1..49")
    normalized = tuple(_validate_draw(draw, index=index) for index, draw in enumerate(draws))
    if not normalized:
        raise InvalidInputError("draws must contain at least one completed draw")
    return _age_stream_for_number(normalized, number)


def build_recurrence_age_streams(
    draws: Sequence[object],
) -> tuple[AgeStream, ...]:
    """Build all 49 recurrence-age streams in numeric order."""

    normalized = tuple(_validate_draw(draw, index=index) for index, draw in enumerate(draws))
    if not normalized:
        raise InvalidInputError("draws must contain at least one completed draw")
    return tuple(_age_stream_for_number(normalized, number) for number in NUMBER_DOMAIN)


@dataclass(frozen=True, slots=True)
class RankInterval:
    """One positive-width contiguous empirical rank interval."""

    value: int
    lower: Fraction
    upper: Fraction

    @property
    def mass(self) -> Fraction:
        return self.upper - self.lower


def build_rank_intervals(values: Sequence[object]) -> tuple[RankInterval, ...]:
    """Return ascending support values with contiguous tie-block intervals."""

    normalized = _validate_integer_stream(values, label="rank values")
    counts: dict[int, int] = {}
    for value in normalized:
        counts[value] = counts.get(value, 0) + 1
    sample_size = len(normalized)
    offset = 0
    intervals: list[RankInterval] = []
    for value in sorted(counts):
        count = counts[value]
        lower = Fraction(offset, sample_size)
        upper = Fraction(offset + count, sample_size)
        intervals.append(RankInterval(value=value, lower=lower, upper=upper))
        offset += count
    if offset != sample_size:
        raise NumericInvariantError("rank interval masses do not sum to one")
    return tuple(intervals)


rank_intervals = build_rank_intervals


@dataclass(frozen=True, slots=True)
class ContingencyTable:
    """Exact discrete joint counts plus their observed support labels."""

    row_values: tuple[int, ...]
    column_values: tuple[int, ...]
    counts: tuple[tuple[int, ...], ...]
    row_counts: tuple[int, ...]
    column_counts: tuple[int, ...]
    sample_size: int

    @property
    def row_masses(self) -> tuple[Fraction, ...]:
        return tuple(Fraction(count, self.sample_size) for count in self.row_counts)

    @property
    def column_masses(self) -> tuple[Fraction, ...]:
        return tuple(Fraction(count, self.sample_size) for count in self.column_counts)


def _table_from_count_matrix(count_matrix: Sequence[Sequence[object]]) -> ContingencyTable:
    rows = tuple(tuple(row) for row in count_matrix)
    if not rows or not rows[0]:
        raise InvalidInputError("contingency counts must be a non-empty matrix")
    column_count = len(rows[0])
    if any(len(row) != column_count for row in rows):
        raise InvalidInputError("contingency counts must be rectangular")
    counts: tuple[tuple[int, ...], ...] = tuple(
        tuple(
            _as_nonnegative_integer(value, label="contingency count")
            for value in row
        )
        for row in rows
    )
    row_counts = tuple(sum(row) for row in counts)
    column_counts = tuple(
        sum(counts[row][column] for row in range(len(counts)))
        for column in range(column_count)
    )
    sample_size = sum(row_counts)
    if sample_size <= 0:
        raise InvalidInputError("contingency counts must have positive total mass")
    if sum(column_counts) != sample_size:
        raise NumericInvariantError("contingency margins do not agree")
    return ContingencyTable(
        row_values=tuple(range(len(counts))),
        column_values=tuple(range(column_count)),
        counts=counts,
        row_counts=row_counts,
        column_counts=column_counts,
        sample_size=sample_size,
    )


def build_contingency_table(
    left: Sequence[object], right: Sequence[object]
) -> ContingencyTable:
    """Build a sorted-support exact contingency table for two streams."""

    left_values = _validate_integer_stream(left, label="left values")
    right_values = _validate_integer_stream(right, label="right values")
    if len(left_values) != len(right_values):
        raise InvalidInputError("paired streams must have equal length")
    left_support = tuple(sorted(set(left_values)))
    right_support = tuple(sorted(set(right_values)))
    left_indices = {value: index for index, value in enumerate(left_support)}
    right_indices = {value: index for index, value in enumerate(right_support)}
    mutable_counts = [
        [0 for _ in right_support]
        for _ in left_support
    ]
    for left_value, right_value in zip(left_values, right_values, strict=True):
        mutable_counts[left_indices[left_value]][right_indices[right_value]] += 1
    table = _table_from_count_matrix(mutable_counts)
    return ContingencyTable(
        row_values=left_support,
        column_values=right_support,
        counts=table.counts,
        row_counts=table.row_counts,
        column_counts=table.column_counts,
        sample_size=table.sample_size,
    )


def _integrate_error_square(
    e00: Fraction,
    e10: Fraction,
    e01: Fraction,
    e11: Fraction,
    width_u: Fraction,
    width_v: Fraction,
) -> Fraction:
    """Integrate (e00 + e10*x + e01*y + e11*x*y)^2 exactly."""

    width_u_squared = width_u * width_u
    width_v_squared = width_v * width_v
    width_u_cubed = width_u_squared * width_u
    width_v_cubed = width_v_squared * width_v
    third = Fraction(1, 3)
    return (
        e00 * e00 * width_u * width_v
        + e10 * e10 * width_u_cubed * width_v * third
        + e01 * e01 * width_u * width_v_cubed * third
        + e11 * e11 * width_u_cubed * width_v_cubed * third * third
        + e00 * e10 * width_u_squared * width_v
        + e00 * e01 * width_u * width_v_squared
        + e00 * e11 * width_u_squared * width_v_squared * Fraction(1, 2)
        + e10 * e01 * width_u_squared * width_v_squared * Fraction(1, 2)
        + e10 * e11 * width_u_cubed * width_v_squared * third
        + e01 * e11 * width_u_squared * width_v_cubed * third
    )


def _checkerboard_dependence_from_table(table: ContingencyTable) -> Fraction:
    if sum(table.row_counts) != table.sample_size:
        raise NumericInvariantError("row masses do not sum to one")
    if sum(table.column_counts) != table.sample_size:
        raise NumericInvariantError("column masses do not sum to one")

    active_rows = tuple(index for index, count in enumerate(table.row_counts) if count > 0)
    active_columns = tuple(
        index for index, count in enumerate(table.column_counts) if count > 0
    )
    if not active_rows or not active_columns:
        raise NumericInvariantError("contingency support is empty")
    if len(active_rows) == 1 or len(active_columns) == 1:
        return Fraction(0)

    counts = tuple(
        tuple(table.counts[row][column] for column in active_columns)
        for row in active_rows
    )
    row_counts = tuple(table.row_counts[row] for row in active_rows)
    column_counts = tuple(table.column_counts[column] for column in active_columns)
    sample_size = table.sample_size
    row_count = len(row_counts)
    column_count = len(column_counts)

    row_before = [[0 for _ in range(column_count)] for _ in range(row_count)]
    column_before = [[0 for _ in range(column_count)] for _ in range(row_count)]
    prefix = [[0 for _ in range(column_count)] for _ in range(row_count)]
    for row in range(row_count):
        running = 0
        for column in range(column_count):
            row_before[row][column] = running
            running += counts[row][column]
    for column in range(column_count):
        running = 0
        for row in range(row_count):
            column_before[row][column] = running
            running += counts[row][column]
    for row in range(row_count):
        for column in range(column_count):
            prefix[row][column] = sum(
                row_before[prior_row][column] for prior_row in range(row)
            )

    row_lowers: list[Fraction] = []
    row_widths: list[Fraction] = []
    running_rows = 0
    for count in row_counts:
        row_lowers.append(Fraction(running_rows, sample_size))
        row_widths.append(Fraction(count, sample_size))
        running_rows += count
    column_lowers: list[Fraction] = []
    column_widths: list[Fraction] = []
    running_columns = 0
    for count in column_counts:
        column_lowers.append(Fraction(running_columns, sample_size))
        column_widths.append(Fraction(count, sample_size))
        running_columns += count

    if running_rows != sample_size or running_columns != sample_size:
        raise NumericInvariantError("rank widths do not cover the unit square")

    dependence = Fraction(0)
    density_total = Fraction(0)
    for row in range(row_count):
        lower_u = row_lowers[row]
        width_u = row_widths[row]
        for column in range(column_count):
            lower_v = column_lowers[column]
            width_v = column_widths[column]
            c00 = Fraction(prefix[row][column], sample_size)
            c10 = Fraction(row_before[row][column], row_counts[row])
            c01 = Fraction(column_before[row][column], column_counts[column])
            c11 = Fraction(
                counts[row][column] * sample_size,
                row_counts[row] * column_counts[column],
            )
            e00 = c00 - lower_u * lower_v
            e10 = c10 - lower_v
            e01 = c01 - lower_u
            e11 = c11 - 1
            density_total += c11 * width_u * width_v
            dependence += _integrate_error_square(
                e00, e10, e01, e11, width_u, width_v
            )

    if density_total != 1:
        raise NumericInvariantError("checkerboard density does not integrate to one")
    if dependence < 0:
        raise NumericInvariantError("checkerboard dependence must be non-negative")
    return dependence


def checkerboard_dependence_from_counts(
    counts: Sequence[Sequence[object]],
) -> Fraction:
    """Return exact squared checkerboard-CDF distance for a count matrix."""

    return _checkerboard_dependence_from_table(_table_from_count_matrix(counts))


def checkerboard_dependence(
    left: Sequence[object], right: Sequence[object]
) -> Fraction:
    """Return exact D for two discrete streams with tied rank blocks."""

    return _checkerboard_dependence_from_table(build_contingency_table(left, right))


checkerboard_distance = checkerboard_dependence
pair_dependence = checkerboard_dependence
checkerboard_cvm = checkerboard_dependence


def round_half_even_fraction(value: RationalValue) -> int:
    """Round a non-negative exact rational to the nearest integer, half-even."""

    exact = _as_exact_fraction(value, label="rounding input")
    if exact < 0:
        raise NumericInvariantError("half-even input must be non-negative")
    quotient, remainder = divmod(exact.numerator, exact.denominator)
    doubled_remainder = remainder * 2
    if doubled_remainder < exact.denominator:
        return quotient
    if doubled_remainder > exact.denominator:
        return quotient + 1
    return quotient if quotient % 2 == 0 else quotient + 1


def quantize_pair_score(value: RationalValue) -> int:
    """Apply the frozen q = ROUND_HALF_EVEN(D * 10^30) rule."""

    exact = _as_exact_fraction(value, label="pair score")
    return round_half_even_fraction(exact * PAIR_QUANTUM_SCALE)


def _canonical_pair_score_map(
    pair_scores: Mapping[Pair, RationalValue], *, require_complete: bool
) -> dict[Pair, Fraction]:
    normalized = _zero_pair_scores()
    for key, value in pair_scores.items():
        pair = _pair_from_object(key)
        score = _as_exact_fraction(value, label=f"pair_scores[{pair[0]},{pair[1]}]")
        if score < 0:
            raise NumericInvariantError("pair scores must be non-negative")
        normalized[pair] = score
    if require_complete and len(pair_scores) != PAIR_COUNT:
        raise NumericInvariantError("all 1,176 unordered pair scores are required")
    return {pair: normalized[pair] for pair in PAIR_KEYS}


def _canonical_pair_weight_map(
    pair_weights: Mapping[Pair, object], *, require_complete: bool
) -> dict[Pair, int]:
    normalized = _zero_pair_weights()
    for key, value in pair_weights.items():
        pair = _pair_from_object(key)
        weight = _as_nonnegative_integer(value, label=f"pair_weights[{pair[0]},{pair[1]}]")
        normalized[pair] = weight
    if require_complete and len(pair_weights) != PAIR_COUNT:
        raise NumericInvariantError("all 1,176 unordered pair weights are required")
    return {pair: normalized[pair] for pair in PAIR_KEYS}


def _canonical_number_aggregates(values: Mapping[int, object]) -> dict[int, int]:
    normalized = {number: 0 for number in NUMBER_DOMAIN}
    for key, value in values.items():
        if not _is_non_boolean_integer(key) or key not in NUMBER_DOMAIN:
            raise NumericInvariantError("number aggregates must use keys 1..49")
        normalized[key] = _as_nonnegative_integer(value, label=f"number_aggregates[{key}]")
    if len(values) != NUMBER_MAX:
        raise NumericInvariantError("all 49 number aggregates are required")
    return {number: normalized[number] for number in NUMBER_DOMAIN}


def incident_pair_sums(pair_weights: Mapping[Pair, object]) -> Mapping[int, int]:
    """Return the exact 48-term incident q sum for each number."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    totals = {number: 0 for number in NUMBER_DOMAIN}
    for left, right in PAIR_KEYS:
        weight = normalized[(left, right)]
        totals[left] += weight
        totals[right] += weight
    return MappingProxyType(totals)


def ticket_objective(ticket: Sequence[object], pair_weights: Mapping[Pair, object]) -> int:
    """Return the exact sum of the 15 contained pair quanta."""

    values = _validate_ticket(ticket)
    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    return sum(
        normalized[(values[left], values[right])]
        for left in range(DRAW_SIZE)
        for right in range(left + 1, DRAW_SIZE)
    )


def _validate_ticket(ticket: Sequence[object]) -> tuple[int, ...]:
    try:
        values = tuple(ticket)
    except Exception as exc:
        raise InvalidInputError("ticket must be iterable") from exc
    if len(values) != DRAW_SIZE:
        raise InvalidInputError("ticket must contain exactly six numbers")
    if any(not _is_non_boolean_integer(value) for value in values):
        raise InvalidInputError("ticket values must be non-boolean integers")
    integer_values = cast(tuple[int, ...], values)
    if tuple(sorted(integer_values)) != integer_values:
        raise InvalidInputError("ticket must be sorted in ascending order")
    if len(set(integer_values)) != DRAW_SIZE:
        raise InvalidInputError("ticket values must be unique")
    if any(value < NUMBER_MIN or value > NUMBER_MAX for value in integer_values):
        raise InvalidInputError("ticket values must lie in 1..49")
    return integer_values


def optimize_ticket(pair_weights: Mapping[Pair, object]) -> tuple[tuple[int, ...], int]:
    """Exhaustively maximize the 15-pair q objective with lexicographic ties."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    scaled = [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]
    for (left, right), weight in normalized.items():
        scaled[left][right] = weight

    best_score: int | None = None
    best_ticket: tuple[int, ...] | None = None
    for first in range(NUMBER_MIN, NUMBER_MAX - DRAW_SIZE + 2):
        first_row = scaled[first]
        for second in range(first + 1, NUMBER_MAX - DRAW_SIZE + 3):
            second_row = scaled[second]
            first_second = first_row[second]
            for third in range(second + 1, NUMBER_MAX - DRAW_SIZE + 4):
                third_row = scaled[third]
                first_three = first_second + first_row[third] + second_row[third]
                for fourth in range(third + 1, NUMBER_MAX - DRAW_SIZE + 5):
                    fourth_row = scaled[fourth]
                    first_four = (
                        first_three
                        + first_row[fourth]
                        + second_row[fourth]
                        + third_row[fourth]
                    )
                    for fifth in range(fourth + 1, NUMBER_MAX - DRAW_SIZE + 6):
                        fifth_row = scaled[fifth]
                        first_five = (
                            first_four
                            + first_row[fifth]
                            + second_row[fifth]
                            + third_row[fifth]
                            + fourth_row[fifth]
                        )
                        for sixth in range(fifth + 1, NUMBER_MAX + 1):
                            score = (
                                first_five
                                + first_row[sixth]
                                + second_row[sixth]
                                + third_row[sixth]
                                + fourth_row[sixth]
                                + fifth_row[sixth]
                            )
                            if best_score is None or score > best_score:
                                best_score = score
                                best_ticket = (first, second, third, fourth, fifth, sixth)

    if best_score is None or best_ticket is None:
        raise NumericInvariantError("ticket enumeration produced no legal six-subset")
    return best_ticket, best_score


def compute_pair_scores(
    age_streams: Sequence[Sequence[object]],
) -> Mapping[Pair, Fraction]:
    """Compute all 1,176 exact raw D scores from 49 age streams."""

    if len(age_streams) != NUMBER_MAX:
        raise InvalidInputError("exactly 49 age streams are required")
    normalized: tuple[AgeStream, ...] = tuple(
        _validate_integer_stream(stream, label="age stream") for stream in age_streams
    )
    if any(len(stream) != WINDOW_SIZE for stream in normalized):
        raise InvalidInputError("every age stream must contain exactly 256 rows")
    if any(
        any(value < 0 or value > SENTINEL_AGE for value in stream)
        for stream in normalized
    ):
        raise InvalidInputError("age streams must use states 0..16 and sentinel 17")

    scores: dict[Pair, Fraction] = {}
    for left_index, left_number in enumerate(NUMBER_DOMAIN):
        for right_index in range(left_index + 1, NUMBER_MAX):
            right_number = NUMBER_DOMAIN[right_index]
            score = checkerboard_dependence(normalized[left_index], normalized[right_index])
            if score < 0:
                raise NumericInvariantError("pair score must be non-negative")
            scores[(left_number, right_number)] = score
    if len(scores) != PAIR_COUNT:
        raise NumericInvariantError("pair-score cardinality is not 1,176")
    return MappingProxyType(scores)


def compute_pair_weights(
    pair_scores: Mapping[Pair, RationalValue],
) -> Mapping[Pair, int]:
    """Quantize a complete raw D matrix into the frozen q matrix."""

    normalized = _canonical_pair_score_map(pair_scores, require_complete=True)
    weights = {
        pair: quantize_pair_score(score)
        for pair, score in normalized.items()
    }
    if len(weights) != PAIR_COUNT or any(weight < 0 for weight in weights.values()):
        raise NumericInvariantError("pair-quantum invariants failed")
    return MappingProxyType(weights)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Canonical NF05 result containing q weights, diagnostics, and one ticket."""

    method_id: str
    design_name: str
    status: str
    window_size: int
    pair_weights: Mapping[Pair, int]
    ticket_objective: int
    ticket: tuple[int, ...]
    recurrence_cap: int = RECURRENCE_CAP
    sentinel_age: int = SENTINEL_AGE
    pair_scores: Mapping[Pair, RationalValue] = field(
        default_factory=_zero_pair_scores, repr=False, compare=False
    )
    number_aggregates: Mapping[int, int] = field(
        default_factory=_zero_number_aggregates, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.design_name != DESIGN_NAME:
            raise NumericInvariantError("result identity does not match the sealed NF05 identity")
        if self.status not in (COMPLETE_STATUS, FALLBACK_STATUS, FAIL_CLOSED_STATUS):
            raise NumericInvariantError("unknown result status")
        if self.window_size != WINDOW_SIZE:
            raise NumericInvariantError("result window size does not match the sealed value")
        if self.recurrence_cap != RECURRENCE_CAP or self.sentinel_age != SENTINEL_AGE:
            raise NumericInvariantError("result recurrence constants are not sealed values")

        weights = _canonical_pair_weight_map(self.pair_weights, require_complete=True)
        object.__setattr__(self, "pair_weights", MappingProxyType(weights))
        objective = _as_nonnegative_integer(self.ticket_objective, label="ticket_objective")
        object.__setattr__(self, "ticket_objective", objective)
        ticket = _validate_ticket(self.ticket)
        object.__setattr__(self, "ticket", ticket)

        if self.pair_scores:
            scores = _canonical_pair_score_map(self.pair_scores, require_complete=True)
            if any(quantize_pair_score(scores[pair]) != weights[pair] for pair in PAIR_KEYS):
                raise NumericInvariantError("raw pair scores and quantized weights disagree")
        else:
            scores = _zero_pair_scores()
        object.__setattr__(self, "pair_scores", MappingProxyType(scores))

        if self.number_aggregates:
            aggregates = _canonical_number_aggregates(self.number_aggregates)
            if aggregates != dict(incident_pair_sums(weights)):
                raise NumericInvariantError("number aggregates do not match pair weights")
        else:
            aggregates = dict(incident_pair_sums(weights))
        object.__setattr__(self, "number_aggregates", MappingProxyType(aggregates))

        if self.status in (FALLBACK_STATUS, FAIL_CLOSED_STATUS):
            if (
                objective != 0
                or ticket != (1, 2, 3, 4, 5, 6)
                or any(value != 0 for value in weights.values())
            ):
                raise NumericInvariantError("non-complete result does not match its frozen output")
        elif objective != ticket_objective(ticket, weights):
            raise NumericInvariantError("ticket objective does not match contained pair weights")

    @property
    def semantic_signature(self) -> str:
        return SEMANTIC_SIGNATURE

    @property
    def pair_quanta(self) -> Mapping[Pair, int]:
        return self.pair_weights

    @property
    def number_level_aggregation(self) -> Mapping[int, object]:
        return self.number_aggregates

    def canonical_dict(self) -> dict[str, object]:
        """Return insertion-ordered compact-serialization data."""

        pair_payload = {
            f"{left}-{right}": weight
            for (left, right), weight in self.pair_weights.items()
        }
        aggregate_payload = {
            str(number): self.number_aggregates[number]
            for number in NUMBER_DOMAIN
        }
        return {
            "method_id": self.method_id,
            "design_name": self.design_name,
            "status": self.status,
            "window_size": self.window_size,
            "recurrence_cap": self.recurrence_cap,
            "sentinel_age": self.sentinel_age,
            "pair_weights": pair_payload,
            "number_aggregates": aggregate_payload,
            "ticket_objective": self.ticket_objective,
            "ticket": list(self.ticket),
        }

    def canonical_bytes(self) -> bytes:
        return dumps(
            self.canonical_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=False
        ).encode("utf-8")

    def canonical_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")


def _empty_result(status: str) -> AnalysisResult:
    weights = _zero_pair_weights()
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=status,
        window_size=WINDOW_SIZE,
        pair_weights=weights,
        ticket_objective=0,
        ticket=(1, 2, 3, 4, 5, 6),
        pair_scores=_zero_pair_scores(),
        number_aggregates=_zero_number_aggregates(),
    )


def analyze(history: object, cutoff: object) -> AnalysisResult:
    """Analyze exactly history[cutoff-256:cutoff] and return one exact ticket."""

    try:
        history_length = _history_length(history)
        validated_cutoff = _validated_cutoff(cutoff, history_length)
        if validated_cutoff < MIN_HISTORY:
            return _empty_result(FALLBACK_STATUS)
        draws = _read_causal_window(history, validated_cutoff)
        age_streams = build_recurrence_age_streams(draws)
        scores = compute_pair_scores(age_streams)
        weights = compute_pair_weights(scores)
        aggregates = incident_pair_sums(weights)
        ticket, objective = optimize_ticket(weights)
        return AnalysisResult(
            method_id=METHOD_ID,
            design_name=DESIGN_NAME,
            status=COMPLETE_STATUS,
            window_size=WINDOW_SIZE,
            pair_weights=weights,
            ticket_objective=objective,
            ticket=ticket,
            pair_scores=scores,
            number_aggregates=aggregates,
        )
    except BigLottoL2PairwiseCheckerboardError:
        return _empty_result(FAIL_CLOSED_STATUS)


__all__ = [
    "COMPLETE_STATUS",
    "DESIGN_NAME",
    "DRAW_SIZE",
    "FAIL_CLOSED_NO_TICKET",
    "FAIL_CLOSED_STATUS",
    "FALLBACK_STATUS",
    "METHOD_ID",
    "MIN_HISTORY",
    "NUMBER_DOMAIN",
    "NUMBER_MAX",
    "NUMBER_MIN",
    "PAIR_COUNT",
    "PAIR_KEYS",
    "PAIR_QUANTUM_SCALE",
    "RANK_LEVELS",
    "RECURRENCE_CAP",
    "SEMANTIC_SIGNATURE",
    "SENTINEL_AGE",
    "TICKET_COUNT",
    "WINDOW_SIZE",
    "AnalysisResult",
    "BigLottoL2PairwiseCheckerboardError",
    "ContingencyTable",
    "InvalidInputError",
    "NumericInvariantError",
    "RankInterval",
    "analyze",
    "build_contingency_table",
    "build_rank_intervals",
    "build_recurrence_age_stream",
    "build_recurrence_age_streams",
    "checkerboard_cvm",
    "checkerboard_dependence",
    "checkerboard_dependence_from_counts",
    "checkerboard_distance",
    "compute_pair_scores",
    "compute_pair_weights",
    "incident_pair_sums",
    "optimize_ticket",
    "pair_dependence",
    "quantize_pair_score",
    "rank_intervals",
    "round_half_even_fraction",
    "ticket_objective",
    "zero_pair_scores",
    "zero_pair_weights",
]
