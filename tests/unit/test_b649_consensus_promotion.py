"""Unit probes for the Authority B candidate and read-only eligibility gate."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.domain.research_live_forecast import (
    CANONICAL_CONSENSUS,
    CONSENSUS_MISSING,
    canonical_json,
    object_json,
)
from lottolab.infrastructure import b649_consensus_promotion as promotion_module
from lottolab.infrastructure.b649_consensus_promotion import (
    BLOCKER_DEADLINE_PASSED,
    BLOCKER_DEADLINE_REACHED,
    BLOCKER_OFFICIAL_OUTCOME_PRESENT,
    BLOCKER_OFFICIAL_OUTCOME_UNKNOWN,
    BLOCKER_SCHEDULE_AUTHORITY_MISSING,
    BLOCKER_SCHEDULE_HASH_CHANGED,
    BLOCKER_SCHEDULE_HASH_NOT_BOUND,
    BLOCKER_TARGET_CHANGED,
    CONSENSUS_STREAM,
    CONSENSUS_STREAM_VERSION,
    CanonicalConsensusEligibilityGate,
    ConsensusCandidateError,
    PromotionRequest,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    EXPECTED_CANDIDATE_LOCATOR as PRODUCTION_CANDIDATE_LOCATOR,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    EXPECTED_CANDIDATE_SHA256 as PRODUCTION_CANDIDATE_SHA256,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    EXPECTED_OPERATION_ROOT as PRODUCTION_OPERATION_ROOT,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    normalized_announcement_sha256,
)

_SCHEDULE_HASH = "a" * 64
_BEFORE_DEADLINE = datetime(2026, 9, 11, 12, 29, 59, tzinfo=UTC)
_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/b649_consensus_promotion"
_HERMETIC_OPERATION_ROOT = _FIXTURE_ROOT / "authority_b"
_HERMETIC_CANDIDATE_LOCATOR = _HERMETIC_OPERATION_ROOT / (
    "forecasts/115000087/B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/"
    "final_forecast_payload.json"
)
_PR283_CANDIDATE_LOCATOR = _FIXTURE_ROOT / "pr283_descriptive/successor_candidate_payload.json"
_AUTHORITY_B_SHA256 = "6290813f8bc7669425fb106a576499bcf5d2d48162e5d05bebdcf6a575a2fe3c"
_AUTHORITY_B_BYTE_LENGTH = 9959
_PR283_CANDIDATE_SHA256 = "d21444820905d49aefb84bfb405709cfd95b95a9484ef525244f9e1c1d40ea3e"


@pytest.fixture(autouse=True)
def _use_hermetic_authority_b(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route production loader globals to the committed test-only mirror."""

    monkeypatch.setattr(
        promotion_module,
        "EXPECTED_OPERATION_ROOT",
        _HERMETIC_OPERATION_ROOT,
    )
    monkeypatch.setattr(
        promotion_module,
        "EXPECTED_CANDIDATE_LOCATOR",
        _HERMETIC_CANDIDATE_LOCATOR,
    )


def _candidate():
    return promotion_module.load_consensus_candidate(
        _HERMETIC_CANDIDATE_LOCATOR,
        candidate_sha256=_AUTHORITY_B_SHA256,
        source_root=_HERMETIC_OPERATION_ROOT,
    )


def _request(
    request_id: str = "unit-request",
    *,
    schedule_hash: str = _SCHEDULE_HASH,
) -> PromotionRequest:
    return PromotionRequest(
        request_id=request_id,
        request_sha256=("b" if request_id == "unit-request" else "c") * 64,
        expected_current_version=0,
        schedule_authority_sha256=schedule_hash,
        authorization_evidence_reference="test://authorization/unit",
        promotion_executor_identity="unit-test-executor",
        execution_source_id="test://b649-cli",
        execution_source_version="unit-v1",
        promotion_attempted_at=datetime(2026, 9, 10, 12, tzinfo=UTC),
        command_runtime_identity={
            "python": "fixture-python",
            "executable": "/fixture/python",
            "command": ["b649-promote", "unit"],
        },
    )


def _scheduled_record(schedule_hash: str | None = _SCHEDULE_HASH) -> ScheduledDrawIdentityRecord:
    target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        "115000087",
        datetime(2026, 9, 11).date(),
    )
    announcement = TargetAnnouncement(
        target=target,
        schedule_timezone="Asia/Taipei",
        scheduled_at=datetime(2026, 9, 11, 12, 30, tzinfo=UTC),
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
            source_version="taiwan-lottery-official-schedule-v1",
            source_locator="https://fixture.example/schedule",
            source_sha256="d" * 64,
            observed_at=datetime(2026, 9, 10, tzinfo=UTC),
        ),
    )
    return ScheduledDrawIdentityRecord(
        internal_id=1,
        announcement=announcement,
        normalized_announcement_hash=normalized_announcement_sha256(announcement),
        ingestion_run_id="fixture-ingestion",
        created_at=datetime(2026, 9, 10, 1, tzinfo=UTC),
        outcome_state=ScheduledDrawOutcomeState.NOT_POPULATED,
        outcome_draw_internal_id=None,
        immutable_schedule_sha256=schedule_hash,
    )


class _ScheduleReader:
    def __init__(self, record: ScheduledDrawIdentityRecord | None) -> None:
        self.record = record

    def get_scheduled_draw(
        self,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> ScheduledDrawIdentityRecord | None:
        assert lottery_type is LotteryType.BIG_LOTTO
        assert draw_number == "115000087"
        return self.record


class _OutcomeProbe:
    def __init__(self, presence: OutcomePresenceAtPrediction | str) -> None:
        self.presence = presence

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation:
        if self.presence == "UNKNOWN":
            return cast(OutcomePresenceAttestation, SimpleNamespace(presence="UNKNOWN"))
        return OutcomePresenceAttestation(
            target=target,
            presence=OutcomePresenceAtPrediction(self.presence),
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="fixture://outcome-presence",
                source_version="unit-v1",
                source_locator="fixture://outcome-presence",
                source_sha256="e" * 64,
                observed_at=as_of,
            ),
        )


def _gate(
    *,
    schedule_hash: str | None = _SCHEDULE_HASH,
    presence: OutcomePresenceAtPrediction | str = OutcomePresenceAtPrediction.ABSENT,
) -> CanonicalConsensusEligibilityGate:
    return CanonicalConsensusEligibilityGate(
        schedule_reader=_ScheduleReader(_scheduled_record(schedule_hash)),
        outcome_probe=_OutcomeProbe(presence),
    )


def test_authority_b_loader_preserves_exact_bytes_and_rejects_old_locator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    request = _request()
    forecast = candidate.build_forecast(request)

    assert Path(
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
        "B649_OPERATIONAL_PREDICTION_LOOP_R1/forecasts/115000087/"
        "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/"
        "final_forecast_payload.json"
    ) == PRODUCTION_CANDIDATE_LOCATOR
    assert PRODUCTION_CANDIDATE_SHA256 == _AUTHORITY_B_SHA256
    assert candidate.candidate_locator == _HERMETIC_CANDIDATE_LOCATOR
    assert candidate.candidate_bytes == _HERMETIC_CANDIDATE_LOCATOR.read_bytes()
    assert len(candidate.candidate_bytes) == _AUTHORITY_B_BYTE_LENGTH
    assert candidate.candidate_sha256 == _AUTHORITY_B_SHA256
    assert candidate.source_root == _HERMETIC_OPERATION_ROOT
    assert len(candidate.stream_inputs) == 11
    assert forecast.provenance_class == CANONICAL_CONSENSUS
    assert forecast.forecast_stream_id == CONSENSUS_STREAM
    assert forecast.forecast_stream_version == CONSENSUS_STREAM_VERSION
    assert forecast.payload_bytes == candidate.candidate_bytes
    assert forecast.target["schedule_authority_sha256"] == _SCHEDULE_HASH
    assert forecast.original == dict.fromkeys(forecast.original)
    assert forecast.missing_provenance_json == canonical_json(CONSENSUS_MISSING)
    imported = object_json(forecast.import_execution_json or "")
    assert imported["activation_event"] == "CANONICAL_CONSENSUS_PROMOTION_IMPORT"
    assert imported["aggregation_execution"] == "NOT_PERFORMED"
    assert imported["native_generation"] == "NOT_PERFORMED"
    assert imported["schedule_authority_sha256"] == _SCHEDULE_HASH
    provenance = forecast.consensus_provenance
    assert provenance is not None
    assert provenance["candidate"] == {
        "locator": str(_HERMETIC_CANDIDATE_LOCATOR),
        "sha256": _AUTHORITY_B_SHA256,
    }
    implementation = cast(dict[str, object], provenance["implementation"])
    assert implementation["commit"] == "573eb1aa519ccf4eb0c688bff0ca2b6c28183558"
    assert provenance["production"] != imported
    assert provenance["strategy_reexecution"] == "NO"
    assert provenance["aggregation_reexecution"] == "NO"
    forecast.validate()

    with monkeypatch.context() as production:
        production.setattr(
            promotion_module,
            "EXPECTED_OPERATION_ROOT",
            PRODUCTION_OPERATION_ROOT,
        )
        production.setattr(
            promotion_module,
            "EXPECTED_CANDIDATE_LOCATOR",
            PRODUCTION_CANDIDATE_LOCATOR,
        )
        with pytest.raises(ConsensusCandidateError, match="Authority B artifact"):
            promotion_module.load_consensus_candidate(
                _PR283_CANDIDATE_LOCATOR,
                candidate_sha256=_PR283_CANDIDATE_SHA256,
            )


def test_promotion_request_requires_schedule_authority_hash() -> None:
    with pytest.raises(ValueError, match="schedule_authority_sha256"):
        PromotionRequest(
            request_id="request",
            request_sha256="b" * 64,
            expected_current_version=0,
            schedule_authority_sha256="not-a-sha",
            authorization_evidence_reference="auth",
            promotion_executor_identity="executor",
            execution_source_id="source",
            execution_source_version="v1",
        )


def test_gate_accepts_matching_immutable_schedule_hash_before_strict_deadline() -> None:
    result = _gate().check(_candidate().build_forecast(_request()).target, now=_BEFORE_DEADLINE)
    assert result.eligible
    assert result.blockers == ()
    assert result.schedule_hash == _SCHEDULE_HASH
    assert result.outcome_presence == "ABSENT"


def test_gate_requires_hash_binding_and_rejects_changed_hash() -> None:
    target = _candidate().target
    missing = _gate().check(target, now=_BEFORE_DEADLINE)
    assert not missing.eligible
    assert BLOCKER_SCHEDULE_HASH_NOT_BOUND in missing.blockers

    changed_target = dict(target)
    changed_target["schedule_authority_sha256"] = "b" * 64
    changed = _gate().check(changed_target, now=_BEFORE_DEADLINE)
    assert not changed.eligible
    assert BLOCKER_SCHEDULE_HASH_CHANGED in changed.blockers

    missing_authority = _gate(schedule_hash=None).check(
        _candidate().build_forecast(_request()).target,
        now=_BEFORE_DEADLINE,
    )
    assert BLOCKER_SCHEDULE_AUTHORITY_MISSING in missing_authority.blockers


def test_gate_rejects_target_outcome_and_unknown_presence() -> None:
    forecast = _candidate().build_forecast(_request())
    changed_target = dict(forecast.target)
    changed_target["target_draw_number"] = "115000088"
    result = _gate().check(changed_target, now=_BEFORE_DEADLINE)
    assert BLOCKER_TARGET_CHANGED in result.blockers

    present_target = dict(forecast.target)
    present_target["target_result_used"] = True
    present = _gate(presence=OutcomePresenceAtPrediction.PRESENT).check(
        present_target,
        now=_BEFORE_DEADLINE,
    )
    assert BLOCKER_OFFICIAL_OUTCOME_PRESENT in present.blockers

    unknown = _gate(presence="UNKNOWN").check(forecast.target, now=_BEFORE_DEADLINE)
    assert BLOCKER_OFFICIAL_OUTCOME_UNKNOWN in unknown.blockers


def test_gate_uses_strict_deadline_with_local_timezone() -> None:
    forecast = _candidate().build_forecast(_request())
    at_deadline = _gate().check(
        forecast.target,
        now=datetime(2026, 9, 11, 20, 30, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert BLOCKER_DEADLINE_REACHED in at_deadline.blockers
    assert not at_deadline.eligible

    after_deadline = _gate().check(
        forecast.target,
        now=datetime(2026, 9, 11, 20, 30, 1, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert BLOCKER_DEADLINE_PASSED in after_deadline.blockers
    assert not after_deadline.eligible


def test_gate_schedule_time_drift_is_a_hard_blocker() -> None:
    record = _scheduled_record()
    drifted = replace(
        record,
        announcement=replace(
            record.announcement,
            scheduled_at=datetime(2026, 9, 11, 12, 31, tzinfo=UTC),
        ),
    )
    result = CanonicalConsensusEligibilityGate(
        schedule_reader=_ScheduleReader(drifted),
        outcome_probe=_OutcomeProbe(OutcomePresenceAtPrediction.ABSENT),
    ).check(_candidate().build_forecast(_request()).target, now=_BEFORE_DEADLINE)
    assert not result.eligible
    assert "SCHEDULED_TIME_CHANGED" in result.blockers
    assert BLOCKER_SCHEDULE_AUTHORITY_MISSING not in result.blockers
