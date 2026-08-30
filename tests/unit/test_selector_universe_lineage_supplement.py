"""Focused tests for the selector-universe lineage supplement."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from tools import build_selector_universe_lineage_supplement as supplement

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECTOR_WORKTREE = (
    REPO_ROOT.parents[2]
    / ".worktrees/MathStatisticalAnalysis/STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_R1"
)
SELECTOR_RESULT = (
    SELECTOR_WORKTREE
    / "docs/research/matrix-native-results/"
    "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
)


def _result() -> dict[str, Any]:
    return supplement.build_result(REPO_ROOT, SELECTOR_RESULT)


def test_authority_qualified_composite_key_is_exact() -> None:
    key = supplement.authority_qualified_key("A", "P638", "same", "v1")
    assert key == ("A", "P638", "same", "v1")
    assert key != supplement.authority_qualified_key("B", "T539", "same", "v1")


def test_raw_id_cross_authority_collision_stays_two_identities() -> None:
    result = _result()
    keys = [
        tuple(row["authority_qualified_identity_key"])
        for row in result["qualified_selector_identities"]  # type: ignore[index]
        if row["strategy_id"] == "midfreq_fourier_2bet"
    ]
    assert len(keys) == 2
    assert {key[1] for key in keys} == {"P638", "T539"}
    assert result["invariants"]["raw_label_collision_is_two_identities"] is True  # type: ignore[index]


def test_exact_p638_source_resolution_and_status() -> None:
    result = _result()
    rows = [
        row
        for row in result["supplement_rows"]  # type: ignore[index]
        if row["lottery_id"] == "P638"
    ]
    assert len(rows) == 56
    assert all(row["resolution_status"] == "RESOLVED_REPLAY_BINDING" for row in rows)
    assert all(
        str(row["implementation_path"]).startswith(
            "src/lottolab/strategies/adapters/powerlotto_wave"
        )
        for row in rows
    )


def test_exact_t539_source_resolution_and_r2_correction() -> None:
    result = _result()
    rows = [
        row
        for row in result["supplement_rows"]  # type: ignore[index]
        if row["lottery_id"] == "T539"
    ]
    assert len(rows) == 54
    assert all(row["resolution_status"] == "RESOLVED_REPLAY_BINDING" for row in rows)
    r2 = [row for row in rows if "t539_r2_source_pin_correction" in row]
    assert len(r2) == 35
    assert all(
        row["t539_r2_source_pin_correction"]["first_definition_commit"]  # type: ignore[index]
        == supplement.T539_R2_FIRST_SOURCE_COMMIT
        for row in r2
    )


def test_t539_b2ce6a3_source_is_rejected() -> None:
    with pytest.raises(supplement.SourceAuthorityConflict):
        supplement.validate_t539_r2_source_pin("b2ce6a3")


def test_t539_c159da43_is_the_r2_source_authority() -> None:
    supplement.validate_t539_r2_source_pin(supplement.T539_R2_FIRST_SOURCE_COMMIT)


def test_donor_provenance_is_not_an_identity_alias() -> None:
    result = _result()
    row = next(
        row
        for row in result["supplement_rows"]  # type: ignore[index]
        if row["strategy_id"] == "power_biglotto_random_core_satellite_3bet"
    )
    assert row["strategy_id"] != row["donor_provenance_references"].get("donor_strategy_id")  # type: ignore[union-attr]
    assert row["donor_provenance_references"]["donor_identity_alias"] is False  # type: ignore[index]


def test_two_and_three_donor_ports_remain_distinct_replay_identities() -> None:
    result = _result()
    ids = {
        row["strategy_id"]
        for row in result["supplement_rows"]  # type: ignore[index]
        if row["strategy_id"] in {
            "power_biglotto_p0_echo_2bet",
            "power_biglotto_random_zone_split_3bet",
        }
    }
    assert ids == {"power_biglotto_p0_echo_2bet", "power_biglotto_random_zone_split_3bet"}


def test_deterministic_binding_fingerprint_and_exact_census() -> None:
    first = _result()
    second = _result()
    first_bytes = supplement.canonical_json_bytes(first)
    second_bytes = supplement.canonical_json_bytes(second)
    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()
    assert first["census"] == {
        "by_lottery": {
            "B649": {"production_exact_joins": 15, "selected": 15, "supplement_rows": 0},
            "P638": {"production_exact_joins": 9, "selected": 65, "supplement_rows": 56},
            "T539": {"production_exact_joins": 1, "selected": 55, "supplement_rows": 54},
        },
        "production_exact_joins": 25,
        "qualified_selector_identities": 135,
        "raw_selector_labels": 134,
        "supplement_rows": 110,
    }


def test_exact_combined_accounting_and_no_alias() -> None:
    result = _result()
    assert result["combined_accounting"] == {
        "accounted_identities": 135,
        "accounting_is_complete": True,
        "production_exact_joins": 25,
        "qualified_selector_identities": 135,
        "supplement_rows": 110,
    }
    assert result["invariants"]["safe_production_alias_mapping"] == "NO"  # type: ignore[index]


def test_unresolved_source_fails_closed() -> None:
    original = supplement.P638_SPEC_PATHS
    supplement.P638_SPEC_PATHS = (Path("src/lottolab/strategies/adapters/missing.py"),)  # type: ignore[misc]
    try:
        with pytest.raises(supplement.UnresolvedSource):
            supplement.build_result(REPO_ROOT, SELECTOR_RESULT)
    finally:
        supplement.P638_SPEC_PATHS = original  # type: ignore[misc]


def test_checked_in_artifacts_match_fresh_generation() -> None:
    result = supplement.build_result(REPO_ROOT)
    result_bytes = supplement.canonical_json_bytes(result)
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    report = supplement.render_markdown(result, result_sha256, len(result_bytes))
    assert (REPO_ROOT / supplement.OUTPUT_PATH).read_bytes() == result_bytes
    assert (REPO_ROOT / supplement.REPORT_PATH).read_text(encoding="utf-8") == report
