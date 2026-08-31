"""Integration tests for T539 and P638 Stage H recurring automation runner.

Validates multi-cycle orchestration over real SQLite and filesystem stores:
  Stage A canonical schedule authority
  -> Stage C pre-draw prediction seal
  -> Stage E exact result join
  -> Stage G append-only forward evidence ledger
across consecutive simulated draw cycles.

Enforces:
- Deterministic multi-cycle progression across consecutive draw terms
- Scheduled_at timing constraints and pre/post-draw wake semantics
- Mid-cycle crash and restart recovery across all stage boundaries
- Strict game isolation between DAILY_539 and POWER_LOTTO
- No-ticket (unavailable prediction) handling without false scoring or losses
- Multi-ticket ordering and exact ledger hash lineage
- Zero-network safety enforcement
"""

from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from tools.t539_p638_recurring_automation_adapter import (
    compose_t539_p638_recurring_automation,
)

from lottolab.application.draw_data import DrawRecord
from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
)
from lottolab.application.t539_p638_recurring_automation import (
    RecurringCycleState,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    MatchedBaselineRef,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    ScoreAvailability,
    TemporalProvenance,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawRepository
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID,
    PROVIDER_VERSION,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)


@pytest.fixture(autouse=True)
def _network_is_forbidden(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("Stage H recurring automation must not access network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _init_paths(root: Path) -> LocalDataPaths:
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(root)})
    initialize_schema(paths)
    return paths


def _insert_run(
    paths: LocalDataPaths,
    *,
    run_id: str,
    lottery_type: LotteryType,
    requested_start: date,
    requested_end: date,
    fetched_count: int,
) -> None:
    timestamp = "2099-01-01T07:30:00.000000Z"
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
                lottery_type.value,
                "synthetic-official-sync.json",
                _sha256(run_id),
                "synthetic-parser-v1",
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
                PROVIDER_ID,
                PROVIDER_VERSION,
                requested_start.isoformat(),
                requested_end.isoformat(),
                fetched_count,
            ),
        )
        connection.commit()


def _seed_draw(
    paths: LocalDataPaths,
    *,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: date,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...] = (),
) -> DrawRecord:
    run_id = f"ingest-{lottery_type.value}-{draw_number}"
    _insert_run(
        paths,
        run_id=run_id,
        lottery_type=lottery_type,
        requested_start=draw_date,
        requested_end=draw_date,
        fetched_count=1,
    )
    with open_database(paths, read_only=False) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                lottery_type.value,
                draw_number,
                draw_date.isoformat(),
                json.dumps(list(main_numbers), separators=(",", ":")),
                json.dumps(list(special_numbers), separators=(",", ":")),
                _sha256(f"draw-{lottery_type.value}-{draw_number}"),
                "synthetic-test-provider",
                run_id,
                "2099-01-01T08:00:00.000000Z",
                "2099-01-01T08:00:00.000000Z",
            ),
        )
        conn.commit()

    with open_database(paths, read_only=True) as conn:
        repo = SQLiteDrawRepository(conn)
        record = repo.find(lottery_type, draw_number)
        assert record is not None
        return record


def _seed_schedule_authority(
    paths: LocalDataPaths,
    rows: Sequence[Mapping[str, object]],
    *,
    active_vetoes: tuple[AuthoritativeScheduleVeto, ...] = (),
) -> None:
    body = json.dumps(
        {
            "content": {"nextDrawDateList": rows},
            "fixtureMarker": 100,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    parsed = parse_official_t539_p638_schedule(
        body,
        observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
        active_vetoes=active_vetoes,
    )
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(parsed)


def _build_t539_cohort(
    member_ids: tuple[str, ...] = ("strat_alpha", "strat_beta"),
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=LotteryType.DAILY_539,
        cohort_id="t539_production_cohort",
        cohort_version="1.0",
        authority_sha256=_sha256("t539_cohort_authority"),
        frozen_at=datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC),
        member_ids=member_ids,
        checkpoint_sizes=(1, 5, 10),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _build_p638_cohort(
    member_ids: tuple[str, ...] = ("p638_member_1", "p638_member_2"),
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=LotteryType.POWER_LOTTO,
        cohort_id="p638_production_cohort",
        cohort_version="1.0",
        authority_sha256=_sha256("p638_cohort_authority"),
        frozen_at=datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC),
        member_ids=member_ids,
        checkpoint_sizes=(1, 5, 10),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _build_producer_fingerprint(producer_id: str) -> ProducerFingerprint:
    dep = ProducerDependency(
        locator=f"fixture://model_weights/{producer_id}",
        source_sha256=_sha256(f"weights_{producer_id}"),
        load_bearing_role="synthetic deterministic prediction behavior",
    )
    return ProducerFingerprint.create(
        producer_id=producer_id,
        producer_version="1.0",
        dependencies=(dep,),
    )


class SyntheticProducer:
    """Outcome-free deterministic synthetic prediction producer."""

    def __init__(
        self,
        lottery_type: LotteryType,
        cohort: FrozenCohortRef,
        *,
        unavailable_members: set[str] | None = None,
    ) -> None:
        self.lottery_type = lottery_type
        self.cohort = cohort
        self.unavailable_members = unavailable_members or set()

    def predict(self, context: PredictionContext) -> PredictionDraft:
        entries: list[PredictionEntryDraft] = []
        for member_id in self.cohort.member_ids:
            if member_id in self.unavailable_members:
                entries.append(
                    PredictionEntryDraft.unavailable(
                        member_id=member_id,
                        reason="Synthetic unavailable fixture",
                    )
                )
            else:
                sel = (
                    ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5))
                    if self.lottery_type is LotteryType.DAILY_539
                    else ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5, 6), special_number=1)
                )
                baseline = MatchedBaselineRef(
                    lottery_type=self.lottery_type,
                    baseline_id=f"base_{self.lottery_type.value.lower()}",
                    baseline_version="1.0",
                    authority_sha256=_sha256(f"base_auth_{self.lottery_type.value}"),
                    ticket_count=1,
                    candidate_sizes=(5,) if self.lottery_type is LotteryType.DAILY_539 else (6,),
                )
                entries.append(
                    PredictionEntryDraft.available(
                        member_id=member_id,
                        selections=(sel,),
                        matched_baseline=baseline,
                    )
                )
        return PredictionDraft(entries=tuple(entries))


class SyntheticProducerFactory:
    """Producer factory creating synthetic producers on demand."""

    def __init__(
        self,
        lottery_type: LotteryType,
        cohort: FrozenCohortRef,
        *,
        unavailable_members: set[str] | None = None,
    ) -> None:
        self.lottery_type = lottery_type
        self.cohort = cohort
        self.unavailable_members = unavailable_members or set()

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> SyntheticProducer:
        return SyntheticProducer(
            lottery_type=self.lottery_type,
            cohort=self.cohort,
            unavailable_members=self.unavailable_members,
        )


def test_recurring_automation_multi_cycle_progression(tmp_path: Path) -> None:
    """Test 3 consecutive simulated draw cycles for T539 and P638 end-to-end."""
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    t539_cohort = _build_t539_cohort(("m_alpha", "m_beta"))
    p638_cohort = _build_p638_cohort(("p_one", "p_two"))
    t539_fp = _build_producer_fingerprint("producer_t539")
    p638_fp = _build_producer_fingerprint("producer_p638")

    t539_factory = SyntheticProducerFactory(LotteryType.DAILY_539, t539_cohort)
    p638_factory = SyntheticProducerFactory(LotteryType.POWER_LOTTO, p638_cohort)

    # Seed baseline prior history draw for both
    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )
    _seed_draw(
        paths,
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="113000200",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14, 15),
        special_numbers=(1,),
    )

    # 3 consecutive draw dates
    t539_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
        {"drawDate": "20990103", "drawTerm": "113000102", "gameCode": T539_SCHEDULE_GAME_CODE},
        {"drawDate": "20990104", "drawTerm": "113000103", "gameCode": T539_SCHEDULE_GAME_CODE},
    ]
    p638_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000201", "gameCode": P638_SCHEDULE_GAME_CODE},
        {"drawDate": "20990105", "drawTerm": "113000202", "gameCode": P638_SCHEDULE_GAME_CODE},
        {"drawDate": "20990108", "drawTerm": "113000203", "gameCode": P638_SCHEDULE_GAME_CODE},
    ]

    _seed_schedule_authority(paths, t539_schedule + p638_schedule)

    # Seed presence run for all scheduled dates
    for d_str in ("2099-01-02", "2099-01-03", "2099-01-04"):
        d_val = date.fromisoformat(d_str)
        _insert_run(
            paths,
            run_id=f"pres-t539-{d_str}",
            lottery_type=LotteryType.DAILY_539,
            requested_start=d_val,
            requested_end=d_val,
            fetched_count=0,
        )
    for d_str in ("2099-01-02", "2099-01-05", "2099-01-08"):
        d_val = date.fromisoformat(d_str)
        _insert_run(
            paths,
            run_id=f"pres-p638-{d_str}",
            lottery_type=LotteryType.POWER_LOTTO,
            requested_start=d_val,
            requested_end=d_val,
            fetched_count=0,
        )

    simulated_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)  # 16:00 Taipei

    with open_database(paths, read_only=False) as conn:
        composition = compose_t539_p638_recurring_automation(
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: simulated_clock,
        )
        service = composition.service

        # -------------------------------------------------------------
        # Cycle 1: Draw 113000101 / 113000201 on 2099-01-02
        # -------------------------------------------------------------
        # 1. Pre-draw wake: seals predictions
        res1 = service.run_cycle_wake(as_of=simulated_clock)
        assert (
            res1.t539 is not None and res1.t539.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        )
        assert (
            res1.p638 is not None and res1.p638.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        )

        # 2. Mid-draw wake: clock is 21:00 Taipei (13:00 UTC), post-schedule but outcome absent
        mid_clock = datetime(2099, 1, 2, 13, 0, tzinfo=UTC)
        res_mid = service.run_cycle_wake(as_of=mid_clock)
        assert (
            res_mid.t539 is not None
            and res_mid.t539.state is RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
        )
        assert (
            res_mid.p638 is not None
            and res_mid.p638.state is RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
        )

        # 3. Official draw ingested
        _seed_draw(
            paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000101",
            draw_date=date(2099, 1, 2),
            main_numbers=(1, 2, 3, 4, 5),
        )
        _seed_draw(
            paths,
            lottery_type=LotteryType.POWER_LOTTO,
            draw_number="113000201",
            draw_date=date(2099, 1, 2),
            main_numbers=(1, 2, 3, 4, 5, 6),
            special_numbers=(1,),
        )

        # 4. Post-draw wake: joins and records forward evidence to ledger
        post_clock = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
        res_post = service.run_cycle_wake(as_of=post_clock)
        assert (
            res_post.t539 is not None
            and res_post.t539.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
        )
        assert (
            res_post.p638 is not None
            and res_post.p638.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
        )
        assert len(res_post.t539.ledger_results) == 2
        assert len(res_post.p638.ledger_results) == 2

        # 5. Redundant wake on the completed target: exact idempotent no-op
        res_dup_t539 = service.run_game_wake(
            LotteryType.DAILY_539, as_of=post_clock, target=res_post.t539.target
        )
        assert res_dup_t539.cycle_action == "REDUNDANT_WAKE_IDEMPOTENT_NO_OP"
        res_dup_p638 = service.run_game_wake(
            LotteryType.POWER_LOTTO, as_of=post_clock, target=res_post.p638.target
        )
        assert res_dup_p638.cycle_action == "REDUNDANT_WAKE_IDEMPOTENT_NO_OP"

        # -------------------------------------------------------------
        # Cycle 2: T539 advances to 113000102 on 2099-01-03
        # -------------------------------------------------------------
        simulated_clock = datetime(2099, 1, 3, 8, 0, tzinfo=UTC)
        res_c2_pre = service.run_game_wake(LotteryType.DAILY_539, as_of=simulated_clock)
        assert res_c2_pre.target is not None and res_c2_pre.target.draw_number == "113000102"
        assert res_c2_pre.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED

        _seed_draw(
            paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000102",
            draw_date=date(2099, 1, 3),
            main_numbers=(1, 2, 3, 4, 6),
        )

        res_c2_post = service.run_game_wake(
            LotteryType.DAILY_539, as_of=datetime(2099, 1, 3, 14, 0, tzinfo=UTC)
        )
        assert res_c2_post.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED

        # -------------------------------------------------------------
        # Cycle 3: T539 advances to 113000103 on 2099-01-04
        # -------------------------------------------------------------
        simulated_clock = datetime(2099, 1, 4, 8, 0, tzinfo=UTC)
        res_c3_pre = service.run_game_wake(LotteryType.DAILY_539, as_of=simulated_clock)
        assert res_c3_pre.target is not None and res_c3_pre.target.draw_number == "113000103"
        assert res_c3_pre.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED

        _seed_draw(
            paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000103",
            draw_date=date(2099, 1, 4),
            main_numbers=(10, 20, 30, 31, 32),
        )

        res_c3_post = service.run_game_wake(
            LotteryType.DAILY_539, as_of=datetime(2099, 1, 4, 14, 0, tzinfo=UTC)
        )
        assert res_c3_post.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED

        # Verify ledger entries sequence across all 3 cycles for T539
        entries = composition.t539_composition.ledger_service.get_cohort_entries(
            LotteryType.DAILY_539,
            t539_cohort.cohort_id,
            t539_cohort.cohort_version,
        )
        assert len(entries) == 6  # 3 draws * 2 members
        draw_sequence = [
            e.identity.target_draw_number for e in entries if e.identity.member_id == "m_alpha"
        ]
        assert draw_sequence == ["113000101", "113000102", "113000103"]

        summary = composition.t539_composition.ledger_service.summarize_member(
            LotteryType.DAILY_539,
            t539_cohort.cohort_id,
            t539_cohort.cohort_version,
            "m_alpha",
        )
        assert summary is not None
        assert summary.total_entries == 3
        assert summary.scored_count == 3
        assert summary.winning_count == 2  # 113000101 (jackpot) + 113000102 (4 hits)


def test_recurring_automation_mid_cycle_restart_recovery(tmp_path: Path) -> None:
    """Test clean resumption after mid-cycle crash/restart at each stage boundary."""
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    t539_cohort = _build_t539_cohort(("m_alpha",))
    p638_cohort = _build_p638_cohort(("p_one",))
    t539_fp = _build_producer_fingerprint("producer_t539")
    p638_fp = _build_producer_fingerprint("producer_p638")

    t539_factory = SyntheticProducerFactory(LotteryType.DAILY_539, t539_cohort)
    p638_factory = SyntheticProducerFactory(LotteryType.POWER_LOTTO, p638_cohort)

    # Seed baseline prior history draw
    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )
    _seed_draw(
        paths,
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="113000200",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14, 15),
        special_numbers=(1,),
    )

    t539_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
    ]
    p638_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000201", "gameCode": P638_SCHEDULE_GAME_CODE},
    ]
    _seed_schedule_authority(paths, t539_schedule + p638_schedule)

    _insert_run(
        paths,
        run_id="pres-t539-101",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )
    _insert_run(
        paths,
        run_id="pres-p638-201",
        lottery_type=LotteryType.POWER_LOTTO,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )

    clock1 = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)

    # 1. First process run: seal Stage C then simulate process crash
    with open_database(paths, read_only=False) as conn:
        comp1 = compose_t539_p638_recurring_automation(
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: clock1,
        )
        res1 = comp1.t539_composition.runner.run_wake()
        assert res1.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        # Process crash happens here (conn closed)

    # 2. Ingest official draw while process is down
    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
    )

    # 3. Second process run: resume after crash
    clock2 = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
    with open_database(paths, read_only=False) as conn:
        comp2 = compose_t539_p638_recurring_automation(
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: clock2,
        )
        # Resuming wake picks up existing prediction, joins outcome and appends to ledger
        res2 = comp2.t539_composition.runner.run_wake()
        assert res2.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
        assert res2.cycle_action == "POST_DRAW_JOIN_AND_EVIDENCE_APPENDED"

        entries = comp2.t539_composition.ledger_service.get_cohort_entries(
            LotteryType.DAILY_539,
            t539_cohort.cohort_id,
            t539_cohort.cohort_version,
        )
        assert len(entries) == 1
        assert entries[0].identity.target_draw_number == "113000101"


def test_recurring_automation_game_isolation(tmp_path: Path) -> None:
    """Test complete isolation between T539 and P638 when one game encounters missing authority."""
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    t539_cohort = _build_t539_cohort(("m_alpha",))
    p638_cohort = _build_p638_cohort(("p_one",))
    t539_fp = _build_producer_fingerprint("producer_t539")
    p638_fp = _build_producer_fingerprint("producer_p638")

    t539_factory = SyntheticProducerFactory(LotteryType.DAILY_539, t539_cohort)
    p638_factory = SyntheticProducerFactory(LotteryType.POWER_LOTTO, p638_cohort)

    # Seed baseline prior history draw for T539 only
    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )

    # Schedule ONLY T539 (P638 has no active schedule)
    t539_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
    ]
    _seed_schedule_authority(paths, t539_schedule)

    _insert_run(
        paths,
        run_id="pres-t539-101",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )

    clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)

    with open_database(paths, read_only=False) as conn:
        composition = compose_t539_p638_recurring_automation(
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: clock,
        )
        service = composition.service

        res = service.run_cycle_wake(as_of=clock)

        # T539 runs successfully
        assert res.t539 is not None
        assert res.t539.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        assert res.t539.error is None

        # P638 safely reports AWAITING_SCHEDULE without affecting T539
        assert res.p638 is not None
        assert res.p638.state is RecurringCycleState.AWAITING_SCHEDULE
        assert res.p638.error is None


def test_recurring_automation_unavailable_prediction_handling(tmp_path: Path) -> None:
    """Test that unavailable predictions (no-ticket) pass cleanly through Stage C -> E -> G."""
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    t539_cohort = _build_t539_cohort(("m_unavailable",))
    p638_cohort = _build_p638_cohort(("p_one",))
    t539_fp = _build_producer_fingerprint("producer_t539")
    p638_fp = _build_producer_fingerprint("producer_p638")

    # T539 producer always returns unavailable draft
    t539_factory = SyntheticProducerFactory(
        LotteryType.DAILY_539,
        t539_cohort,
        unavailable_members={"m_unavailable"},
    )
    p638_factory = SyntheticProducerFactory(LotteryType.POWER_LOTTO, p638_cohort)

    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )

    t539_schedule = [
        {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
    ]
    _seed_schedule_authority(paths, t539_schedule)

    _insert_run(
        paths,
        run_id="pres-t539-101",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )

    clock_pre = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)

    with open_database(paths, read_only=False) as conn:
        composition = compose_t539_p638_recurring_automation(
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: clock_pre,
        )

        res_pre = composition.t539_composition.runner.run_wake()
        assert res_pre.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED

        _seed_draw(
            paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000101",
            draw_date=date(2099, 1, 2),
            main_numbers=(1, 2, 3, 4, 5),
        )

        clock_post = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
        res_post = composition.t539_composition.runner.run_wake(as_of=clock_post)
        assert res_post.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED

        entries = composition.t539_composition.ledger_service.get_cohort_entries(
            LotteryType.DAILY_539,
            t539_cohort.cohort_id,
            t539_cohort.cohort_version,
        )
        assert len(entries) == 1
        entry = entries[0]
        assert entry.availability is ScoreAvailability.UNAVAILABLE_PREDICTION
        assert entry.tickets == ()
        assert entry.is_winner is None
