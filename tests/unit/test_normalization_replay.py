from __future__ import annotations

import builtins
import hashlib
import json
import os
import random
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.evidence import canonical_json, validator
from lottolab.evidence.models import (
    DatasetProvenance,
    DatasetProvenanceKind,
    EvidenceStatus,
    EvidenceTrustClass,
    StrategyEvaluationEvidence,
)
from lottolab.normalization import (
    NormalizationOutcome,
    NormalizationParameters,
    manifest_canonical_bytes,
    manifest_committed_bytes,
    normalize,
    snapshot_canonical_bytes,
    snapshot_committed_bytes,
    verify_replay,
)
from lottolab.normalization import normalizer as normalizer_module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests/fixtures/normalization/synthetic"
EVIDENCE_FIXTURES = REPO_ROOT / "tests/fixtures/evidence/synthetic"


def _fixture_identity(stem: str) -> tuple[str, str]:
    if stem == "minimal":
        return (
            "SYNTHETIC_BIGLOTTO_NORMALIZATION_MINIMAL",
            "Synthetic normalization fixture only.",
        )
    return (
        "SYNTHETIC_BIGLOTTO_NORMALIZATION_SIX_DRAW",
        "Synthetic six-draw normalization fixture only.",
    )


def _normalize_fixture(stem: str, *, implementation_oid: str | None = None):
    dataset_id, description = _fixture_identity(stem)
    return normalize(
        (FIXTURES / f"{stem}.csv").read_bytes(),
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id=dataset_id,
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description=description,
        ),
        declared_implementation_oid=implementation_oid,
    )


@pytest.mark.parametrize("stem", ["minimal", "six_draw"])
def test_golden_replay_is_exact_and_identical_twice(stem: str) -> None:
    expected_snapshot = (FIXTURES / f"{stem}.expected_snapshot.json").read_bytes()
    expected_manifest = (FIXTURES / f"{stem}.expected_manifest.json").read_bytes()
    first = _normalize_fixture(stem)
    second = _normalize_fixture(stem)
    assert first == second
    assert first.outcome is NormalizationOutcome.NORMALIZATION_PASS
    assert first.snapshot is not None and first.manifest is not None
    snapshot_findings, snapshot_hash_checks = validator.validate_dataset_snapshot(first.snapshot)
    assert snapshot_findings == []
    assert snapshot_hash_checks and all(
        check.state.value == "VERIFIED_MATCH" for check in snapshot_hash_checks
    )
    assert snapshot_committed_bytes(first.snapshot) == expected_snapshot
    assert manifest_committed_bytes(first.manifest) == expected_manifest
    assert verify_replay(
        first,
        expected_snapshot_bytes=expected_snapshot,
        expected_manifest_bytes=expected_manifest,
    ) is first


def test_golden_replay_proof_token() -> None:
    for stem in ("minimal", "six_draw"):
        result = _normalize_fixture(stem)
        assert result.snapshot is not None and result.manifest is not None
        assert snapshot_committed_bytes(result.snapshot) == (
            FIXTURES / f"{stem}.expected_snapshot.json"
        ).read_bytes()
        assert manifest_committed_bytes(result.manifest) == (
            FIXTURES / f"{stem}.expected_manifest.json"
        ).read_bytes()
    print("NORMALIZATION_GOLDEN_REPLAY_PASS fixtures=2")


def test_canonical_and_committed_byte_boundaries_are_exact() -> None:
    result = _normalize_fixture("minimal")
    assert result.snapshot is not None and result.manifest is not None
    assert not snapshot_canonical_bytes(result.snapshot).endswith(b"\n")
    assert not manifest_canonical_bytes(result.manifest).endswith(b"\n")
    assert snapshot_committed_bytes(result.snapshot) == (
        snapshot_canonical_bytes(result.snapshot) + b"\n"
    )
    assert manifest_committed_bytes(result.manifest) == (
        manifest_canonical_bytes(result.manifest) + b"\n"
    )
    snapshot_document = result.snapshot.model_dump(mode="json", exclude_none=True)
    manifest_document = result.manifest.model_dump(mode="json", exclude_none=True)
    assert result.snapshot.dataset_sha256 == hashlib.sha256(
        canonical_json.canonical_bytes_excluding_keys(snapshot_document, "dataset_sha256")
    ).hexdigest()
    assert result.manifest.manifest_sha256 == hashlib.sha256(
        canonical_json.canonical_bytes_excluding_keys(manifest_document, "manifest_sha256")
    ).hexdigest()


def test_valid_source_mutation_changes_source_dataset_and_manifest_hashes() -> None:
    original = _normalize_fixture("minimal")
    source = (FIXTURES / "minimal.csv").read_bytes().replace(
        b"1|2|3|4|5|6,7", b"2|3|4|5|6|7,8"
    )
    mutated = normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO_NORMALIZATION_MINIMAL",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description="Synthetic normalization fixture only.",
        ),
    )
    assert original.snapshot is not None and original.manifest is not None
    assert mutated.snapshot is not None and mutated.manifest is not None
    assert mutated.snapshot.dataset_sha256 != original.snapshot.dataset_sha256
    assert mutated.manifest.source_input_sha256 != original.manifest.source_input_sha256
    assert mutated.manifest.manifest_sha256 != original.manifest.manifest_sha256


def test_declared_oid_changes_only_manifest_lineage() -> None:
    first = _normalize_fixture("minimal", implementation_oid="1" * 40)
    second = _normalize_fixture("minimal", implementation_oid="2" * 40)
    assert first.snapshot == second.snapshot
    assert first.manifest is not None and second.manifest is not None
    assert first.manifest.normalizer_implementation_git_oid == "1" * 40
    assert second.manifest.normalizer_implementation_git_oid == "2" * 40
    assert first.manifest.manifest_sha256 != second.manifest.manifest_sha256


def test_parameter_substitution_changes_snapshot_and_manifest_identity() -> None:
    original = _normalize_fixture("minimal")
    substituted = normalize(
        (FIXTURES / "minimal.csv").read_bytes(),
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO_NORMALIZATION_SUBSTITUTED",
            dataset_version="2.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description="Synthetic normalization fixture only.",
        ),
    )
    assert original.snapshot is not None and original.manifest is not None
    assert substituted.snapshot is not None and substituted.manifest is not None
    assert substituted.snapshot.dataset_sha256 != original.snapshot.dataset_sha256
    assert substituted.manifest.manifest_sha256 != original.manifest.manifest_sha256


def test_replay_mismatch_cases_clear_both_artifacts_in_stable_order() -> None:
    result = _normalize_fixture("minimal")
    assert result.snapshot is not None and result.manifest is not None
    snapshot_bytes = snapshot_committed_bytes(result.snapshot)
    manifest_bytes = manifest_committed_bytes(result.manifest)

    snapshot_bad = verify_replay(
        result,
        expected_snapshot_bytes=snapshot_bytes + b"x",
        expected_manifest_bytes=manifest_bytes,
    )
    assert [item.reason_code for item in snapshot_bad.findings] == [
        "NRM_REPLAY_SNAPSHOT_MISMATCH"
    ]

    manifest_bad = verify_replay(
        result,
        expected_snapshot_bytes=snapshot_bytes,
        expected_manifest_bytes=manifest_bytes + b"x",
    )
    assert [item.reason_code for item in manifest_bad.findings] == [
        "NRM_REPLAY_MANIFEST_MISMATCH"
    ]

    both_bad = verify_replay(
        result,
        expected_snapshot_bytes=b"wrong snapshot",
        expected_manifest_bytes=b"wrong manifest",
    )
    assert both_bad.outcome is NormalizationOutcome.NORMALIZATION_OUTPUT_HASH_MISMATCH
    assert both_bad.snapshot is None and both_bad.manifest is None
    assert [item.reason_code for item in both_bad.findings] == [
        "NRM_REPLAY_MANIFEST_MISMATCH",
        "NRM_REPLAY_SNAPSHOT_MISMATCH",
    ]


def test_non_pass_replay_returns_same_result_unchanged() -> None:
    rejected = normalize(
        b"bad",
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BAD",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(kind=DatasetProvenanceKind.SYNTHETIC),
    )
    assert verify_replay(
        rejected,
        expected_snapshot_bytes=b"anything",
        expected_manifest_bytes=b"anything",
    ) is rejected


def test_local_hash_mismatch_precedes_parser_and_exposes_no_partial_output() -> None:
    provenance = DatasetProvenance(
        kind=DatasetProvenanceKind.LOCAL_COMMITTED_FILE,
        source_definition_path="contracts/evidence/synthetic_source.csv",
        source_git_oid="1" * 40,
        source_file_sha256="0" * 64,
    )
    result = normalize(
        b"not even csv",
        format_id="unsupported",
        format_version="9.9.9",
        parameters=NormalizationParameters(
            dataset_id="LOCAL_DATASET",
            dataset_version="1.0.0",
            lottery_type=LotteryType.DAILY_539,
        ),
        provenance=provenance,
    )
    assert result.outcome is NormalizationOutcome.NORMALIZATION_INPUT_UNVERIFIED
    assert [finding.reason_code for finding in result.findings] == [
        "NRM_SRC_INPUT_HASH_MISMATCH"
    ]
    assert result.snapshot is None and result.manifest is None


@pytest.mark.parametrize(
    "format_id,format_version,code",
    [
        ("other", "1.0.0", "NRM_SRC_FORMAT_ID_UNSUPPORTED"),
        ("synthetic_draw_csv", "2.0.0", "NRM_SRC_FORMAT_VERSION_UNSUPPORTED"),
    ],
)
def test_unsupported_contract_identity_fails_before_source(
    format_id: str, format_version: str, code: str
) -> None:
    result = normalize(
        b"bad source",
        format_id=format_id,
        format_version=format_version,
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BAD",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(kind=DatasetProvenanceKind.SYNTHETIC),
    )
    assert result.outcome is NormalizationOutcome.NORMALIZATION_CONTRACT_FAILURE
    assert result.findings[0].reason_code == code


def test_unsupported_lottery_and_missing_rule_contract_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (FIXTURES / "minimal.csv").read_bytes()
    unsupported = normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_539",
            dataset_version="1.0.0",
            lottery_type=LotteryType.DAILY_539,
        ),
        provenance=DatasetProvenance(kind=DatasetProvenanceKind.SYNTHETIC),
    )
    assert unsupported.findings[0].reason_code == "NRM_RULE_UNSUPPORTED_LOTTERY"

    monkeypatch.setattr(normalizer_module, "LOTTERY_RULE_CONTRACTS", {})
    unavailable = normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(kind=DatasetProvenanceKind.SYNTHETIC),
    )
    assert unavailable.findings[0].reason_code == "NRM_RULE_CONTRACT_UNAVAILABLE"


def test_internal_contract_identity_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(normalizer_module, "NORMALIZER_VERSION", "9.9.9")
    result = _normalize_fixture("minimal")
    assert result.outcome is NormalizationOutcome.NORMALIZATION_CONTRACT_FAILURE
    assert result.findings[0].reason_code == "NRM_LIN_CONTRACT_IDENTITY_MISMATCH"


def test_normalize_uses_no_effectful_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (FIXTURES / "minimal.csv").read_bytes()
    tolerant_module_name = "lottolab.infrastructure.imports.csv_draws"
    tolerant_module_before = sys.modules.get(tolerant_module_name)

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("effectful boundary invoked")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(random, "random", forbidden)

    result = normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO_NORMALIZATION_MINIMAL",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description="Synthetic normalization fixture only.",
        ),
    )
    assert result.outcome is NormalizationOutcome.NORMALIZATION_PASS
    assert sys.modules.get(tolerant_module_name) is tolerant_module_before


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_local_commit_a_bytes_remain_authoritative_over_head_b_and_worktree_c(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    source_path = repo / "contracts/evidence/synthetic_source.csv"
    source_path.parent.mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.name", "Normalization test")
    _git(repo, "config", "user.email", "normalization@example.invalid")
    source_a = (FIXTURES / "minimal.csv").read_bytes()
    source_path.write_bytes(source_a)
    _git(repo, "add", "contracts/evidence/synthetic_source.csv")
    _git(repo, "commit", "-q", "-m", "source A")
    oid_a = _git(repo, "rev-parse", "HEAD")

    source_path.write_bytes(source_a.replace(b"SYN-D-0", b"SYN-D-B"))
    _git(repo, "commit", "-q", "-am", "source B")
    source_path.write_bytes(source_a.replace(b"SYN-D-0", b"SYN-D-C"))

    result = normalize(
        source_a,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="LOCAL_BIGLOTTO_NORMALIZATION",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.LOCAL_COMMITTED_FILE,
            source_definition_path="contracts/evidence/synthetic_source.csv",
            source_git_oid=oid_a,
            source_file_sha256=hashlib.sha256(source_a).hexdigest(),
        ),
    )
    assert result.outcome is NormalizationOutcome.NORMALIZATION_PASS
    assert result.snapshot is not None
    findings, checks, unverified = validator.verify_dataset_provenance(
        result.snapshot,
        repo_root=repo,
        evidence_status=EvidenceStatus.DRAFT,
    )
    assert findings == []
    assert checks and all(check.state.value == "VERIFIED_MATCH" for check in checks)
    assert unverified is False


def _six_draw_source_without_duplicate_date() -> bytes:
    return (
        b"draw_id,draw_sequence,draw_date,main_numbers,special_numbers\n"
        b"SYN-D-0,0,2020-01-01,1|2|3|4|5|6,7\n"
        b"SYN-D-1,1,2020-01-02,2|3|4|5|6|7,8\n"
        b"SYN-D-2,2,2020-01-03,3|4|5|6|7|8,9\n"
        b"SYN-D-3,3,2020-01-04,4|5|6|7|8|9,10\n"
        b"SYN-D-4,4,2020-01-05,5|6|7|8|9|10,11\n"
        b"SYN-D-5,5,2020-01-06,6|7|8|9|10|11,12\n"
    )


@pytest.mark.parametrize(
    "kind,dataset_id,expected_unverified",
    [
        (DatasetProvenanceKind.SYNTHETIC, "SYNTHETIC_BIGLOTTO_MINI_001", False),
        (DatasetProvenanceKind.EXTERNAL_DECLARED, "EXTERNAL_BIGLOTTO_MINI_001", True),
    ],
)
def test_registry_injection_does_not_upgrade_synthetic_or_external_normalization(
    kind: DatasetProvenanceKind,
    dataset_id: str,
    expected_unverified: bool,
) -> None:
    result = normalize(
        _six_draw_source_without_duplicate_date(),
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id=dataset_id,
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(kind=kind, declared_description="Declared test source."),
    )
    assert result.snapshot is not None

    document = json.loads((EVIDENCE_FIXTURES / "evaluation_evidence.json").read_bytes())
    document["dataset_reference"]["dataset_id"] = dataset_id
    document["dataset_reference"]["dataset_sha256"] = result.snapshot.dataset_sha256
    document["artifact_content_sha256"] = "0" * 64
    document["artifact_content_sha256"] = canonical_json.self_key_removed_sha256(
        document, "artifact_content_sha256"
    )
    evidence = StrategyEvaluationEvidence.model_validate(document)
    report = validator.validate_evidence_artifact(
        evidence,
        repo_root=REPO_ROOT,
        dataset=result.snapshot,
        canonical_registry=frozenset({evidence.artifact_content_sha256}),
    )
    assert report.canonical_gate_passed is False
    assert report.trust_classification is not EvidenceTrustClass.REGISTERED_CANONICAL
    provenance_findings, _checks, unverified = validator.verify_dataset_provenance(
        result.snapshot,
        repo_root=REPO_ROOT,
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
    )
    assert unverified is expected_unverified
    if kind is DatasetProvenanceKind.EXTERNAL_DECLARED:
        assert {finding.code for finding in provenance_findings} == {
            "DATASET_EXTERNAL_DECLARED_UNVERIFIED"
        }
