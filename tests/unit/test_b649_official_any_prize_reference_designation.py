"""Focused authority and scope checks for the B649 reference designation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import tools.generate_b649_official_any_prize_reference_designation as mod


def _serialized(designation: dict[str, Any]) -> bytes:
    return (json.dumps(designation, indent=2, sort_keys=True).rstrip("\n") + "\n").encode("utf-8")


def test_generator_reproduces_exact_designation_and_report_bytes() -> None:
    designation = mod.build_designation()

    assert json.loads((mod.REPO_ROOT / mod.OUTPUT_PATH).read_text(encoding="utf-8")) == designation
    assert (mod.REPO_ROOT / mod.OUTPUT_PATH).read_bytes() == _serialized(designation)
    assert (mod.REPO_ROOT / mod.REPORT_PATH).read_text(encoding="utf-8") == mod.render_report(
        designation
    )


@pytest.mark.parametrize(
    "mapping_name",
    ["RESEARCH_SOURCE_HASHES", "EVIDENCE_FILE_HASHES"],
)
def test_every_pinned_artifact_hash_is_load_bearing(
    monkeypatch: pytest.MonkeyPatch, mapping_name: str
) -> None:
    mapping = getattr(mod, mapping_name)
    path = next(iter(mapping))
    monkeypatch.setitem(mapping, path, "0" * 64)

    with pytest.raises(ValueError, match=mod.STOP_TOKEN):
        mod.build_designation()


def test_wrong_reference_e_seed_hash_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(mod.REFERENCE_E_SEED_HASHES, 10, "0" * 64)

    with pytest.raises(ValueError, match=mod.STOP_TOKEN):
        mod.build_designation()


@pytest.mark.parametrize(
    "artifact_path, expected_hash",
    [
        (mod.PHASE9_RESULT_PATH, mod.PHASE9_RESULT_SHA256),
        (mod.PHASE10_RESULT_PATH, mod.PHASE10_RESULT_SHA256),
    ],
)
def test_wrong_phase_result_hash_fails_closed(
    monkeypatch: pytest.MonkeyPatch, artifact_path: Path, expected_hash: str
) -> None:
    assert mod.RESEARCH_SOURCE_HASHES[artifact_path] == expected_hash
    monkeypatch.setitem(mod.RESEARCH_SOURCE_HASHES, artifact_path, "0" * 64)

    with pytest.raises(ValueError, match=mod.STOP_TOKEN):
        mod.build_designation()


def test_wrong_terminal_hash_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(mod.TERMINAL_PORTFOLIO_HASHES, 20, "0" * 64)

    with pytest.raises(ValueError, match=mod.STOP_TOKEN):
        mod.build_designation()


@pytest.mark.parametrize(
    "field, wrong_value",
    [
        ("reference_official_any_prize_count", 0),
        ("reference_official_any_prize_q", "0/1"),
    ],
)
def test_wrong_official_count_or_fraction_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str, wrong_value: object
) -> None:
    monkeypatch.setitem(mod.EXPECTED_OFFICIAL_ROWS[10], field, wrong_value)

    with pytest.raises(ValueError, match=mod.STOP_TOKEN):
        mod.build_designation()


def test_scope_and_exclusions_are_exact() -> None:
    designation = mod.build_designation()
    assert designation["scope"] == "BIG_LOTTO K10/K15/K20 only"
    assert designation["scope_detail"]["superseded_k"] == [10, 15, 20]
    assert designation["scope_detail"]["not_superseded_k"] == [1, 2, 3, 5]
    assert designation["scope_detail"]["other_lotteries_not_superseded"] == ["T539", "P638"]
    assert set(designation["per_k"]) == {"10", "15", "20"}


def test_method_objective_and_decision_metric_are_separate() -> None:
    designation = mod.build_designation()
    assert designation["reference_method_id"] == "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
    assert designation["seed_policy"] == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    assert designation["reference_method_version"] == "V1"
    assert designation["optimization_objective"] == "M3_PLUS_EXACT_COVERAGE"
    assert designation["reference_primary_decision_metric"] == "OFFICIAL_ANY_PRIZE"
    assert designation["postcheck_objective"] == "OFFICIAL_ANY_PRIZE_EXACT"
    assert designation["objective_split"]["optimization_metric"] == "M3_PLUS"
    assert (
        designation["objective_split"]["optimization_did_not_optimize_official_any_prize_directly"]
        is True
    )


def test_status_boundaries_and_no_new_strategy() -> None:
    designation = mod.build_designation()
    assert designation["global_optimum_status"] == "UNKNOWN"
    assert designation["known_frontier"] == "NO"
    assert designation["reference_comparator"] == "YES"
    assert designation["runtime_promotion"] == "NOT_AUTHORIZED"
    assert designation["production_promotion"] == "NOT_AUTHORIZED"
    assert designation["predictive_signal_claim"] == "NO"
    assert designation["historical_oos_claim"] == "NO"
    assert designation["expected_payout_claim"] == "NO"
    assert designation["strategy_id_created"] == "NO"


def test_hash_conventions_and_load_bearing_tie_break_are_recorded() -> None:
    designation = mod.build_designation()
    conventions = designation["hash_conventions"]
    assert conventions["reference_e_seed"] == "constructor-order compact JSON"
    assert conventions["terminal_portfolio"] == "sorted compact JSON"
    assert designation["per_k"]["10"]["first_step_max_ties"] == 1
    assert designation["per_k"]["15"]["first_step_max_ties"] == 40
    assert designation["per_k"]["20"]["first_step_max_ties"] == 1
    assert [
        designation["per_k"][str(k)]["combined_accepted_moves_from_reference_e"]
        for k in (10, 15, 20)
    ] == [1, 22, 28]


def test_official_any_prize_outcomes_and_terminal_hashes_reconcile() -> None:
    designation = mod.build_designation()
    expected = {
        10: (176219120, 176291360, 72240, mod.TERMINAL_PORTFOLIO_HASHES[10]),
        15: (248523240, 250028100, 1504860, mod.TERMINAL_PORTFOLIO_HASHES[15]),
        20: (311373272, 312463830, 1090558, mod.TERMINAL_PORTFOLIO_HASHES[20]),
    }
    for k, values in expected.items():
        official = designation["per_k"][str(k)]["official_any_prize"]
        assert (
            official["reference_official_any_prize_count"],
            official["terminal_official_any_prize_count"],
            official["official_outcome_count_delta"],
            official["terminal_portfolio_sha256"],
        ) == values


def test_canonicalized_manifest_and_logical_verifier_mapping_are_explicit() -> None:
    designation = mod.build_designation()
    evidence = designation["evidence"]
    manifest_path = mod.REPO_ROOT / mod.EVIDENCE_MANIFEST_PATH
    stored_verifier = mod.REPO_ROOT / Path(evidence["logical_to_stored"]["verifier.py"])

    assert set(evidence["manifest_entries"]) == {
        "inputs.json",
        "official_any_prize_postcheck.json",
        "verifier.py",
    }
    assert evidence["manifest_entries"]["verifier.py"] == mod.MANIFEST_ENTRIES["verifier.py"]
    assert stored_verifier.name == "verifier-source.txt"
    assert stored_verifier.suffix != ".py"
    assert (
        hashlib.sha256(stored_verifier.read_bytes()).hexdigest()
        == evidence["manifest_entries"]["verifier.py"]
    )
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == evidence["manifest_sha256"]
    assert evidence["verifier_bytes"] == "PRESERVED_EXACTLY"
