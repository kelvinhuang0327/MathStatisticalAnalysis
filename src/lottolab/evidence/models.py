"""Immutable, closed-schema contract models for LottoLab strategy-evaluation evidence.

These Pydantic models are the *structural* enforcement layer described in
``docs/architecture/evaluation-evidence-contract.md`` (Contract Part 10,
layer 2): field types, regex patterns, enum membership, required keys, and
strictly local, single-document shape invariants. Cross-document semantics
(hash recomputation, causality arithmetic, hit recomputation, dataset
cross-checks, definition-path containment, trust classification, and
comparability) live in :mod:`lottolab.evidence.validator` and
:mod:`lottolab.evidence.comparability`, never here.

No model in this module embeds its own content hash as a field it computes;
every ``*_sha256`` field below is a *declared* value whose correctness is
verified by the semantic validator, not by these models.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from lottolab.domain.draws import LotteryType
from lottolab.evidence.canonical_json import CanonicalizationError, validate_value_domain

_CLOSED_FROZEN = ConfigDict(extra="forbid", frozen=True)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID_HEX = re.compile(r"^[0-9a-f]{40}$")
_CANONICAL_DECIMAL = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")


def _validate_sha256(value: str) -> str:
    if _SHA256_HEX.fullmatch(value) is None:
        raise ValueError("must be a 64-character lowercase hexadecimal SHA-256 digest")
    return value


def _validate_git_oid(value: str) -> str:
    if _GIT_OID_HEX.fullmatch(value) is None:
        raise ValueError("must be a 40-character lowercase hexadecimal Git object id")
    return value


def _validate_canonical_decimal(value: str) -> str:
    if _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise ValueError(
            "must be a canonical decimal string: optional leading '-', no leading zero "
            "(except '0' itself), no '+', no exponent"
        )
    if value.startswith("-"):
        digits_only = value[1:].replace(".", "")
        if set(digits_only) <= {"0"}:
            raise ValueError("negative zero is forbidden")
    return value


def _validate_definition_path_lexical(value: str) -> str:
    """Pure lexical containment pre-check — no filesystem access.

    Full containment (symlink resolution against the repository root),
    status-based root restriction, and protected-path rejection happen in
    :mod:`lottolab.evidence.validator`, which alone knows the repository
    root at runtime.
    """

    if not value:
        raise ValueError("definition path must not be empty")
    if value.startswith("/"):
        raise ValueError("definition path must not be absolute")
    if "\\" in value:
        raise ValueError("definition path must not contain a backslash")
    if re.match(r"^[A-Za-z]:", value):
        raise ValueError("definition path must not contain a drive prefix")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError("definition path must not contain empty, '.', or '..' segments")
    return value


def _validate_lcj1_object(value: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_value_domain(value)
    except CanonicalizationError as exc:
        raise ValueError(str(exc)) from exc
    return value


Sha256Hex = Annotated[str, AfterValidator(_validate_sha256)]
GitOidHex = Annotated[str, AfterValidator(_validate_git_oid)]
CanonicalDecimal = Annotated[str, AfterValidator(_validate_canonical_decimal)]
DefinitionPath = Annotated[str, AfterValidator(_validate_definition_path_lexical)]
Lcj1Object = Annotated[dict[str, Any], AfterValidator(_validate_lcj1_object)]


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]


# --------------------------------------------------------------------------
# Enums (Contract Parts 3, 4, 6, 8, 9, 10)
# --------------------------------------------------------------------------


class EvidenceStatus(StrEnum):
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
    DRAFT = "DRAFT"
    CANONICAL = "CANONICAL"


class PolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class EvidenceTrustClass(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    UNTRUSTED_DECLARED = "UNTRUSTED_DECLARED"
    REGISTERED_CANONICAL = "REGISTERED_CANONICAL"


class PolicyTrustClass(StrEnum):
    UNTRUSTED_DECLARED = "UNTRUSTED_DECLARED"
    REGISTERED_APPROVED = "REGISTERED_APPROVED"


class DatasetProvenanceKind(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    LOCAL_COMMITTED_FILE = "LOCAL_COMMITTED_FILE"
    EXTERNAL_DECLARED = "EXTERNAL_DECLARED"


class EvaluationMode(StrEnum):
    EX_ANTE = "EX_ANTE"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"


class EvaluationProtocol(StrEnum):
    WALK_FORWARD = "WALK_FORWARD"
    ONE_SHOT = "ONE_SHOT"


class ParameterSelectionMode(StrEnum):
    FIXED = "FIXED"
    PER_STEP_REFIT = "PER_STEP_REFIT"


class MissingDrawPolicy(StrEnum):
    """Closed for this foundation task: dataset snapshots already forbid gaps outright."""

    STRICT_NONE_TOLERATED = "STRICT_NONE_TOLERATED"


class DuplicateDrawPolicy(StrEnum):
    """Closed for this foundation task: dataset snapshots already forbid duplicates outright."""

    STRICT_NONE_TOLERATED = "STRICT_NONE_TOLERATED"


class OutcomeSource(StrEnum):
    """Closed for this foundation task: outcomes resolve only from the supplied snapshot."""

    DATASET_SNAPSHOT = "DATASET_SNAPSHOT"


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"


class SampleUnit(StrEnum):
    DRAWS = "DRAWS"
    TICKETS = "TICKETS"


class FormulaStatus(StrEnum):
    DEFINED = "DEFINED"
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"


class MetricValueStatus(StrEnum):
    VALUE_PRESENT = "VALUE_PRESENT"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"


class HashVerificationState(StrEnum):
    VERIFIED_MATCH = "VERIFIED_MATCH"
    VERIFIED_MISMATCH = "VERIFIED_MISMATCH"
    NOT_VERIFIABLE_INPUT_ABSENT = "NOT_VERIFIABLE_INPUT_ABSENT"


class CandidateCountPolicy(StrEnum):
    REQUIRE_EQUAL = "REQUIRE_EQUAL"
    ALLOW_ANY = "ALLOW_ANY"


class ParameterPolicy(StrEnum):
    """``PINNED_HASH`` is the only value in this task (Contract Part 9)."""

    PINNED_HASH = "PINNED_HASH"


class MissingEvidenceBehavior(StrEnum):
    TREAT_AS_INELIGIBLE = "TREAT_AS_INELIGIBLE"


class FindingCategory(StrEnum):
    SCHEMA_FAILURE = "SCHEMA_FAILURE"
    SEMANTIC_FAILURE = "SEMANTIC_FAILURE"
    HASH_MISMATCH = "HASH_MISMATCH"
    CAUSAL_VIOLATION = "CAUSAL_VIOLATION"
    UNVERIFIED_PROVENANCE = "UNVERIFIED_PROVENANCE"
    METRIC_DEFINITION_FAILURE = "METRIC_DEFINITION_FAILURE"
    COMPARABILITY_FAILURE = "COMPARABILITY_FAILURE"
    AUTHORITY_FAILURE = "AUTHORITY_FAILURE"


#: Fixed, non-configurable comparability-dimension vocabulary (Contract Part 9).
SHARED_ENVIRONMENT_DIMENSIONS: tuple[str, ...] = (
    "lottery_type",
    "dataset_sha256",
    "evaluation_mode",
    "evaluation_protocol",
    "evaluation_window",
    "metric_identity",
    "sample_unit",
    "candidate_count_conformance",
)

PER_STRATEGY_IDENTITY_DIMENSIONS: tuple[str, ...] = (
    "strategy_identity",
    "method_identity",
    "feature_version",
    "parameters_sha256",
)


# --------------------------------------------------------------------------
# Shared sub-models
# --------------------------------------------------------------------------


class RuleParameters(BaseModel):
    """Generic lottery-rule binding, self-hashed (Contract Parts 2 and 5)."""

    model_config = _CLOSED_FROZEN

    main_number_count: int = Field(gt=0)
    main_number_min: int
    main_number_max: int
    main_numbers_unique: bool
    special_number_count: int = Field(ge=0)
    special_number_min: int
    special_number_max: int
    special_numbers_unique: bool
    main_special_overlap_allowed: bool
    rule_contract_version: str = Field(min_length=1)
    rule_parameters_sha256: Sha256Hex

    @model_validator(mode="after")
    def _check_ranges(self) -> RuleParameters:
        if self.main_number_min > self.main_number_max:
            raise ValueError("main number range is inverted")
        main_capacity = self.main_number_max - self.main_number_min + 1
        if self.main_numbers_unique and self.main_number_count > main_capacity:
            raise ValueError("unique main numbers exceed the configured range")
        if self.special_number_min > self.special_number_max:
            raise ValueError("special number range is inverted")
        special_capacity = self.special_number_max - self.special_number_min + 1
        if self.special_numbers_unique and self.special_number_count > special_capacity:
            raise ValueError("unique special numbers exceed the configured range")
        return self


class DrawRef(BaseModel):
    """Identity + sequence + date for one referenced draw."""

    model_config = _CLOSED_FROZEN

    draw_id: str = Field(min_length=1)
    draw_sequence: int = Field(ge=0)
    draw_date: date


class DatasetProvenance(BaseModel):
    model_config = _CLOSED_FROZEN

    kind: DatasetProvenanceKind
    source_definition_path: DefinitionPath | None = None
    source_git_oid: GitOidHex | None = None
    source_file_sha256: Sha256Hex | None = None
    declared_description: str | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> DatasetProvenance:
        local_fields = (self.source_definition_path, self.source_git_oid, self.source_file_sha256)
        if self.kind is DatasetProvenanceKind.LOCAL_COMMITTED_FILE:
            if any(field is None for field in local_fields):
                raise ValueError(
                    "LOCAL_COMMITTED_FILE provenance requires source_definition_path, "
                    "source_git_oid, and source_file_sha256"
                )
        elif any(field is not None for field in local_fields):
            raise ValueError(
                "only LOCAL_COMMITTED_FILE provenance may declare "
                "source_definition_path, source_git_oid, or source_file_sha256"
            )
        return self


# --------------------------------------------------------------------------
# Dataset snapshot (Contract Part 4)
# --------------------------------------------------------------------------


class DrawEntry(BaseModel):
    model_config = _CLOSED_FROZEN

    draw_id: str = Field(min_length=1)
    draw_sequence: int = Field(ge=0)
    draw_date: date
    main_numbers: tuple[int, ...] = Field(min_length=1)
    special_numbers: tuple[int, ...] = Field(default_factory=tuple)


class DatasetSnapshot(BaseModel):
    model_config = _CLOSED_FROZEN

    schema_id: str = Field(pattern=r"^lottolab\.evidence\.dataset_snapshot$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    lottery_type: LotteryType
    rule_binding: RuleParameters
    source_provenance: DatasetProvenance
    draws: tuple[DrawEntry, ...] = Field(min_length=1)
    dataset_sha256: Sha256Hex

    @model_validator(mode="after")
    def _check_synthetic_id_prefix(self) -> DatasetSnapshot:
        is_synthetic = self.source_provenance.kind is DatasetProvenanceKind.SYNTHETIC
        has_synthetic_prefix = self.dataset_id.startswith("SYNTHETIC_")
        if is_synthetic != has_synthetic_prefix:
            raise ValueError(
                "dataset_id must start with 'SYNTHETIC_' if and only if "
                "source_provenance.kind is SYNTHETIC"
            )
        return self


# --------------------------------------------------------------------------
# Metric definitions and results (Contract Part 8)
# --------------------------------------------------------------------------


class MetricDefinition(BaseModel):
    """A metric-definition document. Never embeds its own content hash."""

    model_config = _CLOSED_FROZEN

    schema_id: str = Field(pattern=r"^lottolab\.evidence\.metric_definition$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    metric_id: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    direction: MetricDirection
    unit: str = Field(min_length=1)
    aggregation: str = Field(min_length=1)
    sample_unit: SampleUnit
    decimal_scale: int = Field(ge=0, le=12)
    rounding_mode: str = Field(pattern=r"^ROUND_HALF_EVEN$")
    formula_status: FormulaStatus
    definition_prose: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_reserved_direction(self) -> MetricDefinition:
        if (
            self.formula_status is FormulaStatus.RESERVED_UNAVAILABLE
            and self.direction is not MetricDirection.DESCRIPTIVE_ONLY
        ):
            raise ValueError(
                "a RESERVED_UNAVAILABLE metric must declare direction=DESCRIPTIVE_ONLY"
            )
        return self


class MetricResult(BaseModel):
    model_config = _CLOSED_FROZEN

    metric_id: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    metric_definition_path: DefinitionPath
    metric_definition_sha256: Sha256Hex
    sample_size: int = Field(ge=0)
    sample_unit: SampleUnit
    aggregation: str = Field(min_length=1)
    value_status: MetricValueStatus
    value: CanonicalDecimal | None = None
    reason_code: str | None = None
    verification_state: str = Field(pattern=r"^DECLARED_NOT_RECOMPUTED$")

    @model_validator(mode="after")
    def _check_value_shape(self) -> MetricResult:
        if self.value_status is MetricValueStatus.VALUE_PRESENT:
            if self.value is None:
                raise ValueError("VALUE_PRESENT requires a canonical value")
            if self.reason_code is not None:
                raise ValueError("VALUE_PRESENT must not declare a reason_code")
        else:
            if self.reason_code is None:
                raise ValueError("NOT_COMPUTABLE requires a reason_code")
            if self.value is not None:
                raise ValueError("NOT_COMPUTABLE must not declare a value")
        return self


# --------------------------------------------------------------------------
# Strategy evaluation evidence (Contract Parts 5, 6, 7)
# --------------------------------------------------------------------------


class DatasetReference(BaseModel):
    model_config = _CLOSED_FROZEN

    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_sha256: Sha256Hex
    lottery_type: LotteryType
    draw_count: int = Field(ge=1)
    first_draw: DrawRef
    last_draw: DrawRef


class SequenceWindow(BaseModel):
    model_config = _CLOSED_FROZEN

    start_sequence: int = Field(ge=0)
    end_sequence: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> SequenceWindow:
        if self.start_sequence > self.end_sequence:
            raise ValueError("start_sequence must not be after end_sequence")
        return self


class EvaluationWindows(BaseModel):
    model_config = _CLOSED_FROZEN

    evaluation_window: SequenceWindow
    training_window: SequenceWindow
    parameter_selection_mode: ParameterSelectionMode
    parameter_selection_window: SequenceWindow | None = None
    minimum_history: int = Field(ge=1)
    missing_draw_policy: MissingDrawPolicy
    duplicate_draw_policy: DuplicateDrawPolicy
    maximum_data_cutoff: DrawRef
    walk_forward_cutoff_lag: int | None = Field(default=None, gt=0)
    one_shot_cutoff: DrawRef | None = None

    @model_validator(mode="after")
    def _check_parameter_selection_window_presence(self) -> EvaluationWindows:
        if self.parameter_selection_mode is ParameterSelectionMode.FIXED:
            if self.parameter_selection_window is None:
                raise ValueError("FIXED parameter selection requires parameter_selection_window")
        elif self.parameter_selection_window is not None:
            raise ValueError("PER_STEP_REFIT must not declare a parameter_selection_window")
        return self


class Ticket(BaseModel):
    model_config = _CLOSED_FROZEN

    ticket_id: str = Field(min_length=1)
    main_numbers: tuple[int, ...] = Field(min_length=1)
    special_numbers: tuple[int, ...] = Field(default_factory=tuple)
    main_hit_count: int = Field(ge=0)
    special_hit: int | bool


class EvaluationRecord(BaseModel):
    model_config = _CLOSED_FROZEN

    target: DrawRef
    cutoff: DrawRef
    tickets: tuple[Ticket, ...] = Field(min_length=1)
    actual_main_numbers: tuple[int, ...] = Field(min_length=1)
    actual_special_numbers: tuple[int, ...] = Field(default_factory=tuple)
    outcome_source: OutcomeSource
    record_sha256: Sha256Hex


class StrategyEvaluationEvidence(BaseModel):
    model_config = _CLOSED_FROZEN

    schema_id: str = Field(pattern=r"^lottolab\.evidence\.strategy_evaluation_evidence$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")

    # Artifact identity
    artifact_id: str = Field(min_length=1)
    evidence_status: EvidenceStatus
    produced_at: UtcDatetime
    producer_name: str = Field(min_length=1)
    producer_git_oid: GitOidHex | None = None
    artifact_content_sha256: Sha256Hex

    # Strategy and method identity
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    method_source_git_oid: GitOidHex
    feature_version: str = Field(min_length=1)
    feature_definition_path: DefinitionPath
    feature_definition_sha256: Sha256Hex
    parameters: Lcj1Object
    parameters_sha256: Sha256Hex

    # Dataset reference and rule binding
    dataset_reference: DatasetReference
    rule_parameters: RuleParameters

    # Evaluation mode, protocol, causality
    evaluation_mode: EvaluationMode
    evaluation_protocol: EvaluationProtocol
    evaluation_windows: EvaluationWindows

    # Per-draw records
    records: tuple[EvaluationRecord, ...] = Field(min_length=1)

    # Metric results
    metric_results: tuple[MetricResult, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_protocol_shape(self) -> StrategyEvaluationEvidence:
        windows = self.evaluation_windows
        if self.evaluation_protocol is EvaluationProtocol.WALK_FORWARD:
            if windows.walk_forward_cutoff_lag is None:
                raise ValueError("WALK_FORWARD requires evaluation_windows.walk_forward_cutoff_lag")
            if windows.one_shot_cutoff is not None:
                raise ValueError("WALK_FORWARD must not declare evaluation_windows.one_shot_cutoff")
        else:  # ONE_SHOT
            if windows.one_shot_cutoff is None:
                raise ValueError("ONE_SHOT requires evaluation_windows.one_shot_cutoff")
            if windows.walk_forward_cutoff_lag is not None:
                raise ValueError(
                    "ONE_SHOT must not declare evaluation_windows.walk_forward_cutoff_lag"
                )
            if windows.parameter_selection_mode is ParameterSelectionMode.PER_STEP_REFIT:
                raise ValueError("PER_STEP_REFIT is allowed only with WALK_FORWARD protocol")
        return self

    @model_validator(mode="after")
    def _check_synthetic_id_prefix(self) -> StrategyEvaluationEvidence:
        is_synthetic = self.evidence_status is EvidenceStatus.SYNTHETIC_TEST_ONLY
        has_synthetic_prefix = self.artifact_id.startswith("SYNTHETIC_")
        if is_synthetic and not has_synthetic_prefix:
            raise ValueError(
                "SYNTHETIC_TEST_ONLY evidence requires an artifact_id starting with 'SYNTHETIC_'"
            )
        return self


# --------------------------------------------------------------------------
# Ranking policy and comparability (Contract Part 9)
# --------------------------------------------------------------------------


class ComparabilityDimensions(BaseModel):
    """Echoes the fixed, non-configurable comparability vocabulary for audit clarity.

    Both tuples are validated to exactly equal the module-level fixed
    constants; a policy cannot redefine what counts as comparable.
    """

    model_config = _CLOSED_FROZEN

    shared_environment: tuple[str, ...]
    per_strategy_identity: tuple[str, ...]

    @model_validator(mode="after")
    def _check_fixed_vocabulary(self) -> ComparabilityDimensions:
        if self.shared_environment != SHARED_ENVIRONMENT_DIMENSIONS:
            raise ValueError(
                "shared_environment must exactly equal the fixed contract dimension list"
            )
        if self.per_strategy_identity != PER_STRATEGY_IDENTITY_DIMENSIONS:
            raise ValueError(
                "per_strategy_identity must exactly equal the fixed contract dimension list"
            )
        return self


class RankingPolicy(BaseModel):
    model_config = _CLOSED_FROZEN

    schema_id: str = Field(pattern=r"^lottolab\.evidence\.ranking_policy$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    declared_status: PolicyStatus
    primary_metric_id: str = Field(min_length=1)
    primary_metric_version: str = Field(min_length=1)
    primary_metric_definition_sha256: Sha256Hex
    minimum_sample_size: int = Field(ge=0)
    required_evidence_trust: EvidenceTrustClass
    eligible_evaluation_modes: tuple[EvaluationMode, ...] = Field(min_length=1)
    required_lottery_type: LotteryType
    candidate_count_policy: CandidateCountPolicy
    parameter_policy: ParameterPolicy
    comparability_dimensions: ComparabilityDimensions
    tie_breakers: tuple[str, ...] = Field(min_length=1)
    missing_evidence_behavior: MissingEvidenceBehavior
    ineligibility_reason_codes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_tie_breaker_termination(self) -> RankingPolicy:
        if self.tie_breakers[-1] != "strategy_id":
            raise ValueError("tie_breakers must terminate with lexicographic strategy_id")
        return self
