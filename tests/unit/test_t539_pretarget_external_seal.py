from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from sigstore.verify.policy import UnsafeNoOp

from lottolab.application.t539_pretarget_external_seal import (
    InspectT539PretargetSealRequest,
    MissingPretargetSnapshotError,
    SubmitT539RekorReceiptRequest,
    T539PretargetExternalSealService,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.domain.t539_pretarget_external_seal import (
    SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY,
    T539_FREEZE_BOUNDARY,
    T539_FREEZE_MANIFEST_SHA256,
    T539_INTEGRATED_STACK_COMMIT,
    T539_INTEGRATED_STACK_TREE,
    T539_PRETARGET_SEAL_SCHEMA_VERSION,
    T539_RULE_FINGERPRINT,
    ExternalReceiptVerificationError,
    PretargetSealConflictError,
    PretargetSealStatus,
    RekorReceiptEvidence,
    RekorVerificationReference,
    SealRecordCreateOutcome,
    T539PretargetSeal,
    T539PretargetSealRecord,
    T539PretargetSnapshotBinding,
    VerifiedRekorReceipt,
    canonical_json_bytes,
    canonical_sha256,
)
from lottolab.infrastructure import t539_pretarget_rekor as rekor_module
from lottolab.infrastructure.t539_pretarget_external_seal_store import (
    FileSystemT539PretargetSealRecordStore,
)
from lottolab.infrastructure.t539_pretarget_rekor import (
    OfficialSigstoreBundleVerifier,
    SigstoreRekorReceiptVerifier,
    receipt_from_sigstore_bundle,
)

TARGET_DATE = date(2026, 9, 1)
OUTCOME_AUTHORITY_TIME = datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
TARGET = ObservationTarget(
    lottery_type=LotteryType.DAILY_539,
    draw_number="115000187",
    draw_date=TARGET_DATE,
)


@dataclass(slots=True)
class _RegistrationReader:
    registration: PreOutcomeTargetRegistration | None

    def get_registration(
        self, target: ObservationTarget
    ) -> PreOutcomeTargetRegistration | None:
        if self.registration is None or self.registration.target != target:
            return None
        return self.registration


@dataclass(slots=True)
class _SnapshotReader:
    snapshot: dict[str, object] | None

    def get_snapshot(self, target: ObservationTarget) -> dict[str, object] | None:
        del target
        return self.snapshot


class _SyntheticSigstoreVerifierFixture:
    """Exact allowlist fixture; it performs no synthetic cryptography."""

    def __init__(self) -> None:
        self._accepted: set[tuple[bytes, str]] = set()
        self.calls: list[tuple[bytes, str]] = []

    def allow(self, seal: T539PretargetSeal, receipt: RekorReceiptEvidence) -> None:
        self._accepted.add((seal.canonical_bytes(), receipt.sigstore_bundle_json))

    def verify_artifact(
        self, artifact: bytes, bundle_json: str
    ) -> RekorVerificationReference:
        self.calls.append((artifact, bundle_json))
        if (artifact, bundle_json) not in self._accepted:
            raise ValueError("synthetic bundle is not an accepted verification fixture")
        return _verification()


def _registration(
    *, lottery_type: LotteryType = LotteryType.DAILY_539, draw_number: str = "115000187"
) -> PreOutcomeTargetRegistration:
    target = ObservationTarget(
        lottery_type=lottery_type,
        draw_number=draw_number,
        draw_date=TARGET_DATE,
    )
    announcement_source = TargetSourceProvenance(
        source_id="SYNTHETIC_OFFICIAL_SCHEDULE",
        source_version="r1",
        source_locator="synthetic://schedule/115000187",
        source_sha256="1" * 64,
        observed_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )
    absence_source = TargetSourceProvenance(
        source_id="SYNTHETIC_OUTCOME_PRESENCE",
        source_version="r1",
        source_locator="synthetic://outcome-presence/115000187",
        source_sha256="2" * 64,
        observed_at=datetime(2026, 9, 1, 10, 1, tzinfo=UTC),
    )
    announcement = TargetAnnouncement(
        target=target,
        schedule_timezone="Asia/Taipei",
        scheduled_at=OUTCOME_AUTHORITY_TIME,
        source=announcement_source,
    )
    absence = OutcomePresenceAttestation(
        target=target,
        presence=OutcomePresenceAtPrediction.ABSENT,
        attested_at=datetime(2026, 9, 1, 10, 2, tzinfo=UTC),
        source=absence_source,
    )
    history = CausalHistoryRef(
        draw_count=1,
        last_draw_number=T539_FREEZE_BOUNDARY,
        last_draw_date=date(2026, 8, 31),
        history_sha256="3" * 64,
    )
    return PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=absence,
        causal_history=history,
        registered_at=datetime(2026, 9, 1, 10, 3, tzinfo=UTC),
    )


def _snapshot(registration: PreOutcomeTargetRegistration) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "experiments": [],
        "freeze": {
            "freeze_boundary_target_identity": T539_FREEZE_BOUNDARY,
            "freeze_id": "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_R1",
            "freeze_manifest_sha256": T539_FREEZE_MANIFEST_SHA256,
            "source_pilot_result_sha256": "4" * 64,
        },
        "input_authority": {
            "identity": "SYNTHETIC_T539_PRETARGET_FIXTURE_R1",
            "schema_version": "T539_PROSPECTIVE_PRETARGET_INPUT_V1",
            "sha256": "5" * 64,
        },
        "outcome_presence_at_prepare": "ABSENT",
        "phase": "PRETARGET_PREPARE",
        "phase_status": "PRETARGET_SNAPSHOT_MATERIALIZED",
        "prospective_classification": "PENDING_EXTERNAL_PRETARGET_SEAL_ATTESTATION",
        "rule_fingerprint": T539_RULE_FINGERPRINT,
        "schema_version": "T539_PROSPECTIVE_PRETARGET_SNAPSHOT_V1",
        "surface": {"arm_record_count": 90, "experiment_count": 30},
        "target_identity": registration.target.draw_number,
    }
    _rehash_snapshot(snapshot)
    return snapshot


def _rehash_snapshot(snapshot: dict[str, object]) -> None:
    material = dict(snapshot)
    material.pop("snapshot_content_hash", None)
    snapshot["snapshot_content_hash"] = canonical_sha256(material)


def _binding_and_seal(
    registration: PreOutcomeTargetRegistration,
    snapshot: dict[str, object],
) -> tuple[T539PretargetSnapshotBinding, T539PretargetSeal]:
    binding = T539PretargetSnapshotBinding.from_snapshot(snapshot, registration)
    return binding, T539PretargetSeal.create(registration, binding)


def _bundle(
    seal: T539PretargetSeal,
    *,
    integrated_time: int,
    log_index: int,
    tag: str,
) -> dict[str, object]:
    signature = base64.b64encode(f"synthetic-signature-{tag}".encode()).decode()
    certificate = base64.b64encode(f"synthetic-certificate-{tag}".encode()).decode()
    body = {
        "apiVersion": "0.0.1",
        "kind": "hashedrekord",
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": seal.seal_digest}},
            "signature": {
                "content": signature,
                "publicKey": {"content": certificate},
            },
        },
    }
    body_base64 = base64.b64encode(canonical_json_bytes(body)).decode()
    return {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "messageSignature": {
            "messageDigest": {
                "algorithm": "SHA2_256",
                "digest": base64.b64encode(bytes.fromhex(seal.seal_digest)).decode(),
            },
            "signature": signature,
        },
        "verificationMaterial": {
            "certificate": {"rawBytes": certificate},
            "tlogEntries": [
                {
                    "canonicalizedBody": body_base64,
                    "inclusionPromise": {
                        "signedEntryTimestamp": base64.b64encode(
                            f"synthetic-set-{tag}".encode()
                        ).decode()
                    },
                    "inclusionProof": {
                        "checkpoint": {"envelope": f"synthetic-checkpoint-{tag}"},
                        "hashes": [],
                        "logIndex": str(log_index),
                        "rootHash": base64.b64encode(
                            hashlib.sha256(tag.encode()).digest()
                        ).decode(),
                        "treeSize": str(log_index + 1),
                    },
                    "integratedTime": str(integrated_time),
                    "kindVersion": {"kind": "hashedrekord", "version": "0.0.1"},
                    "logId": {
                        "keyId": base64.b64encode(
                            hashlib.sha256(b"synthetic-log").digest()
                        ).decode()
                    },
                    "logIndex": str(log_index),
                }
            ],
        },
    }


def _receipt(
    seal: T539PretargetSeal,
    backend: _SyntheticSigstoreVerifierFixture,
    *,
    integrated_time: int,
    log_index: int = 42,
    tag: str = "one",
    allow: bool = True,
) -> RekorReceiptEvidence:
    bundle = _bundle(
        seal,
        integrated_time=integrated_time,
        log_index=log_index,
        tag=tag,
    )
    receipt = receipt_from_sigstore_bundle(
        rekor_entry_id=_rekor_uuid(bundle),
        seal_digest=seal.seal_digest,
        sigstore_bundle_json=json.dumps(bundle),
    )
    if allow:
        backend.allow(seal, receipt)
    return receipt


def _rekor_uuid(bundle: dict[str, object]) -> str:
    verification_material = cast(dict[str, object], bundle["verificationMaterial"])
    entries = cast(list[object], verification_material["tlogEntries"])
    entry = cast(dict[str, object], entries[0])
    canonicalized_body = cast(str, entry["canonicalizedBody"])
    body = base64.b64decode(canonicalized_body, validate=True)
    return hashlib.sha256(b"\x00" + body).hexdigest()


def _verification() -> RekorVerificationReference:
    return RekorVerificationReference(
        trust_root_identity=SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY,
        trust_root_version=f"sha256:{'a' * 64}",
        verifier="sigstore-python",
        verifier_version="4.5.0",
    )


def _service(
    root: Path,
    registration: PreOutcomeTargetRegistration,
    snapshot: dict[str, object] | None,
    backend: _SyntheticSigstoreVerifierFixture,
) -> tuple[
    T539PretargetExternalSealService,
    FileSystemT539PretargetSealRecordStore,
    _SnapshotReader,
]:
    snapshot_reader = _SnapshotReader(snapshot)
    store = FileSystemT539PretargetSealRecordStore(root)
    service = T539PretargetExternalSealService(
        registrations=_RegistrationReader(registration),
        snapshots=snapshot_reader,
        receipts=SigstoreRekorReceiptVerifier(backend=backend),
        records=store,
    )
    return service, store, snapshot_reader


def test_exact_canonical_t539_seal_bytes_and_sha() -> None:
    seal = T539PretargetSeal(
        schema_version=T539_PRETARGET_SEAL_SCHEMA_VERSION,
        target=TARGET,
        snapshot_content_hash="a" * 64,
        rule_fingerprint=T539_RULE_FINGERPRINT,
        freeze_boundary=T539_FREEZE_BOUNDARY,
        freeze_manifest_sha256=T539_FREEZE_MANIFEST_SHA256,
        integrated_stack_commit=T539_INTEGRATED_STACK_COMMIT,
        integrated_stack_tree=T539_INTEGRATED_STACK_TREE,
        pre_outcome_registration_digest="b" * 64,
    )
    expected = (
        b'{"freeze_boundary":"115000186","freeze_manifest_sha256":"f1b299ace019393440'
        b'bce8bd2768f6618b2362d220d81b4cc14151a5080908a8","integrated_stack_commit":"1fdb'
        b'2d53a7ef62baa8bdbd5ce962f7aeb0176c62","integrated_stack_tree":"7a3e0a6892cf666'
        b'ef9f20826225ccfffab455e07","pre_outcome_registration_digest":"bbbbbbbbbbbbbbbbbbbb'
        b'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","rule_fingerprint":"eb4eb89082cd782'
        b'041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446","schema_version":"T539_PRETA'
        b'RGET_SEAL_V1","snapshot_content_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        b'aaaaaaaaaaaaaaaa","target":{"draw_date":"2026-09-01","draw_number":"115000187","lo'
        b'ttery_type":"DAILY_539"}}'
    )
    assert seal.canonical_bytes() == expected
    assert not seal.canonical_bytes().endswith(b"\n")
    assert seal.seal_digest == "2e3b8849fc80103feefecf0eab125114dae12a49f86f2712d293374f4ecef998"


def test_wrong_lottery_and_target_at_or_before_freeze_are_rejected() -> None:
    wrong_registration = _registration(lottery_type=LotteryType.BIG_LOTTO)
    with pytest.raises(ValueError, match="DAILY_539"):
        T539PretargetSnapshotBinding.from_snapshot(
            _snapshot(wrong_registration), wrong_registration
        )

    with pytest.raises(ValueError, match="strictly after"):
        T539PretargetSeal(
            schema_version=T539_PRETARGET_SEAL_SCHEMA_VERSION,
            target=ObservationTarget(
                LotteryType.DAILY_539, T539_FREEZE_BOUNDARY, TARGET_DATE
            ),
            snapshot_content_hash="a" * 64,
            rule_fingerprint=T539_RULE_FINGERPRINT,
            freeze_boundary=T539_FREEZE_BOUNDARY,
            freeze_manifest_sha256=T539_FREEZE_MANIFEST_SHA256,
            integrated_stack_commit=T539_INTEGRATED_STACK_COMMIT,
            integrated_stack_tree=T539_INTEGRATED_STACK_TREE,
            pre_outcome_registration_digest="b" * 64,
        )


def test_registration_digest_mismatch_is_rejected() -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    binding, seal = _binding_and_seal(registration, snapshot)
    different_registration = replace(seal, pre_outcome_registration_digest="c" * 64)
    with pytest.raises(PretargetSealConflictError, match="registration"):
        different_registration.validate_against(registration, binding)


def test_snapshot_hash_rule_freeze_and_stack_mismatches_are_rejected() -> None:
    registration = _registration()
    snapshot = _snapshot(registration)

    hash_mismatch = copy.deepcopy(snapshot)
    hash_mismatch["phase_status"] = "TAMPERED"
    with pytest.raises(ValueError, match="snapshot_content_hash mismatch"):
        T539PretargetSnapshotBinding.from_snapshot(hash_mismatch, registration)

    wrong_rule = copy.deepcopy(snapshot)
    wrong_rule["rule_fingerprint"] = "6" * 64
    _rehash_snapshot(wrong_rule)
    with pytest.raises(ValueError, match="rule_fingerprint"):
        T539PretargetSnapshotBinding.from_snapshot(wrong_rule, registration)

    wrong_boundary = copy.deepcopy(snapshot)
    freeze = cast(dict[str, object], wrong_boundary["freeze"])
    freeze["freeze_boundary_target_identity"] = "115000185"
    _rehash_snapshot(wrong_boundary)
    with pytest.raises(ValueError, match="freeze_boundary"):
        T539PretargetSnapshotBinding.from_snapshot(wrong_boundary, registration)

    wrong_manifest = copy.deepcopy(snapshot)
    freeze = cast(dict[str, object], wrong_manifest["freeze"])
    freeze["freeze_manifest_sha256"] = "7" * 64
    _rehash_snapshot(wrong_manifest)
    with pytest.raises(ValueError, match="freeze_manifest_sha256"):
        T539PretargetSnapshotBinding.from_snapshot(wrong_manifest, registration)

    _, seal = _binding_and_seal(registration, snapshot)
    with pytest.raises(ValueError, match="integrated_stack_commit"):
        replace(seal, integrated_stack_commit="8" * 64)
    with pytest.raises(ValueError, match="integrated_stack_tree"):
        replace(seal, integrated_stack_tree="9" * 64)


def test_externally_verified_timely_receipt_is_accepted(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=1)).timestamp()),
    )
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        decision = service.submit_receipt(
            SubmitT539RekorReceiptRequest(TARGET, receipt)
        )
        assert decision.status is PretargetSealStatus.SEALED
        assert decision.external_seal_authority_time == receipt.external_authority_time
        assert decision.persistence_outcome is SealRecordCreateOutcome.INSERTED
        assert backend.calls == [(seal.canonical_bytes(), receipt.sigstore_bundle_json)]
    finally:
        store.close()


def test_unverified_receipt_and_raw_uuid_are_rejected(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    unverified = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=2)).timestamp()),
        allow=False,
    )
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        with pytest.raises(ExternalReceiptVerificationError, match="failed closed"):
            service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, unverified))
        with pytest.raises(ValueError, match="complete RekorReceiptEvidence"):
            SubmitT539RekorReceiptRequest(
                TARGET,
                cast(RekorReceiptEvidence, {"rekor_entry_id": "raw-uuid"}),
            )
        with pytest.raises(ValueError, match="fields differ"):
            RekorReceiptEvidence.from_canonical_dict(
                cast(dict[str, object], {"rekor_entry_id": "raw-uuid"})
            )
    finally:
        store.close()


def test_local_timestamp_cannot_create_seal_authority(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    backend = _SyntheticSigstoreVerifierFixture()
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        decision = service.inspect_or_finalize(
            InspectT539PretargetSealRequest(
                TARGET,
                OUTCOME_AUTHORITY_TIME - timedelta(seconds=1),
            )
        )
        assert decision.status is PretargetSealStatus.PENDING
        assert decision.external_seal_authority_time is None
        assert "local_timestamp" not in inspect.signature(RekorReceiptEvidence).parameters
        assert "external_timestamp" not in inspect.signature(RekorReceiptEvidence).parameters
    finally:
        store.close()


@pytest.mark.parametrize("offset_seconds", [0, 1])
def test_receipt_at_or_after_outcome_time_is_missed(
    tmp_path: Path, offset_seconds: int
) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int(OUTCOME_AUTHORITY_TIME.timestamp()) + offset_seconds,
        tag=f"late-{offset_seconds}",
    )
    service, store, _ = _service(
        tmp_path / f"receipts-{offset_seconds}", registration, snapshot, backend
    )
    try:
        decision = service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, receipt))
        assert decision.status is PretargetSealStatus.MISSED
        assert decision.external_seal_authority_time is None
        persisted = store.get_record(TARGET)
        assert persisted is not None and persisted.receipt is None
    finally:
        store.close()


def test_exact_duplicate_is_idempotent_and_retains_original_authority(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=10)).timestamp()),
    )
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        first = service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, receipt))
        second = service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, receipt))
        assert first.external_seal_authority_time == second.external_seal_authority_time
        assert first.persistence_outcome is SealRecordCreateOutcome.INSERTED
        assert second.persistence_outcome is SealRecordCreateOutcome.ALREADY_PRESENT
    finally:
        store.close()


def test_competing_receipt_and_snapshot_conflict(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    first = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=20)).timestamp()),
        log_index=10,
        tag="winner",
    )
    second = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=19)).timestamp()),
        log_index=11,
        tag="competitor",
    )
    service, store, snapshots = _service(
        tmp_path / "receipts", registration, snapshot, backend
    )
    try:
        service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, first))
        with pytest.raises(PretargetSealConflictError, match="different Rekor receipt"):
            service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, second))

        competing_snapshot = copy.deepcopy(snapshot)
        authority = cast(dict[str, object], competing_snapshot["input_authority"])
        authority["identity"] = "SYNTHETIC_COMPETING_SNAPSHOT"
        _rehash_snapshot(competing_snapshot)
        snapshots.snapshot = competing_snapshot
        with pytest.raises(PretargetSealConflictError, match="deterministic snapshot"):
            service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, first))
    finally:
        store.close()


def test_restart_reverifies_and_retains_original_authority(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(minutes=1)).timestamp()),
    )
    root = tmp_path / "receipts"
    first_service, first_store, _ = _service(root, registration, snapshot, backend)
    first = first_service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, receipt))
    first_store.close()

    restarted_service, restarted_store, _ = _service(root, registration, snapshot, backend)
    try:
        recovered = restarted_service.inspect_or_finalize(
            InspectT539PretargetSealRequest(TARGET, OUTCOME_AUTHORITY_TIME + timedelta(days=1))
        )
        assert recovered.status is PretargetSealStatus.SEALED
        assert recovered.external_seal_authority_time == first.external_seal_authority_time
        assert len(backend.calls) == 2
    finally:
        restarted_store.close()


def test_missing_receipt_after_window_is_missed_and_late_receipt_cannot_undo(
    tmp_path: Path,
) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        missed = service.inspect_or_finalize(
            InspectT539PretargetSealRequest(TARGET, OUTCOME_AUTHORITY_TIME)
        )
        assert missed.status is PretargetSealStatus.MISSED

        late = _receipt(
            seal,
            backend,
            integrated_time=int((OUTCOME_AUTHORITY_TIME + timedelta(seconds=1)).timestamp()),
            tag="late-after-missed",
        )
        still_missed = service.submit_receipt(
            SubmitT539RekorReceiptRequest(TARGET, late)
        )
        assert still_missed.status is PretargetSealStatus.MISSED
        assert store.get_record(TARGET) is not None
        assert store.get_record(TARGET).receipt is None  # type: ignore[union-attr]
    finally:
        store.close()


def test_missing_snapshot_after_outcome_fails_closed(tmp_path: Path) -> None:
    registration = _registration()
    backend = _SyntheticSigstoreVerifierFixture()
    service, store, _ = _service(tmp_path / "receipts", registration, None, backend)
    try:
        with pytest.raises(MissingPretargetSnapshotError, match="required"):
            service.inspect_or_finalize(
                InspectT539PretargetSealRequest(TARGET, OUTCOME_AUTHORITY_TIME)
            )
    finally:
        store.close()


def test_seal_schema_contains_no_outcome_numbers_or_timestamp() -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    assert set(seal.canonical_dict()) == {
        "freeze_boundary",
        "freeze_manifest_sha256",
        "integrated_stack_commit",
        "integrated_stack_tree",
        "pre_outcome_registration_digest",
        "rule_fingerprint",
        "schema_version",
        "snapshot_content_hash",
        "target",
    }
    encoded = seal.canonical_bytes().decode()
    assert "winning_numbers" not in encoded
    assert "outcome_numbers" not in encoded
    assert "timestamp" not in encoded


def test_persisted_record_has_no_secret_and_exact_reassociation(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=3)).timestamp()),
    )
    root = tmp_path / "receipts"
    service, store, _ = _service(root, registration, snapshot, backend)
    try:
        service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, receipt))
        record_path = store.record_path_for(root, TARGET)
        encoded = record_path.read_text(encoding="utf-8")
        for forbidden in ("private_key", "privateKey", "password", '"secret"', '"token"'):
            assert forbidden not in encoded

        associated = store.find_associated_receipt(
            target=TARGET,
            seal_digest=seal.seal_digest,
            rekor_entry_id=receipt.rekor_entry_id,
        )
        assert associated is not None
        assert associated.receipt == receipt
        assert (
            store.find_associated_receipt(
                target=TARGET,
                seal_digest="0" * 64,
                rekor_entry_id=receipt.rekor_entry_id,
            )
            is None
        )
        assert (
            store.find_associated_receipt(
                target=TARGET,
                seal_digest=seal.seal_digest,
                rekor_entry_id="different-entry",
            )
            is None
        )
    finally:
        store.close()


def test_secret_shaped_bundle_and_tampered_receipt_fail_closed(tmp_path: Path) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()

    secret_bundle = _bundle(
        seal,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=4)).timestamp()),
        log_index=90,
        tag="secret",
    )
    secret_bundle["privateKey"] = "must-not-persist"
    with pytest.raises(ValueError, match="prohibited field"):
        receipt_from_sigstore_bundle(
            rekor_entry_id=_rekor_uuid(secret_bundle),
            seal_digest=seal.seal_digest,
            sigstore_bundle_json=json.dumps(secret_bundle),
        )

    tampered_bundle = _bundle(
        seal,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=4)).timestamp()),
        log_index=91,
        tag="tampered",
    )
    signature = cast(dict[str, object], tampered_bundle["messageSignature"])
    signature["signature"] = base64.b64encode(b"tampered-after-signing").decode()
    tampered = receipt_from_sigstore_bundle(
        rekor_entry_id=_rekor_uuid(tampered_bundle),
        seal_digest=seal.seal_digest,
        sigstore_bundle_json=json.dumps(tampered_bundle),
    )
    service, store, _ = _service(tmp_path / "receipts", registration, snapshot, backend)
    try:
        with pytest.raises(ExternalReceiptVerificationError, match="failed closed"):
            service.submit_receipt(SubmitT539RekorReceiptRequest(TARGET, tampered))
        assert store.get_record(TARGET) is None
    finally:
        store.close()


def test_unrelated_rekor_entry_id_is_rejected_before_verification() -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    bundle = _bundle(
        seal,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=5)).timestamp()),
        log_index=92,
        tag="entry-id-binding",
    )
    assert _rekor_uuid(bundle) != "0" * 64

    with pytest.raises(ExternalReceiptVerificationError, match="RFC6962 leaf hash"):
        receipt_from_sigstore_bundle(
            rekor_entry_id="0" * 64,
            seal_digest=seal.seal_digest,
            sigstore_bundle_json=json.dumps(bundle),
        )


def test_restart_rejects_forged_persisted_verification_reference(
    tmp_path: Path,
) -> None:
    registration = _registration()
    snapshot = _snapshot(registration)
    _, seal = _binding_and_seal(registration, snapshot)
    backend = _SyntheticSigstoreVerifierFixture()
    receipt = _receipt(
        seal,
        backend,
        integrated_time=int((OUTCOME_AUTHORITY_TIME - timedelta(seconds=6)).timestamp()),
        log_index=93,
        tag="forged-verification-reference",
    )
    forged = replace(
        _verification(),
        trust_root_version=f"sha256:{'f' * 64}",
        verifier_version="99.0.0-forged",
    )
    root = tmp_path / "forged-verification-reference"
    seed_store = FileSystemT539PretargetSealRecordStore(root)
    try:
        outcome = seed_store.create_record(
            T539PretargetSealRecord.sealed(
                registration,
                seal,
                VerifiedRekorReceipt(receipt=receipt, verification=forged),
            )
        )
        assert outcome is SealRecordCreateOutcome.INSERTED
    finally:
        seed_store.close()

    service, recovered_store, _ = _service(root, registration, snapshot, backend)
    try:
        with pytest.raises(
            ExternalReceiptVerificationError,
            match="trust-root/verifier reference",
        ):
            service.inspect_or_finalize(
                InspectT539PretargetSealRequest(
                    TARGET,
                    OUTCOME_AUTHORITY_TIME - timedelta(minutes=1),
                )
            )
    finally:
        recovered_store.close()


def test_official_backend_forces_offline_sigstore_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class _FakeBundle:
        @classmethod
        def from_json(cls, raw: bytes | str) -> object:
            observed["bundle"] = raw
            return object()

    class _FakeTrustedRootInner:
        def to_json(self) -> str:
            return json.dumps({"mediaType": "synthetic-root", "tlogs": []})

    class _FakeTrustedRoot:
        def __init__(self) -> None:
            self._inner = _FakeTrustedRootInner()

    class _FakeTrustConfig:
        trusted_root = _FakeTrustedRoot()

    class _FakeClientTrustConfig:
        @classmethod
        def production(cls, offline: bool = False) -> _FakeTrustConfig:
            observed["offline"] = offline
            return _FakeTrustConfig()

    class _FakeVerifier:
        def __init__(self, *, trusted_root: object) -> None:
            observed["trusted_root"] = trusted_root

        def verify_artifact(
            self, artifact: bytes, bundle: object, policy: object
        ) -> None:
            observed["artifact"] = artifact
            observed["parsed_bundle"] = bundle
            observed["policy"] = policy

    monkeypatch.setattr(rekor_module, "Bundle", _FakeBundle)
    monkeypatch.setattr(rekor_module, "ClientTrustConfig", _FakeClientTrustConfig)
    monkeypatch.setattr(rekor_module, "Verifier", _FakeVerifier)
    policy = UnsafeNoOp()
    reference = OfficialSigstoreBundleVerifier(policy).verify_artifact(b"seal", "{}")
    assert observed["offline"] is True
    assert observed["artifact"] == b"seal"
    assert observed["bundle"] == "{}"
    assert observed["policy"] is policy
    assert observed["trusted_root"] is _FakeTrustConfig.trusted_root
    assert reference == RekorVerificationReference(
        trust_root_identity=SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY,
        trust_root_version=(
            "sha256:"
            + canonical_sha256({"mediaType": "synthetic-root", "tlogs": []})
        ),
        verifier="sigstore-python",
        verifier_version="4.5.0",
    )
