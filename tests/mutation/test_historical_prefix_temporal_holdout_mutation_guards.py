"""Mutation-sensitive guards for the fixed temporal feature-cohort holdout."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
MODELS = ROOT / "src/lottolab/application/historical_prefix_success_windows.py"
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


def test_guard_prior_only_assignment_sequence_is_built_once_and_reused() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    assignment = source.split("def _build_walk_forward_assignments(", 1)[1].split(
        "def _feature_cohorts_from_assignments(", 1
    )[0]
    holdout = source.split("def _temporal_holdout(", 1)[1].split(
        "def _recent_50_stability_audit(", 1
    )[0]

    assert "prior_observations=observations[:index]" in assignment
    assert assignment.index("_snapshot_feature_key(") < assignment.index(
        "_current_target_succeeded("
    )
    assert "chronological_index=index" in assignment
    assert holdout.count("_build_walk_forward_assignments(") == 1
    assert holdout.count("_feature_cohorts_from_assignments(") == 2
    assert "load_source(" not in holdout


def test_guard_fixed_split_cannot_shift_shorten_overlap_or_fallback() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    holdout = source.split("def _temporal_holdout(", 1)[1].split(
        "def _recent_50_stability_audit(", 1
    )[0]
    models = MODELS.read_text(encoding="utf-8")

    assert "total_count - REQUIRED_LABELED_TARGET_COUNT" in holdout
    assert "total_count - CONFIRMATION_TARGET_COUNT" in holdout
    assert "assignments[warmup_count:discovery_end]" in holdout
    assert "assignments[discovery_end:]" in holdout
    assert "len(discovery_assignments) != DISCOVERY_TARGET_COUNT" in holdout
    assert "len(confirmation_assignments) != CONFIRMATION_TARGET_COUNT" in holdout
    assert "discovery_assignments[-1].chronological_index" in holdout
    assert ">= confirmation_assignments[0].chronological_index" in holdout
    assert 'DISCOVERY_TARGET_COUNT = 750' in models
    assert 'CONFIRMATION_TARGET_COUNT = 300' in models
    assert 'REQUIRED_LABELED_TARGET_COUNT = 1050' in models
    assert "percentage" not in holdout.casefold()
    assert "fallback" not in holdout.casefold()


def test_guard_not_ready_never_runs_partial_inference() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    holdout = source.split("def _temporal_holdout(", 1)[1].split(
        "warmup_count = total_count - REQUIRED_LABELED_TARGET_COUNT",
        1,
    )[0]

    assert "total_count < REQUIRED_LABELED_TARGET_COUNT" in holdout
    assert "warmup_count=total_count" in holdout
    assert "discovery_count=0" in holdout
    assert "confirmation_count=0" in holdout
    assert "discovery=None" in holdout
    assert "confirmation=None" in holdout
    assert "comparisons=()" in holdout
    assert "_feature_cohort_diagnostics(" not in holdout


def test_guard_two_separate_64_families_and_all_canonical_comparisons() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    holdout = source.split("def _temporal_holdout(", 1)[1].split(
        "def _recent_50_stability_audit(", 1
    )[0]

    assert holdout.count("_feature_cohort_diagnostics(") == 2
    assert "zip(discovery.diagnostics, confirmation.diagnostics, strict=True)" in holdout
    assert "len(comparisons) != 64" in holdout
    assert "comparison.feature_key != comparison.discovery_diagnostic.feature_key" in holdout
    assert "comparison.feature_key != comparison.confirmation_diagnostic.feature_key" in holdout
    assert "128" not in holdout
    assert "p_value" not in holdout


def test_guard_exact_effect_change_neutral_relationship_and_single_route() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    effect = source.split("def _effect_change(", 1)[1].split(
        "def _temporal_relationship(", 1
    )[0]

    assert "Fraction(" in effect
    assert ") - Fraction(" in effect
    assert "confirmation.numerator" in effect
    assert "discovery.numerator" in effect
    assert "SAME_HIGHER" in source
    assert "SAME_EQUAL" in source
    assert "SAME_LOWER" in source
    assert "DIFFERENT" in source
    assert "UNAVAILABLE" in source
    assert api.count("/feature-cohorts/temporal-holdout") == 1
    assert 'operation_id="getHistoricalPrefixStrategyFeatureCohortTemporalHoldout"' in api
