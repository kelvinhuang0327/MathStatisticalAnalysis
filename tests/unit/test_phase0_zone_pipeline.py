from __future__ import annotations

import random

import pytest

from lottolab.research.conditional_state_features import compute_zone_observations
from lottolab.research.phase0_zone_pipeline import (
    BASELINE_NAMES,
    EVALUATION_FOLDS,
    run_zone_pipeline,
)

POOL_SIZE = 49
DRAW_SIZE = 6
N_DRAWS = 3000


def _generate_draws_with_repeat_bias(
    pool_size: int, draw_size: int, n_draws: int, p_repeat_bias: float, seed: int
) -> list[frozenset[int]]:
    """Test-only synthetic draw generator with a controllable, known repeat signal.

    Each number in the previous draw is independently re-included with
    probability `p_repeat_bias`; remaining slots fill uniformly at random.
    `p_repeat_bias=0` degenerates to plain uniform, independent draws (the
    true null). Independent per-number weighting (rather than forcing a
    single slot) avoids an artificial dilution ceiling on the achievable
    signal strength.
    """

    rng = random.Random(seed)
    draws: list[frozenset[int]] = []
    previous: frozenset[int] = frozenset()
    for _ in range(n_draws):
        forced = {number for number in previous if rng.random() < p_repeat_bias}
        if len(forced) > draw_size:
            forced = set(rng.sample(sorted(forced), draw_size))
        remaining_pool = [n for n in range(1, pool_size + 1) if n not in forced]
        fill_count = draw_size - len(forced)
        filled: set[int] = set(rng.sample(remaining_pool, fill_count)) if fill_count > 0 else set()
        current = frozenset(forced | filled)
        draws.append(current)
        previous = current
    return draws


def test_pipeline_structure_has_exactly_the_frozen_folds_and_baselines() -> None:
    draws = _generate_draws_with_repeat_bias(POOL_SIZE, DRAW_SIZE, N_DRAWS, 0.0, seed=1)
    observations = compute_zone_observations(draws, pool_size=POOL_SIZE)
    result = run_zone_pipeline(
        observations, pool_size=POOL_SIZE, zone_draw_size=DRAW_SIZE, zone_label="test_zone"
    )
    assert [fold.evaluation_fold for fold in result.fold_diagnostics] == list(EVALUATION_FOLDS)
    assert {score.name for score in result.baseline_scores} == set(BASELINE_NAMES)


def test_reliability_table_covers_every_calibrated_prediction() -> None:
    draws = _generate_draws_with_repeat_bias(POOL_SIZE, DRAW_SIZE, N_DRAWS, 0.0, seed=1)
    observations = compute_zone_observations(draws, pool_size=POOL_SIZE)
    result = run_zone_pipeline(
        observations, pool_size=POOL_SIZE, zone_draw_size=DRAW_SIZE, zone_label="test_zone"
    )
    calibrated = next(s for s in result.baseline_scores if s.name == "CALIBRATED_CONDITIONAL")
    assert sum(entry.count for entry in result.reliability) == calibrated.n


def test_pipeline_rejects_empty_observations() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        run_zone_pipeline((), pool_size=49, zone_draw_size=6, zone_label="empty")


def test_pipeline_detects_an_injected_repeat_signal() -> None:
    # Each previous-draw number independently has a 40% chance of repeating
    # -- a strong, unambiguous signal chosen so the test has comfortable
    # margin above pure-noise AUC (~0.5 at this sample size).
    draws = _generate_draws_with_repeat_bias(POOL_SIZE, DRAW_SIZE, N_DRAWS, 0.4, seed=2)
    observations = compute_zone_observations(draws, pool_size=POOL_SIZE)
    result = run_zone_pipeline(
        observations, pool_size=POOL_SIZE, zone_draw_size=DRAW_SIZE, zone_label="signal_zone"
    )
    calibrated = next(s for s in result.baseline_scores if s.name == "CALIBRATED_CONDITIONAL")
    assert result.primary_endpoint_brier_delta_vs_marginal < 0.0
    assert calibrated.auc is not None
    assert calibrated.auc > 0.65
    # the fitted coefficient on was_in_previous_draw should be clearly positive
    # in every fold, since the injected signal is exactly that feature.
    assert all(fold.base_coefficients[1] > 0.5 for fold in result.fold_diagnostics)


def test_pipeline_shows_no_improvement_under_the_true_null() -> None:
    draws = _generate_draws_with_repeat_bias(POOL_SIZE, DRAW_SIZE, N_DRAWS, 0.0, seed=3)
    observations = compute_zone_observations(draws, pool_size=POOL_SIZE)
    result = run_zone_pipeline(
        observations, pool_size=POOL_SIZE, zone_draw_size=DRAW_SIZE, zone_label="null_zone"
    )
    calibrated = next(s for s in result.baseline_scores if s.name == "CALIBRATED_CONDITIONAL")
    assert calibrated.auc is not None
    assert 0.45 < calibrated.auc < 0.55


def test_pipeline_raises_on_too_short_a_history_for_the_fold_schedule() -> None:
    draws = _generate_draws_with_repeat_bias(POOL_SIZE, DRAW_SIZE, 5, 0.0, seed=4)
    observations = compute_zone_observations(draws, pool_size=POOL_SIZE)
    with pytest.raises(ValueError):
        run_zone_pipeline(
            observations, pool_size=POOL_SIZE, zone_draw_size=DRAW_SIZE, zone_label="too_short"
        )
