from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from lottolab.research.b649_k20_paused_checkpoint_compatibility_bridge_r2 import (
    BASELINE_RESULT_RELATIVE_PATH,
    JOURNAL_NAME,
    RUN1_ID,
    RUN2_ID,
    TASK_ID,
    BridgeAuthority,
    BridgePaths,
    CompatibilityBridgeError,
    ExecutionAuthority,
    derive_bundle,
    write_bundle,
)


@dataclass(frozen=True)
class SyntheticCase:
    paths: BridgePaths
    authority: BridgeAuthority
    original_state_path: Path
    original_journal_path: Path
    source_path: Path


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _make_case(tmp_path: Path) -> SyntheticCase:
    repo_root = tmp_path.resolve()
    run_root = repo_root / ".task-data" / TASK_ID / "run1"
    output_dir = run_root.parent / "bridge-r2"
    run_root.mkdir(parents=True)

    source_path = run_root / "predicate-source.snapshot.py"
    source_bytes = b"synthetic predicate source\n"
    _write(source_path, source_bytes)
    baseline_path = repo_root / BASELINE_RESULT_RELATIVE_PATH
    baseline_bytes = b'{"synthetic":"baseline file bytes"}\n'
    _write(baseline_path, baseline_bytes)
    driver_path = run_root / "driver.py"
    driver_bytes = b"synthetic immutable driver\n"
    _write(driver_path, driver_bytes)
    source_sha = _sha256(source_bytes)
    baseline_file_sha = _sha256(baseline_bytes)
    baseline_normalized_sha = "a" * 64
    driver_sha = _sha256(driver_bytes)
    universe_sha = "b" * 64
    command = ["/usr/bin/env", "PYTHONDONTWRITEBYTECODE=1", "python", "driver.py", "run"]

    contract = {
        "TASK_ID": TASK_ID,
        "RUN_ROOT": str(run_root),
        "SOURCE_SNAPSHOT": str(source_path),
        "SOURCE_SHA256": source_sha,
        "SNAPSHOT_SHA256": source_sha,
        "BASELINE_SHA256": baseline_normalized_sha,
        "BASELINE_NORMALIZED_TICKETS_SHA256_INDEPENDENT": baseline_normalized_sha,
        "BASELINE_RESULT_FILE_SHA256": baseline_file_sha,
        "BASELINE_RESULT_PATH": BASELINE_RESULT_RELATIVE_PATH.as_posix(),
        "DRIVER_SHA256": driver_sha,
        "UNIVERSE_SHA256": universe_sha,
        "PROTECTED_RUN_ARGV": ["ruby", "task_checkpoint.rb", "--run", "--", *command],
    }
    contract_bytes = _json_bytes(contract)
    _write(run_root / "execution-contract.json", contract_bytes)

    total_attempts = 37_674_720
    completed_attempts = 4_844_448
    interval = 7_776
    rows: list[dict[str, Any]] = []
    previous = 0
    for index in range(completed_attempts // interval):
        last = previous + interval
        rows.append(
            {
                "RECORD_TYPE": "QUADRUPLE_COMPLETE",
                "TASK_ID": TASK_ID,
                "QUADRUPLE_INDEX": index,
                "PREVIOUS_COMPLETED_RAW_ATTEMPTS": previous,
                "COMPLETED_RAW_ATTEMPTS": last,
                "RAW": interval,
                "SOURCE_SHA256": source_sha,
                "BASELINE_SHA256": baseline_normalized_sha,
                "UNIVERSE_SHA256": universe_sha,
            }
        )
        previous = last
    original_journal = b"".join(_json_bytes(row) for row in rows)
    journal_path = run_root / "attempt-results.jsonl"
    _write(journal_path, original_journal)

    state = {
        "TASK_ID": TASK_ID,
        "STATUS": "SEARCHING",
        "SOURCE_SHA256": source_sha,
        "SOURCE_SNAPSHOT": str(source_path),
        "BASELINE_SHA256": baseline_normalized_sha,
        "DRIVER_SHA256": driver_sha,
        "COMPLETED_RAW_ATTEMPTS": completed_attempts,
        "NEXT_RAW_ATTEMPT": completed_attempts + 1,
        "TOTAL_RAW_ATTEMPTS": total_attempts,
        "JOURNAL_PREFIX_BYTES": len(original_journal),
        "JOURNAL_PREFIX_SHA256": _sha256(original_journal),
    }
    state_path = run_root / "state.json"
    _write(state_path, _json_bytes(state))
    _write(
        run_root / "writer.lock",
        _json_bytes(
            {
                "TASK_ID": TASK_ID,
                "WRITE_OWNERSHIP": "RELEASED_ON_STOP",
                "PID": 99_999_999,
            }
        ),
    )

    evidence: list[ExecutionAuthority] = []
    for index, execution_id in enumerate((RUN1_ID, RUN2_ID)):
        capture_path = (
            repo_root / ".fable" / "checkpoints" / TASK_ID / "captures" / f"{execution_id}.json"
        )
        record_path = (
            repo_root / ".fable" / "checkpoints" / TASK_ID / "executions" / f"{execution_id}.json"
        )
        capture = {
            "schema_version": 1,
            "command": command,
            "stdout": "",
            "stderr": "",
            "exit_status": "SIGNALED:15" if index == 0 else 1,
            "started_at": "2026-10-08T00:00:00Z",
            "ended_at": "2026-10-08T00:01:00Z",
        }
        capture_bytes = _json_bytes(capture)
        _write(capture_path, capture_bytes)
        record = {
            "schema_version": 1,
            "task_id": TASK_ID,
            "execution_id": execution_id,
            "pid": 12_345 + index,
            "status": "COMPLETED",
            "durable_capture_path": str(capture_path),
            "started_at": "2026-10-08T00:00:00Z",
            "ended_at": "2026-10-08T00:01:00Z",
            "parent_execution_id": None,
            "continuation_from_execution_id": None,
        }
        record_bytes = _json_bytes(record)
        _write(record_path, record_bytes)
        evidence.append(
            ExecutionAuthority(
                execution_id=execution_id,
                record_sha256=_sha256(record_bytes),
                capture_sha256=_sha256(capture_bytes),
                first_attempt=1 if index == 0 else 2_527_201,
                last_attempt=2_527_200 if index == 0 else completed_attempts,
            )
        )

    authority = BridgeAuthority(
        state_sha256=_sha256(state_path.read_bytes()),
        journal_sha256=_sha256(original_journal),
        source_sha256=source_sha,
        baseline_normalized_sha256=baseline_normalized_sha,
        baseline_file_sha256=baseline_file_sha,
        driver_sha256=driver_sha,
        completed_attempts=completed_attempts,
        total_attempts=total_attempts,
        checkpoint_interval=interval,
        journal_record_count=len(rows),
        executions=(evidence[0], evidence[1]),
    )
    return SyntheticCase(
        BridgePaths(repo_root=repo_root, run_root=run_root, output_dir=output_dir),
        authority,
        state_path,
        journal_path,
        source_path,
    )


def test_builds_fable_projection_with_verified_run_boundaries(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    state_before = _sha256(case.original_state_path.read_bytes())
    journal_before = _sha256(case.original_journal_path.read_bytes())

    bundle = derive_bundle(case.paths, case.authority)

    checkpoint = json.loads(bundle.checkpoint)
    rows = [json.loads(line) for line in bundle.journal.splitlines()]
    manifest = json.loads(bundle.provenance)
    assert checkpoint["scientific_status"] == "PAUSED_RESUMABLE"
    assert checkpoint["completed_attempts"] == 4_844_448
    assert checkpoint["next_expected_attempt"] == 4_844_449
    assert checkpoint["journal_record_count"] == 623
    assert checkpoint["journal_execution_ids"] == [RUN1_ID, RUN2_ID]
    assert len(rows) == 623
    assert sum(row["execution_id"] == RUN1_ID for row in rows) == 325
    assert sum(row["execution_id"] == RUN2_ID for row in rows) == 298
    assert rows[0]["first_attempt"] == 1
    assert rows[324]["last_attempt"] == 2_527_200
    assert rows[325]["first_attempt"] == 2_527_201
    assert rows[-1]["last_attempt"] == 4_844_448
    assert checkpoint["baseline_sha256"] == case.authority.baseline_file_sha256
    assert checkpoint["baseline_sha256"] != case.authority.baseline_normalized_sha256
    assert manifest["original_authority"]["baseline_file"]["normalized_tickets_sha256"] == (
        case.authority.baseline_normalized_sha256
    )
    assert manifest["original_driver_resume"]["resume_from_attempt"] == 4_844_449
    assert manifest["original_driver_resume"]["first_uncompleted_group_index"] == 623
    assert manifest["mutation_boundary"]["actual_run3_started"] is False
    assert _sha256(bundle.checkpoint) == bundle.checkpoint_sha256
    assert _sha256(bundle.journal) == bundle.journal_sha256
    assert _sha256(case.original_state_path.read_bytes()) == state_before
    assert _sha256(case.original_journal_path.read_bytes()) == journal_before


def test_rejects_tampered_source_and_execution_evidence(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    case.source_path.write_bytes(b"tampered source\n")
    with pytest.raises(CompatibilityBridgeError, match="predicate source snapshot SHA-256"):
        derive_bundle(case.paths, case.authority)

    second_case = _make_case(tmp_path / "second")
    capture_path = (
        second_case.paths.repo_root
        / ".fable"
        / "checkpoints"
        / TASK_ID
        / "captures"
        / f"{RUN2_ID}.json"
    )
    capture_path.write_bytes(capture_path.read_bytes() + b" ")
    with pytest.raises(CompatibilityBridgeError, match="RUN2 capture SHA-256"):
        derive_bundle(second_case.paths, second_case.authority)


def test_rejects_a_journal_gap_even_when_its_new_hash_is_supplied(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    lines = case.original_journal_path.read_bytes().splitlines()
    second = json.loads(lines[1])
    second["PREVIOUS_COMPLETED_RAW_ATTEMPTS"] += 1
    lines[1] = _json_bytes(second).rstrip(b"\n")
    journal_bytes = b"\n".join(lines) + b"\n"
    case.original_journal_path.write_bytes(journal_bytes)
    state = json.loads(case.original_state_path.read_bytes())
    state["JOURNAL_PREFIX_BYTES"] = len(journal_bytes)
    state["JOURNAL_PREFIX_SHA256"] = _sha256(journal_bytes)
    state_bytes = _json_bytes(state)
    case.original_state_path.write_bytes(state_bytes)
    altered_authority = replace(
        case.authority,
        journal_sha256=_sha256(journal_bytes),
        state_sha256=_sha256(state_bytes),
    )

    with pytest.raises(CompatibilityBridgeError, match="journal line 2 has a gap"):
        derive_bundle(case.paths, altered_authority)


def test_rejects_ambiguous_execution_lineage_and_live_writer(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    ambiguous = replace(
        case.authority, executions=(case.authority.executions[0], case.authority.executions[0])
    )
    with pytest.raises(CompatibilityBridgeError, match="execution boundaries differ"):
        derive_bundle(case.paths, ambiguous)

    lock_path = case.paths.run_root / "writer.lock"
    lock = json.loads(lock_path.read_bytes())
    lock["PID"] = os.getpid()
    lock_path.write_bytes(_json_bytes(lock))
    with pytest.raises(CompatibilityBridgeError, match="legacy writer PID is still live"):
        derive_bundle(case.paths, case.authority)


def test_write_is_create_only_and_keeps_artifacts_task_local(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    bundle = derive_bundle(case.paths, case.authority)

    write_bundle(case.paths, bundle)

    assert (case.paths.output_dir / JOURNAL_NAME).read_bytes() == bundle.journal
    with pytest.raises(CompatibilityBridgeError, match="already exists"):
        write_bundle(case.paths, bundle)
