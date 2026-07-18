"""Closed models for deterministic source-to-snapshot normalization."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from lottolab.domain.draws import LotteryType
from lottolab.evidence.canonical_json import self_key_removed_sha256
from lottolab.evidence.models import DatasetProvenance, DatasetProvenanceKind, DatasetSnapshot

NORMALIZATION_MANIFEST_SCHEMA_ID = "lottolab.normalization.dataset_normalization_manifest"
NORMALIZATION_MANIFEST_SCHEMA_VERSION = "1.0.0"
SOURCE_FORMAT_ID = "synthetic_draw_csv"
SOURCE_FORMAT_VERSION = "1.0.0"
NORMALIZER_ID = "lottolab_source_to_snapshot"
NORMALIZER_VERSION = "1.0.0"
FORMAT_DEFINITION_PATH = "contracts/normalization/formats/synthetic_draw_csv_v1.json"
NORMALIZER_CONTRACT_PATH = "docs/architecture/source-to-snapshot-normalization-contract.md"

_CLOSED_FROZEN = ConfigDict(extra="forbid", frozen=True)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID_HEX = re.compile(r"^[0-9a-f]{40}$")
_REASON_CODE = re.compile(r"^NRM_(?:SRC|REC|DUP|RULE|SEQ|LIN|REPLAY)_[A-Z0-9_]+$")
_FINDING_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


def _validate_sha256(value: str) -> str:
    if _SHA256_HEX.fullmatch(value) is None:
        raise ValueError("must be a 64-character lowercase hexadecimal SHA-256 digest")
    return value


def _validate_git_oid(value: str) -> str:
    if _GIT_OID_HEX.fullmatch(value) is None:
        raise ValueError("must be a 40-character lowercase hexadecimal Git object id")
    return value


def _validate_reason_code(value: str) -> str:
    if _REASON_CODE.fullmatch(value) is None:
        raise ValueError("reason_code is outside the closed normalization namespace")
    return value


def _validate_finding_field(value: str) -> str:
    if _FINDING_FIELD.fullmatch(value) is None:
        raise ValueError("field must be a stable lowercase identifier")
    return value


def _validate_finding_message(value: str) -> str:
    if not value.isascii() or any(ord(character) < 0x20 for character in value):
        raise ValueError("message must contain printable ASCII only")
    return value


Sha256Hex = Annotated[str, AfterValidator(_validate_sha256)]
GitOidHex = Annotated[str, AfterValidator(_validate_git_oid)]
ReasonCode = Annotated[str, AfterValidator(_validate_reason_code)]
FindingField = Annotated[str, AfterValidator(_validate_finding_field)]
FindingMessage = Annotated[str, AfterValidator(_validate_finding_message)]


class NormalizationParameters(BaseModel):
    """The complete, closed parameter set that affects normalized content."""

    model_config = _CLOSED_FROZEN

    dataset_id: str = Field(min_length=1, max_length=128)
    dataset_version: str = Field(min_length=1, max_length=64)
    lottery_type: LotteryType


class RecordMappingKind(StrEnum):
    IDENTITY_ORDER_PRESERVING = "IDENTITY_ORDER_PRESERVING"


class NormalizationOutcome(StrEnum):
    NORMALIZATION_PASS = "NORMALIZATION_PASS"
    NORMALIZATION_INPUT_UNVERIFIED = "NORMALIZATION_INPUT_UNVERIFIED"
    NORMALIZATION_CONTRACT_FAILURE = "NORMALIZATION_CONTRACT_FAILURE"
    NORMALIZATION_REJECTED_SOURCE = "NORMALIZATION_REJECTED_SOURCE"
    NORMALIZATION_OUTPUT_HASH_MISMATCH = "NORMALIZATION_OUTPUT_HASH_MISMATCH"


class NormalizationFinding(BaseModel):
    """A deterministic, sanitized normalization finding."""

    model_config = _CLOSED_FROZEN

    reason_code: ReasonCode = Field(max_length=96)
    source_record_ordinal: int = Field(ge=0)
    field: FindingField = Field(max_length=64)
    message: FindingMessage = Field(min_length=1, max_length=192)


class DatasetNormalizationManifest(BaseModel):
    """Timeless derivation identity kept separate from DatasetSnapshot."""

    model_config = _CLOSED_FROZEN

    schema_id: Literal["lottolab.normalization.dataset_normalization_manifest"]
    schema_version: Literal["1.0.0"]
    source: DatasetProvenance
    source_input_sha256: Sha256Hex
    source_format_id: Literal["synthetic_draw_csv"]
    source_format_version: Literal["1.0.0"]
    format_definition_path: Literal[
        "contracts/normalization/formats/synthetic_draw_csv_v1.json"
    ]
    format_definition_sha256: Sha256Hex
    normalizer_id: Literal["lottolab_source_to_snapshot"]
    normalizer_version: Literal["1.0.0"]
    normalizer_contract_path: Literal[
        "docs/architecture/source-to-snapshot-normalization-contract.md"
    ]
    normalizer_contract_sha256: Sha256Hex
    normalizer_implementation_git_oid: GitOidHex | None = None
    normalization_parameters: NormalizationParameters
    record_mapping_kind: Literal[RecordMappingKind.IDENTITY_ORDER_PRESERVING]
    source_record_count: int = Field(gt=0)
    accepted_record_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    normalized_draw_count: int = Field(ge=0)
    normalized_dataset_sha256: Sha256Hex
    manifest_sha256: Sha256Hex

    @model_validator(mode="after")
    def _check_pass_invariants(self) -> DatasetNormalizationManifest:
        if self.accepted_record_count != self.source_record_count:
            raise ValueError("accepted_record_count must equal source_record_count")
        if self.rejected_record_count != 0:
            raise ValueError("rejected_record_count must be zero")
        if self.normalized_draw_count != self.accepted_record_count:
            raise ValueError("normalized_draw_count must equal accepted_record_count")
        if (
            self.source.kind is DatasetProvenanceKind.LOCAL_COMMITTED_FILE
            and self.source_input_sha256 != self.source.source_file_sha256
        ):
            raise ValueError("LOCAL source_input_sha256 must equal source_file_sha256")
        dumped = self.model_dump(mode="json", exclude_none=True)
        recomputed = self_key_removed_sha256(dumped, "manifest_sha256")
        if self.manifest_sha256 != recomputed:
            raise ValueError("manifest_sha256 does not match self-key-removed content")
        return self


class NormalizationResult(BaseModel):
    """Runtime-only result; failed outcomes never expose partial artifacts."""

    model_config = _CLOSED_FROZEN

    outcome: NormalizationOutcome
    findings: tuple[NormalizationFinding, ...] = ()
    snapshot: DatasetSnapshot | None = None
    manifest: DatasetNormalizationManifest | None = None

    @model_validator(mode="after")
    def _check_result_shape(self) -> NormalizationResult:
        ordered = tuple(
            sorted(
                self.findings,
                key=lambda finding: (
                    finding.source_record_ordinal,
                    finding.reason_code,
                    finding.field,
                ),
            )
        )
        if self.findings != ordered:
            raise ValueError("findings must use deterministic contract order")
        if self.outcome is NormalizationOutcome.NORMALIZATION_PASS:
            if self.findings:
                raise ValueError("NORMALIZATION_PASS must not contain findings")
            if self.snapshot is None or self.manifest is None:
                raise ValueError("NORMALIZATION_PASS requires snapshot and manifest")
            if self.manifest.normalized_dataset_sha256 != self.snapshot.dataset_sha256:
                raise ValueError("manifest dataset hash must equal snapshot dataset hash")
            if self.manifest.source != self.snapshot.source_provenance:
                raise ValueError("manifest source must mirror snapshot provenance")
            if self.manifest.normalized_draw_count != len(self.snapshot.draws):
                raise ValueError("manifest normalized count must equal snapshot draw count")
        else:
            if self.snapshot is not None or self.manifest is not None:
                raise ValueError("failed normalization must not expose artifacts")
            if not self.findings:
                raise ValueError("failed normalization requires at least one finding")
        return self
