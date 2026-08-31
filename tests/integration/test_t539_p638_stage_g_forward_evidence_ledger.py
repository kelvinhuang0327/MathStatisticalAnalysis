"""Combined integration tests and fixture rehearsal for T539/P638 Stage G Forward Evidence Ledger.

Validates the full prospective evidence ledger pipeline over the Stage A -> C -> E pipeline:
- Deterministic append-only forward evidence recording.
- Preservation of immutable prediction, outcome, and score hashes and authority.
- Per-ticket ordering, exact hit signatures, and prize tier resolution.
- No-ticket semantics (unavailable prediction is not scored and not a loss).
- Exact duplicate idempotent replay.
- Conflicting duplicate fail-closed error.
- Crash recovery and restart safety.
- Complete T539 / P638 game and cohort isolation.
- Zero-network and storage safety enforcement.
"""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from tools.t539_p638_stage_g_forward_evidence_ledger import (
    compose_t539_p638_stage_g_forward_evidence_ledger,
)

from lottolab.application.draw_data import DrawRecord
from lottolab.application.forward_evidence_ledger import (
    ForwardEvidenceLedgerAppendStatus,
    ForwardEvidenceLedgerService,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.forward_evidence_ledger import (
    ForwardEvidenceLedgerConflictError,
    ForwardEvidenceLedgerLinkError,
)
from lottolab.domain.prize_evaluation import (
    PrizeEvaluationResult,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    GameEvaluation,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
    TemporalProvenance,
)
from lottolab.infrastructure.forward_evidence_ledger_store import (
    FileSystemForwardEvidenceLedgerStore,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawRepository

_NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)
_SCORED_AT = datetime(2099, 1, 2, 22, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _network_is_forbidden(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("Stage G forward evidence ledger must not access network")

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
    draw_date: date,
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
            ) VALUES (
                ?, 'MANUAL_SYNC', 'SUCCESS', ?, 'synthetic.json', ?, 'v1',
                1, 1, 0, 0, 0, NULL, NULL, ?, ?, NULL
            )
            """,
            (
                run_id,
                lottery_type.value,
                _sha256(run_id),
                timestamp,
                timestamp,
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
    _insert_run(paths, run_id=run_id, lottery_type=lottery_type, draw_date=draw_date)
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
        locator="canonical_schedule_authority",
        source_sha256=_sha256("schedule_authority_source"),
        load_bearing_role="SCHEDULE_AUTHORITY",
    )
    return ProducerFingerprint.create(
        producer_id=producer_id,
        producer_version="1.0",
        dependencies=(dep,),
    )


def _create_prediction(
    *,
    cohort: FrozenCohortRef,
    draw_number: str,
    draw_date: date,
    draft_entries: tuple[PredictionEntryDraft, ...],
    predicted_at: datetime = _NOW,
) -> PredictionRecord:
    target = ObservationTarget(
        lottery_type=cohort.lottery_type,
        draw_number=draw_number,
        draw_date=draw_date,
    )
    causal = CausalHistoryRef(
        draw_count=50,
        last_draw_number="999999000",
        last_draw_date=date(2099, 1, 1),
        history_sha256=_sha256("causal_history"),
    )
    fingerprint = _build_producer_fingerprint(f"{cohort.lottery_type.value.lower()}_producer")
    context = PredictionContext(
        target=target,
        cohort=cohort,
        producer_fingerprint=fingerprint,
        causal_history=causal,
    )
    request = PredictionPhaseRequest(
        context=context,
        outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
    )
    return PredictionRecord.create(
        request=request,
        draft=PredictionDraft(entries=draft_entries),
        predicted_at=predicted_at,
    )


def test_t539_append_sequential_draws_and_chronological_ordering(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    cohort = _build_t539_cohort(("m_alpha", "m_beta"))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )

    # 3 sequential draws: 101, 102, 103
    draw_dates = [date(2099, 1, 2), date(2099, 1, 3), date(2099, 1, 4)]
    draw_terms = ["113000101", "113000102", "113000103"]

    for d_term, d_date in zip(draw_terms, draw_dates, strict=True):
        _seed_draw(
            paths,
            lottery_type=LotteryType.DAILY_539,
            draw_number=d_term,
            draw_date=d_date,
            main_numbers=(1, 2, 3, 4, 5),
        )

    with open_database(paths, read_only=False) as conn:
        comp = compose_t539_p638_stage_g_forward_evidence_ledger(
            lottery_type=LotteryType.DAILY_539,
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            clock=lambda: _SCORED_AT,
        )

        for d_term, d_date in zip(draw_terms, draw_dates, strict=True):
            pred = _create_prediction(
                cohort=cohort,
                draw_number=d_term,
                draw_date=d_date,
                draft_entries=(
                    PredictionEntryDraft.available(
                        member_id="m_alpha",
                        selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                        matched_baseline=baseline,
                    ),
                    PredictionEntryDraft.available(
                        member_id="m_beta",
                        selections=(ProspectiveSelection(main_numbers=(10, 11, 12, 13, 14)),),
                        matched_baseline=baseline,
                    ),
                ),
            )
            comp.prediction_store.create_prediction(pred)

            join_res = comp.result_join_service.join_result(
                pred.identity,
                pred.producer_fingerprint,
            )
            assert join_res.status is ProspectiveResultJoinStatus.CREATED

            append_results = comp.ledger_service.record_stage_e_result(
                result=join_res,
                prediction=pred,
            )
            assert len(append_results) == 2
            assert all(
                r.status is ForwardEvidenceLedgerAppendStatus.APPENDED for r in append_results
            )

        # Verify chronological ordering for m_alpha
        alpha_entries = comp.ledger_service.get_member_entries(
            lottery_type=LotteryType.DAILY_539,
            cohort_id=cohort.cohort_id,
            cohort_version=cohort.cohort_version,
            member_id="m_alpha",
        )
        assert len(alpha_entries) == 3
        assert [e.identity.target_draw_number for e in alpha_entries] == draw_terms
        assert [e.identity.target_draw_date for e in alpha_entries] == draw_dates
        assert all(e.is_winner is True for e in alpha_entries)

        # Verify summary for m_alpha
        summary_alpha = comp.ledger_service.summarize_member(
            lottery_type=LotteryType.DAILY_539,
            cohort_id=cohort.cohort_id,
            cohort_version=cohort.cohort_version,
            member_id="m_alpha",
        )
        assert summary_alpha is not None
        assert summary_alpha.total_entries == 3
        assert summary_alpha.scored_count == 3
        assert summary_alpha.winning_count == 3
        assert summary_alpha.nonwinning_count == 0
        assert summary_alpha.unavailable_count == 0
        assert summary_alpha.prize_tier_counts == {"FIRST": 3}

        # Verify summary for m_beta (0 hits each)
        summary_beta = comp.ledger_service.summarize_member(
            lottery_type=LotteryType.DAILY_539,
            cohort_id=cohort.cohort_id,
            cohort_version=cohort.cohort_version,
            member_id="m_beta",
        )
        assert summary_beta is not None
        assert summary_beta.total_entries == 3
        assert summary_beta.scored_count == 3
        assert summary_beta.winning_count == 0
        assert summary_beta.nonwinning_count == 3
        assert summary_beta.prize_tier_counts == {}


def test_p638_append_and_zone_evaluation_preservation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    cohort = _build_p638_cohort(("p_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.POWER_LOTTO,
        baseline_id="p638_base",
        baseline_version="1.0",
        authority_sha256=_sha256("p_base_auth"),
        ticket_count=2,
        candidate_sizes=(6, 6),
    )

    _seed_draw(
        paths,
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="113000201",
        draw_date=date(2099, 1, 5),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(8,),
    )

    with open_database(paths, read_only=False) as conn:
        comp = compose_t539_p638_stage_g_forward_evidence_ledger(
            lottery_type=LotteryType.POWER_LOTTO,
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            clock=lambda: _SCORED_AT,
        )

        pred = _create_prediction(
            cohort=cohort,
            draw_number="113000201",
            draw_date=date(2099, 1, 5),
            draft_entries=(
                PredictionEntryDraft.available(
                    member_id="p_alpha",
                    selections=(
                        # Ticket 0: 6 main + zone2 (8) -> FIRST tier (頭獎)
                        ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5, 6), special_number=8),
                        # Ticket 1: 3 main + zone2 (8) -> SEVENTH tier (柒獎, zone1=3, zone2=True)
                        ProspectiveSelection(main_numbers=(1, 2, 3, 20, 21, 22), special_number=8),
                    ),
                    matched_baseline=baseline,
                ),
            ),
        )
        comp.prediction_store.create_prediction(pred)

        join_res = comp.result_join_service.join_result(
            pred.identity,
            pred.producer_fingerprint,
        )
        assert join_res.status is ProspectiveResultJoinStatus.CREATED

        results = comp.ledger_service.record_stage_e_result(result=join_res, prediction=pred)
        assert len(results) == 1
        entry = results[0].entry

        assert entry.identity.lottery_type is LotteryType.POWER_LOTTO
        assert len(entry.tickets) == 2
        # Ticket 0
        assert entry.tickets[0].selection_index == 0
        assert entry.tickets[0].zone1_hits == 6
        assert entry.tickets[0].zone2_hit is True
        assert entry.tickets[0].prize_tier == "FIRST"
        assert entry.tickets[0].prize_tier_order == 1
        assert entry.tickets[0].is_winner is True
        # Ticket 1
        assert entry.tickets[1].selection_index == 1
        assert entry.tickets[1].zone1_hits == 3
        assert entry.tickets[1].zone2_hit is True
        assert entry.tickets[1].prize_tier == "SEVENTH"
        assert entry.tickets[1].prize_tier_order == 7
        assert entry.tickets[1].is_winner is True


def test_exact_duplicate_replay_idempotent_no_op(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    paths = _init_paths(data_dir)
    pred_root = tmp_path / "predictions"
    ledger_root = tmp_path / "ledger"

    cohort = _build_t539_cohort(("m_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )

    _seed_draw(
        paths,
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
    )

    with open_database(paths, read_only=False) as conn:
        comp = compose_t539_p638_stage_g_forward_evidence_ledger(
            lottery_type=LotteryType.DAILY_539,
            data_directory=data_dir,
            prediction_store_root=pred_root,
            ledger_store_root=ledger_root,
            connection=conn,
            clock=lambda: _SCORED_AT,
        )

        pred = _create_prediction(
            cohort=cohort,
            draw_number="113000101",
            draw_date=date(2099, 1, 2),
            draft_entries=(
                PredictionEntryDraft.available(
                    member_id="m_alpha",
                    selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                    matched_baseline=baseline,
                ),
            ),
        )
        comp.prediction_store.create_prediction(pred)

        join_res = comp.result_join_service.join_result(
            pred.identity,
            pred.producer_fingerprint,
        )

        # 1st time: APPENDED
        res1 = comp.ledger_service.record_stage_e_result(result=join_res, prediction=pred)
        assert res1[0].status is ForwardEvidenceLedgerAppendStatus.APPENDED

        # 2nd time: EXACT_IDEMPOTENT_NO_OP
        res2 = comp.ledger_service.record_stage_e_result(result=join_res, prediction=pred)
        assert res2[0].status is ForwardEvidenceLedgerAppendStatus.EXACT_IDEMPOTENT_NO_OP
        assert res2[0].entry.ledger_entry_hash == res1[0].entry.ledger_entry_hash


def test_conflicting_duplicate_fails_closed(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"

    cohort = _build_t539_cohort(("m_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )

    pred1 = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="m_alpha",
                selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                matched_baseline=baseline,
            ),
        ),
    )
    outcome1 = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="src_1",
        source_sha256=_sha256("src_1"),
    )
    score1 = ScoreRecord.create(
        prediction=pred1,
        outcome=outcome1,
        entries=(
            ScoreEntry(
                member_id="m_alpha",
                prediction_hash=pred1.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.DAILY_539,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.DAILY_539,
                            is_winner=True,
                            prize_tier="頭獎",
                            prize_tier_order=1,
                            zone1_hits=5,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    # Alternate conflicting score for same identity
    outcome2 = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(10, 11, 12, 13, 14),
        special_number=None,
        source_id="src_2",
        source_sha256=_sha256("src_2"),
    )
    score2 = ScoreRecord.create(
        prediction=pred1,
        outcome=outcome2,
        entries=(
            ScoreEntry(
                member_id="m_alpha",
                prediction_hash=pred1.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.DAILY_539,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.DAILY_539,
                            is_winner=False,
                            prize_tier=None,
                            prize_tier_order=None,
                            zone1_hits=0,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    store = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    # 1. Record score1 -> ok
    service.record_score(prediction=pred1, score=score1)

    # 2. Record conflicting score2 -> fails closed
    with pytest.raises(ForwardEvidenceLedgerConflictError, match="Conflicting forward evidence"):
        service.record_score(prediction=pred1, score=score2)


def test_restart_and_reload_persisted_state(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store1 = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service1 = ForwardEvidenceLedgerService(store=store1, clock=lambda: _SCORED_AT)

    cohort = _build_t539_cohort(("m_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )

    pred = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="m_alpha",
                selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                matched_baseline=baseline,
            ),
        ),
    )
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="src_1",
        source_sha256=_sha256("src_1"),
    )
    score = ScoreRecord.create(
        prediction=pred,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id="m_alpha",
                prediction_hash=pred.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.DAILY_539,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.DAILY_539,
                            is_winner=True,
                            prize_tier="頭獎",
                            prize_tier_order=1,
                            zone1_hits=5,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    service1.record_score(prediction=pred, score=score)

    # Create brand new store and service instance simulating process restart
    store2 = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service2 = ForwardEvidenceLedgerService(store=store2, clock=lambda: _SCORED_AT)

    summary = service2.summarize_member(
        lottery_type=LotteryType.DAILY_539,
        cohort_id=cohort.cohort_id,
        cohort_version=cohort.cohort_version,
        member_id="m_alpha",
    )
    assert summary is not None
    assert summary.total_entries == 1
    assert summary.scored_count == 1
    assert summary.winning_count == 1
    assert summary.prize_tier_counts == {"頭獎": 1}


def test_no_ticket_unavailable_semantics(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    cohort = _build_t539_cohort(("m_unavail",))
    pred = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.unavailable(
                member_id="m_unavail",
                reason="Cold start period",
            ),
        ),
    )
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="src_1",
        source_sha256=_sha256("src_1"),
    )
    score = ScoreRecord.create(
        prediction=pred,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id="m_unavail",
                prediction_hash=pred.entries[0].prediction_hash,
                availability=ScoreAvailability.UNAVAILABLE_PREDICTION,
                evaluation=None,
            ),
        ),
        scored_at=_SCORED_AT,
    )

    results = service.record_score(prediction=pred, score=score)
    assert len(results) == 1
    entry = results[0].entry

    assert entry.availability is ScoreAvailability.UNAVAILABLE_PREDICTION
    assert entry.unavailable_reason == "Cold start period"
    assert entry.is_winner is None
    assert entry.tickets == ()

    summary = service.summarize_member(
        lottery_type=LotteryType.DAILY_539,
        cohort_id=cohort.cohort_id,
        cohort_version=cohort.cohort_version,
        member_id="m_unavail",
    )
    assert summary is not None
    assert summary.total_entries == 1
    assert summary.unavailable_count == 1
    assert summary.scored_count == 0
    assert summary.winning_count == 0
    assert summary.nonwinning_count == 0
    assert summary.total_tickets_evaluated == 0
    assert summary.winning_tickets_count == 0


def test_t539_p638_cross_game_isolation(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    t539_cohort = _build_t539_cohort(("common_member_id",))
    p638_cohort = _build_p638_cohort(("common_member_id",))

    t539_baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("t_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )
    p638_baseline = MatchedBaselineRef(
        lottery_type=LotteryType.POWER_LOTTO,
        baseline_id="p638_base",
        baseline_version="1.0",
        authority_sha256=_sha256("p_auth"),
        ticket_count=1,
        candidate_sizes=(6,),
    )

    t539_pred = _create_prediction(
        cohort=t539_cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="common_member_id",
                selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                matched_baseline=t539_baseline,
            ),
        ),
    )
    t539_outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="t_src",
        source_sha256=_sha256("t_src"),
    )
    t539_score = ScoreRecord.create(
        prediction=t539_pred,
        outcome=t539_outcome,
        entries=(
            ScoreEntry(
                member_id="common_member_id",
                prediction_hash=t539_pred.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.DAILY_539,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.DAILY_539,
                            is_winner=True,
                            prize_tier="頭獎",
                            prize_tier_order=1,
                            zone1_hits=5,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    p638_pred = _create_prediction(
        cohort=p638_cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="common_member_id",
                selections=(
                    ProspectiveSelection(
                        main_numbers=(10, 11, 12, 13, 14, 15),
                        special_number=1,
                    ),
                ),
                matched_baseline=p638_baseline,
            ),
        ),
    )
    p638_outcome = OfficialOutcome.create(
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
        source_id="p_src",
        source_sha256=_sha256("p_src"),
    )
    p638_score = ScoreRecord.create(
        prediction=p638_pred,
        outcome=p638_outcome,
        entries=(
            ScoreEntry(
                member_id="common_member_id",
                prediction_hash=p638_pred.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.POWER_LOTTO,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.POWER_LOTTO,
                            is_winner=False,
                            prize_tier=None,
                            prize_tier_order=None,
                            zone1_hits=0,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    service.record_score(prediction=t539_pred, score=t539_score)
    service.record_score(prediction=p638_pred, score=p638_score)

    t539_entries = service.get_member_entries(
        lottery_type=LotteryType.DAILY_539,
        cohort_id=t539_cohort.cohort_id,
        cohort_version=t539_cohort.cohort_version,
        member_id="common_member_id",
    )
    p638_entries = service.get_member_entries(
        lottery_type=LotteryType.POWER_LOTTO,
        cohort_id=p638_cohort.cohort_id,
        cohort_version=p638_cohort.cohort_version,
        member_id="common_member_id",
    )

    assert len(t539_entries) == 1
    assert t539_entries[0].identity.lottery_type is LotteryType.DAILY_539
    assert t539_entries[0].is_winner is True

    assert len(p638_entries) == 1
    assert p638_entries[0].identity.lottery_type is LotteryType.POWER_LOTTO
    assert p638_entries[0].is_winner is False


def test_prediction_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store = FileSystemForwardEvidenceLedgerStore(ledger_root)
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    cohort = _build_t539_cohort(("m_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )

    pred1 = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="m_alpha",
                selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                matched_baseline=baseline,
            ),
        ),
    )
    pred2 = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="m_alpha",
                selections=(ProspectiveSelection(main_numbers=(10, 11, 12, 13, 14)),),
                matched_baseline=baseline,
            ),
        ),
    )
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="src_1",
        source_sha256=_sha256("src_1"),
    )
    score_for_pred2 = ScoreRecord.create(
        prediction=pred2,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id="m_alpha",
                prediction_hash=pred2.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=GameEvaluation(
                    lottery_type=LotteryType.DAILY_539,
                    ticket_results=(
                        PrizeEvaluationResult(
                            lottery_type=LotteryType.DAILY_539,
                            is_winner=False,
                            prize_tier=None,
                            prize_tier_order=None,
                            zone1_hits=0,
                            zone2_hit=False,
                            prize_rule_version="v1",
                            prize_rule_provenance="prov1",
                        ),
                    ),
                    diagnostic_events=(),
                ),
            ),
        ),
        scored_at=_SCORED_AT,
    )

    with pytest.raises(ForwardEvidenceLedgerLinkError, match="prediction_hash does not match"):
        service.record_score(prediction=pred1, score=score_for_pred2)


def test_outcome_hash_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="outcome_hash does not match official outcome content"):
        OfficialOutcome(
            schema_version="1.0.0",
            lottery_type=LotteryType.DAILY_539,
            draw_number="113000101",
            draw_date=date(2099, 1, 2),
            main_numbers=(1, 2, 3, 4, 5),
            special_number=None,
            source_id="src_1",
            source_sha256=_sha256("src_1"),
            outcome_hash="f" * 64,  # corrupt outcome hash
        )


def test_score_hash_mismatch_fails_closed() -> None:
    cohort = _build_t539_cohort(("m_alpha",))
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.DAILY_539,
        baseline_id="t539_base",
        baseline_version="1.0",
        authority_sha256=_sha256("base_auth"),
        ticket_count=1,
        candidate_sizes=(5,),
    )
    pred = _create_prediction(
        cohort=cohort,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        draft_entries=(
            PredictionEntryDraft.available(
                member_id="m_alpha",
                selections=(ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),),
                matched_baseline=baseline,
            ),
        ),
    )
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number="113000101",
        draw_date=date(2099, 1, 2),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="src_1",
        source_sha256=_sha256("src_1"),
    )
    with pytest.raises(ValueError, match="score_hash does not match score record content"):
        ScoreRecord(
            schema_version="1.0.0",
            identity=pred.identity,
            prediction_hash=pred.prediction_hash,
            outcome=outcome,
            scored_at=_SCORED_AT,
            entries=(
                ScoreEntry(
                    member_id="m_alpha",
                    prediction_hash=pred.entries[0].prediction_hash,
                    availability=ScoreAvailability.SCORED,
                    evaluation=GameEvaluation(
                        lottery_type=LotteryType.DAILY_539,
                        ticket_results=(
                            PrizeEvaluationResult(
                                lottery_type=LotteryType.DAILY_539,
                                is_winner=True,
                                prize_tier="頭獎",
                                prize_tier_order=1,
                                zone1_hits=5,
                                zone2_hit=False,
                                prize_rule_version="v1",
                                prize_rule_provenance="prov1",
                            ),
                        ),
                        diagnostic_events=(),
                    ),
                ),
            ),
            score_hash="e" * 64,  # corrupt score hash
        )


def test_producer_fingerprint_drift_fails_closed() -> None:
    dep = ProducerDependency(
        locator="canonical_schedule_authority",
        source_sha256=_sha256("sched_auth"),
        load_bearing_role="SCHEDULE_AUTHORITY",
    )
    with pytest.raises(ValueError, match="digest does not match the producer fingerprint"):
        ProducerFingerprint(
            schema_version="1.0.0",
            producer_id="t539_producer",
            producer_version="1.0",
            dependencies=(dep,),
            digest="d" * 64,  # corrupt digest
        )


def test_storage_safety_no_git_ancestor() -> None:
    runtime_root = Path(
        "/Users/kelvin/LottoLab-TaskData/T539_P638_STAGE_G_FORWARD_EVIDENCE_LEDGER_R1"
    )
    curr = runtime_root
    while curr != curr.parent:
        assert not (curr / ".git").exists(), f"Discovered forbidden .git repository at {curr}"
        curr = curr.parent
