from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from lottolab.domain.draws import LotteryType
from lottolab.evidence.models import DatasetProvenance, DatasetProvenanceKind
from lottolab.normalization.models import (
    DatasetNormalizationManifest,
    NormalizationFinding,
    NormalizationOutcome,
    NormalizationParameters,
    NormalizationResult,
    RecordMappingKind,
)
from lottolab.normalization.normalizer import (
    FORMAT_DEFINITION_SHA256,
    NORMALIZER_CONTRACT_SHA256,
    normalize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests/fixtures/normalization/synthetic"

EVIDENCE_INVARIANTS = {
    "contracts/evidence/strategy_evaluation_evidence.schema.json": (
        "7729010bd6f8d1a41c5f9ffe15ccdd867a5f2341d82f775fd405ca8d469f49fc"
    ),
    "contracts/evidence/dataset_snapshot.schema.json": (
        "96b93ab312bc2b516b89259860b16930c87c19ce2dd938bb855324182ab44c76"
    ),
    "contracts/evidence/ranking_policy.schema.json": (
        "eccd3791ec83ba94fd4c4723e71880b17fa782d1aa57391f48ecc9ef5129eb58"
    ),
    "contracts/evidence/metric_definition.schema.json": (
        "c8e1c74c00e1fdaa4073a3eb522a7cedb52e144f4ecd1d97c9e8a895c6ed94c1"
    ),
    "contracts/evidence/metric_definitions/d3.json": (
        "857d4bcc6ff317c2998287b12956657be72b29def3f240879d8af1fbc2fc798c"
    ),
    "contracts/evidence/canonical_evidence_registry.json": (
        "8e07470750dc1630db4c9e25476e91f624e9d0809c0e5db36b2ad6df250dc87f"
    ),
    "contracts/evidence/approved_ranking_policy_registry.json": (
        "d017bdb72a066c095aeb3ecb1ef6eaffde833b5cc0b797522dd7d4644a5fe50c"
    ),
}


def _pass_result(*, implementation_oid: str | None = None) -> NormalizationResult:
    return normalize(
        (FIXTURES / "minimal.csv").read_bytes(),
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
        declared_implementation_oid=implementation_oid,
    )


@pytest.mark.parametrize(
    "model_type,document",
    [
        (
            NormalizationParameters,
            {
                "dataset_id": "SYNTHETIC_X",
                "dataset_version": "1.0.0",
                "lottery_type": "BIG_LOTTO",
                "unexpected": True,
            },
        ),
        (
            NormalizationFinding,
            {
                "reason_code": "NRM_SRC_HEADER_MISMATCH",
                "source_record_ordinal": 0,
                "field": "header",
                "message": "header mismatch",
                "unexpected": True,
            },
        ),
    ],
)
def test_models_reject_extra_fields(model_type: type[Any], document: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(document)


def test_parameters_are_frozen() -> None:
    parameters = NormalizationParameters(
        dataset_id="SYNTHETIC_X",
        dataset_version="1.0.0",
        lottery_type=LotteryType.BIG_LOTTO,
    )
    with pytest.raises(ValidationError):
        parameters.dataset_id = "SYNTHETIC_CHANGED"


def test_closed_enums_have_exact_members() -> None:
    assert [member.value for member in RecordMappingKind] == ["IDENTITY_ORDER_PRESERVING"]
    assert [member.value for member in NormalizationOutcome] == [
        "NORMALIZATION_PASS",
        "NORMALIZATION_INPUT_UNVERIFIED",
        "NORMALIZATION_CONTRACT_FAILURE",
        "NORMALIZATION_REJECTED_SOURCE",
        "NORMALIZATION_OUTPUT_HASH_MISMATCH",
    ]


def test_finding_namespace_order_and_sanitization_are_closed() -> None:
    with pytest.raises(ValidationError):
        NormalizationFinding(
            reason_code="RAW_EXCEPTION_ValueError",
            source_record_ordinal=0,
            field="source",
            message="safe",
        )
    with pytest.raises(ValidationError):
        NormalizationFinding(
            reason_code="NRM_SRC_INVALID_BYTE_DOMAIN",
            source_record_ordinal=0,
            field="source",
            message="raw\nrow",
        )


def test_pass_manifest_has_exact_ids_counts_and_self_hash() -> None:
    result = _pass_result()
    assert result.outcome is NormalizationOutcome.NORMALIZATION_PASS
    assert result.snapshot is not None
    assert result.manifest is not None
    manifest = result.manifest
    assert manifest.schema_id == "lottolab.normalization.dataset_normalization_manifest"
    assert manifest.schema_version == "1.0.0"
    assert manifest.source_format_id == "synthetic_draw_csv"
    assert manifest.source_format_version == "1.0.0"
    assert manifest.normalizer_id == "lottolab_source_to_snapshot"
    assert manifest.normalizer_version == "1.0.0"
    assert manifest.record_mapping_kind == "IDENTITY_ORDER_PRESERVING"
    assert manifest.source_record_count == 1
    assert manifest.accepted_record_count == 1
    assert manifest.rejected_record_count == 0
    assert manifest.normalized_draw_count == 1
    assert manifest.normalized_dataset_sha256 == result.snapshot.dataset_sha256

    tampered = manifest.model_dump(mode="json", exclude_none=True)
    tampered["manifest_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        DatasetNormalizationManifest.model_validate(tampered)


def test_manifest_optional_oid_is_omitted_or_exact() -> None:
    absent = _pass_result()
    present = _pass_result(implementation_oid="a" * 40)
    assert absent.manifest is not None
    assert present.manifest is not None
    assert "normalizer_implementation_git_oid" not in absent.manifest.model_dump(
        mode="json", exclude_none=True
    )
    assert present.manifest.normalizer_implementation_git_oid == "a" * 40
    with pytest.raises(ValidationError):
        DatasetNormalizationManifest.model_validate(
            {
                **present.manifest.model_dump(mode="json", exclude_none=True),
                "normalizer_implementation_git_oid": "A" * 40,
            }
        )


def test_result_shape_forbids_partial_or_empty_failure() -> None:
    result = _pass_result()
    assert result.snapshot is not None
    with pytest.raises(ValidationError):
        NormalizationResult(outcome=NormalizationOutcome.NORMALIZATION_PASS)
    with pytest.raises(ValidationError):
        NormalizationResult(
            outcome=NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE,
            snapshot=result.snapshot,
            findings=(
                NormalizationFinding(
                    reason_code="NRM_SRC_HEADER_MISMATCH",
                    source_record_ordinal=0,
                    field="header",
                    message="header mismatch",
                ),
            ),
        )
    with pytest.raises(ValidationError):
        NormalizationResult(outcome=NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE)


def test_definition_hash_constants_match_raw_committed_files() -> None:
    format_bytes = (
        REPO_ROOT / "contracts/normalization/formats/synthetic_draw_csv_v1.json"
    ).read_bytes()
    contract_bytes = (
        REPO_ROOT / "docs/architecture/source-to-snapshot-normalization-contract.md"
    ).read_bytes()
    assert hashlib.sha256(format_bytes).hexdigest() == FORMAT_DEFINITION_SHA256
    assert hashlib.sha256(contract_bytes).hexdigest() == NORMALIZER_CONTRACT_SHA256
    assert FORMAT_DEFINITION_SHA256.encode() not in format_bytes
    assert NORMALIZER_CONTRACT_SHA256.encode() not in contract_bytes


def test_format_contract_is_compact_sorted_json_plus_one_lf() -> None:
    path = REPO_ROOT / "contracts/normalization/formats/synthetic_draw_csv_v1.json"
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\r\n")
    assert raw.count(b"\n") == 1
    value = json.loads(raw)
    rendered = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert raw == rendered + b"\n"
    assert "hash" not in value


def test_manifest_schema_is_closed_and_generator_is_fresh() -> None:
    path = REPO_ROOT / "contracts/normalization/dataset_normalization_manifest.schema.json"
    raw = path.read_bytes()
    schema = json.loads(raw)
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_id"]["const"] == (
        "lottolab.normalization.dataset_normalization_manifest"
    )
    completed = subprocess.run(
        [sys.executable, "tools/generate_normalization_schemas.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "NORMALIZATION_SCHEMA_CHECK_PASS stale=0"


@pytest.mark.parametrize("relative_path,expected", EVIDENCE_INVARIANTS.items())
def test_seven_evidence_foundation_hashes_are_unchanged(
    relative_path: str, expected: str
) -> None:
    assert hashlib.sha256((REPO_ROOT / relative_path).read_bytes()).hexdigest() == expected
