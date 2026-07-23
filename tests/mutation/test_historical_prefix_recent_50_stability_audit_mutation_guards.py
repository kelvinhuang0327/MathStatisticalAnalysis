"""Mutation-sensitive guards for the fixed recent-50 feature-cohort audit."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
MODELS = ROOT / "src/lottolab/application/historical_prefix_success_windows.py"
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


def _audit_source() -> str:
    return USE_CASE.read_text(encoding="utf-8").split(
        "def _recent_50_stability_audit(", 1
    )[1].split("def _cross_import_pair_status(", 1)[0]


def _entrypoint_source() -> str:
    return USE_CASE.read_text(encoding="utf-8").split(
        "def get_feature_cohort_recent_50_stability_audit(", 1
    )[1].split("def get_cross_import_concordance(", 1)[0]


def test_guard_one_reader_load_assignment_sequence_and_temporal_reuse() -> None:
    audit = _audit_source()
    entrypoint = _entrypoint_source()

    assert entrypoint.count("self._load(import_identity_sha256)") == 1
    assert entrypoint.count("_find_exact_strategy(") == 1
    assert entrypoint.count("_build_walk_forward_assignments(") == 1
    assert entrypoint.count("_recent_50_stability_audit(") == 1
    assert audit.count("_temporal_holdout(") == 1
    assert "_build_walk_forward_assignments(" not in audit
    assert "load_source(" not in audit


def test_guard_closed_250_50_split_is_exact_disjoint_and_chronological() -> None:
    audit = _audit_source()
    models = MODELS.read_text(encoding="utf-8")

    assert "RECENT_REFERENCE_TARGET_COUNT = 250" in models
    assert "RECENT_AUDIT_TARGET_COUNT = 50" in models
    assert (
        'RECENT_AUDIT_SPLIT_METHOD = "FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT"'
        in models
    )
    assert "total_count - CONFIRMATION_TARGET_COUNT" in audit
    assert "total_count - RECENT_AUDIT_TARGET_COUNT" in audit
    assert "assignments[confirmation_start:recent_start]" in audit
    assert "assignments[recent_start:]" in audit
    assert "reference_assignments + recent_assignments != confirmation_assignments" in audit
    assert "set(reference_assignments).intersection(recent_assignments)" in audit
    assert "reference_assignments[-1].chronological_index" in audit
    assert ">= recent_assignments[0].chronological_index" in audit
    assert "percentage" not in audit.casefold()
    assert "fallback" not in audit.casefold()


def test_guard_sparse_cohorts_two_separate_64_families_and_recent_minus_reference() -> None:
    audit = _audit_source()

    assert audit.count("_feature_cohort_diagnostics(") == 2
    assert audit.count("_feature_cohorts_from_assignments(") == 2
    assert "assignments=reference_assignments" in audit
    assert "assignments=recent_assignments" in audit
    assert "zip(reference.diagnostics, recent.diagnostics, strict=True)" in audit
    assert "len(comparisons) != 64" in audit
    assert "reference_diagnostic.risk_difference," in audit
    assert "recent_diagnostic.risk_difference," in audit
    assert "128" not in audit
    assert ".sort(" not in audit


def test_guard_not_ready_has_no_partial_diagnostics_and_one_get_route() -> None:
    audit = _audit_source().split("total_count = len(assignments)", 1)[0]
    api = API.read_text(encoding="utf-8")

    assert "reference_count=0" in audit
    assert "recent_count=0" in audit
    assert "reference=None" in audit
    assert "recent=None" in audit
    assert "comparisons=()" in audit
    assert api.count("recent-50-stability-audit") == 1
    assert (
        'operation_id="getHistoricalPrefixStrategyFeatureCohortRecent50StabilityAudit"'
        in api
    )
