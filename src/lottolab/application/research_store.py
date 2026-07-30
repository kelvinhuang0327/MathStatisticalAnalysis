"""Application-owned contracts for the canonical research-store port."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
    StrategyProvenanceAvailability,
)


@dataclass(frozen=True, slots=True)
class StrategySnapshotInput:
    lottery_type: str
    strategy_id: str
    strategy_version: str
    source_commit_oid: str | None
    strategy_source_sha256: str | None
    producer_identity: str
    producer_version: str
    runtime_fingerprint: str | None
    parameters_json: str | None
    seed_protocol: str | None
    replicate: int
    execution_code_version: str
    strategy_name: str | None = None
    provenance_availability: StrategyProvenanceAvailability = (
        StrategyProvenanceAvailability.COMPLETE
    )
    governance_status: str | None = None
    lifecycle_status: str | None = None


@dataclass(frozen=True, slots=True)
class DrawBindingInput:
    lottery_type: str
    draw_number: str
    draw_date: str
    main_numbers_json: str
    special_numbers_json: str
    draw_sha256: str
    draw_data_version: str


@dataclass(frozen=True, slots=True)
class TicketInput:
    native_position: int
    ordered_portfolio_position: int | None
    canonical_ticket_json: str
    legacy_record_json: str | None = None
    legacy_provenance_hash: str | None = None
    legacy_provenance_source: str | None = None


@dataclass(frozen=True, slots=True)
class ClosureInput:
    closure_type: ResearchExecutionStatus
    reason_code: str
    sanitized_detail: str | None = None


@dataclass(frozen=True, slots=True)
class TicketResultInput:
    ticket_native_position: int
    ticket_count_prefix: int
    main_hit_count: int
    special_hit_count: int
    prize_tier_id: str | None
    hit_numbers_json: str | None = None
    legacy_reported_result_json: str | None = None


@dataclass(frozen=True, slots=True)
class TargetCommitInput:
    run_id: str
    strategy_snapshot_id: str
    target_order: int
    input_dataset_identity: str
    input_dataset_sha256: str
    history_cutoff: DrawBindingInput
    history_draw_count: int
    source_history_order: str
    target_draw: DrawBindingInput
    causal_eligible: bool
    candidate_k: int | None
    combination_count: int | None
    ticket_count_prefix: int | None
    tickets: tuple[TicketInput, ...]
    execution_status: ResearchExecutionStatus
    closure: ClosureInput | None = None
    result_draw: DrawBindingInput | None = None
    ticket_results: tuple[TicketResultInput, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetCommitResult:
    target_id: str
    verified_no_op: bool
    ticket_count: int


@dataclass(frozen=True, slots=True)
class RunProgress:
    run_id: str
    status: ResearchRunStatus
    expected_target_count: int
    completed_target_count: int
    progress_cursor: str | None


@dataclass(frozen=True, slots=True)
class CoverageRow:
    run_id: str
    run_kind: ResearchRunKind
    strategy_snapshot_id: str
    denominator_count: int
    ok_count: int
    closed_count: int


@dataclass(frozen=True, slots=True)
class CompletedTargetCursor:
    target_order: int
    strategy_snapshot_id: str
    target_id: str


@dataclass(frozen=True, slots=True)
class CoverageCursor:
    started_at: str
    run_id: str
    strategy_snapshot_id: str


@dataclass(frozen=True, slots=True)
class RankingCursor:
    rank_missing: int
    rank_sort: float
    prefix_sort: int
    run_id: str
    strategy_key: str
    summary_id: str


@dataclass(frozen=True, slots=True)
class TicketCursor:
    native_position: int
    ticket_id: str


type PageCursor = (
    CompletedTargetCursor | CoverageCursor | RankingCursor | TicketCursor
)


@dataclass(frozen=True, slots=True)
class QueryPage[PageItem]:
    items: tuple[PageItem, ...]
    next_cursor: PageCursor | None


@dataclass(frozen=True, slots=True)
class RunSummaryInput:
    run_id: str
    strategy_snapshot_id: str | None
    summary_kind: str
    ticket_count_prefix: int | None
    summary_version: int
    denominator_count: int
    successful_count: int
    closed_count: int
    rank_value: float | None
    canonical_summary_json: str


@dataclass(frozen=True, slots=True)
class RankingRow:
    run_id: str
    run_kind: ResearchRunKind
    strategy_snapshot_id: str | None
    ticket_count_prefix: int | None
    rank_value: float | None
    summary_sha256: str


@dataclass(frozen=True, slots=True)
class ResearchStoreReport:
    resolved_path: str
    schema_version: int
    migration_checksum: str
    migration_checksum_match: bool
    table_inventory: tuple[str, ...]
    row_counts: tuple[tuple[str, int], ...]
    append_only_triggers: tuple[str, ...]
    missing_append_only_triggers: tuple[str, ...]
    wal_sidecars_present: tuple[str, ...]
    missing_artifact_references: int
    resumable_runs: tuple[RunProgress, ...]

    @property
    def healthy(self) -> bool:
        return (
            self.migration_checksum_match
            and not self.missing_append_only_triggers
            and not self.wal_sidecars_present
            and self.missing_artifact_references == 0
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "append_only_trigger_count": len(self.append_only_triggers),
            "healthy": self.healthy,
            "migration_checksum": self.migration_checksum,
            "migration_checksum_match": self.migration_checksum_match,
            "missing_append_only_triggers": list(self.missing_append_only_triggers),
            "missing_artifact_references": self.missing_artifact_references,
            "resolved_path": self.resolved_path,
            "resumable_runs": [
                {
                    "completed_target_count": run.completed_target_count,
                    "expected_target_count": run.expected_target_count,
                    "progress_cursor": run.progress_cursor,
                    "run_id": run.run_id,
                    "status": run.status.value,
                }
                for run in self.resumable_runs
            ],
            "row_counts": [
                {"row_count": count, "table_name": table}
                for table, count in self.row_counts
            ],
            "schema_version": self.schema_version,
            "table_inventory": list(self.table_inventory),
            "wal_sidecars_present": list(self.wal_sidecars_present),
        }


class ResearchStore(Protocol):
    """Narrow application port implemented by the SQLite repository."""

    def register_rule_contract(
        self,
        contract: LotteryRuleContract,
        *,
        idempotency_key: str,
    ) -> str: ...

    def register_artifact(
        self,
        *,
        artifact_kind: str,
        source_locator: str,
        media_type: str,
        byte_length: int,
        artifact_sha256: str,
        idempotency_key: str,
    ) -> str: ...

    def create_run(
        self,
        *,
        run_kind: ResearchRunKind,
        rule_contract_id: str,
        input_dataset_identity: str,
        input_dataset_sha256: str,
        expected_target_count: int,
        producer_identity: str,
        execution_code_version: str,
        source_commit_oid: str,
        idempotency_key: str,
        run_id: str | None = None,
        status: ResearchRunStatus = ResearchRunStatus.RUNNING,
        progress_cursor: str | None = None,
        supersedes_run_id: str | None = None,
        derived_from_run_id: str | None = None,
        imported_from_artifact_id: str | None = None,
    ) -> str: ...

    def register_strategy_snapshot(
        self,
        run_id: str,
        value: StrategySnapshotInput,
        *,
        idempotency_key: str,
        snapshot_id: str | None = None,
    ) -> str: ...

    def commit_target(
        self,
        value: TargetCommitInput,
        *,
        idempotency_key: str,
    ) -> TargetCommitResult: ...

    def commit_ticket_results(
        self,
        target_id: str,
        draw: DrawBindingInput,
        results: Sequence[TicketResultInput],
        *,
        idempotency_key: str,
    ) -> int: ...

    def append_run_status(
        self,
        run_id: str,
        *,
        status: ResearchRunStatus,
        progress_cursor: str | None,
        idempotency_key: str,
    ) -> None: ...

    def store_run_summary(
        self,
        value: RunSummaryInput,
        *,
        idempotency_key: str,
        summary_id: str | None = None,
    ) -> str: ...

    def find_progress(self, run_id: str) -> RunProgress | None: ...

    def completed_target_keys(
        self,
        run_id: str,
        *,
        limit: int = 100,
        after: CompletedTargetCursor | None = None,
    ) -> QueryPage[tuple[str, str, str]]: ...

    def progress(self, run_id: str) -> RunProgress: ...

    def coverage(
        self,
        *,
        include_reference_baselines: bool = False,
        limit: int = 100,
        after: CoverageCursor | None = None,
    ) -> QueryPage[CoverageRow]: ...

    def rankings(
        self,
        *,
        include_reference_baselines: bool = False,
        limit: int = 100,
        after: RankingCursor | None = None,
    ) -> QueryPage[RankingRow]: ...

    def verify_store(self) -> ResearchStoreReport: ...


__all__ = [
    "ClosureInput",
    "CompletedTargetCursor",
    "CoverageCursor",
    "CoverageRow",
    "DrawBindingInput",
    "QueryPage",
    "RankingCursor",
    "RankingRow",
    "ResearchStore",
    "ResearchStoreReport",
    "RunProgress",
    "RunSummaryInput",
    "StrategySnapshotInput",
    "TargetCommitInput",
    "TargetCommitResult",
    "TicketCursor",
    "TicketInput",
    "TicketResultInput",
]
