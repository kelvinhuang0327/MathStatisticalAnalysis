from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.application.biglotto_l2_pairwise_prospective_shadow_capture import (
    FileSystemProspectiveShadowBundleStore,
    ProspectiveCandidateRuntime,
    ProspectiveShadowBundleConflictError,
    ProspectiveShadowBundleVerificationError,
    ProspectiveShadowCaptureRequest,
    ProspectiveShadowCaptureService,
    ProspectiveShadowIncompleteEvidenceError,
    ProspectiveShadowOutcomeAvailableError,
    ProspectiveShadowReceiptShapeError,
    ProspectiveShadowReceiptTamperError,
    ProspectiveShadowSealResult,
    ProspectiveShadowSealStatus,
    _capture_prospective_shadow_bundle_with_runtime,  # pyright: ignore[reportPrivateUsage]
    deserialize_prospective_shadow_final_capture_receipt,
    serialize_prospective_shadow_bundle,
    verify_prospective_shadow_capture_evidence,
    verify_prospective_shadow_final_capture_receipt,
    verify_prospective_shadow_pre_producer_receipt,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
)

TARGET_DRAW = "115000082"
HISTORY_CUTOFF = "115000081"
EXPECTED_IDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C8", "C9", "C10")
PRE_CHECK_AT = datetime(2026, 8, 31, 1, tzinfo=UTC)
CAPTURE_STARTED_AT = PRE_CHECK_AT + timedelta(seconds=1)
CAPTURE_SEALED_AT = PRE_CHECK_AT + timedelta(seconds=2)
FINAL_CHECK_AT = PRE_CHECK_AT + timedelta(seconds=3)
HISTORY: tuple[object, ...] = tuple(range(751))


def _capture(request: ProspectiveShadowCaptureRequest):
    bundle, _ = _capture_prospective_shadow_bundle_with_runtime(
        request,
        monotonic_ns=None,
    )
    return bundle


def _announcement() -> TargetAnnouncement:
    return TargetAnnouncement(
        target=ObservationTarget(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=TARGET_DRAW,
            draw_date=date(2026, 9, 1),
        ),
        schedule_timezone="Asia/Taipei",
        scheduled_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        source=TargetSourceProvenance(
            source_id="synthetic_schedule",
            source_version="r1",
            source_locator="fixture://future-draw",
            source_sha256="c" * 64,
            observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        ),
    )


def _method_id(candidate_id: str) -> str:
    return f"SYNTHETIC_PAIRWISE_METHOD_{candidate_id}"


def _runtimes(
    calls: list[str],
    *,
    fail_if_called: bool = False,
    before_producer: Callable[[str], None] | None = None,
) -> tuple[ProspectiveCandidateRuntime, ...]:
    runtimes: list[ProspectiveCandidateRuntime] = []
    for candidate_id in reversed(EXPECTED_IDS):
        index = int(candidate_id[1:])

        def produce(
            history: tuple[object, ...],
            history_cutoff: str,
            /,
            *,
            bound_id: str = candidate_id,
            bound_index: int = index,
        ) -> OrderedCandidateEmission:
            if fail_if_called:
                raise AssertionError("sealed authority must bypass producers")
            assert history is HISTORY
            assert history_cutoff == HISTORY_CUTOFF
            if before_producer is not None:
                before_producer(bound_id)
            calls.append(bound_id)
            return OrderedCandidateEmission(
                schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
                lottery_type=LotteryType.BIG_LOTTO,
                strategy_id=_method_id(bound_id),
                strategy_version="r1",
                replicate=1,
                target_draw=TARGET_DRAW,
                history_cutoff=HISTORY_CUTOFF,
                emitted_main_numbers=tuple(range(bound_index, bound_index + 6)),
                auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
                auxiliary_operand_availability=(AuxiliaryOperandAvailability.EXPLICITLY_MISSING),
                auxiliary_operand_value=None,
            )

        runtimes.append(
            ProspectiveCandidateRuntime(
                candidate_id=candidate_id,
                method_id=_method_id(candidate_id),
                semantic_signature=hashlib.sha256(candidate_id.encode()).hexdigest(),
                strategy_version="r1",
                producer=produce,
            )
        )
    return tuple(runtimes)


def _request(
    calls: list[str],
    *,
    fail_if_called: bool = False,
    before_producer: Callable[[str], None] | None = None,
) -> ProspectiveShadowCaptureRequest:
    return ProspectiveShadowCaptureRequest(
        announcement=_announcement(),
        history=HISTORY,
        history_cutoff=HISTORY_CUTOFF,
        expected_candidate_ids=EXPECTED_IDS,
        candidate_runtimes=_runtimes(
            calls,
            fail_if_called=fail_if_called,
            before_producer=before_producer,
        ),
        generated_at_utc=CAPTURE_STARTED_AT,
        repository_head="a" * 40,
        repository_tree="b" * 40,
    )


class _SequenceClock:
    def __init__(self) -> None:
        self._values = iter((PRE_CHECK_AT, CAPTURE_STARTED_AT, CAPTURE_SEALED_AT, FINAL_CHECK_AT))

    def __call__(self) -> datetime:
        return next(self._values)


class _StepMonotonic:
    def __init__(self) -> None:
        self._value = 1_000

    def __call__(self) -> int:
        value = self._value
        self._value += 10
        return value


class _PresenceProbe:
    def __init__(
        self,
        presences: tuple[OutcomePresenceAtPrediction, ...],
        events: list[str] | None = None,
    ) -> None:
        self._presences = iter(presences)
        self._events = events
        self.calls = 0

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation:
        self.calls += 1
        if self._events is not None:
            self._events.append("PRE_OUTCOME_CHECK" if self.calls == 1 else "FINAL_OUTCOME_CHECK")
        presence = next(self._presences)
        return OutcomePresenceAttestation(
            target=target,
            presence=presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="synthetic_official_presence",
                source_version="r1",
                source_locator=f"fixture://official-presence/{target.draw_number}",
                source_sha256=hashlib.sha256(
                    f"{target.draw_number}:{self.calls}:{presence.value}".encode()
                ).hexdigest(),
                observed_at=as_of,
            ),
        )


class _RecordingStore(FileSystemProspectiveShadowBundleStore):
    def __init__(self, root: Path, events: list[str]) -> None:
        super().__init__(root)
        self._events = events

    def create_pre_producer_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome:
        result = super().create_pre_producer_receipt(target, data)
        if result is CreateOnceOutcome.INSERTED:
            self._events.append("DURABLE_PRE_RECEIPT")
        return result

    def create_bundle(self, target: ObservationTarget, data: bytes) -> CreateOnceOutcome:
        result = super().create_bundle(target, data)
        if result is CreateOnceOutcome.INSERTED:
            self._events.append("BUNDLE_SEAL")
        return result

    def create_final_capture_receipt(
        self,
        target: ObservationTarget,
        data: bytes,
    ) -> CreateOnceOutcome:
        result = super().create_final_capture_receipt(target, data)
        if result is CreateOnceOutcome.INSERTED:
            self._events.append("DURABLE_FINAL_RECEIPT")
        return result


def _service(
    store: FileSystemProspectiveShadowBundleStore,
    *,
    presences: tuple[OutcomePresenceAtPrediction, ...] = (
        OutcomePresenceAtPrediction.ABSENT,
        OutcomePresenceAtPrediction.ABSENT,
    ),
    events: list[str] | None = None,
) -> tuple[ProspectiveShadowCaptureService, _PresenceProbe]:
    probe = _PresenceProbe(presences, events)
    return (
        ProspectiveShadowCaptureService(
            store,
            outcome_presence_probe=probe,
            clock=_SequenceClock(),
            monotonic_ns=_StepMonotonic(),
        ),
        probe,
    )


def _capture_complete(
    root: Path,
) -> tuple[
    FileSystemProspectiveShadowBundleStore,
    ProspectiveShadowCaptureService,
    ProspectiveShadowCaptureRequest,
    ProspectiveShadowSealResult,
    list[str],
]:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(root)
    service, _ = _service(store)
    request = _request(calls)
    return store, service, request, service.seal(request), calls


def test_full_capture_sequence_is_durable_exact_and_idempotent(tmp_path: Path) -> None:
    events: list[str] = []
    calls: list[str] = []
    store = _RecordingStore(tmp_path, events)

    def before_producer(candidate_id: str) -> None:
        pre_bytes = store.read_pre_producer_receipt(_announcement().target)
        assert pre_bytes is not None
        verify_prospective_shadow_pre_producer_receipt(pre_bytes)
        events.append(f"PRODUCER_{candidate_id}")

    request = _request(calls, before_producer=before_producer)
    service, probe = _service(store, events=events)
    created = service.seal(request)

    assert created.status is ProspectiveShadowSealStatus.CREATED
    assert calls == list(EXPECTED_IDS)
    assert probe.calls == 2
    assert events == [
        "PRE_OUTCOME_CHECK",
        "DURABLE_PRE_RECEIPT",
        *(f"PRODUCER_{candidate_id}" for candidate_id in EXPECTED_IDS),
        "BUNDLE_SEAL",
        "FINAL_OUTCOME_CHECK",
        "DURABLE_FINAL_RECEIPT",
    ]
    assert all(
        len(record.ticket) == 6
        and len(set(record.ticket)) == 6
        and tuple(sorted(record.ticket)) == record.ticket
        and all(1 <= number <= 49 for number in record.ticket)
        for record in created.bundle.predictions
    )
    final = created.final_capture_receipt
    assert tuple(item.candidate_id for item in final.per_candidate_runtime_ns) == EXPECTED_IDS
    assert tuple(item.runtime_ns for item in final.per_candidate_runtime_ns) == (10,) * 9
    assert final.total_capture_runtime_ns == 190
    assert final.capture_started_at_utc == CAPTURE_STARTED_AT
    assert final.capture_sealed_at_utc == CAPTURE_SEALED_AT
    assert final.final_outcome_absence_checked_at_utc == FINAL_CHECK_AT
    assert final.final_outcome_absent is True
    assert created.pre_producer_receipt.outcome_absent is True
    assert verify_prospective_shadow_capture_evidence(
        pre_producer_receipt_bytes=created.pre_producer_receipt_bytes,
        bundle_bytes=created.bundle_bytes,
        final_capture_receipt_bytes=created.final_capture_receipt_bytes,
    ) == (
        created.pre_producer_receipt,
        created.bundle,
        created.final_capture_receipt,
    )

    target = request.announcement.target
    paths = (
        store.pre_producer_receipt_path_for(tmp_path, target),
        store.record_path_for(tmp_path, target),
        store.final_capture_receipt_path_for(tmp_path, target),
    )
    assert all(path.is_file() for path in paths)
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in paths)
    assert {path.name for path in tmp_path.iterdir()} == {path.name for path in paths}

    def fail_clock() -> datetime:
        raise AssertionError("idempotent recapture must not read the wall clock")

    def fail_monotonic() -> int:
        raise AssertionError("idempotent recapture must not read the monotonic clock")

    class FailProbe:
        def probe(
            self,
            target: ObservationTarget,
            *,
            as_of: datetime,
        ) -> OutcomePresenceAttestation:
            raise AssertionError("idempotent recapture must not probe outcome presence")

    idempotent_service = ProspectiveShadowCaptureService(
        store,
        outcome_presence_probe=FailProbe(),
        clock=fail_clock,
        monotonic_ns=fail_monotonic,
    )
    existing = idempotent_service.seal(_request(calls, fail_if_called=True))
    assert existing.status is ProspectiveShadowSealStatus.EXACT_IDEMPOTENT_EXISTING
    assert existing.pre_producer_receipt_bytes == created.pre_producer_receipt_bytes
    assert existing.bundle_bytes == created.bundle_bytes
    assert existing.final_capture_receipt_bytes == created.final_capture_receipt_bytes
    assert calls == list(EXPECTED_IDS)


def test_conflicting_second_authority_fails_without_overwrite(tmp_path: Path) -> None:
    store, service, request, created, calls = _capture_complete(tmp_path)
    path = store.record_path_for(tmp_path, request.announcement.target)
    conflicting = replace(
        _request(calls, fail_if_called=True),
        repository_tree="d" * 40,
    )

    with pytest.raises(ProspectiveShadowBundleConflictError, match="different immutable"):
        service.seal(conflicting)

    assert path.read_bytes() == created.bundle_bytes
    assert calls == list(EXPECTED_IDS)


def test_store_reports_exact_existing_and_conflicting_canonical_bundle_bytes(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    request = _request(calls)
    first = _capture(request)
    first_bytes = serialize_prospective_shadow_bundle(first)

    assert store.create_bundle(request.announcement.target, first_bytes) is (
        CreateOnceOutcome.INSERTED
    )
    assert store.create_bundle(request.announcement.target, first_bytes) is (
        CreateOnceOutcome.ALREADY_PRESENT
    )

    later = _capture(replace(request, generated_at_utc=CAPTURE_STARTED_AT + timedelta(minutes=1)))
    later_bytes = serialize_prospective_shadow_bundle(later)
    assert later_bytes != first_bytes
    assert store.create_bundle(request.announcement.target, later_bytes) is (
        CreateOnceOutcome.CONFLICT
    )
    assert store.read_bundle(request.announcement.target) == first_bytes


def test_tampered_existing_bundle_is_rejected_before_recapture(tmp_path: Path) -> None:
    store, service, request, created, calls = _capture_complete(tmp_path)
    path = store.record_path_for(tmp_path, request.announcement.target)
    tampered = created.bundle_bytes.replace(b'"C1"', b'"X1"', 1)
    assert tampered != created.bundle_bytes
    path.write_bytes(tampered)

    with pytest.raises(ProspectiveShadowBundleVerificationError):
        service.seal(_request(calls, fail_if_called=True))

    assert calls == list(EXPECTED_IDS)
    assert path.read_bytes() == tampered


def test_pre_and_final_receipt_tampering_are_rejected(tmp_path: Path) -> None:
    _, _, _, created, _ = _capture_complete(tmp_path)
    tampered_pre = created.pre_producer_receipt_bytes.replace(
        b'"outcome_absent":true',
        b'"outcome_absent":false',
    )
    tampered_final = created.final_capture_receipt_bytes.replace(
        b'"total_capture_runtime_ns":190',
        b'"total_capture_runtime_ns":191',
    )
    assert tampered_pre != created.pre_producer_receipt_bytes
    assert tampered_final != created.final_capture_receipt_bytes

    with pytest.raises(ProspectiveShadowReceiptTamperError):
        verify_prospective_shadow_pre_producer_receipt(tampered_pre)
    with pytest.raises(ProspectiveShadowReceiptTamperError):
        verify_prospective_shadow_final_capture_receipt(tampered_final)


def test_missing_or_float_runtime_encoding_is_rejected(tmp_path: Path) -> None:
    _, _, _, created, _ = _capture_complete(tmp_path)
    missing_payload = cast(
        dict[str, Any],
        loads_canonical(created.final_capture_receipt_bytes),
    )
    missing_runtimes = cast(list[dict[str, Any]], missing_payload["per_candidate_runtime_ns"])
    del missing_runtimes[0]["runtime_ns"]
    missing_payload["receipt_payload_sha256"] = self_key_removed_sha256(
        missing_payload,
        "receipt_payload_sha256",
    )
    with pytest.raises(ProspectiveShadowReceiptShapeError, match="keys are not closed"):
        deserialize_prospective_shadow_final_capture_receipt(canonical_bytes(missing_payload))

    float_payload = cast(
        dict[str, Any],
        loads_canonical(created.final_capture_receipt_bytes),
    )
    float_runtimes = cast(list[dict[str, Any]], float_payload["per_candidate_runtime_ns"])
    float_runtimes[0]["runtime_ns"] = 1.5
    float_bytes = json.dumps(
        float_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    with pytest.raises(ProspectiveShadowReceiptShapeError, match="LCJ-1"):
        deserialize_prospective_shadow_final_capture_receipt(float_bytes)


def test_final_outcome_presence_fails_closed_and_stays_non_countable(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    service, probe = _service(
        store,
        presences=(
            OutcomePresenceAtPrediction.ABSENT,
            OutcomePresenceAtPrediction.PRESENT,
        ),
    )
    request = _request(calls)

    with pytest.raises(ProspectiveShadowOutcomeAvailableError, match="non-countable"):
        service.seal(request)

    target = request.announcement.target
    assert probe.calls == 2
    assert calls == list(EXPECTED_IDS)
    assert store.read_pre_producer_receipt(target) is not None
    assert store.read_bundle(target) is not None
    assert store.read_final_capture_receipt(target) is None

    retry_service, retry_probe = _service(store)
    with pytest.raises(ProspectiveShadowIncompleteEvidenceError, match="non-countable"):
        retry_service.seal(_request(calls, fail_if_called=True))
    assert retry_probe.calls == 0
    assert calls == list(EXPECTED_IDS)
