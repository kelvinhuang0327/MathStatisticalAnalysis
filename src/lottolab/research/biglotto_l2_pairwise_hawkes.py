"""Deterministic causal bivariate exponential Hawkes pairwise candidate.

This is the independently implemented R2 candidate for
``BMSGV1_L2_PAIRWISE_7080016a070700c3``.  The module deliberately keeps the
research boundary self-contained: it uses only ``decimal`` and ``itertools``
for the frozen numerical algorithm and exact six-number search.  It does not
read persistence, network, empirical-result, or random-state inputs.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    Underflow,
    localcontext,
)
from typing import TypeGuard, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_7080016a070700c3"
DESIGN_NAME = "CAUSAL_BIVARIATE_EXPONENTIAL_HAWKES_EXACT6_V2"
SEMANTIC_SIGNATURE = (
    "7080016a070700c34990c834df208135be0eb0338d744cdb9974bc11852176a6"
)

NUMBER_MIN = 1
NUMBER_MAX = 49
DRAW_CARDINALITY = 6
WINDOW_SIZE = 256
PAIR_COUNT = 1176
ROW_FIT_COUNT = 2352
TICKET_COMBINATION_COUNT = 13_983_816

DECIMAL_PRECISION = 80
COEFFICIENT_DECIMAL_PLACES = 24
AUDIT_DECIMAL_PLACES = 36
MAX_ACCEPTED_ITERATIONS_PER_ROW = 256
MAX_ARMIJO_TRIALS_PER_DIRECTION = 256
# Retain the historical public spelling as an alias; R2 freezes the same
# value as the number of Armijo trials in either direction.
MAX_BACKTRACKS_PER_ITERATION = MAX_ARMIJO_TRIALS_PER_DIRECTION

_D_ZERO = Decimal("0")
_D_ONE = Decimal("1")
_D_TWO = Decimal("2")
_D_T = Decimal("256")
_D_INV_T = Decimal("0.00390625")
_D_L2 = Decimal("0.00390625")
_D_L2_HALF = Decimal("0.001953125")
_D_RHO = Decimal("0.95")
_D_MU_FLOOR = Decimal("0.000000000001")
_D_ARMIJO_C = Decimal("0.0001")
_D_PROJECTED_GRADIENT_TOLERANCE = Decimal("1e-32")
_D_COEFFICIENT_QUANTUM = Decimal("1e-24")
_D_PAIR_WEIGHT_QUANTUM = Decimal("1e-24")
_D_AUDIT_QUANTUM = Decimal("1e-36")
_MAX_ALPHA_QUANTA = 950_000_000_000_000_000_000_000


def _make_decimal_context() -> Context:
    context = Context(
        prec=DECIMAL_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=-999_999,
        Emax=999_999,
        capitals=1,
        clamp=0,
    )
    context.traps[InvalidOperation] = True
    context.traps[DivisionByZero] = True
    context.traps[Overflow] = True
    context.traps[Underflow] = True
    return context


DECIMAL_CONTEXT = _make_decimal_context()


class HawkesContractError(ValueError):
    """Base class for fail-closed candidate contract failures."""


class InvalidCutoffError(HawkesContractError):
    """The cutoff is not a non-boolean integer within the history length."""


class InvalidHistoryError(HawkesContractError):
    """An accessed draw is not a valid six-number Big Lotto draw."""


class SolverConvergenceError(HawkesContractError):
    """A deterministic row solver exceeded a frozen convergence limit."""


class NumericContractError(HawkesContractError):
    """A frozen Decimal, quantization, or stability invariant was violated."""


class PairMatrixContractError(HawkesContractError):
    """The exact 1176-pair matrix could not be completed or validated."""


@dataclass(frozen=True, slots=True)
class EncodedHistory:
    """The validated, bounded causal representation for one invocation."""

    cutoff: int
    used_draws: tuple[tuple[int, ...], ...]
    incidence: tuple[tuple[int, ...], ...]
    event_times: tuple[tuple[int, ...], ...]
    insufficient_history: bool


@dataclass(frozen=True, slots=True)
class RowFit:
    """One certified and quantized target-row fit plus deterministic audit data."""

    target_number: int | None
    self_number: int | None
    cross_number: int | None
    target_event_count: int
    accepted_updates: int
    newton_updates: int
    fallback_updates: int
    maximum_backtracks: int
    total_backtracks: int
    status: str
    baseline: Decimal
    self_alpha: Decimal
    cross_alpha: Decimal
    baseline_quantum: int
    self_alpha_quantum: int
    cross_alpha_quantum: int
    baseline_serialized: str
    self_alpha_serialized: str
    cross_alpha_serialized: str
    objective: Decimal
    objective_serialized: str
    projected_gradient_residual: Decimal
    projected_gradient_residual_serialized: str
    residual_raw: Decimal
    residual_raw_serialized: str
    boundary_flags: dict[str, bool]

    @property
    def mu(self) -> Decimal:
        """Compatibility alias for the frozen baseline coefficient."""

        return self.baseline

    @property
    def alpha_aa(self) -> Decimal:
        """Compatibility alias for the frozen self coefficient."""

        return self.self_alpha

    @property
    def alpha_ab(self) -> Decimal:
        """Compatibility alias for the frozen cross coefficient."""

        return self.cross_alpha

    @property
    def iterations(self) -> int:
        """Compatibility alias for accepted solver updates."""

        return self.accepted_updates

    def to_dict(self) -> dict[str, object]:
        return {
            "target_number": self.target_number,
            "self_number": self.self_number,
            "cross_number": self.cross_number,
            "target_event_count": self.target_event_count,
            "accepted_updates": self.accepted_updates,
            "newton_updates": self.newton_updates,
            "fallback_updates": self.fallback_updates,
            "maximum_backtracks": self.maximum_backtracks,
            "total_backtracks": self.total_backtracks,
            "status": self.status,
            "baseline": self.baseline_serialized,
            "self_alpha": self.self_alpha_serialized,
            "cross_alpha": self.cross_alpha_serialized,
            "baseline_quantum": self.baseline_quantum,
            "self_alpha_quantum": self.self_alpha_quantum,
            "cross_alpha_quantum": self.cross_alpha_quantum,
            "objective": self.objective_serialized,
            "projected_gradient_residual": self.projected_gradient_residual_serialized,
            "residual_raw": self.residual_raw_serialized,
            "boundary_flags": dict(self.boundary_flags),
        }


RowAudit = RowFit


@dataclass(frozen=True, slots=True)
class PairAudit:
    """Both directional row fits and the exact symmetrized pair weight."""

    i: int
    j: int
    row_i: RowFit
    row_j: RowFit
    pair_quantum: int
    pair_weight: Decimal
    pair_weight_serialized: str

    @property
    def directional_cross_quanta(self) -> tuple[int, int]:
        return (self.row_i.cross_alpha_quantum, self.row_j.cross_alpha_quantum)

    def to_dict(self) -> dict[str, object]:
        return {
            "i": self.i,
            "j": self.j,
            "row_i": self.row_i.to_dict(),
            "row_j": self.row_j.to_dict(),
            "pair_quantum": self.pair_quantum,
            "pair_weight": self.pair_weight_serialized,
        }


@dataclass(frozen=True, slots=True)
class NumberRank:
    """One exact aggregate score and its deterministic rank."""

    number: int
    aggregate_quantum: int
    rank: int

    def to_dict(self) -> dict[str, int]:
        return {
            "number": self.number,
            "aggregate_quantum": self.aggregate_quantum,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class TicketSelection:
    """The single exact six-number optimizer result."""

    ticket: tuple[int, ...]
    objective: int
    combinations_examined: int

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket": list(self.ticket),
            "objective": self.objective,
            "combinations_examined": self.combinations_examined,
        }


@dataclass(frozen=True, slots=True)
class PairwiseHawkesResult:
    """Complete deterministic output for one validated invocation."""

    method_id: str
    design_name: str
    semantic_signature: str
    status: str
    pair_rows: tuple[PairAudit, ...]
    pair_quanta: dict[tuple[int, int], int]
    pair_matrix: tuple[tuple[int, ...], ...]
    number_scores: tuple[tuple[int, int], ...]
    rank_table: tuple[NumberRank, ...]
    ticket: tuple[int, ...]
    ticket_objective: int

    @property
    def pair_weights(self) -> dict[tuple[int, int], Decimal]:
        with localcontext(DECIMAL_CONTEXT):
            return {
                pair: Decimal(quantum) * _D_PAIR_WEIGHT_QUANTUM
                for pair, quantum in self.pair_quanta.items()
            }

    @property
    def fallback(self) -> bool:
        return self.status == "FALLBACK_INSUFFICIENT_HISTORY"

    def to_dict(self) -> dict[str, object]:
        return {
            "method_id": self.method_id,
            "design_name": self.design_name,
            "semantic_signature": self.semantic_signature,
            "status": self.status,
            "pair_rows": [row.to_dict() for row in self.pair_rows],
            "number_scores": [
                {"number": number, "aggregate_quantum": score}
                for number, score in self.number_scores
            ],
            "rank_table": [row.to_dict() for row in self.rank_table],
            "ticket": list(self.ticket),
            "ticket_objective": self.ticket_objective,
        }

    def serialize(self) -> str:
        """Serialize all public audit surfaces deterministically."""

        return json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )

    def pair_quantum(self, i: int, j: int) -> int:
        """Return one canonical unordered pair quantum."""

        if i == j:
            return 0
        low, high = (i, j) if i < j else (j, i)
        return self.pair_quanta[(low, high)]


@dataclass(frozen=True, slots=True)
class _RowFeatures:
    target_events: tuple[int, ...]
    self_trace: tuple[Decimal, ...]
    cross_trace: tuple[Decimal, ...]
    self_compensator: Decimal
    cross_compensator: Decimal


def _is_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _decimal_operand(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif _is_integer(value) or isinstance(value, str):
        result = Decimal(value)
    else:
        raise TypeError("Decimal operands must be Decimal, int, or canonical decimal strings")
    if not result.is_finite():
        raise NumericContractError("non-finite Decimal operand")
    return result


def _fixed_string(value: Decimal, quantum: Decimal) -> str:
    return format(value.quantize(quantum), "f")


def _audit_decimal(value: Decimal) -> Decimal:
    return value.quantize(_D_AUDIT_QUANTUM, rounding=ROUND_HALF_EVEN)


def _normalize_event_times(events: Iterable[object]) -> tuple[int, ...]:
    try:
        values = tuple(events)
    except TypeError as exc:
        raise ValueError("event times must be iterable") from exc
    normalized_values: list[int] = []
    for value in values:
        if not _is_integer(value) or not WINDOW_SIZE >= value >= 1:
            raise ValueError("event times must be non-boolean integers in [1, 256]")
        normalized_values.append(value)
    normalized = tuple(sorted(normalized_values))
    if len(set(normalized)) != len(normalized):
        raise ValueError("event times must not contain duplicates")
    return normalized


def _normalize_draw(draw: object) -> tuple[int, ...]:
    if isinstance(draw, (str, bytes, bytearray)):
        raise InvalidHistoryError("draw must be a sequence of six integers")
    try:
        raw_values: tuple[object, ...] = tuple(cast(Iterable[object], draw))
    except TypeError as exc:
        raise InvalidHistoryError("draw must be a sequence of six integers") from exc
    if len(raw_values) != DRAW_CARDINALITY:
        raise InvalidHistoryError("draw must contain exactly six numbers")
    normalized_values: list[int] = []
    for value in raw_values:
        if not _is_integer(value):
            raise InvalidHistoryError("draw numbers must be non-boolean integers")
        if not NUMBER_MIN <= value <= NUMBER_MAX:
            raise InvalidHistoryError("draw number is outside [1, 49]")
        normalized_values.append(value)
    normalized = tuple(sorted(normalized_values))
    if len(set(normalized)) != DRAW_CARDINALITY:
        raise InvalidHistoryError("draw numbers must be distinct")
    return normalized


def _zero_encoded_history(cutoff: int) -> EncodedHistory:
    incidence = tuple(tuple(0 for _ in range(WINDOW_SIZE)) for _ in range(NUMBER_MAX))
    event_times = tuple(() for _ in range(NUMBER_MAX))
    return EncodedHistory(
        cutoff=cutoff,
        used_draws=(),
        incidence=incidence,
        event_times=event_times,
        insufficient_history=True,
    )


def validate_and_encode_history(history: Sequence[object], cutoff: object) -> EncodedHistory:
    """Validate only the causal completed slice and encode its 49 streams.

    A cutoff below 256 never indexes the history.  A complete window indexes
    exactly ``history[cutoff - 256:cutoff]`` in ascending order.
    """

    if not _is_integer(cutoff):
        raise InvalidCutoffError("cutoff must be a non-boolean integer")
    try:
        history_length = len(history)
    except TypeError as exc:
        raise InvalidCutoffError("history must be a finite random-access sequence") from exc
    if cutoff < 0 or cutoff > history_length:
        raise InvalidCutoffError("cutoff must be within the history length")
    if cutoff < WINDOW_SIZE:
        return _zero_encoded_history(cutoff)

    start = cutoff - WINDOW_SIZE
    used_draws: list[tuple[int, ...]] = []
    for index in range(start, cutoff):
        used_draws.append(_normalize_draw(history[index]))

    incidence = [[0 for _ in range(WINDOW_SIZE)] for _ in range(NUMBER_MAX)]
    for local_index, draw in enumerate(used_draws):
        for number in draw:
            incidence[number - NUMBER_MIN][local_index] = 1
    event_times = tuple(
        tuple(local_index + 1 for local_index, present in enumerate(stream) if present)
        for stream in incidence
    )
    return EncodedHistory(
        cutoff=cutoff,
        used_draws=tuple(used_draws),
        incidence=tuple(tuple(stream) for stream in incidence),
        event_times=event_times,
        insufficient_history=False,
    )


def build_exponential_table() -> tuple[Decimal, ...]:
    """Build exp(-d), d=0..255, once in ascending integer order."""

    with localcontext(DECIMAL_CONTEXT):
        table = [_D_ONE]
        for delta in range(1, WINDOW_SIZE):
            table.append((-Decimal(delta)).exp())
        return tuple(table)


def _validate_exponential_table(table: Sequence[Decimal]) -> tuple[Decimal, ...]:
    if len(table) != WINDOW_SIZE:
        raise NumericContractError("exponential table must contain 256 entries")
    validated: list[Decimal] = []
    for value in table:
        if type(value) is not Decimal or not value.is_finite():
            raise NumericContractError("exponential table contains a non-Decimal value")
        validated.append(value)
    return tuple(validated)


def build_trace(
    event_times: Iterable[object], exponential_table: Sequence[Decimal] | None = None
) -> tuple[Decimal, ...]:
    """Build one strict-past exponential trace."""

    with localcontext(DECIMAL_CONTEXT):
        events = _normalize_event_times(event_times)
        table = _validate_exponential_table(
            build_exponential_table() if exponential_table is None else exponential_table
        )
        incidence = [0 for _ in range(WINDOW_SIZE)]
        for event_time in events:
            incidence[event_time - 1] = 1
        trace = [_D_ZERO for _ in range(WINDOW_SIZE)]
        for local_time in range(2, WINDOW_SIZE + 1):
            trace[local_time - 1] = table[1] * (
                trace[local_time - 2] + Decimal(incidence[local_time - 2])
            )
        return tuple(trace)


def build_compensator(
    event_times: Iterable[object], exponential_table: Sequence[Decimal] | None = None
) -> Decimal:
    """Build the post-event compensator feature in ascending event order."""

    with localcontext(DECIMAL_CONTEXT):
        events = _normalize_event_times(event_times)
        table = _validate_exponential_table(
            build_exponential_table() if exponential_table is None else exponential_table
        )
        compensator = _D_ZERO
        for event_time in events:
            compensator += _D_ONE - table[WINDOW_SIZE - event_time]
        return compensator


def _build_row_features(
    target_events: tuple[int, ...],
    self_events: tuple[int, ...],
    cross_events: tuple[int, ...],
    exponential_table: Sequence[Decimal],
) -> _RowFeatures:
    return _RowFeatures(
        target_events=target_events,
        self_trace=build_trace(self_events, exponential_table),
        cross_trace=build_trace(cross_events, exponential_table),
        self_compensator=build_compensator(self_events, exponential_table),
        cross_compensator=build_compensator(cross_events, exponential_table),
    )


def _precompute_stream_features(
    event_times: tuple[tuple[int, ...], ...], exponential_table: Sequence[Decimal]
) -> tuple[tuple[tuple[Decimal, ...], ...], tuple[Decimal, ...]]:
    traces = tuple(build_trace(events, exponential_table) for events in event_times)
    compensators = tuple(build_compensator(events, exponential_table) for events in event_times)
    return traces, compensators


def build_row_features(
    target_events: Iterable[object],
    self_events: Iterable[object],
    cross_events: Iterable[object],
    exponential_table: Sequence[Decimal] | None = None,
) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...], Decimal, Decimal]:
    """Return strict-past self/cross traces and compensators."""

    with localcontext(DECIMAL_CONTEXT):
        target = _normalize_event_times(target_events)
        self_tuple = _normalize_event_times(self_events)
        cross_tuple = _normalize_event_times(cross_events)
        table = _validate_exponential_table(
            build_exponential_table() if exponential_table is None else exponential_table
        )
        features = _build_row_features(target, self_tuple, cross_tuple, table)
        return (
            features.self_trace,
            features.cross_trace,
            features.self_compensator,
            features.cross_compensator,
        )


def _intensity(
    parameters: tuple[Decimal, Decimal, Decimal],
    features: _RowFeatures,
    event_time: int,
) -> Decimal:
    mu, alpha_self, alpha_cross = parameters
    intensity = mu + alpha_self * features.self_trace[event_time - 1]
    intensity += alpha_cross * features.cross_trace[event_time - 1]
    if not intensity.is_finite() or intensity <= _D_ZERO:
        raise NumericContractError("target event intensity is not strictly positive")
    return intensity


def _row_objective(
    parameters: tuple[Decimal, Decimal, Decimal], features: _RowFeatures
) -> Decimal:
    mu, alpha_self, alpha_cross = parameters
    for value in parameters:
        if not value.is_finite():
            raise NumericContractError("non-finite row parameter")
    log_sum = _D_ZERO
    for event_time in features.target_events:
        log_sum += _intensity(parameters, features, event_time).ln()
    negative_log_likelihood = mu * _D_T
    negative_log_likelihood += alpha_self * features.self_compensator
    negative_log_likelihood += alpha_cross * features.cross_compensator
    negative_log_likelihood -= log_sum
    ridge = (mu * mu + alpha_self * alpha_self + alpha_cross * alpha_cross) * _D_L2_HALF
    return negative_log_likelihood * _D_INV_T + ridge


def _row_gradient(
    parameters: tuple[Decimal, Decimal, Decimal], features: _RowFeatures
) -> tuple[Decimal, Decimal, Decimal]:
    mu, alpha_self, alpha_cross = parameters
    inverse_sum = _D_ZERO
    self_ratio_sum = _D_ZERO
    cross_ratio_sum = _D_ZERO
    for event_time in features.target_events:
        intensity = _intensity(parameters, features, event_time)
        inverse = _D_ONE / intensity
        inverse_sum += inverse
        self_ratio_sum += features.self_trace[event_time - 1] * inverse
        cross_ratio_sum += features.cross_trace[event_time - 1] * inverse
    return (
        _D_ONE - _D_INV_T * inverse_sum + _D_L2 * mu,
        _D_INV_T * features.self_compensator
        - _D_INV_T * self_ratio_sum
        + _D_L2 * alpha_self,
        _D_INV_T * features.cross_compensator
        - _D_INV_T * cross_ratio_sum
        + _D_L2 * alpha_cross,
    )


def _row_hessian(
    parameters: tuple[Decimal, Decimal, Decimal], features: _RowFeatures
) -> tuple[tuple[Decimal, ...], ...]:
    hessian = [
        [_D_L2, _D_ZERO, _D_ZERO],
        [_D_ZERO, _D_L2, _D_ZERO],
        [_D_ZERO, _D_ZERO, _D_L2],
    ]
    for event_time in features.target_events:
        intensity = _intensity(parameters, features, event_time)
        inverse = _D_ONE / intensity
        inverse_squared = inverse * inverse
        vector = (
            _D_ONE,
            features.self_trace[event_time - 1],
            features.cross_trace[event_time - 1],
        )
        for row in range(3):
            for column in range(3):
                hessian[row][column] += (
                    _D_INV_T * vector[row] * vector[column] * inverse_squared
                )
    return tuple(tuple(row) for row in hessian)


def _row_objective_and_gradient(
    parameters: tuple[Decimal, Decimal, Decimal], features: _RowFeatures
) -> tuple[Decimal, tuple[Decimal, Decimal, Decimal]]:
    return _row_objective(parameters, features), _row_gradient(parameters, features)


def _row_derivatives(
    parameters: tuple[Decimal, Decimal, Decimal], features: _RowFeatures
) -> tuple[Decimal, tuple[Decimal, Decimal, Decimal], tuple[tuple[Decimal, ...], ...]]:
    objective = _row_objective(parameters, features)
    gradient = _row_gradient(parameters, features)
    hessian = _row_hessian(parameters, features)
    return objective, gradient, hessian


def target_row_objective(
    target_events: Iterable[object],
    self_events: Iterable[object],
    cross_events: Iterable[object],
    mu: Decimal | int | str,
    alpha_self: Decimal | int | str,
    alpha_cross: Decimal | int | str,
) -> Decimal:
    """Evaluate the normalized frozen row objective using Decimal only."""

    with localcontext(DECIMAL_CONTEXT):
        target = _normalize_event_times(target_events)
        self_tuple = _normalize_event_times(self_events)
        cross_tuple = _normalize_event_times(cross_events)
        features = _build_row_features(target, self_tuple, cross_tuple, build_exponential_table())
        parameters = (
            _decimal_operand(mu),
            _decimal_operand(alpha_self),
            _decimal_operand(alpha_cross),
        )
        return _row_objective(parameters, features)


def target_row_gradient(
    target_events: Iterable[object],
    self_events: Iterable[object],
    cross_events: Iterable[object],
    mu: Decimal | int | str,
    alpha_self: Decimal | int | str,
    alpha_cross: Decimal | int | str,
) -> tuple[Decimal, Decimal, Decimal]:
    """Evaluate the analytic frozen row gradient using Decimal only."""

    with localcontext(DECIMAL_CONTEXT):
        target = _normalize_event_times(target_events)
        self_tuple = _normalize_event_times(self_events)
        cross_tuple = _normalize_event_times(cross_events)
        features = _build_row_features(target, self_tuple, cross_tuple, build_exponential_table())
        parameters = (
            _decimal_operand(mu),
            _decimal_operand(alpha_self),
            _decimal_operand(alpha_cross),
        )
        return _row_gradient(parameters, features)


def _project_feasible(
    point: tuple[Decimal, Decimal, Decimal]
) -> tuple[Decimal, Decimal, Decimal]:
    z_mu, z_self, z_cross = point
    for value in point:
        if not value.is_finite():
            raise NumericContractError("non-finite projection coordinate")
    projected_mu = max(_D_MU_FLOOR, z_mu)
    u = max(_D_ZERO, z_self)
    v = max(_D_ZERO, z_cross)
    if u + v <= _D_RHO:
        projected_self, projected_cross = u, v
    elif z_self - z_cross >= _D_RHO:
        projected_self, projected_cross = _D_RHO, _D_ZERO
    elif z_cross - z_self >= _D_RHO:
        projected_self, projected_cross = _D_ZERO, _D_RHO
    else:
        projected_self = (z_self - z_cross + _D_RHO) / _D_TWO
        projected_cross = (z_cross - z_self + _D_RHO) / _D_TWO
    return projected_mu, projected_self, projected_cross


def project_feasible(
    mu: Decimal | int | str,
    alpha_self: Decimal | int | str,
    alpha_cross: Decimal | int | str,
) -> tuple[Decimal, Decimal, Decimal]:
    """Project a row vector onto the frozen nonnegative subcritical set."""

    with localcontext(DECIMAL_CONTEXT):
        return _project_feasible(
            (_decimal_operand(mu), _decimal_operand(alpha_self), _decimal_operand(alpha_cross))
        )


def _projected_gradient_residual(
    point: tuple[Decimal, Decimal, Decimal],
    gradient: tuple[Decimal, Decimal, Decimal],
) -> Decimal:
    projected = _project_feasible(
        (
            point[0] - gradient[0],
            point[1] - gradient[1],
            point[2] - gradient[2],
        )
    )
    return max(abs(point[index] - projected[index]) for index in range(3))


def projected_gradient_residual(
    point: tuple[Decimal, Decimal, Decimal],
    gradient: tuple[Decimal, Decimal, Decimal],
) -> Decimal:
    """Return the unit-step max-coordinate projected-gradient certificate."""

    with localcontext(DECIMAL_CONTEXT):
        if len(point) != 3 or len(gradient) != 3:
            raise NumericContractError("projected-gradient vectors must have three coordinates")
        return _projected_gradient_residual(point, gradient)


def _dot(
    left: tuple[Decimal, Decimal, Decimal], right: tuple[Decimal, Decimal, Decimal]
) -> Decimal:
    result = _D_ZERO
    for index in range(3):
        result += left[index] * right[index]
    return result


def _active_constraints(
    point: tuple[Decimal, Decimal, Decimal],
    gradient: tuple[Decimal, Decimal, Decimal],
) -> tuple[tuple[tuple[Decimal, Decimal, Decimal], ...], dict[str, bool]]:
    projected = _project_feasible(
        (
            point[0] - gradient[0],
            point[1] - gradient[1],
            point[2] - gradient[2],
        )
    )
    flags = {
        "mu_floor": point[0] == _D_MU_FLOOR and projected[0] == _D_MU_FLOOR,
        "self_zero": point[1] == _D_ZERO and projected[1] == _D_ZERO,
        "cross_zero": point[2] == _D_ZERO and projected[2] == _D_ZERO,
        "alpha_sum": (
            point[1] + point[2] == _D_RHO
            and projected[1] + projected[2] == _D_RHO
        ),
    }
    rows: list[tuple[Decimal, Decimal, Decimal]] = []
    if flags["mu_floor"]:
        rows.append((_D_ONE, _D_ZERO, _D_ZERO))
    if flags["self_zero"]:
        rows.append((_D_ZERO, _D_ONE, _D_ZERO))
    if flags["cross_zero"]:
        rows.append((_D_ZERO, _D_ZERO, _D_ONE))
    if flags["alpha_sum"]:
        rows.append((_D_ZERO, _D_ONE, _D_ONE))
    return tuple(rows), flags


def _preserve_active_face(
    point: tuple[Decimal, Decimal, Decimal],
    flags: Mapping[str, bool],
) -> tuple[Decimal, Decimal, Decimal]:
    """Keep a projected trial on the exact face that generated its direction."""

    mu, alpha_self, alpha_cross = point
    if flags["mu_floor"]:
        mu = _D_MU_FLOOR
    if flags["self_zero"]:
        alpha_self = _D_ZERO
    if flags["cross_zero"]:
        alpha_cross = _D_ZERO
    if flags["alpha_sum"]:
        if flags["self_zero"]:
            alpha_self = _D_ZERO
            alpha_cross = _D_RHO
        elif flags["cross_zero"]:
            alpha_self = _D_RHO
            alpha_cross = _D_ZERO
        else:
            alpha_cross = _D_RHO - alpha_self
    return mu, alpha_self, alpha_cross


def _solve_kkt(
    hessian: tuple[tuple[Decimal, ...], ...],
    gradient: tuple[Decimal, Decimal, Decimal],
    active_rows: tuple[tuple[Decimal, Decimal, Decimal], ...],
) -> tuple[Decimal, Decimal, Decimal]:
    """Solve the frozen KKT system by deterministic Decimal Gauss-Jordan."""

    dimension = 3 + len(active_rows)
    augmented = [[_D_ZERO for _ in range(dimension + 1)] for _ in range(dimension)]
    for row in range(3):
        for column in range(3):
            augmented[row][column] = hessian[row][column]
        augmented[row][dimension] = -gradient[row]
    for active_index, active_row in enumerate(active_rows):
        matrix_row = 3 + active_index
        for column in range(3):
            value = active_row[column]
            augmented[matrix_row][column] = value
            augmented[column][matrix_row] = value

    for column in range(dimension):
        pivot_row = column
        pivot_abs = abs(augmented[column][column])
        for candidate in range(column + 1, dimension):
            candidate_abs = abs(augmented[candidate][column])
            if candidate_abs > pivot_abs:
                pivot_row = candidate
                pivot_abs = candidate_abs
        if pivot_abs == _D_ZERO:
            raise NumericContractError("singular Decimal KKT system")
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]
        pivot = augmented[column][column]
        for entry in range(column, dimension + 1):
            augmented[column][entry] /= pivot
        for row in range(dimension):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == _D_ZERO:
                continue
            for entry in range(column, dimension + 1):
                augmented[row][entry] -= factor * augmented[column][entry]
    return (
        augmented[0][dimension],
        augmented[1][dimension],
        augmented[2][dimension],
    )


def _maximum_feasible_step(
    point: tuple[Decimal, Decimal, Decimal],
    direction: tuple[Decimal, Decimal, Decimal],
) -> Decimal | None:
    """Return the exact finite upper bound for a feasible ray, if any."""

    maximum: Decimal | None = None

    def apply_bound(numerator: Decimal, denominator: Decimal) -> None:
        nonlocal maximum
        if denominator <= _D_ZERO:
            return
        bound = numerator / denominator
        if bound < _D_ZERO:
            raise NumericContractError("negative feasible-step bound")
        if maximum is None or bound < maximum:
            maximum = bound

    if direction[0] < _D_ZERO:
        apply_bound(point[0] - _D_MU_FLOOR, -direction[0])
    if direction[1] < _D_ZERO:
        apply_bound(point[1], -direction[1])
    if direction[2] < _D_ZERO:
        apply_bound(point[2], -direction[2])
    alpha_direction = direction[1] + direction[2]
    if alpha_direction > _D_ZERO:
        apply_bound(_D_RHO - point[1] - point[2], alpha_direction)
    return maximum


def _armijo_search(
    point: tuple[Decimal, Decimal, Decimal],
    objective: Decimal,
    gradient: tuple[Decimal, Decimal, Decimal],
    direction: tuple[Decimal, Decimal, Decimal],
    initial_step: Decimal,
    features: _RowFeatures,
    active_flags: Mapping[str, bool],
    preserve_face: bool,
) -> tuple[tuple[Decimal, Decimal, Decimal], int] | None:
    if initial_step <= _D_ZERO:
        return None
    step = initial_step
    for backtracks in range(MAX_ARMIJO_TRIALS_PER_DIRECTION):
        trial_point = (
            point[0] + step * direction[0],
            point[1] + step * direction[1],
            point[2] + step * direction[2],
        )
        trial = _project_feasible(trial_point)
        if preserve_face:
            trial = _preserve_active_face(trial, active_flags)
        delta = (
            trial[0] - point[0],
            trial[1] - point[1],
            trial[2] - point[2],
        )
        trial_objective = _row_objective(trial, features)
        armijo_bound = objective + _D_ARMIJO_C * _dot(gradient, delta)
        if trial_objective <= armijo_bound:
            return trial, backtracks
        step /= _D_TWO
    return None


def _quantize_baseline(value: Decimal) -> tuple[Decimal, int, str]:
    quantized = value.quantize(_D_COEFFICIENT_QUANTUM, rounding=ROUND_HALF_EVEN)
    quantum = int(quantized / _D_COEFFICIENT_QUANTUM)
    return quantized, quantum, _fixed_string(quantized, _D_COEFFICIENT_QUANTUM)


def _quantize_alpha(value: Decimal) -> tuple[Decimal, int, str]:
    quantized = value.quantize(_D_COEFFICIENT_QUANTUM, rounding=ROUND_FLOOR)
    quantum = int(quantized / _D_COEFFICIENT_QUANTUM)
    return quantized, quantum, _fixed_string(quantized, _D_COEFFICIENT_QUANTUM)


def _finalize_row(
    parameters: tuple[Decimal, Decimal, Decimal],
    features: _RowFeatures,
    *,
    target_number: int | None,
    self_number: int | None,
    cross_number: int | None,
    accepted_updates: int,
    newton_updates: int,
    fallback_updates: int,
    maximum_backtracks: int,
    total_backtracks: int,
    status: str = "CERTIFIED",
) -> RowFit:
    objective, gradient = _row_objective_and_gradient(parameters, features)
    residual_raw = _projected_gradient_residual(parameters, gradient)
    if residual_raw > _D_PROJECTED_GRADIENT_TOLERANCE:
        raise SolverConvergenceError("row finalization lacks the frozen certificate")
    baseline, baseline_quantum, baseline_serialized = _quantize_baseline(parameters[0])
    self_alpha, self_quantum, self_serialized = _quantize_alpha(parameters[1])
    cross_alpha, cross_quantum, cross_serialized = _quantize_alpha(parameters[2])
    if not (_D_MU_FLOOR <= baseline <= _D_ONE):
        raise NumericContractError("quantized baseline outside the frozen range")
    if not (
        _D_ZERO <= self_alpha <= _D_RHO
        and _D_ZERO <= cross_alpha <= _D_RHO
        and self_quantum + cross_quantum <= _MAX_ALPHA_QUANTA
    ):
        raise NumericContractError("quantized alpha values violate stability")
    audit_objective = _audit_decimal(objective)
    audit_residual = _audit_decimal(residual_raw)
    _, boundary_flags = _active_constraints(parameters, gradient)
    return RowFit(
        target_number=target_number,
        self_number=self_number,
        cross_number=cross_number,
        target_event_count=len(features.target_events),
        accepted_updates=accepted_updates,
        newton_updates=newton_updates,
        fallback_updates=fallback_updates,
        maximum_backtracks=maximum_backtracks,
        total_backtracks=total_backtracks,
        status=status,
        baseline=baseline,
        self_alpha=self_alpha,
        cross_alpha=cross_alpha,
        baseline_quantum=baseline_quantum,
        self_alpha_quantum=self_quantum,
        cross_alpha_quantum=cross_quantum,
        baseline_serialized=baseline_serialized,
        self_alpha_serialized=self_serialized,
        cross_alpha_serialized=cross_serialized,
        objective=audit_objective,
        objective_serialized=_fixed_string(audit_objective, _D_AUDIT_QUANTUM),
        projected_gradient_residual=audit_residual,
        projected_gradient_residual_serialized=_fixed_string(audit_residual, _D_AUDIT_QUANTUM),
        residual_raw=residual_raw,
        residual_raw_serialized=format(residual_raw, "f"),
        boundary_flags=boundary_flags,
    )


def _fit_row_features(
    features: _RowFeatures,
    *,
    target_number: int | None,
    self_number: int | None,
    cross_number: int | None,
) -> RowFit:
    target_count = len(features.target_events)
    initial_mu = max(_D_MU_FLOOR, Decimal(target_count) * _D_INV_T)
    point = (initial_mu, _D_ZERO, _D_ZERO)
    accepted_updates = 0
    newton_updates = 0
    fallback_updates = 0
    maximum_backtracks = 0
    total_backtracks = 0

    while True:
        objective, gradient, hessian = _row_derivatives(point, features)
        residual = _projected_gradient_residual(point, gradient)
        if residual <= _D_PROJECTED_GRADIENT_TOLERANCE:
            return _finalize_row(
                point,
                features,
                target_number=target_number,
                self_number=self_number,
                cross_number=cross_number,
                accepted_updates=accepted_updates,
                newton_updates=newton_updates,
                fallback_updates=fallback_updates,
                maximum_backtracks=maximum_backtracks,
                total_backtracks=total_backtracks,
            )
        if accepted_updates >= MAX_ACCEPTED_ITERATIONS_PER_ROW:
            raise SolverConvergenceError("row exceeded 256 accepted updates")

        active_rows, active_flags = _active_constraints(point, gradient)
        newton_direction: tuple[Decimal, Decimal, Decimal] | None = None
        try:
            newton_direction = _solve_kkt(hessian, gradient, active_rows)
        except NumericContractError:
            newton_direction = None

        accepted: tuple[tuple[Decimal, Decimal, Decimal], int] | None = None
        if newton_direction is not None:
            max_step = _maximum_feasible_step(point, newton_direction)
            direction_is_zero = all(value == _D_ZERO for value in newton_direction)
            non_descent = _dot(gradient, newton_direction) >= _D_ZERO
            if (
                not direction_is_zero
                and not non_descent
                and (max_step is None or max_step > _D_ZERO)
            ):
                initial_step = _D_ONE if max_step is None else min(_D_ONE, max_step)
                accepted = _armijo_search(
                    point,
                    objective,
                    gradient,
                    newton_direction,
                    initial_step,
                    features,
                    active_flags,
                    True,
                )
                if accepted is not None:
                    new_point, backtracks = accepted
                    point = new_point
                    accepted_updates += 1
                    newton_updates += 1
                    total_backtracks += backtracks
                    maximum_backtracks = max(maximum_backtracks, backtracks)
                    continue

        projected = _project_feasible(
            (
                point[0] - gradient[0],
                point[1] - gradient[1],
                point[2] - gradient[2],
            )
        )
        fallback_direction = (
            projected[0] - point[0],
            projected[1] - point[1],
            projected[2] - point[2],
        )
        if all(value == _D_ZERO for value in fallback_direction):
            raise SolverConvergenceError("projected-gradient fallback has zero direction")
        accepted = _armijo_search(
            point,
            objective,
            gradient,
            fallback_direction,
            _D_ONE,
            features,
            active_flags,
            False,
        )
        if accepted is None:
            raise SolverConvergenceError("Newton and projected-gradient searches exhausted")
        point, backtracks = accepted
        accepted_updates += 1
        fallback_updates += 1
        total_backtracks += backtracks
        maximum_backtracks = max(maximum_backtracks, backtracks)


def fit_target_row(
    target_events: Iterable[object],
    self_events: Iterable[object],
    cross_events: Iterable[object],
    *,
    target_number: int | None = None,
    self_number: int | None = None,
    cross_number: int | None = None,
    exponential_table: Sequence[Decimal] | None = None,
) -> RowFit:
    """Fit one row with the frozen shared-binding Newton solver."""

    with localcontext(DECIMAL_CONTEXT):
        target = _normalize_event_times(target_events)
        self_tuple = _normalize_event_times(self_events)
        cross_tuple = _normalize_event_times(cross_events)
        table = _validate_exponential_table(
            build_exponential_table() if exponential_table is None else exponential_table
        )
        features = _build_row_features(target, self_tuple, cross_tuple, table)
        return _fit_row_features(
            features,
            target_number=target_number,
            self_number=self_number,
            cross_number=cross_number,
        )


def _half_even_integer_mean(left: int, right: int) -> int:
    if not (_is_integer(left) and _is_integer(right) and left >= 0 and right >= 0):
        raise NumericContractError("directional pair quanta must be nonnegative integers")
    total = left + right
    lower, remainder = divmod(total, 2)
    if remainder == 0 or lower % 2 == 0:
        return lower
    return lower + 1


def half_even_pair_quantum(left: int, right: int) -> int:
    """Symmetrize two directional integer quanta with exact half-even rounding."""

    return _half_even_integer_mean(left, right)


def _pair_weight_serialization(quantum: int) -> tuple[Decimal, str]:
    if not _is_integer(quantum) or quantum < 0:
        raise NumericContractError("pair quantum must be a nonnegative integer")
    if quantum > _MAX_ALPHA_QUANTA:
        raise NumericContractError("pair quantum exceeds the frozen range")
    weight = Decimal(quantum) * _D_PAIR_WEIGHT_QUANTUM
    return weight, _fixed_string(weight, _D_PAIR_WEIGHT_QUANTUM)


def _fallback_row(target_number: int, self_number: int, cross_number: int) -> RowFit:
    zero = _fixed_string(_D_ZERO, _D_COEFFICIENT_QUANTUM)
    baseline = _fixed_string(_D_MU_FLOOR, _D_COEFFICIENT_QUANTUM)
    return RowFit(
        target_number=target_number,
        self_number=self_number,
        cross_number=cross_number,
        target_event_count=0,
        accepted_updates=0,
        newton_updates=0,
        fallback_updates=0,
        maximum_backtracks=0,
        total_backtracks=0,
        status="FALLBACK_INSUFFICIENT_HISTORY",
        baseline=_D_MU_FLOOR,
        self_alpha=_D_ZERO,
        cross_alpha=_D_ZERO,
        baseline_quantum=1_000_000_000_000,
        self_alpha_quantum=0,
        cross_alpha_quantum=0,
        baseline_serialized=baseline,
        self_alpha_serialized=zero,
        cross_alpha_serialized=zero,
        objective=_D_ZERO,
        objective_serialized=_fixed_string(_D_ZERO, _D_AUDIT_QUANTUM),
        projected_gradient_residual=_D_ZERO,
        projected_gradient_residual_serialized=_fixed_string(_D_ZERO, _D_AUDIT_QUANTUM),
        residual_raw=_D_ZERO,
        residual_raw_serialized=_fixed_string(_D_ZERO, _D_AUDIT_QUANTUM),
        boundary_flags={
            "mu_floor": True,
            "self_zero": True,
            "cross_zero": True,
            "alpha_sum": False,
        },
    )


def _pair_rows_from_quanta(
    pair_quanta: Mapping[tuple[int, int], int],
    *,
    fallback: bool = False,
) -> tuple[tuple[PairAudit, ...], tuple[tuple[int, ...], ...]]:
    rows: list[PairAudit] = []
    matrix = [[0 for _ in range(NUMBER_MAX)] for _ in range(NUMBER_MAX)]
    for i, j in itertools.combinations(range(NUMBER_MIN, NUMBER_MAX + 1), 2):
        if (i, j) not in pair_quanta:
            raise PairMatrixContractError(f"missing pair {(i, j)}")
        quantum = pair_quanta[(i, j)]
        weight, weight_serialized = _pair_weight_serialization(quantum)
        if not fallback:
            raise PairMatrixContractError("non-fallback rows require directional fits")
        row_i = _fallback_row(i, i, j)
        row_j = _fallback_row(j, j, i)
        rows.append(
            PairAudit(
                i=i,
                j=j,
                row_i=row_i,
                row_j=row_j,
                pair_quantum=quantum,
                pair_weight=weight,
                pair_weight_serialized=weight_serialized,
            )
        )
        matrix[i - 1][j - 1] = quantum
        matrix[j - 1][i - 1] = quantum
    if len(rows) != PAIR_COUNT:
        raise PairMatrixContractError("pair row count is not 1176")
    return tuple(rows), tuple(tuple(row) for row in matrix)


def _validate_pair_quanta(pair_quanta: Mapping[tuple[int, int], int]) -> dict[tuple[int, int], int]:
    expected = set(itertools.combinations(range(NUMBER_MIN, NUMBER_MAX + 1), 2))
    if set(pair_quanta) != expected:
        raise PairMatrixContractError("pair matrix has missing, duplicate, or noncanonical pairs")
    normalized: dict[tuple[int, int], int] = {}
    for pair in sorted(expected):
        value = pair_quanta[pair]
        if not _is_integer(value) or not 0 <= value <= _MAX_ALPHA_QUANTA:
            raise PairMatrixContractError("pair matrix contains an invalid quantum")
        normalized[pair] = value
    return normalized


def construct_exact_six_ticket(pair_quanta: Mapping[tuple[int, int], int]) -> TicketSelection:
    """Exhaustively maximize the exact 15-edge objective over all six-subsets."""

    normalized = _validate_pair_quanta(pair_quanta)
    matrix = [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]
    for (i, j), quantum in normalized.items():
        matrix[i][j] = quantum
        matrix[j][i] = quantum

    best_objective = -1
    best_ticket: tuple[int, ...] | None = None
    combinations_examined = 0
    for candidate in itertools.combinations(range(NUMBER_MIN, NUMBER_MAX + 1), DRAW_CARDINALITY):
        combinations_examined += 1
        a, b, c, d, e, f = candidate
        objective = (
            matrix[a][b]
            + matrix[a][c]
            + matrix[b][c]
            + matrix[a][d]
            + matrix[b][d]
            + matrix[c][d]
            + matrix[a][e]
            + matrix[b][e]
            + matrix[c][e]
            + matrix[d][e]
            + matrix[a][f]
            + matrix[b][f]
            + matrix[c][f]
            + matrix[d][f]
            + matrix[e][f]
        )
        if objective > best_objective:
            best_objective = objective
            best_ticket = candidate
    if combinations_examined != TICKET_COMBINATION_COUNT or best_ticket is None:
        raise PairMatrixContractError("exact six-subset enumeration was incomplete")
    return TicketSelection(
        ticket=best_ticket,
        objective=best_objective,
        combinations_examined=combinations_examined,
    )


def select_exact_six_ticket(pair_quanta: Mapping[tuple[int, int], int]) -> tuple[int, ...]:
    """Return only the exact optimizer's one ticket."""

    return construct_exact_six_ticket(pair_quanta).ticket


def _build_number_ranks(
    pair_quanta: Mapping[tuple[int, int], int],
) -> tuple[tuple[tuple[int, int], ...], tuple[NumberRank, ...]]:
    aggregates = {number: 0 for number in range(NUMBER_MIN, NUMBER_MAX + 1)}
    for (i, j), quantum in sorted(pair_quanta.items()):
        aggregates[i] += quantum
        aggregates[j] += quantum
    number_scores = tuple(sorted(aggregates.items()))
    ordered = sorted(aggregates.items(), key=lambda item: (-item[1], item[0]))
    ranks = tuple(
        NumberRank(number=number, aggregate_quantum=score, rank=rank)
        for rank, (number, score) in enumerate(ordered, start=1)
    )
    return number_scores, ranks


def _result_from_pair_quanta(
    pair_quanta: Mapping[tuple[int, int], int],
    *,
    status: str,
    pair_rows: tuple[PairAudit, ...],
    pair_matrix: tuple[tuple[int, ...], ...],
) -> PairwiseHawkesResult:
    number_scores, rank_table = _build_number_ranks(pair_quanta)
    selection = construct_exact_six_ticket(pair_quanta)
    return PairwiseHawkesResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        semantic_signature=SEMANTIC_SIGNATURE,
        status=status,
        pair_rows=pair_rows,
        pair_quanta=dict(pair_quanta),
        pair_matrix=pair_matrix,
        number_scores=number_scores,
        rank_table=rank_table,
        ticket=selection.ticket,
        ticket_objective=selection.objective,
    )


def compute_pairwise_hawkes(
    history: Sequence[object], cutoff: object
) -> PairwiseHawkesResult:
    """Run the complete frozen R2 pairwise Hawkes candidate."""

    encoded = validate_and_encode_history(history, cutoff)
    if encoded.insufficient_history:
        zero_quanta = {
            pair: 0 for pair in itertools.combinations(range(NUMBER_MIN, NUMBER_MAX + 1), 2)
        }
        fallback_rows, fallback_matrix = _pair_rows_from_quanta(zero_quanta, fallback=True)
        return _result_from_pair_quanta(
            zero_quanta,
            status="FALLBACK_INSUFFICIENT_HISTORY",
            pair_rows=fallback_rows,
            pair_matrix=fallback_matrix,
        )

    with localcontext(DECIMAL_CONTEXT):
        exponential_table = build_exponential_table()
        traces, compensators = _precompute_stream_features(
            encoded.event_times, exponential_table
        )
        pair_quanta: dict[tuple[int, int], int] = {}
        pair_rows: list[PairAudit] = []
        matrix = [[0 for _ in range(NUMBER_MAX)] for _ in range(NUMBER_MAX)]
        for i, j in itertools.combinations(range(NUMBER_MIN, NUMBER_MAX + 1), 2):
            i_index = i - NUMBER_MIN
            j_index = j - NUMBER_MIN
            events_i = encoded.event_times[i_index]
            events_j = encoded.event_times[j_index]
            features_i = _RowFeatures(
                target_events=events_i,
                self_trace=traces[i_index],
                cross_trace=traces[j_index],
                self_compensator=compensators[i_index],
                cross_compensator=compensators[j_index],
            )
            features_j = _RowFeatures(
                target_events=events_j,
                self_trace=traces[j_index],
                cross_trace=traces[i_index],
                self_compensator=compensators[j_index],
                cross_compensator=compensators[i_index],
            )
            row_i = _fit_row_features(
                features_i,
                target_number=i,
                self_number=i,
                cross_number=j,
            )
            row_j = _fit_row_features(
                features_j,
                target_number=j,
                self_number=j,
                cross_number=i,
            )
            quantum = _half_even_integer_mean(
                row_i.cross_alpha_quantum,
                row_j.cross_alpha_quantum,
            )
            weight, weight_serialized = _pair_weight_serialization(quantum)
            pair = (i, j)
            pair_quanta[pair] = quantum
            matrix[i - 1][j - 1] = quantum
            matrix[j - 1][i - 1] = quantum
            pair_rows.append(
                PairAudit(
                    i=i,
                    j=j,
                    row_i=row_i,
                    row_j=row_j,
                    pair_quantum=quantum,
                    pair_weight=weight,
                    pair_weight_serialized=weight_serialized,
                )
            )
        if len(pair_rows) != PAIR_COUNT or len(pair_quanta) != PAIR_COUNT:
            raise PairMatrixContractError("pairwise invocation did not produce all 1176 pairs")
        return _result_from_pair_quanta(
            pair_quanta,
            status="NORMAL",
            pair_rows=tuple(pair_rows),
            pair_matrix=tuple(tuple(row) for row in matrix),
        )


def run_pairwise_hawkes(
    history: Sequence[object], cutoff: object
) -> PairwiseHawkesResult:
    """Named execution alias for the frozen candidate."""

    return compute_pairwise_hawkes(history, cutoff)


def semantic_signature_for_core(core: object) -> str:
    """Compute the jq-compatible SHA-256 signature for a semantic core."""

    canonical = json.dumps(core, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest()


__all__ = [
    "AUDIT_DECIMAL_PLACES",
    "COEFFICIENT_DECIMAL_PLACES",
    "DECIMAL_CONTEXT",
    "DECIMAL_PRECISION",
    "DESIGN_NAME",
    "DRAW_CARDINALITY",
    "MAX_ACCEPTED_ITERATIONS_PER_ROW",
    "MAX_ARMIJO_TRIALS_PER_DIRECTION",
    "MAX_BACKTRACKS_PER_ITERATION",
    "METHOD_ID",
    "NUMBER_MAX",
    "NUMBER_MIN",
    "PAIR_COUNT",
    "ROW_FIT_COUNT",
    "SEMANTIC_SIGNATURE",
    "TICKET_COMBINATION_COUNT",
    "WINDOW_SIZE",
    "EncodedHistory",
    "HawkesContractError",
    "InvalidCutoffError",
    "InvalidHistoryError",
    "NumericContractError",
    "PairAudit",
    "PairMatrixContractError",
    "PairwiseHawkesResult",
    "RowAudit",
    "RowFit",
    "SolverConvergenceError",
    "TicketSelection",
    "build_compensator",
    "build_exponential_table",
    "build_row_features",
    "build_trace",
    "compute_pairwise_hawkes",
    "construct_exact_six_ticket",
    "fit_target_row",
    "half_even_pair_quantum",
    "project_feasible",
    "projected_gradient_residual",
    "run_pairwise_hawkes",
    "select_exact_six_ticket",
    "semantic_signature_for_core",
    "target_row_gradient",
    "target_row_objective",
    "validate_and_encode_history",
]
