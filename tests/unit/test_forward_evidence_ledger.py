"""Unit tests for Stage G Forward Evidence Ledger domain, application, and store layers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lottolab.application.forward_evidence_ledger import (
    ForwardEvidenceLedgerAppendStatus,
    ForwardEvidenceLedgerService,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.forward_evidence_ledger import (
    FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION,
    ForwardEvidenceLedgerConflictError,
    ForwardEvidenceLedgerEntry,
    ForwardEvidenceLedgerEntryIdentity,
    ForwardEvidenceLedgerLinkError,
    LedgerTicketEvidence,
    build_member_longitudinal_summary,
)
from lottolab.domain.prize_evaluation import (
    DAILY_FIVE39_PRIZE_RULE_CONTRACT,
    PrizeEvaluationResult,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    DiagnosticEvent,
    FrozenCohortRef,
    GameEvaluation,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionAvailability,
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
    ForwardEvidenceLedgerStoreCorruptionError,
)

_NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)
_SCORED_AT = datetime(2026, 8, 31, 22, 0, 0, tzinfo=UTC)


def _sha256(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def _make_t539_prediction_and_score(
    *,
    draw_number: str = "113000001",
    draw_date: date = date(2026, 9, 1),
    member_id: str = "member_alpha",
    unavailable: bool = False,
    selections: tuple[ProspectiveSelection, ...] | None = None,
    outcome_main: tuple[int, ...] = (1, 2, 3, 4, 5),
    outcome_special: int | None = None,
) -> tuple[PredictionRecord, ScoreRecord]:
    cohort = FrozenCohortRef(
        lottery_type=LotteryType.DAILY_539,
        cohort_id="t539_cohort_v1",
        cohort_version="1.0",
        authority_sha256=_sha256("t539_cohort_auth"),
        frozen_at=datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC),
        member_ids=(member_id,),
        checkpoint_sizes=(1, 5),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )
    dep = ProducerDependency(
        locator="canonical_schedule_authority",
        source_sha256=_sha256("sched_auth"),
        load_bearing_role="SCHEDULE_AUTHORITY",
    )
    fingerprint = ProducerFingerprint.create(
        producer_id="t539_producer",
        producer_version="1.0",
        dependencies=(dep,),
    )
    causal = CausalHistoryRef(
        draw_count=100,
        last_draw_number="113000000",
        last_draw_date=date(2026, 8, 31),
        history_sha256=_sha256("t539_causal_history"),
    )
    obs_target = ObservationTarget(
        lottery_type=LotteryType.DAILY_539,
        draw_number=draw_number,
        draw_date=draw_date,
    )
    context = PredictionContext(
        target=obs_target,
        cohort=cohort,
        producer_fingerprint=fingerprint,
        causal_history=causal,
    )
    request = PredictionPhaseRequest(
        context=context,
        outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
    )

    if unavailable:
        draft = PredictionDraft(
            entries=(
                PredictionEntryDraft.unavailable(
                    member_id=member_id,
                    reason="Insufficient history for strategy warmup",
                ),
            )
        )
    else:
        actual_selections = selections or (
            ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5)),
            ProspectiveSelection(main_numbers=(6, 7, 8, 9, 10)),
        )
        baseline = MatchedBaselineRef(
            lottery_type=LotteryType.DAILY_539,
            baseline_id="t539_random_baseline",
            baseline_version="1.0",
            authority_sha256=_sha256("t539_baseline_auth"),
            ticket_count=len(actual_selections),
            candidate_sizes=tuple(len(s.main_numbers) for s in actual_selections),
        )
        draft = PredictionDraft(
            entries=(
                PredictionEntryDraft.available(
                    member_id=member_id,
                    selections=actual_selections,
                    matched_baseline=baseline,
                ),
            )
        )

    prediction = PredictionRecord.create(
        request=request,
        draft=draft,
        predicted_at=_NOW,
    )

    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=outcome_main,
        special_number=outcome_special,
        source_id="synthetic_t539_source",
        source_sha256=_sha256("synthetic_t539_source_sha"),
    )

    pred_entry = prediction.entries[0]
    if pred_entry.availability is PredictionAvailability.UNAVAILABLE:
        score_entries = (
            ScoreEntry(
                member_id=member_id,
                prediction_hash=pred_entry.prediction_hash,
                availability=ScoreAvailability.UNAVAILABLE_PREDICTION,
                evaluation=None,
            ),
        )
    else:
        ticket_results: list[PrizeEvaluationResult] = []
        for sel in pred_entry.selections:
            hits = len(set(sel.main_numbers) & set(outcome.main_numbers))
            tier = DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=hits)
            ticket_results.append(
                PrizeEvaluationResult(
                    lottery_type=LotteryType.DAILY_539,
                    is_winner=tier is not None,
                    prize_tier=tier.official_label if tier else None,
                    prize_tier_order=tier.tier_order if tier else None,
                    zone1_hits=hits,
                    zone2_hit=False,
                    prize_rule_version=DAILY_FIVE39_PRIZE_RULE_CONTRACT.schema_version,
                    prize_rule_provenance=DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_locator,
                )
            )
        has_jackpot = any(r.zone1_hits == 5 for r in ticket_results)
        evaluation = GameEvaluation(
            lottery_type=LotteryType.DAILY_539,
            ticket_results=tuple(ticket_results),
            diagnostic_events=(
                DiagnosticEvent(name="HAS_ZONE1_JACKPOT_HIT", occurred=has_jackpot),
            ),
        )
        score_entries = (
            ScoreEntry(
                member_id=member_id,
                prediction_hash=pred_entry.prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=evaluation,
            ),
        )

    score = ScoreRecord.create(
        prediction=prediction,
        outcome=outcome,
        entries=score_entries,
        scored_at=_SCORED_AT,
    )
    return prediction, score


def test_forward_evidence_ledger_entry_identity_validation() -> None:
    ident = ForwardEvidenceLedgerEntryIdentity(
        lottery_type=LotteryType.DAILY_539,
        cohort_id="c1",
        cohort_version="1.0",
        member_id="m1",
        target_draw_date=date(2026, 9, 1),
        target_draw_number="113000001",
    )
    assert ident.lottery_type is LotteryType.DAILY_539
    assert ident.cohort_id == "c1"
    assert ident.member_id == "m1"
    assert ident.canonical_dict() == {
        "cohort_id": "c1",
        "cohort_version": "1.0",
        "lottery_type": "DAILY_539",
        "member_id": "m1",
        "target_draw_date": "2026-09-01",
        "target_draw_number": "113000001",
    }

    with pytest.raises(ValueError, match="lottery_type"):
        ForwardEvidenceLedgerEntryIdentity(
            lottery_type="DAILY_539",  # type: ignore[arg-type]
            cohort_id="c1",
            cohort_version="1.0",
            member_id="m1",
            target_draw_date=date(2026, 9, 1),
            target_draw_number="113000001",
        )

    with pytest.raises(ValueError, match="target_draw_number"):
        ForwardEvidenceLedgerEntryIdentity(
            lottery_type=LotteryType.DAILY_539,
            cohort_id="c1",
            cohort_version="1.0",
            member_id="m1",
            target_draw_date=date(2026, 9, 1),
            target_draw_number="invalid-draw-term",
        )


def test_ledger_ticket_evidence_validation() -> None:
    ticket = LedgerTicketEvidence(
        selection_index=0,
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        zone1_hits=5,
        zone2_hit=False,
        prize_tier="頭獎",
        prize_tier_order=1,
        is_winner=True,
    )
    assert ticket.is_winner is True
    assert ticket.prize_tier == "頭獎"

    # Non-winning ticket cannot claim is_winner=True
    with pytest.raises(ValueError, match="winning prize_tier requires is_winner=True"):
        LedgerTicketEvidence(
            selection_index=0,
            main_numbers=(1, 2, 3, 4, 5),
            special_number=None,
            zone1_hits=1,
            zone2_hit=False,
            prize_tier="頭獎",
            prize_tier_order=1,
            is_winner=False,
        )

    # Unsorted main numbers fail closed
    with pytest.raises(ValueError, match="main_numbers must be unique"):
        LedgerTicketEvidence(
            selection_index=0,
            main_numbers=(5, 4, 3, 2, 1),
            special_number=None,
            zone1_hits=0,
            zone2_hit=False,
            prize_tier=None,
            prize_tier_order=None,
            is_winner=False,
        )


def test_forward_evidence_ledger_entry_from_records_available() -> None:
    pred, score = _make_t539_prediction_and_score()
    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred,
        score=score,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )

    assert entry.schema_version == FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION
    assert entry.identity.member_id == "member_alpha"
    assert entry.identity.target_draw_number == "113000001"
    assert entry.prediction_hash == pred.prediction_hash
    assert entry.outcome_hash == score.outcome.outcome_hash
    assert entry.score_hash == score.score_hash
    assert entry.availability is ScoreAvailability.SCORED
    assert entry.unavailable_reason is None
    assert entry.is_winner is True
    assert len(entry.tickets) == 2
    assert entry.tickets[0].selection_index == 0
    assert entry.tickets[0].zone1_hits == 5
    assert entry.tickets[0].is_winner is True
    assert entry.tickets[1].selection_index == 1
    assert entry.tickets[1].zone1_hits == 0
    assert entry.tickets[1].is_winner is False
    assert entry.prize_rule_version == DAILY_FIVE39_PRIZE_RULE_CONTRACT.schema_version
    assert entry.prize_rule_provenance == DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_locator
    assert entry.matched_baseline_id == "t539_random_baseline"


def test_forward_evidence_ledger_entry_from_records_unavailable() -> None:
    pred, score = _make_t539_prediction_and_score(unavailable=True)
    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred,
        score=score,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )

    assert entry.availability is ScoreAvailability.UNAVAILABLE_PREDICTION
    assert entry.unavailable_reason == "Insufficient history for strategy warmup"
    assert entry.is_winner is None
    assert entry.tickets == ()
    assert entry.prize_rule_version is None
    assert entry.prize_rule_provenance is None
    assert entry.matched_baseline_id is None


def test_forward_evidence_ledger_entry_mismatch_link_error() -> None:
    pred1, _ = _make_t539_prediction_and_score(draw_number="113000001")
    _, score2 = _make_t539_prediction_and_score(draw_number="113000002")

    with pytest.raises(ForwardEvidenceLedgerLinkError, match="prediction_hash does not match"):
        ForwardEvidenceLedgerEntry.from_records(
            prediction=pred1,
            score=score2,
            member_id="member_alpha",
            entry_created_at=_SCORED_AT,
        )


def test_member_longitudinal_summary_aggregation() -> None:
    pred1, score1 = _make_t539_prediction_and_score(
        draw_number="113000001",
        draw_date=date(2026, 9, 1),
        outcome_main=(1, 2, 3, 4, 5),  # ticket 0 hits 5 (win)
    )
    pred2, score2 = _make_t539_prediction_and_score(
        draw_number="113000002",
        draw_date=date(2026, 9, 2),
        outcome_main=(21, 22, 23, 24, 25),  # ticket 0 hits 0, ticket 1 hits 0 (loss)
    )
    pred3, score3 = _make_t539_prediction_and_score(
        draw_number="113000003",
        draw_date=date(2026, 9, 3),
        unavailable=True,  # unavailable (not a win, not a loss)
    )

    e1 = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred1, score=score1, member_id="member_alpha", entry_created_at=_SCORED_AT
    )
    e2 = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred2, score=score2, member_id="member_alpha", entry_created_at=_SCORED_AT
    )
    e3 = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred3, score=score3, member_id="member_alpha", entry_created_at=_SCORED_AT
    )

    summary = build_member_longitudinal_summary((e2, e1, e3))  # deliberately unordered input

    assert summary.member_id == "member_alpha"
    assert summary.total_entries == 3
    assert summary.scored_count == 2
    assert summary.unavailable_count == 1
    assert summary.winning_count == 1
    assert summary.nonwinning_count == 1
    assert summary.total_tickets_evaluated == 4
    assert summary.winning_tickets_count == 1
    assert summary.prize_tier_counts == {"頭獎": 1}
    assert summary.first_draw_date == date(2026, 9, 1)
    assert summary.last_draw_date == date(2026, 9, 3)
    assert summary.first_draw_number == "113000001"
    assert summary.last_draw_number == "113000003"


def test_file_system_forward_evidence_ledger_store(tmp_path: Path) -> None:
    store = FileSystemForwardEvidenceLedgerStore(tmp_path / "ledger_root")
    pred, score = _make_t539_prediction_and_score()
    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred,
        score=score,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )

    # 1. Insertion
    res1 = store.create_entry(entry)
    assert res1 is CreateOnceOutcome.INSERTED

    # 2. Get entry
    retrieved = store.get_entry(entry.identity)
    assert retrieved is not None
    assert retrieved.ledger_entry_hash == entry.ledger_entry_hash
    assert retrieved.canonical_dict() == entry.canonical_dict()

    # 3. Exact duplicate idempotent replay
    res2 = store.create_entry(entry)
    assert res2 is CreateOnceOutcome.ALREADY_PRESENT

    # 4. List member entries
    member_entries = store.list_member_entries(
        lottery_type=entry.identity.lottery_type,
        cohort_id=entry.identity.cohort_id,
        cohort_version=entry.identity.cohort_version,
        member_id=entry.identity.member_id,
    )
    assert len(member_entries) == 1
    assert member_entries[0].ledger_entry_hash == entry.ledger_entry_hash

    # 5. List cohort entries
    cohort_entries = store.list_cohort_entries(
        lottery_type=entry.identity.lottery_type,
        cohort_id=entry.identity.cohort_id,
        cohort_version=entry.identity.cohort_version,
    )
    assert len(cohort_entries) == 1
    assert cohort_entries[0].ledger_entry_hash == entry.ledger_entry_hash


def test_file_system_forward_evidence_ledger_store_conflict(tmp_path: Path) -> None:
    store = FileSystemForwardEvidenceLedgerStore(tmp_path / "ledger_root")
    pred1, score1 = _make_t539_prediction_and_score(outcome_main=(1, 2, 3, 4, 5))
    pred2, score2 = _make_t539_prediction_and_score(outcome_main=(11, 12, 13, 14, 15))

    entry1 = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred1,
        score=score1,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )
    entry2 = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred2,
        score=score2,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )

    assert entry1.identity == entry2.identity
    assert entry1.ledger_entry_hash != entry2.ledger_entry_hash

    res1 = store.create_entry(entry1)
    assert res1 is CreateOnceOutcome.INSERTED

    res2 = store.create_entry(entry2)
    assert res2 is CreateOnceOutcome.CONFLICT


def test_forward_evidence_ledger_service_orchestration(tmp_path: Path) -> None:
    store = FileSystemForwardEvidenceLedgerStore(tmp_path / "ledger_root")
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    pred, score = _make_t539_prediction_and_score()

    # 1. Record score
    results = service.record_score(prediction=pred, score=score)
    assert len(results) == 1
    assert results[0].status is ForwardEvidenceLedgerAppendStatus.APPENDED
    assert results[0].entry.identity.member_id == "member_alpha"

    # 2. Re-record exact score (idempotent no-op)
    replay_results = service.record_score(prediction=pred, score=score)
    assert len(replay_results) == 1
    assert replay_results[0].status is ForwardEvidenceLedgerAppendStatus.EXACT_IDEMPOTENT_NO_OP

    # 3. Summarize member
    summary = service.summarize_member(
        lottery_type=LotteryType.DAILY_539,
        cohort_id="t539_cohort_v1",
        cohort_version="1.0",
        member_id="member_alpha",
    )
    assert summary is not None
    assert summary.total_entries == 1
    assert summary.scored_count == 1
    assert summary.winning_count == 1

    # 4. Non-existent member summary returns None
    assert (
        service.summarize_member(
            lottery_type=LotteryType.DAILY_539,
            cohort_id="t539_cohort_v1",
            cohort_version="1.0",
            member_id="non_existent",
        )
        is None
    )


def test_forward_evidence_ledger_service_conflict_raises(tmp_path: Path) -> None:
    store = FileSystemForwardEvidenceLedgerStore(tmp_path / "ledger_root")
    service = ForwardEvidenceLedgerService(store=store, clock=lambda: _SCORED_AT)

    pred1, score1 = _make_t539_prediction_and_score(outcome_main=(1, 2, 3, 4, 5))
    pred2, score2 = _make_t539_prediction_and_score(outcome_main=(11, 12, 13, 14, 15))

    service.record_score(prediction=pred1, score=score1)

    with pytest.raises(ForwardEvidenceLedgerConflictError, match="Conflicting forward evidence"):
        service.record_score(prediction=pred2, score=score2)


def test_file_system_forward_evidence_ledger_store_corruption(tmp_path: Path) -> None:
    store = FileSystemForwardEvidenceLedgerStore(tmp_path / "ledger_root")
    pred, score = _make_t539_prediction_and_score()
    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred,
        score=score,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )
    store.create_entry(entry)

    # Corrupt the persisted file
    entry_path = store.entry_path(entry.identity)
    with open(entry_path, encoding="utf-8") as f:
        data = json.load(f)

    # Tamper with envelope hash
    data["envelope_sha256"] = "0" * 64
    with open(entry_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ForwardEvidenceLedgerStoreCorruptionError, match="corrupt ledger entry"):
        store.get_entry(entry.identity)


def test_forward_evidence_ledger_entry_hash_verification() -> None:
    pred, score = _make_t539_prediction_and_score()
    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=pred,
        score=score,
        member_id="member_alpha",
        entry_created_at=_SCORED_AT,
    )

    # Modify ledger_entry_hash to trigger validation error
    with pytest.raises(ValueError, match="ledger_entry_hash does not match canonical material"):
        ForwardEvidenceLedgerEntry(
            schema_version=entry.schema_version,
            identity=entry.identity,
            prediction_hash=entry.prediction_hash,
            outcome_hash=entry.outcome_hash,
            score_hash=entry.score_hash,
            producer_fingerprint_digest=entry.producer_fingerprint_digest,
            cohort_authority_sha256=entry.cohort_authority_sha256,
            temporal_provenance=entry.temporal_provenance,
            availability=entry.availability,
            unavailable_reason=entry.unavailable_reason,
            matched_baseline_id=entry.matched_baseline_id,
            prize_rule_version=entry.prize_rule_version,
            prize_rule_provenance=entry.prize_rule_provenance,
            tickets=entry.tickets,
            diagnostic_events=entry.diagnostic_events,
            is_winner=entry.is_winner,
            entry_created_at=entry.entry_created_at,
            ledger_entry_hash="a" * 64,  # invalid hash
        )
