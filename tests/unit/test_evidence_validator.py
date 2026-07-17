"""Semantic-validator adversarial tests (hashes, dataset, causality, tickets,
outcomes, metrics, and authority/trust — Contract Part 10, layer 3).

Tests that only need Pydantic-level rejection live in
``test_evidence_models_schema.py``; everything here builds a document that
parses successfully and then checks what the semantic validator finds.
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.evidence import canonical_json, validator
from lottolab.evidence.models import (
    DatasetSnapshot,
    EvidenceStatus,
    FindingCategory,
    HashVerificationState,
    StrategyEvaluationEvidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

HASH_A = "a" * 64
OID_A = "c" * 40

RULE_PARAMETERS_DRAFT = {
    "main_number_count": 6,
    "main_number_min": 1,
    "main_number_max": 49,
    "main_numbers_unique": True,
    "special_number_count": 1,
    "special_number_min": 1,
    "special_number_max": 49,
    "special_numbers_unique": True,
    "main_special_overlap_allowed": False,
    "rule_contract_version": "2026-07-16.1",
    "rule_parameters_sha256": "0" * 64,
}

DrawTuple = tuple[str, int, str, tuple[int, ...], tuple[int, ...]]

DRAWS: list[DrawTuple] = [
    ("D0", 0, "2020-01-01", (1, 2, 3, 4, 5, 6), (7,)),
    ("D1", 1, "2020-01-02", (2, 3, 4, 5, 6, 7), (8,)),
    ("D2", 2, "2020-01-03", (3, 4, 5, 6, 7, 8), (9,)),
    ("D3", 3, "2020-01-04", (4, 5, 6, 7, 8, 9), (10,)),
]
DRAWS_BY_ID: dict[str, tuple[int, str, tuple[int, ...], tuple[int, ...]]] = {
    draw_id: (seq, date, main, special) for draw_id, seq, date, main, special in DRAWS
}


def _with_self_hash(draft: dict[str, Any], key: str) -> dict[str, Any]:
    return {**draft, key: canonical_json.self_key_removed_sha256(draft, key)}


def _rehash_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    rehashed = copy.deepcopy(evidence)
    rehashed["records"] = [
        _with_self_hash(record, "record_sha256") for record in rehashed["records"]
    ]
    return _with_self_hash(rehashed, "artifact_content_sha256")


def _rule_parameters() -> dict[str, Any]:
    return _with_self_hash(RULE_PARAMETERS_DRAFT, "rule_parameters_sha256")


def _draw_ref(draw_id: str) -> dict[str, Any]:
    seq, date, _main, _special = DRAWS_BY_ID[draw_id]
    return {"draw_id": draw_id, "draw_sequence": seq, "draw_date": date}


def _dataset_dict() -> dict[str, Any]:
    draft = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": "SYNTHETIC_VALIDATOR_TEST_DATASET",
        "dataset_version": "1.0.0",
        "lottery_type": "BIG_LOTTO",
        "rule_binding": _rule_parameters(),
        "source_provenance": {
            "kind": "SYNTHETIC",
            "declared_description": "validator test fixture",
        },
        "draws": [
            {
                "draw_id": draw_id,
                "draw_sequence": seq,
                "draw_date": date,
                "main_numbers": list(main),
                "special_numbers": list(special),
            }
            for draw_id, seq, date, main, special in DRAWS
        ],
        "dataset_sha256": "0" * 64,
    }
    return _with_self_hash(draft, "dataset_sha256")


def _make_ticket(
    ticket_id: str, main: tuple[int, ...], special: tuple[int, ...], target_draw_id: str
) -> dict[str, Any]:
    _seq, _date, actual_main, actual_special = DRAWS_BY_ID[target_draw_id]
    main_hit_count = len(set(main) & set(actual_main))
    overlap = len(set(special) & set(actual_special))
    special_hit = overlap > 0 if len(special) <= 1 else overlap
    return {
        "ticket_id": ticket_id,
        "main_numbers": list(main),
        "special_numbers": list(special),
        "main_hit_count": main_hit_count,
        "special_hit": special_hit,
    }


def _make_record(
    target_draw_id: str, cutoff_draw_id: str, tickets: list[dict[str, Any]]
) -> dict[str, Any]:
    _seq, _date, actual_main, actual_special = DRAWS_BY_ID[target_draw_id]
    draft = {
        "target": _draw_ref(target_draw_id),
        "cutoff": _draw_ref(cutoff_draw_id),
        "tickets": tickets,
        "actual_main_numbers": list(actual_main),
        "actual_special_numbers": list(actual_special),
        "outcome_source": "DATASET_SNAPSHOT",
        "record_sha256": "0" * 64,
    }
    return _with_self_hash(draft, "record_sha256")


def _write_definition(repo_root: Path, relative_path: str, definition: dict[str, Any]) -> str:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json.canonical_file_bytes(definition))
    return canonical_json.sha256_hex(path.read_bytes())


def _write_hit_rate_definition(
    repo_root: Path,
    *,
    sample_unit: str = "TICKETS",
    aggregation: str = "MEAN",
) -> tuple[str, str]:
    relative_path = "contracts/evidence/metric_definition_hit_rate.json"
    definition = {
        "schema_id": "lottolab.evidence.metric_definition",
        "schema_version": "1.0.0",
        "metric_id": "HIT_RATE_MAIN",
        "metric_version": "v1",
        "direction": "HIGHER_IS_BETTER",
        "unit": "RATIO",
        "aggregation": aggregation,
        "sample_unit": sample_unit,
        "decimal_scale": 4,
        "rounding_mode": "ROUND_HALF_EVEN",
        "formula_status": "DEFINED",
        "definition_prose": "validator test metric",
    }
    return relative_path, _write_definition(repo_root, relative_path, definition)


def _write_d3_definition(repo_root: Path) -> tuple[str, str]:
    relative_path = "contracts/evidence/d3_test_copy.json"
    definition = {
        "schema_id": "lottolab.evidence.metric_definition",
        "schema_version": "1.0.0",
        "metric_id": "D3",
        "metric_version": "v1",
        "direction": "DESCRIPTIVE_ONLY",
        "unit": "UNITLESS",
        "aggregation": "NONE",
        "sample_unit": "DRAWS",
        "decimal_scale": 4,
        "rounding_mode": "ROUND_HALF_EVEN",
        "formula_status": "RESERVED_UNAVAILABLE",
        "definition_prose": "reserved test copy",
    }
    return relative_path, _write_definition(repo_root, relative_path, definition)


def _evidence_dict(repo_root: Path, feature_path: str, feature_sha256: str) -> dict[str, Any]:
    tickets0 = [_make_ticket("T0", (1, 2, 3, 4, 5, 6), (7,), "D2")]
    tickets1 = [_make_ticket("T1", (4, 5, 6, 7, 8, 9), (10,), "D3")]
    records = [
        _make_record("D2", "D1", tickets0),
        _make_record("D3", "D2", tickets1),
    ]
    parameters = {"window": 2}
    parameters_sha256 = canonical_json.sha256_hex(canonical_json.canonical_bytes(parameters))

    draft = {
        "schema_id": "lottolab.evidence.strategy_evaluation_evidence",
        "schema_version": "1.0.0",
        "artifact_id": "SYNTHETIC_VALIDATOR_TEST_EVIDENCE",
        "evidence_status": "SYNTHETIC_TEST_ONLY",
        "produced_at": "2026-01-01T00:00:00Z",
        "producer_name": "validator-test",
        "artifact_content_sha256": "0" * 64,
        "strategy_id": "validator_test_strategy",
        "strategy_version": "v1",
        "method_id": "validator_test_method",
        "method_version": "v1",
        "method_source_git_oid": OID_A,
        "feature_version": "v1",
        "feature_definition_path": feature_path,
        "feature_definition_sha256": feature_sha256,
        "parameters": parameters,
        "parameters_sha256": parameters_sha256,
        "dataset_reference": {
            "dataset_id": "SYNTHETIC_VALIDATOR_TEST_DATASET",
            "dataset_version": "1.0.0",
            "dataset_sha256": "PLACEHOLDER",
            "lottery_type": "BIG_LOTTO",
            "draw_count": len(DRAWS),
            "first_draw": _draw_ref("D0"),
            "last_draw": _draw_ref("D3"),
        },
        "rule_parameters": _rule_parameters(),
        "evaluation_mode": "EX_ANTE",
        "evaluation_protocol": "WALK_FORWARD",
        "evaluation_windows": {
            "evaluation_window": {"start_sequence": 2, "end_sequence": 3},
            "training_window": {"start_sequence": 0, "end_sequence": 0},
            "parameter_selection_mode": "FIXED",
            "parameter_selection_window": {"start_sequence": 0, "end_sequence": 0},
            "minimum_history": 1,
            "missing_draw_policy": "STRICT_NONE_TOLERATED",
            "duplicate_draw_policy": "STRICT_NONE_TOLERATED",
            "maximum_data_cutoff": _draw_ref("D2"),
            "walk_forward_cutoff_lag": 1,
        },
        "records": records,
        "metric_results": [],
    }
    return draft


def _build_valid_pair(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """A dataset + evidence pair that validates completely clean."""

    dataset = _dataset_dict()
    feature_path, feature_sha256 = _write_hit_rate_definition(tmp_path)
    evidence = _evidence_dict(tmp_path, feature_path, feature_sha256)
    evidence["dataset_reference"]["dataset_sha256"] = dataset["dataset_sha256"]
    evidence = _with_self_hash(evidence, "artifact_content_sha256")
    return dataset, evidence, tmp_path


def _rehash_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    return _with_self_hash(
        {**copy.deepcopy(dataset), "dataset_sha256": "0" * 64},
        "dataset_sha256",
    )


def _bind_evidence_to_dataset(
    evidence: dict[str, Any],
    dataset: dict[str, Any],
    *,
    evidence_status: str | None = None,
) -> dict[str, Any]:
    rebound = copy.deepcopy(evidence)
    rebound["dataset_reference"]["dataset_id"] = dataset["dataset_id"]
    rebound["dataset_reference"]["dataset_version"] = dataset["dataset_version"]
    rebound["dataset_reference"]["dataset_sha256"] = dataset["dataset_sha256"]
    if evidence_status is not None:
        rebound["evidence_status"] = evidence_status
        rebound["artifact_id"] = (
            "SYNTHETIC_VALIDATOR_TEST_EVIDENCE"
            if evidence_status == "SYNTHETIC_TEST_ONLY"
            else "VALIDATOR_TEST_EVIDENCE"
        )
    return _rehash_evidence(rebound)


def _with_local_provenance(
    dataset: dict[str, Any],
    evidence: dict[str, Any],
    *,
    source_path: str,
    source_git_oid: str,
    source_file_sha256: str,
    evidence_status: str = "CANONICAL",
) -> tuple[dict[str, Any], dict[str, Any]]:
    rebound_dataset = copy.deepcopy(dataset)
    rebound_dataset["dataset_id"] = "VALIDATOR_LOCAL_COMMITTED_DATASET"
    rebound_dataset["source_provenance"] = {
        "kind": "LOCAL_COMMITTED_FILE",
        "source_definition_path": source_path,
        "source_git_oid": source_git_oid,
        "source_file_sha256": source_file_sha256,
        "declared_description": "task-owned temporary Git provenance fixture",
    }
    rebound_dataset = _rehash_dataset(rebound_dataset)
    rebound_evidence = _bind_evidence_to_dataset(
        evidence,
        rebound_dataset,
        evidence_status=evidence_status,
    )
    return rebound_dataset, rebound_evidence


def _with_external_provenance(
    dataset: dict[str, Any], evidence: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    rebound_dataset = copy.deepcopy(dataset)
    rebound_dataset["dataset_id"] = "VALIDATOR_EXTERNAL_DECLARED_DATASET"
    rebound_dataset["source_provenance"] = {
        "kind": "EXTERNAL_DECLARED",
        "declared_description": "task-owned unverified external declaration",
    }
    rebound_dataset = _rehash_dataset(rebound_dataset)
    rebound_evidence = _bind_evidence_to_dataset(
        evidence,
        rebound_dataset,
        evidence_status="CANONICAL",
    )
    return rebound_dataset, rebound_evidence


def _git(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def _observe_git_repository(repo_root: Path) -> tuple[bytes, ...]:
    return (
        _git(repo_root, "rev-parse", "HEAD"),
        _git(repo_root, "diff", "--binary"),
        _git(repo_root, "diff", "--cached", "--binary"),
        _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all"),
        _git(repo_root, "show-ref"),
        _git(repo_root, "config", "--local", "--list"),
    )


def _git_info_path(repo_root: Path, filename: str) -> Path:
    git_dir_output = _git(repo_root, "rev-parse", "--git-dir").decode("utf-8")
    git_dir = Path(git_dir_output)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    info_path = git_dir / "objects" / "info" / filename
    info_path.parent.mkdir(parents=True, exist_ok=True)
    return info_path


def _run_validator_read_only_git(
    repo_root: Path, *args: str
) -> subprocess.CompletedProcess[bytes] | None:
    runner = cast(
        Callable[..., subprocess.CompletedProcess[bytes] | None],
        vars(validator)["_run_read_only_git"],
    )
    return runner(repo_root, *args)


def _build_local_committed_pair(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], Path, str, bytes]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "LottoLab validator test")
    _git(repo_root, "config", "user.email", "validator-test@example.invalid")

    dataset, evidence, _ = _build_valid_pair(repo_root)
    source_path = "contracts/evidence/task_owned_source.json"
    source_bytes = b'{"fixture":"task-owned-synthetic-source-v1"}\n'
    source_file = repo_root / source_path
    source_file.write_bytes(source_bytes)
    _git(repo_root, "add", "--", "contracts/evidence")
    _git(repo_root, "commit", "-q", "-m", "task-owned provenance fixture")
    source_git_oid = _git(repo_root, "rev-parse", "HEAD").decode("ascii")
    assert len(source_git_oid) == 40
    source_file_sha256 = canonical_json.sha256_hex(source_bytes)

    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=source_git_oid,
        source_file_sha256=source_file_sha256,
    )
    return dataset, evidence, repo_root, source_path, source_bytes


def _validate(
    evidence_dict: dict[str, Any], dataset_dict: dict[str, Any], repo_root: Path
) -> validator.ValidationReport:
    evidence_model = StrategyEvaluationEvidence.model_validate(evidence_dict)
    dataset_model = DatasetSnapshot.model_validate(dataset_dict)
    return validator.validate_evidence_artifact(
        evidence_model, repo_root=repo_root, dataset=dataset_model
    )


def _codes(report: validator.ValidationReport) -> set[str]:
    return {finding.code for finding in report.findings}


# --------------------------------------------------------------------------
# Sanitized malformed input
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b'{"secret":"RAW_INPUT_MUST_NOT_LEAK",',
        b'\xff{"secret":"RAW_BYTES_MUST_NOT_LEAK"}',
    ],
    ids=("malformed-json", "invalid-utf8"),
)
def test_load_evidence_returns_one_sanitized_schema_finding(
    tmp_path: Path, payload: bytes
):
    evidence_path = tmp_path / "malformed-evidence.json"
    evidence_path.write_bytes(payload)

    evidence, findings = validator.load_evidence(evidence_path)

    assert evidence is None
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category is FindingCategory.SCHEMA_FAILURE
    assert finding.code == "EVIDENCE_NOT_LCJ1"
    assert finding.message == "$: input is not valid UTF-8 JSON"
    assert "RAW_INPUT_MUST_NOT_LEAK" not in finding.message
    assert "RAW_BYTES_MUST_NOT_LEAK" not in finding.message
    assert str(evidence_path) not in finding.message


def test_cli_malformed_json_fails_without_traceback_or_input_disclosure(tmp_path: Path):
    sensitive_absolute_marker = "/SENSITIVE/PROTECTED/ABSOLUTE/PATH"
    raw_marker = "RAW_INVALID_INPUT_MUST_NOT_LEAK"
    evidence_path = tmp_path / "malformed-evidence.json"
    evidence_path.write_bytes(
        f'{{"secret":"{sensitive_absolute_marker}","raw":"{raw_marker}",'.encode()
    )
    data_dir = tmp_path / "nonexistent-data"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/validate_evaluation_evidence.py"),
            str(evidence_path),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "LOTTOLAB_DATA_DIR": str(data_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 1
    assert "EVIDENCE_VALIDATION_FAILED" in output
    assert "EVIDENCE_NOT_LCJ1" in output
    assert "Traceback" not in output
    assert sensitive_absolute_marker not in output
    assert raw_marker not in output
    assert not data_dir.exists()


# --------------------------------------------------------------------------
# Baseline must be clean
# --------------------------------------------------------------------------


def test_valid_pair_is_completely_clean(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    report = _validate(evidence, dataset, repo_root)
    assert report.findings == ()
    assert report.structurally_valid is True
    assert report.trust_classification is not None
    assert report.trust_classification.value == "SYNTHETIC"
    assert report.canonical_gate_passed is False
    assert all(hc.state is HashVerificationState.VERIFIED_MATCH for hc in report.hash_checks)


# --------------------------------------------------------------------------
# Hashes
# --------------------------------------------------------------------------


def test_one_changed_digit_yields_hash_mismatch(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    original = evidence["artifact_content_sha256"]
    flipped = ("0" if original[0] != "0" else "1") + original[1:]
    evidence["artifact_content_sha256"] = flipped
    report = _validate(evidence, dataset, repo_root)
    assert "ARTIFACT_CONTENT_HASH_MISMATCH" in _codes(report)
    checks = {hc.pointer: hc.state for hc in report.hash_checks}
    assert checks["/artifact_content_sha256"] is HashVerificationState.VERIFIED_MISMATCH


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------


def test_duplicate_draw_id_rejected():
    dataset = _dataset_dict()
    dataset["draws"][1]["draw_id"] = dataset["draws"][0]["draw_id"]
    model = DatasetSnapshot.model_validate(dataset)
    findings, _ = validator.validate_dataset_snapshot(model)
    assert any(f.code == "DUPLICATE_DRAW_ID" for f in findings)


def test_sequence_gap_rejected():
    dataset = _dataset_dict()
    dataset["draws"][2]["draw_sequence"] = 5
    model = DatasetSnapshot.model_validate(dataset)
    findings, _ = validator.validate_dataset_snapshot(model)
    assert any(f.code == "DRAW_SEQUENCE_NOT_CONTIGUOUS" for f in findings)


def test_wrong_number_ordering_rejected():
    dataset = _dataset_dict()
    dataset["draws"][0]["main_numbers"] = [6, 5, 4, 3, 2, 1]
    model = DatasetSnapshot.model_validate(dataset)
    findings, _ = validator.validate_dataset_snapshot(model)
    assert any(f.code == "MAIN_NUMBERS_NOT_ASCENDING" for f in findings)


def test_evidence_validation_recomputes_supplied_dataset_intrinsic_hashes(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)

    report = _validate(evidence, dataset, repo_root)

    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/dataset_sha256"]
        is HashVerificationState.VERIFIED_MATCH
    )
    assert (
        checks["/dataset_snapshot/rule_binding/rule_parameters_sha256"]
        is HashVerificationState.VERIFIED_MATCH
    )


def test_matching_fake_dataset_declarations_cannot_bypass_intrinsic_recomputation(
    tmp_path: Path,
):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset["source_provenance"]["declared_description"] = "changed without rehashing"
    assert evidence["dataset_reference"]["dataset_sha256"] == dataset["dataset_sha256"]

    report = _validate(evidence, dataset, repo_root)

    assert "DATASET_HASH_MISMATCH" in _codes(report)
    assert "DATASET_REFERENCE_HASH_MISMATCH" not in _codes(report)
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/dataset_sha256"]
        is HashVerificationState.VERIFIED_MISMATCH
    )
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_evidence_validation_recomputes_dataset_rule_binding_hash(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset["rule_binding"]["rule_parameters_sha256"] = HASH_A
    dataset = _rehash_dataset(dataset)
    evidence = _bind_evidence_to_dataset(evidence, dataset)

    report = _validate(evidence, dataset, repo_root)

    rule_findings = [
        finding
        for finding in report.findings
        if finding.code == "RULE_PARAMETERS_HASH_MISMATCH"
    ]
    assert rule_findings
    assert rule_findings[0].pointer == (
        "/dataset_snapshot/rule_binding/rule_parameters_sha256"
    )
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/rule_binding/rule_parameters_sha256"]
        is HashVerificationState.VERIFIED_MISMATCH
    )


def test_dataset_semantic_findings_are_integrated_with_prefixed_pointers(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset["draws"][2]["draw_sequence"] = 7
    dataset = _rehash_dataset(dataset)
    evidence = _bind_evidence_to_dataset(evidence, dataset)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding for finding in report.findings if finding.code == "DRAW_SEQUENCE_NOT_CONTIGUOUS"
    )
    assert finding.pointer == "/dataset_snapshot/draws/2/draw_sequence"
    assert report.structurally_valid is False


def test_dataset_schema_findings_are_prefixed_in_file_validation(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset.pop("dataset_id")
    evidence_path = tmp_path / "evidence.json"
    dataset_path = tmp_path / "dataset.json"
    evidence_path.write_bytes(canonical_json.canonical_file_bytes(evidence))
    dataset_path.write_bytes(canonical_json.canonical_file_bytes(dataset))

    report = validator.validate_evidence_file(
        evidence_path,
        repo_root=repo_root,
        dataset_path=dataset_path,
    )

    finding = next(
        finding for finding in report.findings if finding.code == "SCHEMA_VALIDATION_ERROR"
    )
    assert finding.pointer == "/dataset_snapshot/dataset_id"
    assert report.schema_valid is False
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_reference_draw_count_first_last_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["dataset_reference"]["draw_count"] = 999
    evidence["dataset_reference"]["first_draw"]["draw_id"] = "D3"
    evidence["dataset_reference"]["last_draw"]["draw_id"] = "D0"
    report = _validate(evidence, dataset, repo_root)
    codes = _codes(report)
    assert "DATASET_DRAW_COUNT_MISMATCH" in codes
    assert "DATASET_FIRST_DRAW_MISMATCH" in codes
    assert "DATASET_LAST_DRAW_MISMATCH" in codes


@pytest.mark.parametrize(
    ("boundary", "false_date", "expected_code"),
    [
        ("first_draw", "2020-01-02", "DATASET_FIRST_DRAW_MISMATCH"),
        ("last_draw", "2020-01-03", "DATASET_LAST_DRAW_MISMATCH"),
    ],
)
def test_reference_first_and_last_draw_date_mismatch_rejected(
    tmp_path: Path, boundary: str, false_date: str, expected_code: str
):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["dataset_reference"][boundary]["draw_date"] = false_date
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    assert expected_code in _codes(report)
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


@pytest.mark.parametrize(
    "fixture_name",
    ("evaluation_evidence.json", "historical_replay_evidence.json"),
)
def test_committed_synthetic_evidence_fixtures_have_zero_findings(fixture_name: str):
    fixture_root = REPO_ROOT / "tests/fixtures/evidence/synthetic"
    evidence, evidence_findings = validator.load_evidence(fixture_root / fixture_name)
    dataset, dataset_findings = validator.load_dataset_snapshot(
        fixture_root / "dataset_snapshot.json"
    )

    assert evidence is not None
    assert dataset is not None
    assert evidence_findings == []
    assert dataset_findings == []

    report = validator.validate_evidence_artifact(
        evidence,
        repo_root=REPO_ROOT,
        dataset=dataset,
    )
    assert report.findings == ()


# --------------------------------------------------------------------------
# Dataset provenance trust matrix
# --------------------------------------------------------------------------


def test_synthetic_dataset_with_synthetic_evidence_remains_valid_synthetic(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)

    report = _validate(evidence, dataset, repo_root)

    assert report.findings == ()
    assert report.trust_classification is not None
    assert report.trust_classification.value == "SYNTHETIC"
    assert report.canonical_gate_passed is False


def test_synthetic_dataset_with_draft_evidence_is_authority_blocked(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _bind_evidence_to_dataset(evidence, dataset, evidence_status="DRAFT")

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "SYNTHETIC_DATASET_REQUIRES_SYNTHETIC_EVIDENCE"
    )
    assert finding.category is FindingCategory.AUTHORITY_FAILURE
    assert report.canonical_gate_passed is False


def test_synthetic_dataset_with_canonical_evidence_is_authority_blocked(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _bind_evidence_to_dataset(evidence, dataset, evidence_status="CANONICAL")

    report = _validate(evidence, dataset, repo_root)

    assert "SYNTHETIC_DATASET_REQUIRES_SYNTHETIC_EVIDENCE" in _codes(report)
    assert report.trust_classification is not None
    assert report.trust_classification.value == "UNTRUSTED_DECLARED"
    assert report.canonical_gate_passed is False


def test_registry_injection_cannot_override_synthetic_dataset_incompatibility(
    tmp_path: Path,
):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _bind_evidence_to_dataset(evidence, dataset, evidence_status="CANONICAL")
    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert "SYNTHETIC_DATASET_REQUIRES_SYNTHETIC_EVIDENCE" in _codes(report)
    assert report.trust_classification is not None
    assert report.trust_classification.value != "REGISTERED_CANONICAL"
    assert report.canonical_gate_passed is False


def test_external_declared_dataset_is_always_unverified_but_can_be_structurally_valid(
    tmp_path: Path,
):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset, evidence = _with_external_provenance(dataset, evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_EXTERNAL_DECLARED_UNVERIFIED"
    )
    assert finding.category is FindingCategory.UNVERIFIED_PROVENANCE
    assert report.structurally_valid is True
    assert report.canonical_gate_passed is False


def test_registry_injection_cannot_make_external_declared_dataset_canonical(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    dataset, evidence = _with_external_provenance(dataset, evidence)
    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert "DATASET_EXTERNAL_DECLARED_UNVERIFIED" in _codes(report)
    assert report.trust_classification is not None
    assert report.trust_classification.value == "UNTRUSTED_DECLARED"
    assert report.canonical_gate_passed is False


def test_local_committed_file_exact_reachable_blob_hash_can_pass_provenance_gate(
    tmp_path: Path,
):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert report.findings == ()
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.VERIFIED_MATCH
    )
    assert report.trust_classification is not None
    assert report.trust_classification.value == "REGISTERED_CANONICAL"
    assert report.canonical_gate_passed is True


def test_local_source_git_oid_must_name_a_commit_object(tmp_path: Path):
    dataset, evidence, repo_root, source_path, source_bytes = _build_local_committed_pair(
        tmp_path
    )
    blob_oid = _git(repo_root, "hash-object", source_path).decode("ascii")
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=blob_oid,
        source_file_sha256=canonical_json.sha256_hex(source_bytes),
    )

    report = _validate(evidence, dataset, repo_root)

    assert "DATASET_SOURCE_GIT_OID_UNVERIFIED" in _codes(report)
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )


def test_local_source_git_oid_must_be_an_ancestor_of_head(tmp_path: Path):
    dataset, evidence, repo_root, source_path, source_bytes = _build_local_committed_pair(
        tmp_path
    )
    tree_oid = _git(repo_root, "write-tree").decode("ascii")
    unrelated_commit = _git(
        repo_root, "commit-tree", tree_oid, "-m", "unrelated task-owned commit"
    ).decode("ascii")
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=unrelated_commit,
        source_file_sha256=canonical_json.sha256_hex(source_bytes),
    )

    report = _validate(evidence, dataset, repo_root)

    assert "DATASET_SOURCE_GIT_OID_NOT_ANCESTOR" in _codes(report)
    assert report.canonical_gate_passed is False


def test_local_source_without_git_repository_remains_unverified(tmp_path: Path):
    repo_root = tmp_path / "plain-directory"
    dataset, evidence, _ = _build_valid_pair(repo_root)
    source_path = "contracts/evidence/task_owned_source.json"
    source_bytes = b'{"fixture":"not-in-git"}\n'
    (repo_root / source_path).write_bytes(source_bytes)
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=OID_A,
        source_file_sha256=canonical_json.sha256_hex(source_bytes),
    )

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_SOURCE_GIT_REPOSITORY_UNAVAILABLE"
    )
    assert finding.category is FindingCategory.UNVERIFIED_PROVENANCE
    assert report.canonical_gate_passed is False


def test_local_source_missing_historical_path_remains_unverified(tmp_path: Path):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    source_git_oid = _git(repo_root, "rev-parse", "HEAD").decode("ascii")
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path="contracts/evidence/missing_historical_source.json",
        source_git_oid=source_git_oid,
        source_file_sha256=HASH_A,
    )

    report = _validate(evidence, dataset, repo_root)

    assert "DATASET_SOURCE_BLOB_UNAVAILABLE" in _codes(report)
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )


def test_local_source_declared_sha_mismatch_is_verified_mismatch(tmp_path: Path):
    dataset, evidence, repo_root, source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    source_git_oid = _git(repo_root, "rev-parse", "HEAD").decode("ascii")
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=source_git_oid,
        source_file_sha256=HASH_A,
    )

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_SOURCE_FILE_HASH_MISMATCH"
    )
    assert finding.category is FindingCategory.HASH_MISMATCH
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.VERIFIED_MISMATCH
    )
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_local_source_uses_historical_blob_not_modified_worktree_bytes(tmp_path: Path):
    dataset, evidence, repo_root, source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    (repo_root / source_path).write_bytes(b'{"fixture":"modified-working-tree"}\n')
    status_before = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.VERIFIED_MATCH
    )
    assert report.canonical_gate_passed is True
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == status_before


def test_local_source_uses_declared_commit_a_when_head_b_changes_the_same_path(tmp_path: Path):
    dataset, evidence, repo_root, source_path, source_bytes_a = _build_local_committed_pair(
        tmp_path
    )
    commit_a = dataset["source_provenance"]["source_git_oid"]
    source_bytes_b = b'{"fixture":"task-owned-synthetic-source-v2"}\n'
    (repo_root / source_path).write_bytes(source_bytes_b)
    _git(repo_root, "add", "--", source_path)
    _git(repo_root, "commit", "-q", "-m", "descendant changes historical source")
    head_b = _git(repo_root, "rev-parse", "HEAD").decode("ascii")

    assert head_b != commit_a
    assert _git(repo_root, "show", f"{commit_a}:{source_path}") == source_bytes_a.strip()
    assert _git(repo_root, "show", f"{head_b}:{source_path}") == source_bytes_b.strip()

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.VERIFIED_MATCH
    )
    assert report.findings == ()
    assert report.canonical_gate_passed is True


def test_local_git_provenance_verification_does_not_mutate_repository_state(tmp_path: Path):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )

    before = _observe_git_repository(repo_root)
    report = _validate(evidence, dataset, repo_root)
    after = _observe_git_repository(repo_root)

    assert report.findings == ()
    assert after == before


def test_local_git_provenance_verification_creates_no_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    data_dir = tmp_path / "nonexistent-data"
    monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(data_dir))

    report = _validate(evidence, dataset, repo_root)

    assert report.findings == ()
    assert not data_dir.exists()


@pytest.mark.parametrize(
    "argv",
    [
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "--git-common-dir"),
        ("cat-file", "-t", OID_A),
        ("cat-file", "-t", f"{OID_A}:contracts/evidence/source.json"),
        ("cat-file", "blob", f"{OID_A}:contracts/evidence/source.json"),
        ("merge-base", "--is-ancestor", OID_A, "HEAD"),
    ],
)
def test_read_only_git_exact_argument_allowlist_accepts_only_required_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: tuple[str, ...],
):
    calls: list[list[str]] = []

    def recording_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert isinstance(args, list)
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(validator.subprocess, "run", recording_run)

    result = _run_validator_read_only_git(tmp_path, *argv)

    assert result is not None
    assert result.returncode == 0
    assert calls == [["git", "-C", str(tmp_path), *argv]]


@pytest.mark.parametrize(
    "argv",
    [
        (),
        ("status",),
        ("rev-parse", "--git-dir"),
        ("rev-parse", "--show-toplevel", "extra"),
        ("rev-parse", "--git-common-dir", "extra"),
        ("cat-file", "--filters", f"{OID_A}:contracts/evidence/source.json"),
        ("cat-file", "--textconv", f"{OID_A}:contracts/evidence/source.json"),
        ("cat-file", "--batch"),
        ("cat-file", "--batch-command"),
        ("cat-file", "-t", "HEAD"),
        ("cat-file", "-t", "--help"),
        ("cat-file", "-t", f"{OID_A}:contracts/evidence/../../outside"),
        ("cat-file", "blob", OID_A),
        ("merge-base", "--is-ancestor", OID_A, "HEAD", "extra"),
        ("merge-base", "--is-ancestor", OID_A, "main"),
        ("merge-base", "--is-ancestor", "HEAD", OID_A),
    ],
)
def test_read_only_git_rejects_malformed_arguments_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: tuple[str, ...],
):
    def forbidden_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("rejected Git argv must not reach subprocess.run")

    monkeypatch.setattr(validator.subprocess, "run", forbidden_run)

    with pytest.raises(ValueError, match="exact read-only allowlist"):
        _run_validator_read_only_git(tmp_path, *argv)


def test_local_git_provenance_commands_are_shell_free_read_only_and_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    real_run = subprocess.run
    calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "redirected-git-dir"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(tmp_path / "redirected-objects"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    monkeypatch.setenv("GIT_TRACE", str(tmp_path / "trace.log"))
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(tmp_path / "trace2-event.log"))
    monkeypatch.setenv("GIT_TRACE_PERFORMANCE", str(tmp_path / "trace-performance.log"))

    def recording_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert isinstance(args, list)
        calls.append((tuple(args), kwargs))
        return cast(subprocess.CompletedProcess[bytes], real_run(args, **kwargs))

    monkeypatch.setattr(validator.subprocess, "run", recording_run)

    report = _validate(evidence, dataset, repo_root)

    assert report.findings == ()
    assert calls
    forbidden = {
        "add",
        "checkout",
        "commit",
        "config",
        "fetch",
        "push",
        "reset",
        "switch",
        "update-index",
        "worktree",
    }
    source_oid = dataset["source_provenance"]["source_git_oid"]
    source_path = dataset["source_provenance"]["source_definition_path"]
    blob_spec = f"{source_oid}:{source_path}"
    approved_argv = {
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "--git-common-dir"),
        ("cat-file", "-t", source_oid),
        ("cat-file", "-t", blob_spec),
        ("cat-file", "blob", blob_spec),
        ("merge-base", "--is-ancestor", source_oid, "HEAD"),
    }
    for command, kwargs in calls:
        assert command[:2] == ("git", "-C")
        assert command[3:] in approved_argv
        assert forbidden.isdisjoint(command)
        assert kwargs["shell"] is False
        env = cast(dict[str, str], kwargs["env"])
        assert "GIT_CONFIG_COUNT" not in env
        assert "GIT_DIR" not in env
        assert "GIT_OBJECT_DIRECTORY" not in env
        assert not any(name.startswith("GIT_TRACE") for name in env)
        assert env["GIT_GRAFT_FILE"] == os.devnull
        assert env["GIT_NO_LAZY_FETCH"] == "1"
        assert env["GIT_NO_REPLACE_OBJECTS"] == "1"
        assert env["GIT_OPTIONAL_LOCKS"] == "0"
        assert env["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.parametrize(
    "trace_variable",
    ["GIT_TRACE", "GIT_TRACE2_EVENT", "GIT_TRACE_PERFORMANCE"],
)
def test_local_git_provenance_never_creates_inherited_trace_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    trace_variable: str,
):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    trace_dir = tmp_path / "task-owned-traces"
    trace_dir.mkdir()
    trace_path = trace_dir / f"{trace_variable.lower()}.log"
    before = _observe_git_repository(repo_root)
    monkeypatch.setenv(trace_variable, str(trace_path))

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert report.findings == ()
    assert report.canonical_gate_passed is True
    assert not trace_path.exists()
    monkeypatch.delenv(trace_variable)
    assert _observe_git_repository(repo_root) == before


def test_local_git_provenance_ignores_repository_graft_that_forges_ancestry(tmp_path: Path):
    dataset, evidence, repo_root, source_path, source_bytes = _build_local_committed_pair(
        tmp_path
    )
    head_oid = _git(repo_root, "rev-parse", "HEAD").decode("ascii")
    tree_oid = _git(repo_root, "write-tree").decode("ascii")
    unrelated_oid = _git(
        repo_root, "commit-tree", tree_oid, "-m", "unrelated task-owned graft object"
    ).decode("ascii")
    ordinary_before = subprocess.run(
        ["git", "merge-base", "--is-ancestor", unrelated_oid, "HEAD"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert ordinary_before.returncode == 1

    git_dir = repo_root / ".git"
    graft_file = git_dir / "info" / "grafts"
    graft_file.parent.mkdir(parents=True, exist_ok=True)
    graft_file.write_text(f"{head_oid} {unrelated_oid}\n", encoding="ascii")
    ordinary_with_graft = subprocess.run(
        ["git", "merge-base", "--is-ancestor", unrelated_oid, "HEAD"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert ordinary_with_graft.returncode == 0

    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=unrelated_oid,
        source_file_sha256=canonical_json.sha256_hex(source_bytes),
    )
    before = _observe_git_repository(repo_root)
    graft_before = graft_file.read_bytes()

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_SOURCE_GIT_OID_NOT_ANCESTOR"
    )
    assert finding.category is FindingCategory.UNVERIFIED_PROVENANCE
    assert report.canonical_gate_passed is False
    assert graft_file.read_bytes() == graft_before
    assert _observe_git_repository(repo_root) == before


def test_local_git_provenance_rejects_object_available_only_from_alternate_database(
    tmp_path: Path,
):
    primary_owner = tmp_path / "primary-owner"
    primary_owner.mkdir()
    _primary_dataset, _primary_evidence, primary_repo, _primary_path, _primary_bytes = (
        _build_local_committed_pair(primary_owner)
    )

    alternate_owner = tmp_path / "alternate-owner"
    alternate_owner.mkdir()
    dataset, evidence, alternate_repo, source_path, _source_bytes = _build_local_committed_pair(
        alternate_owner
    )
    hostile_bytes = b'{"fixture":"alternate-only-source"}\n'
    (alternate_repo / source_path).write_bytes(hostile_bytes)
    _git(alternate_repo, "add", "--", source_path)
    _git(alternate_repo, "commit", "-q", "-m", "alternate-only provenance object")
    hostile_oid = _git(alternate_repo, "rev-parse", "HEAD").decode("ascii")
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=source_path,
        source_git_oid=hostile_oid,
        source_file_sha256=canonical_json.sha256_hex(hostile_bytes),
    )

    primary_without_alternate = subprocess.run(
        ["git", "cat-file", "-t", hostile_oid],
        cwd=primary_repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert primary_without_alternate.returncode != 0

    alternates_file = _git_info_path(primary_repo, "alternates")
    alternates_file.write_text(str(alternate_repo / ".git" / "objects") + "\n", encoding="utf-8")
    assert _git(primary_repo, "cat-file", "-t", hostile_oid) == b"commit"
    alternates_before = alternates_file.read_bytes()
    before = _observe_git_repository(primary_repo)

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=primary_repo,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_SOURCE_ALTERNATE_OBJECT_DATABASE_UNSAFE"
    )
    assert finding.category is FindingCategory.UNVERIFIED_PROVENANCE
    assert str(primary_repo) not in finding.message
    assert str(alternate_repo) not in finding.message
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )
    assert report.canonical_gate_passed is False
    assert alternates_file.read_bytes() == alternates_before
    assert _observe_git_repository(primary_repo) == before


def test_local_git_provenance_accepts_empty_alternates_file(tmp_path: Path):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    alternates_file = _git_info_path(repo_root, "alternates")
    alternates_file.write_bytes(b"")

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert report.findings == ()
    assert report.canonical_gate_passed is True
    assert alternates_file.read_bytes() == b""


def test_local_git_provenance_supports_linked_worktree_common_directory(tmp_path: Path):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    linked_worktree = tmp_path / "linked-worktree"
    _git(repo_root, "worktree", "add", "--detach", str(linked_worktree), "HEAD")
    common_dir = _git(linked_worktree, "rev-parse", "--git-common-dir").decode("utf-8")
    assert Path(common_dir).is_absolute()
    assert Path(common_dir) != linked_worktree / ".git"

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=linked_worktree,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    assert report.findings == ()
    assert report.canonical_gate_passed is True


@pytest.mark.parametrize("unsafe_kind", ["malformed", "symlink", "unreadable", "http-entry"])
def test_local_git_provenance_fails_closed_on_unsafe_alternates_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_kind: str,
):
    dataset, evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    filename = "http-alternates" if unsafe_kind == "http-entry" else "alternates"
    configuration_file = _git_info_path(repo_root, filename)
    if unsafe_kind == "malformed":
        configuration_file.write_bytes(b"\xff\n")
    elif unsafe_kind == "symlink":
        symlink_target = tmp_path / "task-owned-empty-alternates"
        symlink_target.write_bytes(b"")
        configuration_file.symlink_to(symlink_target)
    elif unsafe_kind == "unreadable":
        configuration_file.write_bytes(b"")
        real_open = validator.os.open

        def denied_open(path: os.PathLike[str] | str, flags: int, *args: int) -> int:
            if Path(path) == configuration_file:
                raise PermissionError("task-owned simulated unreadable alternates")
            return real_open(path, flags, *args)

        monkeypatch.setattr(validator.os, "open", denied_open)
    else:
        configuration_file.write_text("https://example.invalid/objects\n", encoding="utf-8")

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DATASET_SOURCE_ALTERNATE_OBJECT_DATABASE_UNSAFE"
    )
    assert finding.category is FindingCategory.UNVERIFIED_PROVENANCE
    assert str(configuration_file) not in finding.message
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )
    assert report.canonical_gate_passed is False


@pytest.mark.parametrize(
    ("raw_path", "expected_code"),
    [
        ("docs/ownerinit.md", "DEFINITION_PATH_PROTECTED"),
        ("contracts/evidence/../../outside.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
        ("contracts/evidence/nul\x00source.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
        ("contracts/evidence/newline\nsource.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
        ("contracts/evidence/control\x01source.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
        ("contracts/evidence/tab\tsource.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
        ("contracts/evidence/del\x7fsource.json", "DEFINITION_PATH_LEXICALLY_INVALID"),
    ],
)
def test_local_provenance_rejects_paths_before_any_git_blob_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_path: str,
    expected_code: str,
):
    dataset, _evidence, repo_root, _source_path, _source_bytes = _build_local_committed_pair(
        tmp_path
    )
    dataset_model = DatasetSnapshot.model_validate(dataset)
    bad_provenance = dataset_model.source_provenance.model_copy(
        update={"source_definition_path": raw_path}
    )
    bad_dataset = dataset_model.model_copy(update={"source_provenance": bad_provenance})

    def forbidden_git(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("path rejection must happen before any Git query")

    monkeypatch.setattr(validator, "_run_read_only_git", forbidden_git)

    findings, hash_checks, unverified = validator.verify_dataset_provenance(
        bad_dataset,
        repo_root=repo_root,
        evidence_status=EvidenceStatus.CANONICAL,
    )

    assert {finding.code for finding in findings} == {expected_code}
    assert hash_checks == [
        validator.HashCheck(
            "/dataset_snapshot/source_provenance/source_file_sha256",
            HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT,
        )
    ]
    assert unverified is True


# --------------------------------------------------------------------------
# EX_ANTE causality
# --------------------------------------------------------------------------


def test_hindsight_target_sequence_lie_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    record = evidence["records"][0]
    record["target"] = {**_draw_ref("D1"), "draw_sequence": 2}
    record["cutoff"] = _draw_ref("D1")
    record["tickets"] = [
        _make_ticket("T0", (1, 2, 3, 4, 5, 6), (7,), "D1")
    ]
    _sequence, _date, actual_main, actual_special = DRAWS_BY_ID["D1"]
    record["actual_main_numbers"] = list(actual_main)
    record["actual_special_numbers"] = list(actual_special)
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "TARGET_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert all(check.state is HashVerificationState.VERIFIED_MATCH for check in report.hash_checks)
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_falsified_cutoff_sequence_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["records"][0]["cutoff"] = {**_draw_ref("D0"), "draw_sequence": 1}
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert all(check.state is HashVerificationState.VERIFIED_MATCH for check in report.hash_checks)
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_unknown_cutoff_draw_id_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["records"][0]["cutoff"] = {
        "draw_id": "UNKNOWN",
        "draw_sequence": 1,
        "draw_date": "2020-01-02",
    }
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding for finding in report.findings if finding.code == "CUTOFF_DRAW_NOT_IN_DATASET"
    )
    assert finding.category is FindingCategory.SEMANTIC_FAILURE
    assert all(check.state is HashVerificationState.VERIFIED_MATCH for check in report.hash_checks)
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_falsified_target_draw_date_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["records"][0]["target"]["draw_date"] = "2030-01-01"
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "TARGET_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_falsified_cutoff_draw_date_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["records"][0]["cutoff"]["draw_date"] = "2030-01-01"
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_maximum_data_cutoff_contradiction_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence["evaluation_windows"]["maximum_data_cutoff"]["draw_date"] = "2030-01-01"
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.pointer == "/evaluation_windows/maximum_data_cutoff"
        and finding.code == "CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_one_shot_cutoff_contradiction_is_rejected_against_snapshot(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    shared_cutoff = _draw_ref("D1")
    evidence["evaluation_protocol"] = "ONE_SHOT"
    evidence["evaluation_windows"].pop("walk_forward_cutoff_lag")
    evidence["evaluation_windows"]["one_shot_cutoff"] = {
        **shared_cutoff,
        "draw_date": "2030-01-01",
    }
    evidence["evaluation_windows"]["maximum_data_cutoff"] = shared_cutoff
    for record in evidence["records"]:
        record["cutoff"] = shared_cutoff
    evidence = _rehash_evidence(evidence)

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding
        for finding in report.findings
        if finding.pointer == "/evaluation_windows/one_shot_cutoff"
        and finding.code == "CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT"
    )
    assert finding.category is FindingCategory.CAUSAL_VIOLATION
    assert report.structurally_valid is False
    assert report.canonical_gate_passed is False


def test_cutoff_equal_to_target_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][0]["cutoff"] = evidence["records"][0]["target"]
    report = _validate(evidence, dataset, repo_root)
    assert "CUTOFF_NOT_BEFORE_TARGET" in _codes(report)


def test_cutoff_after_target_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][0]["cutoff"] = _draw_ref("D3")
    report = _validate(evidence, dataset, repo_root)
    assert "CUTOFF_NOT_BEFORE_TARGET" in _codes(report)


def test_walk_forward_lag_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evaluation_windows"]["walk_forward_cutoff_lag"] = 2
    report = _validate(evidence, dataset, repo_root)
    assert "WALK_FORWARD_LAG_MISMATCH" in _codes(report)


def test_one_shot_target_before_shared_cutoff_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evaluation_protocol"] = "ONE_SHOT"
    del evidence["evaluation_windows"]["walk_forward_cutoff_lag"]
    shared_cutoff = _draw_ref("D3")  # after both targets D2 and D3
    evidence["evaluation_windows"]["one_shot_cutoff"] = shared_cutoff
    for record in evidence["records"]:
        record["cutoff"] = shared_cutoff
    report = _validate(evidence, dataset, repo_root)
    assert "ONE_SHOT_TARGET_BEFORE_CUTOFF" in _codes(report)


def test_training_window_after_cutoff_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evaluation_windows"]["training_window"] = {"start_sequence": 0, "end_sequence": 2}
    report = _validate(evidence, dataset, repo_root)
    assert "TRAINING_WINDOW_AFTER_MINIMUM_CUTOFF" in _codes(report)


def test_fixed_parameter_selection_overlapping_evaluation_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evaluation_windows"]["parameter_selection_window"] = {
        "start_sequence": 0,
        "end_sequence": 2,
    }
    report = _validate(evidence, dataset, repo_root)
    assert "PARAMETER_SELECTION_OVERLAPS_EVALUATION" in _codes(report)


def test_maximum_cutoff_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evaluation_windows"]["maximum_data_cutoff"] = _draw_ref("D1")
    report = _validate(evidence, dataset, repo_root)
    assert "MAXIMUM_CUTOFF_MISMATCH" in _codes(report)


# --------------------------------------------------------------------------
# Tickets and outcomes
# --------------------------------------------------------------------------


def test_duplicate_ticket_combination_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    duplicate = copy.deepcopy(evidence["records"][0]["tickets"][0])
    duplicate["ticket_id"] = "T0-DUPLICATE-COMBO"
    evidence["records"][0]["tickets"].append(duplicate)
    report = _validate(evidence, dataset, repo_root)
    assert "DUPLICATE_TICKET_COMBINATION" in _codes(report)


def test_duplicate_ticket_id_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][1]["tickets"][0]["ticket_id"] = evidence["records"][0]["tickets"][0][
        "ticket_id"
    ]
    report = _validate(evidence, dataset, repo_root)
    assert "DUPLICATE_TICKET_ID" in _codes(report)


def test_invalid_ticket_number_count_range_overlap_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)

    too_few = copy.deepcopy(evidence)
    too_few["records"][0]["tickets"][0]["main_numbers"] = [1, 2, 3]
    assert "MAIN_NUMBER_COUNT_MISMATCH" in _codes(_validate(too_few, dataset, repo_root))

    out_of_range = copy.deepcopy(evidence)
    out_of_range["records"][0]["tickets"][0]["main_numbers"] = [1, 2, 3, 4, 5, 99]
    assert "MAIN_NUMBERS_OUT_OF_RANGE" in _codes(_validate(out_of_range, dataset, repo_root))

    overlapping = copy.deepcopy(evidence)
    overlapping["records"][0]["tickets"][0]["main_numbers"] = [1, 2, 3, 4, 5, 7]
    overlapping["records"][0]["tickets"][0]["special_numbers"] = [7]
    assert "MAIN_SPECIAL_OVERLAP_NOT_ALLOWED" in _codes(_validate(overlapping, dataset, repo_root))


def test_big_lotto_embedded_rule_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    mismatched = {**evidence["rule_parameters"], "main_number_max": 42}
    evidence["rule_parameters"] = _with_self_hash(
        {**mismatched, "rule_parameters_sha256": "0" * 64}, "rule_parameters_sha256"
    )
    report = _validate(evidence, dataset, repo_root)
    assert "RULE_BINDING_MISMATCH" in _codes(report)


def test_wrong_declared_main_hits_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][0]["tickets"][0]["main_hit_count"] = 99
    report = _validate(evidence, dataset, repo_root)
    assert "MAIN_HIT_COUNT_MISMATCH" in _codes(report)


def test_wrong_declared_special_hits_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][1]["tickets"][0]["special_hit"] = False  # actually True (10 matches D3)
    report = _validate(evidence, dataset, repo_root)
    assert "SPECIAL_HIT_MISMATCH" in _codes(report)


def test_actual_outcome_inconsistent_with_snapshot_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["records"][0]["actual_main_numbers"] = [10, 20, 30, 40, 41, 42]
    evidence = _with_self_hash(
        {**evidence, "artifact_content_sha256": "0" * 64}, "artifact_content_sha256"
    )
    report = _validate(evidence, dataset, repo_root)
    assert "ACTUAL_OUTCOME_INCONSISTENT_WITH_SNAPSHOT" in _codes(report)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def _add_metric_result(
    evidence: dict[str, Any],
    repo_root: Path,
    *,
    definition_sample_unit: str = "TICKETS",
    definition_aggregation: str = "MEAN",
    **overrides: object,
) -> dict[str, Any]:
    metric_path, metric_sha256 = _write_hit_rate_definition(
        repo_root,
        sample_unit=definition_sample_unit,
        aggregation=definition_aggregation,
    )
    result: dict[str, Any] = {
        "metric_id": "HIT_RATE_MAIN",
        "metric_version": "v1",
        "metric_definition_path": metric_path,
        "metric_definition_sha256": metric_sha256,
        "sample_size": 2,
        "sample_unit": "TICKETS",
        "aggregation": "MEAN",
        "value_status": "VALUE_PRESENT",
        "value": "0.5000",
        "verification_state": "DECLARED_NOT_RECOMPUTED",
    }
    for key, value in overrides.items():
        if value is None:
            result.pop(key, None)  # LCJ-1 omits absent fields; never stores null
        else:
            result[key] = value
    evidence = copy.deepcopy(evidence)
    evidence["metric_results"] = [result]
    return _with_self_hash(
        {**evidence, "artifact_content_sha256": "0" * 64}, "artifact_content_sha256"
    )


def _with_three_candidate_tickets(evidence: dict[str, Any]) -> dict[str, Any]:
    expanded = copy.deepcopy(evidence)
    expanded["records"][0]["tickets"].append(
        _make_ticket("T0-B", (1, 2, 3, 4, 5, 7), (8,), "D2")
    )
    return _rehash_evidence(expanded)


def test_sample_size_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _add_metric_result(evidence, repo_root, sample_size=999)
    report = _validate(evidence, dataset, repo_root)
    assert "SAMPLE_SIZE_MISMATCH" in _codes(report)


def test_metric_result_sample_unit_must_match_definition(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _add_metric_result(evidence, repo_root, sample_unit="DRAWS")

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding for finding in report.findings if finding.code == "METRIC_SAMPLE_UNIT_MISMATCH"
    )
    assert finding.category is FindingCategory.METRIC_DEFINITION_FAILURE
    assert finding.pointer == "/metric_results/0/sample_unit"


def test_metric_result_aggregation_must_match_definition(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _add_metric_result(evidence, repo_root, aggregation="SUM")

    report = _validate(evidence, dataset, repo_root)

    finding = next(
        finding for finding in report.findings if finding.code == "METRIC_AGGREGATION_MISMATCH"
    )
    assert finding.category is FindingCategory.METRIC_DEFINITION_FAILURE
    assert finding.pointer == "/metric_results/0/aggregation"


def test_ticket_sized_result_cannot_evade_draw_definition_sample_size(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _with_three_candidate_tickets(evidence)
    evidence = _add_metric_result(
        evidence,
        repo_root,
        definition_sample_unit="DRAWS",
        sample_unit="TICKETS",
        sample_size=3,
    )

    report = _validate(evidence, dataset, repo_root)

    assert {"METRIC_SAMPLE_UNIT_MISMATCH", "SAMPLE_SIZE_MISMATCH"} <= _codes(report)


def test_draw_sized_result_cannot_evade_ticket_definition_sample_size(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _with_three_candidate_tickets(evidence)
    evidence = _add_metric_result(
        evidence,
        repo_root,
        definition_sample_unit="TICKETS",
        sample_unit="DRAWS",
        sample_size=2,
    )

    report = _validate(evidence, dataset, repo_root)

    assert {"METRIC_SAMPLE_UNIT_MISMATCH", "SAMPLE_SIZE_MISMATCH"} <= _codes(report)


def test_aggregation_mismatch_does_not_suppress_sample_size_validation(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _add_metric_result(
        evidence,
        repo_root,
        aggregation="SUM",
        sample_size=999,
    )

    report = _validate(evidence, dataset, repo_root)

    assert {"METRIC_AGGREGATION_MISMATCH", "SAMPLE_SIZE_MISMATCH"} <= _codes(report)


def test_matching_metric_alignment_uses_definition_owned_ticket_count(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _with_three_candidate_tickets(evidence)
    evidence = _add_metric_result(evidence, repo_root, sample_size=3)

    report = _validate(evidence, dataset, repo_root)

    assert report.findings == ()


def test_invalid_decimal_scale_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    # "0.50" is a well-formed canonical decimal string (Pydantic-level shape is
    # fine), but the hit-rate definition fixture declares decimal_scale=4.
    evidence = _add_metric_result(evidence, repo_root, value="0.50")
    report = _validate(evidence, dataset, repo_root)
    assert "METRIC_VALUE_SCALE_MISMATCH" in _codes(report)


def test_absent_zero_and_not_computable_are_distinct(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    assert evidence["metric_results"] == []  # absent

    zero_valued = _add_metric_result(evidence, repo_root, value="0.0000")
    zero_report = _validate(zero_valued, dataset, repo_root)
    assert zero_report.findings == ()

    not_computable = _add_metric_result(
        evidence,
        repo_root,
        value_status="NOT_COMPUTABLE",
        value=None,
        reason_code="INSUFFICIENT_HISTORY",
    )
    nc_report = _validate(not_computable, dataset, repo_root)
    assert nc_report.findings == ()
    assert zero_valued["metric_results"][0]["value"] != not_computable["metric_results"][0].get(
        "value"
    )


def test_missing_definition_fails_verification(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = _add_metric_result(
        evidence,
        repo_root,
        metric_definition_path="contracts/evidence/does_not_exist.json",
        metric_definition_sha256=HASH_A,
    )
    report = _validate(evidence, dataset, repo_root)
    checks = {hc.pointer: hc.state for hc in report.hash_checks}
    assert (
        checks["/metric_results/0/metric_definition_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )


def test_raw_definition_hash_mismatch_rejected(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    metric_path, _real_sha256 = _write_hit_rate_definition(repo_root)
    evidence = _add_metric_result(
        evidence, repo_root, metric_definition_path=metric_path, metric_definition_sha256=HASH_A
    )
    report = _validate(evidence, dataset, repo_root)
    assert "REFERENCED_FILE_HASH_MISMATCH" in _codes(report)


def test_d3_value_present_produces_metric_definition_failure(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    d3_path, d3_sha256 = _write_d3_definition(repo_root)
    evidence = _add_metric_result(
        evidence,
        repo_root,
        metric_id="D3",
        metric_definition_path=d3_path,
        metric_definition_sha256=d3_sha256,
        value_status="VALUE_PRESENT",
        value="1.0000",
    )
    report = _validate(evidence, dataset, repo_root)
    d3_findings = [f for f in report.findings if f.code == "RESERVED_METRIC_VALUE_PRESENT"]
    assert d3_findings
    assert d3_findings[0].category is FindingCategory.METRIC_DEFINITION_FAILURE


def test_no_metric_value_is_synthesized(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    not_computable = _add_metric_result(
        evidence,
        repo_root,
        value_status="NOT_COMPUTABLE",
        value=None,
        reason_code="INSUFFICIENT_HISTORY",
    )
    assert not_computable["metric_results"][0].get("value") is None
    report = _validate(not_computable, dataset, repo_root)
    assert report.findings == ()


# --------------------------------------------------------------------------
# Definition-path containment (fail-closed, zero filesystem access)
# --------------------------------------------------------------------------


def test_absolute_and_traversal_paths_rejected_without_filesystem_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no filesystem access should occur for a lexically invalid path")

    monkeypatch.setattr(Path, "resolve", _forbidden)
    monkeypatch.setattr(Path, "stat", _forbidden)
    monkeypatch.setattr(Path, "open", _forbidden)
    monkeypatch.setattr(Path, "read_bytes", _forbidden)

    with pytest.raises(validator.DefinitionPathRejected) as absolute_exc:
        validator.resolve_definition_path(
            "/etc/passwd",
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )
    assert absolute_exc.value.finding.code == "DEFINITION_PATH_LEXICALLY_INVALID"

    with pytest.raises(validator.DefinitionPathRejected) as traversal_exc:
        validator.resolve_definition_path(
            "contracts/evidence/../../etc/passwd",
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )
    assert traversal_exc.value.finding.code == "DEFINITION_PATH_LEXICALLY_INVALID"


@pytest.mark.parametrize(
    "raw_path",
    [
        "contracts/evidence/nul\x00source.json",
        "contracts/evidence/newline\nsource.json",
        "contracts/evidence/control\x01source.json",
        "contracts/evidence/tab\tsource.json",
        "contracts/evidence/del\x7fsource.json",
    ],
)
def test_control_character_paths_rejected_without_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_path: str,
):
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("control-character path must fail before filesystem access")

    monkeypatch.setattr(Path, "resolve", _forbidden)
    monkeypatch.setattr(Path, "stat", _forbidden)
    monkeypatch.setattr(Path, "open", _forbidden)
    monkeypatch.setattr(Path, "read_bytes", _forbidden)

    with pytest.raises(validator.DefinitionPathRejected) as exc:
        validator.resolve_definition_path(
            raw_path,
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )

    finding = exc.value.finding
    assert finding.code == "DEFINITION_PATH_LEXICALLY_INVALID"
    assert finding.message == "definition path must not contain control characters"
    assert raw_path not in finding.message


@pytest.mark.parametrize(
    "resolution_error",
    [
        ValueError("raw path and absolute location must not leak"),
        RuntimeError("symlink detail must not leak"),
        OSError("OS-specific detail must not leak"),
    ],
)
def test_definition_path_resolution_exceptions_are_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolution_error: Exception,
):
    raw_path = "contracts/evidence/task-owned-source.json"

    def failed_resolve(*_args: object, **_kwargs: object) -> None:
        raise resolution_error

    monkeypatch.setattr(Path, "resolve", failed_resolve)

    with pytest.raises(validator.DefinitionPathRejected) as exc:
        validator.resolve_definition_path(
            raw_path,
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )

    finding = exc.value.finding
    assert finding.code == "DEFINITION_PATH_RESOLUTION_FAILED"
    assert finding.message == "definition path could not be resolved safely"
    assert raw_path not in finding.message
    assert str(tmp_path) not in finding.message
    assert type(resolution_error).__name__ not in finding.message


def test_local_provenance_symlink_loop_is_sanitized_and_registry_cannot_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset, evidence, repo_root, _source_path, source_bytes = _build_local_committed_pair(
        tmp_path
    )
    loop_a = repo_root / "contracts/evidence/loop-a"
    loop_b = repo_root / "contracts/evidence/loop-b"
    loop_a.symlink_to("loop-b")
    loop_b.symlink_to("loop-a")
    raw_path = "contracts/evidence/loop-a/source.json"
    dataset, evidence = _with_local_provenance(
        dataset,
        evidence,
        source_path=raw_path,
        source_git_oid=dataset["source_provenance"]["source_git_oid"],
        source_file_sha256=canonical_json.sha256_hex(source_bytes),
    )

    def forbidden_git(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("resolution failure must happen before any Git query")

    monkeypatch.setattr(validator, "_run_read_only_git", forbidden_git)

    report = validator.validate_evidence_artifact(
        StrategyEvaluationEvidence.model_validate(evidence),
        repo_root=repo_root,
        dataset=DatasetSnapshot.model_validate(dataset),
        canonical_registry=frozenset({evidence["artifact_content_sha256"]}),
    )

    finding = next(
        finding
        for finding in report.findings
        if finding.code == "DEFINITION_PATH_RESOLUTION_FAILED"
    )
    assert finding.message == "definition path could not be resolved safely"
    assert raw_path not in finding.message
    assert str(repo_root) not in finding.message
    checks = {check.pointer: check.state for check in report.hash_checks}
    assert (
        checks["/dataset_snapshot/source_provenance/source_file_sha256"]
        is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    )
    assert report.canonical_gate_passed is False


def test_protected_path_rejected_without_any_filesystem_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("protected path must never be touched on disk")

    monkeypatch.setattr(Path, "resolve", _forbidden)
    monkeypatch.setattr(Path, "stat", _forbidden)
    monkeypatch.setattr(Path, "open", _forbidden)
    monkeypatch.setattr(Path, "read_bytes", _forbidden)

    with pytest.raises(validator.DefinitionPathRejected) as exc:
        validator.resolve_definition_path(
            "docs/ownerinit.md",
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )
    assert exc.value.finding.code == "DEFINITION_PATH_PROTECTED"

    with pytest.raises(validator.DefinitionPathRejected) as exc2:
        validator.resolve_definition_path(
            ".local/secret.json",
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
            pointer="/x",
        )
    assert exc2.value.finding.code == "DEFINITION_PATH_PROTECTED"


def test_canonical_status_cannot_reference_tests_fixtures_path(tmp_path: Path):
    fixture_dir = tmp_path / "tests/fixtures/evidence/synthetic"
    fixture_dir.mkdir(parents=True)
    target = fixture_dir / "some_def.json"
    target.write_bytes(canonical_json.canonical_file_bytes({"a": 1}))

    with pytest.raises(validator.DefinitionPathRejected) as exc:
        validator.resolve_definition_path(
            "tests/fixtures/evidence/synthetic/some_def.json",
            repo_root=tmp_path,
            evidence_status=EvidenceStatus.CANONICAL,
            pointer="/x",
        )
    assert exc.value.finding.code == "DEFINITION_PATH_OUTSIDE_ALLOWED_ROOT"

    resolved = validator.resolve_definition_path(
        "tests/fixtures/evidence/synthetic/some_def.json",
        repo_root=tmp_path,
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
        pointer="/x",
    )
    assert resolved == target.resolve()


# --------------------------------------------------------------------------
# Authority
# --------------------------------------------------------------------------


def test_self_declared_canonical_not_in_registry_fails_canonical_gate(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["evidence_status"] = "CANONICAL"
    evidence["artifact_id"] = "NOT_SYNTHETIC_ARTIFACT"
    evidence = _with_self_hash(
        {**evidence, "artifact_content_sha256": "0" * 64}, "artifact_content_sha256"
    )
    report = _validate(evidence, dataset, repo_root)
    assert report.trust_classification is not None
    assert report.trust_classification.value != "REGISTERED_CANONICAL"
    assert report.canonical_gate_passed is False


def test_synthetic_evidence_cannot_become_canonical_even_via_temporary_registry(tmp_path: Path):
    dataset, evidence, repo_root = _build_valid_pair(tmp_path)
    evidence_model = StrategyEvaluationEvidence.model_validate(evidence)
    dataset_model = DatasetSnapshot.model_validate(dataset)
    fake_registry = frozenset({evidence["artifact_content_sha256"]})
    report = validator.validate_evidence_artifact(
        evidence_model, repo_root=repo_root, dataset=dataset_model, canonical_registry=fake_registry
    )
    assert report.trust_classification is not None
    assert report.trust_classification.value == "SYNTHETIC"
    assert report.canonical_gate_passed is False


def test_committed_empty_registries_make_canonical_gate_unsatisfied():
    registry_path = REPO_ROOT / "contracts/evidence/canonical_evidence_registry.json"
    registry = validator.load_canonical_evidence_registry(registry_path)
    assert registry == frozenset()

    approved_path = REPO_ROOT / "contracts/evidence/approved_ranking_policy_registry.json"
    approved_registry = validator.load_approved_ranking_policy_registry(approved_path)
    assert approved_registry == frozenset()


def test_self_declared_approved_policy_not_in_registry_remains_unapproved():
    from lottolab.evidence.models import PolicyTrustClass

    trust = validator.classify_policy_trust(
        _approved_policy_stub(), raw_file_sha256=HASH_A, approved_registry=frozenset()
    )
    assert trust is PolicyTrustClass.UNTRUSTED_DECLARED


def _approved_policy_stub():
    from lottolab.evidence.models import RankingPolicy

    return RankingPolicy.model_validate(
        {
            "schema_id": "lottolab.evidence.ranking_policy",
            "schema_version": "1.0.0",
            "policy_id": "SYNTHETIC_APPROVAL_TEST",
            "policy_version": "v1",
            "declared_status": "APPROVED",
            "primary_metric_id": "HIT_RATE_MAIN",
            "primary_metric_version": "v1",
            "primary_metric_definition_sha256": HASH_A,
            "minimum_sample_size": 1,
            "required_evidence_trust": "REGISTERED_CANONICAL",
            "eligible_evaluation_modes": ["EX_ANTE"],
            "required_lottery_type": "BIG_LOTTO",
            "candidate_count_policy": "ALLOW_ANY",
            "parameter_policy": "PINNED_HASH",
            "comparability_dimensions": {
                "shared_environment": [
                    "lottery_type",
                    "dataset_sha256",
                    "evaluation_mode",
                    "evaluation_protocol",
                    "evaluation_window",
                    "metric_identity",
                    "sample_unit",
                    "candidate_count_conformance",
                ],
                "per_strategy_identity": [
                    "strategy_identity",
                    "method_identity",
                    "feature_version",
                    "parameters_sha256",
                ],
            },
            "tie_breakers": ["strategy_id"],
            "missing_evidence_behavior": "TREAT_AS_INELIGIBLE",
            "ineligibility_reason_codes": ["NOT_REGISTERED_CANONICAL"],
        }
    )
