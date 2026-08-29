"""Unit contracts for the read-only Next-Draw Recommendation lifecycle lookup."""

from __future__ import annotations

from datetime import UTC, date, datetime

from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
    normalized_announcement_sha256,
)
from lottolab.application.pre_outcome_target_operational import (
    OutcomePresenceEvidenceUnavailableError,
)
from lottolab.application.use_cases.get_next_draw_recommendation_lifecycle import (
    GetNextDrawRecommendationLifecycle,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationLifecycleState,
    NextDrawRecommendationSeal,
    SealedRecommendationBucket,
)
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget, OutcomePresenceAtPrediction

LOTTERY_TYPE = LotteryType.BIG_LOTTO
TARGET = ObservationTarget(
    lottery_type=LOTTERY_TYPE, draw_number="115000090", draw_date=date(2099, 9, 1)
)
SCHEDULED_AT = datetime(2099, 9, 1, 8, 30, tzinfo=UTC)
NOW = datetime(2099, 8, 30, 6, 0, tzinfo=UTC)


def _announcement() -> TargetAnnouncement:
    return TargetAnnouncement(
        target=TARGET,
        schedule_timezone="Asia/Taipei",
        scheduled_at=SCHEDULED_AT,
        source=TargetSourceProvenance(
            source_id="official-schedule",
            source_version="v1",
            source_locator="https://example.test/115000090",
            source_sha256="a" * 64,
            observed_at=NOW,
        ),
    )


def _record() -> ScheduledDrawIdentityRecord:
    announcement = _announcement()
    return ScheduledDrawIdentityRecord(
        internal_id=1,
        announcement=announcement,
        normalized_announcement_hash=normalized_announcement_sha256(announcement),
        ingestion_run_id="run-1",
        created_at=NOW,
        outcome_state=ScheduledDrawOutcomeState.NOT_POPULATED,
        outcome_draw_internal_id=None,
    )


class _Reader:
    def __init__(
        self,
        *,
        future: ScheduledDrawIdentityRecord | None = None,
        due: ScheduledDrawIdentityRecord | None = None,
    ) -> None:
        self._future = future
        self._due = due

    def find_earliest_unpopulated_future(self, lottery_type, as_of):
        del lottery_type, as_of
        return self._future

    def find_earliest_unpopulated_due(self, lottery_type, as_of):
        del lottery_type, as_of
        return self._due

    def get_scheduled_draw(self, lottery_type, draw_number):
        del lottery_type, draw_number
        return self._future or self._due


class _PresenceProbe:
    def __init__(self, presence: OutcomePresenceAtPrediction | None) -> None:
        self._presence = presence
        self.calls = 0

    def probe(self, target, *, as_of):
        self.calls += 1
        if self._presence is None:
            raise OutcomePresenceEvidenceUnavailableError(
                "no official audit covers this target yet"
            )
        from lottolab.domain.pre_outcome_target import OutcomePresenceAttestation

        return OutcomePresenceAttestation(
            target=target,
            presence=self._presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="official-presence-audit",
                source_version="v1",
                source_locator="https://example.test/audit",
                source_sha256="b" * 64,
                observed_at=as_of,
            ),
        )


class _SealReader:
    def __init__(self, seal: NextDrawRecommendationSeal | None = None) -> None:
        self._seal = seal
        self.calls = 0

    def get_seal(self, target):
        self.calls += 1
        return self._seal if self._seal is not None and self._seal.target == target else None


def _seal() -> NextDrawRecommendationSeal:
    from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS

    buckets = tuple(
        SealedRecommendationBucket(
            native_ticket_count=count,
            availability="UNAVAILABLE",
            total_candidate_count=0,
            ranked_strategy_ids=(),
            ranking_projection_sha256="c" * 64,
            sealed_tickets=(),
        )
        for count in NATIVE_TICKET_COUNT_BUCKETS
    )
    return NextDrawRecommendationSeal.create(
        target=TARGET,
        target_scheduled_at=SCHEDULED_AT,
        sealed_at=NOW,
        target_registration_digest="d" * 64,
        evidence_artifact_sha256="e" * 64,
        causal_history_sha256="f" * 64,
        causal_history_draw_count=2,
        buckets=buckets,
    )


def _clock() -> datetime:
    return NOW


def test_no_eligible_target_reports_waiting() -> None:
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.WAITING_FOR_ELIGIBLE_TARGET
    assert view.target is None
    assert view.seal is None


def test_future_target_with_no_seal_reports_target_available() -> None:
    seal_reader = _SealReader()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(future=_record()),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=seal_reader,
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.TARGET_AVAILABLE
    assert view.target == TARGET
    assert view.seal is None
    # A read-only lookup must never probe outcome presence for an unsealed
    # target -- there is nothing sealed yet to confirm absence for.
    assert seal_reader.calls == 1


def test_due_but_never_sealed_target_reports_waiting_not_available() -> None:
    """Once the pre-draw window has closed without a seal, it is no longer a
    *sealable* (eligible) target -- reported the same as no target at all."""

    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(due=_record()),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.WAITING_FOR_ELIGIBLE_TARGET
    assert view.target is None


def test_sealed_target_with_absent_outcome_reports_predictions_sealed() -> None:
    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(future=_record()),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(seal),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.PREDICTIONS_SEALED
    assert view.target == TARGET
    assert view.seal == seal


def test_sealed_target_with_present_outcome_reports_outcome_available() -> None:
    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(future=_record()),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.PRESENT),
        seal_reader=_SealReader(seal),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.OUTCOME_AVAILABLE
    assert view.seal == seal


def test_sealed_target_still_due_and_present_reports_outcome_available() -> None:
    """A seal legitimately outlives the "future" window: once the schedule
    passes it moves to "due", but a prior seal for that exact target must
    still be recognized and progressed to OUTCOME_AVAILABLE once resolved."""

    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(due=_record()),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.PRESENT),
        seal_reader=_SealReader(seal),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.OUTCOME_AVAILABLE


def test_unavailable_presence_evidence_stays_sealed_rather_than_failing() -> None:
    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(future=_record()),
        outcome_presence_probe=_PresenceProbe(None),
        seal_reader=_SealReader(seal),
        clock=_clock,
    )

    view = use_case.execute(LOTTERY_TYPE)

    assert view.state is NextDrawRecommendationLifecycleState.PREDICTIONS_SEALED


def test_lifecycle_lookup_is_pure_and_repeatable() -> None:
    """Calling execute twice in a row must be indistinguishable from once."""

    seal_reader = _SealReader()
    reader = _Reader(future=_record())
    probe = _PresenceProbe(OutcomePresenceAtPrediction.ABSENT)
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=reader,
        outcome_presence_probe=probe,
        seal_reader=seal_reader,
        clock=_clock,
    )

    first = use_case.execute(LOTTERY_TYPE)
    second = use_case.execute(LOTTERY_TYPE)

    assert first == second
