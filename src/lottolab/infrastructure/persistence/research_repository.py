"""Sole read/write contract for the canonical LottoLab research store.

Ad-hoc Agent SQL is forbidden. Every state-changing operation must pass through
``SQLiteResearchRepository`` with an idempotency key. Writes verify the schema
version/checksum first, use short ``BEGIN IMMEDIATE`` transactions, and retain
append-only history. Readers use the read-only schema helper.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast

from lottolab.application.research_store import (
    ClosureInput,
    CompletedTargetCursor,
    CoverageCursor,
    CoverageRow,
    DrawBindingInput,
    QueryPage,
    RankingCursor,
    RankingRow,
    ResearchStoreReport,
    RunProgress,
    RunSummaryInput,
    StrategySnapshotInput,
    TargetCommitInput,
    TargetCommitResult,
    TicketCursor,
    TicketInput,
    TicketResultInput,
)
from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
    StrategyProvenanceAvailability,
)
from lottolab.infrastructure.persistence.research_schema import (
    APPEND_ONLY_TRIGGER_NAMES,
    BUSY_TIMEOUT_MS,
    IMMUTABLE_TABLE_NAMES,
    MIGRATION_CHECKSUM,
    TABLE_NAMES,
    ResearchDataPaths,
    initialize_schema,
    open_database,
)

WRITER_ROLE = "RESEARCH_STORE_WRITER_V1"
WRITE_RETRY_ATTEMPTS = 3
WRITE_RETRY_BACKOFF_SECONDS = (0.01, 0.05)
_T = TypeVar("_T")


class ResearchRepositoryError(RuntimeError):
    """A research-store request was invalid or could not be persisted."""


class DuplicateIdempotencyKeyError(ResearchRepositoryError):
    """A state-changing request reused a consumed idempotency key."""


class ResearchConflictError(ResearchRepositoryError):
    """Stored immutable bytes conflict with a recomputed identity."""


class SQLiteResearchRepository:
    """The only production-authorized SQL writer for research tables."""

    def __init__(self, paths: ResearchDataPaths, *, initialize: bool = True) -> None:
        self._paths = paths
        if initialize:
            initialize_schema(paths)

    @property
    def paths(self) -> ResearchDataPaths:
        return self._paths

    def register_rule_contract(
        self,
        contract: LotteryRuleContract,
        *,
        idempotency_key: str,
    ) -> str:
        canonical_payload = contract.canonical_json()
        contract_sha256 = _sha256(canonical_payload)
        contract_id = f"rule-{contract_sha256}"
        request_sha256 = _request_sha256(
            "register_rule_contract",
            {"contract_sha256": contract_sha256},
        )

        def operation(connection: sqlite3.Connection) -> str:
            _claim_idempotency(
                connection,
                operation_name="register_rule_contract",
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
            )
            row = connection.execute(
                """
                SELECT canonical_payload_json
                FROM research_rule_contracts
                WHERE id = ?
                """,
                (contract_id,),
            ).fetchone()
            if row is not None:
                if row[0] != canonical_payload:
                    raise ResearchConflictError("rule contract hash collision")
                return contract_id
            connection.execute(
                """
                INSERT INTO research_rule_contracts (
                    id, lottery_type, contract_version, canonical_payload_json,
                    contract_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    contract.lottery_type.value,
                    contract.contract_version,
                    canonical_payload,
                    contract_sha256,
                    _utc_now(),
                ),
            )
            return contract_id

        return self._write_transaction(operation)

    def register_artifact(
        self,
        *,
        artifact_kind: str,
        source_locator: str,
        media_type: str,
        byte_length: int,
        artifact_sha256: str,
        idempotency_key: str,
    ) -> str:
        _require_sha256(artifact_sha256, "artifact_sha256")
        artifact_id = f"artifact-{artifact_sha256}-{_sha256(artifact_kind)[:12]}"
        payload = {
            "artifact_kind": artifact_kind,
            "artifact_sha256": artifact_sha256,
            "byte_length": byte_length,
            "media_type": media_type,
            "source_locator": source_locator,
        }

        def operation(connection: sqlite3.Connection) -> str:
            _claim_idempotency(
                connection,
                operation_name="register_artifact",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("register_artifact", payload),
            )
            row = connection.execute(
                """
                SELECT artifact_kind, source_locator, media_type, byte_length, artifact_sha256
                FROM research_artifacts WHERE id = ?
                """,
                (artifact_id,),
            ).fetchone()
            expected = (
                artifact_kind,
                source_locator,
                media_type,
                byte_length,
                artifact_sha256,
            )
            if row is not None:
                if tuple(row) != expected:
                    raise ResearchConflictError("artifact identity conflicts with stored bytes")
                return artifact_id
            connection.execute(
                """
                INSERT INTO research_artifacts (
                    id, artifact_kind, source_locator, media_type, byte_length,
                    artifact_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, *expected, _utc_now()),
            )
            return artifact_id

        return self._write_transaction(operation)

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
    ) -> str:
        _require_sha256(input_dataset_sha256, "input_dataset_sha256")
        if expected_target_count < 0:
            raise ResearchRepositoryError("expected_target_count must not be negative")
        selected_run_id = run_id or f"run-{uuid.uuid4()}"
        payload = {
            "derived_from_run_id": derived_from_run_id,
            "execution_code_version": execution_code_version,
            "expected_target_count": expected_target_count,
            "imported_from_artifact_id": imported_from_artifact_id,
            "input_dataset_identity": input_dataset_identity,
            "input_dataset_sha256": input_dataset_sha256,
            "producer_identity": producer_identity,
            "progress_cursor": progress_cursor,
            "rule_contract_id": rule_contract_id,
            "run_id": selected_run_id,
            "run_kind": run_kind.value,
            "source_commit_oid": source_commit_oid,
            "status": status.value,
            "supersedes_run_id": supersedes_run_id,
        }

        def operation(connection: sqlite3.Connection) -> str:
            _claim_idempotency(
                connection,
                operation_name="create_run",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("create_run", payload),
            )
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO research_runs (
                    id, run_kind, rule_contract_id, input_dataset_identity,
                    input_dataset_sha256, status, progress_cursor,
                    expected_target_count, supersedes_run_id, derived_from_run_id,
                    imported_from_artifact_id, producer_identity,
                    execution_code_version, source_commit_oid, started_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selected_run_id,
                    run_kind.value,
                    rule_contract_id,
                    input_dataset_identity,
                    input_dataset_sha256,
                    status.value,
                    progress_cursor,
                    expected_target_count,
                    supersedes_run_id,
                    derived_from_run_id,
                    imported_from_artifact_id,
                    producer_identity,
                    execution_code_version,
                    source_commit_oid,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO research_run_status_events (
                    id, run_id, sequence, status, progress_cursor,
                    completed_target_count, observed_at, created_at
                ) VALUES (?, ?, 0, ?, ?, 0, ?, ?)
                """,
                (
                    f"event-{uuid.uuid4()}",
                    selected_run_id,
                    status.value,
                    progress_cursor,
                    now,
                    now,
                ),
            )
            return selected_run_id

        return self._write_transaction(operation)

    def register_strategy_snapshot(
        self,
        run_id: str,
        value: StrategySnapshotInput,
        *,
        idempotency_key: str,
        snapshot_id: str | None = None,
    ) -> str:
        if value.strategy_source_sha256 is not None:
            _require_sha256(value.strategy_source_sha256, "strategy_source_sha256")
        if value.strategy_name is not None and not value.strategy_name.strip():
            raise ResearchRepositoryError("strategy_name must be non-empty when present")
        provenance_values = (
            value.source_commit_oid,
            value.strategy_source_sha256,
            value.runtime_fingerprint,
            value.parameters_json,
            value.seed_protocol,
        )
        if value.provenance_availability is StrategyProvenanceAvailability.COMPLETE:
            if any(item is None for item in provenance_values):
                raise ResearchRepositoryError(
                    "complete strategy provenance requires every native provenance field"
                )
        elif value.provenance_availability is StrategyProvenanceAvailability.LEGACY_UNAVAILABLE:
            if any(item is not None for item in provenance_values):
                raise ResearchRepositoryError(
                    "legacy-unavailable provenance fields must remain null"
                )
        else:
            raise ResearchRepositoryError("strategy provenance availability is unsupported")
        canonical_parameters = (
            None
            if value.parameters_json is None
            else _validated_canonical_json(value.parameters_json, "parameters_json")
        )
        parameters_sha256 = (
            None if canonical_parameters is None else _sha256(canonical_parameters)
        )
        selected_id = snapshot_id or f"strategy-{uuid.uuid4()}"
        payload = {
            "parameters_sha256": parameters_sha256,
            "provenance_availability": value.provenance_availability.value,
            "run_id": run_id,
            "snapshot_id": selected_id,
            "strategy_id": value.strategy_id,
            "strategy_name": value.strategy_name,
            "strategy_source_sha256": value.strategy_source_sha256,
            "strategy_version": value.strategy_version,
        }

        def operation(connection: sqlite3.Connection) -> str:
            _claim_idempotency(
                connection,
                operation_name="register_strategy_snapshot",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("register_strategy_snapshot", payload),
            )
            expected = (
                run_id,
                value.lottery_type,
                value.strategy_id,
                value.strategy_name,
                value.strategy_version,
                value.provenance_availability.value,
                value.source_commit_oid,
                value.strategy_source_sha256,
                value.producer_identity,
                value.producer_version,
                value.runtime_fingerprint,
                canonical_parameters,
                parameters_sha256,
                value.seed_protocol,
                value.replicate,
                value.execution_code_version,
                value.governance_status,
                value.lifecycle_status,
            )
            existing = connection.execute(
                """
                SELECT run_id, lottery_type, strategy_id, strategy_name,
                       strategy_version, provenance_availability,
                       source_commit_oid, strategy_source_sha256,
                       producer_identity, producer_version, runtime_fingerprint,
                       parameters_json, parameters_sha256, seed_protocol,
                       replicate, execution_code_version, governance_status,
                       lifecycle_status
                FROM research_strategy_snapshots
                WHERE id = ?
                """,
                (selected_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != expected:
                    raise ResearchConflictError(
                        "strategy snapshot identity conflicts with stored bytes"
                    )
                return selected_id
            connection.execute(
                """
                INSERT INTO research_strategy_snapshots (
                    id, run_id, lottery_type, strategy_id, strategy_name,
                    strategy_version, provenance_availability, source_commit_oid,
                    strategy_source_sha256, producer_identity, producer_version,
                    runtime_fingerprint, parameters_json, parameters_sha256,
                    seed_protocol, replicate, execution_code_version,
                    governance_status, lifecycle_status, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (selected_id, *expected, _utc_now()),
            )
            return selected_id

        return self._write_transaction(operation)

    def commit_target(
        self,
        value: TargetCommitInput,
        *,
        idempotency_key: str,
    ) -> TargetCommitResult:
        normalized = _normalize_target(value)
        request_sha256 = _request_sha256("commit_target", normalized.request_payload)

        def operation(connection: sqlite3.Connection) -> TargetCommitResult:
            _claim_idempotency(
                connection,
                operation_name="commit_target",
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
            )
            existing = connection.execute(
                """
                SELECT id, target_payload_sha256
                FROM research_prediction_targets
                WHERE run_id = ?
                  AND strategy_snapshot_id = ?
                  AND target_lottery_type = ?
                  AND target_draw_number = ?
                """,
                (
                    value.run_id,
                    value.strategy_snapshot_id,
                    value.target_draw.lottery_type,
                    value.target_draw.draw_number,
                ),
            ).fetchone()
            if existing is not None:
                target_id = str(existing[0])
                stored_hashes = tuple(
                    (
                        int(row[0]),
                        None if row[1] is None else int(row[1]),
                        str(row[2]),
                        str(row[3]),
                        None if row[4] is None else str(row[4]),
                        None if row[5] is None else str(row[5]),
                        None if row[6] is None else str(row[6]),
                        None if row[7] is None else str(row[7]),
                    )
                    for row in connection.execute(
                        """
                        SELECT native_position, ordered_portfolio_position,
                               canonical_ticket_json, ticket_sha256,
                               legacy_record_json, legacy_record_sha256,
                               legacy_provenance_hash, legacy_provenance_source
                        FROM research_prediction_tickets
                        WHERE target_id = ?
                        ORDER BY native_position, id
                        """,
                        (target_id,),
                    )
                )
                if (
                    str(existing[1]) != normalized.target_payload_sha256
                    or stored_hashes != normalized.ticket_identity_rows
                ):
                    raise ResearchConflictError(
                        "completed target conflicts with recomputed ticket hashes"
                    )
                return TargetCommitResult(
                    target_id=target_id,
                    verified_no_op=True,
                    ticket_count=len(stored_hashes),
                )

            cutoff_id = _insert_or_verify_draw_binding(connection, value.history_cutoff)
            target_binding_id = _insert_or_verify_draw_binding(connection, value.target_draw)
            target_id = f"target-{uuid.uuid4()}"
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO research_prediction_targets (
                    id, run_id, strategy_snapshot_id, target_order,
                    input_dataset_identity, input_dataset_sha256,
                    history_cutoff_binding_id, history_cutoff_lottery_type,
                    history_cutoff_draw_number, history_cutoff_draw_date,
                    history_draw_count, source_history_order,
                    target_draw_binding_id, target_lottery_type,
                    target_draw_number, target_draw_date, causal_eligible,
                    candidate_k, combination_count, ticket_count_prefix,
                    native_ticket_count, ordered_portfolio_count,
                    execution_status, terminal_marker, target_payload_sha256,
                    completed_at, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, 1, ?, ?, ?
                )
                """,
                (
                    target_id,
                    value.run_id,
                    value.strategy_snapshot_id,
                    value.target_order,
                    value.input_dataset_identity,
                    value.input_dataset_sha256,
                    cutoff_id,
                    value.history_cutoff.lottery_type,
                    value.history_cutoff.draw_number,
                    value.history_cutoff.draw_date,
                    value.history_draw_count,
                    value.source_history_order,
                    target_binding_id,
                    value.target_draw.lottery_type,
                    value.target_draw.draw_number,
                    value.target_draw.draw_date,
                    int(value.causal_eligible),
                    value.candidate_k,
                    value.combination_count,
                    value.ticket_count_prefix,
                    len(normalized.tickets),
                    normalized.ordered_ticket_count,
                    value.execution_status.value,
                    normalized.target_payload_sha256,
                    now,
                    now,
                ),
            )
            for ticket in normalized.tickets:
                connection.execute(
                    """
                    INSERT INTO research_prediction_tickets (
                        id, target_id, native_position, ordered_portfolio_position,
                        canonical_ticket_json, main_numbers_json,
                        special_numbers_json, ticket_sha256,
                        native_duplicate_of_position,
                        portfolio_duplicate_of_position, legacy_record_json,
                        legacy_record_sha256, legacy_provenance_hash,
                        legacy_provenance_source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{target_id}-ticket-{ticket.native_position}",
                        target_id,
                        ticket.native_position,
                        ticket.ordered_portfolio_position,
                        ticket.canonical_ticket_json,
                        ticket.main_numbers_json,
                        ticket.special_numbers_json,
                        ticket.ticket_sha256,
                        ticket.native_duplicate_of_position,
                        ticket.portfolio_duplicate_of_position,
                        ticket.legacy_record_json,
                        ticket.legacy_record_sha256,
                        ticket.legacy_provenance_hash,
                        ticket.legacy_provenance_source,
                        now,
                    ),
                )
            if value.result_draw is not None:
                inserted_results = _commit_ticket_result_rows(
                    connection,
                    target_id,
                    value.result_draw,
                    value.ticket_results,
                )
                if inserted_results != len(value.ticket_results):
                    raise ResearchConflictError(
                        "atomic ticket results did not insert as one complete target"
                    )
            if value.closure is not None:
                connection.execute(
                    """
                    INSERT INTO research_execution_closures (
                        id, target_id, closure_type, reason_code,
                        sanitized_detail, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"closure-{uuid.uuid4()}",
                        target_id,
                        value.closure.closure_type.value,
                        value.closure.reason_code,
                        value.closure.sanitized_detail,
                        now,
                    ),
                )
            return TargetCommitResult(
                target_id=target_id,
                verified_no_op=False,
                ticket_count=len(normalized.tickets),
            )

        return self._write_transaction(operation)

    def commit_ticket_results(
        self,
        target_id: str,
        draw: DrawBindingInput,
        results: Sequence[TicketResultInput],
        *,
        idempotency_key: str,
    ) -> int:
        if not results:
            raise ResearchRepositoryError("at least one ticket result is required")
        result_payload = [_ticket_result_payload(row) for row in results]
        request_sha256 = _request_sha256(
            "commit_ticket_results",
            {
                "draw_sha256": draw.draw_sha256,
                "results": result_payload,
                "target_id": target_id,
            },
        )

        def operation(connection: sqlite3.Connection) -> int:
            _claim_idempotency(
                connection,
                operation_name="commit_ticket_results",
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
            )
            return _commit_ticket_result_rows(connection, target_id, draw, results)

        return self._write_transaction(operation)

    def append_run_status(
        self,
        run_id: str,
        *,
        status: ResearchRunStatus,
        progress_cursor: str | None,
        idempotency_key: str,
    ) -> None:
        payload = {
            "progress_cursor": progress_cursor,
            "run_id": run_id,
            "status": status.value,
        }

        def operation(connection: sqlite3.Connection) -> None:
            _claim_idempotency(
                connection,
                operation_name="append_run_status",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("append_run_status", payload),
            )
            sequence_row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), -1)
                FROM research_run_status_events
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            completed_row = connection.execute(
                """
                SELECT COUNT(*)
                FROM research_prediction_targets
                WHERE run_id = ? AND terminal_marker = 1
                """,
                (run_id,),
            ).fetchone()
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO research_run_status_events (
                    id, run_id, sequence, status, progress_cursor,
                    completed_target_count, observed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event-{uuid.uuid4()}",
                    run_id,
                    int(sequence_row[0]) + 1,
                    status.value,
                    progress_cursor,
                    int(completed_row[0]),
                    now,
                    now,
                ),
            )

        self._write_transaction(operation)

    def set_current_run(
        self,
        pointer_name: str,
        run_id: str,
        *,
        idempotency_key: str,
    ) -> None:
        payload = {"pointer_name": pointer_name, "run_id": run_id}

        def operation(connection: sqlite3.Connection) -> None:
            _claim_idempotency(
                connection,
                operation_name="set_current_run",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("set_current_run", payload),
            )
            connection.execute(
                """
                INSERT INTO research_run_current_pointer (pointer_name, run_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(pointer_name) DO UPDATE SET
                    run_id = excluded.run_id,
                    updated_at = excluded.updated_at
                """,
                (pointer_name, run_id, _utc_now()),
            )

        self._write_transaction(operation)

    def store_run_summary(
        self,
        value: RunSummaryInput,
        *,
        idempotency_key: str,
        summary_id: str | None = None,
    ) -> str:
        if value.summary_kind not in {"COVERAGE", "RANKING", "DENOMINATOR", "AUDIT"}:
            raise ResearchRepositoryError("summary_kind is not supported")
        if value.ticket_count_prefix is not None and value.ticket_count_prefix <= 0:
            raise ResearchRepositoryError("ticket_count_prefix must be positive")
        if value.summary_version < 1:
            raise ResearchRepositoryError("summary_version must be positive")
        for label, count in (
            ("denominator_count", value.denominator_count),
            ("successful_count", value.successful_count),
            ("closed_count", value.closed_count),
        ):
            if count < 0:
                raise ResearchRepositoryError(f"{label} must not be negative")
        canonical = _validated_canonical_json(
            value.canonical_summary_json,
            "canonical_summary_json",
        )
        summary_sha256 = _sha256(canonical)
        selected_summary_id = summary_id or f"summary-{uuid.uuid4()}"
        payload = {
            "canonical_summary_json": canonical,
            "closed_count": value.closed_count,
            "denominator_count": value.denominator_count,
            "rank_value": value.rank_value,
            "run_id": value.run_id,
            "strategy_snapshot_id": value.strategy_snapshot_id,
            "successful_count": value.successful_count,
            "summary_kind": value.summary_kind,
            "summary_id": selected_summary_id,
            "summary_version": value.summary_version,
            "ticket_count_prefix": value.ticket_count_prefix,
        }

        def operation(connection: sqlite3.Connection) -> str:
            _claim_idempotency(
                connection,
                operation_name="store_run_summary",
                idempotency_key=idempotency_key,
                request_sha256=_request_sha256("store_run_summary", payload),
            )
            expected = (
                value.run_id,
                value.strategy_snapshot_id,
                value.summary_kind,
                value.ticket_count_prefix,
                value.summary_version,
                value.denominator_count,
                value.successful_count,
                value.closed_count,
                value.rank_value,
                canonical,
                summary_sha256,
            )
            existing = connection.execute(
                """
                SELECT run_id, strategy_snapshot_id, summary_kind,
                       ticket_count_prefix, summary_version, denominator_count,
                       successful_count, closed_count, rank_value,
                       canonical_summary_json, summary_sha256
                FROM research_run_summaries
                WHERE id = ?
                """,
                (selected_summary_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != expected:
                    raise ResearchConflictError(
                        "run summary identity conflicts with stored bytes"
                    )
                return selected_summary_id
            connection.execute(
                """
                INSERT INTO research_run_summaries (
                    id, run_id, strategy_snapshot_id, summary_kind,
                    ticket_count_prefix, summary_version, denominator_count,
                    successful_count, closed_count, rank_value,
                    canonical_summary_json, summary_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selected_summary_id,
                    *expected,
                    _utc_now(),
                ),
            )
            return selected_summary_id

        return self._write_transaction(operation)

    def completed_target_keys(
        self,
        run_id: str,
        *,
        limit: int = 100,
        after: CompletedTargetCursor | None = None,
    ) -> QueryPage[tuple[str, str, str]]:
        """Return one deterministic keyset page without scanning ticket rows."""

        _validate_page_limit(limit)
        cursor_clause = ""
        parameters: list[object] = [run_id]
        if after is not None:
            cursor_clause = (
                "AND (target_order, strategy_snapshot_id, id) > (?, ?, ?)"
            )
            parameters.extend(
                (after.target_order, after.strategy_snapshot_id, after.target_id)
            )
        parameters.append(limit + 1)
        with open_database(self._paths, read_only=True) as connection:
            rows = connection.execute(
                f"""
                    SELECT strategy_snapshot_id, target_lottery_type,
                           target_draw_number, target_order, id
                    FROM research_prediction_targets
                    WHERE run_id = ? AND terminal_marker = 1
                      {cursor_clause}
                    ORDER BY target_order, strategy_snapshot_id, id
                    LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        page_rows = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page_rows:
            last = page_rows[-1]
            next_cursor = CompletedTargetCursor(
                target_order=int(last[3]),
                strategy_snapshot_id=str(last[0]),
                target_id=str(last[4]),
            )
        return QueryPage(
            items=tuple(
                (str(row[0]), str(row[1]), str(row[2])) for row in page_rows
            ),
            next_cursor=next_cursor,
        )

    def find_progress(self, run_id: str) -> RunProgress | None:
        with open_database(self._paths, read_only=True) as connection:
            row = connection.execute(
                """
                SELECT r.expected_target_count,
                       COALESCE((
                           SELECT COUNT(*)
                           FROM research_prediction_targets AS t
                           WHERE t.run_id = r.id AND t.terminal_marker = 1
                       ), 0),
                       e.status,
                       COALESCE(
                           e.progress_cursor,
                           (
                               SELECT CAST(MAX(t.target_order) AS TEXT)
                               FROM research_prediction_targets AS t
                               WHERE t.run_id = r.id AND t.terminal_marker = 1
                           ),
                           r.progress_cursor
                       )
                FROM research_runs AS r
                JOIN research_run_status_events AS e
                  ON e.run_id = r.id
                 AND e.sequence = (
                     SELECT MAX(e2.sequence)
                     FROM research_run_status_events AS e2
                     WHERE e2.run_id = r.id
                 )
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunProgress(
            run_id=run_id,
            status=ResearchRunStatus(str(row[2])),
            expected_target_count=int(row[0]),
            completed_target_count=int(row[1]),
            progress_cursor=None if row[3] is None else str(row[3]),
        )

    def progress(self, run_id: str) -> RunProgress:
        progress = self.find_progress(run_id)
        if progress is None:
            raise ResearchRepositoryError("research run does not exist")
        return progress

    def coverage(
        self,
        *,
        include_reference_baselines: bool = False,
        limit: int = 100,
        after: CoverageCursor | None = None,
    ) -> QueryPage[CoverageRow]:
        _validate_page_limit(limit)
        baseline_clause = "" if include_reference_baselines else "AND r.run_kind != ?"
        parameters: list[object] = []
        if not include_reference_baselines:
            parameters.append(ResearchRunKind.REFERENCE_BASELINE.value)
        cursor_clause = ""
        if after is not None:
            cursor_clause = (
                "WHERE (started_at, run_id, strategy_snapshot_id) > (?, ?, ?)"
            )
            parameters.extend(
                (after.started_at, after.run_id, after.strategy_snapshot_id)
            )
        parameters.append(limit + 1)
        with open_database(self._paths, read_only=True) as connection:
            rows = connection.execute(
                f"""
                WITH coverage_rows AS (
                    SELECT r.started_at, r.id AS run_id, r.run_kind,
                           t.strategy_snapshot_id,
                           COUNT(*) AS denominator_count,
                           SUM(
                               CASE WHEN t.execution_status = 'OK' THEN 1 ELSE 0 END
                           ) AS ok_count,
                           SUM(
                               CASE WHEN t.execution_status != 'OK' THEN 1 ELSE 0 END
                           ) AS closed_count
                    FROM research_runs AS r
                    JOIN research_prediction_targets AS t ON t.run_id = r.id
                    WHERE t.terminal_marker = 1 {baseline_clause}
                    GROUP BY r.started_at, r.id, r.run_kind, t.strategy_snapshot_id
                )
                SELECT run_id, run_kind, strategy_snapshot_id,
                       denominator_count, ok_count, closed_count, started_at
                FROM coverage_rows
                {cursor_clause}
                ORDER BY started_at, run_id, strategy_snapshot_id
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        page_rows = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page_rows:
            last = page_rows[-1]
            next_cursor = CoverageCursor(
                started_at=str(last[6]),
                run_id=str(last[0]),
                strategy_snapshot_id=str(last[2]),
            )
        return QueryPage(
            items=tuple(
                CoverageRow(
                    run_id=str(row[0]),
                    run_kind=ResearchRunKind(str(row[1])),
                    strategy_snapshot_id=str(row[2]),
                    denominator_count=int(row[3]),
                    ok_count=int(row[4]),
                    closed_count=int(row[5]),
                )
                for row in page_rows
            ),
            next_cursor=next_cursor,
        )

    def rankings(
        self,
        *,
        include_reference_baselines: bool = False,
        limit: int = 100,
        after: RankingCursor | None = None,
    ) -> QueryPage[RankingRow]:
        _validate_page_limit(limit)
        baseline_clause = "" if include_reference_baselines else "AND r.run_kind != ?"
        parameters: list[object] = []
        if not include_reference_baselines:
            parameters.append(ResearchRunKind.REFERENCE_BASELINE.value)
        cursor_clause = ""
        if after is not None:
            cursor_clause = """
                WHERE (
                    rank_missing, rank_sort, prefix_sort,
                    run_id, strategy_key, summary_id
                ) > (?, ?, ?, ?, ?, ?)
            """
            parameters.extend(
                (
                    after.rank_missing,
                    after.rank_sort,
                    after.prefix_sort,
                    after.run_id,
                    after.strategy_key,
                    after.summary_id,
                )
            )
        parameters.append(limit + 1)
        with open_database(self._paths, read_only=True) as connection:
            rows = connection.execute(
                f"""
                WITH ranking_rows AS (
                    SELECT s.run_id, r.run_kind, s.strategy_snapshot_id,
                           s.ticket_count_prefix, s.rank_value, s.summary_sha256,
                           CASE WHEN s.rank_value IS NULL THEN 1 ELSE 0 END
                               AS rank_missing,
                           CASE
                               WHEN s.rank_value IS NULL THEN 0.0
                               ELSE -s.rank_value
                           END AS rank_sort,
                           COALESCE(s.ticket_count_prefix, 0) AS prefix_sort,
                           COALESCE(s.strategy_snapshot_id, '') AS strategy_key,
                           s.id AS summary_id
                    FROM research_run_summaries AS s
                    JOIN research_runs AS r ON r.id = s.run_id
                    WHERE s.summary_kind = 'RANKING' {baseline_clause}
                )
                SELECT run_id, run_kind, strategy_snapshot_id,
                       ticket_count_prefix, rank_value, summary_sha256,
                       rank_missing, rank_sort, prefix_sort, strategy_key, summary_id
                FROM ranking_rows
                {cursor_clause}
                ORDER BY
                    rank_missing, rank_sort, prefix_sort,
                    run_id, strategy_key, summary_id
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        page_rows = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page_rows:
            last = page_rows[-1]
            next_cursor = RankingCursor(
                rank_missing=int(last[6]),
                rank_sort=float(last[7]),
                prefix_sort=int(last[8]),
                run_id=str(last[0]),
                strategy_key=str(last[9]),
                summary_id=str(last[10]),
            )
        return QueryPage(
            items=tuple(
                RankingRow(
                    run_id=str(row[0]),
                    run_kind=ResearchRunKind(str(row[1])),
                    strategy_snapshot_id=None if row[2] is None else str(row[2]),
                    ticket_count_prefix=None if row[3] is None else int(row[3]),
                    rank_value=None if row[4] is None else float(row[4]),
                    summary_sha256=str(row[5]),
                )
                for row in page_rows
            ),
            next_cursor=next_cursor,
        )

    def list_target_tickets(
        self,
        target_id: str,
        *,
        limit: int = 100,
        after: TicketCursor | None = None,
    ) -> QueryPage[tuple[int, int | None, str, str]]:
        _validate_page_limit(limit)
        cursor_clause = ""
        parameters: list[object] = [target_id]
        if after is not None:
            cursor_clause = "AND (native_position, id) > (?, ?)"
            parameters.extend((after.native_position, after.ticket_id))
        parameters.append(limit + 1)
        with open_database(self._paths, read_only=True) as connection:
            rows = connection.execute(
                f"""
                    SELECT native_position, ordered_portfolio_position,
                           canonical_ticket_json, ticket_sha256, id
                    FROM research_prediction_tickets
                    WHERE target_id = ?
                      {cursor_clause}
                    ORDER BY native_position, id
                    LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        page_rows = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page_rows:
            last = page_rows[-1]
            next_cursor = TicketCursor(
                native_position=int(last[0]),
                ticket_id=str(last[4]),
            )
        return QueryPage(
            items=tuple(
                (
                    int(row[0]),
                    None if row[1] is None else int(row[1]),
                    str(row[2]),
                    str(row[3]),
                )
                for row in page_rows
            ),
            next_cursor=next_cursor,
        )

    def verify_store(self) -> ResearchStoreReport:
        with open_database(self._paths, read_only=True) as connection:
            inventory = tuple(
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_schema
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                )
            )
            counts = tuple(
                (table, int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]))
                for table in TABLE_NAMES
            )
            triggers = tuple(
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_schema
                    WHERE type = 'trigger'
                    ORDER BY name
                    """
                )
            )
            migration_row = connection.execute(
                """
                SELECT version, checksum
                FROM research_schema_migrations
                ORDER BY version DESC
                LIMIT 1
                """
            ).fetchone()
            missing_artifacts = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM research_runs AS r
                    LEFT JOIN research_artifacts AS a
                      ON a.id = r.imported_from_artifact_id
                    WHERE r.imported_from_artifact_id IS NOT NULL AND a.id IS NULL
                    """
                ).fetchone()[0]
            )
            resumable_rows = connection.execute(
                """
                SELECT r.id
                FROM research_runs AS r
                JOIN research_run_status_events AS e
                  ON e.run_id = r.id
                 AND e.sequence = (
                     SELECT MAX(e2.sequence)
                     FROM research_run_status_events AS e2
                     WHERE e2.run_id = r.id
                 )
                WHERE e.status IN ('PENDING', 'RUNNING', 'PAUSED')
                ORDER BY r.started_at, r.id
                """
            ).fetchall()
        resumable = tuple(self.progress(str(row[0])) for row in resumable_rows)
        trigger_set = set(triggers)
        wal_sidecars = tuple(
            str(candidate)
            for candidate in (
                Path(f"{self._paths.database}-wal"),
                Path(f"{self._paths.database}-shm"),
            )
            if candidate.exists()
        )
        return ResearchStoreReport(
            resolved_path=str(self._paths.database),
            schema_version=int(migration_row[0]),
            migration_checksum=str(migration_row[1]),
            migration_checksum_match=str(migration_row[1]) == MIGRATION_CHECKSUM,
            table_inventory=inventory,
            row_counts=counts,
            append_only_triggers=tuple(
                trigger for trigger in triggers if trigger in set(APPEND_ONLY_TRIGGER_NAMES)
            ),
            missing_append_only_triggers=tuple(
                trigger for trigger in APPEND_ONLY_TRIGGER_NAMES if trigger not in trigger_set
            ),
            wal_sidecars_present=wal_sidecars,
            missing_artifact_references=missing_artifacts,
            resumable_runs=resumable,
        )

    def _write_transaction(self, operation: Callable[[sqlite3.Connection], _T]) -> _T:
        last_busy_error: sqlite3.OperationalError | None = None
        for attempt in range(WRITE_RETRY_ATTEMPTS):
            try:
                with open_database(self._paths, read_only=False) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        result = operation(connection)
                    except BaseException:
                        connection.rollback()
                        raise
                    connection.commit()
                    return result
            except sqlite3.OperationalError as exc:
                if not _is_busy_error(exc):
                    raise ResearchRepositoryError("research write failed") from exc
                last_busy_error = exc
                if attempt < len(WRITE_RETRY_BACKOFF_SECONDS):
                    time.sleep(WRITE_RETRY_BACKOFF_SECONDS[attempt])
            except sqlite3.IntegrityError as exc:
                raise ResearchRepositoryError("research write violates the store contract") from exc
        raise ResearchRepositoryError(
            f"research writer remained busy after {WRITE_RETRY_ATTEMPTS} attempts "
            f"with {BUSY_TIMEOUT_MS}ms busy timeout"
        ) from last_busy_error


@dataclass(frozen=True, slots=True)
class _NormalizedTicket:
    native_position: int
    ordered_portfolio_position: int | None
    canonical_ticket_json: str
    main_numbers_json: str
    special_numbers_json: str
    ticket_sha256: str
    native_duplicate_of_position: int | None
    portfolio_duplicate_of_position: int | None
    legacy_record_json: str | None
    legacy_record_sha256: str | None
    legacy_provenance_hash: str | None
    legacy_provenance_source: str | None


@dataclass(frozen=True, slots=True)
class _NormalizedTarget:
    tickets: tuple[_NormalizedTicket, ...]
    ordered_ticket_count: int
    ticket_identity_rows: tuple[
        tuple[
            int,
            int | None,
            str,
            str,
            str | None,
            str | None,
            str | None,
            str | None,
        ],
        ...,
    ]
    target_payload_sha256: str
    request_payload: dict[str, object]


def _normalize_target(value: TargetCommitInput) -> _NormalizedTarget:
    _require_sha256(value.input_dataset_sha256, "input_dataset_sha256")
    if value.target_order < 0:
        raise ResearchRepositoryError("target_order must not be negative")
    if value.history_draw_count < 0:
        raise ResearchRepositoryError("history_draw_count must not be negative")
    if value.ticket_count_prefix is not None and value.ticket_count_prefix <= 0:
        raise ResearchRepositoryError("ticket_count_prefix must be positive")
    if value.execution_status is ResearchExecutionStatus.OK and value.closure is not None:
        raise ResearchRepositoryError("OK target cannot carry a closure")
    if value.execution_status is not ResearchExecutionStatus.OK and (
        value.closure is None or value.closure.closure_type is not value.execution_status
    ):
        raise ResearchRepositoryError("closed target requires a matching typed closure")
    if (value.result_draw is None) != (not value.ticket_results):
        raise ResearchRepositoryError(
            "atomic ticket results require both result_draw and ticket_results"
        )
    positions = [ticket.native_position for ticket in value.tickets]
    if positions != list(range(1, len(value.tickets) + 1)):
        raise ResearchRepositoryError("native ticket positions must be contiguous and ordered")
    ordered_positions = [
        ticket.ordered_portfolio_position
        for ticket in value.tickets
        if ticket.ordered_portfolio_position is not None
    ]
    if sorted(ordered_positions) != list(range(1, len(ordered_positions) + 1)):
        raise ResearchRepositoryError(
            "ordered portfolio positions must be unique and contiguous"
        )
    result_positions = [row.ticket_native_position for row in value.ticket_results]
    if result_positions and result_positions != positions:
        raise ResearchRepositoryError(
            "atomic ticket results must cover every ticket in native order"
        )

    native_first: dict[str, int] = {}
    portfolio_first: dict[str, int] = {}
    normalized: list[_NormalizedTicket] = []
    for ticket in value.tickets:
        canonical = _validated_canonical_json(
            ticket.canonical_ticket_json,
            "canonical_ticket_json",
        )
        decoded_value = cast(object, json.loads(canonical))
        if not isinstance(decoded_value, dict):
            raise ResearchRepositoryError(
                "canonical_ticket_json must contain main_numbers and special_numbers"
            )
        decoded = cast(dict[str, object], decoded_value)
        if set(decoded) != {
            "main_numbers",
            "special_numbers",
        }:
            raise ResearchRepositoryError(
                "canonical_ticket_json must contain main_numbers and special_numbers"
            )
        main_numbers = decoded["main_numbers"]
        special_numbers = decoded["special_numbers"]
        if not isinstance(main_numbers, list) or not isinstance(special_numbers, list):
            raise ResearchRepositoryError("ticket number fields must be JSON arrays")
        legacy_record = (
            None
            if ticket.legacy_record_json is None
            else _validated_canonical_json(
                ticket.legacy_record_json,
                "legacy_record_json",
            )
        )
        native_duplicate = native_first.get(canonical)
        native_first.setdefault(canonical, ticket.native_position)
        portfolio_duplicate: int | None = None
        if ticket.ordered_portfolio_position is not None:
            portfolio_duplicate = portfolio_first.get(canonical)
            portfolio_first.setdefault(canonical, ticket.ordered_portfolio_position)
        normalized.append(
            _NormalizedTicket(
                native_position=ticket.native_position,
                ordered_portfolio_position=ticket.ordered_portfolio_position,
                canonical_ticket_json=canonical,
                main_numbers_json=_canonical_json(cast(list[object], main_numbers)),
                special_numbers_json=_canonical_json(cast(list[object], special_numbers)),
                ticket_sha256=_sha256(canonical),
                native_duplicate_of_position=native_duplicate,
                portfolio_duplicate_of_position=portfolio_duplicate,
                legacy_record_json=legacy_record,
                legacy_record_sha256=(
                    None if legacy_record is None else _sha256(legacy_record)
                ),
                legacy_provenance_hash=ticket.legacy_provenance_hash,
                legacy_provenance_source=ticket.legacy_provenance_source,
            )
        )
    ticket_rows = tuple(
        (
            row.native_position,
            row.ordered_portfolio_position,
            row.canonical_ticket_json,
            row.ticket_sha256,
            row.legacy_record_json,
            row.legacy_record_sha256,
            row.legacy_provenance_hash,
            row.legacy_provenance_source,
        )
        for row in normalized
    )
    request_payload: dict[str, object] = {
        "candidate_k": value.candidate_k,
        "causal_eligible": value.causal_eligible,
        "combination_count": value.combination_count,
        "execution_status": value.execution_status.value,
        "history_cutoff": _draw_payload(value.history_cutoff),
        "history_draw_count": value.history_draw_count,
        "input_dataset_identity": value.input_dataset_identity,
        "input_dataset_sha256": value.input_dataset_sha256,
        "run_id": value.run_id,
        "source_history_order": value.source_history_order,
        "strategy_snapshot_id": value.strategy_snapshot_id,
        "target_draw": _draw_payload(value.target_draw),
        "target_order": value.target_order,
        "ticket_count_prefix": value.ticket_count_prefix,
        "tickets": [
            {
                "canonical_ticket_json": row.canonical_ticket_json,
                "native_position": row.native_position,
                "ordered_portfolio_position": row.ordered_portfolio_position,
                "ticket_sha256": row.ticket_sha256,
                "legacy_record_json": row.legacy_record_json,
                "legacy_record_sha256": row.legacy_record_sha256,
                "legacy_provenance_hash": row.legacy_provenance_hash,
                "legacy_provenance_source": row.legacy_provenance_source,
            }
            for row in normalized
        ],
    }
    if value.result_draw is not None:
        request_payload["result_draw"] = _draw_payload(value.result_draw)
        request_payload["ticket_results"] = [
            _ticket_result_payload(row) for row in value.ticket_results
        ]
    if value.closure is not None:
        request_payload["closure"] = {
            "closure_type": value.closure.closure_type.value,
            "reason_code": value.closure.reason_code,
            "sanitized_detail": value.closure.sanitized_detail,
        }
    return _NormalizedTarget(
        tickets=tuple(normalized),
        ordered_ticket_count=len(ordered_positions),
        ticket_identity_rows=ticket_rows,
        target_payload_sha256=_sha256(_canonical_json(request_payload)),
        request_payload=request_payload,
    )


def _ticket_result_payload(value: TicketResultInput) -> dict[str, object]:
    for label, number in (
        ("ticket_native_position", value.ticket_native_position),
        ("ticket_count_prefix", value.ticket_count_prefix),
        ("main_hit_count", value.main_hit_count),
        ("special_hit_count", value.special_hit_count),
    ):
        if type(number) is not int:
            raise ResearchRepositoryError(f"{label} must be an integer")
    if value.ticket_native_position < 1:
        raise ResearchRepositoryError("ticket_native_position must be positive")
    if value.ticket_count_prefix < 1:
        raise ResearchRepositoryError("ticket_count_prefix must be positive")
    if value.main_hit_count < 0 or value.special_hit_count < 0:
        raise ResearchRepositoryError("ticket hit counts must not be negative")
    hit_numbers_json = (
        None
        if value.hit_numbers_json is None
        else _validated_canonical_json(value.hit_numbers_json, "hit_numbers_json")
    )
    if hit_numbers_json is not None and not isinstance(json.loads(hit_numbers_json), list):
        raise ResearchRepositoryError("hit_numbers_json must contain a JSON array")
    legacy_result_json = (
        None
        if value.legacy_reported_result_json is None
        else _validated_canonical_json(
            value.legacy_reported_result_json,
            "legacy_reported_result_json",
        )
    )
    return {
        "hit_numbers_json": hit_numbers_json,
        "legacy_reported_result_json": legacy_result_json,
        "legacy_reported_result_sha256": (
            None if legacy_result_json is None else _sha256(legacy_result_json)
        ),
        "main_hit_count": value.main_hit_count,
        "prize_tier_id": value.prize_tier_id,
        "special_hit_count": value.special_hit_count,
        "ticket_count_prefix": value.ticket_count_prefix,
        "ticket_native_position": value.ticket_native_position,
    }


def _commit_ticket_result_rows(
    connection: sqlite3.Connection,
    target_id: str,
    draw: DrawBindingInput,
    results: Sequence[TicketResultInput],
) -> int:
    target_key = connection.execute(
        """
        SELECT target_lottery_type, target_draw_number
        FROM research_prediction_targets
        WHERE id = ?
        """,
        (target_id,),
    ).fetchone()
    if target_key is None:
        raise ResearchRepositoryError("ticket results reference a missing target")
    if (str(target_key[0]), str(target_key[1])) != (
        draw.lottery_type,
        draw.draw_number,
    ):
        raise ResearchRepositoryError(
            "ticket result draw natural key does not match the prediction target"
        )
    draw_binding_id = _insert_or_verify_draw_binding(connection, draw)
    inserted = 0
    for row in results:
        normalized = _ticket_result_payload(row)
        ticket_row = connection.execute(
            """
            SELECT id
            FROM research_prediction_tickets
            WHERE target_id = ? AND native_position = ?
            """,
            (target_id, row.ticket_native_position),
        ).fetchone()
        if ticket_row is None:
            raise ResearchRepositoryError("ticket result references a missing ticket")
        ticket_id = str(ticket_row[0])
        payload = _canonical_json(
            {
                "draw_sha256": draw.draw_sha256,
                "hit_numbers_json": normalized["hit_numbers_json"],
                "legacy_reported_result_json": normalized[
                    "legacy_reported_result_json"
                ],
                "legacy_reported_result_sha256": normalized[
                    "legacy_reported_result_sha256"
                ],
                "main_hit_count": row.main_hit_count,
                "prize_tier_id": row.prize_tier_id,
                "special_hit_count": row.special_hit_count,
                "ticket_count_prefix": row.ticket_count_prefix,
                "ticket_id": ticket_id,
            }
        )
        result_sha256 = _sha256(payload)
        existing = connection.execute(
            """
            SELECT result_sha256
            FROM research_ticket_results
            WHERE target_id = ? AND ticket_id = ?
              AND ticket_count_prefix = ? AND draw_sha256 = ?
            """,
            (
                target_id,
                ticket_id,
                row.ticket_count_prefix,
                draw.draw_sha256,
            ),
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != result_sha256:
                raise ResearchConflictError(
                    "same draw checksum produced different ticket results"
                )
            continue
        version_row = connection.execute(
            """
            SELECT COALESCE(MAX(result_version), 0)
            FROM research_ticket_results
            WHERE target_id = ? AND ticket_id = ?
              AND ticket_count_prefix = ?
            """,
            (target_id, ticket_id, row.ticket_count_prefix),
        ).fetchone()
        next_version = int(version_row[0]) + 1
        connection.execute(
            """
            INSERT INTO research_ticket_results (
                id, target_id, ticket_id, draw_binding_id, result_version,
                draw_sha256, ticket_count_prefix, main_hit_count,
                special_hit_count, hit_numbers_json,
                legacy_reported_result_json, legacy_reported_result_sha256,
                prize_tier_id, result_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"result-{uuid.uuid4()}",
                target_id,
                ticket_id,
                draw_binding_id,
                next_version,
                draw.draw_sha256,
                row.ticket_count_prefix,
                row.main_hit_count,
                row.special_hit_count,
                normalized["hit_numbers_json"],
                normalized["legacy_reported_result_json"],
                normalized["legacy_reported_result_sha256"],
                row.prize_tier_id,
                result_sha256,
                _utc_now(),
            ),
        )
        inserted += 1
    return inserted


def _insert_or_verify_draw_binding(
    connection: sqlite3.Connection,
    value: DrawBindingInput,
) -> str:
    _require_sha256(value.draw_sha256, "draw_sha256")
    main_numbers_json = _validated_canonical_json(
        value.main_numbers_json,
        "main_numbers_json",
    )
    special_numbers_json = _validated_canonical_json(
        value.special_numbers_json,
        "special_numbers_json",
    )
    payload = _draw_payload(value)
    binding_id = f"draw-{_sha256(_canonical_json(payload))}"
    row = connection.execute(
        """
        SELECT lottery_type, draw_number, draw_date, main_numbers_json,
               special_numbers_json, draw_sha256, draw_data_version
        FROM research_draw_bindings
        WHERE id = ?
        """,
        (binding_id,),
    ).fetchone()
    expected = (
        value.lottery_type,
        value.draw_number,
        value.draw_date,
        main_numbers_json,
        special_numbers_json,
        value.draw_sha256,
        value.draw_data_version,
    )
    if row is not None:
        if tuple(row) != expected:
            raise ResearchConflictError("draw binding hash collision")
        return binding_id
    connection.execute(
        """
        INSERT INTO research_draw_bindings (
            id, lottery_type, draw_number, draw_date, main_numbers_json,
            special_numbers_json, draw_sha256, draw_data_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (binding_id, *expected, _utc_now()),
    )
    return binding_id


def _draw_payload(value: DrawBindingInput) -> dict[str, object]:
    return {
        "draw_data_version": value.draw_data_version,
        "draw_date": value.draw_date,
        "draw_number": value.draw_number,
        "draw_sha256": value.draw_sha256,
        "lottery_type": value.lottery_type,
        "main_numbers_json": _validated_canonical_json(
            value.main_numbers_json,
            "main_numbers_json",
        ),
        "special_numbers_json": _validated_canonical_json(
            value.special_numbers_json,
            "special_numbers_json",
        ),
    }


def _claim_idempotency(
    connection: sqlite3.Connection,
    *,
    operation_name: str,
    idempotency_key: str,
    request_sha256: str,
) -> None:
    if not idempotency_key.strip():
        raise ResearchRepositoryError("idempotency_key must not be empty")
    try:
        connection.execute(
            """
            INSERT INTO research_idempotency_keys (
                id, writer_role, operation_name, idempotency_key,
                request_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"idempotency-{uuid.uuid4()}",
                WRITER_ROLE,
                operation_name,
                idempotency_key,
                request_sha256,
                _utc_now(),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise DuplicateIdempotencyKeyError("idempotency key was already consumed") from exc


def _request_sha256(operation: str, payload: object) -> str:
    return _sha256(_canonical_json({"operation": operation, "payload": payload}))


def _validated_canonical_json(raw: str, label: str) -> str:
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ResearchRepositoryError(f"{label} must be valid JSON") from exc
    canonical = _canonical_json(decoded)
    if raw != canonical:
        raise ResearchRepositoryError(f"{label} must use canonical JSON serialization")
    return canonical


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ResearchRepositoryError(f"{label} must be a lowercase SHA-256 digest")


def _validate_page_limit(limit: int) -> None:
    if not 1 <= limit <= 1_000:
        raise ResearchRepositoryError("page limit must be between 1 and 1000")


def _is_busy_error(error: sqlite3.OperationalError) -> bool:
    message = str(error).casefold()
    return "locked" in message or "busy" in message


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def fetch_research_draw_bindings_for_dataset(
    connection: sqlite3.Connection,
    *,
    lottery_type: str,
    draw_data_version: str,
) -> tuple[list[tuple[str, str, str]], int]:
    """Read bounded draw bindings from the research store for dataset ingestion."""
    rows = connection.execute(
        """
        SELECT draw_number, draw_date, main_numbers_json
        FROM research_draw_bindings
        WHERE lottery_type = ?
          AND draw_data_version = ?
          AND draw_number != replace(draw_date, '-', '')
        ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
        """,
        (lottery_type, draw_data_version),
    ).fetchall()
    (total_count,) = connection.execute(
        "SELECT count(*) FROM research_draw_bindings "
        "WHERE lottery_type = ? AND draw_data_version = ?",
        (lottery_type, draw_data_version),
    ).fetchone()
    return (
        [(str(r[0]), str(r[1]), str(r[2])) for r in rows],
        int(total_count),
    )


__all__ = [
    "BUSY_TIMEOUT_MS",
    "IMMUTABLE_TABLE_NAMES",
    "WRITE_RETRY_ATTEMPTS",
    "WRITE_RETRY_BACKOFF_SECONDS",
    "ClosureInput",
    "CompletedTargetCursor",
    "CoverageCursor",
    "CoverageRow",
    "DrawBindingInput",
    "DuplicateIdempotencyKeyError",
    "QueryPage",
    "RankingCursor",
    "RankingRow",
    "ResearchConflictError",
    "ResearchRepositoryError",
    "ResearchStoreReport",
    "RunProgress",
    "RunSummaryInput",
    "SQLiteResearchRepository",
    "StrategySnapshotInput",
    "TargetCommitInput",
    "TargetCommitResult",
    "TicketCursor",
    "TicketInput",
    "TicketResultInput",
    "fetch_research_draw_bindings_for_dataset",
]
