"""Application services and orchestration for forward evidence ledgers.

Consumes sealed Stage C PredictionRecord and Stage E ScoreRecord instances,
appends deterministic ForwardEvidenceLedgerEntry records into durable storage,
and exposes longitudinal query and summary capabilities without introducing
promotion policies or ranking thresholds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.forward_evidence_ledger import (
    ForwardEvidenceLedgerConflictError,
    ForwardEvidenceLedgerEntry,
    ForwardEvidenceLedgerEntryIdentity,
    ForwardEvidenceLedgerError,
    MemberLongitudinalEvidenceSummary,
    build_member_longitudinal_summary,
)
from lottolab.domain.prospective_observer import (
    CreateOnceOutcome,
    PredictionRecord,
    ScoreRecord,
)


class ForwardEvidenceLedgerAppendStatus(StrEnum):
    APPENDED = "APPENDED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"


@dataclass(frozen=True, slots=True)
class ForwardEvidenceLedgerAppendResult:
    """Outcome of attempting to append one member's evidence to the ledger."""

    status: ForwardEvidenceLedgerAppendStatus
    entry: ForwardEvidenceLedgerEntry

    def __post_init__(self) -> None:
        if type(self.status) is not ForwardEvidenceLedgerAppendStatus:
            raise ValueError("status must be a ForwardEvidenceLedgerAppendStatus")
        if type(self.entry) is not ForwardEvidenceLedgerEntry:
            raise ValueError("entry must be a ForwardEvidenceLedgerEntry")


@runtime_checkable
class ForwardEvidenceLedgerStore(Protocol):
    """Create-once durable ledger storage protocol."""

    def get_entry(
        self,
        identity: ForwardEvidenceLedgerEntryIdentity,
    ) -> ForwardEvidenceLedgerEntry | None: ...

    def create_entry(self, entry: ForwardEvidenceLedgerEntry) -> CreateOnceOutcome: ...

    def list_member_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
        member_id: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]: ...

    def list_cohort_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]: ...


class ForwardEvidenceLedgerService:
    """Application service managing forward evidence ledger entry creation and summaries."""

    def __init__(
        self,
        store: ForwardEvidenceLedgerStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def store(self) -> ForwardEvidenceLedgerStore:
        return self._store

    def record_score(
        self,
        *,
        prediction: PredictionRecord,
        score: ScoreRecord,
    ) -> tuple[ForwardEvidenceLedgerAppendResult, ...]:
        """Record forward evidence for all cohort members from sealed records."""
        now = self._clock()
        results: list[ForwardEvidenceLedgerAppendResult] = []

        for member_id in prediction.cohort.member_ids:
            entry = ForwardEvidenceLedgerEntry.from_records(
                prediction=prediction,
                score=score,
                member_id=member_id,
                entry_created_at=now,
            )
            outcome = self._store.create_entry(entry)
            if outcome is CreateOnceOutcome.INSERTED:
                results.append(
                    ForwardEvidenceLedgerAppendResult(
                        status=ForwardEvidenceLedgerAppendStatus.APPENDED,
                        entry=entry,
                    )
                )
            elif outcome is CreateOnceOutcome.ALREADY_PRESENT:
                results.append(
                    ForwardEvidenceLedgerAppendResult(
                        status=ForwardEvidenceLedgerAppendStatus.EXACT_IDEMPOTENT_NO_OP,
                        entry=entry,
                    )
                )
            elif outcome is CreateOnceOutcome.CONFLICT:
                draw_num = entry.identity.target_draw_number
                draw_dt = entry.identity.target_draw_date
                raise ForwardEvidenceLedgerConflictError(
                    f"Conflicting forward evidence for '{member_id}' at {draw_num} ({draw_dt})"
                )
            else:
                raise ForwardEvidenceLedgerError(f"Unexpected store outcome: {outcome}")

        return tuple(results)

    def record_stage_e_result(
        self,
        *,
        result: ProspectiveResultJoinResult,
        prediction: PredictionRecord,
    ) -> tuple[ForwardEvidenceLedgerAppendResult, ...]:
        """Record forward evidence from a completed Stage E ProspectiveResultJoinResult."""
        if type(result) is not ProspectiveResultJoinResult:
            raise ValueError("result must be a ProspectiveResultJoinResult")
        if result.score is None:
            raise ForwardEvidenceLedgerError(
                f"Cannot record ledger entry for incomplete Stage E result: {result.status}"
            )
        return self.record_score(prediction=prediction, score=result.score)

    def get_entry(
        self,
        identity: ForwardEvidenceLedgerEntryIdentity,
    ) -> ForwardEvidenceLedgerEntry | None:
        """Fetch a specific ledger entry by its immutable 6-tuple identity."""
        return self._store.get_entry(identity)

    def get_member_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
        member_id: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]:
        """Retrieve all chronological entries for a member."""
        return self._store.list_member_entries(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
            member_id=member_id,
        )

    def get_cohort_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]:
        """Retrieve all chronological entries for a cohort."""
        return self._store.list_cohort_entries(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
        )

    def summarize_member(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
        member_id: str,
    ) -> MemberLongitudinalEvidenceSummary | None:
        """Build longitudinal evidence summary for a single cohort member, or None if empty."""
        entries = self.get_member_entries(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
            member_id=member_id,
        )
        if not entries:
            return None
        return build_member_longitudinal_summary(entries)


__all__ = [
    "ForwardEvidenceLedgerAppendResult",
    "ForwardEvidenceLedgerAppendStatus",
    "ForwardEvidenceLedgerService",
    "ForwardEvidenceLedgerStore",
]
