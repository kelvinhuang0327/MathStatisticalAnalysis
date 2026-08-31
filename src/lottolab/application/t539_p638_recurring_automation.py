"""Deterministic recurring automation orchestration for T539 and P638.

Repeatedly composes:
  Stage A canonical schedule authority
  -> Stage C pre-draw prediction seal
  -> Stage E exact result join
  -> Stage G append-only forward evidence ledger
across consecutive simulated draw cycles.

Enforces:
- Strict canonical cycle target identity (lottery_type, draw_number, draw_date)
- Scheduled_at timing constraints (no arithmetic draw derivation)
- Complete game isolation between DAILY_539 and POWER_LOTTO
- Resumable state machine and restart recovery across all stage boundaries
- Idempotent no-op on redundant completed wakes
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path

from lottolab.application.forward_evidence_ledger import (
    ForwardEvidenceLedgerAppendResult,
    ForwardEvidenceLedgerService,
)
from lottolab.application.ports import FutureDrawIdentityReader
from lottolab.application.prospective_observer import ProspectiveObservationStore
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealResult,
    RunnablePredictionSealService,
    RunnablePredictionSealStatus,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinResult,
    ProspectiveResultJoinService,
    ProspectiveResultJoinStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    ObservationTarget,
    PredictionRecord,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ScoreRecord,
)

_SUPPORTED_LOTTERIES = frozenset({LotteryType.DAILY_539, LotteryType.POWER_LOTTO})


class RecurringAutomationError(RuntimeError):
    """Base class for recurring automation errors."""


class RecurringCycleCausalityError(RecurringAutomationError):
    """Operation violated cycle timing or causality constraints."""


class RecurringCycleConflictError(RecurringAutomationError):
    """Conflicting schedule, prediction, score, or ledger evidence detected."""


class RecurringCycleState(StrEnum):
    """State model for a recurring automation draw cycle."""

    AWAITING_SCHEDULE = "AWAITING_SCHEDULE"
    PRE_DRAW_SEAL_COMPLETED = "PRE_DRAW_SEAL_COMPLETED"
    AWAITING_OFFICIAL_OUTCOME = "AWAITING_OFFICIAL_OUTCOME"
    POST_DRAW_JOIN_COMPLETED = "POST_DRAW_JOIN_COMPLETED"
    EVIDENCE_LEDGER_APPENDED = "EVIDENCE_LEDGER_APPENDED"
    CYCLE_ADVANCED = "CYCLE_ADVANCED"


@dataclass(frozen=True, slots=True)
class CanonicalCycleTarget:
    """Canonical cycle target derived strictly from Stage A schedule authority."""

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    scheduled_at: datetime

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if self.lottery_type not in _SUPPORTED_LOTTERIES:
            raise ValueError(f"Unsupported lottery type for Stage H: {self.lottery_type}")
        if type(self.draw_number) is not str or not self.draw_number:
            raise ValueError("draw_number must be non-empty text")
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")
        if type(self.scheduled_at) is not datetime or self.scheduled_at.tzinfo is None:
            raise ValueError("scheduled_at must be a timezone-aware datetime")

    @property
    def observation_target(self) -> ObservationTarget:
        return ObservationTarget(
            lottery_type=self.lottery_type,
            draw_number=self.draw_number,
            draw_date=self.draw_date,
        )


@dataclass(frozen=True, slots=True)
class SingleGameCycleResult:
    """Observable outcome of executing one game's recurring automation wake."""

    lottery_type: LotteryType
    target: CanonicalCycleTarget | None
    state: RecurringCycleState
    seal_result: RunnablePredictionSealResult | None
    join_result: ProspectiveResultJoinResult | None
    ledger_results: tuple[ForwardEvidenceLedgerAppendResult, ...]
    error: str | None
    cycle_action: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.state) is not RecurringCycleState:
            raise ValueError("state must be a RecurringCycleState")
        if type(self.cycle_action) is not str:
            raise ValueError("cycle_action must be a string")


@dataclass(frozen=True, slots=True)
class RecurringAutomationCycleResult:
    """Observable multi-game cycle result for T539 and P638."""

    as_of: datetime
    game_results: Mapping[LotteryType, SingleGameCycleResult]

    @property
    def t539(self) -> SingleGameCycleResult | None:
        return self.game_results.get(LotteryType.DAILY_539)

    @property
    def p638(self) -> SingleGameCycleResult | None:
        return self.game_results.get(LotteryType.POWER_LOTTO)


class SingleGameRecurringRunner:
    """Deterministic recurring automation runner for a single configured lottery."""

    def __init__(
        self,
        *,
        lottery_type: LotteryType,
        future_draw_reader: FutureDrawIdentityReader,
        seal_service: RunnablePredictionSealService,
        prediction_store: ProspectiveObservationStore,
        join_service: ProspectiveResultJoinService,
        ledger_service: ForwardEvidenceLedgerService,
        cohort: FrozenCohortRef,
        base_producer_fingerprint: ProducerFingerprint,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if type(lottery_type) is not LotteryType or lottery_type not in _SUPPORTED_LOTTERIES:
            raise ValueError("SingleGameRecurringRunner supports only DAILY_539 and POWER_LOTTO")
        if cohort.lottery_type is not lottery_type:
            raise ValueError("cohort lottery_type does not match configured runner")

        self._lottery_type = lottery_type
        self._future_draw_reader = future_draw_reader
        self._seal_service = seal_service
        self._prediction_store = prediction_store
        self._join_service = join_service
        self._ledger_service = ledger_service
        self._cohort = cohort
        self._base_producer_fingerprint = base_producer_fingerprint
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def lottery_type(self) -> LotteryType:
        return self._lottery_type

    @property
    def cohort(self) -> FrozenCohortRef:
        return self._cohort

    def identity_for_target(self, target: CanonicalCycleTarget) -> ProspectiveObservationIdentity:
        """Construct the ProspectiveObservationIdentity for a canonical target under this cohort."""
        return ProspectiveObservationIdentity(
            lottery_type=self._lottery_type,
            cohort_id=self._cohort.cohort_id,
            cohort_version=self._cohort.cohort_version,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
        )

    def resolve_canonical_target(
        self, as_of: datetime | None = None
    ) -> CanonicalCycleTarget | None:
        """Resolve the active canonical target (pending in-flight or earliest unpopulated)."""
        now = self._require_utc(as_of or self._clock())

        # Phase A: Check if any sealed prediction for this cohort is pending
        # result join or ledger append.
        pending_target = self._find_pending_unrecorded_target()
        if pending_target is not None:
            return pending_target

        # Phase B: First check unpopulated targets already due (scheduled_at <= now)
        due_record = self._future_draw_reader.find_earliest_unpopulated_due(self._lottery_type, now)
        if due_record is not None:
            announcement = due_record.announcement
            return CanonicalCycleTarget(
                lottery_type=self._lottery_type,
                draw_number=announcement.target.draw_number,
                draw_date=announcement.target.draw_date,
                scheduled_at=announcement.scheduled_at,
            )

        # Phase C: Next check unpopulated targets in future (scheduled_at > now)
        future_record = self._future_draw_reader.find_earliest_unpopulated_future(
            self._lottery_type, now
        )
        if future_record is not None:
            announcement = future_record.announcement
            return CanonicalCycleTarget(
                lottery_type=self._lottery_type,
                draw_number=announcement.target.draw_number,
                draw_date=announcement.target.draw_date,
                scheduled_at=announcement.scheduled_at,
            )

        return None

    def _find_pending_unrecorded_target(self) -> CanonicalCycleTarget | None:
        """Find any sealed prediction for this cohort that has not completed ledger append."""
        recorded_entries = self._ledger_service.get_cohort_entries(
            self._lottery_type,
            self._cohort.cohort_id,
            self._cohort.cohort_version,
        )
        recorded_draws = {e.identity.target_draw_number for e in recorded_entries}

        store_root = getattr(self._prediction_store, "root", None)
        if store_root is not None and isinstance(store_root, Path):
            game_dir = store_root / self._lottery_type.value.lower()
            if game_dir.is_dir():
                pending_targets: list[CanonicalCycleTarget] = []
                for pred_file in game_dir.glob("cohort-*/target-*/prediction.json"):
                    if pred_file.is_file():
                        try:
                            envelope = json.loads(pred_file.read_text(encoding="utf-8"))
                            rec_json = envelope.get("record", {})
                            ident_json = rec_json.get("identity", {})
                            if (
                                ident_json.get("cohort_id") != self._cohort.cohort_id
                                or ident_json.get("cohort_version") != self._cohort.cohort_version
                            ):
                                continue
                            draw_num = ident_json.get("target_draw_number")
                            draw_date_str = ident_json.get("target_draw_date")
                            if draw_num and draw_num not in recorded_draws and draw_date_str:
                                sched_rec = self._future_draw_reader.get_scheduled_draw(
                                    self._lottery_type, draw_num
                                )
                                if sched_rec is not None:
                                    pending_targets.append(
                                        CanonicalCycleTarget(
                                            lottery_type=self._lottery_type,
                                            draw_number=sched_rec.announcement.target.draw_number,
                                            draw_date=sched_rec.announcement.target.draw_date,
                                            scheduled_at=sched_rec.announcement.scheduled_at,
                                        )
                                    )
                        except Exception:
                            continue
                if pending_targets:
                    pending_targets.sort(
                        key=lambda t: (
                            t.draw_date,
                            int(t.draw_number) if t.draw_number.isdigit() else 0,
                        )
                    )
                    return pending_targets[0]
        return None

    def inspect_state(
        self,
        target: CanonicalCycleTarget,
        as_of: datetime | None = None,
    ) -> RecurringCycleState:
        """Inspect the exact observable cycle state for a target."""
        now = self._require_utc(as_of or self._clock())
        identity = self.identity_for_target(target)

        prediction = self._prediction_store.get_prediction(identity)
        if prediction is None:
            return RecurringCycleState.AWAITING_SCHEDULE

        score = self._prediction_store.get_score(identity)
        if score is None:
            if now < target.scheduled_at:
                return RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
            return RecurringCycleState.AWAITING_OFFICIAL_OUTCOME

        # Check if ledger entries exist for all cohort members
        existing_entries = self._ledger_service.get_cohort_entries(
            self._lottery_type,
            self._cohort.cohort_id,
            self._cohort.cohort_version,
        )
        target_draw_numbers = {e.identity.target_draw_number for e in existing_entries}
        if target.draw_number in target_draw_numbers:
            return RecurringCycleState.EVIDENCE_LEDGER_APPENDED

        return RecurringCycleState.POST_DRAW_JOIN_COMPLETED

    def run_wake(
        self,
        as_of: datetime | None = None,
        target: CanonicalCycleTarget | None = None,
    ) -> SingleGameCycleResult:
        """Execute one deterministic wake cycle for this lottery game."""
        now = self._require_utc(as_of or self._clock())

        resolved_target = target or self.resolve_canonical_target(now)
        if resolved_target is None:
            return SingleGameCycleResult(
                lottery_type=self._lottery_type,
                target=None,
                state=RecurringCycleState.AWAITING_SCHEDULE,
                seal_result=None,
                join_result=None,
                ledger_results=(),
                error=None,
                cycle_action="AWAITING_SCHEDULE",
            )

        identity = self.identity_for_target(resolved_target)
        existing_prediction: PredictionRecord | None = self._prediction_store.get_prediction(
            identity
        )
        existing_score: ScoreRecord | None = self._prediction_store.get_score(identity)

        seal_result: RunnablePredictionSealResult | None = None
        join_result: ProspectiveResultJoinResult | None = None
        ledger_results: tuple[ForwardEvidenceLedgerAppendResult, ...] = ()

        # -------------------------------------------------------------
        # Phase 1: Pre-Draw Prediction Sealing (Stage C)
        # -------------------------------------------------------------
        if existing_prediction is None:
            if now >= resolved_target.scheduled_at:
                # Prediction window expired; fail closed without generating retroactive prediction
                return SingleGameCycleResult(
                    lottery_type=self._lottery_type,
                    target=resolved_target,
                    state=RecurringCycleState.AWAITING_OFFICIAL_OUTCOME,
                    seal_result=None,
                    join_result=None,
                    ledger_results=(),
                    error="PREDICTION_WINDOW_EXPIRED",
                    cycle_action="UNSEALED_TARGET_PAST_SCHEDULED_AT",
                )

            # Clock is before scheduled_at; attempt pre-draw seal
            seal_result = self._seal_service.seal_earliest()
            if seal_result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET:
                return SingleGameCycleResult(
                    lottery_type=self._lottery_type,
                    target=resolved_target,
                    state=RecurringCycleState.AWAITING_SCHEDULE,
                    seal_result=seal_result,
                    join_result=None,
                    ledger_results=(),
                    error=None,
                    cycle_action="NO_RUNNABLE_TARGET",
                )

            active_prediction = seal_result.prediction
            assert active_prediction is not None
        else:
            active_prediction = existing_prediction

        # -------------------------------------------------------------
        # Phase 2: Post-Draw Result Join & Scoring (Stage E)
        # -------------------------------------------------------------
        if existing_score is None:
            join_result = self._join_service.join_result(
                active_prediction.identity,
                active_prediction.producer_fingerprint,
            )

            if join_result.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE:
                # Outcome is absent
                state = (
                    RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
                    if now < resolved_target.scheduled_at
                    else RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
                )
                action = (
                    "PRE_DRAW_SEAL_COMPLETED"
                    if seal_result is not None
                    else "AWAITING_OFFICIAL_OUTCOME"
                )
                return SingleGameCycleResult(
                    lottery_type=self._lottery_type,
                    target=resolved_target,
                    state=state,
                    seal_result=seal_result,
                    join_result=join_result,
                    ledger_results=(),
                    error=None,
                    cycle_action=action,
                )

            active_score = join_result.score
            assert active_score is not None
        else:
            active_score = existing_score
            join_result = ProspectiveResultJoinResult(
                status=ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP,
                lottery_type=self._lottery_type,
                identity=identity,
                outcome=active_score.outcome,
                score=active_score,
            )

        # -------------------------------------------------------------
        # Phase 3: Forward Evidence Ledger Append (Stage G)
        # -------------------------------------------------------------
        ledger_results = self._ledger_service.record_score(
            prediction=active_prediction,
            score=active_score,
        )

        all_idempotent = all(
            r.status.name == "EXACT_IDEMPOTENT_NO_OP" for r in ledger_results
        ) and (existing_prediction is not None and existing_score is not None)

        action = (
            "REDUNDANT_WAKE_IDEMPOTENT_NO_OP"
            if all_idempotent
            else "POST_DRAW_JOIN_AND_EVIDENCE_APPENDED"
        )

        return SingleGameCycleResult(
            lottery_type=self._lottery_type,
            target=resolved_target,
            state=RecurringCycleState.EVIDENCE_LEDGER_APPENDED,
            seal_result=seal_result,
            join_result=join_result,
            ledger_results=ledger_results,
            error=None,
            cycle_action=action,
        )

    def _require_utc(self, value: datetime) -> datetime:
        if type(value) is not datetime or value.tzinfo is None or value.tzinfo is not UTC:
            raise RecurringCycleCausalityError(
                "Recurring automation clock must return a timezone-aware UTC datetime"
            )
        return value


class T539P638RecurringAutomationService:
    """Multi-game recurring automation coordinator for T539 and P638 with strict isolation."""

    def __init__(
        self,
        runners: Mapping[LotteryType, SingleGameRecurringRunner],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._runners = dict(runners)
        for lottery_type in _SUPPORTED_LOTTERIES:
            if lottery_type not in self._runners:
                raise ValueError(f"Runner missing for supported lottery: {lottery_type}")
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_runner(self, lottery_type: LotteryType) -> SingleGameRecurringRunner:
        runner = self._runners.get(lottery_type)
        if runner is None:
            raise ValueError(f"Unsupported lottery type: {lottery_type}")
        return runner

    def run_game_wake(
        self,
        lottery_type: LotteryType,
        as_of: datetime | None = None,
        target: CanonicalCycleTarget | None = None,
    ) -> SingleGameCycleResult:
        """Run a wake cycle for a specific lottery game."""
        runner = self.get_runner(lottery_type)
        return runner.run_wake(as_of=as_of, target=target)

    def run_cycle_wake(
        self,
        as_of: datetime | None = None,
    ) -> RecurringAutomationCycleResult:
        """Run isolated wake cycles across all configured games (T539 and P638)."""
        now = as_of or self._clock()
        results: dict[LotteryType, SingleGameCycleResult] = {}

        for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
            runner = self._runners[lottery_type]
            try:
                results[lottery_type] = runner.run_wake(as_of=now)
            except Exception as exc:
                # Capture game failure isolated to this game
                results[lottery_type] = SingleGameCycleResult(
                    lottery_type=lottery_type,
                    target=None,
                    state=RecurringCycleState.AWAITING_SCHEDULE,
                    seal_result=None,
                    join_result=None,
                    ledger_results=(),
                    error=f"{type(exc).__name__}: {exc}",
                    cycle_action="GAME_CYCLE_ERROR",
                )

        return RecurringAutomationCycleResult(
            as_of=now,
            game_results=results,
        )


__all__ = [
    "CanonicalCycleTarget",
    "RecurringAutomationCycleResult",
    "RecurringAutomationError",
    "RecurringCycleCausalityError",
    "RecurringCycleConflictError",
    "RecurringCycleState",
    "SingleGameCycleResult",
    "SingleGameRecurringRunner",
    "T539P638RecurringAutomationService",
]
