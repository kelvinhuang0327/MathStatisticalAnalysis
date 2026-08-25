"""Frozen deterministic Big Lotto L2 marked pair-matrix-profile candidate.

This module implements ``BMSGV1_L2_PAIRWISE_2e8fb1bb6d0648fa`` exactly as
specified by the sealed ``CAUSAL_MARKED_UNION_MATRIX_PROFILE_EXACT6_V1``
semantics.  It is deliberately self-contained: it reads only the validated
completed draw window supplied by its caller, uses the standard-library
``decimal`` and ``itertools`` implementations, and has no database,
network, empirical-result, or random-number dependency.

The public entry point is :func:`analyze`.  The smaller public helpers expose
the literal pair encoder/profile and exact six-subset constructor so the
frozen synthetic fixtures can test each contract surface independently.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    Underflow,
    localcontext,
)
from functools import lru_cache
from itertools import combinations
from typing import Any, Literal, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_2e8fb1bb6d0648fa"
DESIGN_NAME = "CAUSAL_MARKED_UNION_MATRIX_PROFILE_EXACT6_V1"
SEMANTIC_SIGNATURE = "2e8fb1bb6d0648fa1e226bc78d35b3677833855e3e8d5e2a1ea51acd2504ce4f"

MIN_HISTORY = 256
WINDOW_SIZE = 256
SUBSEQUENCE_LENGTH = 6
MIN_UNION_EVENTS = 12
NUMBER_MIN = 1
NUMBER_MAX = 49
TICKET_SIZE = 6
PAIR_WEIGHT_SCALE = 10**30
DISTANCE2_SCALE = 10**36

MARK_I_ONLY = "I_ONLY"
MARK_J_ONLY = "J_ONLY"
MARK_BOTH = "BOTH"
MARKS = (MARK_I_ONLY, MARK_J_ONLY, MARK_BOTH)
type Mark = Literal["I_ONLY", "J_ONLY", "BOTH"]

STATUS_OK = "OK"
STATUS_FALLBACK_INSUFFICIENT_HISTORY = "FALLBACK_INSUFFICIENT_HISTORY"
STATUS_INSUFFICIENT_PAIR_GEOMETRY = "INSUFFICIENT_PAIR_GEOMETRY"

_D2_QUANTUM = Decimal("1e-36")
_PAIR_WEIGHT_QUANTUM = Decimal("1e-30")
_DECIMAL_ZERO = Decimal(0)
_DECIMAL_ONE = Decimal(1)
_DECIMAL_SIX = Decimal(6)
_DECIMAL_TWENTY_FOUR = Decimal(24)
_DECIMAL_HALF = Decimal("0.5")

DECIMAL_CONTEXT = Context(
    prec=80,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
)
for _signal in (InvalidOperation, DivisionByZero, Overflow, Underflow):
    DECIMAL_CONTEXT.traps[_signal] = True


class InvalidCutoffError(ValueError):
    """Raised when the cutoff is not a valid non-boolean history boundary."""


class InvalidHistoryError(ValueError):
    """Raised when an accessed draw is not a valid six-number Big Lotto draw."""


class NumericContractError(ValueError):
    """Raised when a frozen Decimal or range invariant is violated."""


class PairMatrixContractError(ValueError):
    """Raised when a six-ticket constructor receives an incomplete matrix."""


@dataclass(frozen=True, slots=True)
class PairEvent:
    """One local pair-union event inside the completed 256-draw window."""

    tau: int
    gap: int
    mark: Mark


@dataclass(frozen=True, slots=True)
class PairProfile:
    """The serialized score surfaces for one unordered pair."""

    union_event_count: int
    status: str
    selected_candidate_start: int | None
    d2_quantum: int | None
    d2: str | None
    weight: str
    pair_weight_quantum: int

    @property
    def u(self) -> int:
        """Short alias for the pair's union-event count."""

        return self.union_event_count

    @property
    def d2q(self) -> int | None:
        """Short alias for the quantized nearest distance-squared."""

        return self.d2_quantum

    @property
    def q(self) -> int:
        """Short alias for the exact pair-weight quantum."""

        return self.pair_weight_quantum


@dataclass(frozen=True, slots=True)
class PairAuditRow:
    """One lexicographically ordered audit row of the 49-by-49 pair matrix."""

    i: int
    j: int
    union_event_count: int
    status: str
    selected_candidate_start: int | None
    d2_quantum: int | None
    d2: str | None
    weight: str
    pair_weight_quantum: int

    @property
    def u(self) -> int:
        return self.union_event_count

    @property
    def d2q(self) -> int | None:
        return self.d2_quantum

    @property
    def q(self) -> int:
        return self.pair_weight_quantum

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-ready audit row."""

        return {
            "i": self.i,
            "j": self.j,
            "union_event_count": self.union_event_count,
            "status": self.status,
            "selected_candidate_start": self.selected_candidate_start,
            "d2_quantum": self.d2_quantum,
            "d2": self.d2,
            "weight": self.weight,
            "pair_weight_quantum": self.pair_weight_quantum,
        }


@dataclass(frozen=True, slots=True)
class NumberScoreRow:
    """One exact incident-pair aggregate and its deterministic rank."""

    number: int
    aggregate_score: int
    rank: int

    @property
    def score(self) -> int:
        """Short alias for the exact aggregate score."""

        return self.aggregate_score

    def to_dict(self) -> dict[str, int]:
        """Return a deterministic JSON-ready number row."""

        return {
            "number": self.number,
            "aggregate_score": self.aggregate_score,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete deterministic output for one valid invocation."""

    cutoff: int
    status: str
    pair_rows: tuple[PairAuditRow, ...]
    number_rank_rows: tuple[NumberScoreRow, ...]
    ticket: tuple[int, ...]

    @property
    def number_scores(self) -> tuple[NumberScoreRow, ...]:
        """Compatibility alias for the complete number rank table."""

        return self.number_rank_rows

    @property
    def number_score_rows(self) -> tuple[NumberScoreRow, ...]:
        """Compatibility alias for the complete number rank table."""

        return self.number_rank_rows

    @property
    def pair_weight_matrix(self) -> dict[tuple[int, int], int]:
        """Return the 1176 unordered pair values as an exact-integer mapping."""

        return {(row.i, row.j): row.pair_weight_quantum for row in self.pair_rows}

    @property
    def ticket_objective(self) -> int:
        """Return the exact sum of the 15 pair quanta inside ``ticket``."""

        pair_weights = self.pair_weight_matrix
        return sum(
            pair_weights[min(i, j), max(i, j)] for i, j in combinations(self.ticket, 2)
        )

    def to_dict(self) -> dict[str, object]:
        """Return the complete output with fixed-point surfaces as strings."""

        return {
            "method_id": METHOD_ID,
            "design": DESIGN_NAME,
            "semantic_signature": SEMANTIC_SIGNATURE,
            "cutoff": self.cutoff,
            "status": self.status,
            "pair_rows": [row.to_dict() for row in self.pair_rows],
            "number_rank_rows": [row.to_dict() for row in self.number_rank_rows],
            "ticket": list(self.ticket),
            "ticket_objective": self.ticket_objective,
        }

    def to_json(self) -> str:
        """Serialize the result canonically with one terminating newline."""

        return (
            json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )

    as_dict = to_dict
    serialize = to_json


def _is_non_boolean_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_number(value: object, label: str) -> int:
    if not _is_non_boolean_integer(value) or not NUMBER_MIN <= cast(int, value) <= NUMBER_MAX:
        raise InvalidHistoryError(f"{label} must be a non-boolean integer in [1, 49]")
    return cast(int, value)


def _validate_cutoff(history: object, cutoff: object) -> tuple[int, int]:
    if not _is_non_boolean_integer(cutoff):
        raise InvalidCutoffError("cutoff must be a non-boolean integer")
    cutoff_int = cast(int, cutoff)
    try:
        history_length = len(cast(Any, history))
    except Exception as exc:  # pragma: no cover - defensive boundary for foreign containers
        raise InvalidHistoryError("history must be a finite random-access container") from exc
    if cutoff_int < 0 or cutoff_int > history_length:
        raise InvalidCutoffError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return cutoff_int, history_length


def _canonicalize_draw(draw: object, index: int) -> tuple[int, ...]:
    if isinstance(draw, (str, bytes, bytearray)):
        raise InvalidHistoryError(f"history[{index}] is not a six-number draw")
    try:
        values = tuple(cast(Any, draw))
    except Exception as exc:
        raise InvalidHistoryError(f"history[{index}] is not an iterable six-number draw") from exc
    if len(values) != TICKET_SIZE:
        raise InvalidHistoryError(f"history[{index}] must contain exactly six numbers")
    numbers: list[int] = []
    for value in values:
        if not _is_non_boolean_integer(value):
            raise InvalidHistoryError(
                f"history[{index}] contains a boolean or non-integer number"
            )
        number = cast(int, value)
        if not NUMBER_MIN <= number <= NUMBER_MAX:
            raise InvalidHistoryError(f"history[{index}] contains a number outside [1, 49]")
        numbers.append(number)
    if len(set(numbers)) != TICKET_SIZE:
        raise InvalidHistoryError(f"history[{index}] contains duplicate numbers")
    return tuple(sorted(numbers))


def _read_completed_window(history: object, cutoff: int) -> tuple[tuple[int, ...], ...]:
    start = cutoff - WINDOW_SIZE
    history_object = cast(Any, history)
    validated: list[tuple[int, ...]] = []
    for index in range(start, cutoff):
        try:
            draw = history_object[index]
        except Exception as exc:
            raise InvalidHistoryError(f"history[{index}] could not be read") from exc
        validated.append(_canonicalize_draw(draw, index))
    return tuple(validated)


def _validate_pair_numbers(i: object, j: object) -> tuple[int, int]:
    first = _validate_number(i, "pair first number")
    second = _validate_number(j, "pair second number")
    if first >= second:
        raise InvalidHistoryError("pair numbers must satisfy 1 <= i < j <= 49")
    return first, second


def _encode_pair_events_from_sets(
    draw_sets: Sequence[frozenset[int]], i: int, j: int
) -> tuple[PairEvent, ...]:
    events: list[PairEvent] = []
    previous_tau = -1
    for tau, draw_set in enumerate(draw_sets):
        has_i = i in draw_set
        has_j = j in draw_set
        if not has_i and not has_j:
            continue
        if has_i and has_j:
            mark: Mark = MARK_BOTH
        elif has_i:
            mark = MARK_I_ONLY
        else:
            mark = MARK_J_ONLY
        gap = tau + 1 if not events else tau - previous_tau
        events.append(PairEvent(tau=tau, gap=gap, mark=mark))
        previous_tau = tau
    return tuple(events)


def encode_pair_union_events(
    draws: Sequence[object], i: int, j: int
) -> tuple[PairEvent, ...]:
    """Encode one unordered pair's marked union events from validated draws.

    The helper validates the supplied draw sequence because it is also a
    standalone synthetic-fixture surface.  The main entry point validates its
    bounded history window once, then uses the internal set-based encoder.
    """

    first, second = _validate_pair_numbers(i, j)
    canonical_draws = tuple(_canonicalize_draw(draw, index) for index, draw in enumerate(draws))
    draw_sets = tuple(frozenset(draw) for draw in canonical_draws)
    return _encode_pair_events_from_sets(draw_sets, first, second)


def encode_marked_pair_union(
    draws: Sequence[object], i: int, j: int
) -> tuple[PairEvent, ...]:
    """Alias for :func:`encode_pair_union_events`."""

    return encode_pair_union_events(draws, i, j)


def _normalize_event_inputs(events: Sequence[object]) -> tuple[PairEvent, ...]:
    normalized: list[PairEvent] = []
    previous_tau = -1
    for event_index, raw_event in enumerate(events):
        if isinstance(raw_event, PairEvent):
            tau_object: object = raw_event.tau
            mark_object: object = raw_event.mark
        elif isinstance(raw_event, Sequence) and not isinstance(
            raw_event, (str, bytes, bytearray)
        ):
            raw_sequence = cast(Sequence[object], raw_event)
            if len(raw_sequence) != 2:
                raise ValueError(f"event {event_index} must contain (tau, mark)")
            tau_object = raw_sequence[0]
            mark_object = raw_sequence[1]
        else:
            raise ValueError(f"event {event_index} must be a PairEvent or (tau, mark)")
        if not _is_non_boolean_integer(tau_object):
            raise ValueError(f"event {event_index} has a non-integer time")
        tau = cast(int, tau_object)
        if not 0 <= tau < WINDOW_SIZE or tau <= previous_tau:
            raise ValueError(f"event {event_index} times must be strictly increasing in [0, 255]")
        if not isinstance(mark_object, str) or mark_object not in MARKS:
            raise ValueError(f"event {event_index} has an invalid mark")
        mark = mark_object
        gap = tau + 1 if not normalized else tau - previous_tau
        normalized.append(PairEvent(tau=tau, gap=gap, mark=mark))
        previous_tau = tau
    return tuple(normalized)


@lru_cache(maxsize=257)
def _ln_one_plus_gap(gap: int) -> Decimal:
    """Compute one exact frozen-context logarithm once per allowed gap."""

    try:
        with localcontext(DECIMAL_CONTEXT):
            return Decimal(gap + 1).ln()
    except (DecimalException, ArithmeticError) as exc:
        raise NumericContractError("frozen Decimal logarithm failed") from exc


@lru_cache(maxsize=32768)
def _standardize_gaps_cached(gap_tuple: tuple[int, ...]) -> tuple[Decimal, ...]:
    if len(set(gap_tuple)) == 1:
        return (_DECIMAL_ZERO,) * SUBSEQUENCE_LENGTH

    try:
        with localcontext(DECIMAL_CONTEXT):
            transformed = [_ln_one_plus_gap(gap) for gap in gap_tuple]

            total = _DECIMAL_ZERO
            for value in transformed:
                total += value
            mean = total / _DECIMAL_SIX

            squared_deviations = _DECIMAL_ZERO
            for value in transformed:
                deviation = value - mean
                squared_deviations += deviation * deviation
            variance = squared_deviations / _DECIMAL_SIX
            if variance <= _DECIMAL_ZERO:
                return (_DECIMAL_ZERO,) * SUBSEQUENCE_LENGTH
            standard_deviation = variance.sqrt()
            coordinates = tuple(
                (value - mean) / standard_deviation for value in transformed
            )
            return coordinates
    except (DecimalException, ArithmeticError) as exc:
        raise NumericContractError("frozen Decimal gap standardization failed") from exc


def standardize_gaps(gaps: Sequence[int]) -> tuple[Decimal, ...]:
    """Return six population-z-normalized ``ln(1 + gap)`` coordinates."""

    if len(gaps) != SUBSEQUENCE_LENGTH:
        raise ValueError("exactly six gaps are required")
    gap_objects = tuple(gaps)
    if any(
        not _is_non_boolean_integer(gap) or not 1 <= gap <= WINDOW_SIZE
        for gap in gap_objects
    ):
        raise ValueError("gaps must be non-boolean integers in [1, 256]")
    gap_tuple = tuple(gap_objects)
    return _standardize_gaps_cached(gap_tuple)


def _fixed_point_from_quantum(quantum: int, scale: int, fractional_digits: int) -> str:
    if quantum < 0:
        raise NumericContractError("fixed-point quantum must be non-negative")
    whole, fraction = divmod(quantum, scale)
    return f"{whole}.{fraction:0{fractional_digits}d}"


def _quantize_d2(value: Decimal) -> tuple[int, str]:
    try:
        with localcontext(DECIMAL_CONTEXT):
            if value < _DECIMAL_ZERO or value > _DECIMAL_ONE:
                raise NumericContractError("distance-squared is outside [0, 1]")
            quantized = value.quantize(_D2_QUANTUM, rounding=ROUND_HALF_EVEN)
            quantum = int(quantized * Decimal(DISTANCE2_SCALE))
            if not 0 <= quantum <= DISTANCE2_SCALE:
                raise NumericContractError("quantized distance-squared is outside [0, 1]")
            return quantum, _fixed_point_from_quantum(quantum, DISTANCE2_SCALE, 36)
    except NumericContractError:
        raise
    except (DecimalException, ArithmeticError) as exc:
        raise NumericContractError("distance-squared quantization failed") from exc


def _distance_quantum_for_subsequences(
    candidate: tuple[PairEvent, ...],
    query: tuple[PairEvent, ...],
    query_coordinates: tuple[Decimal, ...] | None = None,
) -> tuple[int, str]:
    candidate_gaps = tuple(event.gap for event in candidate)
    query_gaps = tuple(event.gap for event in query)
    candidate_marks = tuple(event.mark for event in candidate)
    query_marks = tuple(event.mark for event in query)
    if candidate_gaps == query_gaps and candidate_marks == query_marks:
        return 0, _fixed_point_from_quantum(0, DISTANCE2_SCALE, 36)

    candidate_coordinates = standardize_gaps(candidate_gaps)
    query_coordinates = (
        standardize_gaps(query_gaps) if query_coordinates is None else query_coordinates
    )
    try:
        with localcontext(DECIMAL_CONTEXT):
            squared_difference = _DECIMAL_ZERO
            for candidate_coordinate, query_coordinate in zip(
                candidate_coordinates, query_coordinates, strict=True
            ):
                difference = candidate_coordinate - query_coordinate
                squared_difference += difference * difference
            gap_component = squared_difference / _DECIMAL_TWENTY_FOUR
            mismatch_count = sum(
                candidate_mark != query_mark
                for candidate_mark, query_mark in zip(candidate_marks, query_marks, strict=True)
            )
            mark_component = Decimal(mismatch_count) / _DECIMAL_SIX
            distance_squared = (gap_component + mark_component) / Decimal(2)
            return _quantize_d2(distance_squared)
    except NumericContractError:
        raise
    except (DecimalException, ArithmeticError) as exc:
        raise NumericContractError("frozen pair distance calculation failed") from exc


def distance_squared_quantum(
    candidate_gaps: Sequence[int],
    candidate_marks: Sequence[str],
    query_gaps: Sequence[int],
    query_marks: Sequence[str],
) -> tuple[int, str]:
    """Compute one literal quantized ``D²`` fixture value."""

    candidate_gap_tuple = tuple(candidate_gaps)
    candidate_mark_tuple = tuple(candidate_marks)
    query_gap_tuple = tuple(query_gaps)
    query_mark_tuple = tuple(query_marks)
    for gaps, marks, label in (
        (candidate_gap_tuple, candidate_mark_tuple, "candidate"),
        (query_gap_tuple, query_mark_tuple, "query"),
    ):
        if len(gaps) != SUBSEQUENCE_LENGTH or len(marks) != SUBSEQUENCE_LENGTH:
            raise ValueError(f"{label} must contain six gaps and six marks")
        if any(
            not _is_non_boolean_integer(gap) or not 1 <= gap <= WINDOW_SIZE for gap in gaps
        ):
            raise ValueError(f"{label} gaps must be non-boolean integers in [1, 256]")
        if any(mark not in MARKS for mark in marks):
            raise ValueError(f"{label} marks contain an invalid mark")
    candidate = tuple(
        PairEvent(tau=index, gap=gap, mark=cast(Mark, mark))
        for index, (gap, mark) in enumerate(
            zip(candidate_gap_tuple, candidate_mark_tuple, strict=True)
        )
    )
    query = tuple(
        PairEvent(tau=index, gap=gap, mark=cast(Mark, mark))
        for index, (gap, mark) in enumerate(zip(query_gap_tuple, query_mark_tuple, strict=True))
    )
    return _distance_quantum_for_subsequences(candidate, query)


def _pair_weight_from_d2_quantum(d2_quantum: int) -> tuple[str, int]:
    if not _is_non_boolean_integer(d2_quantum) or not 0 <= d2_quantum <= DISTANCE2_SCALE:
        raise NumericContractError("distance-squared quantum is outside the frozen range")
    try:
        with localcontext(DECIMAL_CONTEXT):
            distance_squared = Decimal(d2_quantum) / Decimal(DISTANCE2_SCALE)
            distance = distance_squared.sqrt()
            weight = _DECIMAL_ONE / (_DECIMAL_ONE + distance)
            if weight < _DECIMAL_HALF or weight > _DECIMAL_ONE:
                raise NumericContractError("pair weight is outside [0.5, 1]")
            quantized_weight = weight.quantize(_PAIR_WEIGHT_QUANTUM, rounding=ROUND_HALF_EVEN)
            quantum = int(quantized_weight * Decimal(PAIR_WEIGHT_SCALE))
            if not PAIR_WEIGHT_SCALE // 2 <= quantum <= PAIR_WEIGHT_SCALE:
                raise NumericContractError("quantized pair weight is outside [0.5, 1]")
            return (
                _fixed_point_from_quantum(quantum, PAIR_WEIGHT_SCALE, 30),
                quantum,
            )
    except NumericContractError:
        raise
    except (DecimalException, ArithmeticError) as exc:
        raise NumericContractError("pair-weight quantization failed") from exc


def pair_profile_from_events(events: Sequence[object]) -> PairProfile:
    """Compute the frozen current-query strict-left profile for one pair."""

    normalized = _normalize_event_inputs(events)
    union_event_count = len(normalized)
    if union_event_count < MIN_UNION_EVENTS:
        return PairProfile(
            union_event_count=union_event_count,
            status=STATUS_INSUFFICIENT_PAIR_GEOMETRY,
            selected_candidate_start=None,
            d2_quantum=None,
            d2=None,
            weight=_fixed_point_from_quantum(0, PAIR_WEIGHT_SCALE, 30),
            pair_weight_quantum=0,
        )

    query = normalized[-SUBSEQUENCE_LENGTH:]
    query_coordinates = standardize_gaps(tuple(event.gap for event in query))
    best_start: int | None = None
    best_d2_quantum: int | None = None
    for start in range(union_event_count - (2 * SUBSEQUENCE_LENGTH) + 1):
        candidate = normalized[start : start + SUBSEQUENCE_LENGTH]
        d2_quantum, _ = _distance_quantum_for_subsequences(
            candidate, query, query_coordinates
        )
        if best_d2_quantum is None or d2_quantum < best_d2_quantum:
            best_start = start
            best_d2_quantum = d2_quantum

    if best_start is None or best_d2_quantum is None:  # pragma: no cover - guarded by U >= 12
        raise NumericContractError("sufficient pair geometry produced no candidate")
    d2 = _fixed_point_from_quantum(best_d2_quantum, DISTANCE2_SCALE, 36)
    weight, pair_weight_quantum = _pair_weight_from_d2_quantum(best_d2_quantum)
    return PairProfile(
        union_event_count=union_event_count,
        status=STATUS_OK,
        selected_candidate_start=best_start,
        d2_quantum=best_d2_quantum,
        d2=d2,
        weight=weight,
        pair_weight_quantum=pair_weight_quantum,
    )


def compute_pair_profile(events: Sequence[object]) -> PairProfile:
    """Alias for :func:`pair_profile_from_events`."""

    return pair_profile_from_events(events)


def _zero_pair_matrix() -> list[list[int]]:
    return [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]


def _build_pair_rows(
    draw_sets: Sequence[frozenset[int]],
) -> tuple[tuple[PairAuditRow, ...], list[list[int]]]:
    rows: list[PairAuditRow] = []
    matrix = _zero_pair_matrix()
    for i in range(NUMBER_MIN, NUMBER_MAX + 1):
        for j in range(i + 1, NUMBER_MAX + 1):
            events = _encode_pair_events_from_sets(draw_sets, i, j)
            profile = pair_profile_from_events(events)
            row = PairAuditRow(
                i=i,
                j=j,
                union_event_count=profile.union_event_count,
                status=profile.status,
                selected_candidate_start=profile.selected_candidate_start,
                d2_quantum=profile.d2_quantum,
                d2=profile.d2,
                weight=profile.weight,
                pair_weight_quantum=profile.pair_weight_quantum,
            )
            rows.append(row)
            matrix[i][j] = profile.pair_weight_quantum
            matrix[j][i] = profile.pair_weight_quantum
    if len(rows) != 1176:  # pragma: no cover - structural guard
        raise PairMatrixContractError("pair matrix did not contain exactly 1176 rows")
    return tuple(rows), matrix


def aggregate_number_scores(
    pair_weights: Mapping[tuple[int, int], int] | Sequence[Sequence[int]],
) -> tuple[NumberScoreRow, ...]:
    """Aggregate every exact pair quantum and return all 49 rank rows."""

    matrix = _coerce_pair_matrix(pair_weights)
    aggregates = [0 for _ in range(NUMBER_MAX + 1)]
    for i in range(NUMBER_MIN, NUMBER_MAX + 1):
        for j in range(i + 1, NUMBER_MAX + 1):
            value = matrix[i][j]
            aggregates[i] += value
            aggregates[j] += value
    order = sorted(
        range(NUMBER_MIN, NUMBER_MAX + 1), key=lambda number: (-aggregates[number], number)
    )
    return tuple(
        NumberScoreRow(
            number=number,
            aggregate_score=aggregates[number],
            rank=rank,
        )
        for rank, number in enumerate(order, start=1)
    )


def _coerce_pair_matrix(
    pair_weights: Mapping[tuple[int, int], int] | Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    matrix = _zero_pair_matrix()
    if isinstance(pair_weights, Mapping):
        expected = {
            (i, j)
            for i in range(NUMBER_MIN, NUMBER_MAX + 1)
            for j in range(i + 1, NUMBER_MAX + 1)
        }
        if set(pair_weights) != expected:
            raise PairMatrixContractError("pair mapping must contain exactly all 1176 i<j pairs")
        for key, value in pair_weights.items():
            i, j = key
            if not _is_non_boolean_integer(value) or value < 0:
                raise PairMatrixContractError("pair quanta must be non-negative integers")
            matrix[i][j] = value
            matrix[j][i] = value
    else:
        matrix_object = cast(Any, pair_weights)
        try:
            if len(matrix_object) != NUMBER_MAX + 1:
                raise PairMatrixContractError("pair matrix must have 50 rows")
            for i in range(NUMBER_MAX + 1):
                row = matrix_object[i]
                if len(row) != NUMBER_MAX + 1:
                    raise PairMatrixContractError("pair matrix must have 50 columns")
                for j in range(NUMBER_MAX + 1):
                    value = row[j]
                    if not _is_non_boolean_integer(value) or value < 0:
                        raise PairMatrixContractError("pair quanta must be non-negative integers")
                    matrix[i][j] = value
        except PairMatrixContractError:
            raise
        except Exception as exc:
            raise PairMatrixContractError("pair matrix is not a readable 50-by-50 matrix") from exc
        for i in range(NUMBER_MIN, NUMBER_MAX + 1):
            if matrix[i][i] != 0:
                raise PairMatrixContractError("pair matrix diagonal must be zero")
            for j in range(i + 1, NUMBER_MAX + 1):
                if matrix[i][j] != matrix[j][i]:
                    raise PairMatrixContractError("pair matrix must be symmetric")
    return tuple(tuple(row) for row in matrix)


def construct_exact_six_ticket(
    pair_weights: Mapping[tuple[int, int], int] | Sequence[Sequence[int]],
) -> tuple[int, ...]:
    """Exhaustively maximize the exact 15-edge objective over all six-subsets.

    The outer five-number combinations plus the final-number loop enumerate
    exactly the same lexicographic order as
    ``itertools.combinations(range(1, 50), 6)``.  The first-five objective is
    streamed, so no candidate set or heuristic pruning state is retained.
    """

    matrix = _coerce_pair_matrix(pair_weights)
    best_objective = -1
    best_ticket: tuple[int, ...] = (NUMBER_MIN,) * TICKET_SIZE
    values = matrix
    for a, b, c, d, e in combinations(range(NUMBER_MIN, NUMBER_MAX + 1), 5):
        first_five_objective = (
            values[a][b]
            + values[a][c]
            + values[a][d]
            + values[a][e]
            + values[b][c]
            + values[b][d]
            + values[b][e]
            + values[c][d]
            + values[c][e]
            + values[d][e]
        )
        for f in range(e + 1, NUMBER_MAX + 1):
            objective = (
                first_five_objective
                + values[a][f]
                + values[b][f]
                + values[c][f]
                + values[d][f]
                + values[e][f]
            )
            candidate = (a, b, c, d, e, f)
            if objective > best_objective:
                best_objective = objective
                best_ticket = candidate
    return best_ticket


def exact_six_optimum(
    pair_weights: Mapping[tuple[int, int], int] | Sequence[Sequence[int]],
) -> tuple[int, ...]:
    """Alias for :func:`construct_exact_six_ticket`."""

    return construct_exact_six_ticket(pair_weights)


def compute_semantic_signature(semantic_core: object) -> str:
    """Recompute the sealed SHA-256 signature from a semantic-core object."""

    canonical = json.dumps(
        semantic_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    return hashlib.sha256(canonical).hexdigest()


def _fallback_pair_rows() -> tuple[PairAuditRow, ...]:
    zero_weight = _fixed_point_from_quantum(0, PAIR_WEIGHT_SCALE, 30)
    return tuple(
        PairAuditRow(
            i=i,
            j=j,
            union_event_count=0,
            status=STATUS_FALLBACK_INSUFFICIENT_HISTORY,
            selected_candidate_start=None,
            d2_quantum=None,
            d2=None,
            weight=zero_weight,
            pair_weight_quantum=0,
        )
        for i in range(NUMBER_MIN, NUMBER_MAX + 1)
        for j in range(i + 1, NUMBER_MAX + 1)
    )


def _zero_number_rank_rows() -> tuple[NumberScoreRow, ...]:
    return tuple(
        NumberScoreRow(number=number, aggregate_score=0, rank=number)
        for number in range(NUMBER_MIN, NUMBER_MAX + 1)
    )


def analyze(history: object, cutoff: object) -> AnalysisResult:
    """Run the frozen method against one causal completed-draw boundary.

    For a valid cutoff below 256 no history element is accessed.  For a
    sufficient cutoff, exactly ``history[cutoff-256:cutoff]`` is read and
    validated before any pair computation begins.
    """

    cutoff_int, _history_length = _validate_cutoff(history, cutoff)
    if cutoff_int < MIN_HISTORY:
        rows = _fallback_pair_rows()
        return AnalysisResult(
            cutoff=cutoff_int,
            status=STATUS_FALLBACK_INSUFFICIENT_HISTORY,
            pair_rows=rows,
            number_rank_rows=_zero_number_rank_rows(),
            ticket=(1, 2, 3, 4, 5, 6),
        )

    validated_draws = _read_completed_window(history, cutoff_int)
    draw_sets = tuple(frozenset(draw) for draw in validated_draws)
    pair_rows, matrix = _build_pair_rows(draw_sets)
    number_rank_rows = aggregate_number_scores(matrix)
    ticket = construct_exact_six_ticket(matrix)
    return AnalysisResult(
        cutoff=cutoff_int,
        status=STATUS_OK,
        pair_rows=pair_rows,
        number_rank_rows=number_rank_rows,
        ticket=ticket,
    )


def analyze_biglotto_l2_pairwise_marked_matrix_profile(
    history: object, cutoff: object
) -> AnalysisResult:
    """Descriptive alias for :func:`analyze`."""

    return analyze(history, cutoff)


def run_analysis(history: object, cutoff: object) -> AnalysisResult:
    """Alias for :func:`analyze`."""

    return analyze(history, cutoff)


__all__ = [
    "DECIMAL_CONTEXT",
    "DESIGN_NAME",
    "MARK_BOTH",
    "MARK_I_ONLY",
    "MARK_J_ONLY",
    "METHOD_ID",
    "MIN_HISTORY",
    "MIN_UNION_EVENTS",
    "SEMANTIC_SIGNATURE",
    "STATUS_FALLBACK_INSUFFICIENT_HISTORY",
    "STATUS_INSUFFICIENT_PAIR_GEOMETRY",
    "STATUS_OK",
    "AnalysisResult",
    "InvalidCutoffError",
    "InvalidHistoryError",
    "NumberScoreRow",
    "NumericContractError",
    "PairAuditRow",
    "PairEvent",
    "PairMatrixContractError",
    "PairProfile",
    "aggregate_number_scores",
    "analyze",
    "analyze_biglotto_l2_pairwise_marked_matrix_profile",
    "compute_pair_profile",
    "compute_semantic_signature",
    "construct_exact_six_ticket",
    "distance_squared_quantum",
    "encode_marked_pair_union",
    "encode_pair_union_events",
    "exact_six_optimum",
    "pair_profile_from_events",
    "run_analysis",
    "standardize_gaps",
]
