"""Unit contracts for the explicit Next-Draw Recommendation seal command.

Uses an in-memory fake for every collaborator (schedule reader, causal-history
authority, target-authority store, outcome-presence probe, and seal store) so
every synthetic lifecycle scenario runs in isolation, with no filesystem or
database access. A deliberately empty strategy catalog keeps bucket/ticket
content trivial (every bucket is UNAVAILABLE with zero candidates) so these
tests exercise orchestration -- target resolution, drift detection, the fresh
final gate, and create-once semantics -- not ticket generation itself (that is
``GenerateNextDrawTopTickets``'s and ``BuildNextDrawRecommendationBucket``'s
own concern).
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
    normalized_announcement_sha256,
)
from lottolab.application.pre_outcome_target import (
    OutcomeAlreadyAvailableError,
    PreOutcomeTargetRegistrationService,
)
from lottolab.application.pre_outcome_target_operational import (
    PreOutcomeTargetOperationalService,
)
from lottolab.application.use_cases.seal_next_draw_recommendation import (
    InvalidScheduleTimeError,
    SealCausalHistoryDriftError,
    SealEvidenceLotteryTypeMismatchError,
    SealEvidenceUnavailableError,
    SealNextDrawRecommendation,
    SealOutcomeStatus,
    SealSourceGitIdentityError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSeal,
    SourceGitIdentity,
)
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
)
from lottolab.infrastructure.source_git_identity import GitSourceIdentityResolver
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog

LOTTERY_TYPE = LotteryType.BIG_LOTTO
DRAW_NUMBER = "115000090"
DRAW_DATE = date(2099, 9, 1)
TARGET = ObservationTarget(lottery_type=LOTTERY_TYPE, draw_number=DRAW_NUMBER, draw_date=DRAW_DATE)
SCHEDULED_AT = datetime(2099, 9, 1, 8, 30, tzinfo=UTC)  # local (Asia/Taipei) date stays 2099-09-01
REGISTERED_AT = datetime(2099, 8, 30, 6, 0, tzinfo=UTC)
SOURCE_GIT_IDENTITY = SourceGitIdentity(source_head="1" * 40, source_tree="2" * 40)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _announcement() -> TargetAnnouncement:
    return TargetAnnouncement(
        target=TARGET,
        schedule_timezone="Asia/Taipei",
        scheduled_at=SCHEDULED_AT,
        source=TargetSourceProvenance(
            source_id="official-schedule",
            source_version="v1",
            source_locator=f"https://example.test/{DRAW_NUMBER}",
            source_sha256=_sha256("announcement"),
            observed_at=REGISTERED_AT - timedelta(hours=1),
        ),
    )


def _record(announcement: TargetAnnouncement) -> ScheduledDrawIdentityRecord:
    return ScheduledDrawIdentityRecord(
        internal_id=1,
        announcement=announcement,
        normalized_announcement_hash=normalized_announcement_sha256(announcement),
        ingestion_run_id="run-1",
        created_at=REGISTERED_AT - timedelta(minutes=30),
        outcome_state=ScheduledDrawOutcomeState.NOT_POPULATED,
        outcome_draw_internal_id=None,
    )


def _history(*, sha_suffix: str = "history") -> CausalHistoryRef:
    return CausalHistoryRef(
        draw_count=2,
        last_draw_number="115000089",
        last_draw_date=date(2099, 8, 25),
        history_sha256=_sha256(sha_suffix),
    )


class _Reader:
    """Fake FutureDrawIdentityReader returning one fixed unpopulated future row."""

    def __init__(self, record: ScheduledDrawIdentityRecord | None) -> None:
        self._record = record

    def find_earliest_unpopulated_future(self, lottery_type, as_of):
        del lottery_type, as_of
        return self._record

    def find_earliest_unpopulated_due(self, lottery_type, as_of):
        del lottery_type, as_of
        return None

    def get_scheduled_draw(self, lottery_type, draw_number):
        del lottery_type, draw_number
        return self._record


class _HistoryAuthority:
    """Fake CausalHistoryAuthority whose answer can change between calls."""

    def __init__(self, *answers: CausalHistoryRef) -> None:
        self._answers = list(answers)
        self.calls = 0

    def resolve(self, target):
        del target
        index = min(self.calls, len(self._answers) - 1)
        self.calls += 1
        return self._answers[index]


class _AuthorityStore:
    """In-memory PreOutcomeTargetAuthorityStore, mirroring the create-once contract."""

    def __init__(self) -> None:
        self._data: dict[tuple, object] = {}

    def get_registration(self, target):
        return self._data.get(_key(target))

    def create_registration(self, registration):
        key = _key(registration.target)
        if key in self._data:
            return CreateOnceOutcome.CONFLICT
        self._data[key] = registration
        return CreateOnceOutcome.INSERTED


class _PresenceProbe:
    """Fake OutcomePresenceProbe whose presence answer can change between calls."""

    def __init__(self, *answers: OutcomePresenceAtPrediction) -> None:
        self._answers = list(answers) or [OutcomePresenceAtPrediction.ABSENT]
        self.calls = 0

    def probe(self, target, *, as_of):
        index = min(self.calls, len(self._answers) - 1)
        self.calls += 1
        return OutcomePresenceAttestation(
            target=target,
            presence=self._answers[index],
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="official-presence-audit",
                source_version="v1",
                source_locator="https://example.test/audit",
                source_sha256=_sha256("audit"),
                observed_at=as_of,
            ),
        )


class _SealStore:
    """In-memory NextDrawRecommendationSealStore mirroring the filesystem contract."""

    def __init__(self) -> None:
        self._data: dict[tuple, NextDrawRecommendationSeal] = {}
        self.create_calls = 0

    def get_seal(self, target):
        return self._data.get(_key(target))

    def create_seal(self, seal):
        self.create_calls += 1
        key = _key(seal.target)
        if key in self._data:
            return CreateOnceOutcome.CONFLICT
        self._data[key] = seal
        return CreateOnceOutcome.INSERTED


def _key(target: ObservationTarget) -> tuple:
    return (target.lottery_type, target.draw_number, target.draw_date)


def _clock(*ticks: datetime) -> object:
    values = list(ticks)

    class _Clock:
        def __call__(self) -> datetime:
            if len(values) > 1:
                return values.pop(0)
            return values[0]

    return _Clock()


def _evidence() -> NextDrawRecommendationEvidenceArtifact:
    return NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256=_sha256("draws"),
        source_draw_count=2,
        last_causal_draw_id="115000089",
        replay_depth=2,
        hit_tier_id="M3",
        records=(),
    )


def _causal_rows() -> tuple[CausalDrawRow, ...]:
    return (
        CausalDrawRow(draw="115000088", date="2099-08-18", numbers=(1, 2, 3, 4, 5, 6)),
        CausalDrawRow(draw="115000089", date="2099-08-25", numbers=(7, 8, 9, 10, 11, 12)),
    )


def _source_git_identity() -> SourceGitIdentity:
    return SOURCE_GIT_IDENTITY


def _build_use_case(
    *,
    reader: _Reader,
    history_authority: _HistoryAuthority,
    authority_store: _AuthorityStore,
    presence_probe: _PresenceProbe,
    seal_store: _SealStore,
    clock,
    evidence_factory=_evidence,
    source_git_identity_factory=_source_git_identity,
) -> SealNextDrawRecommendation:
    registration_service = PreOutcomeTargetRegistrationService(
        store=authority_store, outcome_presence_probe=presence_probe, clock=clock
    )
    operational_service = PreOutcomeTargetOperationalService(
        future_draw_identity_reader=reader,
        causal_history_authority=history_authority,
        registration_service=registration_service,
        clock=clock,
    )
    return SealNextDrawRecommendation(
        catalog=StrategyCatalog(()),
        operational_service=operational_service,
        causal_history_authority=history_authority,
        causal_history_rows_factory=lambda lottery_type: _causal_rows(),
        evidence_factory=evidence_factory,
        source_git_identity_factory=source_git_identity_factory,
        outcome_presence_probe=presence_probe,
        seal_store=seal_store,
        clock=clock,
    )


def test_no_eligible_target_writes_nothing() -> None:
    reader = _Reader(None)
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=reader,
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT),
    )

    result = use_case.execute(LOTTERY_TYPE)

    assert result.status is SealOutcomeStatus.NO_ELIGIBLE_TARGET
    assert result.seal is None
    assert seal_store.create_calls == 0


def test_target_available_seals_successfully_across_every_supported_bucket() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
    )

    result = use_case.execute(LOTTERY_TYPE)

    assert result.status is SealOutcomeStatus.CREATED
    assert result.seal is not None
    assert result.seal.target == TARGET
    assert result.seal.source_head == SOURCE_GIT_IDENTITY.source_head
    assert result.seal.source_tree == SOURCE_GIT_IDENTITY.source_tree
    assert tuple(b.native_ticket_count for b in result.seal.buckets) == NATIVE_TICKET_COUNT_BUCKETS
    assert seal_store.get_seal(TARGET) == result.seal


def test_clean_exact_commit_worktree_identity_flows_into_created_seal(tmp_path: Path) -> None:
    repository = tmp_path / "source-repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "LottoLab Test")
    _git(repository, "config", "user.email", "lottolab@example.test")
    source_file = repository / "runtime.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    _git(repository, "add", "runtime.py")
    _git(repository, "commit", "-q", "-m", "synthetic source")
    expected_head = _git(repository, "rev-parse", "--verify", "HEAD^{commit}")
    expected_tree = _git(repository, "rev-parse", "--verify", "HEAD^{tree}")

    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(_record(_announcement())),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
        source_git_identity_factory=GitSourceIdentityResolver(source_file),
    )

    result = use_case.execute(LOTTERY_TYPE)

    assert result.status is SealOutcomeStatus.CREATED
    assert result.seal is not None
    assert result.seal.source_head == expected_head
    assert result.seal.source_tree == expected_tree


def test_outcome_already_available_before_generation_fails_closed_without_writing() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.PRESENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT),
    )

    with pytest.raises(OutcomeAlreadyAvailableError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_outcome_becomes_available_during_generation_fails_closed_without_writing() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    # ABSENT at registration (two probe calls inside register_earliest's
    # underlying service), PRESENT at the fresh final gate re-probe.
    presence_probe = _PresenceProbe(
        OutcomePresenceAtPrediction.ABSENT, OutcomePresenceAtPrediction.PRESENT
    )
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=5)),
    )

    with pytest.raises(OutcomeAlreadyAvailableError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_schedule_elapsing_during_generation_fails_closed_without_writing() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        # registration clock reads twice (before/after the probe), both still
        # before scheduled_at; the fresh-final-gate clock read lands *after*
        # scheduled_at, simulating the window elapsing during generation.
        clock=_clock(REGISTERED_AT, REGISTERED_AT, SCHEDULED_AT + timedelta(minutes=1)),
    )

    with pytest.raises(InvalidScheduleTimeError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_causal_history_drift_during_generation_fails_closed_without_writing() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    # register_earliest resolves history once (used for the registration);
    # the fresh final gate resolves it again and must see the same value.
    # A different second answer simulates new draws landing mid-generation.
    history_authority = _HistoryAuthority(_history(), _history(sha_suffix="drifted"))
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
    )

    with pytest.raises(SealCausalHistoryDriftError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_source_git_identity_drift_during_generation_fails_closed_without_writing() -> None:
    first = SOURCE_GIT_IDENTITY
    second = SourceGitIdentity(source_head="3" * 40, source_tree="4" * 40)
    answers = iter((first, second))
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(_record(_announcement())),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
        source_git_identity_factory=lambda: next(answers),
    )

    with pytest.raises(SealSourceGitIdentityError, match="changed"):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_unavailable_source_git_identity_fails_closed_without_writing() -> None:
    def unavailable() -> SourceGitIdentity:
        raise SealSourceGitIdentityError("identity unavailable")

    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(_record(_announcement())),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT),
        source_git_identity_factory=unavailable,
    )

    with pytest.raises(SealSourceGitIdentityError, match="unavailable"):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def test_idempotent_reseal_returns_the_existing_seal_without_regenerating() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    authority_store = _AuthorityStore()
    history_authority = _HistoryAuthority(_history())
    presence_probe = _PresenceProbe(OutcomePresenceAtPrediction.ABSENT)

    first = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=authority_store,
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
    )
    first_result = first.execute(LOTTERY_TYPE)
    assert first_result.status is SealOutcomeStatus.CREATED

    second = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=authority_store,
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT + timedelta(minutes=2)),
    )
    second_result = second.execute(LOTTERY_TYPE)

    assert second_result.status is SealOutcomeStatus.IDEMPOTENT_EXISTING
    assert second_result.seal == first_result.seal
    assert seal_store.create_calls == 1


def test_competing_reseal_is_rejected_without_overwriting_the_existing_seal() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    authority_store = _AuthorityStore()
    history_authority = _HistoryAuthority(_history())
    presence_probe = _PresenceProbe(OutcomePresenceAtPrediction.ABSENT)

    first = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=authority_store,
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
    )
    first_result = first.execute(LOTTERY_TYPE)
    assert first_result.status is SealOutcomeStatus.CREATED

    def different_evidence():
        return NextDrawRecommendationEvidenceArtifact.build(
            lottery_type="BIG_LOTTO",
            source_draw_db_sha256=_sha256("a-different-draw-db"),
            source_draw_count=2,
            last_causal_draw_id="115000089",
            replay_depth=2,
            hit_tier_id="M3",
            records=(),
        )

    second = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=authority_store,
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT + timedelta(minutes=2)),
        evidence_factory=different_evidence,
    )
    second_result = second.execute(LOTTERY_TYPE)

    assert second_result.status is SealOutcomeStatus.FAIL_CLOSED_CONFLICT
    assert second_result.seal is None
    # The original, valid seal must survive untouched.
    assert seal_store.get_seal(TARGET) == first_result.seal
    assert seal_store.create_calls == 1


def test_concurrent_create_seal_race_is_resolved_by_the_store_not_overwritten() -> None:
    """Two racing attempts both pass the early "no existing seal" check; the
    store's create-once atomicity, not the use case, must be what prevents
    a second writer from overwriting the winner."""

    record = _record(_announcement())
    seal_store = _SealStore()
    authority_store = _AuthorityStore()
    history_authority = _HistoryAuthority(_history())
    presence_probe = _PresenceProbe(OutcomePresenceAtPrediction.ABSENT)

    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=history_authority,
        authority_store=authority_store,
        presence_probe=presence_probe,
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT, REGISTERED_AT, REGISTERED_AT + timedelta(minutes=1)),
    )
    winner = use_case.execute(LOTTERY_TYPE)
    assert winner.status is SealOutcomeStatus.CREATED

    # Simulate a second writer that already resolved its seal (identical
    # frozen inputs) before the first writer's create_seal committed, by
    # calling the store directly with the same content.
    outcome = seal_store.create_seal(winner.seal)
    assert outcome is CreateOnceOutcome.CONFLICT
    assert seal_store.get_seal(TARGET) == winner.seal


def test_evidence_unavailable_raises_without_touching_the_seal_store() -> None:
    record = _record(_announcement())
    seal_store = _SealStore()
    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT),
        evidence_factory=lambda: None,
    )

    with pytest.raises(SealEvidenceUnavailableError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0


def test_evidence_for_a_different_lottery_type_is_rejected_without_writing() -> None:
    """The target authority is multi-lottery; a misconfigured evidence factory
    covering a different lottery type must never be silently frozen into a
    seal for this one."""

    record = _record(_announcement())
    seal_store = _SealStore()

    def wrong_lottery_evidence():
        return NextDrawRecommendationEvidenceArtifact.build(
            lottery_type="DAILY_539",
            source_draw_db_sha256=_sha256("draws"),
            source_draw_count=2,
            last_causal_draw_id="115000089",
            replay_depth=2,
            hit_tier_id="M3",
            records=(),
        )

    use_case = _build_use_case(
        reader=_Reader(record),
        history_authority=_HistoryAuthority(_history()),
        authority_store=_AuthorityStore(),
        presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_store=seal_store,
        clock=_clock(REGISTERED_AT),
        evidence_factory=wrong_lottery_evidence,
    )

    with pytest.raises(SealEvidenceLotteryTypeMismatchError):
        use_case.execute(LOTTERY_TYPE)

    assert seal_store.create_calls == 0
    assert seal_store.get_seal(TARGET) is None


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
