"""Verification of the Strategy Matrix Phase 7 reference designation.

Independently re-reads the pinned canonical source commit (not via the
generator module's own `load_source`/`_read_pinned_blob` helpers) and
cross-checks the designation's required fields against it, so a bug in the
generator's own gating would fail this test even though the generator would
happily produce an internally-consistent-but-wrong designation. Reads no
historical draw or outcome data and performs no new enumeration.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from tools.generate_strategy_matrix_phase7_reference_designation import (
    DESIGNATION_ID,
    IN_SCOPE_K,
    NOT_ESTABLISHED,
    OUTPUT_PATH,
    REFERENCE_DESIGNATION_STATUS,
    REPO_ROOT,
    REQUIRED_CLASSIFICATION,
    REQUIRED_RECOMMENDATION,
    RUNTIME_PROMOTION,
    SOURCE_COMMIT,
    SOURCE_PATH,
    SOURCE_SYNTHESIS_ID,
    TIE_ONLY_K,
    build_designation,
)

REPORT_PATH = (
    Path("docs/research/matrix-native-results")
    / "strategy-matrix-phase7-reference-designation-v1-report.md"
)


@pytest.fixture(scope="module")
def designation() -> dict[str, Any]:
    return build_designation()


def _independent_read(commit: str, path: Path) -> dict[str, Any]:
    """Bypasses the module's own `_read_pinned_blob`/`load_source` entirely."""
    show_cmd = ["git", "show", f"{commit}:{path.as_posix()}"]
    proc = subprocess.run(show_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        subprocess.run(
            ["git", "fetch", "--depth=1", "origin", commit],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        proc = subprocess.run(show_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"cannot read pinned canonical blob {commit}:{path} -- "
        f"tried fetching {commit} from origin and it still failed. stderr: {proc.stderr}"
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def raw_source() -> dict[str, Any]:
    return _independent_read(SOURCE_COMMIT, SOURCE_PATH)


def test_determinism_two_independent_builds_are_identical() -> None:
    first = build_designation()
    second = build_designation()
    assert first == second


def test_source_commit_is_full_sha1_and_is_the_files_only_commit(
    raw_source: dict[str, Any],
) -> None:
    assert len(SOURCE_COMMIT) == 40
    assert all(c in "0123456789abcdef" for c in SOURCE_COMMIT)
    log = subprocess.run(
        ["git", "log", "--format=%H", "--follow", "--", SOURCE_PATH.as_posix()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    commits = [line for line in log.stdout.splitlines() if line]
    assert commits == [SOURCE_COMMIT], (
        "expected the pinned commit to be the source file's only commit; got "
        f"{commits!r}"
    )
    assert raw_source["synthesis_id"] == SOURCE_SYNTHESIS_ID


def test_canonical_synthesis_identity(
    designation: dict[str, Any], raw_source: dict[str, Any]
) -> None:
    src = designation["source_synthesis"]
    assert src["synthesis_id"] == raw_source["synthesis_id"] == SOURCE_SYNTHESIS_ID
    assert src["source_commit"] == SOURCE_COMMIT
    assert src["source_result_path"] == str(SOURCE_PATH)
    assert designation["designation_id"] == DESIGNATION_ID


def test_promotion_decision_identity(
    designation: dict[str, Any], raw_source: dict[str, Any]
) -> None:
    verified = designation["source_synthesis"]["verified"]
    assert verified["synthesis_classification"] == raw_source["synthesis_classification"]
    assert verified["synthesis_classification"] == REQUIRED_CLASSIFICATION
    assert (
        verified["reference_promotion_recommendation"]
        == raw_source["reference_promotion_assessment"]["recommendation"]
    )
    assert verified["reference_promotion_recommendation"] == REQUIRED_RECOMMENDATION
    assert verified["global_optimum_status"] == raw_source["global_optimum_status"] == "UNKNOWN"
    assert raw_source["reference_promotion_assessment"]["not_a_global_optimum_claim"] is True


def test_required_top_level_statuses(designation: dict[str, Any]) -> None:
    assert REFERENCE_DESIGNATION_STATUS == "METHOD_E_IS_NEXT_RESEARCH_REFERENCE_IN_SCOPE"
    assert designation["reference_designation_status"] == REFERENCE_DESIGNATION_STATUS
    assert designation["runtime_promotion"] == RUNTIME_PROMOTION == "NOT_AUTHORIZED"
    assert designation["global_optimum_status"] == "UNKNOWN"
    assert designation["constructor_id"] == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    assert designation["next_task"] == "MATRIX_PHASE7_REFERENCE_DESIGNATION_CANONICALIZE_PUBLISH_R1"


def test_effective_scope_is_k_gte_10_only(designation: dict[str, Any]) -> None:
    scope = designation["effective_scope"]
    assert scope["k_ladder_in_scope"] == IN_SCOPE_K == [10, 15, 20]
    assert set(scope["structures_in_scope"]) == {
        "STRUCTURE_A_B649",
        "STRUCTURE_B_T539",
        "STRUCTURE_C_P638_ZONE1",
    }
    assert set(scope["domains_in_scope"]) == {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO_ZONE1"}
    conditions = scope["conditions_all_must_hold"]
    for key in (
        "primary_tested_coverage_event",
        "k_gte_10",
        "domain_compatible_with_sealed_evidence",
        "method_e_applicable_unchanged",
    ):
        assert key in conditions
        assert isinstance(conditions[key], str) and conditions[key]
    assert "M3_PLUS" in scope["recommendation_scope_as_sealed"]


def test_excluded_scope_k_1_3_5_is_tie_only_not_a_replacement(designation: dict[str, Any]) -> None:
    excluded = designation["excluded_scope"]
    assert TIE_ONLY_K == [1, 3, 5]
    k135 = excluded["k_1_3_5"]
    assert k135["k"] == TIE_ONLY_K
    assert k135["status"] == "TIE_ONLY_DOES_NOT_TRIGGER_REPLACEMENT"
    assert k135["reference_status"] == NOT_ESTABLISHED == "NOT_ESTABLISHED_BY_THIS_DESIGNATION"


def test_excluded_scope_untested_items_are_not_established(designation: dict[str, Any]) -> None:
    excluded = designation["excluded_scope"]
    for key in ("k_beyond_20", "p638_zone2", "any_4th_structure", "incompatible_domains"):
        assert excluded[key] == "NOT_ESTABLISHED_BY_THIS_DESIGNATION"
    for key in ("predictive_advantage", "profitability", "prize_economic_value"):
        assert excluded["untested_objectives"][key] == "NOT_ESTABLISHED_BY_THIS_DESIGNATION"
    assert excluded["extrapolation_policy"] == "DO_NOT_EXTRAPOLATE"


def test_prior_reference_is_not_replaced(designation: dict[str, Any]) -> None:
    prior = designation["prior_reference_treatment"]
    assert prior["status"] == "HISTORICAL_SEALED_COMPARATOR"
    assert prior["replaced_by_this_designation"] is False


def test_claim_boundary_excludes_runtime_and_profitability_claims(
    designation: dict[str, Any],
) -> None:
    claim = designation["claim_boundary"]
    for key in (
        "production_default",
        "prediction_method",
        "runtime_strategy",
        "profitability_claim",
        "universal_portability",
        "global_optimum",
    ):
        assert claim[key] == "NOT_CLAIMED"


def test_no_new_science(designation: dict[str, Any]) -> None:
    no_new_science = designation["no_new_science"]
    for key in (
        "reran_a_b_c",
        "regenerated_portfolios",
        "changed_method_e",
        "tuned_parameters",
        "new_matrix_native_result_cell",
        "altered_prior_sealed_artifacts",
        "inspected_outcome_or_history_data",
    ):
        assert no_new_science[key] == "NO"


def test_mismatched_source_field_stops_the_designation(
    monkeypatch: pytest.MonkeyPatch, raw_source: dict[str, Any]
) -> None:
    import tools.generate_strategy_matrix_phase7_reference_designation as mod

    tampered = dict(raw_source)
    tampered["synthesis_classification"] = "NOT_SUPPORTED_ACROSS_3_NATIVE_STRUCTURES"

    def _fake_read(commit: str, path: Path) -> str:
        return json.dumps(tampered)

    monkeypatch.setattr(mod, "_read_pinned_blob", _fake_read)
    with pytest.raises(ValueError, match="STOP_REFERENCE_DESIGNATION_AUTHORITY_UNRESOLVED"):
        mod.load_source()


def test_result_json_matches_generated_designation_and_report_contains_required_strings(
    designation: dict[str, Any],
) -> None:
    assert json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) == designation

    report = REPORT_PATH.read_text(encoding="utf-8")
    for required in (
        "METHOD_E_IS_NEXT_RESEARCH_REFERENCE_IN_SCOPE",
        "RUNTIME_PROMOTION:             NOT_AUTHORIZED",
        "GLOBAL_OPTIMUM_STATUS:         UNKNOWN",
        "PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR",
        "NOT_ESTABLISHED_BY_THIS_DESIGNATION",
        "TIE_ONLY_DOES_NOT_TRIGGER_REPLACEMENT",
        SOURCE_COMMIT,
    ):
        assert required in report
    assert report.rstrip().endswith(
        "Do not push, open a PR, or start\n"
        "`MATRIX_PHASE7_REFERENCE_DESIGNATION_CANONICALIZE_PUBLISH_R1` in this task."
    )
