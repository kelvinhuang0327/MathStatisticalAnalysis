from __future__ import annotations

import hashlib
import stat
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from lottolab.application.biglotto_l2_pairwise_prospective_shadow_capture import (
    FileSystemProspectiveShadowBundleStore,
    ProspectiveCandidateRuntime,
    ProspectiveShadowBundleConflictError,
    ProspectiveShadowBundleVerificationError,
    ProspectiveShadowCaptureRequest,
    ProspectiveShadowCaptureService,
    ProspectiveShadowSealStatus,
    capture_prospective_shadow_bundle,
    serialize_prospective_shadow_bundle,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import CreateOnceOutcome, ObservationTarget

TARGET_DRAW = "115000082"
HISTORY_CUTOFF = "115000081"
EXPECTED_IDS = tuple(f"S{index}" for index in range(1, 10))
GENERATED_AT = datetime(2026, 8, 31, 1, tzinfo=UTC)
HISTORY: tuple[object, ...] = tuple(range(751))


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
                raise AssertionError("an exact existing bundle must bypass producers")
            assert history is HISTORY
            assert history_cutoff == HISTORY_CUTOFF
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
                auxiliary_operand_availability=(
                    AuxiliaryOperandAvailability.EXPLICITLY_MISSING
                ),
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
) -> ProspectiveShadowCaptureRequest:
    return ProspectiveShadowCaptureRequest(
        announcement=_announcement(),
        history=HISTORY,
        history_cutoff=HISTORY_CUTOFF,
        expected_candidate_ids=EXPECTED_IDS,
        candidate_runtimes=_runtimes(calls, fail_if_called=fail_if_called),
        generated_at_utc=GENERATED_AT,
        repository_head="a" * 40,
        repository_tree="b" * 40,
    )


def test_filesystem_seal_is_exclusive_durable_and_idempotent(tmp_path: Path) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    service = ProspectiveShadowCaptureService(store)
    request = _request(calls)

    created = service.seal(request)
    record_path = store.record_path_for(tmp_path, request.announcement.target)

    assert created.status is ProspectiveShadowSealStatus.CREATED
    assert calls == list(EXPECTED_IDS)
    assert record_path.read_bytes() == created.bundle_bytes
    assert stat.S_IMODE(record_path.stat().st_mode) == 0o600
    assert tuple(tmp_path.iterdir()) == (record_path,)

    existing_request = replace(
        _request(calls, fail_if_called=True),
        generated_at_utc=GENERATED_AT + timedelta(minutes=1),
    )
    existing = service.seal(existing_request)

    assert existing.status is ProspectiveShadowSealStatus.EXACT_IDEMPOTENT_EXISTING
    assert existing.bundle_bytes == created.bundle_bytes
    assert calls == list(EXPECTED_IDS)
    assert tuple(tmp_path.iterdir()) == (record_path,)


def test_conflicting_second_authority_fails_without_overwrite(tmp_path: Path) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    service = ProspectiveShadowCaptureService(store)
    request = _request(calls)
    created = service.seal(request)
    path = store.record_path_for(tmp_path, request.announcement.target)

    conflicting = replace(
        _request(calls, fail_if_called=True),
        repository_tree="d" * 40,
    )
    with pytest.raises(ProspectiveShadowBundleConflictError, match="different immutable"):
        service.seal(conflicting)

    assert path.read_bytes() == created.bundle_bytes
    assert calls == list(EXPECTED_IDS)


def test_store_reports_exact_existing_and_conflicting_canonical_bytes(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    request = _request(calls)
    first = capture_prospective_shadow_bundle(request)
    first_bytes = serialize_prospective_shadow_bundle(first)

    assert store.create_bundle(request.announcement.target, first_bytes) is (
        CreateOnceOutcome.INSERTED
    )
    assert store.create_bundle(request.announcement.target, first_bytes) is (
        CreateOnceOutcome.ALREADY_PRESENT
    )

    later = capture_prospective_shadow_bundle(
        replace(request, generated_at_utc=GENERATED_AT + timedelta(minutes=1))
    )
    later_bytes = serialize_prospective_shadow_bundle(later)
    assert later_bytes != first_bytes
    assert store.create_bundle(request.announcement.target, later_bytes) is (
        CreateOnceOutcome.CONFLICT
    )
    assert store.read_bundle(request.announcement.target) == first_bytes


def test_tampered_existing_bundle_is_rejected_before_recapture(tmp_path: Path) -> None:
    calls: list[str] = []
    store = FileSystemProspectiveShadowBundleStore(tmp_path)
    service = ProspectiveShadowCaptureService(store)
    request = _request(calls)
    created = service.seal(request)
    path = store.record_path_for(tmp_path, request.announcement.target)
    original = created.bundle_bytes
    tampered = original.replace(b'"S1"', b'"X1"', 1)
    assert tampered != original
    path.write_bytes(tampered)

    with pytest.raises(ProspectiveShadowBundleVerificationError):
        service.seal(_request(calls, fail_if_called=True))

    assert calls == list(EXPECTED_IDS)
    assert path.read_bytes() == tampered
