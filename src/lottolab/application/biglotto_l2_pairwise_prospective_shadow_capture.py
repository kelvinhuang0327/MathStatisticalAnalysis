"""Outcome-free prospective capture and create-once sealing for one Big Lotto target.

The common core accepts an immutable causal history and injected candidate runtimes,
durably proves official-outcome absence before producers, times each ordered emission,
seals one canonical bundle, proves absence again, and seals a final capture receipt.
Outcome values, scoring, and reporting deliberately have no port here.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.pre_outcome_target import OutcomePresenceAttestation, TargetAnnouncement
from lottolab.domain.prospective_observer import (
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.evidence.canonical_json import (
    MAX_SAFE_INTEGER,
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
    sha256_hex,
)
from lottolab.evidence.ordered_candidate_emission_artifact import (
    build_ordered_candidate_emission_artifact,
)

BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION = (
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_R1"
)
BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION = (
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_R1"
)
BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_SCHEMA_VERSION = (
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_R1"
)
BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_SCHEMA_VERSION = (
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_R1"
)
BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_ELIGIBILITY_FLOOR = 115000082
BIGLOTTO_L2_PAIRWISE_COMMON_MINIMUM_HISTORY_ROWS = 751
BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_COUNT = 9
BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS = (
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C8",
    "C9",
    "C10",
)
BIGLOTTO_L2_PAIRWISE_SEALED_STAGE = "PREDICTION_BUNDLE_SEALED_STOP"

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_REPOSITORY_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", flags=re.ASCII)
_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_CANDIDATE_ID = re.compile(r"[A-Z][A-Z0-9_]{0,63}", flags=re.ASCII)
_MAX_BUNDLE_BYTES = 4 * 1024 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)

_RECORD_KEYS = {
    "candidate_id",
    "generated_at_utc",
    "history_cutoff",
    "history_row_count",
    "lottery_type",
    "method_id",
    "prediction_payload_sha256",
    "repository_head",
    "repository_tree",
    "schema_version",
    "semantic_signature",
    "strategy_version",
    "target_announcement",
    "target_announcement_sha256",
    "target_draw",
    "ticket",
}
_BUNDLE_KEYS = {
    "bundle_sha256",
    "expected_candidate_ids",
    "generated_at_utc",
    "history_cutoff",
    "history_row_count",
    "lottery_type",
    "predictions",
    "repository_head",
    "repository_tree",
    "schema_version",
    "stage",
    "target_announcement",
    "target_announcement_sha256",
    "target_draw",
}
_PRE_RECEIPT_KEYS = {
    "history_cutoff",
    "lottery_type",
    "outcome_absence_checked_at_utc",
    "outcome_absence_attestation",
    "outcome_absent",
    "receipt_payload_sha256",
    "repository_head",
    "repository_tree",
    "scheduled_draw_at_utc",
    "schema_version",
    "target_announcement",
    "target_announcement_sha256",
    "target_draw",
}
_FINAL_RECEIPT_KEYS = {
    "capture_sealed_at_utc",
    "capture_started_at_utc",
    "embedded_bundle_sha256",
    "final_outcome_absence_attestation",
    "final_outcome_absence_checked_at_utc",
    "final_outcome_absent",
    "history_cutoff",
    "lottery_type",
    "per_candidate_runtime_ns",
    "pre_producer_receipt_sha256",
    "receipt_payload_sha256",
    "repository_head",
    "repository_tree",
    "scheduled_draw_at_utc",
    "schema_version",
    "sealed_bundle_file_sha256",
    "target_announcement",
    "target_announcement_sha256",
    "target_draw",
    "total_capture_runtime_ns",
}
_CANDIDATE_RUNTIME_KEYS = {"candidate_id", "runtime_ns"}


class ProspectiveShadowCaptureError(RuntimeError):
    """Base error for the prospective capture boundary."""


class ProspectiveShadowBundleConflictError(ProspectiveShadowCaptureError):
    """A target already has different immutable bundle authority."""


class ProspectiveShadowBundleStoreError(ProspectiveShadowCaptureError):
    """The create-once bundle store failed closed."""


class ProspectiveShadowBundleVerificationError(ValueError):
    """Canonical bundle bytes violate the closed R1 contract."""


class ProspectiveShadowBundleShapeError(ProspectiveShadowBundleVerificationError):
    """Bundle bytes do not have the exact closed R1 shape."""


class ProspectiveShadowBundleTamperError(ProspectiveShadowBundleVerificationError):
    """A declared digest does not match its canonical payload."""


class ProspectiveShadowReceiptVerificationError(ValueError):
    """Canonical capture-receipt bytes violate the closed evidence contract."""


class ProspectiveShadowReceiptShapeError(ProspectiveShadowReceiptVerificationError):
    """Capture-receipt bytes do not have the exact closed shape."""


class ProspectiveShadowReceiptTamperError(ProspectiveShadowReceiptVerificationError):
    """A capture-receipt digest or referenced artifact does not match."""


class ProspectiveShadowOutcomeAvailableError(ProspectiveShadowCaptureError):
    """Official outcome presence makes the attempted capture non-countable."""


class ProspectiveShadowIncompleteEvidenceError(ProspectiveShadowCaptureError):
    """Partial evidence exists and cannot be completed by reconstructing timing facts."""


class ProspectiveShadowSealStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_EXISTING = "EXACT_IDEMPOTENT_EXISTING"


@runtime_checkable
class ProspectiveCandidateProducer(Protocol):
    """Injected prediction-only runtime; target rows are never part of ``history``."""

    def __call__(
        self,
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission: ...


@runtime_checkable
class ProspectiveOutcomePresenceProbe(Protocol):
    """Presence-only official source port; outcome values never cross this boundary."""

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation: ...


@dataclass(frozen=True, slots=True)
class ProspectiveCandidateRuntime:
    """Frozen identity plus one injected, prediction-only callable."""

    candidate_id: str
    method_id: str
    semantic_signature: str
    strategy_version: str
    producer: ProspectiveCandidateProducer

    def __post_init__(self) -> None:
        _require_candidate_id(self.candidate_id)
        _require_canonical_text(self.method_id, "method_id")
        _require_sha256(self.semantic_signature, "semantic_signature")
        _require_canonical_text(self.strategy_version, "strategy_version")
        if not callable(self.producer):
            raise ValueError("producer must be callable")


@dataclass(frozen=True, slots=True)
class ProspectiveShadowCaptureRequest:
    """All authority supplied to one deterministic pre-draw capture."""

    announcement: TargetAnnouncement
    history: tuple[object, ...]
    history_cutoff: str
    expected_candidate_ids: tuple[str, ...]
    candidate_runtimes: tuple[ProspectiveCandidateRuntime, ...]
    generated_at_utc: datetime
    repository_head: str
    repository_tree: str

    def __post_init__(self) -> None:
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        if self.announcement.target.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("the capture layer accepts only BIG_LOTTO targets")
        if int(self.announcement.target.draw_number) < (
            BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_ELIGIBILITY_FLOOR
        ):
            raise ValueError("target draw is below the prospective eligibility floor")
        if type(self.history) is not tuple:
            raise ValueError("history must be an immutable tuple")
        if len(self.history) < BIGLOTTO_L2_PAIRWISE_COMMON_MINIMUM_HISTORY_ROWS:
            raise ValueError("history does not satisfy the common nine-candidate minimum")
        _require_history_cutoff(self.history_cutoff, self.announcement.target.draw_number)
        _require_candidate_ids(self.expected_candidate_ids)
        if type(self.candidate_runtimes) is not tuple or any(
            type(runtime) is not ProspectiveCandidateRuntime for runtime in self.candidate_runtimes
        ):
            raise ValueError("candidate_runtimes must be an immutable typed tuple")
        runtime_ids = tuple(runtime.candidate_id for runtime in self.candidate_runtimes)
        if len(runtime_ids) != len(set(runtime_ids)):
            raise ValueError("candidate_runtimes contain duplicate candidate_id values")
        if set(runtime_ids) != set(self.expected_candidate_ids):
            raise ValueError("candidate_runtimes must match the exact expected candidate set")
        _require_exact_utc(self.generated_at_utc, "generated_at_utc")
        if self.generated_at_utc < self.announcement.source.observed_at:
            raise ValueError("capture cannot precede the target announcement observation")
        if self.generated_at_utc >= self.announcement.scheduled_at:
            raise ValueError("capture must finish strictly before the announced draw time")
        _require_repository_oid(self.repository_head, "repository_head")
        _require_repository_oid(self.repository_tree, "repository_tree")


@dataclass(frozen=True, slots=True)
class ProspectiveCandidateRuntimeNs:
    """Exact observational runtime for one candidate, outside prediction identity."""

    candidate_id: str
    runtime_ns: int

    def __post_init__(self) -> None:
        _require_candidate_id(self.candidate_id)
        _require_nonnegative_lcj_integer(self.runtime_ns, "runtime_ns")

    def canonical_dict(self) -> dict[str, object]:
        return {"candidate_id": self.candidate_id, "runtime_ns": self.runtime_ns}


@dataclass(frozen=True, slots=True)
class ProspectiveShadowPreProducerReceipt:
    """Durable proof that official outcome data was absent before producers ran."""

    schema_version: str
    lottery_type: LotteryType
    target_draw: str
    target_announcement: TargetAnnouncement
    target_announcement_sha256: str
    scheduled_draw_at_utc: datetime
    history_cutoff: str
    outcome_absent: bool
    outcome_absence_checked_at_utc: datetime
    outcome_absence_attestation: OutcomePresenceAttestation
    repository_head: str
    repository_tree: str
    receipt_payload_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != (BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_SCHEMA_VERSION):
            raise ValueError("unsupported prospective pre-producer receipt schema")
        _require_receipt_target_authority(
            lottery_type=self.lottery_type,
            target_draw=self.target_draw,
            target_announcement=self.target_announcement,
            target_announcement_sha256=self.target_announcement_sha256,
            scheduled_draw_at_utc=self.scheduled_draw_at_utc,
            history_cutoff=self.history_cutoff,
            repository_head=self.repository_head,
            repository_tree=self.repository_tree,
        )
        if self.outcome_absent is not True:
            raise ValueError("pre-producer receipt requires outcome_absent=true")
        _require_absent_attestation(
            self.outcome_absence_attestation,
            target=self.target_announcement.target,
            checked_at=self.outcome_absence_checked_at_utc,
            scheduled_at=self.scheduled_draw_at_utc,
        )
        _require_sha256(self.receipt_payload_sha256, "receipt_payload_sha256")
        if self.receipt_payload_sha256 != self_key_removed_sha256(
            self.canonical_dict(),
            "receipt_payload_sha256",
        ):
            raise ProspectiveShadowReceiptTamperError(
                "pre-producer receipt digest does not match its canonical payload"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "history_cutoff": self.history_cutoff,
            "lottery_type": self.lottery_type.value,
            "outcome_absence_attestation": (self.outcome_absence_attestation.canonical_dict()),
            "outcome_absence_checked_at_utc": _utc_text(self.outcome_absence_checked_at_utc),
            "outcome_absent": self.outcome_absent,
            "receipt_payload_sha256": self.receipt_payload_sha256,
            "repository_head": self.repository_head,
            "repository_tree": self.repository_tree,
            "scheduled_draw_at_utc": _utc_text(self.scheduled_draw_at_utc),
            "schema_version": self.schema_version,
            "target_announcement": self.target_announcement.canonical_dict(),
            "target_announcement_sha256": self.target_announcement_sha256,
            "target_draw": self.target_draw,
        }


@dataclass(frozen=True, slots=True)
class ProspectiveShadowFinalCaptureReceipt:
    """Durable final evidence binding timings, sealed bundle, and final absence."""

    schema_version: str
    lottery_type: LotteryType
    target_draw: str
    target_announcement: TargetAnnouncement
    target_announcement_sha256: str
    scheduled_draw_at_utc: datetime
    history_cutoff: str
    pre_producer_receipt_sha256: str
    sealed_bundle_file_sha256: str
    embedded_bundle_sha256: str
    per_candidate_runtime_ns: tuple[ProspectiveCandidateRuntimeNs, ...]
    total_capture_runtime_ns: int
    capture_started_at_utc: datetime
    capture_sealed_at_utc: datetime
    final_outcome_absence_checked_at_utc: datetime
    final_outcome_absent: bool
    final_outcome_absence_attestation: OutcomePresenceAttestation
    repository_head: str
    repository_tree: str
    receipt_payload_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != (BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_SCHEMA_VERSION):
            raise ValueError("unsupported prospective final capture receipt schema")
        _require_receipt_target_authority(
            lottery_type=self.lottery_type,
            target_draw=self.target_draw,
            target_announcement=self.target_announcement,
            target_announcement_sha256=self.target_announcement_sha256,
            scheduled_draw_at_utc=self.scheduled_draw_at_utc,
            history_cutoff=self.history_cutoff,
            repository_head=self.repository_head,
            repository_tree=self.repository_tree,
        )
        for value, label in (
            (self.pre_producer_receipt_sha256, "pre_producer_receipt_sha256"),
            (self.sealed_bundle_file_sha256, "sealed_bundle_file_sha256"),
            (self.embedded_bundle_sha256, "embedded_bundle_sha256"),
        ):
            _require_sha256(value, label)
        if type(self.per_candidate_runtime_ns) is not tuple or any(
            type(item) is not ProspectiveCandidateRuntimeNs
            for item in self.per_candidate_runtime_ns
        ):
            raise ValueError("per_candidate_runtime_ns must be an immutable typed tuple")
        runtime_ids = tuple(item.candidate_id for item in self.per_candidate_runtime_ns)
        if runtime_ids != BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS:
            raise ValueError("per_candidate_runtime_ns must follow the exact candidate order")
        _require_nonnegative_lcj_integer(
            self.total_capture_runtime_ns,
            "total_capture_runtime_ns",
        )
        if self.total_capture_runtime_ns < sum(
            item.runtime_ns for item in self.per_candidate_runtime_ns
        ):
            raise ValueError("total_capture_runtime_ns cannot be below candidate runtime sum")
        for value, label in (
            (self.capture_started_at_utc, "capture_started_at_utc"),
            (self.capture_sealed_at_utc, "capture_sealed_at_utc"),
            (
                self.final_outcome_absence_checked_at_utc,
                "final_outcome_absence_checked_at_utc",
            ),
        ):
            _require_exact_utc(value, label)
        if not (
            self.capture_started_at_utc
            <= self.capture_sealed_at_utc
            <= self.final_outcome_absence_checked_at_utc
            < self.scheduled_draw_at_utc
        ):
            raise ValueError("final receipt timestamps violate the pre-draw sequence")
        if self.final_outcome_absent is not True:
            raise ValueError("final capture receipt requires final_outcome_absent=true")
        _require_absent_attestation(
            self.final_outcome_absence_attestation,
            target=self.target_announcement.target,
            checked_at=self.final_outcome_absence_checked_at_utc,
            scheduled_at=self.scheduled_draw_at_utc,
        )
        _require_sha256(self.receipt_payload_sha256, "receipt_payload_sha256")
        if self.receipt_payload_sha256 != self_key_removed_sha256(
            self.canonical_dict(),
            "receipt_payload_sha256",
        ):
            raise ProspectiveShadowReceiptTamperError(
                "final capture receipt digest does not match its canonical payload"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "capture_sealed_at_utc": _utc_text(self.capture_sealed_at_utc),
            "capture_started_at_utc": _utc_text(self.capture_started_at_utc),
            "embedded_bundle_sha256": self.embedded_bundle_sha256,
            "final_outcome_absence_attestation": (
                self.final_outcome_absence_attestation.canonical_dict()
            ),
            "final_outcome_absence_checked_at_utc": _utc_text(
                self.final_outcome_absence_checked_at_utc
            ),
            "final_outcome_absent": self.final_outcome_absent,
            "history_cutoff": self.history_cutoff,
            "lottery_type": self.lottery_type.value,
            "per_candidate_runtime_ns": [
                item.canonical_dict() for item in self.per_candidate_runtime_ns
            ],
            "pre_producer_receipt_sha256": self.pre_producer_receipt_sha256,
            "receipt_payload_sha256": self.receipt_payload_sha256,
            "repository_head": self.repository_head,
            "repository_tree": self.repository_tree,
            "scheduled_draw_at_utc": _utc_text(self.scheduled_draw_at_utc),
            "schema_version": self.schema_version,
            "sealed_bundle_file_sha256": self.sealed_bundle_file_sha256,
            "target_announcement": self.target_announcement.canonical_dict(),
            "target_announcement_sha256": self.target_announcement_sha256,
            "target_draw": self.target_draw,
            "total_capture_runtime_ns": self.total_capture_runtime_ns,
        }


@dataclass(frozen=True, slots=True)
class ProspectivePredictionRecord:
    """One self-verifying candidate prediction with no later-result fields."""

    schema_version: str
    lottery_type: LotteryType
    target_draw: str
    target_announcement: TargetAnnouncement
    target_announcement_sha256: str
    candidate_id: str
    method_id: str
    semantic_signature: str
    strategy_version: str
    history_cutoff: str
    history_row_count: int
    ticket: tuple[int, ...]
    generated_at_utc: datetime
    repository_head: str
    repository_tree: str
    prediction_payload_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != (BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION):
            raise ValueError("unsupported prospective prediction record schema")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("prediction record lottery_type must be BIG_LOTTO")
        if type(self.target_announcement) is not TargetAnnouncement:
            raise ValueError("target_announcement must be a TargetAnnouncement")
        if self.target_announcement.target.lottery_type is not self.lottery_type:
            raise ValueError("target announcement lottery identity does not match")
        if self.target_announcement.target.draw_number != self.target_draw:
            raise ValueError("target announcement draw identity does not match")
        _require_sha256(self.target_announcement_sha256, "target_announcement_sha256")
        if self.target_announcement_sha256 != normalized_announcement_sha256(
            self.target_announcement
        ):
            raise ProspectiveShadowBundleTamperError(
                "target announcement digest does not match its canonical identity"
            )
        _require_candidate_id(self.candidate_id)
        _require_canonical_text(self.method_id, "method_id")
        _require_sha256(self.semantic_signature, "semantic_signature")
        _require_canonical_text(self.strategy_version, "strategy_version")
        _require_history_cutoff(self.history_cutoff, self.target_draw)
        if (
            type(self.history_row_count) is not int
            or self.history_row_count < BIGLOTTO_L2_PAIRWISE_COMMON_MINIMUM_HISTORY_ROWS
        ):
            raise ValueError("history_row_count does not satisfy the common minimum")
        _require_legal_biglotto_ticket(self.ticket)
        _require_exact_utc(self.generated_at_utc, "generated_at_utc")
        if self.generated_at_utc >= self.target_announcement.scheduled_at:
            raise ValueError("prediction must be generated strictly before the draw time")
        _require_repository_oid(self.repository_head, "repository_head")
        _require_repository_oid(self.repository_tree, "repository_tree")
        _require_sha256(self.prediction_payload_sha256, "prediction_payload_sha256")
        expected_payload_sha256 = _prediction_payload_sha256_from_record(self)
        if self.prediction_payload_sha256 != expected_payload_sha256:
            raise ProspectiveShadowBundleTamperError(
                "prediction payload digest does not match the ordered emission"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "generated_at_utc": _utc_text(self.generated_at_utc),
            "history_cutoff": self.history_cutoff,
            "history_row_count": self.history_row_count,
            "lottery_type": self.lottery_type.value,
            "method_id": self.method_id,
            "prediction_payload_sha256": self.prediction_payload_sha256,
            "repository_head": self.repository_head,
            "repository_tree": self.repository_tree,
            "schema_version": self.schema_version,
            "semantic_signature": self.semantic_signature,
            "strategy_version": self.strategy_version,
            "target_announcement": self.target_announcement.canonical_dict(),
            "target_announcement_sha256": self.target_announcement_sha256,
            "target_draw": self.target_draw,
            "ticket": list(self.ticket),
        }


@dataclass(frozen=True, slots=True)
class ProspectiveShadowBundle:
    """One closed, canonical nine-candidate authority for a single target."""

    schema_version: str
    stage: str
    lottery_type: LotteryType
    target_draw: str
    target_announcement: TargetAnnouncement
    target_announcement_sha256: str
    expected_candidate_ids: tuple[str, ...]
    history_cutoff: str
    history_row_count: int
    generated_at_utc: datetime
    repository_head: str
    repository_tree: str
    predictions: tuple[ProspectivePredictionRecord, ...]
    bundle_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != (BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION):
            raise ValueError("unsupported prospective shadow bundle schema")
        if self.stage != BIGLOTTO_L2_PAIRWISE_SEALED_STAGE:
            raise ValueError("bundle stage must stop at the sealed prediction boundary")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("bundle lottery_type must be BIG_LOTTO")
        if type(self.target_announcement) is not TargetAnnouncement:
            raise ValueError("target_announcement must be a TargetAnnouncement")
        if (
            self.target_announcement.target.lottery_type is not self.lottery_type
            or self.target_announcement.target.draw_number != self.target_draw
        ):
            raise ValueError("bundle target identity does not match its announcement")
        _require_sha256(self.target_announcement_sha256, "target_announcement_sha256")
        if self.target_announcement_sha256 != normalized_announcement_sha256(
            self.target_announcement
        ):
            raise ProspectiveShadowBundleTamperError(
                "bundle announcement digest does not match its canonical identity"
            )
        _require_candidate_ids(self.expected_candidate_ids)
        _require_history_cutoff(self.history_cutoff, self.target_draw)
        if (
            type(self.history_row_count) is not int
            or self.history_row_count < BIGLOTTO_L2_PAIRWISE_COMMON_MINIMUM_HISTORY_ROWS
        ):
            raise ValueError("bundle history_row_count does not satisfy the common minimum")
        _require_exact_utc(self.generated_at_utc, "generated_at_utc")
        if self.generated_at_utc >= self.target_announcement.scheduled_at:
            raise ValueError("bundle must be generated strictly before the draw time")
        _require_repository_oid(self.repository_head, "repository_head")
        _require_repository_oid(self.repository_tree, "repository_tree")
        if type(self.predictions) is not tuple or any(
            type(record) is not ProspectivePredictionRecord for record in self.predictions
        ):
            raise ValueError("predictions must be an immutable typed tuple")
        record_ids = tuple(record.candidate_id for record in self.predictions)
        if record_ids != self.expected_candidate_ids:
            raise ValueError("predictions must follow the exact caller-supplied candidate order")
        for record in self.predictions:
            self._validate_shared_record_authority(record)
        _require_sha256(self.bundle_sha256, "bundle_sha256")
        if self.bundle_sha256 != self_key_removed_sha256(
            self.canonical_dict(),
            "bundle_sha256",
        ):
            raise ProspectiveShadowBundleTamperError(
                "bundle digest does not match the canonical prediction authority"
            )

    def _validate_shared_record_authority(
        self,
        record: ProspectivePredictionRecord,
    ) -> None:
        shared_pairs = (
            (record.lottery_type, self.lottery_type),
            (record.target_draw, self.target_draw),
            (record.target_announcement, self.target_announcement),
            (record.target_announcement_sha256, self.target_announcement_sha256),
            (record.history_cutoff, self.history_cutoff),
            (record.history_row_count, self.history_row_count),
            (record.generated_at_utc, self.generated_at_utc),
            (record.repository_head, self.repository_head),
            (record.repository_tree, self.repository_tree),
        )
        if any(left != right for left, right in shared_pairs):
            raise ValueError("prediction record does not share the bundle authority")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "bundle_sha256": self.bundle_sha256,
            "expected_candidate_ids": list(self.expected_candidate_ids),
            "generated_at_utc": _utc_text(self.generated_at_utc),
            "history_cutoff": self.history_cutoff,
            "history_row_count": self.history_row_count,
            "lottery_type": self.lottery_type.value,
            "predictions": [record.canonical_dict() for record in self.predictions],
            "repository_head": self.repository_head,
            "repository_tree": self.repository_tree,
            "schema_version": self.schema_version,
            "stage": self.stage,
            "target_announcement": self.target_announcement.canonical_dict(),
            "target_announcement_sha256": self.target_announcement_sha256,
            "target_draw": self.target_draw,
        }


@dataclass(frozen=True, slots=True)
class ProspectiveShadowSealResult:
    status: ProspectiveShadowSealStatus
    pre_producer_receipt: ProspectiveShadowPreProducerReceipt
    pre_producer_receipt_bytes: bytes
    bundle: ProspectiveShadowBundle
    bundle_bytes: bytes
    final_capture_receipt: ProspectiveShadowFinalCaptureReceipt
    final_capture_receipt_bytes: bytes

    def __post_init__(self) -> None:
        if type(self.status) is not ProspectiveShadowSealStatus:
            raise ValueError("status must be a ProspectiveShadowSealStatus")
        if type(self.pre_producer_receipt) is not ProspectiveShadowPreProducerReceipt:
            raise ValueError("pre_producer_receipt must be a ProspectiveShadowPreProducerReceipt")
        if type(self.pre_producer_receipt_bytes) is not bytes:
            raise ValueError("pre_producer_receipt_bytes must be exact bytes")
        if type(self.bundle) is not ProspectiveShadowBundle:
            raise ValueError("bundle must be a ProspectiveShadowBundle")
        if type(self.bundle_bytes) is not bytes:
            raise ValueError("bundle_bytes must be exact bytes")
        if type(self.final_capture_receipt) is not ProspectiveShadowFinalCaptureReceipt:
            raise ValueError("final_capture_receipt must be a ProspectiveShadowFinalCaptureReceipt")
        if type(self.final_capture_receipt_bytes) is not bytes:
            raise ValueError("final_capture_receipt_bytes must be exact bytes")
        verified = verify_prospective_shadow_capture_evidence(
            pre_producer_receipt_bytes=self.pre_producer_receipt_bytes,
            bundle_bytes=self.bundle_bytes,
            final_capture_receipt_bytes=self.final_capture_receipt_bytes,
        )
        if verified != (
            self.pre_producer_receipt,
            self.bundle,
            self.final_capture_receipt,
        ):
            raise ValueError("capture evidence bytes do not match the typed result")


@runtime_checkable
class ProspectiveShadowBundleStore(Protocol):
    """Create-once byte boundary for all three capture-evidence artifacts."""

    def read_pre_producer_receipt(self, target: ObservationTarget) -> bytes | None: ...

    def create_pre_producer_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome: ...

    def read_bundle(self, target: ObservationTarget) -> bytes | None: ...

    def create_bundle(self, target: ObservationTarget, data: bytes) -> CreateOnceOutcome: ...

    def read_final_capture_receipt(self, target: ObservationTarget) -> bytes | None: ...

    def create_final_capture_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome: ...


class FileSystemProspectiveShadowBundleStore:
    """Small local create-exclusive store for one canonical file per target."""

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        self._root = Path(root).absolute()
        try:
            metadata = self._root.lstat()
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError("bundle store root must already exist") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ProspectiveShadowBundleStoreError(
                "bundle store root must be a non-symlink directory"
            )
        if metadata.st_uid != os.getuid():
            raise ProspectiveShadowBundleStoreError(
                "bundle store root must be owned by the current user"
            )
        self._root_identity = (metadata.st_dev, metadata.st_ino)

    @property
    def root(self) -> Path:
        return self._root

    @classmethod
    def record_path_for(cls, root: str | Path, target: ObservationTarget) -> Path:
        _require_target(target)
        return Path(root).absolute() / (
            f"{target.lottery_type.value.lower()}-{target.draw_number}.prospective-shadow.json"
        )

    @classmethod
    def pre_producer_receipt_path_for(
        cls,
        root: str | Path,
        target: ObservationTarget,
    ) -> Path:
        _require_target(target)
        return Path(root).absolute() / (
            f"{target.lottery_type.value.lower()}-{target.draw_number}."
            "prospective-shadow.pre-receipt.json"
        )

    @classmethod
    def final_capture_receipt_path_for(
        cls,
        root: str | Path,
        target: ObservationTarget,
    ) -> Path:
        _require_target(target)
        return Path(root).absolute() / (
            f"{target.lottery_type.value.lower()}-{target.draw_number}."
            "prospective-shadow.final-receipt.json"
        )

    def read_pre_producer_receipt(self, target: ObservationTarget) -> bytes | None:
        _require_target(target)
        return self._read_record(
            self.pre_producer_receipt_path_for(self._root, target),
            "pre-producer receipt",
        )

    def read_bundle(self, target: ObservationTarget) -> bytes | None:
        _require_target(target)
        return self._read_record(self.record_path_for(self._root, target), "sealed bundle")

    def read_final_capture_receipt(self, target: ObservationTarget) -> bytes | None:
        _require_target(target)
        return self._read_record(
            self.final_capture_receipt_path_for(self._root, target),
            "final capture receipt",
        )

    def _read_record(self, path: Path, label: str) -> bytes | None:
        self._verify_root()
        flags = os.O_RDONLY | _NOFOLLOW | _CLOEXEC | _NONBLOCK
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError(f"cannot safely open the {label}") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise ProspectiveShadowBundleStoreError(
                    f"{label} must be an owner-controlled regular file"
                )
            if metadata.st_size > _MAX_BUNDLE_BYTES:
                raise ProspectiveShadowBundleStoreError(f"{label} exceeds the bounded size limit")
            chunks: list[bytes] = []
            remaining = _MAX_BUNDLE_BYTES + 1
            while remaining > 0:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > _MAX_BUNDLE_BYTES:
                raise ProspectiveShadowBundleStoreError(f"{label} exceeds the bounded size limit")
            return data
        finally:
            os.close(descriptor)

    def create_pre_producer_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome:
        _require_target(target)
        receipt = deserialize_prospective_shadow_pre_producer_receipt(data)
        if receipt.target_announcement.target != target:
            raise ValueError("pre-producer receipt target does not match the create-once key")
        return self._create_record(
            path=self.pre_producer_receipt_path_for(self._root, target),
            data=data,
            label="pre-producer receipt",
            reread=lambda: self.read_pre_producer_receipt(target),
        )

    def create_bundle(self, target: ObservationTarget, data: bytes) -> CreateOnceOutcome:
        _require_target(target)
        bundle = deserialize_prospective_shadow_bundle(data)
        if bundle.target_announcement.target != target:
            raise ValueError("bundle target does not match the create-once key")
        return self._create_record(
            path=self.record_path_for(self._root, target),
            data=data,
            label="sealed bundle",
            reread=lambda: self.read_bundle(target),
        )

    def create_final_capture_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome:
        _require_target(target)
        receipt = deserialize_prospective_shadow_final_capture_receipt(data)
        if receipt.target_announcement.target != target:
            raise ValueError("final capture receipt target does not match the create-once key")
        return self._create_record(
            path=self.final_capture_receipt_path_for(self._root, target),
            data=data,
            label="final capture receipt",
            reread=lambda: self.read_final_capture_receipt(target),
        )

    def _create_record(
        self,
        *,
        path: Path,
        data: bytes,
        label: str,
        reread: Callable[[], bytes | None],
    ) -> CreateOnceOutcome:
        if type(data) is not bytes:
            raise ValueError("data must be exact bytes")
        self._verify_root()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            existing = reread()
            if existing is None:
                raise ProspectiveShadowBundleStoreError(
                    f"{label} disappeared after an exclusive-create conflict"
                ) from None
            return (
                CreateOnceOutcome.ALREADY_PRESENT
                if existing == data
                else CreateOnceOutcome.CONFLICT
            )
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError(
                f"cannot create the {label} exclusively"
            ) from exc

        identity: tuple[int, int] | None = None
        try:
            os.fchmod(descriptor, 0o600)
            metadata = os.fstat(descriptor)
            identity = (metadata.st_dev, metadata.st_ino)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ProspectiveShadowBundleStoreError(
                    f"exclusive {label} entry is not a single regular file"
                )
            view = memoryview(data)
            written = 0
            while written < len(view):
                count = os.write(descriptor, view[written:])
                if count <= 0:
                    raise ProspectiveShadowBundleStoreError(
                        f"{label} writer made no forward progress"
                    )
                written += count
            os.fsync(descriptor)
        except BaseException as exc:
            os.close(descriptor)
            self._remove_owned_partial(path, identity, exc)
            if isinstance(exc, ProspectiveShadowBundleStoreError):
                raise
            raise ProspectiveShadowBundleStoreError(
                f"{label} create failed before sealing"
            ) from exc
        else:
            os.close(descriptor)

        self._fsync_root()
        persisted = reread()
        if persisted != data:
            raise ProspectiveShadowBundleStoreError(
                f"{label} reread differs from the canonical bytes"
            )
        return CreateOnceOutcome.INSERTED

    def _verify_root(self) -> None:
        try:
            metadata = self._root.lstat()
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError("bundle store root is unavailable") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != self._root_identity
        ):
            raise ProspectiveShadowBundleStoreError(
                "bundle store root identity changed after startup"
            )

    def _fsync_root(self) -> None:
        flags = os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
        try:
            descriptor = os.open(self._root, flags)
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError(
                "cannot open the bundle store root for durability"
            ) from exc
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _remove_owned_partial(
        path: Path,
        identity: tuple[int, int] | None,
        original_error: BaseException,
    ) -> None:
        if identity is None:
            raise ProspectiveShadowBundleStoreError(
                "partial capture-evidence ownership could not be established"
            ) from original_error
        try:
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != identity:
                raise ProspectiveShadowBundleStoreError(
                    "partial capture evidence changed before safe cleanup"
                )
            path.unlink()
        except ProspectiveShadowBundleStoreError:
            raise
        except OSError as exc:
            raise ProspectiveShadowBundleStoreError(
                "partial capture-evidence cleanup failed"
            ) from exc


class ProspectiveShadowCaptureService:
    """Seal a countable capture only when all three evidence artifacts verify."""

    def __init__(
        self,
        store: ProspectiveShadowBundleStore,
        *,
        outcome_presence_probe: ProspectiveOutcomePresenceProbe,
        clock: Callable[[], datetime],
        monotonic_ns: Callable[[], int],
    ) -> None:
        if not callable(clock) or not callable(monotonic_ns):
            raise ValueError("clock and monotonic_ns must be callable")
        self._store = store
        self._outcome_presence_probe = outcome_presence_probe
        self._clock = clock
        self._monotonic_ns = monotonic_ns

    def seal(self, request: ProspectiveShadowCaptureRequest) -> ProspectiveShadowSealResult:
        if type(request) is not ProspectiveShadowCaptureRequest:
            raise ValueError("request must be a ProspectiveShadowCaptureRequest")
        target = request.announcement.target
        existing = self._read_existing_complete_capture(request)
        if existing is not None:
            return existing

        pre_check_at = self._clock_utc("outcome_absence_checked_at_utc")
        pre_attestation = self._probe_absence(
            request,
            checked_at=pre_check_at,
            phase="pre-producer",
        )
        pre_receipt = _build_pre_producer_receipt(
            request=request,
            checked_at=pre_check_at,
            attestation=pre_attestation,
        )
        pre_receipt_bytes = serialize_prospective_shadow_pre_producer_receipt(pre_receipt)
        pre_create = self._store.create_pre_producer_receipt(
            target,
            pre_receipt_bytes,
        )
        if pre_create is not CreateOnceOutcome.INSERTED:
            raise ProspectiveShadowIncompleteEvidenceError(
                "pre-producer receipt was not newly and exclusively persisted"
            )
        persisted_pre = self._store.read_pre_producer_receipt(target)
        if persisted_pre is None or persisted_pre != pre_receipt_bytes:
            raise ProspectiveShadowBundleStoreError(
                "pre-producer receipt reread is not the exact durable authority"
            )
        verify_prospective_shadow_pre_producer_receipt(persisted_pre)

        capture_started_at = self._clock_utc("capture_started_at_utc")
        if capture_started_at < pre_check_at:
            raise ProspectiveShadowCaptureError("capture clock regressed after pre-receipt seal")
        if capture_started_at >= request.announcement.scheduled_at:
            raise ProspectiveShadowCaptureError(
                "producer capture must start strictly before the announced draw"
            )
        capture_request = replace(request, generated_at_utc=capture_started_at)
        total_started_ns = self._monotonic_value("total_capture_runtime_ns.start")
        bundle, candidate_runtime_ns = _capture_prospective_shadow_bundle_with_runtime(
            capture_request,
            monotonic_ns=self._monotonic_ns,
        )
        bundle_bytes = serialize_prospective_shadow_bundle(bundle)
        bundle_create = self._store.create_bundle(target, bundle_bytes)
        if bundle_create is not CreateOnceOutcome.INSERTED:
            raise ProspectiveShadowIncompleteEvidenceError(
                "prediction bundle was not newly and exclusively persisted"
            )
        persisted_bundle = self._store.read_bundle(target)
        if persisted_bundle is None or persisted_bundle != bundle_bytes:
            raise ProspectiveShadowBundleStoreError(
                "created bundle is not the exact persisted authority"
            )
        verified_bundle = verify_prospective_shadow_bundle(persisted_bundle)

        capture_sealed_at = self._clock_utc("capture_sealed_at_utc")
        if capture_sealed_at < capture_started_at:
            raise ProspectiveShadowCaptureError("capture clock regressed before bundle seal")
        total_finished_ns = self._monotonic_value("total_capture_runtime_ns.end")
        if total_finished_ns < total_started_ns:
            raise ProspectiveShadowCaptureError("monotonic clock regressed during capture")
        total_capture_runtime_ns = total_finished_ns - total_started_ns
        _require_nonnegative_lcj_integer(
            total_capture_runtime_ns,
            "total_capture_runtime_ns",
        )

        final_check_at = self._clock_utc("final_outcome_absence_checked_at_utc")
        if final_check_at < capture_sealed_at:
            raise ProspectiveShadowCaptureError("capture clock regressed before final check")
        final_attestation = self._probe_absence(
            request,
            checked_at=final_check_at,
            phase="final",
        )
        final_receipt = _build_final_capture_receipt(
            request=request,
            pre_receipt=pre_receipt,
            bundle=verified_bundle,
            bundle_bytes=persisted_bundle,
            candidate_runtime_ns=candidate_runtime_ns,
            total_capture_runtime_ns=total_capture_runtime_ns,
            capture_started_at=capture_started_at,
            capture_sealed_at=capture_sealed_at,
            final_check_at=final_check_at,
            final_attestation=final_attestation,
        )
        final_receipt_bytes = serialize_prospective_shadow_final_capture_receipt(final_receipt)
        final_create = self._store.create_final_capture_receipt(
            target,
            final_receipt_bytes,
        )
        if final_create is not CreateOnceOutcome.INSERTED:
            raise ProspectiveShadowIncompleteEvidenceError(
                "final capture receipt was not newly and exclusively persisted"
            )
        persisted_final = self._store.read_final_capture_receipt(target)
        if persisted_final is None or persisted_final != final_receipt_bytes:
            raise ProspectiveShadowBundleStoreError(
                "final capture receipt reread is not the exact durable authority"
            )
        verified_pre, verified_bundle, verified_final = verify_prospective_shadow_capture_evidence(
            pre_producer_receipt_bytes=persisted_pre,
            bundle_bytes=persisted_bundle,
            final_capture_receipt_bytes=persisted_final,
        )
        return ProspectiveShadowSealResult(
            status=ProspectiveShadowSealStatus.CREATED,
            pre_producer_receipt=verified_pre,
            pre_producer_receipt_bytes=persisted_pre,
            bundle=verified_bundle,
            bundle_bytes=persisted_bundle,
            final_capture_receipt=verified_final,
            final_capture_receipt_bytes=persisted_final,
        )

    def _read_existing_complete_capture(
        self,
        request: ProspectiveShadowCaptureRequest,
    ) -> ProspectiveShadowSealResult | None:
        target = request.announcement.target
        pre_bytes = self._store.read_pre_producer_receipt(target)
        bundle_bytes = self._store.read_bundle(target)
        final_bytes = self._store.read_final_capture_receipt(target)
        present_count = sum(item is not None for item in (pre_bytes, bundle_bytes, final_bytes))
        if present_count == 0:
            return None
        if present_count != 3:
            raise ProspectiveShadowIncompleteEvidenceError(
                "partial capture evidence is non-countable and cannot be reconstructed"
            )
        if pre_bytes is None or bundle_bytes is None or final_bytes is None:
            raise AssertionError("present_count proved all capture artifacts are present")
        pre_receipt, bundle, final_receipt = verify_prospective_shadow_capture_evidence(
            pre_producer_receipt_bytes=pre_bytes,
            bundle_bytes=bundle_bytes,
            final_capture_receipt_bytes=final_bytes,
        )
        _require_matching_request_authority(bundle, request)
        return ProspectiveShadowSealResult(
            status=ProspectiveShadowSealStatus.EXACT_IDEMPOTENT_EXISTING,
            pre_producer_receipt=pre_receipt,
            pre_producer_receipt_bytes=pre_bytes,
            bundle=bundle,
            bundle_bytes=bundle_bytes,
            final_capture_receipt=final_receipt,
            final_capture_receipt_bytes=final_bytes,
        )

    def _clock_utc(self, label: str) -> datetime:
        value = self._clock()
        _require_exact_utc(value, label)
        return value

    def _monotonic_value(self, label: str) -> int:
        value = self._monotonic_ns()
        _require_nonnegative_integer(value, label)
        return value

    def _probe_absence(
        self,
        request: ProspectiveShadowCaptureRequest,
        *,
        checked_at: datetime,
        phase: str,
    ) -> OutcomePresenceAttestation:
        if checked_at >= request.announcement.scheduled_at:
            raise ProspectiveShadowOutcomeAvailableError(
                f"{phase} outcome check did not occur strictly before the draw"
            )
        attestation = self._outcome_presence_probe.probe(
            request.announcement.target,
            as_of=checked_at,
        )
        if type(attestation) is not OutcomePresenceAttestation:
            raise ValueError("outcome presence probe must return OutcomePresenceAttestation")
        if attestation.target != request.announcement.target:
            raise ValueError("outcome presence attestation target does not match the request")
        if attestation.attested_at != checked_at:
            raise ValueError("outcome presence attestation must bind the requested instant")
        if attestation.presence is OutcomePresenceAtPrediction.PRESENT:
            raise ProspectiveShadowOutcomeAvailableError(
                f"official outcome became available during the {phase} check; "
                "capture is non-countable"
            )
        _require_absent_attestation(
            attestation,
            target=request.announcement.target,
            checked_at=checked_at,
            scheduled_at=request.announcement.scheduled_at,
        )
        return attestation


def _capture_prospective_shadow_bundle_with_runtime(
    request: ProspectiveShadowCaptureRequest,
    *,
    monotonic_ns: Callable[[], int] | None,
) -> tuple[ProspectiveShadowBundle, tuple[ProspectiveCandidateRuntimeNs, ...]]:
    """Run the exact producer order and optionally retain integer-nanosecond timings."""

    if type(request) is not ProspectiveShadowCaptureRequest:
        raise ValueError("request must be a ProspectiveShadowCaptureRequest")
    runtimes = {runtime.candidate_id: runtime for runtime in request.candidate_runtimes}
    announcement_sha256 = normalized_announcement_sha256(request.announcement)
    records: list[ProspectivePredictionRecord] = []
    runtime_measurements: list[ProspectiveCandidateRuntimeNs] = []
    for candidate_id in request.expected_candidate_ids:
        runtime = runtimes[candidate_id]
        started_ns = None if monotonic_ns is None else monotonic_ns()
        if started_ns is not None:
            _require_nonnegative_integer(started_ns, f"{candidate_id}.runtime_start_ns")
        emission = runtime.producer(request.history, request.history_cutoff)
        finished_ns = None if monotonic_ns is None else monotonic_ns()
        if started_ns is not None and finished_ns is not None:
            _require_nonnegative_integer(
                finished_ns,
                f"{candidate_id}.runtime_finish_ns",
            )
            if finished_ns < started_ns:
                raise ProspectiveShadowCaptureError(
                    f"monotonic clock regressed while measuring {candidate_id}"
                )
            runtime_measurements.append(
                ProspectiveCandidateRuntimeNs(
                    candidate_id=candidate_id,
                    runtime_ns=finished_ns - started_ns,
                )
            )
        _validate_candidate_emission(emission, runtime, request)
        artifact = build_ordered_candidate_emission_artifact(emission)
        records.append(
            ProspectivePredictionRecord(
                schema_version=(BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION),
                lottery_type=LotteryType.BIG_LOTTO,
                target_draw=request.announcement.target.draw_number,
                target_announcement=request.announcement,
                target_announcement_sha256=announcement_sha256,
                candidate_id=candidate_id,
                method_id=runtime.method_id,
                semantic_signature=runtime.semantic_signature,
                strategy_version=runtime.strategy_version,
                history_cutoff=request.history_cutoff,
                history_row_count=len(request.history),
                ticket=emission.emitted_main_numbers,
                generated_at_utc=request.generated_at_utc,
                repository_head=request.repository_head,
                repository_tree=request.repository_tree,
                prediction_payload_sha256=artifact.payload_sha256,
            )
        )

    common: dict[str, object] = {
        "bundle_sha256": "0" * 64,
        "expected_candidate_ids": list(request.expected_candidate_ids),
        "generated_at_utc": _utc_text(request.generated_at_utc),
        "history_cutoff": request.history_cutoff,
        "history_row_count": len(request.history),
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "predictions": [record.canonical_dict() for record in records],
        "repository_head": request.repository_head,
        "repository_tree": request.repository_tree,
        "schema_version": BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION,
        "stage": BIGLOTTO_L2_PAIRWISE_SEALED_STAGE,
        "target_announcement": request.announcement.canonical_dict(),
        "target_announcement_sha256": announcement_sha256,
        "target_draw": request.announcement.target.draw_number,
    }
    bundle_sha256 = self_key_removed_sha256(common, "bundle_sha256")
    bundle = ProspectiveShadowBundle(
        schema_version=BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION,
        stage=BIGLOTTO_L2_PAIRWISE_SEALED_STAGE,
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw=request.announcement.target.draw_number,
        target_announcement=request.announcement,
        target_announcement_sha256=announcement_sha256,
        expected_candidate_ids=request.expected_candidate_ids,
        history_cutoff=request.history_cutoff,
        history_row_count=len(request.history),
        generated_at_utc=request.generated_at_utc,
        repository_head=request.repository_head,
        repository_tree=request.repository_tree,
        predictions=tuple(records),
        bundle_sha256=bundle_sha256,
    )
    return bundle, tuple(runtime_measurements)


def serialize_prospective_shadow_bundle(bundle: ProspectiveShadowBundle) -> bytes:
    if type(bundle) is not ProspectiveShadowBundle:
        raise ValueError("bundle must be a ProspectiveShadowBundle")
    return canonical_bytes(bundle.canonical_dict())


def deserialize_prospective_shadow_bundle(data: bytes) -> ProspectiveShadowBundle:
    if type(data) is not bytes:
        raise ValueError("data must be exact bytes")
    try:
        raw = loads_canonical(data)
    except ValueError as exc:
        raise ProspectiveShadowBundleShapeError("bundle is not valid LCJ-1 canonical JSON") from exc
    payload = _require_mapping(raw, "bundle")
    _require_exact_keys(payload, _BUNDLE_KEYS, "bundle")
    if canonical_bytes(payload) != data:
        raise ProspectiveShadowBundleShapeError(
            "bundle bytes are not the exact LCJ-1 serialization"
        )
    declared_sha256 = payload["bundle_sha256"]
    _require_sha256(declared_sha256, "bundle_sha256")
    if declared_sha256 != self_key_removed_sha256(payload, "bundle_sha256"):
        raise ProspectiveShadowBundleTamperError("bundle digest does not match the canonical bytes")

    try:
        announcement = TargetAnnouncement.from_canonical_dict(
            cast(
                Mapping[str, object],
                _require_mapping(
                    payload["target_announcement"],
                    "target_announcement",
                ),
            )
        )
        expected_candidate_ids = _text_tuple(
            payload["expected_candidate_ids"],
            "expected_candidate_ids",
        )
        raw_predictions = payload["predictions"]
        if type(raw_predictions) is not list:
            raise ProspectiveShadowBundleShapeError("predictions must be an array")
        prediction_values = cast(list[object], raw_predictions)
        predictions = tuple(_prediction_record_from_payload(item) for item in prediction_values)
        return ProspectiveShadowBundle(
            schema_version=_require_canonical_text(
                payload["schema_version"],
                "schema_version",
            ),
            stage=_require_canonical_text(payload["stage"], "stage"),
            lottery_type=LotteryType(
                _require_canonical_text(payload["lottery_type"], "lottery_type")
            ),
            target_draw=_require_canonical_text(payload["target_draw"], "target_draw"),
            target_announcement=announcement,
            target_announcement_sha256=cast(str, payload["target_announcement_sha256"]),
            expected_candidate_ids=expected_candidate_ids,
            history_cutoff=_require_canonical_text(
                payload["history_cutoff"],
                "history_cutoff",
            ),
            history_row_count=_require_exact_int(
                payload["history_row_count"],
                "history_row_count",
            ),
            generated_at_utc=_datetime_from_utc_text(
                payload["generated_at_utc"],
                "generated_at_utc",
            ),
            repository_head=cast(str, payload["repository_head"]),
            repository_tree=cast(str, payload["repository_tree"]),
            predictions=predictions,
            bundle_sha256=cast(str, declared_sha256),
        )
    except ProspectiveShadowBundleVerificationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProspectiveShadowBundleShapeError(
            "bundle contains malformed identity or prediction values"
        ) from exc


def verify_prospective_shadow_bundle(data: bytes) -> ProspectiveShadowBundle:
    """Reparse canonical bytes and verify the bundle plus all prediction digests."""

    return deserialize_prospective_shadow_bundle(data)


def _build_pre_producer_receipt(
    *,
    request: ProspectiveShadowCaptureRequest,
    checked_at: datetime,
    attestation: OutcomePresenceAttestation,
) -> ProspectiveShadowPreProducerReceipt:
    announcement_sha256 = normalized_announcement_sha256(request.announcement)
    material: dict[str, object] = {
        "history_cutoff": request.history_cutoff,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "outcome_absence_attestation": attestation.canonical_dict(),
        "outcome_absence_checked_at_utc": _utc_text(checked_at),
        "outcome_absent": True,
        "receipt_payload_sha256": "0" * 64,
        "repository_head": request.repository_head,
        "repository_tree": request.repository_tree,
        "scheduled_draw_at_utc": _utc_text(request.announcement.scheduled_at),
        "schema_version": BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_SCHEMA_VERSION,
        "target_announcement": request.announcement.canonical_dict(),
        "target_announcement_sha256": announcement_sha256,
        "target_draw": request.announcement.target.draw_number,
    }
    receipt_payload_sha256 = self_key_removed_sha256(
        material,
        "receipt_payload_sha256",
    )
    return ProspectiveShadowPreProducerReceipt(
        schema_version=BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw=request.announcement.target.draw_number,
        target_announcement=request.announcement,
        target_announcement_sha256=announcement_sha256,
        scheduled_draw_at_utc=request.announcement.scheduled_at,
        history_cutoff=request.history_cutoff,
        outcome_absent=True,
        outcome_absence_checked_at_utc=checked_at,
        outcome_absence_attestation=attestation,
        repository_head=request.repository_head,
        repository_tree=request.repository_tree,
        receipt_payload_sha256=receipt_payload_sha256,
    )


def _build_final_capture_receipt(
    *,
    request: ProspectiveShadowCaptureRequest,
    pre_receipt: ProspectiveShadowPreProducerReceipt,
    bundle: ProspectiveShadowBundle,
    bundle_bytes: bytes,
    candidate_runtime_ns: tuple[ProspectiveCandidateRuntimeNs, ...],
    total_capture_runtime_ns: int,
    capture_started_at: datetime,
    capture_sealed_at: datetime,
    final_check_at: datetime,
    final_attestation: OutcomePresenceAttestation,
) -> ProspectiveShadowFinalCaptureReceipt:
    pre_receipt_file_sha256 = sha256_hex(
        serialize_prospective_shadow_pre_producer_receipt(pre_receipt)
    )
    bundle_file_sha256 = sha256_hex(bundle_bytes)
    announcement_sha256 = normalized_announcement_sha256(request.announcement)
    material: dict[str, object] = {
        "capture_sealed_at_utc": _utc_text(capture_sealed_at),
        "capture_started_at_utc": _utc_text(capture_started_at),
        "embedded_bundle_sha256": bundle.bundle_sha256,
        "final_outcome_absence_attestation": final_attestation.canonical_dict(),
        "final_outcome_absence_checked_at_utc": _utc_text(final_check_at),
        "final_outcome_absent": True,
        "history_cutoff": request.history_cutoff,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "per_candidate_runtime_ns": [item.canonical_dict() for item in candidate_runtime_ns],
        "pre_producer_receipt_sha256": pre_receipt_file_sha256,
        "receipt_payload_sha256": "0" * 64,
        "repository_head": request.repository_head,
        "repository_tree": request.repository_tree,
        "scheduled_draw_at_utc": _utc_text(request.announcement.scheduled_at),
        "schema_version": BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_SCHEMA_VERSION,
        "sealed_bundle_file_sha256": bundle_file_sha256,
        "target_announcement": request.announcement.canonical_dict(),
        "target_announcement_sha256": announcement_sha256,
        "target_draw": request.announcement.target.draw_number,
        "total_capture_runtime_ns": total_capture_runtime_ns,
    }
    receipt_payload_sha256 = self_key_removed_sha256(
        material,
        "receipt_payload_sha256",
    )
    return ProspectiveShadowFinalCaptureReceipt(
        schema_version=BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw=request.announcement.target.draw_number,
        target_announcement=request.announcement,
        target_announcement_sha256=announcement_sha256,
        scheduled_draw_at_utc=request.announcement.scheduled_at,
        history_cutoff=request.history_cutoff,
        pre_producer_receipt_sha256=pre_receipt_file_sha256,
        sealed_bundle_file_sha256=bundle_file_sha256,
        embedded_bundle_sha256=bundle.bundle_sha256,
        per_candidate_runtime_ns=candidate_runtime_ns,
        total_capture_runtime_ns=total_capture_runtime_ns,
        capture_started_at_utc=capture_started_at,
        capture_sealed_at_utc=capture_sealed_at,
        final_outcome_absence_checked_at_utc=final_check_at,
        final_outcome_absent=True,
        final_outcome_absence_attestation=final_attestation,
        repository_head=request.repository_head,
        repository_tree=request.repository_tree,
        receipt_payload_sha256=receipt_payload_sha256,
    )


def serialize_prospective_shadow_pre_producer_receipt(
    receipt: ProspectiveShadowPreProducerReceipt,
) -> bytes:
    if type(receipt) is not ProspectiveShadowPreProducerReceipt:
        raise ValueError("receipt must be a ProspectiveShadowPreProducerReceipt")
    return canonical_bytes(receipt.canonical_dict())


def deserialize_prospective_shadow_pre_producer_receipt(
    data: bytes,
) -> ProspectiveShadowPreProducerReceipt:
    payload = _deserialize_receipt_payload(data, _PRE_RECEIPT_KEYS, "pre-producer receipt")
    try:
        declared_sha256 = payload["receipt_payload_sha256"]
        _require_sha256(declared_sha256, "receipt_payload_sha256")
        if declared_sha256 != self_key_removed_sha256(payload, "receipt_payload_sha256"):
            raise ProspectiveShadowReceiptTamperError(
                "pre-producer receipt digest does not match the canonical bytes"
            )
        announcement = TargetAnnouncement.from_canonical_dict(
            cast(
                Mapping[str, object],
                _require_mapping(payload["target_announcement"], "target_announcement"),
            )
        )
        attestation = OutcomePresenceAttestation.from_canonical_dict(
            cast(
                Mapping[str, object],
                _require_mapping(
                    payload["outcome_absence_attestation"],
                    "outcome_absence_attestation",
                ),
            )
        )
        return ProspectiveShadowPreProducerReceipt(
            schema_version=_require_canonical_text(
                payload["schema_version"],
                "schema_version",
            ),
            lottery_type=LotteryType(
                _require_canonical_text(payload["lottery_type"], "lottery_type")
            ),
            target_draw=_require_canonical_text(payload["target_draw"], "target_draw"),
            target_announcement=announcement,
            target_announcement_sha256=cast(str, payload["target_announcement_sha256"]),
            scheduled_draw_at_utc=_datetime_from_utc_text(
                payload["scheduled_draw_at_utc"],
                "scheduled_draw_at_utc",
            ),
            history_cutoff=_require_canonical_text(
                payload["history_cutoff"],
                "history_cutoff",
            ),
            outcome_absent=cast(bool, payload["outcome_absent"]),
            outcome_absence_checked_at_utc=_datetime_from_utc_text(
                payload["outcome_absence_checked_at_utc"],
                "outcome_absence_checked_at_utc",
            ),
            outcome_absence_attestation=attestation,
            repository_head=cast(str, payload["repository_head"]),
            repository_tree=cast(str, payload["repository_tree"]),
            receipt_payload_sha256=cast(str, declared_sha256),
        )
    except ProspectiveShadowReceiptVerificationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProspectiveShadowReceiptShapeError(
            "pre-producer receipt contains malformed evidence values"
        ) from exc


def verify_prospective_shadow_pre_producer_receipt(
    data: bytes,
) -> ProspectiveShadowPreProducerReceipt:
    return deserialize_prospective_shadow_pre_producer_receipt(data)


def serialize_prospective_shadow_final_capture_receipt(
    receipt: ProspectiveShadowFinalCaptureReceipt,
) -> bytes:
    if type(receipt) is not ProspectiveShadowFinalCaptureReceipt:
        raise ValueError("receipt must be a ProspectiveShadowFinalCaptureReceipt")
    return canonical_bytes(receipt.canonical_dict())


def deserialize_prospective_shadow_final_capture_receipt(
    data: bytes,
) -> ProspectiveShadowFinalCaptureReceipt:
    payload = _deserialize_receipt_payload(data, _FINAL_RECEIPT_KEYS, "final receipt")
    try:
        declared_sha256 = payload["receipt_payload_sha256"]
        _require_sha256(declared_sha256, "receipt_payload_sha256")
        if declared_sha256 != self_key_removed_sha256(payload, "receipt_payload_sha256"):
            raise ProspectiveShadowReceiptTamperError(
                "final capture receipt digest does not match the canonical bytes"
            )
        announcement = TargetAnnouncement.from_canonical_dict(
            cast(
                Mapping[str, object],
                _require_mapping(payload["target_announcement"], "target_announcement"),
            )
        )
        attestation = OutcomePresenceAttestation.from_canonical_dict(
            cast(
                Mapping[str, object],
                _require_mapping(
                    payload["final_outcome_absence_attestation"],
                    "final_outcome_absence_attestation",
                ),
            )
        )
        runtime_values = payload["per_candidate_runtime_ns"]
        if type(runtime_values) is not list:
            raise ProspectiveShadowReceiptShapeError("per_candidate_runtime_ns must be an array")
        runtimes = tuple(
            _candidate_runtime_ns_from_payload(item) for item in cast(list[object], runtime_values)
        )
        return ProspectiveShadowFinalCaptureReceipt(
            schema_version=_require_canonical_text(
                payload["schema_version"],
                "schema_version",
            ),
            lottery_type=LotteryType(
                _require_canonical_text(payload["lottery_type"], "lottery_type")
            ),
            target_draw=_require_canonical_text(payload["target_draw"], "target_draw"),
            target_announcement=announcement,
            target_announcement_sha256=cast(str, payload["target_announcement_sha256"]),
            scheduled_draw_at_utc=_datetime_from_utc_text(
                payload["scheduled_draw_at_utc"],
                "scheduled_draw_at_utc",
            ),
            history_cutoff=_require_canonical_text(
                payload["history_cutoff"],
                "history_cutoff",
            ),
            pre_producer_receipt_sha256=cast(
                str,
                payload["pre_producer_receipt_sha256"],
            ),
            sealed_bundle_file_sha256=cast(str, payload["sealed_bundle_file_sha256"]),
            embedded_bundle_sha256=cast(str, payload["embedded_bundle_sha256"]),
            per_candidate_runtime_ns=runtimes,
            total_capture_runtime_ns=_require_exact_int(
                payload["total_capture_runtime_ns"],
                "total_capture_runtime_ns",
            ),
            capture_started_at_utc=_datetime_from_utc_text(
                payload["capture_started_at_utc"],
                "capture_started_at_utc",
            ),
            capture_sealed_at_utc=_datetime_from_utc_text(
                payload["capture_sealed_at_utc"],
                "capture_sealed_at_utc",
            ),
            final_outcome_absence_checked_at_utc=_datetime_from_utc_text(
                payload["final_outcome_absence_checked_at_utc"],
                "final_outcome_absence_checked_at_utc",
            ),
            final_outcome_absent=cast(bool, payload["final_outcome_absent"]),
            final_outcome_absence_attestation=attestation,
            repository_head=cast(str, payload["repository_head"]),
            repository_tree=cast(str, payload["repository_tree"]),
            receipt_payload_sha256=cast(str, declared_sha256),
        )
    except ProspectiveShadowReceiptVerificationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProspectiveShadowReceiptShapeError(
            "final capture receipt contains malformed evidence values"
        ) from exc


def verify_prospective_shadow_final_capture_receipt(
    data: bytes,
) -> ProspectiveShadowFinalCaptureReceipt:
    return deserialize_prospective_shadow_final_capture_receipt(data)


def verify_prospective_shadow_capture_evidence(
    *,
    pre_producer_receipt_bytes: bytes,
    bundle_bytes: bytes,
    final_capture_receipt_bytes: bytes,
) -> tuple[
    ProspectiveShadowPreProducerReceipt,
    ProspectiveShadowBundle,
    ProspectiveShadowFinalCaptureReceipt,
]:
    """Independently verify all bytes and every cross-artifact binding."""

    pre_receipt = verify_prospective_shadow_pre_producer_receipt(pre_producer_receipt_bytes)
    bundle = verify_prospective_shadow_bundle(bundle_bytes)
    final_receipt = verify_prospective_shadow_final_capture_receipt(final_capture_receipt_bytes)
    if final_receipt.pre_producer_receipt_sha256 != sha256_hex(pre_producer_receipt_bytes):
        raise ProspectiveShadowReceiptTamperError(
            "final receipt does not reference the exact pre-producer receipt bytes"
        )
    if final_receipt.sealed_bundle_file_sha256 != sha256_hex(bundle_bytes):
        raise ProspectiveShadowReceiptTamperError(
            "final receipt does not reference the exact sealed bundle file bytes"
        )
    if final_receipt.embedded_bundle_sha256 != bundle.bundle_sha256:
        raise ProspectiveShadowReceiptTamperError(
            "final receipt embedded bundle digest does not match the bundle"
        )
    shared_pairs = (
        (pre_receipt.lottery_type, bundle.lottery_type, final_receipt.lottery_type),
        (pre_receipt.target_draw, bundle.target_draw, final_receipt.target_draw),
        (
            pre_receipt.target_announcement,
            bundle.target_announcement,
            final_receipt.target_announcement,
        ),
        (
            pre_receipt.target_announcement_sha256,
            bundle.target_announcement_sha256,
            final_receipt.target_announcement_sha256,
        ),
        (pre_receipt.history_cutoff, bundle.history_cutoff, final_receipt.history_cutoff),
        (
            pre_receipt.repository_head,
            bundle.repository_head,
            final_receipt.repository_head,
        ),
        (
            pre_receipt.repository_tree,
            bundle.repository_tree,
            final_receipt.repository_tree,
        ),
    )
    if any(first != second or second != third for first, second, third in shared_pairs):
        raise ProspectiveShadowReceiptTamperError(
            "capture artifacts do not share one target and source authority"
        )
    if pre_receipt.outcome_absence_checked_at_utc > final_receipt.capture_started_at_utc:
        raise ProspectiveShadowReceiptTamperError(
            "pre-producer receipt was not established before capture start"
        )
    if bundle.generated_at_utc != final_receipt.capture_started_at_utc:
        raise ProspectiveShadowReceiptTamperError(
            "bundle generation time does not match the recorded capture start"
        )
    return pre_receipt, bundle, final_receipt


def _deserialize_receipt_payload(
    data: bytes,
    expected_keys: set[str],
    label: str,
) -> dict[str, Any]:
    if type(data) is not bytes:
        raise ValueError("data must be exact bytes")
    try:
        raw = loads_canonical(data)
    except ValueError as exc:
        raise ProspectiveShadowReceiptShapeError(
            f"{label} is not valid LCJ-1 canonical JSON"
        ) from exc
    if type(raw) is not dict:
        raise ProspectiveShadowReceiptShapeError(f"{label} must be an object")
    payload = cast(dict[str, Any], raw)
    if set(payload) != expected_keys:
        raise ProspectiveShadowReceiptShapeError(f"{label} keys are not closed")
    if canonical_bytes(payload) != data:
        raise ProspectiveShadowReceiptShapeError(
            f"{label} bytes are not the exact LCJ-1 serialization"
        )
    return payload


def _candidate_runtime_ns_from_payload(value: object) -> ProspectiveCandidateRuntimeNs:
    if type(value) is not dict:
        raise ProspectiveShadowReceiptShapeError("per_candidate_runtime_ns item must be an object")
    payload = cast(dict[str, Any], value)
    if set(payload) != _CANDIDATE_RUNTIME_KEYS:
        raise ProspectiveShadowReceiptShapeError(
            "per_candidate_runtime_ns item keys are not closed"
        )
    return ProspectiveCandidateRuntimeNs(
        candidate_id=_require_canonical_text(payload["candidate_id"], "candidate_id"),
        runtime_ns=_require_exact_int(payload["runtime_ns"], "runtime_ns"),
    )


def _prediction_record_from_payload(value: object) -> ProspectivePredictionRecord:
    payload = _require_mapping(value, "prediction")
    _require_exact_keys(payload, _RECORD_KEYS, "prediction")
    raw_ticket = payload["ticket"]
    if type(raw_ticket) is not list:
        raise ProspectiveShadowBundleShapeError("prediction.ticket must be an array")
    ticket_values = cast(list[object], raw_ticket)
    announcement = TargetAnnouncement.from_canonical_dict(
        cast(
            Mapping[str, object],
            _require_mapping(
                payload["target_announcement"],
                "prediction.target_announcement",
            ),
        )
    )
    return ProspectivePredictionRecord(
        schema_version=_require_canonical_text(
            payload["schema_version"],
            "prediction.schema_version",
        ),
        lottery_type=LotteryType(
            _require_canonical_text(
                payload["lottery_type"],
                "prediction.lottery_type",
            )
        ),
        target_draw=_require_canonical_text(
            payload["target_draw"],
            "prediction.target_draw",
        ),
        target_announcement=announcement,
        target_announcement_sha256=cast(str, payload["target_announcement_sha256"]),
        candidate_id=_require_canonical_text(
            payload["candidate_id"],
            "prediction.candidate_id",
        ),
        method_id=_require_canonical_text(
            payload["method_id"],
            "prediction.method_id",
        ),
        semantic_signature=cast(str, payload["semantic_signature"]),
        strategy_version=_require_canonical_text(
            payload["strategy_version"],
            "prediction.strategy_version",
        ),
        history_cutoff=_require_canonical_text(
            payload["history_cutoff"],
            "prediction.history_cutoff",
        ),
        history_row_count=_require_exact_int(
            payload["history_row_count"],
            "prediction.history_row_count",
        ),
        ticket=_integer_tuple(ticket_values, "prediction.ticket"),
        generated_at_utc=_datetime_from_utc_text(
            payload["generated_at_utc"],
            "prediction.generated_at_utc",
        ),
        repository_head=cast(str, payload["repository_head"]),
        repository_tree=cast(str, payload["repository_tree"]),
        prediction_payload_sha256=cast(str, payload["prediction_payload_sha256"]),
    )


def _validate_candidate_emission(
    emission: object,
    runtime: ProspectiveCandidateRuntime,
    request: ProspectiveShadowCaptureRequest,
) -> None:
    if type(emission) is not OrderedCandidateEmission:
        raise ValueError("candidate producer must return an OrderedCandidateEmission")
    if emission.lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("candidate emission lottery_type must be BIG_LOTTO")
    if emission.strategy_id != runtime.method_id:
        raise ValueError("candidate emission strategy_id must equal its frozen method_id")
    if emission.strategy_version != runtime.strategy_version:
        raise ValueError("candidate emission strategy_version does not match runtime identity")
    if emission.target_draw != request.announcement.target.draw_number:
        raise ValueError("candidate emission target_draw does not match the announcement")
    if emission.history_cutoff != request.history_cutoff:
        raise ValueError("candidate emissions must share the request history_cutoff")
    if emission.replicate != 1:
        raise ValueError("prospective candidate emissions require replicate=1")
    _require_legal_biglotto_ticket(emission.emitted_main_numbers)
    if (
        emission.auxiliary_operand_kind is not AuxiliaryOperandKind.BIG_LOTTO_SPECIAL
        or emission.auxiliary_operand_availability
        is not AuxiliaryOperandAvailability.EXPLICITLY_MISSING
        or emission.auxiliary_operand_value is not None
    ):
        raise ValueError("prospective Big Lotto tickets must omit the auxiliary operand")


def _prediction_payload_sha256_from_record(record: ProspectivePredictionRecord) -> str:
    emission = OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=record.lottery_type,
        strategy_id=record.method_id,
        strategy_version=record.strategy_version,
        replicate=1,
        target_draw=record.target_draw,
        history_cutoff=record.history_cutoff,
        emitted_main_numbers=record.ticket,
        auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        auxiliary_operand_availability=AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
        auxiliary_operand_value=None,
    )
    return build_ordered_candidate_emission_artifact(emission).payload_sha256


def _require_matching_request_authority(
    bundle: ProspectiveShadowBundle,
    request: ProspectiveShadowCaptureRequest,
) -> None:
    by_id = {runtime.candidate_id: runtime for runtime in request.candidate_runtimes}
    common_matches = (
        bundle.target_announcement == request.announcement
        and bundle.target_announcement_sha256
        == normalized_announcement_sha256(request.announcement)
        and bundle.history_cutoff == request.history_cutoff
        and bundle.history_row_count == len(request.history)
        and bundle.expected_candidate_ids == request.expected_candidate_ids
        and bundle.repository_head == request.repository_head
        and bundle.repository_tree == request.repository_tree
    )
    identity_matches = tuple(
        (
            record.candidate_id,
            record.method_id,
            record.semantic_signature,
            record.strategy_version,
        )
        for record in bundle.predictions
    ) == tuple(
        (
            candidate_id,
            by_id[candidate_id].method_id,
            by_id[candidate_id].semantic_signature,
            by_id[candidate_id].strategy_version,
        )
        for candidate_id in request.expected_candidate_ids
    )
    if not common_matches or not identity_matches:
        raise ProspectiveShadowBundleConflictError(
            "target already has different immutable prospective authority"
        )


def _require_receipt_target_authority(
    *,
    lottery_type: LotteryType,
    target_draw: str,
    target_announcement: TargetAnnouncement,
    target_announcement_sha256: str,
    scheduled_draw_at_utc: datetime,
    history_cutoff: str,
    repository_head: str,
    repository_tree: str,
) -> None:
    if lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("capture receipt lottery_type must be BIG_LOTTO")
    if type(target_announcement) is not TargetAnnouncement:
        raise ValueError("target_announcement must be a TargetAnnouncement")
    if (
        target_announcement.target.lottery_type is not lottery_type
        or target_announcement.target.draw_number != target_draw
    ):
        raise ValueError("capture receipt target identity does not match its announcement")
    _require_sha256(target_announcement_sha256, "target_announcement_sha256")
    if target_announcement_sha256 != normalized_announcement_sha256(target_announcement):
        raise ProspectiveShadowReceiptTamperError(
            "capture receipt announcement digest does not match its canonical identity"
        )
    _require_exact_utc(scheduled_draw_at_utc, "scheduled_draw_at_utc")
    if scheduled_draw_at_utc != target_announcement.scheduled_at:
        raise ValueError("scheduled draw timestamp does not match the target announcement")
    _require_history_cutoff(history_cutoff, target_draw)
    _require_repository_oid(repository_head, "repository_head")
    _require_repository_oid(repository_tree, "repository_tree")


def _require_absent_attestation(
    value: object,
    *,
    target: ObservationTarget,
    checked_at: datetime,
    scheduled_at: datetime,
) -> None:
    if type(value) is not OutcomePresenceAttestation:
        raise ValueError("absence attestation must be an OutcomePresenceAttestation")
    attestation = value
    _require_exact_utc(checked_at, "outcome_absence_checked_at_utc")
    if attestation.target != target:
        raise ValueError("absence attestation target does not match capture target")
    if attestation.presence is not OutcomePresenceAtPrediction.ABSENT:
        raise ProspectiveShadowOutcomeAvailableError(
            "capture receipt requires an ABSENT official-outcome attestation"
        )
    if attestation.attested_at != checked_at:
        raise ValueError("absence attestation does not bind the recorded check timestamp")
    if checked_at >= scheduled_at:
        raise ValueError("outcome absence must be checked strictly before the draw")


def _require_target(value: object) -> None:
    if type(value) is not ObservationTarget:
        raise ValueError("target must be an ObservationTarget")
    if value.lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("bundle store accepts only BIG_LOTTO targets")


def _require_candidate_ids(value: object) -> None:
    if type(value) is not tuple:
        raise ValueError("expected_candidate_ids must be an immutable tuple")
    ids = cast(tuple[object, ...], value)
    if len(ids) != BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_COUNT:
        raise ValueError("expected_candidate_ids must contain exactly nine candidates")
    for candidate_id in ids:
        _require_candidate_id(candidate_id)
    if len(ids) != len(set(ids)):
        raise ValueError("expected_candidate_ids must be unique")
    if cast(tuple[str, ...], ids) != BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS:
        raise ValueError("expected_candidate_ids must equal C1-C6/C8-C10 in exact order")


def _require_candidate_id(value: object) -> None:
    if type(value) is not str or _CANDIDATE_ID.fullmatch(value) is None:
        raise ValueError("candidate_id must be canonical uppercase ASCII text")


def _require_history_cutoff(value: object, target_draw: str) -> None:
    if type(value) is not str or _ASCII_DECIMAL.fullmatch(value) is None:
        raise ValueError("history_cutoff must be an ASCII decimal draw identity")
    if int(value) >= int(target_draw):
        raise ValueError("history_cutoff must precede target_draw")


def _require_legal_biglotto_ticket(value: object) -> None:
    if type(value) is not tuple:
        raise ValueError("ticket must be an immutable tuple")
    ticket = cast(tuple[object, ...], value)
    if (
        len(ticket) != 6
        or any(type(number) is not int for number in ticket)
        or any(not 1 <= cast(int, number) <= 49 for number in ticket)
        or tuple(sorted(cast(tuple[int, ...], ticket))) != ticket
        or len(set(ticket)) != 6
    ):
        raise ValueError("ticket must be six distinct sorted exact integers in 1..49")


def _require_canonical_text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{label} must be non-empty canonical text")
    return value


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_repository_oid(value: object, label: str) -> None:
    if type(value) is not str or _REPOSITORY_OID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase repository object id")


def _require_exact_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _datetime_from_utc_text(value: object, label: str) -> datetime:
    text = _require_canonical_text(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must use canonical UTC text")
    parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    _require_exact_utc(parsed, label)
    if _utc_text(parsed) != text:
        raise ValueError(f"{label} must use canonical UTC text")
    return parsed


def _require_exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact integer")
    return value


def _require_nonnegative_integer(value: object, label: str) -> int:
    integer = _require_exact_int(value, label)
    if integer < 0:
        raise ValueError(f"{label} must be non-negative")
    return integer


def _require_nonnegative_lcj_integer(value: object, label: str) -> int:
    integer = _require_nonnegative_integer(value, label)
    if integer > MAX_SAFE_INTEGER:
        raise ValueError(f"{label} exceeds the LCJ-1 exact-integer bound")
    return integer


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ProspectiveShadowBundleShapeError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise ProspectiveShadowBundleShapeError(f"{label} keys are not closed")


def _text_tuple(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise ProspectiveShadowBundleShapeError(f"{label} must be an array")
    items = cast(list[object], value)
    return tuple(
        _require_canonical_text(item, f"{label}[{index}]") for index, item in enumerate(items)
    )


def _integer_tuple(value: object, label: str) -> tuple[int, ...]:
    if type(value) is not list:
        raise ProspectiveShadowBundleShapeError(f"{label} must be an array")
    items = cast(list[object], value)
    if any(type(item) is not int for item in items):
        raise ProspectiveShadowBundleShapeError(f"{label} must contain exact integers")
    return cast(tuple[int, ...], tuple(items))


__all__ = [
    "BIGLOTTO_L2_PAIRWISE_COMMON_MINIMUM_HISTORY_ROWS",
    "BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_COUNT",
    "BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS",
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_ELIGIBILITY_FLOOR",
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_FINAL_RECEIPT_SCHEMA_VERSION",
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_PRE_RECEIPT_SCHEMA_VERSION",
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION",
    "BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION",
    "BIGLOTTO_L2_PAIRWISE_SEALED_STAGE",
    "FileSystemProspectiveShadowBundleStore",
    "ProspectiveCandidateProducer",
    "ProspectiveCandidateRuntime",
    "ProspectiveCandidateRuntimeNs",
    "ProspectiveOutcomePresenceProbe",
    "ProspectivePredictionRecord",
    "ProspectiveShadowBundle",
    "ProspectiveShadowBundleConflictError",
    "ProspectiveShadowBundleShapeError",
    "ProspectiveShadowBundleStore",
    "ProspectiveShadowBundleStoreError",
    "ProspectiveShadowBundleTamperError",
    "ProspectiveShadowBundleVerificationError",
    "ProspectiveShadowCaptureError",
    "ProspectiveShadowCaptureRequest",
    "ProspectiveShadowCaptureService",
    "ProspectiveShadowFinalCaptureReceipt",
    "ProspectiveShadowIncompleteEvidenceError",
    "ProspectiveShadowOutcomeAvailableError",
    "ProspectiveShadowPreProducerReceipt",
    "ProspectiveShadowReceiptShapeError",
    "ProspectiveShadowReceiptTamperError",
    "ProspectiveShadowReceiptVerificationError",
    "ProspectiveShadowSealResult",
    "ProspectiveShadowSealStatus",
    "deserialize_prospective_shadow_bundle",
    "deserialize_prospective_shadow_final_capture_receipt",
    "deserialize_prospective_shadow_pre_producer_receipt",
    "serialize_prospective_shadow_bundle",
    "serialize_prospective_shadow_final_capture_receipt",
    "serialize_prospective_shadow_pre_producer_receipt",
    "verify_prospective_shadow_bundle",
    "verify_prospective_shadow_capture_evidence",
    "verify_prospective_shadow_final_capture_receipt",
    "verify_prospective_shadow_pre_producer_receipt",
]
