"""Pure deterministic source-to-snapshot normalization entry points."""

from __future__ import annotations

import re
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    LOTTERY_RULE_CONTRACTS,
    LotteryRuleContract,
    resolve_lottery_rule_contract,
)
from lottolab.evidence import canonical_json
from lottolab.evidence.models import (
    DatasetProvenance,
    DatasetProvenanceKind,
    DatasetSnapshot,
    DrawEntry,
    RuleParameters,
)
from lottolab.normalization.models import (
    FORMAT_DEFINITION_PATH,
    NORMALIZATION_MANIFEST_SCHEMA_ID,
    NORMALIZATION_MANIFEST_SCHEMA_VERSION,
    NORMALIZER_CONTRACT_PATH,
    NORMALIZER_ID,
    NORMALIZER_VERSION,
    SOURCE_FORMAT_ID,
    SOURCE_FORMAT_VERSION,
    DatasetNormalizationManifest,
    NormalizationFinding,
    NormalizationOutcome,
    NormalizationParameters,
    NormalizationResult,
    RecordMappingKind,
)
from lottolab.normalization.synthetic_csv import ParsedRecord, parse_synthetic_draw_csv

FORMAT_DEFINITION_SHA256 = "bfee6ecb42701a2071e5bbe7e3e91931c6cb6b6f5051fa1491e4b34a597f8257"
NORMALIZER_CONTRACT_SHA256 = "668d047dbd10d1e26d1bc1f9282e3a6f411bcdf88407ad7c03e870899a6607d8"

_DATASET_SCHEMA_ID = "lottolab.evidence.dataset_snapshot"
_DATASET_SCHEMA_VERSION = "1.0.0"
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _finding(code: str, field: str, message: str) -> NormalizationFinding:
    return NormalizationFinding(
        reason_code=code,
        source_record_ordinal=0,
        field=field,
        message=message,
    )


def _failure(
    outcome: NormalizationOutcome,
    findings: tuple[NormalizationFinding, ...] | list[NormalizationFinding],
) -> NormalizationResult:
    ordered = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.source_record_ordinal,
                finding.reason_code,
                finding.field,
            ),
        )
    )
    return NormalizationResult(outcome=outcome, findings=ordered)


def _model_dict(model: Any) -> dict[str, Any]:
    return cast(dict[str, Any], model.model_dump(mode="json", exclude_none=True))


def snapshot_canonical_bytes(snapshot: DatasetSnapshot) -> bytes:
    return canonical_json.canonical_bytes(_model_dict(snapshot))


def snapshot_committed_bytes(snapshot: DatasetSnapshot) -> bytes:
    return canonical_json.canonical_file_bytes(_model_dict(snapshot))


def manifest_canonical_bytes(manifest: DatasetNormalizationManifest) -> bytes:
    return canonical_json.canonical_bytes(_model_dict(manifest))


def manifest_committed_bytes(manifest: DatasetNormalizationManifest) -> bytes:
    return canonical_json.canonical_file_bytes(_model_dict(manifest))


def _build_rule_binding(rule: LotteryRuleContract) -> RuleParameters:
    draft: dict[str, Any] = {
        "main_number_count": rule.main_number_count,
        "main_number_min": rule.main_number_min,
        "main_number_max": rule.main_number_max,
        "main_numbers_unique": rule.main_numbers_unique,
        "special_number_count": rule.special_number_count,
        "special_number_min": rule.special_number_min,
        "special_number_max": rule.special_number_max,
        "special_numbers_unique": rule.special_numbers_unique,
        "main_special_overlap_allowed": rule.main_special_overlap_allowed,
        "rule_contract_version": rule.contract_version,
        "rule_parameters_sha256": "0" * 64,
    }
    draft["rule_parameters_sha256"] = canonical_json.self_key_removed_sha256(
        draft, "rule_parameters_sha256"
    )
    return RuleParameters.model_validate(draft)


def _build_snapshot(
    records: tuple[ParsedRecord, ...],
    *,
    parameters: NormalizationParameters,
    provenance: DatasetProvenance,
    rule: LotteryRuleContract,
) -> DatasetSnapshot:
    rule_binding = _build_rule_binding(rule)
    draft: dict[str, Any] = {
        "schema_id": _DATASET_SCHEMA_ID,
        "schema_version": _DATASET_SCHEMA_VERSION,
        "dataset_id": parameters.dataset_id,
        "dataset_version": parameters.dataset_version,
        "lottery_type": parameters.lottery_type.value,
        "rule_binding": _model_dict(rule_binding),
        "source_provenance": _model_dict(provenance),
        "draws": [
            _model_dict(
                DrawEntry(
                    draw_id=record.draw_id,
                    draw_sequence=record.draw_sequence,
                    draw_date=record.draw_date,
                    main_numbers=record.main_numbers,
                    special_numbers=record.special_numbers,
                )
            )
            for record in records
        ],
        "dataset_sha256": "0" * 64,
    }
    draft["dataset_sha256"] = canonical_json.self_key_removed_sha256(
        draft, "dataset_sha256"
    )
    return DatasetSnapshot.model_validate(draft)


def _build_manifest(
    *,
    input_sha256: str,
    source_record_count: int,
    snapshot: DatasetSnapshot,
    parameters: NormalizationParameters,
    provenance: DatasetProvenance,
    declared_implementation_oid: str | None,
) -> DatasetNormalizationManifest:
    draft: dict[str, Any] = {
        "schema_id": NORMALIZATION_MANIFEST_SCHEMA_ID,
        "schema_version": NORMALIZATION_MANIFEST_SCHEMA_VERSION,
        "source": _model_dict(provenance),
        "source_input_sha256": input_sha256,
        "source_format_id": SOURCE_FORMAT_ID,
        "source_format_version": SOURCE_FORMAT_VERSION,
        "format_definition_path": FORMAT_DEFINITION_PATH,
        "format_definition_sha256": FORMAT_DEFINITION_SHA256,
        "normalizer_id": NORMALIZER_ID,
        "normalizer_version": NORMALIZER_VERSION,
        "normalizer_contract_path": NORMALIZER_CONTRACT_PATH,
        "normalizer_contract_sha256": NORMALIZER_CONTRACT_SHA256,
        "normalization_parameters": _model_dict(parameters),
        "record_mapping_kind": RecordMappingKind.IDENTITY_ORDER_PRESERVING.value,
        "source_record_count": source_record_count,
        "accepted_record_count": source_record_count,
        "rejected_record_count": 0,
        "normalized_draw_count": len(snapshot.draws),
        "normalized_dataset_sha256": snapshot.dataset_sha256,
        "manifest_sha256": "0" * 64,
    }
    if declared_implementation_oid is not None:
        draft["normalizer_implementation_git_oid"] = declared_implementation_oid
    draft["manifest_sha256"] = canonical_json.self_key_removed_sha256(
        draft, "manifest_sha256"
    )
    return DatasetNormalizationManifest.model_validate(draft)


def _contract_failure(code: str, field: str, message: str) -> NormalizationResult:
    return _failure(
        NormalizationOutcome.NORMALIZATION_CONTRACT_FAILURE,
        [_finding(code, field, message)],
    )


def normalize(
    source_bytes: bytes,
    *,
    format_id: str,
    format_version: str,
    parameters: NormalizationParameters,
    provenance: DatasetProvenance,
    declared_implementation_oid: str | None = None,
) -> NormalizationResult:
    """Normalize supplied bytes using only arguments and closed deterministic constants."""

    if type(source_bytes) is not bytes or type(provenance) is not DatasetProvenance:
        return _contract_failure(
            "NRM_LIN_PARAMETERS_INVALID",
            "parameters",
            "normalization arguments violate the closed runtime contract",
        )
    input_sha256 = canonical_json.sha256_hex(source_bytes)
    if (
        provenance.kind is DatasetProvenanceKind.LOCAL_COMMITTED_FILE
        and input_sha256 != provenance.source_file_sha256
    ):
        return _failure(
            NormalizationOutcome.NORMALIZATION_INPUT_UNVERIFIED,
            [
                _finding(
                    "NRM_SRC_INPUT_HASH_MISMATCH",
                    "source_bytes",
                    "supplied bytes do not match LOCAL committed provenance",
                )
            ],
        )

    if format_id != SOURCE_FORMAT_ID:
        return _contract_failure(
            "NRM_SRC_FORMAT_ID_UNSUPPORTED",
            "format_id",
            "source format identifier is not supported",
        )
    if format_version != SOURCE_FORMAT_VERSION:
        return _contract_failure(
            "NRM_SRC_FORMAT_VERSION_UNSUPPORTED",
            "format_version",
            "source format version is not supported",
        )
    if (
        SOURCE_FORMAT_ID != "synthetic_draw_csv"
        or SOURCE_FORMAT_VERSION != "1.0.0"
        or NORMALIZER_ID != "lottolab_source_to_snapshot"
        or NORMALIZER_VERSION != "1.0.0"
        or FORMAT_DEFINITION_PATH
        != "contracts/normalization/formats/synthetic_draw_csv_v1.json"
        or NORMALIZER_CONTRACT_PATH
        != "docs/architecture/source-to-snapshot-normalization-contract.md"
        or _SHA256.fullmatch(FORMAT_DEFINITION_SHA256) is None
        or _SHA256.fullmatch(NORMALIZER_CONTRACT_SHA256) is None
    ):
        return _contract_failure(
            "NRM_LIN_CONTRACT_IDENTITY_MISMATCH",
            "contract_identity",
            "closed normalization contract identity is internally inconsistent",
        )
    if type(parameters) is not NormalizationParameters:
        return _contract_failure(
            "NRM_LIN_PARAMETERS_INVALID",
            "parameters",
            "normalization parameters violate the closed model",
        )
    if declared_implementation_oid is not None and (
        type(declared_implementation_oid) is not str
        or _GIT_OID.fullmatch(declared_implementation_oid) is None
    ):
        return _contract_failure(
            "NRM_LIN_IMPLEMENTATION_OID_INVALID",
            "declared_implementation_oid",
            "declared implementation object id must be 40 lowercase hex",
        )
    if parameters.lottery_type is not LotteryType.BIG_LOTTO:
        return _contract_failure(
            "NRM_RULE_UNSUPPORTED_LOTTERY",
            "lottery_type",
            "lottery type is not supported by this normalization version",
        )
    rule = resolve_lottery_rule_contract(parameters.lottery_type, LOTTERY_RULE_CONTRACTS)
    if rule is None:
        return _contract_failure(
            "NRM_RULE_CONTRACT_UNAVAILABLE",
            "lottery_type",
            "a complete active primary rule contract is unavailable",
        )

    parsed = parse_synthetic_draw_csv(source_bytes, rule=rule)
    if parsed.findings:
        return _failure(NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE, parsed.findings)
    if parsed.source_record_count != len(parsed.records):
        return _contract_failure(
            "NRM_LIN_COUNT_MISMATCH",
            "records",
            "accepted records do not mirror the complete source",
        )

    try:
        snapshot = _build_snapshot(
            parsed.records,
            parameters=parameters,
            provenance=provenance,
            rule=rule,
        )
        if snapshot.dataset_sha256 != canonical_json.self_key_removed_sha256(
            _model_dict(snapshot), "dataset_sha256"
        ):
            return _failure(
                NormalizationOutcome.NORMALIZATION_OUTPUT_HASH_MISMATCH,
                [
                    _finding(
                        "NRM_LIN_DATASET_HASH_MISMATCH",
                        "dataset_sha256",
                        "normalized dataset hash failed independent recomputation",
                    )
                ],
            )
        manifest = _build_manifest(
            input_sha256=input_sha256,
            source_record_count=parsed.source_record_count,
            snapshot=snapshot,
            parameters=parameters,
            provenance=provenance,
            declared_implementation_oid=declared_implementation_oid,
        )
    except (TypeError, ValueError):
        return _contract_failure(
            "NRM_LIN_SOURCE_MIRROR_MISMATCH",
            "normalization_output",
            "normalized output violates the closed construction contract",
        )

    if manifest.manifest_sha256 != canonical_json.self_key_removed_sha256(
        _model_dict(manifest), "manifest_sha256"
    ):
        return _failure(
            NormalizationOutcome.NORMALIZATION_OUTPUT_HASH_MISMATCH,
            [
                _finding(
                    "NRM_LIN_MANIFEST_HASH_MISMATCH",
                    "manifest_sha256",
                    "normalization manifest hash failed independent recomputation",
                )
            ],
        )
    return NormalizationResult(
        outcome=NormalizationOutcome.NORMALIZATION_PASS,
        snapshot=snapshot,
        manifest=manifest,
    )


def verify_replay(
    result: NormalizationResult,
    *,
    expected_snapshot_bytes: bytes,
    expected_manifest_bytes: bytes,
) -> NormalizationResult:
    """Require exact committed-byte replay without retaining mismatched artifacts."""

    if result.outcome is not NormalizationOutcome.NORMALIZATION_PASS:
        return result
    if result.snapshot is None or result.manifest is None:
        return result
    findings: list[NormalizationFinding] = []
    if snapshot_committed_bytes(result.snapshot) != expected_snapshot_bytes:
        findings.append(
            _finding(
                "NRM_REPLAY_SNAPSHOT_MISMATCH",
                "snapshot_bytes",
                "snapshot committed bytes do not match expected replay bytes",
            )
        )
    if manifest_committed_bytes(result.manifest) != expected_manifest_bytes:
        findings.append(
            _finding(
                "NRM_REPLAY_MANIFEST_MISMATCH",
                "manifest_bytes",
                "manifest committed bytes do not match expected replay bytes",
            )
        )
    if findings:
        return _failure(NormalizationOutcome.NORMALIZATION_OUTPUT_HASH_MISMATCH, findings)
    return result
