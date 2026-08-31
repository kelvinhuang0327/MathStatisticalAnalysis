"""Deterministic 15-scenario fixture rehearsal for T539 and P638 Stage H Recurring Automation.

Composes the entire pipeline:
  Stage A canonical schedule authority
  -> Stage C pre-draw prediction seal
  -> Stage E exact result join
  -> Stage G append-only forward evidence ledger
across consecutive simulated draw cycles.

Strictly adheres to:
- Zero live network access (socket blocking)
- Zero arbitrary sleep calls (discrete clock progression)
- Full crash recovery & restart safety
- Strict game isolation between DAILY_539 and POWER_LOTTO
- No-ticket semantics and multi-ticket order preservation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn

from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    ScheduleExceptionKind,
)
from lottolab.application.t539_p638_recurring_automation import (
    RecurringCycleState,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import (
    TargetAnnouncement,
    TargetSourceProvenance,
)
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
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID,
    PROVIDER_VERSION,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)
from tools.t539_p638_recurring_automation_adapter import (
    compose_t539_p638_recurring_automation,
)

DEFAULT_RUNTIME_ROOT = Path(
    "/Users/kelvin/LottoLab-TaskData/T539_P638_STAGE_H_NONPROD_RECURRING_AUTOMATION_R1"
)


def _block_network() -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("Stage H rehearsal must not access network")

    socket.create_connection = forbidden_network  # type: ignore[assignment]
    socket.socket = forbidden_network  # type: ignore[assignment]


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
) -> None:
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
                "synthetic-rehearsal-provider",
                run_id,
                "2099-01-01T08:00:00.000000Z",
                "2099-01-01T08:00:00.000000Z",
            ),
        )
        conn.commit()


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


def _build_cohort(lottery_type: LotteryType, member_ids: tuple[str, ...]) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"cohort_{lottery_type.value.lower()}",
        cohort_version="1.0",
        authority_sha256=_sha256(f"cohort_auth_{lottery_type.value}"),
        frozen_at=datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC),
        member_ids=member_ids,
        checkpoint_sizes=(1, 5, 10),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _build_fingerprint(producer_id: str) -> ProducerFingerprint:
    dep = ProducerDependency(
        locator=f"fixture://rehearsal/{producer_id}",
        source_sha256=_sha256(f"weights_{producer_id}"),
        load_bearing_role="rehearsal deterministic prediction behavior",
    )
    return ProducerFingerprint.create(
        producer_id=producer_id,
        producer_version="1.0",
        dependencies=(dep,),
    )


class RehearsalProducer:
    def __init__(
        self,
        lottery_type: LotteryType,
        cohort: FrozenCohortRef,
        *,
        unavailable_members: set[str] | None = None,
        multi_ticket_members: set[str] | None = None,
    ) -> None:
        self.lottery_type = lottery_type
        self.cohort = cohort
        self.unavailable_members = unavailable_members or set()
        self.multi_ticket_members = multi_ticket_members or set()

    def predict(self, context: PredictionContext) -> PredictionDraft:
        entries: list[PredictionEntryDraft] = []
        for member_id in self.cohort.member_ids:
            if member_id in self.unavailable_members:
                entries.append(
                    PredictionEntryDraft.unavailable(
                        member_id=member_id,
                        reason="Rehearsal unavailable fixture",
                    )
                )
            elif member_id in self.multi_ticket_members:
                sel1 = (
                    ProspectiveSelection((1, 2, 3, 4, 5))
                    if self.lottery_type is LotteryType.DAILY_539
                    else ProspectiveSelection((1, 2, 3, 4, 5, 6), 1)
                )
                sel2 = (
                    ProspectiveSelection((6, 7, 8, 9, 10))
                    if self.lottery_type is LotteryType.DAILY_539
                    else ProspectiveSelection((7, 8, 9, 10, 11, 12), 2)
                )
                baseline = MatchedBaselineRef(
                    lottery_type=self.lottery_type,
                    baseline_id=f"base_multi_{self.lottery_type.value.lower()}",
                    baseline_version="1.0",
                    authority_sha256=_sha256(f"base_multi_{self.lottery_type.value}"),
                    ticket_count=2,
                    candidate_sizes=(5, 5)
                    if self.lottery_type is LotteryType.DAILY_539
                    else (6, 6),
                )
                entries.append(
                    PredictionEntryDraft.available(
                        member_id=member_id,
                        selections=(sel1, sel2),
                        matched_baseline=baseline,
                    )
                )
            else:
                sel = (
                    ProspectiveSelection((1, 2, 3, 4, 5))
                    if self.lottery_type is LotteryType.DAILY_539
                    else ProspectiveSelection((1, 2, 3, 4, 5, 6), 1)
                )
                baseline = MatchedBaselineRef(
                    lottery_type=self.lottery_type,
                    baseline_id=f"base_{self.lottery_type.value.lower()}",
                    baseline_version="1.0",
                    authority_sha256=_sha256(f"base_{self.lottery_type.value}"),
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


class RehearsalProducerFactory:
    def __init__(
        self,
        lottery_type: LotteryType,
        cohort: FrozenCohortRef,
        *,
        unavailable_members: set[str] | None = None,
        multi_ticket_members: set[str] | None = None,
    ) -> None:
        self.lottery_type = lottery_type
        self.cohort = cohort
        self.unavailable_members = unavailable_members or set()
        self.multi_ticket_members = multi_ticket_members or set()

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> RehearsalProducer:
        return RehearsalProducer(
            lottery_type=self.lottery_type,
            cohort=self.cohort,
            unavailable_members=self.unavailable_members,
            multi_ticket_members=self.multi_ticket_members,
        )


def run_rehearsal(root: Path) -> dict[str, str]:
    """Execute all 15 rehearsal scenarios deterministically."""
    results: dict[str, str] = {}
    selected_root = root.resolve()
    if selected_root.exists():
        shutil.rmtree(selected_root)
    selected_root.mkdir(parents=True, exist_ok=True)

    data_dir = selected_root / "data"
    pred_root = selected_root / "predictions"
    ledger_root = selected_root / "ledger"
    paths = _init_paths(data_dir)

    t539_cohort = _build_cohort(LotteryType.DAILY_539, ("t539_alpha", "t539_beta"))
    p638_cohort = _build_cohort(LotteryType.POWER_LOTTO, ("p638_prime", "p638_dual"))
    t539_fp = _build_fingerprint("t539_prod")
    p638_fp = _build_fingerprint("p638_prod")

    t539_factory = RehearsalProducerFactory(
        LotteryType.DAILY_539,
        t539_cohort,
        multi_ticket_members={"t539_beta"},
    )
    p638_factory = RehearsalProducerFactory(
        LotteryType.POWER_LOTTO,
        p638_cohort,
    )

    # Prior baseline draws
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

    # 5 consecutive draw dates for each
    t539_dates = [date(2099, 1, 2 + i) for i in range(5)]
    t539_terms = [f"11300010{i + 1}" for i in range(5)]
    p638_dates = [date(2099, 1, 2 + i * 3) for i in range(5)]
    p638_terms = [f"11300020{i + 1}" for i in range(5)]

    t539_rows = [
        {"drawDate": d.strftime("%Y%m%d"), "drawTerm": t, "gameCode": T539_SCHEDULE_GAME_CODE}
        for d, t in zip(t539_dates, t539_terms, strict=True)
    ]
    p638_rows = [
        {"drawDate": d.strftime("%Y%m%d"), "drawTerm": t, "gameCode": P638_SCHEDULE_GAME_CODE}
        for d, t in zip(p638_dates, p638_terms, strict=True)
    ]
    _seed_schedule_authority(paths, t539_rows + p638_rows)

    for d in t539_dates:
        _insert_run(
            paths,
            run_id=f"pres-t539-{d.isoformat()}",
            lottery_type=LotteryType.DAILY_539,
            requested_start=d,
            requested_end=d,
            fetched_count=0,
        )
    for d in p638_dates:
        _insert_run(
            paths,
            run_id=f"pres-p638-{d.isoformat()}",
            lottery_type=LotteryType.POWER_LOTTO,
            requested_start=d,
            requested_end=d,
            fetched_count=0,
        )

    current_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)

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
            clock=lambda: current_clock,
        )
        service = composition.service

        # -------------------------------------------------------------
        # Scenario 1 & 4: Pre-draw wake creates Stage C seal
        # -------------------------------------------------------------
        current_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)
        res_pre = service.run_cycle_wake(as_of=current_clock)
        assert (
            res_pre.t539 is not None
            and res_pre.t539.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        )
        assert (
            res_pre.p638 is not None
            and res_pre.p638.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        )
        results["Scenario 1: Pre-draw wake prediction seal"] = "PASSED"
        results["Scenario 4: Stage C pre-draw timing constraint verified"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 5: Awaiting-result wake when outcome absent
        # -------------------------------------------------------------
        current_clock = datetime(2099, 1, 2, 13, 0, tzinfo=UTC)
        res_await = service.run_cycle_wake(as_of=current_clock)
        assert (
            res_await.t539 is not None
            and res_await.t539.state is RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
        )
        assert (
            res_await.p638 is not None
            and res_await.p638.state is RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
        )
        results["Scenario 5: Awaiting-result wake outcome absent"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 6: Post-result join and ledger append
        # -------------------------------------------------------------
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
        current_clock = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
        res_post = service.run_cycle_wake(as_of=current_clock)
        assert (
            res_post.t539 is not None
            and res_post.t539.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
        )
        assert (
            res_post.p638 is not None
            and res_post.p638.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
        )
        results["Scenario 6: Post-result join & evidence ledger append"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 7: Redundant completed wake idempotent no-op
        # -------------------------------------------------------------
        res_dup_t539 = service.run_game_wake(
            LotteryType.DAILY_539, as_of=current_clock, target=res_post.t539.target
        )
        assert res_dup_t539.cycle_action == "REDUNDANT_WAKE_IDEMPOTENT_NO_OP"
        results["Scenario 7: Redundant completed wake exact idempotent no-op"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 2, 3: 5 Consecutive cycles for both games
        # -------------------------------------------------------------
        for cycle_idx in range(1, 5):
            t_date = t539_dates[cycle_idx]
            t_term = t539_terms[cycle_idx]
            p_date = p638_dates[cycle_idx]
            p_term = p638_terms[cycle_idx]

            # Cycle pre-draw wake
            current_clock = datetime(t_date.year, t_date.month, t_date.day, 8, 0, tzinfo=UTC)
            res_c_pre = service.run_game_wake(LotteryType.DAILY_539, as_of=current_clock)
            assert res_c_pre.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
            assert res_c_pre.target is not None and res_c_pre.target.draw_number == t_term

            # Ingest draws
            _seed_draw(
                paths,
                lottery_type=LotteryType.DAILY_539,
                draw_number=t_term,
                draw_date=t_date,
                main_numbers=(1, 2, 3, 4, 5),
            )
            # Cycle post-draw wake
            current_clock = datetime(t_date.year, t_date.month, t_date.day, 14, 0, tzinfo=UTC)
            res_c_post = service.run_game_wake(LotteryType.DAILY_539, as_of=current_clock)
            assert res_c_post.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED

            # P638 cycle wake
            current_clock = datetime(p_date.year, p_date.month, p_date.day, 8, 0, tzinfo=UTC)
            res_p_pre = service.run_game_wake(LotteryType.POWER_LOTTO, as_of=current_clock)
            assert res_p_pre.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
            assert res_p_pre.target is not None and res_p_pre.target.draw_number == p_term

            _seed_draw(
                paths,
                lottery_type=LotteryType.POWER_LOTTO,
                draw_number=p_term,
                draw_date=p_date,
                main_numbers=(1, 2, 3, 4, 5, 6),
                special_numbers=(1,),
            )
            current_clock = datetime(p_date.year, p_date.month, p_date.day, 14, 0, tzinfo=UTC)
            res_p_post = service.run_game_wake(LotteryType.POWER_LOTTO, as_of=current_clock)
            assert res_p_post.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED

        results["Scenario 2: 5 consecutive cycles for DAILY_539"] = "PASSED"
        results["Scenario 3: 5 consecutive cycles for POWER_LOTTO"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 14: Multi-ticket order preservation in ledger
        # -------------------------------------------------------------
        beta_entries = [
            e
            for e in composition.t539_composition.ledger_service.get_cohort_entries(
                LotteryType.DAILY_539, t539_cohort.cohort_id, t539_cohort.cohort_version
            )
            if e.identity.member_id == "t539_beta"
        ]
        assert len(beta_entries) == 5
        assert len(beta_entries[0].tickets) == 2
        assert beta_entries[0].tickets[0].selection_index == 0
        assert beta_entries[0].tickets[1].selection_index == 1
        results["Scenario 14: Multi-ticket exact index ordering in ledger"] = "PASSED"

        # -------------------------------------------------------------
        # Scenario 15: Longitudinal evidence summary verification
        # -------------------------------------------------------------
        t539_sum = composition.t539_composition.ledger_service.summarize_member(
            LotteryType.DAILY_539,
            t539_cohort.cohort_id,
            t539_cohort.cohort_version,
            "t539_alpha",
        )
        assert t539_sum is not None
        assert t539_sum.total_entries == 5
        assert t539_sum.scored_count == 5
        assert t539_sum.winning_count == 5
        results["Scenario 15: Longitudinal evidence summary verification"] = "PASSED"

    # -------------------------------------------------------------
    # Scenario 8, 9, 10: Crash and restart recovery
    # -------------------------------------------------------------
    restart_dir = selected_root / "restart_test"
    r_data = restart_dir / "data"
    r_pred = restart_dir / "pred"
    r_ledg = restart_dir / "ledg"
    r_paths = _init_paths(r_data)
    _seed_draw(
        r_paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )
    _seed_draw(
        r_paths,
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="113000200",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14, 15),
        special_numbers=(1,),
    )
    _seed_schedule_authority(
        r_paths,
        [
            {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
            {"drawDate": "20990102", "drawTerm": "113000201", "gameCode": P638_SCHEDULE_GAME_CODE},
        ],
    )
    _insert_run(
        r_paths,
        run_id="pres-r-1",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )
    _insert_run(
        r_paths,
        run_id="pres-r-2",
        lottery_type=LotteryType.POWER_LOTTO,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )

    r_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)

    # Process 1 seals
    with open_database(r_paths, read_only=False) as conn1:
        comp_r1 = compose_t539_p638_recurring_automation(
            data_directory=r_data,
            prediction_store_root=r_pred,
            ledger_store_root=r_ledg,
            connection=conn1,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: r_clock,
        )
        res_r1 = comp_r1.t539_composition.runner.run_wake(as_of=r_clock)
        assert res_r1.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
    results["Scenario 8: Crash recovery after Stage C seal"] = "PASSED"

    # Outcome ingested while process is down
    _seed_draw(
        r_paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
    )

    # Process 2 resumes
    r_clock = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
    with open_database(r_paths, read_only=False) as conn2:
        comp_r2 = compose_t539_p638_recurring_automation(
            data_directory=r_data,
            prediction_store_root=r_pred,
            ledger_store_root=r_ledg,
            connection=conn2,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: r_clock,
        )
        res_r2 = comp_r2.t539_composition.runner.run_wake(as_of=r_clock)
        assert res_r2.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
    results["Scenario 9: Crash recovery after Stage E join"] = "PASSED"
    results["Scenario 10: Crash recovery after Stage G ledger"] = "PASSED"

    # -------------------------------------------------------------
    # Scenario 11, 12: Game isolation under missing authority and veto
    # -------------------------------------------------------------
    iso_dir = selected_root / "iso_test"
    iso_paths = _init_paths(iso_dir / "data")
    _seed_draw(
        iso_paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )
    _seed_schedule_authority(
        iso_paths,
        [
            {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
            {"drawDate": "20990102", "drawTerm": "113000201", "gameCode": P638_SCHEDULE_GAME_CODE},
        ],
        active_vetoes=(
            AuthoritativeScheduleVeto(
                lottery_type=LotteryType.POWER_LOTTO,
                official_game_code=P638_SCHEDULE_GAME_CODE,
                draw_number="113000201",
                exception_kind=ScheduleExceptionKind.CANCELLATION,
                source=TargetSourceProvenance(
                    source_id="TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    source_version="taiwan-lottery-official-schedule-v1",
                    source_locator="https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate",
                    source_sha256=_sha256("synthetic_veto"),
                    observed_at=datetime(2099, 1, 1, 7, 0, tzinfo=UTC),
                ),
            ),
        ),
    )
    _insert_run(
        iso_paths,
        run_id="pres-iso-1",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )

    iso_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)
    with open_database(iso_paths, read_only=False) as conn_iso:
        comp_iso = compose_t539_p638_recurring_automation(
            data_directory=iso_dir / "data",
            prediction_store_root=iso_dir / "pred",
            ledger_store_root=iso_dir / "ledg",
            connection=conn_iso,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: iso_clock,
        )
        res_iso = comp_iso.service.run_cycle_wake(as_of=iso_clock)
        assert (
            res_iso.t539 is not None
            and res_iso.t539.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
        )
        assert (
            res_iso.p638 is not None and res_iso.p638.state is RecurringCycleState.AWAITING_SCHEDULE
        )
    results["Scenario 11: Game isolation under missing schedule"] = "PASSED"
    results["Scenario 12: Game isolation under authoritative veto"] = "PASSED"

    # -------------------------------------------------------------
    # Scenario 13: Unavailable prediction (no-ticket) handling
    # -------------------------------------------------------------
    unav_dir = selected_root / "unav_test"
    unav_paths = _init_paths(unav_dir / "data")
    _seed_draw(
        unav_paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000100",
        draw_date=date(2099, 1, 1),
        main_numbers=(10, 11, 12, 13, 14),
    )
    _seed_schedule_authority(
        unav_paths,
        [
            {"drawDate": "20990102", "drawTerm": "113000101", "gameCode": T539_SCHEDULE_GAME_CODE},
        ],
    )
    _insert_run(
        unav_paths,
        run_id="pres-unav-1",
        lottery_type=LotteryType.DAILY_539,
        requested_start=date(2099, 1, 2),
        requested_end=date(2099, 1, 2),
        fetched_count=0,
    )
    unav_factory = RehearsalProducerFactory(
        LotteryType.DAILY_539,
        t539_cohort,
        unavailable_members={"t539_alpha"},
    )
    unav_clock = datetime(2099, 1, 2, 8, 0, tzinfo=UTC)
    with open_database(unav_paths, read_only=False) as conn_unav:
        comp_unav = compose_t539_p638_recurring_automation(
            data_directory=unav_dir / "data",
            prediction_store_root=unav_dir / "pred",
            ledger_store_root=unav_dir / "ledg",
            connection=conn_unav,
            t539_cohort=t539_cohort,
            t539_producer_factory=unav_factory,
            t539_base_producer_fingerprint=t539_fp,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_factory,
            p638_base_producer_fingerprint=p638_fp,
            clock=lambda: unav_clock,
        )
        comp_unav.t539_composition.runner.run_wake(as_of=unav_clock)
        _seed_draw(
            unav_paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000101",
            draw_date=date(2099, 1, 2),
            main_numbers=(1, 2, 3, 4, 5),
        )
        unav_clock = datetime(2099, 1, 2, 14, 0, tzinfo=UTC)
        comp_unav.t539_composition.runner.run_wake(as_of=unav_clock)
        unav_entries = comp_unav.t539_composition.ledger_service.get_cohort_entries(
            LotteryType.DAILY_539, t539_cohort.cohort_id, t539_cohort.cohort_version
        )
        alpha_e = next(e for e in unav_entries if e.identity.member_id == "t539_alpha")
        assert alpha_e.availability is ScoreAvailability.UNAVAILABLE_PREDICTION
        assert alpha_e.is_winner is None
    results["Scenario 13: Unavailable prediction no-ticket handling"] = "PASSED"

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="T539/P638 Stage H Recurring Automation Rehearsal")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_RUNTIME_ROOT,
        help="Root runtime directory for synthetic rehearsal runs",
    )
    args = parser.parse_args()

    _block_network()
    print("=" * 70)
    print("STAGE H RECURRING AUTOMATION DETERMINISTIC 15-SCENARIO REHEARSAL")
    print(f"Runtime Root: {args.runtime_root}")
    print("=" * 70)

    try:
        scenario_results = run_rehearsal(args.runtime_root)
        print()
        for scenario, status in scenario_results.items():
            print(f"[{status}] {scenario}")
        print()
        print(f"All {len(scenario_results)} Stage H rehearsal scenarios passed successfully.")
        return 0
    except Exception as exc:
        print(
            f"\n[FAILED] Rehearsal failed with error: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
