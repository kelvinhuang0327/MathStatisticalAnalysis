"""Hermetic regression suite proving B649 pre-outcome next-draw forecast readiness.

Invariants verified:
Given the latest officially completed draw N:
* Forecast generation for N+1 is possible before the N+1 outcome exists.
* Forecast persistence, query, and readiness do NOT require the N+1 outcome.
* Outcome scoring and reconciliation remain pending/not-yet-scorable until N+1 arrives.
* Requirements A through H are durable and hermetic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypedDict, cast

import pytest
from tests.unit.test_b649_next_undrawn_forecast import (
    Generator,
    descriptor,
    make_request,
)

from lottolab.application.b649_next_undrawn_forecast import (
    ForecastContractError,
    ForecastLiveState,
    ForecastRequest,
    ForecastTimingError,
    NextUndrawnForecastService,
    prepare_forecast,
)
from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
)
from lottolab.application.pre_outcome_target import (
    PreOutcomeTargetRegistrationRequest,
    PreOutcomeTargetRegistrationService,
    RegistrationSyncResult,
    RegistrationSyncStatus,
)
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
    PreOutcomeTargetOperationalService,
)
from lottolab.application.prospective_observer import (
    InMemoryProspectiveObservationStore,
    ScorePhaseRequest,
    ScoreSyncStatus,
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.domain.b649_next_undrawn_forecast import (
    OUTPUT_BUCKETS,
    validate_history,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
)
from lottolab.infrastructure import b649_live_forecast as live
from lottolab.infrastructure.b649_next_undrawn_forecast import (
    FileSystemForecastBundleStore,
    FixtureRegistration,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence import research_schema
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
    SQLiteManualFutureDrawIdentitySupplementRepository,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.persistence.research_repository import SQLiteResearchRepository
from lottolab.infrastructure.persistence.research_schema import ResearchDataPaths
from lottolab.infrastructure.pre_outcome_target_operational import (
    OFFICIAL_DRAW_PROVIDER_ID,
    OFFICIAL_DRAW_PROVIDER_VERSION,
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    SQLiteOfficialOutcomePresenceProbe,
    SQLitePreOutcomeCausalHistoryAuthority,
    parse_owner_certified_future_draw_identity_input,
    select_owner_certified_future_draw_identity,
)

DRAW_N_NUMBER = "115000085"
DRAW_N_DATE = date(2099, 1, 6)
TARGET_N1_NUMBER = "115000086"
TARGET_N1_DATE = date(2099, 1, 7)
TARGET_N1_SCHEDULED_AT = datetime(2099, 1, 7, 12, 30, tzinfo=UTC)

# Predraw decision time: strictly before N+1 draw deadline
PREDRAW_TIME = datetime(2099, 1, 6, 20, 0, 0, tzinfo=UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class HermeticState(TypedDict):
    paths: LocalDataPaths
    research_paths: ResearchDataPaths
    research_repo: SQLiteResearchRepository
    reader: SQLiteFutureDrawIdentityReader
    history_authority: SQLitePreOutcomeCausalHistoryAuthority
    probe: SQLiteOfficialOutcomePresenceProbe
    target: ObservationTarget
    forecast_request: ForecastRequest
    bundle_store: FileSystemForecastBundleStore


def _insert_completed_draw(
    paths: LocalDataPaths,
    *,
    run_id: str,
    draw_number: str,
    draw_date: date,
    main_numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    special_number: int = 7,
) -> None:
    del run_id
    m_str = "|".join(str(n) for n in main_numbers)
    csv_content = (
        "LOTTERY_TYPE,DRAW_NUMBER,DRAW_DATE,MAIN_NUMBERS,SPECIAL_NUMBERS,SOURCE_NAME\n"
        f"BIG_LOTTO,{draw_number},{draw_date.isoformat()},{m_str},{special_number},synthetic\n"
    )
    parsed = parse_draw_csv(csv_content, filename=f"completed-{draw_number}.csv")
    assert parsed.is_valid, parsed.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(parsed)
    assert result.status is IngestionRunStatus.SUCCESS
    assert result.inserted_count == 1


def _insert_official_presence_audit(
    paths: LocalDataPaths,
    *,
    run_id: str,
    requested_start: date,
    requested_end: date,
    completed_at: datetime,
    fetched_count: int = 0,
) -> None:
    timestamp = completed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                LotteryType.BIG_LOTTO.value,
                "presence-audit.json",
                _sha256(run_id),
                "official-parser-v1",
                fetched_count,
                fetched_count,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, provider, provider_version,
                requested_start, requested_end, resolved_start, resolved_end,
                fetched_count
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                OFFICIAL_DRAW_PROVIDER_ID,
                OFFICIAL_DRAW_PROVIDER_VERSION,
                requested_start.isoformat(),
                requested_end.isoformat(),
                fetched_count,
            ),
        )
        connection.commit()


def _commit_schedule(
    paths: LocalDataPaths,
    *,
    draw_number: str,
    draw_date: date,
    scheduled_at: datetime,
) -> ScheduledDrawIdentityRecord:
    doc = {
        "announcements": [
            {
                "schedule_timezone": "Asia/Taipei",
                "scheduled_at": scheduled_at.isoformat().replace("+00:00", "Z"),
                "source": {
                    "observed_at": "2099-01-01T00:00:00Z",
                    "source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    "source_locator": f"https://www.taiwanlottery.com/schedule/{draw_number}",
                    "source_payload_sha256": _sha256(f"official-schedule:{draw_number}"),
                    "source_version": "taiwan-lottery-official-schedule-v1",
                },
                "target": {
                    "draw_date": draw_date.isoformat(),
                    "draw_number": draw_number,
                    "lottery_type": "BIG_LOTTO",
                },
            }
        ],
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    }
    encoded = json.dumps(doc, separators=(",", ":"), sort_keys=True).encode("utf-8")
    parsed = parse_owner_certified_future_draw_identity_input(
        encoded, source_filename=f"schedule-{draw_number}.json"
    )
    selected = select_owner_certified_future_draw_identity(
        parsed, lottery_type=LotteryType.BIG_LOTTO, draw_number=draw_number
    )
    repo = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    repo.apply_owner_certified_supplement(parsed, selected, parsed.input_sha256)
    reader = SQLiteFutureDrawIdentityReader(paths)
    record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, draw_number)
    assert record is not None
    return record


@pytest.fixture
def hermetic_state(tmp_path: Path) -> HermeticState:
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / "lottolab-data")})
    initialize_schema(paths)

    research_dir = tmp_path / "research"
    research_paths = ResearchDataPaths(
        research_dir, research_dir / research_schema.RESEARCH_DATABASE_FILENAME
    )
    research_schema.initialize_schema(research_paths)
    research_repo = SQLiteResearchRepository(research_paths)

    # Insert historical completed draws through N (115000080 .. 115000085)
    for i in range(6):
        d_num = str(115000080 + i)
        d_date = date(2099, 1, 1) + timedelta(days=i)
        _commit_schedule(
            paths,
            draw_number=d_num,
            draw_date=d_date,
            scheduled_at=datetime(2099, 1, 1, 12, 30, tzinfo=UTC) + timedelta(days=i),
        )
        _insert_completed_draw(paths, run_id=f"hist-{d_num}", draw_number=d_num, draw_date=d_date)

    # Insert covering official audit covering target N+1
    _insert_official_presence_audit(
        paths,
        run_id="audit-covering-n1",
        requested_start=date(2099, 1, 1),
        requested_end=TARGET_N1_DATE,
        completed_at=PREDRAW_TIME,
        fetched_count=6,
    )

    # Insert schedule for next undrawn draw N+1 (115000086)
    _commit_schedule(
        paths,
        draw_number=TARGET_N1_NUMBER,
        draw_date=TARGET_N1_DATE,
        scheduled_at=TARGET_N1_SCHEDULED_AT,
    )

    # Ensure N+1 outcome is ABSENT
    with open_database(paths, read_only=True) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND draw_number=?",
            (LotteryType.BIG_LOTTO.value, TARGET_N1_NUMBER),
        ).fetchone()[0]
        assert count == 0

    reader = SQLiteFutureDrawIdentityReader(paths)
    history_authority = SQLitePreOutcomeCausalHistoryAuthority(paths)
    probe = SQLiteOfficialOutcomePresenceProbe(paths)
    target = ObservationTarget(LotteryType.BIG_LOTTO, TARGET_N1_NUMBER, TARGET_N1_DATE)

    req = make_request(
        descriptors=(descriptor("fixture_a", 1), descriptor("fixture_b", 2)),
    )
    # Rebind request to exact hermetic target
    schedule_rec = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, TARGET_N1_NUMBER)
    assert schedule_rec is not None
    sched_hash = schedule_rec.immutable_schedule_sha256 or schedule_rec.normalized_announcement_hash
    req = replace(
        req,
        target=target,
        schedule_authority_sha256=sched_hash,
    )

    bundle_store = FileSystemForecastBundleStore(tmp_path / "bundle-store")

    return {
        "paths": paths,
        "research_paths": research_paths,
        "research_repo": research_repo,
        "reader": reader,
        "history_authority": history_authority,
        "probe": probe,
        "target": target,
        "forecast_request": req,
        "bundle_store": bundle_store,
    }


def test_requirement_a_target_resolves_n1_as_next_undrawn_target(
    hermetic_state: HermeticState,
) -> None:
    """A. TARGET: The system resolves N+1 as the next undrawn forecast target."""
    reader = hermetic_state["reader"]
    record = reader.find_earliest_unpopulated_future(LotteryType.BIG_LOTTO, as_of=PREDRAW_TIME)
    assert record is not None
    assert record.announcement.target.draw_number == TARGET_N1_NUMBER
    assert record.announcement.target.draw_date == TARGET_N1_DATE
    assert record.outcome_state is ScheduledDrawOutcomeState.NOT_POPULATED

    # Verify operational registration resolves N+1
    reg_authority = hermetic_state["history_authority"].resolve(record.announcement.target)
    reg_probe = hermetic_state["probe"].probe(record.announcement.target, as_of=PREDRAW_TIME)
    reg_record = PreOutcomeTargetRegistration.create(
        announcement=record.announcement,
        absence_attestation=reg_probe,
        causal_history=reg_authority,
        registered_at=PREDRAW_TIME,
    )

    class _MockTargetRegistrationService:
        def register(
            self, request: PreOutcomeTargetRegistrationRequest
        ) -> RegistrationSyncResult:
            del request
            return RegistrationSyncResult(
                RegistrationSyncStatus.CREATED,
                reg_record,
            )

    reg_service = PreOutcomeTargetOperationalService(
        future_draw_identity_reader=reader,
        causal_history_authority=hermetic_state["history_authority"],
        registration_service=cast(
            PreOutcomeTargetRegistrationService,
            _MockTargetRegistrationService(),
        ),
        clock=lambda: PREDRAW_TIME,
    )
    reg_result = reg_service.register_earliest(LotteryType.BIG_LOTTO)
    assert reg_result.announcement is not None
    assert reg_result.announcement.target.draw_number == TARGET_N1_NUMBER
    assert reg_result.causal_history is not None
    assert reg_result.causal_history.last_draw_number == DRAW_N_NUMBER


def test_requirement_b_no_outcome_dependency_and_fail_closed_if_outcome_present(
    hermetic_state: HermeticState,
) -> None:
    """B. NO OUTCOME DEPENDENCY: No generation query requires N+1, and premature outcome fails."""
    paths = hermetic_state["paths"]
    probe = hermetic_state["probe"]
    target = hermetic_state["target"]

    # 1. Outcome row for N+1 is absent in database
    with open_database(paths, read_only=True) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND draw_number=?",
                (LotteryType.BIG_LOTTO.value, TARGET_N1_NUMBER),
            ).fetchone()[0]
            == 0
        )

    # 2. Probe attests ABSENT
    attestation = probe.probe(target, as_of=PREDRAW_TIME)
    assert attestation.presence is OutcomePresenceAtPrediction.ABSENT

    # 3. Forecast generation path succeeds without outcome row
    generator = Generator()
    prepared = prepare_forecast(hermetic_state["forecast_request"], generator)
    assert prepared.bundle.identity.target.draw_number == TARGET_N1_NUMBER

    # 4. Negative control: If N+1 outcome were prematurely present, generation is blocked
    service_request = hermetic_state["forecast_request"]
    source = TargetSourceProvenance(
        "fixture",
        "fixture-v1",
        "fixture://schedule",
        service_request.schedule_authority_sha256,
        PREDRAW_TIME,
    )
    announcement = TargetAnnouncement(
        target, "Asia/Taipei", TARGET_N1_SCHEDULED_AT, source
    )
    reg = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            target, OutcomePresenceAtPrediction.ABSENT, PREDRAW_TIME, source
        ),
        causal_history=service_request.history_authority,
        registered_at=PREDRAW_TIME,
    )
    op_result = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        service_request.history_authority,
        reg,
        service_request.schedule_authority_sha256,
    )

    # If outcome is reported present, NextUndrawnForecastService MUST reject
    service_blocked = NextUndrawnForecastService(
        FixtureRegistration(op_result),
        lambda _target: ForecastLiveState(
            TARGET_N1_SCHEDULED_AT, service_request.schedule_authority_sha256, True
        ),
        lambda: PREDRAW_TIME,
        Generator(),
        hermetic_state["bundle_store"],
    )
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT"):
        service_blocked.run(service_request)


def test_requirement_c_cutoff_bounds_all_inputs_through_n_without_leakage(
    hermetic_state: HermeticState,
) -> None:
    """C. CUTOFF / NO LEAKAGE: Inputs are strictly bounded through N, target is excluded."""
    paths = hermetic_state["paths"]
    target = hermetic_state["target"]

    # In B649LiveForecastService._history query:
    service = live.B649LiveForecastService(
        hermetic_state["research_repo"], paths, Path(__file__).resolve().parents[2]
    )
    read_history = service._history  # pyright: ignore[reportPrivateUsage]
    history_rows = read_history(target)
    assert len(history_rows) == 6
    assert history_rows[-1].draw_number == DRAW_N_NUMBER
    assert history_rows[-1].draw_date == DRAW_N_DATE
    assert all(int(d.draw_number) < int(TARGET_N1_NUMBER) for d in history_rows)
    assert all(d.draw_date < TARGET_N1_DATE for d in history_rows)

    # Causal history authority bounds strictly through N
    causal_ref = hermetic_state["history_authority"].resolve(target)
    assert causal_ref.last_draw_number == DRAW_N_NUMBER
    assert causal_ref.last_draw_date == DRAW_N_DATE
    assert causal_ref.draw_count == 6

    # Validation rejects future row leakage
    leaked_row = Draw(
        TARGET_N1_NUMBER, TARGET_N1_DATE, (1, 2, 3, 4, 5, 6), 7
    )
    leaked_history = (*history_rows, leaked_row)
    with pytest.raises(ForecastContractError, match="FUTURE_OR_NONCHRONOLOGICAL"):
        validate_history(leaked_history, target, causal_ref)


def test_requirement_d_canonical_forecast_generation_succeeds_before_draw(
    hermetic_state: HermeticState,
) -> None:
    """D. GENERATION: Canonical forecast path succeeds before N+1 is drawn."""
    req = hermetic_state["forecast_request"]
    generator = Generator()
    prepared = prepare_forecast(req, generator)

    payload = prepared.bundle.payload()
    identity_dict = cast(dict[str, object], payload["identity"])
    history_dict = cast(dict[str, object], payload["history"])
    assert identity_dict["target_draw_number"] == TARGET_N1_NUMBER
    assert history_dict["last_draw_number"] == DRAW_N_NUMBER

    raw_buckets = cast(list[dict[str, object]], payload["buckets"])
    assert [b["native_k"] for b in raw_buckets] == list(OUTPUT_BUCKETS)

    # K=1, 2 are available with valid legal tickets
    k1 = next(b for b in raw_buckets if b["native_k"] == 1)
    assert k1["status"] == "AVAILABLE"
    assert k1["tickets"] == [[1, 2, 7, 8, 9, 10]]

    k2 = next(b for b in raw_buckets if b["native_k"] == 2)
    assert k2["status"] == "AVAILABLE"
    assert len(cast(list[object], k2["tickets"])) == 2

    # K=20 is truthfully unavailable
    k20 = next(b for b in raw_buckets if b["native_k"] == 20)
    assert k20["status"] == "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"


def test_requirement_e_persistence_and_read_before_outcome_exists(
    hermetic_state: HermeticState,
) -> None:
    """E. PERSISTENCE / READ: Forecast can be persisted and read before outcome exists."""
    req = hermetic_state["forecast_request"]
    store = hermetic_state["bundle_store"]

    source = TargetSourceProvenance(
        "fixture", "fixture-v1", "fixture://schedule", req.schedule_authority_sha256, PREDRAW_TIME
    )
    announcement = TargetAnnouncement(
        hermetic_state["target"], "Asia/Taipei", TARGET_N1_SCHEDULED_AT, source
    )
    reg = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            hermetic_state["target"],
            OutcomePresenceAtPrediction.ABSENT,
            PREDRAW_TIME,
            source,
        ),
        causal_history=req.history_authority,
        registered_at=PREDRAW_TIME,
    )
    authority = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        req.history_authority,
        reg,
        req.schedule_authority_sha256,
    )
    service = NextUndrawnForecastService(
        FixtureRegistration(authority),
        lambda _target: ForecastLiveState(
            TARGET_N1_SCHEDULED_AT, req.schedule_authority_sha256, False
        ),
        lambda: PREDRAW_TIME,
        Generator(),
        store,
    )
    stored = service.run(req)
    assert stored is not None

    # Verify bundle is readable through canonical interface before outcome exists
    loaded = store.load(req.identity)
    assert loaded is not None
    assert loaded.bundle == stored.bundle
    assert loaded.prediction == stored.prediction

    # Archive on disk exists and contains bundle.json and prediction.json
    path = store.path_for(req.identity)
    assert path.is_file()
    assert path.stat().st_size > 0


def test_requirement_f_outcome_boundary_returns_pending_until_outcome_arrives(
    hermetic_state: HermeticState,
) -> None:
    """F. OUTCOME BOUNDARY: Scoring returns OUTCOME_UNAVAILABLE until N+1 arrives."""
    req = hermetic_state["forecast_request"]
    store = hermetic_state["bundle_store"]

    source = TargetSourceProvenance(
        "fixture", "fixture-v1", "fixture://schedule", req.schedule_authority_sha256, PREDRAW_TIME
    )
    announcement = TargetAnnouncement(
        hermetic_state["target"], "Asia/Taipei", TARGET_N1_SCHEDULED_AT, source
    )
    reg = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            hermetic_state["target"],
            OutcomePresenceAtPrediction.ABSENT,
            PREDRAW_TIME,
            source,
        ),
        causal_history=req.history_authority,
        registered_at=PREDRAW_TIME,
    )
    authority = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        req.history_authority,
        reg,
        req.schedule_authority_sha256,
    )
    service = NextUndrawnForecastService(
        FixtureRegistration(authority),
        lambda _target: ForecastLiveState(
            TARGET_N1_SCHEDULED_AT, req.schedule_authority_sha256, False
        ),
        lambda: PREDRAW_TIME,
        Generator(),
        store,
    )
    stored = service.run(req)

    # Register prediction in generic store
    generic_store = InMemoryProspectiveObservationStore()
    generic_store.create_prediction(stored.prediction)

    scoring_service = ScoringPhaseService(
        store=generic_store,
        game_contracts=repository_game_contracts(),
        clock=lambda: PREDRAW_TIME,
    )

    # 1. Attempt scoring BEFORE N+1 outcome arrives: returns OUTCOME_UNAVAILABLE
    score_request_pending = ScorePhaseRequest(
        identity=stored.prediction.identity,
        producer_fingerprint=stored.prediction.producer_fingerprint,
        outcome=None,
    )
    result_pending = scoring_service.sync(score_request_pending)
    assert result_pending.status is ScoreSyncStatus.OUTCOME_UNAVAILABLE
    assert result_pending.score is None

    # Stored forecast remains completely valid and un-invalidated
    assert generic_store.get_prediction(stored.prediction.identity) == stored.prediction

    # 2. Now simulate arrival of N+1 outcome AFTER draw occurs:
    draw_time = TARGET_N1_SCHEDULED_AT + timedelta(minutes=30)
    official_outcome = OfficialOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=TARGET_N1_NUMBER,
        draw_date=TARGET_N1_DATE,
        main_numbers=(1, 2, 7, 8, 9, 10),
        special_number=20,
        source_id="taiwan_lottery_official",
        source_sha256=_sha256("official_result_n1"),
    )
    score_request_resolved = ScorePhaseRequest(
        identity=stored.prediction.identity,
        producer_fingerprint=stored.prediction.producer_fingerprint,
        outcome=official_outcome,
    )
    scoring_service_postdraw = ScoringPhaseService(
        store=generic_store,
        game_contracts=repository_game_contracts(),
        clock=lambda: draw_time,
    )
    result_scored = scoring_service_postdraw.sync(score_request_resolved)
    assert result_scored.status is ScoreSyncStatus.CREATED
    assert result_scored.score is not None
    assert len(result_scored.score.entries) == 6


def test_requirement_g_idempotency_prevents_duplicate_issuance(
    hermetic_state: HermeticState,
) -> None:
    """G. IDEMPOTENCY: Repeated generation does not create duplicate authoritative state."""
    req = hermetic_state["forecast_request"]
    store = hermetic_state["bundle_store"]

    source = TargetSourceProvenance(
        "fixture", "fixture-v1", "fixture://schedule", req.schedule_authority_sha256, PREDRAW_TIME
    )
    announcement = TargetAnnouncement(
        hermetic_state["target"], "Asia/Taipei", TARGET_N1_SCHEDULED_AT, source
    )
    reg = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            hermetic_state["target"],
            OutcomePresenceAtPrediction.ABSENT,
            PREDRAW_TIME,
            source,
        ),
        causal_history=req.history_authority,
        registered_at=PREDRAW_TIME,
    )
    authority = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        req.history_authority,
        reg,
        req.schedule_authority_sha256,
    )
    service = NextUndrawnForecastService(
        FixtureRegistration(authority),
        lambda _target: ForecastLiveState(
            TARGET_N1_SCHEDULED_AT, req.schedule_authority_sha256, False
        ),
        lambda: PREDRAW_TIME,
        Generator(),
        store,
    )

    # First run: created
    first = service.run(req)
    path = store.path_for(req.identity)
    before_mtime = path.stat().st_mtime_ns

    # Second run: identical verified return
    second = service.run(req)
    assert second == first
    assert path.stat().st_mtime_ns == before_mtime
    assert list(store.root.iterdir()) == [path]


def test_requirement_h_rollover_semantics_and_stale_schedule_handling(
    hermetic_state: HermeticState,
) -> None:
    """H. ROLLOVER SEMANTICS: Stale schedules do not suppress genuinely due/next-undrawn target."""
    paths = hermetic_state["paths"]
    reader = hermetic_state["reader"]

    # 1. Completed draws N-1 and N do not suppress N+1
    record = reader.find_earliest_unpopulated_future(LotteryType.BIG_LOTTO, as_of=PREDRAW_TIME)
    assert record is not None
    assert record.announcement.target.draw_number == TARGET_N1_NUMBER

    # 2. Add an additional future schedule N+2 (115000087)
    _commit_schedule(
        paths,
        draw_number="115000087",
        draw_date=date(2099, 1, 10),
        scheduled_at=datetime(2099, 1, 10, 12, 30, tzinfo=UTC),
    )
    # The earliest unpopulated target is still N+1 (115000086)
    record_still_n1 = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO, as_of=PREDRAW_TIME
    )
    assert record_still_n1 is not None
    assert record_still_n1.announcement.target.draw_number == TARGET_N1_NUMBER

    # 3. Add an authority evidence record marking a cancelled schedule
    with open_database(paths, read_only=False) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO draw_schedule_authority_evidence (
                lottery_type, official_game_code, draw_number, event_kind,
                disposition, detail_code, source_id, source_version,
                source_locator, source_payload_sha256, source_observed_at,
                run_id, created_at
            ) VALUES (
                ?, 1, ?, 'CANCELLATION',
                'REJECTED', 'CANCELLED', 'src', 'v1',
                'https://fixture/cancelled', ?, '2099-01-02T00:00:00Z',
                'audit-covering-n1', '2099-01-02T00:00:00Z'
            )
            """,
            (LotteryType.BIG_LOTTO.value, "115000084", _sha256("cancelled-084")),
        )
        conn.commit()

    # Cancelled schedule does not suppress N+1
    record_after_evidence = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO, as_of=PREDRAW_TIME
    )
    assert record_after_evidence is not None
    assert record_after_evidence.announcement.target.draw_number == TARGET_N1_NUMBER


def test_preoutcome_full_hermetic_lifecycle_contract(
    hermetic_state: HermeticState,
) -> None:
    """Complete lifecycle test: latest N -> target N+1 -> predraw forecast -> score deferred."""
    # 1. State check
    target = hermetic_state["target"]
    reader = hermetic_state["reader"]
    probe = hermetic_state["probe"]

    # Target is resolved
    sched_record = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO, as_of=PREDRAW_TIME
    )
    assert sched_record is not None
    assert sched_record.announcement.target.draw_number == TARGET_N1_NUMBER

    # Outcome is absent
    attestation = probe.probe(target, as_of=PREDRAW_TIME)
    assert attestation.presence is OutcomePresenceAtPrediction.ABSENT

    # 2. Generate and persist forecast
    req = hermetic_state["forecast_request"]
    store = hermetic_state["bundle_store"]
    source = TargetSourceProvenance(
        "fixture", "fixture-v1", "fixture://schedule", req.schedule_authority_sha256, PREDRAW_TIME
    )
    announcement = TargetAnnouncement(
        target, "Asia/Taipei", TARGET_N1_SCHEDULED_AT, source
    )
    reg = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=attestation,
        causal_history=req.history_authority,
        registered_at=PREDRAW_TIME,
    )
    authority = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        req.history_authority,
        reg,
        req.schedule_authority_sha256,
    )
    service = NextUndrawnForecastService(
        FixtureRegistration(authority),
        lambda _target: ForecastLiveState(
            TARGET_N1_SCHEDULED_AT, req.schedule_authority_sha256, False
        ),
        lambda: PREDRAW_TIME,
        Generator(),
        store,
    )
    stored = service.run(req)
    assert stored.bundle.identity.target.draw_number == TARGET_N1_NUMBER
    assert stored.prediction.causal_history.last_draw_number == DRAW_N_NUMBER

    # 3. Read back from store
    loaded = store.load(req.identity)
    assert loaded == stored

    # 4. Scoring boundary: score deferred until outcome
    obs_store = InMemoryProspectiveObservationStore()
    obs_store.create_prediction(stored.prediction)
    scoring = ScoringPhaseService(
        store=obs_store,
        game_contracts=repository_game_contracts(),
        clock=lambda: PREDRAW_TIME,
    )
    score_res = scoring.sync(
        ScorePhaseRequest(
            identity=stored.prediction.identity,
            producer_fingerprint=stored.prediction.producer_fingerprint,
            outcome=None,
        )
    )
    assert score_res.status is ScoreSyncStatus.OUTCOME_UNAVAILABLE

    # 5. Idempotent re-run
    second_run = service.run(req)
    assert second_run == stored
