"""Create-once application service for the T539 external PRETARGET seal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.domain.t539_pretarget_external_seal import (
    ExternalReceiptVerificationError,
    PretargetSealConflictError,
    PretargetSealStatus,
    RekorReceiptEvidence,
    SealRecordCreateOutcome,
    T539PretargetSeal,
    T539PretargetSealRecord,
    T539PretargetSnapshotBinding,
    VerifiedRekorReceipt,
)


class MissingPreOutcomeRegistrationError(RuntimeError):
    """The existing create-once target authority is absent."""


class MissingPretargetSnapshotError(RuntimeError):
    """The deterministic PRETARGET snapshot is absent, so recovery fails closed."""


class PreOutcomeRegistrationReader(Protocol):
    def get_registration(
        self, target: ObservationTarget
    ) -> PreOutcomeTargetRegistration | None: ...


class PretargetSnapshotReader(Protocol):
    def get_snapshot(self, target: ObservationTarget) -> Mapping[str, object] | None: ...


class RekorReceiptVerifier(Protocol):
    def verify(
        self,
        seal: T539PretargetSeal,
        receipt: RekorReceiptEvidence,
    ) -> VerifiedRekorReceipt: ...


class PretargetSealRecordStore(Protocol):
    def get_record(self, target: ObservationTarget) -> T539PretargetSealRecord | None: ...

    def create_record(self, record: T539PretargetSealRecord) -> SealRecordCreateOutcome: ...


@dataclass(frozen=True, slots=True)
class SubmitT539RekorReceiptRequest:
    target: ObservationTarget
    receipt: RekorReceiptEvidence

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if type(self.receipt) is not RekorReceiptEvidence:
            raise ValueError("receipt must be complete RekorReceiptEvidence")


@dataclass(frozen=True, slots=True)
class InspectT539PretargetSealRequest:
    """Operational inspection time can only keep PENDING or fail closed to MISSED."""

    target: ObservationTarget
    inspection_time: datetime

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if (
            type(self.inspection_time) is not datetime
            or self.inspection_time.tzinfo is None
            or self.inspection_time.utcoffset() != UTC.utcoffset(self.inspection_time)
        ):
            raise ValueError("inspection_time must use UTC")


@dataclass(frozen=True, slots=True)
class T539PretargetSealDecision:
    status: PretargetSealStatus
    seal_digest: str
    external_seal_authority_time: datetime | None
    rekor_entry_id: str | None
    persistence_outcome: SealRecordCreateOutcome | None

    def __post_init__(self) -> None:
        if type(self.status) is not PretargetSealStatus:
            raise ValueError("status must be a PretargetSealStatus")
        if self.status is PretargetSealStatus.SEALED:
            if self.external_seal_authority_time is None or self.rekor_entry_id is None:
                raise ValueError("SEALED decision requires external Rekor authority")
        elif self.external_seal_authority_time is not None or self.rekor_entry_id is not None:
            raise ValueError("only SEALED decisions carry external Rekor authority")


@dataclass(frozen=True, slots=True)
class _SealInputs:
    registration: PreOutcomeTargetRegistration
    snapshot: T539PretargetSnapshotBinding
    seal: T539PretargetSeal


class T539PretargetExternalSealService:
    """First valid timely receipt wins; every restart reverifies durable evidence."""

    def __init__(
        self,
        *,
        registrations: PreOutcomeRegistrationReader,
        snapshots: PretargetSnapshotReader,
        receipts: RekorReceiptVerifier,
        records: PretargetSealRecordStore,
    ) -> None:
        self._registrations = registrations
        self._snapshots = snapshots
        self._receipts = receipts
        self._records = records

    def submit_receipt(
        self, request: SubmitT539RekorReceiptRequest
    ) -> T539PretargetSealDecision:
        if type(request) is not SubmitT539RekorReceiptRequest:
            raise ValueError("request must be SubmitT539RekorReceiptRequest")
        inputs = self._load_inputs(request.target)
        existing = self._records.get_record(request.target)
        if existing is not None:
            return self._decision_from_existing(
                existing,
                inputs,
                requested_receipt=request.receipt,
                persistence_outcome=SealRecordCreateOutcome.ALREADY_PRESENT,
            )

        verified = self._verify_exact(inputs.seal, request.receipt)
        if verified.receipt.external_authority_time >= (
            inputs.registration.announcement.scheduled_at
        ):
            candidate = T539PretargetSealRecord.missed(inputs.registration, inputs.seal)
        else:
            candidate = T539PretargetSealRecord.sealed(
                inputs.registration,
                inputs.seal,
                verified,
            )
        return self._create_and_resolve(
            candidate,
            inputs,
            requested_receipt=request.receipt,
        )

    def inspect_or_finalize(
        self, request: InspectT539PretargetSealRequest
    ) -> T539PretargetSealDecision:
        """Recover after restart or durably mark a closed receipt window MISSED.

        ``inspection_time`` is never seal authority and is not persisted.  It can
        only leave the target pending or move it to the fail-closed MISSED state.
        """

        if type(request) is not InspectT539PretargetSealRequest:
            raise ValueError("request must be InspectT539PretargetSealRequest")
        inputs = self._load_inputs(request.target)
        existing = self._records.get_record(request.target)
        if existing is not None:
            return self._decision_from_existing(
                existing,
                inputs,
                requested_receipt=None,
                persistence_outcome=SealRecordCreateOutcome.ALREADY_PRESENT,
            )
        if request.inspection_time < inputs.registration.announcement.scheduled_at:
            return T539PretargetSealDecision(
                status=PretargetSealStatus.PENDING,
                seal_digest=inputs.seal.seal_digest,
                external_seal_authority_time=None,
                rekor_entry_id=None,
                persistence_outcome=None,
            )
        missed = T539PretargetSealRecord.missed(inputs.registration, inputs.seal)
        return self._create_and_resolve(missed, inputs, requested_receipt=None)

    def _load_inputs(self, target: ObservationTarget) -> _SealInputs:
        registration = self._registrations.get_registration(target)
        if registration is None:
            raise MissingPreOutcomeRegistrationError(
                "existing pre-outcome target registration is required"
            )
        if registration.target != target:
            raise PretargetSealConflictError(
                "registration reader returned a different target authority"
            )
        raw_snapshot = self._snapshots.get_snapshot(target)
        if raw_snapshot is None:
            raise MissingPretargetSnapshotError(
                "deterministic PRETARGET snapshot is required for sealing or recovery"
            )
        snapshot = T539PretargetSnapshotBinding.from_snapshot(raw_snapshot, registration)
        seal = T539PretargetSeal.create(registration, snapshot)
        return _SealInputs(registration=registration, snapshot=snapshot, seal=seal)

    def _verify_exact(
        self,
        seal: T539PretargetSeal,
        receipt: RekorReceiptEvidence,
    ) -> VerifiedRekorReceipt:
        if receipt.seal_digest != seal.seal_digest:
            raise ExternalReceiptVerificationError(
                "receipt seal_digest does not match canonical T539 seal"
            )
        verified = self._receipts.verify(seal, receipt)
        if type(verified) is not VerifiedRekorReceipt:
            raise ExternalReceiptVerificationError(
                "receipt verifier did not return VerifiedRekorReceipt"
            )
        if verified.receipt != receipt or verified.receipt.seal_digest != seal.seal_digest:
            raise ExternalReceiptVerificationError(
                "receipt verifier result does not bind the supplied evidence and seal"
            )
        return verified

    def _reverify_record(self, record: T539PretargetSealRecord) -> None:
        if record.receipt is None:
            raise ExternalReceiptVerificationError("SEALED record is missing receipt evidence")
        verified = self._verify_exact(record.seal, record.receipt)
        if verified.receipt.receipt_identity != record.receipt.receipt_identity:
            raise ExternalReceiptVerificationError(
                "reverified receipt identity differs from durable evidence"
            )
        if verified.verification != record.receipt_verification:
            raise ExternalReceiptVerificationError(
                "reverified trust-root/verifier reference differs from durable evidence"
            )

    def _decision_from_existing(
        self,
        record: T539PretargetSealRecord,
        inputs: _SealInputs,
        *,
        requested_receipt: RekorReceiptEvidence | None,
        persistence_outcome: SealRecordCreateOutcome,
    ) -> T539PretargetSealDecision:
        record.validate_against(inputs.registration, inputs.snapshot)
        if record.status is PretargetSealStatus.MISSED:
            return self._decision(record, persistence_outcome)

        self._reverify_record(record)
        if record.receipt is None:  # pragma: no cover - guarded by record invariants
            raise ExternalReceiptVerificationError("SEALED record is missing receipt evidence")
        if requested_receipt is not None and requested_receipt != record.receipt:
            raise PretargetSealConflictError(
                "CONFLICT: a different Rekor receipt already won for this target"
            )
        return self._decision(record, persistence_outcome)

    def _create_and_resolve(
        self,
        candidate: T539PretargetSealRecord,
        inputs: _SealInputs,
        *,
        requested_receipt: RekorReceiptEvidence | None,
    ) -> T539PretargetSealDecision:
        outcome = self._records.create_record(candidate)
        if outcome is SealRecordCreateOutcome.INSERTED:
            return self._decision(candidate, outcome)

        winner = self._records.get_record(candidate.seal.target)
        if winner is None:
            raise PretargetSealConflictError(
                "create-once store reported an existing state but no winner can be loaded"
            )
        return self._decision_from_existing(
            winner,
            inputs,
            requested_receipt=requested_receipt,
            persistence_outcome=outcome,
        )

    @staticmethod
    def _decision(
        record: T539PretargetSealRecord,
        persistence_outcome: SealRecordCreateOutcome,
    ) -> T539PretargetSealDecision:
        return T539PretargetSealDecision(
            status=record.status,
            seal_digest=record.seal_digest,
            external_seal_authority_time=record.external_seal_authority_time,
            rekor_entry_id=(record.receipt.rekor_entry_id if record.receipt is not None else None),
            persistence_outcome=persistence_outcome,
        )


__all__ = [
    "InspectT539PretargetSealRequest",
    "MissingPreOutcomeRegistrationError",
    "MissingPretargetSnapshotError",
    "PreOutcomeRegistrationReader",
    "PretargetSealRecordStore",
    "PretargetSnapshotReader",
    "RekorReceiptVerifier",
    "SubmitT539RekorReceiptRequest",
    "T539PretargetExternalSealService",
    "T539PretargetSealDecision",
]
