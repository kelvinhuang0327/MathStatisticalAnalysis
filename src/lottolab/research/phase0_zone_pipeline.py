"""H04-conditional per-zone pipeline: fold split -> fit -> calibrate -> evaluate -> baselines.

Implements `docs/research/phase0-h04-conditional-preregistration.md` §6-9
for one zone. Lottery-agnostic: operates on `ZoneObservation` tuples, not on
any database or lottery-specific structure.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from lottolab.research.conditional_probability_model import (
    ReliabilityBin,
    apply_platt_calibration,
    brier_score,
    fit_logistic_regression,
    fit_platt_calibration,
    mean_log_loss,
    rank_auc,
    reliability_table,
    sigmoid,
)
from lottolab.research.conditional_state_features import ZoneObservation

N_FOLDS = 5
EVALUATION_FOLDS: tuple[int, ...] = (3, 4, 5)
BASELINE_NAMES: tuple[str, ...] = (
    "NO_SKILL_UNIFORM",
    "CAUSAL_MARGINAL_EMPIRICAL",
    "UNCALIBRATED_CONDITIONAL",
    "CALIBRATED_CONDITIONAL",
)


def _fold_assignment(min_index: int, max_index: int, n_folds: int) -> dict[int, int]:
    """Map each draw_index in [min_index, max_index] to a 1-indexed fold number."""

    total = max_index - min_index + 1
    assignment: dict[int, int] = {}
    for fold in range(1, n_folds + 1):
        start = min_index + round((fold - 1) * total / n_folds)
        end = min_index + round(fold * total / n_folds)
        for index in range(start, end):
            assignment[index] = fold
    return assignment


def _design_row(observation: ZoneObservation) -> list[float]:
    return [1.0, float(observation.was_in_previous_draw), float(observation.last_seen_gap)]


@dataclass(frozen=True, slots=True)
class FoldDiagnostics:
    evaluation_fold: int
    n_train_draws: int
    n_calibration_draws: int
    n_evaluation_draws: int
    base_coefficients: tuple[float, ...]
    base_converged: bool
    calibration_coefficients: tuple[float, ...]
    calibration_converged: bool


@dataclass(frozen=True, slots=True)
class BaselineScores:
    name: str
    n: int
    mean_predicted: float
    brier: float
    log_loss: float
    auc: float | None


@dataclass(frozen=True, slots=True)
class ZonePipelineResult:
    zone_label: str
    pool_size: int
    zone_draw_size: int
    n_draws_total: int
    n_observations_total: int
    fold_diagnostics: tuple[FoldDiagnostics, ...]
    baseline_scores: tuple[BaselineScores, ...]
    reliability: tuple[ReliabilityBin, ...]
    primary_endpoint_brier_delta_vs_marginal: float
    secondary_endpoint_brier_delta_vs_no_skill: float
    secondary_endpoint_brier_delta_vs_uncalibrated: float
    secondary_endpoint_log_loss_delta_vs_marginal: float


def run_zone_pipeline(
    observations: tuple[ZoneObservation, ...],
    *,
    pool_size: int,
    zone_draw_size: int,
    zone_label: str,
) -> ZonePipelineResult:
    if not observations:
        raise ValueError("observations must be non-empty")

    by_draw_index: dict[int, list[ZoneObservation]] = defaultdict(list)
    for observation in observations:
        by_draw_index[observation.draw_index].append(observation)
    all_draw_indices = sorted(by_draw_index)
    fold_of = _fold_assignment(all_draw_indices[0], all_draw_indices[-1], N_FOLDS)

    pooled_predictions: dict[str, list[float]] = {name: [] for name in BASELINE_NAMES}
    pooled_outcomes: dict[str, list[int]] = {name: [] for name in BASELINE_NAMES}
    fold_diagnostics: list[FoldDiagnostics] = []

    for evaluation_fold in EVALUATION_FOLDS:
        training_folds = set(range(1, (evaluation_fold - 2) + 1))
        calibration_fold = evaluation_fold - 1

        training_obs = [
            observation
            for draw_index in all_draw_indices
            if fold_of[draw_index] in training_folds
            for observation in by_draw_index[draw_index]
        ]
        calibration_obs = [
            observation
            for draw_index in all_draw_indices
            if fold_of[draw_index] == calibration_fold
            for observation in by_draw_index[draw_index]
        ]
        evaluation_obs = [
            observation
            for draw_index in all_draw_indices
            if fold_of[draw_index] == evaluation_fold
            for observation in by_draw_index[draw_index]
        ]
        if not training_obs or not calibration_obs or not evaluation_obs:
            raise ValueError(
                f"fold {evaluation_fold}: training/calibration/evaluation set is empty "
                "-- the draw history is too short for this fold schedule"
            )

        base_fit = fit_logistic_regression(
            [_design_row(o) for o in training_obs], [o.outcome for o in training_obs]
        )

        calibration_raw_logits = [
            sum(c * v for c, v in zip(base_fit.coefficients, _design_row(o), strict=True))
            for o in calibration_obs
        ]
        platt_fit = fit_platt_calibration(
            calibration_raw_logits, [o.outcome for o in calibration_obs]
        )

        evaluation_raw_logits = [
            sum(c * v for c, v in zip(base_fit.coefficients, _design_row(o), strict=True))
            for o in evaluation_obs
        ]
        uncalibrated_probs = [sigmoid(value) for value in evaluation_raw_logits]
        calibrated_probs = apply_platt_calibration(evaluation_raw_logits, platt_fit)
        evaluation_outcomes = [o.outcome for o in evaluation_obs]

        no_skill_prob = zone_draw_size / pool_size
        no_skill_probs = [no_skill_prob] * len(evaluation_obs)

        n_train_draws = len({o.draw_index for o in training_obs})
        if n_train_draws == 0:
            raise ValueError(f"fold {evaluation_fold}: zero distinct training draws")
        training_hit_counts = Counter(o.number for o in training_obs if o.outcome == 1)
        marginal_rate = {
            number: training_hit_counts.get(number, 0) / n_train_draws
            for number in range(1, pool_size + 1)
        }
        marginal_probs = [marginal_rate[o.number] for o in evaluation_obs]

        for name, predictions in (
            ("NO_SKILL_UNIFORM", no_skill_probs),
            ("CAUSAL_MARGINAL_EMPIRICAL", marginal_probs),
            ("UNCALIBRATED_CONDITIONAL", uncalibrated_probs),
            ("CALIBRATED_CONDITIONAL", calibrated_probs),
        ):
            pooled_predictions[name].extend(predictions)
            pooled_outcomes[name].extend(evaluation_outcomes)

        fold_diagnostics.append(
            FoldDiagnostics(
                evaluation_fold=evaluation_fold,
                n_train_draws=n_train_draws,
                n_calibration_draws=len({o.draw_index for o in calibration_obs}),
                n_evaluation_draws=len({o.draw_index for o in evaluation_obs}),
                base_coefficients=base_fit.coefficients,
                base_converged=base_fit.converged,
                calibration_coefficients=platt_fit.coefficients,
                calibration_converged=platt_fit.converged,
            )
        )

    baseline_scores = tuple(
        BaselineScores(
            name=name,
            n=len(pooled_outcomes[name]),
            mean_predicted=sum(pooled_predictions[name]) / len(pooled_predictions[name]),
            brier=brier_score(pooled_predictions[name], pooled_outcomes[name]),
            log_loss=mean_log_loss(pooled_predictions[name], pooled_outcomes[name]),
            auc=rank_auc(pooled_predictions[name], pooled_outcomes[name]),
        )
        for name in BASELINE_NAMES
    )
    scores_by_name = {score.name: score for score in baseline_scores}

    return ZonePipelineResult(
        zone_label=zone_label,
        pool_size=pool_size,
        zone_draw_size=zone_draw_size,
        n_draws_total=len(all_draw_indices) + 1,  # +1 restores the excluded position 0
        n_observations_total=len(observations),
        fold_diagnostics=tuple(fold_diagnostics),
        baseline_scores=baseline_scores,
        reliability=reliability_table(
            pooled_predictions["CALIBRATED_CONDITIONAL"], pooled_outcomes["CALIBRATED_CONDITIONAL"]
        ),
        primary_endpoint_brier_delta_vs_marginal=(
            scores_by_name["CALIBRATED_CONDITIONAL"].brier
            - scores_by_name["CAUSAL_MARGINAL_EMPIRICAL"].brier
        ),
        secondary_endpoint_brier_delta_vs_no_skill=(
            scores_by_name["CALIBRATED_CONDITIONAL"].brier
            - scores_by_name["NO_SKILL_UNIFORM"].brier
        ),
        secondary_endpoint_brier_delta_vs_uncalibrated=(
            scores_by_name["CALIBRATED_CONDITIONAL"].brier
            - scores_by_name["UNCALIBRATED_CONDITIONAL"].brier
        ),
        secondary_endpoint_log_loss_delta_vs_marginal=(
            scores_by_name["CALIBRATED_CONDITIONAL"].log_loss
            - scores_by_name["CAUSAL_MARGINAL_EMPIRICAL"].log_loss
        ),
    )
