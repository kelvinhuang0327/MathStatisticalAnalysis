"""Pooled logistic regression, Platt calibration, and proper-score evaluation.

Lottery-agnostic building blocks for the H04/H07-conditional Phase 0 vertical
slice: a small, fixed-dimension logistic regression fit by exact
Newton-Raphson (no numpy/scipy — this project ships neither), a Platt-style
one-feature recalibration built on the same fitter, and proper-scoring-rule
(Brier, log-loss) plus discrimination (rank-based AUC) evaluation.

Nothing here reads a database, a file, or a clock, and nothing here is
lottery-specific: every function takes plain design rows and outcomes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


def sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid, safe for large |x|."""

    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve `matrix @ x = vector` by Gaussian elimination with partial pivoting.

    `matrix` is square, `len(matrix) == len(vector)`. Intended only for the
    small (2-3 dimensional) systems this module's fitters produce.
    """

    n = len(vector)
    augmented = [[*matrix[row], vector[row]] for row in range(n)]

    for column in range(n):
        pivot_row = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot_row][column]) < 1e-14:
            raise ValueError("linear system is singular or near-singular")
        augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot_value = augmented[column][column]
        augmented[column] = [value / pivot_value for value in augmented[column]]

        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor != 0.0:
                augmented[row] = [
                    a - factor * b for a, b in zip(augmented[row], augmented[column], strict=True)
                ]

    return [augmented[row][n] for row in range(n)]


@dataclass(frozen=True, slots=True)
class LogisticFitResult:
    coefficients: tuple[float, ...]
    iterations: int
    converged: bool


def fit_logistic_regression(
    design_rows: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    *,
    max_iterations: int = 50,
    tolerance: float = 1e-10,
) -> LogisticFitResult:
    """Exact unregularized logistic regression MLE via Newton-Raphson (IRLS).

    `design_rows[i]` must include an explicit intercept column (a leading
    `1.0`) if one is wanted -- this function does not add one implicitly.
    """

    n_rows = len(design_rows)
    if n_rows == 0:
        raise ValueError("design_rows must be non-empty")
    if len(outcomes) != n_rows:
        raise ValueError("design_rows and outcomes must have the same length")
    n_params = len(design_rows[0])
    if any(len(row) != n_params for row in design_rows):
        raise ValueError("every design row must have the same length")
    if any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError("outcomes must be 0/1")

    coefficients = [0.0] * n_params
    for iteration in range(1, max_iterations + 1):
        linear_predictor = [
            sum(coefficients[j] * design_rows[i][j] for j in range(n_params))
            for i in range(n_rows)
        ]
        probabilities = [sigmoid(value) for value in linear_predictor]

        gradient = [
            sum((outcomes[i] - probabilities[i]) * design_rows[i][j] for i in range(n_rows))
            for j in range(n_params)
        ]
        hessian = [[0.0] * n_params for _ in range(n_params)]
        for i in range(n_rows):
            weight = probabilities[i] * (1.0 - probabilities[i])
            if weight <= 0.0:
                continue
            row_i = design_rows[i]
            for a in range(n_params):
                weighted = weight * row_i[a]
                for b in range(n_params):
                    hessian[a][b] += weighted * row_i[b]
        for a in range(n_params):
            hessian[a][a] += 1e-10  # ridge-free jitter for numerical stability only

        step = _solve_linear_system(hessian, gradient)
        coefficients = [coefficients[j] + step[j] for j in range(n_params)]

        if math.sqrt(sum(value * value for value in step)) < tolerance:
            return LogisticFitResult(tuple(coefficients), iteration, True)

    return LogisticFitResult(tuple(coefficients), max_iterations, False)


def predict_probabilities(
    design_rows: Sequence[Sequence[float]], coefficients: Sequence[float]
) -> list[float]:
    return [
        sigmoid(sum(coefficients[j] * row[j] for j in range(len(coefficients))))
        for row in design_rows
    ]


def fit_platt_calibration(
    raw_logits: Sequence[float], outcomes: Sequence[int]
) -> LogisticFitResult:
    """Fit `logit(P) = a + b * raw_logit` -- a 1-feature Platt recalibration."""

    design_rows = [[1.0, logit] for logit in raw_logits]
    return fit_logistic_regression(design_rows, outcomes)


def apply_platt_calibration(
    raw_logits: Sequence[float], calibration: LogisticFitResult
) -> list[float]:
    a, b = calibration.coefficients
    return [sigmoid(a + b * logit) for logit in raw_logits]


def logit(probability: float) -> float:
    clipped = min(max(probability, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    if not probabilities:
        raise ValueError("probabilities must be non-empty")
    return math.fsum((p - y) ** 2 for p, y in zip(probabilities, outcomes, strict=True)) / len(
        probabilities
    )


def mean_log_loss(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    if not probabilities:
        raise ValueError("probabilities must be non-empty")
    total = 0.0
    for p, y in zip(probabilities, outcomes, strict=True):
        clipped = min(max(p, 1e-12), 1.0 - 1e-12)
        total += -(y * math.log(clipped) + (1 - y) * math.log(1.0 - clipped))
    return total / len(probabilities)


def rank_auc(probabilities: Sequence[float], outcomes: Sequence[int]) -> float | None:
    """Mann-Whitney-U based AUC: P(score(positive) > score(negative)), ties=0.5.

    Returns None if `outcomes` has no positives or no negatives (AUC is
    undefined, not zero).
    """

    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    n_pos = sum(1 for y in outcomes if y == 1)
    n_neg = len(outcomes) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None

    order = sorted(range(len(probabilities)), key=lambda i: probabilities[i])
    ranks = [0.0] * len(probabilities)
    index = 0
    while index < len(order):
        tie_end = index
        while (
            tie_end + 1 < len(order)
            and probabilities[order[tie_end + 1]] == probabilities[order[index]]
        ):
            tie_end += 1
        average_rank = (index + 1 + tie_end + 1) / 2.0
        for position in range(index, tie_end + 1):
            ranks[order[position]] = average_rank
        index = tie_end + 1

    rank_sum_positive = math.fsum(ranks[i] for i in range(len(outcomes)) if outcomes[i] == 1)
    return (rank_sum_positive - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    bin_index: int
    count: int
    mean_predicted: float
    observed_rate: float


def reliability_table(
    probabilities: Sequence[float], outcomes: Sequence[int], *, n_bins: int = 10
) -> tuple[ReliabilityBin, ...]:
    """Bin predictions into `n_bins` equal-width [0,1] bins; report predicted vs observed."""

    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    buckets: list[list[int]] = [[] for _ in range(n_bins)]
    for index, p in enumerate(probabilities):
        bin_index = min(n_bins - 1, int(p * n_bins))
        buckets[bin_index].append(index)

    result: list[ReliabilityBin] = []
    for bin_index, indices in enumerate(buckets):
        if not indices:
            continue
        mean_predicted = math.fsum(probabilities[i] for i in indices) / len(indices)
        observed_rate = math.fsum(outcomes[i] for i in indices) / len(indices)
        result.append(ReliabilityBin(bin_index, len(indices), mean_predicted, observed_rate))
    return tuple(result)
