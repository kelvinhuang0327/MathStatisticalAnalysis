"""Pure data contract for the fixed B649 C2 seven-pair equality batch.

This module validates supplied histogram results only. It does not load the
measurement engine, run a checker, or create candidate rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

Pair = tuple[int, int]
Histogram = tuple[tuple[int, int], ...]

EXPECTED_HISTOGRAM_TOTAL = 13_983_798


class PairStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NOT_RUN = "NOT_RUN"


class BatchStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class PairSpec:
    ordered_pair: Pair
    engine_pair: Pair
    orbit_index: int
    orbit_size: int


BATCH_PAIR_SPECS = (
    PairSpec((0, 6), (0, 11), 5, 1),
    PairSpec((0, 12), (0, 12), 11, 6),
    PairSpec((0, 18), (0, 18), 12, 2),
    PairSpec((12, 13), (12, 13), 90, 6),
    PairSpec((12, 15), (12, 15), 91, 9),
    PairSpec((12, 18), (12, 18), 92, 12),
    PairSpec((18, 19), (18, 19), 93, 1),
)
BATCH_ORBIT_WEIGHT_TOTAL = sum(spec.orbit_size for spec in BATCH_PAIR_SPECS)


@dataclass(frozen=True)
class PairResult:
    """One fixed pair's histogram status and, only when complete, exact E."""

    ordered_pair: Pair
    engine_pair: Pair
    orbit_index: int
    orbit_size: int
    status: PairStatus
    target_gain_sum: int | None = None
    histogram: Histogram | None = None
    exact_equality_count: int | None = None


@dataclass(frozen=True)
class ComplementContribution:
    gain_a: int
    gain_b: int
    count_a: int
    count_b: int
    formula: str
    contribution: int


@dataclass(frozen=True)
class BatchSummary:
    status: BatchStatus
    results: tuple[PairResult, ...]
    completed_ordered_pairs: tuple[Pair, ...]
    completed_pair_count: int
    coverage_orbit_size: int


def _require_nonnegative_int(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _validate_pair(pair: object, name: str) -> Pair:
    if not isinstance(pair, tuple) or len(pair) != 2:
        raise ValueError(f"{name} must be a two-integer tuple")
    left = _require_nonnegative_int(pair[0], f"{name}[0]")
    right = _require_nonnegative_int(pair[1], f"{name}[1]")
    return (left, right)


def _validate_histogram_shape(histogram: Histogram) -> int:
    if not isinstance(histogram, tuple):
        raise ValueError("histogram must be a tuple of ordered (gain, count) buckets")

    previous_gain: int | None = None
    total = 0
    for bucket in histogram:
        if not isinstance(bucket, tuple) or len(bucket) != 2:
            raise ValueError("each histogram bucket must be a (gain, count) tuple")
        gain, count = bucket
        _require_nonnegative_int(gain, "gain key")
        if type(count) is not int or count <= 0:
            raise ValueError("histogram counts must be positive integers")
        if previous_gain is not None and gain <= previous_gain:
            raise ValueError("histogram gain keys must be unique and strictly increasing")
        previous_gain = gain
        total += count
    return total


def complementary_contributions(
    histogram: Histogram, target_gain_sum: int
) -> tuple[ComplementContribution, ...]:
    """Return each unordered complementary gain pair exactly once."""

    target = _require_nonnegative_int(target_gain_sum, "target_gain_sum")
    _validate_histogram_shape(histogram)
    counts = dict(histogram)
    rows: list[ComplementContribution] = []
    for gain_a, count_a in histogram:
        gain_b = target - gain_a
        if gain_a > gain_b or gain_b not in counts:
            continue
        count_b = counts[gain_b]
        if gain_a < gain_b:
            formula = "PRODUCT"
            contribution = count_a * count_b
        else:
            formula = "CHOOSE_2_DISTINCT"
            contribution = math.comb(count_a, 2)
        rows.append(
            ComplementContribution(
                gain_a=gain_a,
                gain_b=gain_b,
                count_a=count_a,
                count_b=count_b,
                formula=formula,
                contribution=contribution,
            )
        )
    return tuple(rows)


def exact_equality_sum(
    histogram: Histogram, target_gain_sum: int
) -> int:
    """Sum exact integer contributions; callers must establish completeness."""

    return sum(
        row.contribution
        for row in complementary_contributions(histogram, target_gain_sum)
    )


def _spec_for(ordered_pair: Pair) -> PairSpec:
    for spec in BATCH_PAIR_SPECS:
        if spec.ordered_pair == ordered_pair:
            return spec
    raise ValueError(f"ordered pair {ordered_pair!r} is not in the fixed seven-pair batch")


def validate_pair_result(result: PairResult) -> None:
    """Validate one result's fixed mapping, status, histogram, and exact E."""

    if not isinstance(result, PairResult):
        raise ValueError("each result must be a PairResult")
    ordered_pair = _validate_pair(result.ordered_pair, "ordered_pair")
    engine_pair = _validate_pair(result.engine_pair, "engine_pair")
    spec = _spec_for(ordered_pair)
    if engine_pair != spec.engine_pair:
        raise ValueError(f"engine pair mismatch for ordered pair {ordered_pair}")
    if type(result.orbit_index) is not int or type(result.orbit_size) is not int:
        raise ValueError("orbit index and size must be integers")
    if result.orbit_index != spec.orbit_index or result.orbit_size != spec.orbit_size:
        raise ValueError(f"orbit metadata mismatch for ordered pair {ordered_pair}")
    if not isinstance(result.status, PairStatus):
        raise ValueError("status must be COMPLETE, INCOMPLETE, or NOT_RUN")

    if result.status is PairStatus.COMPLETE:
        if result.histogram is None:
            raise ValueError("COMPLETE result requires a full histogram")
        histogram_total = _validate_histogram_shape(result.histogram)
        if histogram_total != EXPECTED_HISTOGRAM_TOTAL:
            raise ValueError(
                "COMPLETE histogram total must equal "
                f"{EXPECTED_HISTOGRAM_TOTAL}; got {histogram_total}"
            )
        if result.target_gain_sum is None:
            raise ValueError("COMPLETE result requires target_gain_sum")
        target = _require_nonnegative_int(result.target_gain_sum, "target_gain_sum")
        if result.exact_equality_count is None:
            raise ValueError("COMPLETE result requires a non-null exact E")
        exact_e = _require_nonnegative_int(result.exact_equality_count, "exact E")
        derived_e = exact_equality_sum(result.histogram, target)
        if exact_e != derived_e:
            raise ValueError(f"exact E mismatch: expected {derived_e}, got {exact_e}")
        return

    if result.exact_equality_count is not None:
        raise ValueError(f"{result.status.value} result must have null exact E")
    if result.target_gain_sum is not None:
        _require_nonnegative_int(result.target_gain_sum, "target_gain_sum")

    if result.status is PairStatus.NOT_RUN:
        if result.histogram is not None:
            raise ValueError("NOT_RUN result cannot carry a histogram")
        return

    if result.histogram is not None:
        histogram_total = _validate_histogram_shape(result.histogram)
        if histogram_total > EXPECTED_HISTOGRAM_TOTAL:
            raise ValueError("INCOMPLETE histogram cannot exceed the expected total")


def validate_batch(results: tuple[PairResult, ...] | list[PairResult]) -> BatchSummary:
    """Validate the exact fixed batch and summarize completed orbit coverage."""

    if not isinstance(results, (tuple, list)):
        raise ValueError("batch results must be a tuple or list")
    if len(results) != len(BATCH_PAIR_SPECS):
        raise ValueError(f"batch must contain exactly {len(BATCH_PAIR_SPECS)} pair results")

    seen: set[Pair] = set()
    for result in results:
        if not isinstance(result, PairResult):
            raise ValueError("each result must be a PairResult")
        validate_pair_result(result)
        if result.ordered_pair in seen:
            raise ValueError(f"duplicate ordered pair {result.ordered_pair}")
        seen.add(result.ordered_pair)

    expected_order = tuple(spec.ordered_pair for spec in BATCH_PAIR_SPECS)
    actual_order = tuple(result.ordered_pair for result in results)
    if actual_order != expected_order:
        raise ValueError("batch ordered pairs must match the fixed seven-pair order")

    completed = tuple(
        result for result in results if result.status is PairStatus.COMPLETE
    )
    return BatchSummary(
        status=(
            BatchStatus.COMPLETE
            if len(completed) == len(BATCH_PAIR_SPECS)
            else BatchStatus.PARTIAL
        ),
        results=tuple(results),
        completed_ordered_pairs=tuple(result.ordered_pair for result in completed),
        completed_pair_count=len(completed),
        coverage_orbit_size=sum(result.orbit_size for result in completed),
    )
