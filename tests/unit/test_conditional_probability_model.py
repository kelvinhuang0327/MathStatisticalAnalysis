from __future__ import annotations

import math
import random

import pytest

from lottolab.research.conditional_probability_model import (
    apply_platt_calibration,
    brier_score,
    fit_logistic_regression,
    fit_platt_calibration,
    logit,
    mean_log_loss,
    predict_probabilities,
    rank_auc,
    reliability_table,
    sigmoid,
)


def test_sigmoid_known_values() -> None:
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(1000.0) == pytest.approx(1.0)
    assert sigmoid(-1000.0) == pytest.approx(0.0)


def test_sigmoid_does_not_overflow_at_extreme_magnitude() -> None:
    # math.exp(800) would raise OverflowError if computed naively.
    assert sigmoid(800.0) == pytest.approx(1.0)
    assert sigmoid(-800.0) == pytest.approx(0.0)


def test_logit_is_inverse_of_sigmoid() -> None:
    for value in (-5.0, -1.0, 0.0, 0.3, 4.0):
        assert logit(sigmoid(value)) == pytest.approx(value, abs=1e-6)


def _synthetic_logistic_dataset(
    true_coefficients: tuple[float, float, float], n: int, seed: int
) -> tuple[list[list[float]], list[int]]:
    rng = random.Random(seed)
    design_rows: list[list[float]] = []
    outcomes: list[int] = []
    for _ in range(n):
        x1 = 1.0 if rng.random() < 0.5 else 0.0
        x2 = rng.uniform(-2.0, 2.0)
        row = [1.0, x1, x2]
        p = sigmoid(sum(c * v for c, v in zip(true_coefficients, row, strict=True)))
        outcomes.append(1 if rng.random() < p else 0)
        design_rows.append(row)
    return design_rows, outcomes


def test_fit_logistic_regression_recovers_known_coefficients() -> None:
    true_coefficients = (-0.5, 0.8, -0.3)
    design_rows, outcomes = _synthetic_logistic_dataset(true_coefficients, n=20_000, seed=12345)
    result = fit_logistic_regression(design_rows, outcomes)
    assert result.converged
    for fitted, true_value in zip(result.coefficients, true_coefficients, strict=True):
        assert fitted == pytest.approx(true_value, abs=0.1)


def test_fit_logistic_regression_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        fit_logistic_regression([[1.0, 0.0]], [0, 1])


def test_fit_logistic_regression_rejects_non_binary_outcomes() -> None:
    with pytest.raises(ValueError, match="0/1"):
        fit_logistic_regression([[1.0, 0.0], [1.0, 1.0]], [0, 2])


def test_predict_probabilities_matches_manual_sigmoid() -> None:
    coefficients = (0.1, -0.2, 0.3)
    rows = [[1.0, 2.0, -1.0], [1.0, 0.0, 0.0]]
    predicted = predict_probabilities(rows, coefficients)
    expected = [sigmoid(0.1 + -0.2 * 2.0 + 0.3 * -1.0), sigmoid(0.1)]
    assert predicted == pytest.approx(expected)


def test_platt_calibration_improves_a_badly_scaled_score() -> None:
    # True model uses a much larger coefficient than the "raw" score below,
    # so the raw score is badly miscalibrated (underconfident) but still
    # perfectly rank-correlated with the truth; Platt scaling should fix the
    # scale and materially reduce Brier score.
    true_coefficients = (0.0, 3.0)
    rng = random.Random(999)
    raw_logits = [rng.uniform(-1.0, 1.0) for _ in range(5000)]
    outcomes = [
        1 if rng.random() < sigmoid(true_coefficients[1] * raw) else 0 for raw in raw_logits
    ]
    calibration = fit_platt_calibration(raw_logits, outcomes)
    calibrated = apply_platt_calibration(raw_logits, calibration)
    uncalibrated = [sigmoid(raw) for raw in raw_logits]
    assert brier_score(calibrated, outcomes) < brier_score(uncalibrated, outcomes)


def test_brier_score_known_cases() -> None:
    assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0)


def test_brier_score_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        brier_score([], [])


def test_mean_log_loss_known_case() -> None:
    assert mean_log_loss([0.5, 0.5], [1, 0]) == pytest.approx(-math.log(0.5))


def test_mean_log_loss_penalizes_confident_wrong_predictions_more() -> None:
    confident_wrong = mean_log_loss([0.01], [1])
    unsure = mean_log_loss([0.5], [1])
    assert confident_wrong > unsure


def test_rank_auc_perfect_separation() -> None:
    probabilities = [0.1, 0.2, 0.8, 0.9]
    outcomes = [0, 0, 1, 1]
    assert rank_auc(probabilities, outcomes) == pytest.approx(1.0)


def test_rank_auc_perfect_reversal() -> None:
    probabilities = [0.9, 0.8, 0.2, 0.1]
    outcomes = [0, 0, 1, 1]
    assert rank_auc(probabilities, outcomes) == pytest.approx(0.0)


def test_rank_auc_ties_score_as_half() -> None:
    assert rank_auc([0.5, 0.5], [0, 1]) == pytest.approx(0.5)


def test_rank_auc_undefined_without_both_classes() -> None:
    assert rank_auc([0.1, 0.2, 0.3], [0, 0, 0]) is None
    assert rank_auc([0.1, 0.2, 0.3], [1, 1, 1]) is None


def test_reliability_table_bins_cover_every_observation() -> None:
    rng = random.Random(7)
    probabilities = [rng.random() for _ in range(1000)]
    outcomes = [1 if rng.random() < p else 0 for p in probabilities]
    table = reliability_table(probabilities, outcomes, n_bins=10)
    assert sum(entry.count for entry in table) == 1000


def test_reliability_table_well_calibrated_predictions_match_observed() -> None:
    rng = random.Random(11)
    probabilities = [rng.random() for _ in range(20_000)]
    outcomes = [1 if rng.random() < p else 0 for p in probabilities]
    table = reliability_table(probabilities, outcomes, n_bins=10)
    for entry in table:
        assert entry.observed_rate == pytest.approx(entry.mean_predicted, abs=0.05)
