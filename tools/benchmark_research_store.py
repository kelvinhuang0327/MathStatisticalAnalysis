"""Reproducible Phase-1A sustained-write/read benchmark.

This tool requires an explicit, noncanonical, outside-worktree data directory.
It never resolves or opens the production research-store locator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import threading
import time
from pathlib import Path

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.research import ResearchExecutionStatus, ResearchRunKind
from lottolab.infrastructure.persistence.research_repository import (
    DrawBindingInput,
    SQLiteResearchRepository,
    StrategySnapshotInput,
    TargetCommitInput,
    TicketInput,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    ResearchDataPaths,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _draw(draw_number: str, draw_date: str) -> DrawBindingInput:
    return DrawBindingInput(
        lottery_type="BIG_LOTTO",
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers_json="[1,2,3,4,5,6]",
        special_numbers_json="[49]",
        draw_sha256=_sha256(f"draw:{draw_number}:{draw_date}"),
        draw_data_version="benchmark-v1",
    )


def _tickets(count: int) -> tuple[TicketInput, ...]:
    return tuple(
        TicketInput(
            native_position=position,
            ordered_portfolio_position=position,
            canonical_ticket_json=(
                f'{{"main_numbers":[1,2,3,4,5,{position + 6}],'
                '"special_numbers":[49]}'
            ),
        )
        for position in range(1, count + 1)
    )


def run_benchmark(
    data_directory: Path,
    *,
    target_count: int,
    ticket_count: int,
) -> dict[str, object]:
    paths = ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / RESEARCH_DATABASE_FILENAME,
    )
    repository = SQLiteResearchRepository(paths)
    rule_id = repository.register_rule_contract(
        BIG_LOTTO_RULE_CONTRACT,
        idempotency_key="benchmark-rule",
    )
    run_id = repository.create_run(
        run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
        rule_contract_id=rule_id,
        input_dataset_identity="synthetic-benchmark-v1",
        input_dataset_sha256=_sha256("synthetic-benchmark-v1"),
        expected_target_count=target_count,
        producer_identity="tools/benchmark_research_store.py",
        execution_code_version="phase-1a",
        source_commit_oid="benchmark",
        idempotency_key="benchmark-run",
    )
    strategy_id = repository.register_strategy_snapshot(
        run_id,
        StrategySnapshotInput(
            lottery_type="BIG_LOTTO",
            strategy_id="synthetic-benchmark",
            strategy_version="1",
            source_commit_oid="benchmark",
            strategy_source_sha256=_sha256("synthetic-benchmark-strategy"),
            producer_identity="tools/benchmark_research_store.py",
            producer_version="1",
            runtime_fingerprint="local-python-sqlite",
            parameters_json="{}",
            seed_protocol="DETERMINISTIC",
            replicate=1,
            execution_code_version="phase-1a",
        ),
        idempotency_key="benchmark-strategy",
    )
    cutoff = _draw("000000", "2025-01-01")
    tickets = _tickets(ticket_count)
    stop_reader = threading.Event()
    reader_wait_ms: list[float] = []
    progress_counts: list[int] = []
    reader_errors: list[str] = []

    def read_progress() -> None:
        while not stop_reader.is_set():
            started = time.perf_counter()
            try:
                progress = repository.progress(run_id)
            except BaseException as exc:  # pragma: no cover - benchmark evidence
                reader_errors.append(type(exc).__name__)
                break
            reader_wait_ms.append((time.perf_counter() - started) * 1_000)
            progress_counts.append(progress.completed_target_count)

    reader = threading.Thread(target=read_progress, name="research-benchmark-reader")
    reader.start()
    commit_ms: list[float] = []
    started_loop = time.perf_counter()
    for index in range(target_count):
        target_started = time.perf_counter()
        repository.commit_target(
            TargetCommitInput(
                run_id=run_id,
                strategy_snapshot_id=strategy_id,
                target_order=index,
                input_dataset_identity="synthetic-benchmark-v1",
                input_dataset_sha256=_sha256("synthetic-benchmark-v1"),
                history_cutoff=cutoff,
                history_draw_count=3_149,
                source_history_order="DRAW_DATE_ASC,DRAW_NUMBER_ASC",
                target_draw=_draw(f"{index + 1:06d}", "2030-01-01"),
                causal_eligible=True,
                candidate_k=20,
                combination_count=1,
                ticket_count_prefix=20,
                tickets=tickets,
                execution_status=ResearchExecutionStatus.OK,
            ),
            idempotency_key=f"benchmark-target-{index}",
        )
        commit_ms.append((time.perf_counter() - target_started) * 1_000)
    loop_seconds = time.perf_counter() - started_loop
    stop_reader.set()
    reader.join(timeout=10)
    final_progress = repository.progress(run_id)
    projected_targets = 135 * 3_149
    return {
        "database_bytes": paths.database.stat().st_size,
        "final_completed_targets": final_progress.completed_target_count,
        "journal_mode": "DELETE",
        "mean_commit_ms_per_target": statistics.fmean(commit_ms),
        "median_commit_ms_per_target": statistics.median(commit_ms),
        "p95_commit_ms_per_target": sorted(commit_ms)[int(len(commit_ms) * 0.95) - 1],
        "projected_135x3149_target_count": projected_targets,
        "projected_135x3149_ticket_rows": projected_targets * ticket_count,
        "projected_write_hours_linear": (
            statistics.fmean(commit_ms) * projected_targets / 3_600_000
        ),
        "reader_error_types": reader_errors,
        "reader_observation_count": len(reader_wait_ms),
        "reader_progress_monotonic": progress_counts == sorted(progress_counts),
        "target_count": target_count,
        "ticket_count_per_target": ticket_count,
        "total_loop_seconds": loop_seconds,
        "wal_sidecar_present": Path(f"{paths.database}-wal").exists(),
        "worst_reader_wait_ms": max(reader_wait_ms, default=0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-directory", required=True, type=Path)
    parser.add_argument("--targets", type=int, default=1_000)
    parser.add_argument("--tickets", type=int, default=20)
    arguments = parser.parse_args()
    if not arguments.data_directory.is_absolute():
        parser.error("--data-directory must be absolute")
    if arguments.targets <= 0 or arguments.tickets <= 0:
        parser.error("--targets and --tickets must be positive")
    result = run_benchmark(
        arguments.data_directory,
        target_count=arguments.targets,
        ticket_count=arguments.tickets,
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
