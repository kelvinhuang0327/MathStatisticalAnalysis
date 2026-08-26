"""Frozen NF01 lag-block HSIC constructor for BIG_LOTTO.

This is a standalone research computation.  It consumes only a caller-owned
chronological sequence of completed six-number draws and never reaches into
application, strategy, persistence, or runtime layers.

The frozen calculation is:

* read exactly the 256 draws before a sufficient cutoff;
* turn each number's raw membership stream into overlapping ordered
  eight-draw blocks;
* use a Kronecker-delta Gram matrix and exact biased finite-sample HSIC for
  every unordered pair; and
* maximize the exact sum of the 15 contained pair weights over every sorted
  six-subset of ``1..49``.

The centered Gram implementation uses a common exact integer numerator over
``N**2``.  This is algebraically identical to the required Fraction matrix
entries and lets the exhaustive pair and ticket calculations remain finite
without introducing floating-point arithmetic, clipping, or approximation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from json import dumps
from math import lcm
from types import MappingProxyType
from typing import TypeGuard, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1"
DESIGN_NAME = "BIGLOTTO_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1"
SEMANTIC_SIGNATURE = "1ce87b2abf6fb55c812d4d09476ba050bab8e8165d08da9b8bf46e19a5a8af6f"

NUMBER_MIN = 1
NUMBER_MAX = 49
NUMBER_DOMAIN: tuple[int, ...] = tuple(range(NUMBER_MIN, NUMBER_MAX + 1))
DRAW_SIZE = 6
MIN_HISTORY = 256
WINDOW_SIZE = MIN_HISTORY
BLOCK_LENGTH = 8
OBSERVATION_COUNT = WINDOW_SIZE - BLOCK_LENGTH + 1
PAIR_COUNT = (NUMBER_MAX * (NUMBER_MAX - 1)) // 2
TICKET_COUNT = 13_983_816

COMPLETE_STATUS = "COMPLETE"
FALLBACK_STATUS = "FALLBACK_INSUFFICIENT_HISTORY"
KERNEL_BANDWIDTH_RULE = "NOT_APPLICABLE: fixed Kronecker-delta kernel has no bandwidth"

type Pair = tuple[int, int]
type Draw = tuple[int, ...]
type LagBlock = tuple[int, ...]
type GramMatrix = tuple[tuple[int, ...], ...]
type RationalMatrix = tuple[tuple[Fraction, ...], ...]
type RationalValue = int | Fraction


class BigLottoL2PairwiseEighthError(ValueError):
    """Base class for closed-contract errors in the frozen computation."""


class InvalidInputError(BigLottoL2PairwiseEighthError):
    """Raised when the cutoff or an accessed draw violates the input contract."""


class NumericInvariantError(BigLottoL2PairwiseEighthError):
    """Raised when an exact mathematical invariant is violated."""


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


def _as_exact_fraction(value: object, *, label: str) -> Fraction:
    if isinstance(value, bool):
        raise BigLottoL2PairwiseEighthError(f"{label} must be an exact integer or Fraction")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    raise BigLottoL2PairwiseEighthError(f"{label} must be an exact integer or Fraction")


def _validate_ticket(ticket: Sequence[object]) -> tuple[int, ...]:
    values = tuple(ticket)
    if len(values) != DRAW_SIZE:
        raise BigLottoL2PairwiseEighthError("ticket must contain exactly six numbers")
    if any(not _is_non_boolean_integer(value) for value in values):
        raise BigLottoL2PairwiseEighthError("ticket values must be non-boolean integers")
    integer_values = cast(tuple[int, ...], values)
    if tuple(sorted(integer_values)) != integer_values:
        raise BigLottoL2PairwiseEighthError("ticket must be sorted in ascending order")
    if len(set(integer_values)) != DRAW_SIZE:
        raise BigLottoL2PairwiseEighthError("ticket values must be unique")
    if any(value < NUMBER_MIN or value > NUMBER_MAX for value in integer_values):
        raise BigLottoL2PairwiseEighthError("ticket values must lie in 1..49")
    return integer_values


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


def _history_length(history: Sequence[object]) -> int:
    try:
        return len(history)
    except Exception as exc:
        raise InvalidInputError("history must be a finite random-access sequence") from exc


def _validated_cutoff(cutoff: object, history_length: int) -> int:
    if not _is_non_boolean_integer(cutoff):
        raise InvalidInputError("cutoff must be a non-boolean integer")
    if cutoff < 0 or cutoff > history_length:
        raise InvalidInputError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return cutoff


def _read_causal_window(history: Sequence[object], cutoff: int) -> tuple[Draw, ...]:
    start = cutoff - WINDOW_SIZE
    draws: list[Draw] = []
    for index in range(start, cutoff):
        try:
            raw_draw = history[index]
        except Exception as exc:
            raise InvalidInputError(f"history[{index}] could not be read") from exc
        draws.append(_validate_draw(raw_draw, index=index))
    if len(draws) != WINDOW_SIZE:
        raise NumericInvariantError("causal window length is not 256")
    return tuple(draws)


def _zero_pair_weights() -> dict[Pair, Fraction]:
    return {pair: Fraction(0) for pair in PAIR_KEYS}


def zero_pair_weights() -> Mapping[Pair, Fraction]:
    """Return a fresh canonical all-zero 1,176-pair matrix for synthetic use."""

    return MappingProxyType(_zero_pair_weights())


def build_lag_blocks(stream: Sequence[object]) -> tuple[LagBlock, ...]:
    """Build ordered overlapping eight-bit blocks from one binary stream."""

    values = tuple(stream)
    if len(values) < BLOCK_LENGTH:
        raise BigLottoL2PairwiseEighthError("binary stream is shorter than the block length")
    if any(not _is_non_boolean_integer(value) or value not in (0, 1) for value in values):
        raise BigLottoL2PairwiseEighthError(
            "lag stream must contain only non-boolean 0/1 integers"
        )
    bits = cast(tuple[int, ...], values)
    return tuple(
        tuple(bits[start : start + BLOCK_LENGTH])
        for start in range(len(bits) - BLOCK_LENGTH + 1)
    )


def delta_kernel(left: Sequence[int], right: Sequence[int]) -> int:
    """Return the fixed Kronecker-delta kernel value for two ordered blocks."""

    return int(tuple(left) == tuple(right))


def build_gram_matrix(blocks: Sequence[Sequence[int]]) -> GramMatrix:
    """Build the exact integer 0/1 delta-kernel Gram matrix."""

    normalized = tuple(tuple(block) for block in blocks)
    if not normalized:
        raise BigLottoL2PairwiseEighthError("at least one lag block is required")
    block_length = len(normalized[0])
    if block_length != BLOCK_LENGTH or any(len(block) != block_length for block in normalized):
        raise BigLottoL2PairwiseEighthError("all lag blocks must contain eight values")
    if any(
        any(not _is_non_boolean_integer(value) or value not in (0, 1) for value in block)
        for block in normalized
    ):
        raise BigLottoL2PairwiseEighthError(
            "lag blocks must contain only non-boolean 0/1 integers"
        )
    return tuple(
        tuple(delta_kernel(left, right) for right in normalized) for left in normalized
    )


def centering_matrix(observation_count: int) -> RationalMatrix:
    """Return ``H[a,b] = 1{a=b} - 1/N`` using exact Fractions."""

    if not _is_non_boolean_integer(observation_count) or observation_count <= 0:
        raise BigLottoL2PairwiseEighthError(
            "observation_count must be a positive non-boolean integer"
        )
    inverse = Fraction(1, observation_count)
    return tuple(
        tuple(Fraction(int(row == column)) - inverse for column in range(observation_count))
        for row in range(observation_count)
    )


def _normalize_exact_matrix(
    matrix: Sequence[Sequence[RationalValue]], *, label: str
) -> tuple[tuple[Fraction, ...], ...]:
    rows = tuple(
        tuple(
            _as_exact_fraction(value, label=f"{label}[{row_index},{column_index}]")
            for column_index, value in enumerate(row)
        )
        for row_index, row in enumerate(matrix)
    )
    if not rows or any(len(row) != len(rows) for row in rows):
        raise BigLottoL2PairwiseEighthError(f"{label} must be a non-empty square matrix")
    return rows


def center_gram_matrix(matrix: Sequence[Sequence[RationalValue]]) -> RationalMatrix:
    """Return ``H K H`` with exact rational entries and no implicit defaults."""

    gram = _normalize_exact_matrix(matrix, label="gram")
    size = len(gram)
    row_sums = tuple(sum(row, Fraction(0)) for row in gram)
    column_sums = tuple(
        sum((gram[row][column] for row in range(size)), Fraction(0))
        for column in range(size)
    )
    total = sum(row_sums, Fraction(0))
    inverse_size = Fraction(1, size)
    inverse_size_squared = Fraction(1, size * size)
    return tuple(
        tuple(
            gram[row][column]
            - row_sums[row] * inverse_size
            - column_sums[column] * inverse_size
            + total * inverse_size_squared
            for column in range(size)
        )
        for row in range(size)
    )


def hsic_from_gram_matrices(
    left: Sequence[Sequence[RationalValue]], right: Sequence[Sequence[RationalValue]]
) -> Fraction:
    """Compute the frozen biased finite-sample HSIC exactly.

    Since ``H`` is symmetric and idempotent and both Gram matrices are
    symmetric, ``tr(K_i H K_j H)`` equals the Frobenius inner product of
    ``H K_i H`` and ``H K_j H``.  The result is divided by exactly ``N**2``.
    """

    left_exact = _normalize_exact_matrix(left, label="left gram")
    right_exact = _normalize_exact_matrix(right, label="right gram")
    if len(left_exact) != len(right_exact):
        raise BigLottoL2PairwiseEighthError("Gram matrices must have the same dimensions")
    left_centered = center_gram_matrix(left_exact)
    right_centered = center_gram_matrix(right_exact)
    trace = sum(
        (
            left_centered[row][column] * right_centered[row][column]
            for row in range(len(left_centered))
            for column in range(len(left_centered))
        ),
        Fraction(0),
    )
    return trace / (len(left_centered) * len(left_centered))


def build_membership_streams(draws: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Build raw 49-number membership streams from already validated draws."""

    normalized_draws = tuple(_validate_draw(draw, index=index) for index, draw in enumerate(draws))
    return tuple(
        tuple(int(number in draw) for draw in normalized_draws) for number in NUMBER_DOMAIN
    )


def _scaled_centered_gram(blocks: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Return exact numerators for ``H K H`` with common denominator ``N**2``."""

    gram = build_gram_matrix(blocks)
    size = len(gram)
    scale = size * size
    row_sums = tuple(sum(row) for row in gram)
    total = sum(row_sums)
    return tuple(
        tuple(
            scale * gram[row][column]
            - size * row_sums[row]
            - size * row_sums[column]
            + total
            for column in range(size)
        )
        for row in range(size)
    )


def _pair_weights_from_draws(draws: Sequence[Draw]) -> dict[Pair, Fraction]:
    streams = tuple(
        tuple(int(number in draw) for draw in draws) for number in NUMBER_DOMAIN
    )
    centered_numerators = tuple(
        _scaled_centered_gram(build_lag_blocks(stream)) for stream in streams
    )
    denominator = OBSERVATION_COUNT**6
    pair_weights: dict[Pair, Fraction] = {}
    for left_index, left_number in enumerate(NUMBER_DOMAIN):
        left_matrix = centered_numerators[left_index]
        for right_index in range(left_index + 1, len(NUMBER_DOMAIN)):
            right_number = NUMBER_DOMAIN[right_index]
            right_matrix = centered_numerators[right_index]
            numerator = sum(
                left_matrix[row][column] * right_matrix[row][column]
                for row in range(OBSERVATION_COUNT)
                for column in range(OBSERVATION_COUNT)
            )
            weight = Fraction(numerator, denominator)
            if weight < 0:
                raise NumericInvariantError("HSIC pair weight must be non-negative")
            pair_weights[(left_number, right_number)] = weight
    if len(pair_weights) != PAIR_COUNT:
        raise NumericInvariantError("pair-weight cardinality is not 1,176")
    return pair_weights


def _canonical_pair_weight_map(
    pair_weights: Mapping[Pair, RationalValue], *, require_complete: bool
) -> dict[Pair, Fraction]:
    normalized = _zero_pair_weights()
    for key, value in pair_weights.items():
        left, right = key
        if (
            not _is_non_boolean_integer(left)
            or not _is_non_boolean_integer(right)
            or left >= right
            or left < NUMBER_MIN
            or right > NUMBER_MAX
        ):
            raise BigLottoL2PairwiseEighthError("pair keys must satisfy 1 <= i < j <= 49")
        pair = (left, right)
        if pair not in normalized:
            raise BigLottoL2PairwiseEighthError("pair key is outside the canonical pair domain")
        fraction = _as_exact_fraction(value, label=f"pair_weights[{left},{right}]")
        if fraction < 0:
            raise NumericInvariantError("pair weights must be non-negative")
        normalized[pair] = fraction
    if require_complete and len(pair_weights) != PAIR_COUNT:
        raise BigLottoL2PairwiseEighthError("all 1,176 unordered pair weights are required")
    return {pair: normalized[pair] for pair in PAIR_KEYS}


def incident_pair_sums(
    pair_weights: Mapping[Pair, RationalValue],
) -> Mapping[int, Fraction]:
    """Return optional exact incident-pair diagnostics without affecting Q."""

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    totals = {number: Fraction(0) for number in NUMBER_DOMAIN}
    for left, right in PAIR_KEYS:
        totals[left] += normalized[(left, right)]
        totals[right] += normalized[(left, right)]
    return MappingProxyType(totals)


def ticket_objective(
    ticket: Sequence[object], pair_weights: Mapping[Pair, RationalValue]
) -> Fraction:
    """Return the exact sum of the 15 contained unordered pair weights."""

    values = _validate_ticket(ticket)
    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    return sum(
        (
            normalized[(values[left_index], values[right_index])]
            for left_index in range(DRAW_SIZE)
            for right_index in range(left_index + 1, DRAW_SIZE)
        ),
        Fraction(0),
    )


def optimize_ticket(
    pair_weights: Mapping[Pair, RationalValue],
) -> tuple[tuple[int, ...], Fraction]:
    """Exhaustively maximize ``Q`` with the frozen first-maximizer tie rule.

    The nested loops are the direct lexicographic expansion of
    ``combinations(range(1, 50), 6)``.  Every one of the 13,983,816 legal
    six-subsets is visited; the partial sums only avoid recomputing already
    contained pairs and never prune a candidate.
    """

    normalized = _canonical_pair_weight_map(pair_weights, require_complete=False)
    denominator = 1
    for value in normalized.values():
        denominator = lcm(denominator, value.denominator)
    scaled = [[0 for _ in range(NUMBER_MAX + 1)] for _ in range(NUMBER_MAX + 1)]
    for (left, right), value in normalized.items():
        scaled[left][right] = value.numerator * (denominator // value.denominator)

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
    return best_ticket, Fraction(best_score, denominator)


def _fallback_result() -> AnalysisResult:
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=FALLBACK_STATUS,
        window_size=WINDOW_SIZE,
        block_length=BLOCK_LENGTH,
        observation_count=OBSERVATION_COUNT,
        pair_weights=MappingProxyType(_zero_pair_weights()),
        ticket_objective=Fraction(0),
        ticket=(1, 2, 3, 4, 5, 6),
    )


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """One canonical NF01 result containing all pair weights and one ticket."""

    method_id: str
    design_name: str
    status: str
    window_size: int
    block_length: int
    observation_count: int
    pair_weights: Mapping[Pair, Fraction]
    ticket_objective: Fraction
    ticket: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.design_name != DESIGN_NAME:
            raise NumericInvariantError("result identity does not match the sealed NF01 identity")
        if self.status not in (COMPLETE_STATUS, FALLBACK_STATUS):
            raise NumericInvariantError("unknown result status")
        if (
            self.window_size != WINDOW_SIZE
            or self.block_length != BLOCK_LENGTH
            or self.observation_count != OBSERVATION_COUNT
        ):
            raise NumericInvariantError("result constants do not match the sealed NF01 constants")
        normalized = _canonical_pair_weight_map(self.pair_weights, require_complete=True)
        object.__setattr__(self, "pair_weights", MappingProxyType(normalized))
        objective = _as_exact_fraction(self.ticket_objective, label="ticket_objective")
        if objective < 0:
            raise NumericInvariantError("ticket objective must be non-negative")
        object.__setattr__(self, "ticket_objective", objective)
        ticket = _validate_ticket(self.ticket)
        object.__setattr__(self, "ticket", ticket)
        if self.status == FALLBACK_STATUS:
            if (
                objective != 0
                or ticket != (1, 2, 3, 4, 5, 6)
                or any(value != 0 for value in self.pair_weights.values())
            ):
                raise NumericInvariantError("fallback result does not match its frozen output")
        elif objective != ticket_objective(ticket, self.pair_weights):
            raise NumericInvariantError(
                "ticket objective does not match the contained pair weights"
            )

    @property
    def number_level_aggregation(self) -> Mapping[int, Fraction]:
        """Optional diagnostic incident sums, excluded from canonical output."""

        return incident_pair_sums(self.pair_weights)

    def canonical_dict(self) -> dict[str, object]:
        """Return the exact insertion-ordered canonical JSON object."""

        pair_payload = {
            f"{left}-{right}": {
                "numerator": value.numerator,
                "denominator": value.denominator,
            }
            for (left, right), value in self.pair_weights.items()
        }
        objective_payload = {
            "numerator": self.ticket_objective.numerator,
            "denominator": self.ticket_objective.denominator,
        }
        return {
            "method_id": self.method_id,
            "design_name": self.design_name,
            "status": self.status,
            "window_size": self.window_size,
            "block_length": self.block_length,
            "observation_count": self.observation_count,
            "pair_weights": pair_payload,
            "ticket_objective": objective_payload,
            "ticket": list(self.ticket),
        }

    def canonical_bytes(self) -> bytes:
        """Serialize the result as compact deterministic UTF-8 JSON bytes."""

        return dumps(
            self.canonical_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=False
        ).encode("utf-8")

    def canonical_json(self) -> str:
        """Serialize the result as compact deterministic JSON text."""

        return self.canonical_bytes().decode("utf-8")


def analyze(history: Sequence[object], cutoff: object) -> AnalysisResult:
    """Analyze only the sealed causal window and emit one exact six-number ticket."""

    history_length = _history_length(history)
    validated_cutoff = _validated_cutoff(cutoff, history_length)
    if validated_cutoff < MIN_HISTORY:
        return _fallback_result()

    draws = _read_causal_window(history, validated_cutoff)
    pair_weights = _pair_weights_from_draws(draws)
    ticket, objective = optimize_ticket(pair_weights)
    return AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=COMPLETE_STATUS,
        window_size=WINDOW_SIZE,
        block_length=BLOCK_LENGTH,
        observation_count=OBSERVATION_COUNT,
        pair_weights=pair_weights,
        ticket_objective=objective,
        ticket=ticket,
    )


__all__ = [
    "BLOCK_LENGTH",
    "COMPLETE_STATUS",
    "DESIGN_NAME",
    "DRAW_SIZE",
    "FALLBACK_STATUS",
    "KERNEL_BANDWIDTH_RULE",
    "METHOD_ID",
    "MIN_HISTORY",
    "NUMBER_DOMAIN",
    "OBSERVATION_COUNT",
    "PAIR_COUNT",
    "PAIR_KEYS",
    "SEMANTIC_SIGNATURE",
    "TICKET_COUNT",
    "WINDOW_SIZE",
    "AnalysisResult",
    "BigLottoL2PairwiseEighthError",
    "GramMatrix",
    "InvalidInputError",
    "NumericInvariantError",
    "analyze",
    "build_gram_matrix",
    "build_lag_blocks",
    "build_membership_streams",
    "center_gram_matrix",
    "centering_matrix",
    "delta_kernel",
    "hsic_from_gram_matrices",
    "incident_pair_sums",
    "optimize_ticket",
    "ticket_objective",
    "zero_pair_weights",
]
