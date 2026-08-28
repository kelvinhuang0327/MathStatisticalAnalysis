"""Frozen NF02 one-step transfer-entropy candidate for BIG LOTTO.

The module is a pure, standalone research surface.  It consumes a caller-owned
chronological sequence of completed six-number draws and a cutoff, reads only
the 257 completed rows needed for the 256 prediction rows, and returns the
quantized symmetric pair matrix together with the exact best six-number ticket.

The frozen estimator uses binary incidence states with one target-history bit
and one source-history bit.  It is deliberately implemented without fitted
states, smoothing, floating-point arithmetic, empirical inputs, or runtime
integration.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence, Sized
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    FloatOperation,
    InvalidOperation,
    Overflow,
    localcontext,
)
from itertools import combinations
from json import dumps
from types import MappingProxyType
from typing import Any, TypeGuard, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_NF02_TRANSFER_ENTROPY_V1"
DESIGN_NAME = "BIGLOTTO_L2_PAIRWISE_NF02_TRANSFER_ENTROPY_V1"
SEMANTIC_SIGNATURE = "339a4a3e3e3df04db4b6a02461ecd433089ad54b3edd56628d5ded568aea4234"

NUMBER_MIN = 1
NUMBER_MAX = 49
NUMBER_DOMAIN: tuple[int, ...] = tuple(range(NUMBER_MIN, NUMBER_MAX + 1))
DRAW_SIZE = 6
WINDOW_SIZE = 256
PREDICTION_COUNT = 256
MIN_HISTORY = 257
K = 1
L = 1
PAIR_COUNT = (NUMBER_MAX * (NUMBER_MAX - 1)) // 2
TICKET_COUNT = 13_983_816

DECIMAL_PRECISION = 80
DECIMAL_OUTPUT_PLACES = 60
OUTPUT_QUANTUM = Decimal("1e-60")
PAIR_WEIGHT_QUANTUM = OUTPUT_QUANTUM
OUTPUT_SCALE = DECIMAL_OUTPUT_PLACES
LOG_BASE = "natural logarithm"

COMPLETE_STATUS = "COMPLETE"
FALLBACK_STATUS = "FALLBACK_INSUFFICIENT_HISTORY"


def _make_decimal_context() -> Context:
    """Build the explicit context required by the frozen numeric contract."""

    context = Context(
        prec=DECIMAL_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=-999_999_999,
        Emax=999_999_999,
        clamp=0,
    )
    for signal in (InvalidOperation, DivisionByZero, Overflow, FloatOperation):
        context.traps[signal] = True
    return context


DECIMAL_CONTEXT = _make_decimal_context()
_HALF_OUTPUT_QUANTUM = Decimal("5e-61")
_DECIMAL_ZERO = Decimal(0)
_DECIMAL_ONE = Decimal(1)
_DECIMAL_TWO = Decimal(2)

type Pair = tuple[int, int]
type Draw = tuple[int, ...]
type BinaryState = tuple[int, ...]
type TripleKey = tuple[int, BinaryState, BinaryState]
type TargetContextKey = tuple[int, BinaryState]
type ContextPairKey = tuple[BinaryState, BinaryState]
type PredictionRow = tuple[int, BinaryState, BinaryState]


class BigLottoL2PairwiseTransferEntropyError(ValueError):
    """Base class for fail-closed NF02 contract errors."""


class InvalidInputError(BigLottoL2PairwiseTransferEntropyError):
    """The history, cutoff, or an accessed draw violates the input contract."""


class InvalidCutoffError(InvalidInputError):
    """The cutoff is not a non-boolean integer within the history boundary."""


class InvalidHistoryError(InvalidInputError):
    """An accessed draw is not a valid six-number BIG LOTTO draw."""


class NumericContractError(BigLottoL2PairwiseTransferEntropyError):
    """A frozen Decimal or mathematical invariant was violated."""


class NumericInvariantError(NumericContractError):
    """Alias-compatible name for a fail-closed numeric invariant failure."""


class PairMatrixContractError(NumericContractError):
    """The complete canonical pair matrix could not be constructed."""


def _is_non_boolean_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _pair_keys() -> tuple[Pair, ...]:
    return tuple(
        (left, right)
        for left in NUMBER_DOMAIN
        for right in NUMBER_DOMAIN
        if left < right
    )


PAIR_KEYS: tuple[Pair, ...] = _pair_keys()


def _validate_binary_stream(stream: Sequence[object], *, label: str) -> tuple[int, ...]:
    try:
        values = tuple(cast(Iterable[object], stream))
    except Exception as exc:
        raise InvalidInputError(f"{label} must be an iterable binary stream") from exc
    if any(not _is_non_boolean_integer(value) or value not in (0, 1) for value in values):
        raise InvalidInputError(f"{label} must contain only non-boolean 0/1 integers")
    return cast(tuple[int, ...], values)


def encode_state(bits: Sequence[object]) -> BinaryState:
    """Return an observed binary state in oldest-to-newest tuple order."""

    return _validate_binary_stream(bits, label="state")


def flatten_state(bits: Sequence[object]) -> int:
    """Flatten a binary state using the frozen 0-before-1 lexicographic code."""

    state = encode_state(bits)
    flattened = 0
    for bit in state:
        flattened = (flattened * 2) + bit
    return flattened


def _validate_draw(raw_draw: object, *, index: int) -> Draw:
    try:
        raw_values = tuple(cast(Iterable[object], raw_draw))
    except Exception as exc:
        raise InvalidHistoryError(f"history[{index}] is not an iterable draw") from exc

    if len(raw_values) != DRAW_SIZE:
        raise InvalidHistoryError(f"history[{index}] must contain exactly six values")
    if any(not _is_non_boolean_integer(value) for value in raw_values):
        raise InvalidHistoryError(
            f"history[{index}] values must be distinct non-boolean integers in 1..49"
        )
    values = cast(tuple[int, ...], raw_values)
    if len(set(values)) != DRAW_SIZE:
        raise InvalidHistoryError(f"history[{index}] values must be distinct")
    if any(value < NUMBER_MIN or value > NUMBER_MAX for value in values):
        raise InvalidHistoryError(f"history[{index}] values must lie in 1..49")
    return tuple(sorted(values))


def _history_length(history: object) -> int:
    try:
        return len(cast(Sized, history))
    except Exception as exc:
        raise InvalidInputError("history must be a finite indexable sequence") from exc


def _validated_cutoff(cutoff: object, history_length: int) -> int:
    if not _is_non_boolean_integer(cutoff):
        raise InvalidCutoffError("cutoff must be a non-boolean integer")
    if cutoff < 0 or cutoff > history_length:
        raise InvalidCutoffError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return cutoff


def _read_causal_window(history: object, cutoff: int) -> tuple[Draw, ...]:
    """Read exactly the 257 completed rows immediately before ``cutoff``."""

    start = cutoff - MIN_HISTORY
    indexable_history = cast(Sequence[object], history)
    draws: list[Draw] = []
    for index in range(start, cutoff):
        try:
            raw_draw = indexable_history[index]
        except Exception as exc:
            raise InvalidInputError(f"history[{index}] could not be read") from exc
        draws.append(_validate_draw(raw_draw, index=index))
    if len(draws) != MIN_HISTORY:
        raise NumericInvariantError("causal window length is not 257")
    return tuple(draws)


def build_membership_streams(draws: Sequence[object]) -> tuple[tuple[int, ...], ...]:
    """Build one chronological binary incidence stream for each number."""

    try:
        raw_draws = tuple(cast(Iterable[object], draws))
    except Exception as exc:
        raise InvalidInputError("draws must be an iterable collection") from exc
    normalized = tuple(
        _validate_draw(draw, index=index) for index, draw in enumerate(raw_draws)
    )
    return tuple(
        tuple(int(number in draw) for draw in normalized) for number in NUMBER_DOMAIN
    )


def build_prediction_rows(
    target_stream: Sequence[object], source_stream: Sequence[object]
) -> tuple[PredictionRow, ...]:
    """Construct ``(x, h_target, h_source)`` rows with a one-step lag."""

    target = _validate_binary_stream(target_stream, label="target_stream")
    source = _validate_binary_stream(source_stream, label="source_stream")
    if len(target) != len(source):
        raise InvalidInputError("target_stream and source_stream must have equal lengths")
    if len(target) < 2:
        raise InvalidInputError("at least two stream rows are required")
    return tuple(
        (
            target[index],
            encode_state((target[index - 1],)),
            encode_state((source[index - 1],)),
        )
        for index in range(1, len(target))
    )


def build_lagged_states(
    target_stream: Sequence[object], source_stream: Sequence[object]
) -> tuple[PredictionRow, ...]:
    """Compatibility spelling for the frozen one-step state construction."""

    return build_prediction_rows(target_stream, source_stream)


@dataclass(frozen=True, slots=True)
class DirectionalCounts:
    """Observed positive count tables for one source-to-target direction."""

    triple_counts: Mapping[TripleKey, int]
    conditional_counts: Mapping[ContextPairKey, int]
    target_context_counts: Mapping[TargetContextKey, int]
    target_history_counts: Mapping[BinaryState, int]
    sample_size: int

    @property
    def c_x_h_g(self) -> Mapping[TripleKey, int]:
        return self.triple_counts

    @property
    def c_h_g(self) -> Mapping[ContextPairKey, int]:
        return self.conditional_counts

    @property
    def c_x_h(self) -> Mapping[TargetContextKey, int]:
        return self.target_context_counts

    @property
    def c_h(self) -> Mapping[BinaryState, int]:
        return self.target_history_counts


def _ordered_mapping[K](counts: Mapping[K, int]) -> Mapping[K, int]:
    return MappingProxyType(dict(sorted(counts.items())))


def build_conditional_counts(
    target_stream: Sequence[object], source_stream: Sequence[object]
) -> DirectionalCounts:
    """Build the four frozen count tables from two binary incidence streams."""

    rows = build_prediction_rows(target_stream, source_stream)
    triple_counts: Counter[TripleKey] = Counter()
    conditional_counts: Counter[ContextPairKey] = Counter()
    target_context_counts: Counter[TargetContextKey] = Counter()
    target_history_counts: Counter[BinaryState] = Counter()

    for x, target_history, source_history in rows:
        triple_counts[(x, target_history, source_history)] += 1
        conditional_counts[(target_history, source_history)] += 1
        target_context_counts[(x, target_history)] += 1
        target_history_counts[target_history] += 1

    return DirectionalCounts(
        triple_counts=_ordered_mapping(triple_counts),
        conditional_counts=_ordered_mapping(conditional_counts),
        target_context_counts=_ordered_mapping(target_context_counts),
        target_history_counts=_ordered_mapping(target_history_counts),
        sample_size=len(rows),
    )


def conditional_counts(
    target_stream: Sequence[object], source_stream: Sequence[object]
) -> DirectionalCounts:
    """Compatibility spelling for :func:`build_conditional_counts`."""

    return build_conditional_counts(target_stream, source_stream)


def _decimal_integer(value: int, context: Context) -> Decimal:
    return context.create_decimal(value)


def _transfer_entropy_raw(counts: DirectionalCounts) -> Decimal:
    if counts.sample_size <= 0:
        raise NumericInvariantError("transfer-entropy sample must not be empty")
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            total = context.create_decimal(_DECIMAL_ZERO)
            sample_size = _decimal_integer(counts.sample_size, context)
            for (x, target_history, source_history), count in sorted(
                counts.triple_counts.items()
            ):
                if count <= 0:
                    if count < 0:
                        raise NumericInvariantError("count tables must be non-negative")
                    continue
                target_source_count = counts.conditional_counts[
                    (target_history, source_history)
                ]
                target_context_count = counts.target_context_counts[(x, target_history)]
                target_history_count = counts.target_history_counts[target_history]
                denominator = target_source_count * target_context_count
                numerator = count * target_history_count
                if denominator <= 0 or numerator <= 0:
                    raise NumericInvariantError("observed-cell count denominator is not positive")
                probability = context.divide(_decimal_integer(count, context), sample_size)
                ratio = context.divide(
                    _decimal_integer(numerator, context),
                    _decimal_integer(denominator, context),
                )
                term = context.multiply(probability, context.ln(ratio))
                total = context.add(total, term)
            return context.plus(total)
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError("transfer-entropy Decimal operation failed") from exc


def _conditional_entropy_raw(counts: DirectionalCounts) -> Decimal:
    if counts.sample_size <= 0:
        raise NumericInvariantError("conditional-entropy sample must not be empty")
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            total = context.create_decimal(_DECIMAL_ZERO)
            sample_size = _decimal_integer(counts.sample_size, context)
            for (_x, target_history), count in sorted(counts.target_context_counts.items()):
                if count <= 0:
                    if count < 0:
                        raise NumericInvariantError("count tables must be non-negative")
                    continue
                target_history_count = counts.target_history_counts[target_history]
                if target_history_count <= 0:
                    raise NumericInvariantError("observed target-history count is not positive")
                probability = context.divide(_decimal_integer(count, context), sample_size)
                ratio = context.divide(
                    _decimal_integer(count, context),
                    _decimal_integer(target_history_count, context),
                )
                term = context.multiply(probability, context.ln(ratio))
                total = context.subtract(total, term)
            return context.plus(total)
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError("conditional-entropy Decimal operation failed") from exc


def _coerce_decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool):
        raise NumericInvariantError(f"{label} must not be boolean")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    else:
        raise NumericInvariantError(f"{label} must be a Decimal or exact integer")
    if not result.is_finite():
        raise NumericInvariantError(f"{label} must be finite")
    return result


def _quantize_output(value: Decimal, *, label: str) -> Decimal:
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            if not value.is_finite():
                raise NumericInvariantError(f"{label} must be finite")
            result = context.quantize(value, OUTPUT_QUANTUM)
            if result.is_zero():
                return context.quantize(context.create_decimal(_DECIMAL_ZERO), OUTPUT_QUANTUM)
            return result
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError(f"{label} could not be quantized") from exc


def _nonnegative_endpoint(value: Decimal, *, label: str) -> Decimal:
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            if not value.is_finite():
                raise NumericInvariantError(f"{label} is non-finite")
            candidate = value
            if candidate < _DECIMAL_ZERO:
                if candidate.copy_abs() < _HALF_OUTPUT_QUANTUM:
                    candidate = context.create_decimal(_DECIMAL_ZERO)
                else:
                    raise NumericInvariantError(f"{label} is materially negative")
            return _quantize_output(candidate, label=label)
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError(f"{label} endpoint failed") from exc


def _unit_endpoint(value: Decimal, *, label: str) -> Decimal:
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            if not value.is_finite():
                raise NumericInvariantError(f"{label} is non-finite")
            candidate = value
            if candidate < _DECIMAL_ZERO:
                if candidate.copy_abs() < _HALF_OUTPUT_QUANTUM:
                    candidate = context.create_decimal(_DECIMAL_ZERO)
                else:
                    raise NumericInvariantError(f"{label} is below zero")
            if candidate > _DECIMAL_ONE:
                excess = context.subtract(candidate, _DECIMAL_ONE)
                if excess < _HALF_OUTPUT_QUANTUM:
                    candidate = _DECIMAL_ONE
                else:
                    raise NumericInvariantError(f"{label} exceeds one")
            result = context.quantize(candidate, OUTPUT_QUANTUM)
            if result < _DECIMAL_ZERO:
                raise NumericInvariantError(f"{label} quantized below zero")
            if result > _DECIMAL_ONE:
                if context.subtract(result, _DECIMAL_ONE) < _HALF_OUTPUT_QUANTUM:
                    result = context.quantize(_DECIMAL_ONE, OUTPUT_QUANTUM)
                else:
                    raise NumericInvariantError(f"{label} quantized above one")
            if result.is_zero():
                return context.quantize(context.create_decimal(_DECIMAL_ZERO), OUTPUT_QUANTUM)
            return result
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError(f"{label} endpoint failed") from exc


@dataclass(frozen=True, slots=True)
class DirectionalScore:
    """Quantized TE, target conditional entropy, and normalized TE."""

    transfer_entropy: Decimal
    conditional_entropy: Decimal
    normalized: Decimal

    @property
    def normalized_transfer_entropy(self) -> Decimal:
        return self.normalized


def _directional_score_from_counts(counts: DirectionalCounts) -> DirectionalScore:
    transfer_entropy_raw = _transfer_entropy_raw(counts)
    conditional_entropy_raw = _conditional_entropy_raw(counts)
    transfer_entropy = _nonnegative_endpoint(transfer_entropy_raw, label="transfer entropy")
    conditional_entropy = _nonnegative_endpoint(
        conditional_entropy_raw, label="conditional entropy"
    )
    if conditional_entropy_raw <= _DECIMAL_ZERO:
        normalized = _nonnegative_endpoint(_DECIMAL_ZERO, label="normalized transfer entropy")
    else:
        try:
            with localcontext(DECIMAL_CONTEXT) as context:
                ratio = context.divide(transfer_entropy_raw, conditional_entropy_raw)
        except DecimalException as exc:
            raise NumericInvariantError("normalized transfer-entropy division failed") from exc
        normalized = _unit_endpoint(ratio, label="normalized transfer entropy")
    return DirectionalScore(
        transfer_entropy=transfer_entropy,
        conditional_entropy=conditional_entropy,
        normalized=normalized,
    )


def directional_score(
    target_stream: Sequence[object], source_stream: Sequence[object]
) -> DirectionalScore:
    """Return the frozen source-to-target directional score."""

    return _directional_score_from_counts(build_conditional_counts(target_stream, source_stream))


def transfer_entropy(
    target_stream_or_counts: Sequence[object] | DirectionalCounts,
    source_stream: Sequence[object] | None = None,
) -> Decimal:
    """Return observed-cell plug-in TE using natural logarithms."""

    if isinstance(target_stream_or_counts, DirectionalCounts):
        if source_stream is not None:
            raise InvalidInputError("source_stream is not used with DirectionalCounts")
        counts = target_stream_or_counts
    else:
        if source_stream is None:
            raise InvalidInputError("source_stream is required")
        counts = build_conditional_counts(target_stream_or_counts, source_stream)
    return _nonnegative_endpoint(_transfer_entropy_raw(counts), label="transfer entropy")


def transfer_entropy_from_counts(counts: DirectionalCounts) -> Decimal:
    """Return TE from an already constructed observed count table."""

    return transfer_entropy(counts)


def conditional_entropy(
    target_stream_or_counts: Sequence[object] | DirectionalCounts,
    source_stream: Sequence[object] | None = None,
) -> Decimal:
    """Return target conditional entropy from its one-step target history."""

    if isinstance(target_stream_or_counts, DirectionalCounts):
        if source_stream is not None:
            raise InvalidInputError("source_stream is not used with DirectionalCounts")
        counts = target_stream_or_counts
    else:
        if source_stream is None:
            validated_target = _validate_binary_stream(
                target_stream_or_counts, label="target_stream"
            )
            source = tuple(0 for _ in validated_target)
        else:
            source = source_stream
        counts = build_conditional_counts(target_stream_or_counts, source)
    return _nonnegative_endpoint(
        _conditional_entropy_raw(counts), label="conditional entropy"
    )


def conditional_entropy_from_counts(counts: DirectionalCounts) -> Decimal:
    """Return target conditional entropy from an observed count table."""

    return conditional_entropy(counts)


def normalized_transfer_entropy(
    transfer_entropy_or_target: Decimal | int | Sequence[object] | DirectionalCounts,
    conditional_entropy_or_source: Decimal | int | Sequence[object] | None = None,
) -> Decimal:
    """Return a frozen normalized TE endpoint.

    The numeric form accepts ``(TE, H)``.  The stream form accepts
    ``(target_stream, source_stream)`` and computes the complete directional
    score before returning its normalized component.
    """

    if isinstance(transfer_entropy_or_target, DirectionalCounts):
        if conditional_entropy_or_source is not None:
            raise InvalidInputError("source is not used with DirectionalCounts")
        return _directional_score_from_counts(transfer_entropy_or_target).normalized
    if isinstance(transfer_entropy_or_target, (Decimal, int)) and isinstance(
        conditional_entropy_or_source, (Decimal, int)
    ):
        transfer = _coerce_decimal(transfer_entropy_or_target, label="transfer entropy")
        entropy = _coerce_decimal(conditional_entropy_or_source, label="conditional entropy")
        if entropy < _DECIMAL_ZERO:
            raise NumericInvariantError("conditional entropy must be non-negative")
        if entropy.is_zero():
            return _nonnegative_endpoint(_DECIMAL_ZERO, label="normalized transfer entropy")
        try:
            with localcontext(DECIMAL_CONTEXT) as context:
                ratio = context.divide(transfer, entropy)
        except DecimalException as exc:
            raise NumericInvariantError("normalized transfer-entropy division failed") from exc
        return _unit_endpoint(ratio, label="normalized transfer entropy")
    if conditional_entropy_or_source is None or isinstance(
        conditional_entropy_or_source, (Decimal, int)
    ):
        raise InvalidInputError("both target and source streams are required")
    return directional_score(
        cast(Sequence[object], transfer_entropy_or_target),
        conditional_entropy_or_source,
    ).normalized


def _pair_weight_from_streams(
    left_stream: Sequence[object], right_stream: Sequence[object]
) -> Decimal:
    """Average ``left->right`` and ``right->left`` after directional quantization."""

    left_to_right = directional_score(right_stream, left_stream).normalized
    right_to_left = directional_score(left_stream, right_stream).normalized
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            mean = context.divide(
                context.add(left_to_right, right_to_left), _DECIMAL_TWO
            )
    except DecimalException as exc:
        raise NumericInvariantError("pair-weight mean failed") from exc
    return _unit_endpoint(mean, label="pair weight")


def pair_weight(
    left_stream: Sequence[object], right_stream: Sequence[object]
) -> Decimal:
    """Return one symmetric unordered-pair weight from two incidence streams."""

    return _pair_weight_from_streams(left_stream, right_stream)


def _pair_weights_from_streams(
    streams: tuple[tuple[int, ...], ...],
) -> dict[Pair, Decimal]:
    pair_weights: dict[Pair, Decimal] = {}
    for left_index, left_number in enumerate(NUMBER_DOMAIN):
        left_stream = streams[left_index]
        for right_index in range(left_index + 1, len(NUMBER_DOMAIN)):
            right_number = NUMBER_DOMAIN[right_index]
            pair_weights[(left_number, right_number)] = _pair_weight_from_streams(
                left_stream, streams[right_index]
            )
    if len(pair_weights) != PAIR_COUNT:
        raise PairMatrixContractError("pair-weight cardinality is not 1,176")
    return pair_weights


def _zero_pair_weights() -> dict[Pair, Decimal]:
    zero = _quantize_output(_DECIMAL_ZERO, label="zero pair weight")
    return {pair: zero for pair in PAIR_KEYS}


def zero_pair_weights() -> Mapping[Pair, Decimal]:
    """Return a fresh canonical all-zero 1,176-pair matrix."""

    return MappingProxyType(_zero_pair_weights())


def _canonical_pair_key(key: object) -> Pair:
    if not isinstance(key, tuple):
        raise PairMatrixContractError("pair keys must be two-number tuples")
    pair_key = cast(tuple[object, ...], key)
    if len(pair_key) != 2:
        raise PairMatrixContractError("pair keys must be two-number tuples")
    left = pair_key[0]
    right = pair_key[1]
    if (
        not _is_non_boolean_integer(left)
        or not _is_non_boolean_integer(right)
        or left < NUMBER_MIN
        or right > NUMBER_MAX
        or left >= right
    ):
        raise PairMatrixContractError("pair keys must satisfy 1 <= i < j <= 49")
    return left, right


def _canonical_pair_weight_map(
    pair_weights: Mapping[Any, Any], *, require_complete: bool
) -> dict[Pair, Decimal]:
    normalized = _zero_pair_weights()
    seen: set[Pair] = set()
    try:
        items = pair_weights.items()
    except Exception as exc:
        raise PairMatrixContractError("pair_weights must be a mapping") from exc
    for raw_key, raw_value in items:
        pair = _canonical_pair_key(raw_key)
        if pair in seen:
            raise PairMatrixContractError("duplicate pair key")
        seen.add(pair)
        value = _coerce_decimal(raw_value, label=f"pair_weights[{pair[0]},{pair[1]}]")
        normalized[pair] = _unit_endpoint(value, label=f"pair weight {pair}")
    if require_complete and len(seen) != PAIR_COUNT:
        raise PairMatrixContractError("all 1,176 unordered pair weights are required")
    return {pair: normalized[pair] for pair in PAIR_KEYS}


def incident_pair_sums(
    pair_weights: Mapping[Any, Any],
) -> Mapping[int, Decimal]:
    """Return optional incident-pair diagnostics; never used by ticket selection."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    totals = {
        number: _quantize_output(_DECIMAL_ZERO, label="number aggregate")
        for number in NUMBER_DOMAIN
    }
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            for left, right in PAIR_KEYS:
                totals[left] = context.add(totals[left], normalized[(left, right)])
                totals[right] = context.add(totals[right], normalized[(left, right)])
            return MappingProxyType(
                {
                    number: _quantize_output(value, label="number aggregate")
                    for number, value in totals.items()
                }
            )
    except DecimalException as exc:
        raise NumericInvariantError("number aggregate failed") from exc


def _validate_ticket(ticket: Sequence[object]) -> tuple[int, ...]:
    try:
        values = tuple(ticket)
    except Exception as exc:
        raise InvalidInputError("ticket must be an iterable six-tuple") from exc
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


def ticket_objective(
    ticket: Sequence[object], pair_weights: Mapping[Any, Any]
) -> Decimal:
    """Return the exact 15-pair objective for a sorted six-number ticket."""

    values = _validate_ticket(ticket)
    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            total = context.create_decimal(_DECIMAL_ZERO)
            for left, right in combinations(values, 2):
                total = context.add(total, normalized[(left, right)])
            return _quantize_output(total, label="ticket objective")
    except DecimalException as exc:
        raise NumericInvariantError("ticket objective failed") from exc


def _quantum_integer(value: Decimal) -> int:
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            scaled = context.divide(value, OUTPUT_QUANTUM)
            integral = scaled.to_integral_value(rounding=ROUND_HALF_EVEN, context=context)
            if scaled != integral:
                raise NumericInvariantError("pair weight is not on the output quantum")
            return int(integral)
    except NumericInvariantError:
        raise
    except DecimalException as exc:
        raise NumericInvariantError("pair weight quantum conversion failed") from exc


def _decimal_from_quantum(value: int, *, label: str) -> Decimal:
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            result = context.multiply(context.create_decimal(value), OUTPUT_QUANTUM)
            return _quantize_output(result, label=label)
    except DecimalException as exc:
        raise NumericInvariantError(f"{label} conversion failed") from exc


def optimize_ticket(
    pair_weights: Mapping[Any, Any],
) -> tuple[tuple[int, ...], Decimal]:
    """Exhaustively maximize the 15-pair sum with the frozen tie rule.

    The nested loops are the direct lexicographic expansion of
    ``combinations(range(1, 50), 6)``.  They visit all 13,983,816 legal
    six-subsets, perform no pruning, and keep the first ticket on equality.
    Integer output quanta make the comparison exact and independent of the
    ambient Decimal context.
    """

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    scaled = [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]
    for (left, right), value in normalized.items():
        quantum = _quantum_integer(value)
        scaled[left][right] = quantum

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
        raise PairMatrixContractError("ticket enumeration produced no legal six-subset")
    return best_ticket, _decimal_from_quantum(best_score, label="ticket objective")


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete deterministic output for one NF02 invocation."""

    method_id: str
    design_name: str
    status: str
    window_size: int
    prediction_count: int
    pair_weights: Mapping[Pair, Decimal]
    ticket_objective: Decimal
    ticket: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.design_name != DESIGN_NAME:
            raise NumericInvariantError("result identity does not match the sealed NF02 identity")
        if self.status not in (COMPLETE_STATUS, FALLBACK_STATUS):
            raise NumericInvariantError("unknown result status")
        if self.window_size != WINDOW_SIZE or self.prediction_count != PREDICTION_COUNT:
            raise NumericInvariantError("result constants do not match the sealed NF02 constants")
        normalized = _canonical_pair_weight_map(self.pair_weights, require_complete=True)
        object.__setattr__(self, "pair_weights", MappingProxyType(normalized))
        objective = _coerce_decimal(self.ticket_objective, label="ticket_objective")
        objective = _quantize_output(objective, label="ticket objective")
        object.__setattr__(self, "ticket_objective", objective)
        ticket = _validate_ticket(self.ticket)
        object.__setattr__(self, "ticket", ticket)
        if self.status == FALLBACK_STATUS:
            if (
                objective != _quantize_output(_DECIMAL_ZERO, label="fallback objective")
                or ticket != (1, 2, 3, 4, 5, 6)
                or any(value != _DECIMAL_ZERO for value in normalized.values())
            ):
                raise NumericInvariantError("fallback result does not match its frozen output")
        elif objective != ticket_objective(ticket, normalized):
            raise NumericInvariantError(
                "ticket objective does not match the contained pair weights"
            )

    @property
    def semantic_signature(self) -> str:
        return SEMANTIC_SIGNATURE

    @property
    def min_history(self) -> int:
        return MIN_HISTORY

    @property
    def k(self) -> int:
        return K

    @property
    def number_level_aggregation(self) -> Mapping[int, Decimal]:
        """Optional incident sums, excluded from the ticket computation/output."""

        return incident_pair_sums(self.pair_weights)

    @property
    def pair_weight_matrix(self) -> Mapping[Pair, Decimal]:
        return self.pair_weights

    def canonical_dict(self) -> dict[str, object]:
        """Return an insertion-ordered fixed-point JSON-ready result."""

        pair_payload = {
            f"{left}-{right}": _fixed_decimal_string(value)
            for (left, right), value in self.pair_weights.items()
        }
        return {
            "method_id": self.method_id,
            "design_name": self.design_name,
            "status": self.status,
            "window_size": self.window_size,
            "prediction_count": self.prediction_count,
            "pair_weights": pair_payload,
            "ticket_objective": _fixed_decimal_string(self.ticket_objective),
            "ticket": list(self.ticket),
        }

    def canonical_bytes(self) -> bytes:
        return dumps(
            self.canonical_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=False
        ).encode("utf-8")

    def canonical_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")

    def to_dict(self) -> dict[str, object]:
        return self.canonical_dict()

    def to_json(self) -> str:
        return self.canonical_json()


def _fixed_decimal_string(value: Decimal) -> str:
    quantized = _quantize_output(value, label="serialization value")
    serialized = format(quantized, "f")
    if "." not in serialized:
        serialized = f"{serialized}.{'0' * DECIMAL_OUTPUT_PLACES}"
    integer, fractional = serialized.split(".", maxsplit=1)
    if len(fractional) < DECIMAL_OUTPUT_PLACES:
        fractional += "0" * (DECIMAL_OUTPUT_PLACES - len(fractional))
    elif len(fractional) > DECIMAL_OUTPUT_PLACES:
        fractional = fractional[:DECIMAL_OUTPUT_PLACES]
    if quantized.is_zero():
        integer = "0"
    return f"{integer}.{fractional}"


def _fallback_result() -> AnalysisResult:
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=FALLBACK_STATUS,
        window_size=WINDOW_SIZE,
        prediction_count=PREDICTION_COUNT,
        pair_weights=zero_pair_weights(),
        ticket_objective=_quantize_output(_DECIMAL_ZERO, label="fallback objective"),
        ticket=(1, 2, 3, 4, 5, 6),
    )


def analyze(history: object, cutoff: object) -> AnalysisResult:
    """Analyze only the sealed causal window and emit one exact six-number ticket."""

    history_length = _history_length(history)
    validated_cutoff = _validated_cutoff(cutoff, history_length)
    if validated_cutoff < MIN_HISTORY:
        return _fallback_result()

    draws = _read_causal_window(history, validated_cutoff)
    streams = build_membership_streams(draws)
    pair_weights = _pair_weights_from_streams(streams)
    ticket, objective = optimize_ticket(pair_weights)
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=COMPLETE_STATUS,
        window_size=WINDOW_SIZE,
        prediction_count=PREDICTION_COUNT,
        pair_weights=pair_weights,
        ticket_objective=objective,
        ticket=ticket,
    )


__all__ = [
    "COMPLETE_STATUS",
    "DECIMAL_CONTEXT",
    "DECIMAL_OUTPUT_PLACES",
    "DESIGN_NAME",
    "DRAW_SIZE",
    "FALLBACK_STATUS",
    "LOG_BASE",
    "METHOD_ID",
    "MIN_HISTORY",
    "NUMBER_DOMAIN",
    "NUMBER_MAX",
    "NUMBER_MIN",
    "OUTPUT_QUANTUM",
    "OUTPUT_SCALE",
    "PAIR_COUNT",
    "PAIR_KEYS",
    "PAIR_WEIGHT_QUANTUM",
    "PREDICTION_COUNT",
    "SEMANTIC_SIGNATURE",
    "TICKET_COUNT",
    "WINDOW_SIZE",
    "AnalysisResult",
    "BigLottoL2PairwiseTransferEntropyError",
    "ContextPairKey",
    "DirectionalCounts",
    "DirectionalScore",
    "InvalidCutoffError",
    "InvalidHistoryError",
    "InvalidInputError",
    "K",
    "L",
    "NumericContractError",
    "NumericInvariantError",
    "Pair",
    "PairMatrixContractError",
    "PredictionRow",
    "TargetContextKey",
    "TripleKey",
    "analyze",
    "build_conditional_counts",
    "build_lagged_states",
    "build_membership_streams",
    "build_prediction_rows",
    "conditional_counts",
    "conditional_entropy",
    "conditional_entropy_from_counts",
    "directional_score",
    "encode_state",
    "flatten_state",
    "incident_pair_sums",
    "normalized_transfer_entropy",
    "optimize_ticket",
    "pair_weight",
    "ticket_objective",
    "transfer_entropy",
    "transfer_entropy_from_counts",
    "zero_pair_weights",
]
