"""Focused report-rendering checks for the frozen model comparison."""

from __future__ import annotations

from tools.run_b649_official_win_marginal_coverage_r1 import render_report


def test_report_renders_k10_readiness_from_the_result_gate() -> None:
    payload: dict[str, object] = {
        "k10": {
            "row_count": 1,
            "unique_candidate_pool_count": 1,
            "baseline_exact_mean_probability": "1/4",
            "selector_exact_mean_probability": "13/50",
            "exact_delta": "1/100",
            "material_relative_gain_threshold": "1/100",
            "ready_for_branch2_oos": "YES",
        },
        "k20": {"status": "SKIPPED_FORCED_SELECTION"},
        "authorities": {
            "sealed_input_locator": "sealed-input.json",
            "sealed_input_sha256": "input-sha",
            "candidate_pool_archive_sha256": "pool-sha",
            "min_overlap_k10_archive_sha256": "baseline-sha",
            "selector_k10_archive_sha256": "selector-sha",
            "baseline_result_sha256": "result-sha",
            "evaluator_content_sha256": "evaluator-sha",
            "branch2_upstream_commit": "commit-id",
            "branch2_upstream_tree": "tree-id",
        },
    }

    report = render_report(payload)

    assert "**YES**" in report
    assert "SKIPPED_FORCED_SELECTION" in report
    assert "1/4 (0.25000000)" in report
    assert "13/50 (0.26000000)" in report
    assert "1/100 (+0.01000000)" in report
