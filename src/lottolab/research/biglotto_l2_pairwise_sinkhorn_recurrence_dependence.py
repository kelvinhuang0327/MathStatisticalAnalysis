"""Frozen NF06 recurrence-dependence computation for Big Lotto.

The module is deliberately a caller-owned, deterministic calculation.  It
uses the trailing 256 completed draws, converts each number to a capped
recurrence-age stream, and scores every unordered number pair with the frozen
debiased entropic transport functional.  The final six-number result is the
strictly exhaustive maximum of the 15 contained integer pair quanta.

The public helpers keep the mathematical stages inspectable for synthetic
verification.  No helper changes the frozen constants, adds smoothing, or
uses a stochastic tie-break.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, TypeGuard, cast


METHOD_ID: Final[str] = "BMSGV1_L2_PAIRWISE_NF06_SINKHORN_RECURRENCE_DEPENDENCE_V1"
DESIGN_NAME: Final[str] = "BIGLOTTO_L2_PAIRWISE_NF06_SINKHORN_RECURRENCE_DEPENDENCE_EXACT6_V1"
SEMANTIC_SIGNATURE: Final[str] = (
    "85b903d8369956c8a72acfb9aa625745d53697f090ab6198abed9769917ac446"
)

NUMBER_MIN: Final[int] = 1
NUMBER_MAX: Final[int] = 49
NUMBER_DOMAIN: Final[tuple[int, ...]] = tuple(range(NUMBER_MIN, NUMBER_MAX + 1))
DRAW_SIZE: Final[int] = 6
MIN_HISTORY: Final[int] = 256
WINDOW_SIZE: Final[int] = 256
W: Final[int] = WINDOW_SIZE
AGE_CAP: Final[int] = 16
G: Final[int] = AGE_CAP
SUPPORT_SIZE: Final[int] = AGE_CAP + 1
EPSILON: Final[float] = 1.0 / 32.0
SINKHORN_EPSILON: Final[float] = EPSILON
CONVERGENCE_TOLERANCE: Final[float] = 2.0**-40
SINKHORN_TOLERANCE: Final[float] = CONVERGENCE_TOLERANCE
MASS_TOLERANCE: Final[float] = CONVERGENCE_TOLERANCE
MAX_ITERATIONS: Final[int] = 10_000
PAIR_SCALE: Final[int] = 10**12
PAIR_QUANTUM_SCALE: Final[int] = PAIR_SCALE
UINT64_MAX: Final[int] = (1 << 64) - 1
PAIR_COUNT: Final[int] = (NUMBER_MAX * (NUMBER_MAX - 1)) // 2
TICKET_COUNT: Final[int] = 13_983_816
COST_DENOMINATOR: Final[int] = 2 * AGE_CAP

OK_STATUS: Final[str] = "OK"
COMPLETE_STATUS: Final[str] = OK_STATUS
FALLBACK_STATUS: Final[str] = "FALLBACK_INSUFFICIENT_HISTORY"
INVALID_INPUT_STATUS: Final[str] = "INVALID_INPUT"
NUMERIC_FAILURE_STATUS: Final[str] = "NUMERIC_FAILURE"
NONCONVERGENCE_STATUS: Final[str] = "NONCONVERGENCE"
CONVERGED_STATUS: Final[str] = "CONVERGED"
EXACT_INDEPENDENCE_STATUS: Final[str] = "EXACT_INDEPENDENCE"
ZERO_MASS_ZERO_ZERO_STATUS: Final[str] = "ZERO_MASS_ZERO_ZERO"

type Pair = tuple[int, int]
type Cell = tuple[int, int]
type Draw = tuple[int, ...]
type AgeSeries = tuple[int, ...]
type Plan = tuple[tuple[float, ...], ...]
type LogPlan = tuple[tuple[float, ...], ...]


class BigLottoL2PairwiseSinkhornError(ValueError):
    """Base class for closed-contract calculation errors."""


class InvalidInputError(BigLottoL2PairwiseSinkhornError):
    """The supplied cutoff, draw, support, or measure is invalid."""


class NumericInvariantError(BigLottoL2PairwiseSinkhornError):
    """A frozen numeric or structural invariant was violated."""


class NonconvergenceError(NumericInvariantError):
    """A required Sinkhorn solve exhausted its exact iteration cap."""


@dataclass(frozen=True, slots=True)
class PairCountTables:
    """Exact integer joint and marginal counts for one age-stream pair."""

    joint: tuple[tuple[int, ...], ...]
    left: tuple[int, ...]
    right: tuple[int, ...]
    total: int


@dataclass(frozen=True, slots=True)
class DiscreteMeasure:
    """A positive-support probability measure over age-pair cells."""

    support: tuple[Cell, ...]
    masses: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SinkhornIteration:
    """Residuals recorded after one complete log-domain u/v update."""

    iteration: int
    row_residual: float
    column_residual: float
    residual_inf: float


@dataclass(frozen=True, slots=True)
class SinkhornSolve:
    """Observable result of one frozen transport solve."""

    value: float | None
    iterations: int
    residual_inf: float | None
    row_residual: float | None
    column_residual: float | None
    status: str
    trace: tuple[SinkhornIteration, ...]

    @property
    def converged(self) -> bool:
        return self.status in (CONVERGED_STATUS, ZERO_MASS_ZERO_ZERO_STATUS)


@dataclass(frozen=True, slots=True)
class PairScoreResult:
    """Raw and quantized score plus the three transport solves."""

    raw_score: float
    quantum: int
    status: str
    cross: SinkhornSolve | None
    self_left: SinkhornSolve | None
    self_right: SinkhornSolve | None


def _is_non_boolean_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_tuple(value: object, *, label: str) -> tuple[object, ...]:
    try:
        return tuple(cast(Iterable[object], value))
    except Exception as exc:
        raise InvalidInputError(f"{label} must be iterable") from exc


def _validate_draw(raw_draw: object, *, index: int) -> Draw:
    raw_values = _as_tuple(raw_draw, label=f"history[{index}]")
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
    if history is None:
        raise InvalidInputError("history is required for a non-fallback computation")
    sequence = cast(Sequence[object], history)
    try:
        length = len(sequence)
    except Exception as exc:
        raise InvalidInputError("history must be a finite indexed sequence") from exc
    if not _is_non_boolean_integer(length) or length < 0:
        raise InvalidInputError("history length is invalid")
    return length


def _validated_cutoff(cutoff: object, history_length: int) -> int:
    if not _is_non_boolean_integer(cutoff):
        raise InvalidInputError("cutoff must be a non-boolean integer")
    if cutoff < 0 or cutoff > history_length:
        raise InvalidInputError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return cutoff


def _read_causal_window(history: object, cutoff: int) -> tuple[Draw, ...]:
    sequence = cast(Sequence[object], history)
    draws: list[Draw] = []
    for index in range(cutoff - WINDOW_SIZE, cutoff):
        try:
            raw_draw = sequence[index]
        except Exception as exc:
            raise InvalidInputError(f"history[{index}] could not be read") from exc
        draws.append(_validate_draw(raw_draw, index=index))
    if len(draws) != WINDOW_SIZE:
        raise NumericInvariantError("causal window length is not 256")
    return tuple(draws)


def build_recurrence_ages(draws: object) -> tuple[AgeSeries, ...]:
    """Build the 49 capped age streams in chronological draw order."""

    raw_draws = _as_tuple(draws, label="draws")
    normalized = tuple(
        _validate_draw(raw_draw, index=index) for index, raw_draw in enumerate(raw_draws)
    )
    streams = [[0 for _ in normalized] for _ in NUMBER_DOMAIN]
    last_occurrence: list[int | None] = [None for _ in range(NUMBER_MAX + 1)]

    for time_index, draw in enumerate(normalized):
        present = [False for _ in range(NUMBER_MAX + 1)]
        for number in draw:
            present[number] = True
        for number_index, number in enumerate(NUMBER_DOMAIN):
            if present[number]:
                age = 0
            else:
                previous = last_occurrence[number]
                age = AGE_CAP if previous is None else min(AGE_CAP, time_index - previous)
            streams[number_index][time_index] = age
        for number in draw:
            last_occurrence[number] = time_index

    return tuple(tuple(stream) for stream in streams)


def recurrence_ages(draws: object) -> tuple[AgeSeries, ...]:
    """Compatibility spelling for :func:`build_recurrence_ages`."""

    return build_recurrence_ages(draws)


def _validate_age_series(values: object, *, label: str, allow_empty: bool = False) -> AgeSeries:
    raw_values = _as_tuple(values, label=label)
    if not raw_values and not allow_empty:
        raise InvalidInputError(f"{label} must not be empty")
    if any(
        not _is_non_boolean_integer(value) or value < 0 or value > AGE_CAP
        for value in raw_values
    ):
        raise InvalidInputError(f"{label} must contain integer ages in 0..{AGE_CAP}")
    return cast(tuple[int, ...], raw_values)


def build_age_histogram(values: object) -> tuple[int, ...]:
    """Return exact counts for ages 0 through 16."""

    ages = _validate_age_series(values, label="age series")
    histogram = [0 for _ in range(SUPPORT_SIZE)]
    for age in ages:
        histogram[age] += 1
    return tuple(histogram)


def build_marginal_counts(values: object) -> tuple[int, ...]:
    """Compatibility spelling for the exact age histogram."""

    return build_age_histogram(values)


def build_joint_counts(left: object, right: object) -> tuple[tuple[int, ...], ...]:
    """Return the exact 17-by-17 joint age count matrix."""

    left_values = _validate_age_series(left, label="left age series")
    right_values = _validate_age_series(right, label="right age series")
    if len(left_values) != len(right_values):
        raise InvalidInputError("left and right age series must have the same length")
    joint = [[0 for _ in range(SUPPORT_SIZE)] for _ in range(SUPPORT_SIZE)]
    for left_age, right_age in zip(left_values, right_values, strict=True):
        joint[left_age][right_age] += 1
    return tuple(tuple(row) for row in joint)


def _validate_count_vector(values: object, *, label: str) -> tuple[int, ...]:
    raw_values = _as_tuple(values, label=label)
    if len(raw_values) != SUPPORT_SIZE:
        raise NumericInvariantError(f"{label} must contain exactly {SUPPORT_SIZE} cells")
    if any(not _is_non_boolean_integer(value) or value < 0 for value in raw_values):
        raise NumericInvariantError(f"{label} must contain non-negative integer counts")
    return cast(tuple[int, ...], raw_values)


def _validate_count_matrix(values: object, *, label: str) -> tuple[tuple[int, ...], ...]:
    raw_rows = _as_tuple(values, label=label)
    if len(raw_rows) != SUPPORT_SIZE:
        raise NumericInvariantError(f"{label} must have {SUPPORT_SIZE} rows")
    return tuple(
        _validate_count_vector(row, label=f"{label}[{row_index}]")
        for row_index, row in enumerate(raw_rows)
    )


def build_pair_counts(left: object, right: object) -> PairCountTables:
    """Build a joint table and its two exact marginal count vectors."""

    left_values = _validate_age_series(left, label="left age series")
    right_values = _validate_age_series(right, label="right age series")
    if len(left_values) != len(right_values):
        raise InvalidInputError("left and right age series must have the same length")
    joint = build_joint_counts(left_values, right_values)
    left_counts = tuple(sum(row) for row in joint)
    right_counts = tuple(
        sum(joint[row][column] for row in range(SUPPORT_SIZE))
        for column in range(SUPPORT_SIZE)
    )
    total = len(left_values)
    return PairCountTables(joint, left_counts, right_counts, total)


def _canonical_pair_counts(tables: PairCountTables) -> PairCountTables:
    joint = _validate_count_matrix(tables.joint, label="joint counts")
    left = _validate_count_vector(tables.left, label="left marginal counts")
    right = _validate_count_vector(tables.right, label="right marginal counts")
    total = tables.total
    if not _is_non_boolean_integer(total) or total <= 0:
        raise NumericInvariantError("pair count total must be a positive integer")
    if sum(left) != total or sum(right) != total:
        raise NumericInvariantError("marginal count totals do not match the joint total")
    if any(sum(joint[row]) != left[row] for row in range(SUPPORT_SIZE)):
        raise NumericInvariantError("left marginal does not match joint counts")
    if any(
        sum(joint[row][column] for row in range(SUPPORT_SIZE)) != right[column]
        for column in range(SUPPORT_SIZE)
    ):
        raise NumericInvariantError("right marginal does not match joint counts")
    return PairCountTables(joint, left, right, total)


def is_exactly_independent(tables: PairCountTables) -> bool:
    """Apply the integer independence equality with no tolerance."""

    canonical = _canonical_pair_counts(tables)
    total = canonical.total
    return all(
        canonical.joint[left_age][right_age] * total
        == canonical.left[left_age] * canonical.right[right_age]
        for left_age in range(SUPPORT_SIZE)
        for right_age in range(SUPPORT_SIZE)
    )


def exact_independence(tables: PairCountTables) -> bool:
    """Compatibility spelling for :func:`is_exactly_independent`."""

    return is_exactly_independent(tables)


def _validate_cell(value: object, *, label: str) -> Cell:
    raw_values = _as_tuple(value, label=label)
    if len(raw_values) != 2 or any(not _is_non_boolean_integer(item) for item in raw_values):
        raise InvalidInputError(f"{label} must be a two-integer age cell")
    cell = cast(tuple[int, int], raw_values)
    if any(item < 0 or item > AGE_CAP for item in cell):
        raise InvalidInputError(f"{label} values must lie in 0..{AGE_CAP}")
    return cell


def ground_cost(left: Cell, right: Cell) -> float:
    """Return the frozen Manhattan ground cost between two age cells."""

    left_cell = _validate_cell(left, label="left cell")
    right_cell = _validate_cell(right, label="right cell")
    distance = abs(left_cell[0] - right_cell[0]) + abs(left_cell[1] - right_cell[1])
    return distance / float(COST_DENOMINATOR)


def cost(left: Cell, right: Cell) -> float:
    """Compatibility spelling for :func:`ground_cost`."""

    return ground_cost(left, right)


def build_cost_matrix(row_support: object, column_support: object) -> tuple[tuple[float, ...], ...]:
    """Build a cost matrix in the caller-provided support order."""

    rows = tuple(
        _validate_cell(cell, label="row support cell")
        for cell in _as_tuple(row_support, label="row support")
    )
    columns = tuple(
        _validate_cell(cell, label="column support cell")
        for cell in _as_tuple(column_support, label="column support")
    )
    if not rows or not columns:
        raise InvalidInputError("cost matrix supports must not be empty")
    return tuple(tuple(ground_cost(row, column) for column in columns) for row in rows)


def cost_matrix(row_support: object, column_support: object) -> tuple[tuple[float, ...], ...]:
    """Compatibility spelling for :func:`build_cost_matrix`."""

    return build_cost_matrix(row_support, column_support)


def _support_from_count_matrix(
    counts: tuple[tuple[int, ...], ...], *, total: int
) -> DiscreteMeasure:
    support: list[Cell] = []
    masses: list[float] = []
    for left_age in range(SUPPORT_SIZE):
        for right_age in range(SUPPORT_SIZE):
            count = counts[left_age][right_age]
            if count > 0:
                support.append((left_age, right_age))
                masses.append(count / float(total))
    return DiscreteMeasure(tuple(support), tuple(masses))


def measure_from_counts(counts: object) -> DiscreteMeasure:
    """Construct the positive-support empirical measure from integer counts."""

    matrix = _validate_count_matrix(counts, label="measure counts")
    total = sum(sum(row) for row in matrix)
    if total == 0:
        return DiscreteMeasure((), ())
    return _support_from_count_matrix(matrix, total=total)


def product_measure(left_counts: object, right_counts: object) -> DiscreteMeasure:
    """Construct the tensor product of two exact marginal count vectors."""

    left = _validate_count_vector(left_counts, label="left marginal counts")
    right = _validate_count_vector(right_counts, label="right marginal counts")
    left_total = sum(left)
    right_total = sum(right)
    if left_total == 0 and right_total == 0:
        return DiscreteMeasure((), ())
    if left_total == 0 or right_total == 0:
        raise NumericInvariantError("zero-positive product measure is invalid")
    support: list[Cell] = []
    masses: list[float] = []
    denominator = float(left_total * right_total)
    for left_age in range(SUPPORT_SIZE):
        if left[left_age] == 0:
            continue
        for right_age in range(SUPPORT_SIZE):
            if right[right_age] == 0:
                continue
            support.append((left_age, right_age))
            masses.append((left[left_age] * right[right_age]) / denominator)
    return DiscreteMeasure(tuple(support), tuple(masses))


def _normalise_measure(support: object, masses: object, *, label: str) -> DiscreteMeasure:
    raw_support = _as_tuple(support, label=f"{label} support")
    raw_masses = _as_tuple(masses, label=f"{label} masses")
    if not raw_support and not raw_masses:
        return DiscreteMeasure((), ())
    if len(raw_support) != len(raw_masses) or not raw_support:
        raise InvalidInputError(f"{label} support and masses must have the same positive length")
    cells = tuple(
        _validate_cell(cell, label=f"{label} support[{index}]")
        for index, cell in enumerate(raw_support)
    )
    if tuple(sorted(cells)) != cells or len(set(cells)) != len(cells):
        raise NumericInvariantError(f"{label} support must be unique and lexicographically sorted")
    normalized_masses: list[float] = []
    for index, value in enumerate(raw_masses):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidInputError(f"{label} mass[{index}] must be a real binary64 value")
        mass = float(value)
        if not math.isfinite(mass) or mass <= 0.0:
            raise NumericInvariantError(f"{label} masses must be finite and positive")
        normalized_masses.append(mass)
    total = 0.0
    for mass in normalized_masses:
        total += mass
    if not math.isfinite(total) or abs(total - 1.0) > MASS_TOLERANCE:
        raise NumericInvariantError(f"{label} masses must sum to one within the frozen tolerance")
    return DiscreteMeasure(cells, tuple(normalized_masses))


def _scalar_exp(value: float) -> float:
    try:
        result = math.exp(value)
    except (OverflowError, ValueError) as exc:
        raise NumericInvariantError("scalar exponential failed") from exc
    if math.isnan(result):
        raise NumericInvariantError("scalar exponential returned NaN")
    return result


def _scalar_log(value: float) -> float:
    try:
        result = math.log(value)
    except (OverflowError, ValueError) as exc:
        raise NumericInvariantError("scalar logarithm failed") from exc
    if not math.isfinite(result):
        raise NumericInvariantError("scalar logarithm returned a non-finite value")
    return result


def _logsumexp(values: Iterable[float]) -> float:
    terms = tuple(values)
    if not terms or any(not math.isfinite(term) for term in terms):
        raise NumericInvariantError("log-sum-exp received an invalid term")
    maximum = terms[0]
    for term in terms[1:]:
        if term > maximum:
            maximum = term
    total = 0.0
    for term in terms:
        addend = _scalar_exp(term - maximum)
        total += addend
    if not math.isfinite(total) or total <= 0.0:
        raise NumericInvariantError("log-sum-exp accumulated an invalid sum")
    result = maximum + _scalar_log(total)
    if not math.isfinite(result):
        raise NumericInvariantError("log-sum-exp returned a non-finite value")
    return result


def _validate_solver_options(tolerance: object, max_iterations: object) -> tuple[float, int]:
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise InvalidInputError("tolerance must be a real binary64 value")
    normalized_tolerance = float(tolerance)
    if not math.isfinite(normalized_tolerance) or normalized_tolerance <= 0.0:
        raise InvalidInputError("tolerance must be finite and positive")
    if not _is_non_boolean_integer(max_iterations) or max_iterations < 0:
        raise InvalidInputError("max_iterations must be a non-negative integer")
    return normalized_tolerance, max_iterations


def _plan_and_residual(
    row_support: tuple[Cell, ...],
    column_support: tuple[Cell, ...],
    log_kernel: tuple[tuple[float, ...], ...],
    log_u: Sequence[float],
    log_v: Sequence[float],
    row_masses: tuple[float, ...],
    column_masses: tuple[float, ...],
) -> tuple[Plan, LogPlan, float, float, float]:
    plan_rows: list[tuple[float, ...]] = []
    log_plan_rows: list[tuple[float, ...]] = []
    column_sums = [0.0 for _ in column_support]
    row_residual = 0.0

    for row_index in range(len(row_support)):
        row_plan: list[float] = []
        row_log_plan: list[float] = []
        row_sum = 0.0
        for column_index in range(len(column_support)):
            log_value = log_u[row_index] + log_kernel[row_index][column_index] + log_v[column_index]
            if not math.isfinite(log_value):
                raise NumericInvariantError("transport plan log value is non-finite")
            probability = _scalar_exp(log_value)
            if not math.isfinite(probability):
                raise NumericInvariantError("transport plan value is non-finite")
            row_log_plan.append(log_value)
            row_plan.append(probability)
            row_sum += probability
            column_sums[column_index] += probability
        if not math.isfinite(row_sum):
            raise NumericInvariantError("transport row sum is non-finite")
        difference = abs(row_sum - row_masses[row_index])
        if difference > row_residual:
            row_residual = difference
        plan_rows.append(tuple(row_plan))
        log_plan_rows.append(tuple(row_log_plan))

    column_residual = 0.0
    for column_index, column_sum in enumerate(column_sums):
        if not math.isfinite(column_sum):
            raise NumericInvariantError("transport column sum is non-finite")
        difference = abs(column_sum - column_masses[column_index])
        if difference > column_residual:
            column_residual = difference
    residual_inf = max(row_residual, column_residual)
    if not math.isfinite(residual_inf):
        raise NumericInvariantError("transport residual is non-finite")
    return (
        tuple(plan_rows),
        tuple(log_plan_rows),
        row_residual,
        column_residual,
        residual_inf,
    )


def _transport_value(
    row_support: tuple[Cell, ...],
    column_support: tuple[Cell, ...],
    row_masses: tuple[float, ...],
    column_masses: tuple[float, ...],
    plan: Plan,
    log_plan: LogPlan,
) -> float:
    log_row_masses = tuple(_scalar_log(value) for value in row_masses)
    log_column_masses = tuple(_scalar_log(value) for value in column_masses)
    transport_cost = 0.0
    relative_entropy = 0.0
    for row_index, row in enumerate(plan):
        for column_index, probability in enumerate(row):
            if probability == 0.0:
                continue
            distance = abs(row_support[row_index][0] - column_support[column_index][0]) + abs(
                row_support[row_index][1] - column_support[column_index][1]
            )
            transport_cost += probability * (distance / float(COST_DENOMINATOR))
            log_ratio = (
                log_plan[row_index][column_index]
                - log_row_masses[row_index]
                - log_column_masses[column_index]
            )
            if not math.isfinite(log_ratio):
                raise NumericInvariantError("transport relative-entropy term is non-finite")
            relative_entropy += probability * log_ratio
    value = transport_cost + EPSILON * relative_entropy
    if not math.isfinite(value):
        raise NumericInvariantError("entropic transport value is non-finite")
    return value


def _solve_transport(
    row_measure: DiscreteMeasure,
    column_measure: DiscreteMeasure,
    *,
    tolerance: float,
    max_iterations: int,
) -> SinkhornSolve:
    if not row_measure.support and not column_measure.support:
        return SinkhornSolve(
            value=0.0,
            iterations=0,
            residual_inf=0.0,
            row_residual=0.0,
            column_residual=0.0,
            status=ZERO_MASS_ZERO_ZERO_STATUS,
            trace=(),
        )
    if not row_measure.support or not column_measure.support:
        raise NumericInvariantError("zero-positive transport measure mismatch")

    row_support = row_measure.support
    column_support = column_measure.support
    row_masses = row_measure.masses
    column_masses = column_measure.masses
    log_kernel = tuple(
        tuple(
            -float(
                abs(row[0] - column[0]) + abs(row[1] - column[1])
            )
            for column in column_support
        )
        for row in row_support
    )
    log_row_masses = tuple(_scalar_log(value) for value in row_masses)
    log_column_masses = tuple(_scalar_log(value) for value in column_masses)
    log_u = [0.0 for _ in row_support]
    log_v = [0.0 for _ in column_support]
    trace: list[SinkhornIteration] = []
    last_residual: float | None = None
    last_row_residual: float | None = None
    last_column_residual: float | None = None

    for iteration in range(1, max_iterations + 1):
        next_log_u: list[float] = []
        for row_index in range(len(row_support)):
            terms = (
                log_kernel[row_index][column_index] + log_v[column_index]
                for column_index in range(len(column_support))
            )
            updated = log_row_masses[row_index] - _logsumexp(terms)
            if not math.isfinite(updated):
                raise NumericInvariantError("row scaling value is non-finite")
            next_log_u.append(updated)

        next_log_v: list[float] = []
        for column_index in range(len(column_support)):
            terms = (
                log_kernel[row_index][column_index] + next_log_u[row_index]
                for row_index in range(len(row_support))
            )
            updated = log_column_masses[column_index] - _logsumexp(terms)
            if not math.isfinite(updated):
                raise NumericInvariantError("column scaling value is non-finite")
            next_log_v.append(updated)

        plan, log_plan, row_residual, column_residual, residual_inf = _plan_and_residual(
            row_support,
            column_support,
            log_kernel,
            next_log_u,
            next_log_v,
            row_masses,
            column_masses,
        )
        trace.append(
            SinkhornIteration(
                iteration=iteration,
                row_residual=row_residual,
                column_residual=column_residual,
                residual_inf=residual_inf,
            )
        )
        log_u = next_log_u
        log_v = next_log_v
        last_residual = residual_inf
        last_row_residual = row_residual
        last_column_residual = column_residual
        if residual_inf <= tolerance:
            value = _transport_value(
                row_support,
                column_support,
                row_masses,
                column_masses,
                plan,
                log_plan,
            )
            return SinkhornSolve(
                value=value,
                iterations=iteration,
                residual_inf=residual_inf,
                row_residual=row_residual,
                column_residual=column_residual,
                status=CONVERGED_STATUS,
                trace=tuple(trace),
            )

    return SinkhornSolve(
        value=None,
        iterations=max_iterations,
        residual_inf=last_residual,
        row_residual=last_row_residual,
        column_residual=last_column_residual,
        status=NONCONVERGENCE_STATUS,
        trace=tuple(trace),
    )


def sinkhorn_solve(
    row_support: object,
    row_masses: object,
    column_support: object,
    column_masses: object,
    *,
    tolerance: object = CONVERGENCE_TOLERANCE,
    max_iterations: object = MAX_ITERATIONS,
) -> SinkhornSolve:
    """Run the exact log-domain scaling contract for two supplied measures."""

    normalized_tolerance, normalized_max_iterations = _validate_solver_options(
        tolerance, max_iterations
    )
    rows = _normalise_measure(row_support, row_masses, label="row")
    columns = _normalise_measure(column_support, column_masses, label="column")
    return _solve_transport(
        rows,
        columns,
        tolerance=normalized_tolerance,
        max_iterations=normalized_max_iterations,
    )


def sinkhorn_transport(
    row_support: object,
    row_masses: object,
    column_support: object,
    column_masses: object,
    *,
    tolerance: object = CONVERGENCE_TOLERANCE,
    max_iterations: object = MAX_ITERATIONS,
) -> float:
    """Return a converged entropic transport value or fail closed."""

    result = sinkhorn_solve(
        row_support,
        row_masses,
        column_support,
        column_masses,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )
    if result.status == NONCONVERGENCE_STATUS:
        raise NonconvergenceError("Sinkhorn iteration cap exhausted")
    if result.value is None:
        raise NumericInvariantError("Sinkhorn solve did not produce a value")
    return result.value


def sinkhorn_ot(
    row_support: object,
    row_masses: object,
    column_support: object,
    column_masses: object,
    *,
    tolerance: object = CONVERGENCE_TOLERANCE,
    max_iterations: object = MAX_ITERATIONS,
) -> float:
    """Compatibility spelling for :func:`sinkhorn_transport`."""

    return sinkhorn_transport(
        row_support,
        row_masses,
        column_support,
        column_masses,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )


def sinkhorn_divergence(left: DiscreteMeasure, right: DiscreteMeasure) -> float:
    """Return the symmetric debiased entropic transport divergence."""

    left_measure = _normalise_measure(left.support, left.masses, label="left")
    right_measure = _normalise_measure(right.support, right.masses, label="right")
    cross = sinkhorn_solve(
        left_measure.support,
        left_measure.masses,
        right_measure.support,
        right_measure.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    self_left = sinkhorn_solve(
        left_measure.support,
        left_measure.masses,
        left_measure.support,
        left_measure.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    self_right = sinkhorn_solve(
        right_measure.support,
        right_measure.masses,
        right_measure.support,
        right_measure.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    solves = (cross, self_left, self_right)
    if any(result.status == NONCONVERGENCE_STATUS for result in solves):
        raise NonconvergenceError("debiased divergence transport solve did not converge")
    if any(result.value is None for result in solves):
        raise NumericInvariantError("debiased divergence solve has no value")
    cross_value = cross.value
    self_left_value = self_left.value
    self_right_value = self_right.value
    if cross_value is None or self_left_value is None or self_right_value is None:
        raise NumericInvariantError("debiased divergence solve has no value")
    raw = cross_value - 0.5 * self_left_value - 0.5 * self_right_value
    if not math.isfinite(raw):
        raise NumericInvariantError("debiased divergence is non-finite")
    if raw < 0.0:
        if raw >= -MASS_TOLERANCE:
            return 0.0
        raise NumericInvariantError("debiased divergence is materially negative")
    return raw


def _quantize_score(raw_score: float) -> int:
    if not math.isfinite(raw_score):
        raise NumericInvariantError("pair score is non-finite")
    score = raw_score
    if score < 0.0:
        if score >= -MASS_TOLERANCE:
            score = 0.0
        else:
            raise NumericInvariantError("pair score is materially negative")
    scaled = max(0.0, score) * float(PAIR_SCALE)
    if not math.isfinite(scaled):
        raise NumericInvariantError("quantized pair score is non-finite")
    quantum = int(round(scaled))
    if quantum < 0 or quantum > UINT64_MAX:
        raise NumericInvariantError("pair score is outside uint64")
    return quantum


def quantize_pair_score(raw_score: float) -> int:
    """Apply the frozen nonnegative binary64 half-even quantization."""

    return _quantize_score(raw_score)


def pair_score_details_from_counts(tables: PairCountTables) -> PairScoreResult:
    """Score one exact joint count table against its product marginal."""

    canonical = _canonical_pair_counts(tables)
    if is_exactly_independent(canonical):
        return PairScoreResult(0.0, 0, EXACT_INDEPENDENCE_STATUS, None, None, None)

    joint_measure = _support_from_count_matrix(canonical.joint, total=canonical.total)
    product = product_measure(canonical.left, canonical.right)
    cross = sinkhorn_solve(
        joint_measure.support,
        joint_measure.masses,
        product.support,
        product.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    self_left = sinkhorn_solve(
        joint_measure.support,
        joint_measure.masses,
        joint_measure.support,
        joint_measure.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    self_right = sinkhorn_solve(
        product.support,
        product.masses,
        product.support,
        product.masses,
        tolerance=CONVERGENCE_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    solves = (cross, self_left, self_right)
    if any(result.status == NONCONVERGENCE_STATUS for result in solves):
        raise NonconvergenceError("pair debiasing solve did not converge")
    if any(result.value is None for result in solves):
        raise NumericInvariantError("pair debiasing solve has no value")
    cross_value = cross.value
    self_left_value = self_left.value
    self_right_value = self_right.value
    if cross_value is None or self_left_value is None or self_right_value is None:
        raise NumericInvariantError("pair debiasing solve has no value")
    raw_score = cross_value - 0.5 * self_left_value - 0.5 * self_right_value
    if not math.isfinite(raw_score):
        raise NumericInvariantError("raw pair score is non-finite")
    if raw_score < 0.0:
        if raw_score >= -MASS_TOLERANCE:
            raw_score = 0.0
        else:
            raise NumericInvariantError("raw pair score is materially negative")
    return PairScoreResult(
        raw_score=raw_score,
        quantum=_quantize_score(raw_score),
        status=CONVERGED_STATUS,
        cross=cross,
        self_left=self_left,
        self_right=self_right,
    )


def pair_score_from_counts(tables: PairCountTables) -> int:
    """Return the stored uint64 pair quantum for exact count tables."""

    return pair_score_details_from_counts(tables).quantum


def pair_score_raw(left: object, right: object) -> float:
    """Return the unquantized debiased score for two age streams."""

    return pair_score_details_from_counts(build_pair_counts(left, right)).raw_score


def pair_score(left: object, right: object) -> int:
    """Return the frozen uint64 pair score for two age streams."""

    return pair_score_details_from_counts(build_pair_counts(left, right)).quantum


def pair_quantum(left: object, right: object) -> int:
    """Compatibility spelling for :func:`pair_score`."""

    return pair_score(left, right)


def pair_weight(left: object, right: object) -> int:
    """Compatibility spelling for :func:`pair_score`."""

    return pair_score(left, right)


def _pair_keys() -> tuple[Pair, ...]:
    return tuple(
        (left, right)
        for left in NUMBER_DOMAIN
        for right in NUMBER_DOMAIN
        if left < right
    )


PAIR_KEYS: Final[tuple[Pair, ...]] = _pair_keys()


def _pair_weights_from_ages(ages: tuple[AgeSeries, ...]) -> dict[Pair, int]:
    if len(ages) != NUMBER_MAX:
        raise NumericInvariantError("age matrix must contain 49 number streams")
    normalized_ages = tuple(
        _validate_age_series(series, label=f"age stream {number}")
        for number, series in enumerate(ages, 1)
    )
    if any(len(series) != WINDOW_SIZE for series in normalized_ages):
        raise NumericInvariantError("every age stream must contain exactly 256 values")
    histograms = tuple(build_age_histogram(series) for series in normalized_ages)
    result: dict[Pair, int] = {}
    for left_index, left_number in enumerate(NUMBER_DOMAIN):
        for right_index in range(left_index + 1, len(NUMBER_DOMAIN)):
            right_number = NUMBER_DOMAIN[right_index]
            joint = [[0 for _ in range(SUPPORT_SIZE)] for _ in range(SUPPORT_SIZE)]
            left_stream = normalized_ages[left_index]
            right_stream = normalized_ages[right_index]
            for left_age, right_age in zip(left_stream, right_stream, strict=True):
                joint[left_age][right_age] += 1
            tables = PairCountTables(
                tuple(tuple(row) for row in joint),
                histograms[left_index],
                histograms[right_index],
                WINDOW_SIZE,
            )
            result[(left_number, right_number)] = pair_score_from_counts(tables)
    if tuple(result) != PAIR_KEYS:
        raise NumericInvariantError("pair matrix does not contain exactly 1,176 ordered edges")
    return result


def pair_weights_from_ages(ages: object) -> Mapping[Pair, int]:
    """Build the complete canonical upper-triangular pair matrix."""

    raw_ages = _as_tuple(ages, label="age matrix")
    normalized = tuple(
        _validate_age_series(series, label=f"age stream {number}")
        for number, series in enumerate(raw_ages, 1)
    )
    return MappingProxyType(_pair_weights_from_ages(normalized))


def _zero_pair_weights() -> dict[Pair, int]:
    return {pair: 0 for pair in PAIR_KEYS}


def zero_pair_weights() -> Mapping[Pair, int]:
    """Return a fresh canonical all-zero 1,176-edge matrix."""

    return MappingProxyType(_zero_pair_weights())


def _canonical_pair_weight_map(
    pair_weights: Mapping[Pair, object], *, require_complete: bool
) -> dict[Pair, int]:
    normalized = _zero_pair_weights()
    for raw_key, raw_value in pair_weights.items():
        key = _as_tuple(raw_key, label="pair key")
        if len(key) != 2 or any(not _is_non_boolean_integer(item) for item in key):
            raise InvalidInputError("pair keys must be two non-boolean integers")
        left, right = cast(tuple[int, int], key)
        if (left, right) not in normalized:
            raise InvalidInputError("pair key must satisfy 1 <= i < j <= 49")
        if not _is_non_boolean_integer(raw_value) or raw_value < 0 or raw_value > UINT64_MAX:
            raise NumericInvariantError("pair weights must be uint64 integers")
        normalized[(left, right)] = raw_value
    if require_complete and len(pair_weights) != PAIR_COUNT:
        raise NumericInvariantError("all 1,176 unordered pair weights are required")
    return {pair: normalized[pair] for pair in PAIR_KEYS}


def incident_pair_sums(pair_weights: Mapping[Pair, object]) -> Mapping[int, int]:
    """Return the exact diagnostic incident sum for each number."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    totals = {number: 0 for number in NUMBER_DOMAIN}
    for left, right in PAIR_KEYS:
        weight = normalized[(left, right)]
        totals[left] += weight
        totals[right] += weight
        if totals[left] > UINT64_MAX or totals[right] > UINT64_MAX:
            raise NumericInvariantError("number aggregate is outside uint64")
    return MappingProxyType(totals)


def number_aggregation(pair_weights: Mapping[Pair, object]) -> Mapping[int, int]:
    """Compatibility spelling for :func:`incident_pair_sums`."""

    return incident_pair_sums(pair_weights)


def rank_numbers(pair_weights: Mapping[Pair, object]) -> tuple[int, ...]:
    """Rank numbers by descending incident sum, then ascending number."""

    aggregates = incident_pair_sums(pair_weights)
    return tuple(sorted(NUMBER_DOMAIN, key=lambda number: (-aggregates[number], number)))


def _validate_ticket(ticket: object) -> tuple[int, ...]:
    raw_values = _as_tuple(ticket, label="ticket")
    if len(raw_values) != DRAW_SIZE or any(
        not _is_non_boolean_integer(value) for value in raw_values
    ):
        raise InvalidInputError("ticket must contain exactly six integer values")
    values = cast(tuple[int, ...], raw_values)
    if tuple(sorted(values)) != values or len(set(values)) != DRAW_SIZE:
        raise InvalidInputError("ticket must be sorted and unique")
    if any(value < NUMBER_MIN or value > NUMBER_MAX for value in values):
        raise InvalidInputError("ticket values must lie in 1..49")
    return values


def ticket_objective(ticket: object, pair_weights: Mapping[Pair, object]) -> int:
    """Return the exact sum of the 15 pair quanta contained in a ticket."""

    values = _validate_ticket(ticket)
    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    objective = 0
    for left_index in range(DRAW_SIZE):
        for right_index in range(left_index + 1, DRAW_SIZE):
            objective += normalized[(values[left_index], values[right_index])]
    if objective > UINT64_MAX:
        raise NumericInvariantError("ticket objective is outside uint64")
    return objective


def optimize_ticket(pair_weights: Mapping[Pair, object]) -> tuple[tuple[int, ...], int]:
    """Exhaustively maximize all 13,983,816 legal six-subsets."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    scaled = [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]
    for (left, right), value in normalized.items():
        scaled[left][right] = value

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
    if best_score != ticket_objective(best_ticket, normalized):
        raise NumericInvariantError("ticket objective disagrees with exhaustive sum")
    return best_ticket, best_score


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete, fallback, or fail-closed result for one invocation."""

    method_id: str
    design_name: str
    status: str
    window_size: int
    pair_weights: Mapping[Pair, int]
    ticket_objective: int | None
    ticket: tuple[int, ...] | None
    number_level_aggregation: Mapping[int, int] | None = None
    cutoff: int | None = None
    number_rank: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.design_name != DESIGN_NAME:
            raise NumericInvariantError("result identity does not match the frozen NF06 identity")
        if self.window_size != WINDOW_SIZE:
            raise NumericInvariantError("result window size does not match the frozen value")
        if self.status not in {
            COMPLETE_STATUS,
            FALLBACK_STATUS,
            INVALID_INPUT_STATUS,
            NUMERIC_FAILURE_STATUS,
            NONCONVERGENCE_STATUS,
        }:
            raise NumericInvariantError("unknown NF06 result status")
        if self.cutoff is not None and (
            not _is_non_boolean_integer(self.cutoff) or self.cutoff < 0
        ):
            raise NumericInvariantError("result cutoff is invalid")

        if self.status in (COMPLETE_STATUS, FALLBACK_STATUS):
            normalized = _canonical_pair_weight_map(self.pair_weights, require_complete=True)
            object.__setattr__(self, "pair_weights", MappingProxyType(normalized))
            if self.ticket_objective is None or not _is_non_boolean_integer(self.ticket_objective):
                raise NumericInvariantError("successful result objective must be uint64")
            if self.ticket_objective < 0 or self.ticket_objective > UINT64_MAX:
                raise NumericInvariantError("successful result objective is outside uint64")
            ticket = _validate_ticket(self.ticket)
            object.__setattr__(self, "ticket", ticket)
            expected_aggregates = incident_pair_sums(normalized)
            if self.number_level_aggregation is None:
                aggregates = expected_aggregates
            else:
                aggregates = _canonical_aggregate_map(self.number_level_aggregation)
                if dict(aggregates) != dict(expected_aggregates):
                    raise NumericInvariantError("result aggregates disagree with pair weights")
            object.__setattr__(self, "number_level_aggregation", aggregates)
            expected_rank = rank_numbers(normalized)
            supplied_rank = tuple(self.number_rank) if self.number_rank else expected_rank
            if supplied_rank != expected_rank:
                raise NumericInvariantError("result number rank disagrees with aggregates")
            object.__setattr__(self, "number_rank", supplied_rank)
            if self.ticket_objective != ticket_objective(ticket, normalized):
                raise NumericInvariantError("result objective disagrees with ticket pairs")
            if self.status == FALLBACK_STATUS:
                if (
                    self.ticket_objective != 0
                    or ticket != (1, 2, 3, 4, 5, 6)
                    or any(value != 0 for value in normalized.values())
                ):
                    raise NumericInvariantError("fallback result does not match frozen output")
        else:
            if len(self.pair_weights) != 0:
                raise NumericInvariantError("fail-closed result must not contain pair output")
            object.__setattr__(self, "pair_weights", MappingProxyType({}))
            if self.ticket_objective is not None or self.ticket is not None:
                raise NumericInvariantError("fail-closed result must not contain ticket output")
            if self.number_level_aggregation is not None and len(
                self.number_level_aggregation
            ) != 0:
                raise NumericInvariantError("fail-closed result must not contain aggregate output")
            object.__setattr__(self, "number_level_aggregation", MappingProxyType({}))
            if self.number_rank:
                raise NumericInvariantError("fail-closed result must not contain rank output")
            object.__setattr__(self, "number_rank", ())

    @property
    def semantic_signature(self) -> str:
        return SEMANTIC_SIGNATURE

    @property
    def min_history(self) -> int:
        return MIN_HISTORY

    @property
    def age_cap(self) -> int:
        return AGE_CAP

    @property
    def number_aggregates(self) -> Mapping[int, int]:
        return cast(Mapping[int, int], self.number_level_aggregation)

    @property
    def pair_weight_matrix(self) -> Mapping[Pair, int]:
        return self.pair_weights

    def canonical_dict(self) -> dict[str, object]:
        """Return an insertion-ordered JSON-ready representation."""

        pair_payload = {
            f"{left}-{right}": value for (left, right), value in self.pair_weights.items()
        }
        aggregate_payload = {
            str(number): value
            for number, value in cast(Mapping[int, int], self.number_level_aggregation).items()
        }
        return {
            "method_id": self.method_id,
            "design_name": self.design_name,
            "semantic_signature": SEMANTIC_SIGNATURE,
            "status": self.status,
            "window_size": self.window_size,
            "cutoff": self.cutoff,
            "pair_weights": pair_payload,
            "number_level_aggregation": aggregate_payload,
            "number_rank": list(self.number_rank),
            "ticket_objective": self.ticket_objective,
            "ticket": None if self.ticket is None else list(self.ticket),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
            allow_nan=False,
        ).encode("utf-8")

    def canonical_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")

    def to_dict(self) -> dict[str, object]:
        return self.canonical_dict()

    def to_json(self) -> str:
        return self.canonical_json()


def _canonical_aggregate_map(values: Mapping[int, int]) -> Mapping[int, int]:
    normalized = {number: 0 for number in NUMBER_DOMAIN}
    for raw_number, raw_value in values.items():
        if not _is_non_boolean_integer(raw_number) or raw_number not in normalized:
            raise NumericInvariantError("aggregate keys must be numbers 1..49")
        if not _is_non_boolean_integer(raw_value) or raw_value < 0 or raw_value > UINT64_MAX:
            raise NumericInvariantError("aggregate values must be uint64 integers")
        normalized[raw_number] = raw_value
    if len(values) != NUMBER_MAX:
        raise NumericInvariantError("all 49 number aggregates are required")
    return MappingProxyType({number: normalized[number] for number in NUMBER_DOMAIN})


def _fallback_result(cutoff: int | None) -> AnalysisResult:
    zeros = zero_pair_weights()
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=FALLBACK_STATUS,
        window_size=WINDOW_SIZE,
        pair_weights=zeros,
        ticket_objective=0,
        ticket=(1, 2, 3, 4, 5, 6),
        number_level_aggregation=incident_pair_sums(zeros),
        cutoff=cutoff,
    )


def _failure_result(status: str, cutoff: int | None) -> AnalysisResult:
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=status,
        window_size=WINDOW_SIZE,
        pair_weights={},
        ticket_objective=None,
        ticket=None,
        number_level_aggregation={},
        cutoff=cutoff,
    )


def analyze(history: object, cutoff: object) -> AnalysisResult:
    """Analyze only the frozen causal window and return one fail-closed result."""

    if not _is_non_boolean_integer(cutoff):
        return _failure_result(INVALID_INPUT_STATUS, None)
    if cutoff < 0:
        return _failure_result(INVALID_INPUT_STATUS, cutoff)
    if cutoff < MIN_HISTORY:
        return _fallback_result(cutoff)

    if history is None:
        return _failure_result(INVALID_INPUT_STATUS, cutoff)

    try:
        history_length = _history_length(history)
        validated_cutoff = _validated_cutoff(cutoff, history_length)
    except InvalidInputError:
        return _failure_result(INVALID_INPUT_STATUS, cutoff)

    try:
        draws = _read_causal_window(history, validated_cutoff)
        ages = build_recurrence_ages(draws)
        pair_weights = _pair_weights_from_ages(ages)
        aggregates = incident_pair_sums(pair_weights)
        ticket, objective = optimize_ticket(pair_weights)
        return AnalysisResult(
            method_id=METHOD_ID,
            design_name=DESIGN_NAME,
            status=COMPLETE_STATUS,
            window_size=WINDOW_SIZE,
            pair_weights=pair_weights,
            ticket_objective=objective,
            ticket=ticket,
            number_level_aggregation=aggregates,
            cutoff=validated_cutoff,
        )
    except NonconvergenceError:
        return _failure_result(NONCONVERGENCE_STATUS, validated_cutoff)
    except InvalidInputError:
        return _failure_result(INVALID_INPUT_STATUS, validated_cutoff)
    except NumericInvariantError:
        return _failure_result(NUMERIC_FAILURE_STATUS, validated_cutoff)


def nf06_compute(history: object, cutoff: object) -> AnalysisResult:
    """Python entrypoint corresponding to the sealed ``nf06_compute`` surface."""

    return analyze(history, cutoff)


def compute(history: object, cutoff: object) -> AnalysisResult:
    """Compatibility spelling for :func:`nf06_compute`."""

    return nf06_compute(history, cutoff)


__all__ = [
    "AGE_CAP",
    "AnalysisResult",
    "BigLottoL2PairwiseSinkhornError",
    "Cell",
    "COMPLETE_STATUS",
    "CONVERGENCE_TOLERANCE",
    "CONVERGED_STATUS",
    "COST_DENOMINATOR",
    "DRAW_SIZE",
    "DESIGN_NAME",
    "DiscreteMeasure",
    "EPSILON",
    "EXACT_INDEPENDENCE_STATUS",
    "FALLBACK_STATUS",
    "G",
    "INVALID_INPUT_STATUS",
    "InvalidInputError",
    "MAX_ITERATIONS",
    "MASS_TOLERANCE",
    "METHOD_ID",
    "MIN_HISTORY",
    "NONCONVERGENCE_STATUS",
    "NonconvergenceError",
    "NUMERIC_FAILURE_STATUS",
    "NumericInvariantError",
    "NUMBER_DOMAIN",
    "NUMBER_MAX",
    "NUMBER_MIN",
    "OK_STATUS",
    "PAIR_COUNT",
    "PAIR_KEYS",
    "PAIR_SCALE",
    "PairCountTables",
    "PairScoreResult",
    "SEMANTIC_SIGNATURE",
    "SINKHORN_EPSILON",
    "SINKHORN_TOLERANCE",
    "SinkhornIteration",
    "SinkhornSolve",
    "SUPPORT_SIZE",
    "TICKET_COUNT",
    "UINT64_MAX",
    "W",
    "WINDOW_SIZE",
    "analyze",
    "build_age_histogram",
    "build_cost_matrix",
    "build_joint_counts",
    "build_marginal_counts",
    "build_pair_counts",
    "build_recurrence_ages",
    "compute",
    "cost",
    "cost_matrix",
    "exact_independence",
    "ground_cost",
    "incident_pair_sums",
    "is_exactly_independent",
    "measure_from_counts",
    "nf06_compute",
    "number_aggregation",
    "optimize_ticket",
    "pair_quantum",
    "pair_score",
    "pair_score_details_from_counts",
    "pair_score_from_counts",
    "pair_score_raw",
    "pair_weight",
    "pair_weights_from_ages",
    "product_measure",
    "quantize_pair_score",
    "rank_numbers",
    "recurrence_ages",
    "sinkhorn_divergence",
    "sinkhorn_ot",
    "sinkhorn_solve",
    "sinkhorn_transport",
    "ticket_objective",
    "zero_pair_weights",
]
