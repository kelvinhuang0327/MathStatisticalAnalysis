"""Build a task-local Fable projection of the paused B649 V1 checkpoint."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

BRIDGE_ID = "B649_K20_PAUSED_CHECKPOINT_COMPATIBILITY_BRIDGE_R2"
TASK_ID = "B649_K20_313263888_FOUR_TICKET_CYCLE_FULL_FAMILY_R1"
RUN1_ID = f"{TASK_ID}_RUN1"
RUN2_ID = f"{TASK_ID}_RUN2"
FABLE_CONTRACT_COMMIT = "139274dc629be48ce97cf7cf480a5065d09c2057"
BASELINE_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)

CHECKPOINT_NAME = "fable-paused-checkpoint.json"
JOURNAL_NAME = "fable-compatible-journal.jsonl"
PROVENANCE_NAME = "bridge-provenance.json"


@dataclass(frozen=True)
class ExecutionAuthority:
    execution_id: str
    record_sha256: str
    capture_sha256: str
    first_attempt: int
    last_attempt: int


@dataclass(frozen=True)
class BridgeAuthority:
    state_sha256: str
    journal_sha256: str
    source_sha256: str
    baseline_normalized_sha256: str
    baseline_file_sha256: str
    driver_sha256: str
    completed_attempts: int
    total_attempts: int
    checkpoint_interval: int
    journal_record_count: int
    executions: tuple[ExecutionAuthority, ExecutionAuthority]


@dataclass(frozen=True)
class BridgePaths:
    repo_root: Path
    run_root: Path
    output_dir: Path


@dataclass(frozen=True)
class BridgeBundle:
    checkpoint: bytes
    journal: bytes
    provenance: bytes
    checkpoint_sha256: str
    journal_sha256: str


class CompatibilityBridgeError(ValueError):
    """Raised when original evidence cannot support an unambiguous projection."""


DEFAULT_AUTHORITY = BridgeAuthority(
    state_sha256="a8fdb78792096c7e24b7ad6af024f96d4140d61c1e3f1fa210135299ccfd7889",
    journal_sha256="818c1c942a99fc5311e712f77e2ef96d3683c39fe55f75d7e8aa1fc3a354eed7",
    source_sha256="97d73e8b9f81969051a03f6b5744d0d7ca0539ff1f70303ce92ddbb760e7134e",
    baseline_normalized_sha256="eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c",
    baseline_file_sha256="3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00",
    driver_sha256="6348fec9daa839753bf375aa3804a3ca67ed0717fec93c58463d2f01814fd2d7",
    completed_attempts=4_844_448,
    total_attempts=37_674_720,
    checkpoint_interval=7_776,
    journal_record_count=623,
    executions=(
        ExecutionAuthority(
            execution_id=RUN1_ID,
            record_sha256="0e703ca082c7b0b7d6d7ad809bcff03cee1f6a41b23c560c2f1a170980d124b3",
            capture_sha256="8b3053238ee8d56255367cb1610aeb4f45e3ed36d5430a34096e2d75f4df8ab9",
            first_attempt=1,
            last_attempt=2_527_200,
        ),
        ExecutionAuthority(
            execution_id=RUN2_ID,
            record_sha256="e6ed121030751847f2ab18bfa182a5c3f33be2fc7210d7ee4fa7d46573c89cba",
            capture_sha256="216b1dfe9078d1cd04c902ef3b13618dfe2fa76c3ffe88ef23ee4eea8b13dc9f",
            first_attempt=2_527_201,
            last_attempt=4_844_448,
        ),
    ),
)


def default_paths() -> BridgePaths:
    repo_root = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis").resolve()
    run_root = repo_root / ".task-data" / TASK_ID / "run1"
    return BridgePaths(repo_root, run_root, run_root.parent / "bridge-r2")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CompatibilityBridgeError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise CompatibilityBridgeError(f"{label} must be an integer")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompatibilityBridgeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CompatibilityBridgeError(f"{label} is not valid JSON") from error
    _require(isinstance(value, dict), f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _read_stable(path: Path, label: str) -> bytes:
    _require(path.is_absolute(), f"{label} path must be absolute")
    try:
        before = path.lstat()
        _require(stat.S_ISREG(before.st_mode), f"{label} must be a regular file")
        _require(not path.is_symlink(), f"{label} must not be a symlink")
        _require(path.resolve(strict=True) == path, f"{label} path resolves through a symlink")
        with path.open("rb") as stream:
            data = stream.read()
        after = path.lstat()
    except OSError as error:
        raise CompatibilityBridgeError(f"cannot read {label}: {path}") from error
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    _require(before_identity == after_identity, f"{label} changed while being read")
    _require(len(data) == after.st_size, f"{label} changed while being read")
    return data


def _check_sha(label: str, data: bytes, expected: str) -> str:
    actual = _sha256(data)
    _require(actual == expected, f"{label} SHA-256 does not match frozen authority")
    return actual


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _validate_writer_lock(data: bytes, task_id: str) -> dict[str, Any]:
    lock = _json_object(data, "legacy writer lock")
    _require(lock.get("TASK_ID") == task_id, "legacy writer lock task id is ambiguous")
    _require(lock.get("WRITE_OWNERSHIP") == "RELEASED_ON_STOP", "legacy writer is not released")
    pid = _integer(lock.get("PID"), "legacy writer lock PID")
    _require(pid > 0, "legacy writer lock PID is invalid")
    _require(not _process_is_alive(pid), "legacy writer PID is still live")
    return lock


def _validate_execution(
    authority: ExecutionAuthority,
    task_id: str,
    record_bytes: bytes,
    capture_bytes: bytes,
    capture_path: Path,
    expected_command: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _check_sha(f"{authority.execution_id} execution record", record_bytes, authority.record_sha256)
    _check_sha(f"{authority.execution_id} capture", capture_bytes, authority.capture_sha256)
    record = _json_object(record_bytes, f"{authority.execution_id} execution record")
    capture = _json_object(capture_bytes, f"{authority.execution_id} capture")
    required_record_keys = {
        "schema_version",
        "task_id",
        "execution_id",
        "pid",
        "status",
        "durable_capture_path",
        "started_at",
        "ended_at",
    }
    optional_record_keys = {
        "parent_execution_id",
        "continuation_from_execution_id",
        "continuation_checkpoint_sha256",
        "continuation_transition_sha256",
    }
    _require(required_record_keys <= record.keys(), "execution record is missing required fields")
    _require(
        record.keys() <= required_record_keys | optional_record_keys,
        "execution record has unknown fields",
    )
    _require(record.get("task_id") == task_id, "execution record task id is mismatched")
    _require(
        record.get("execution_id") == authority.execution_id, "execution record id is mismatched"
    )
    _require(record.get("status") == "COMPLETED", "execution record is not terminal")
    record_pid = _integer(record.get("pid"), "execution record PID")
    _require(record_pid > 0, "execution record PID is invalid")
    _require(
        record.get("durable_capture_path") == str(capture_path),
        "execution record capture path is mismatched",
    )
    capture_keys = {
        "schema_version",
        "command",
        "stdout",
        "stderr",
        "exit_status",
        "started_at",
        "ended_at",
    }
    _require(capture.keys() == capture_keys, "terminal capture schema is unsupported")
    _require(isinstance(capture.get("command"), list), "terminal capture command is invalid")
    _require(
        capture.get("command") == expected_command, "execution command differs from frozen RUN argv"
    )
    _require(isinstance(capture.get("stdout"), str), "terminal capture stdout is invalid")
    _require(isinstance(capture.get("stderr"), str), "terminal capture stderr is invalid")
    _require(
        bool(capture.get("started_at")) and bool(capture.get("ended_at")),
        "capture timestamps are missing",
    )
    return record, capture


def _validate_journal(
    original_journal: bytes,
    state: dict[str, Any],
    contract: dict[str, Any],
    authority: BridgeAuthority,
) -> tuple[bytes, list[dict[str, Any]], list[dict[str, int | str]]]:
    _require(original_journal.endswith(b"\n"), "original journal ends with an incomplete record")
    lines = original_journal.splitlines(keepends=True)
    _require(
        len(lines) == authority.journal_record_count, "original journal record count is ambiguous"
    )
    _require(
        state.get("JOURNAL_PREFIX_BYTES") == len(original_journal),
        "checkpoint journal byte count differs",
    )
    _require(
        state.get("JOURNAL_PREFIX_SHA256") == _sha256(original_journal),
        "checkpoint journal prefix hash differs",
    )

    source_sha = authority.source_sha256
    normalized_baseline_sha = authority.baseline_normalized_sha256
    universe_sha = contract.get("UNIVERSE_SHA256")
    expected_attempt: int = 1
    fable_rows: list[dict[str, Any]] = []
    run1_count = 0
    run2_count = 0
    for sequence, line in enumerate(lines, start=1):
        _require(
            line.endswith(b"\n") and not line.endswith(b"\r\n"),
            f"journal line {sequence} is not canonical LF",
        )
        original = _json_object(line[:-1], f"original journal line {sequence}")
        first: int = expected_attempt
        previous: int = first - 1
        last = _integer(
            original.get("COMPLETED_RAW_ATTEMPTS"), f"journal line {sequence} last attempt"
        )
        _require(
            original.get("RECORD_TYPE") == "QUADRUPLE_COMPLETE",
            f"journal line {sequence} is not complete",
        )
        _require(original.get("TASK_ID") == TASK_ID, f"journal line {sequence} task id differs")
        _require(
            original.get("QUADRUPLE_INDEX") == sequence - 1,
            f"journal line {sequence} order differs",
        )
        _require(
            original.get("PREVIOUS_COMPLETED_RAW_ATTEMPTS") == previous,
            f"journal line {sequence} has a gap",
        )
        _require(
            last == previous + authority.checkpoint_interval,
            f"journal line {sequence} attempt span differs",
        )
        _require(
            original.get("RAW") == authority.checkpoint_interval,
            f"journal line {sequence} raw count differs",
        )
        _require(
            original.get("SOURCE_SHA256") == source_sha,
            f"journal line {sequence} source hash differs",
        )
        _require(
            original.get("BASELINE_SHA256") == normalized_baseline_sha,
            f"journal line {sequence} baseline identity differs",
        )
        _require(
            original.get("UNIVERSE_SHA256") == universe_sha,
            f"journal line {sequence} universe hash differs",
        )

        if last <= authority.executions[0].last_attempt:
            execution_id = authority.executions[0].execution_id
            run1_count += 1
        elif first > authority.executions[0].last_attempt:
            execution_id = authority.executions[1].execution_id
            run2_count += 1
        else:
            raise CompatibilityBridgeError(
                f"journal line {sequence} crosses the RUN1/RUN2 boundary"
            )
        fable_rows.append(
            {
                "sequence": sequence,
                "first_attempt": first,
                "last_attempt": last,
                "status": "COMPLETED",
                "execution_id": execution_id,
                "source_sha256": source_sha,
                "baseline_sha256": authority.baseline_file_sha256,
            }
        )
        expected_attempt = last + 1

    _require(
        expected_attempt - 1 == authority.completed_attempts, "journal ends at the wrong attempt"
    )
    _require(run1_count == 325, "RUN1 journal ownership count is ambiguous")
    _require(run2_count == 298, "RUN2 journal ownership count is ambiguous")
    _require(
        fable_rows[0]["first_attempt"] == authority.executions[0].first_attempt
        and fable_rows[324]["last_attempt"] == authority.executions[0].last_attempt
        and fable_rows[325]["first_attempt"] == authority.executions[1].first_attempt
        and fable_rows[-1]["last_attempt"] == authority.executions[1].last_attempt,
        "journal execution boundaries differ from verified RUN1/RUN2 ranges",
    )
    journal = b"".join(
        (json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
        for row in fable_rows
    )
    segments = [
        {
            "execution_id": authority.executions[0].execution_id,
            "first_attempt": authority.executions[0].first_attempt,
            "last_attempt": authority.executions[0].last_attempt,
            "journal_records": run1_count,
        },
        {
            "execution_id": authority.executions[1].execution_id,
            "first_attempt": authority.executions[1].first_attempt,
            "last_attempt": authority.executions[1].last_attempt,
            "journal_records": run2_count,
        },
    ]
    return journal, fable_rows, segments


def derive_bundle(
    paths: BridgePaths, authority: BridgeAuthority = DEFAULT_AUTHORITY
) -> BridgeBundle:
    repo_root = paths.repo_root.resolve(strict=True)
    run_root = paths.run_root.resolve(strict=True)
    output_dir = paths.output_dir.absolute()
    _require(
        run_root == repo_root / ".task-data" / TASK_ID / "run1",
        "run root is outside the authorized task",
    )
    _require(output_dir == run_root.parent / "bridge-r2", "output directory is outside bridge-r2")
    _require(
        output_dir.parent.is_dir() and not output_dir.parent.is_symlink(),
        "bridge-r2 parent is unavailable",
    )
    _require(
        not output_dir.exists() and not output_dir.is_symlink(), "bridge-r2 output already exists"
    )

    state_path = run_root / "state.json"
    journal_path = run_root / "attempt-results.jsonl"
    contract_path = run_root / "execution-contract.json"
    driver_path = run_root / "driver.py"
    writer_lock_path = run_root / "writer.lock"
    state_bytes = _read_stable(state_path, "legacy checkpoint")
    original_journal = _read_stable(journal_path, "legacy journal")
    contract_bytes = _read_stable(contract_path, "execution contract")
    driver_bytes = _read_stable(driver_path, "scientific driver")
    writer_lock_bytes = _read_stable(writer_lock_path, "legacy writer lock")
    state = _json_object(state_bytes, "legacy checkpoint")
    contract = _json_object(contract_bytes, "execution contract")

    _check_sha("legacy checkpoint", state_bytes, authority.state_sha256)
    _check_sha("legacy journal", original_journal, authority.journal_sha256)
    _check_sha("scientific driver", driver_bytes, authority.driver_sha256)
    source_path = Path(str(contract.get("SOURCE_SNAPSHOT", "")))
    _require(
        source_path == run_root / "predicate-source.snapshot.py", "predicate snapshot path differs"
    )
    source_bytes = _read_stable(source_path, "predicate source snapshot")
    _check_sha("predicate source snapshot", source_bytes, authority.source_sha256)

    baseline_relative = Path(str(contract.get("BASELINE_RESULT_PATH", "")))
    _require(
        baseline_relative == BASELINE_RESULT_RELATIVE_PATH,
        "baseline result path differs from authority",
    )
    _require(
        not baseline_relative.is_absolute() and ".." not in baseline_relative.parts,
        "baseline path is unsafe",
    )
    baseline_path = repo_root / baseline_relative
    baseline_bytes = _read_stable(baseline_path, "baseline result file")
    baseline_file_sha = _check_sha(
        "baseline result file bytes", baseline_bytes, authority.baseline_file_sha256
    )
    _require(
        baseline_file_sha != authority.baseline_normalized_sha256,
        "baseline file SHA must remain distinct from normalized ticket digest",
    )

    _require(
        contract.get("TASK_ID") == TASK_ID and state.get("TASK_ID") == TASK_ID,
        "task identity differs",
    )
    _require(contract.get("RUN_ROOT") == str(run_root), "execution contract run root differs")
    _require(
        contract.get("SOURCE_SHA256") == authority.source_sha256, "contract source hash differs"
    )
    _require(
        contract.get("SNAPSHOT_SHA256") == authority.source_sha256, "contract snapshot hash differs"
    )
    _require(
        contract.get("BASELINE_SHA256") == authority.baseline_normalized_sha256,
        "contract baseline digest differs",
    )
    _require(
        contract.get("BASELINE_NORMALIZED_TICKETS_SHA256_INDEPENDENT")
        == authority.baseline_normalized_sha256,
        "contract normalized baseline digest differs",
    )
    _require(
        contract.get("BASELINE_RESULT_FILE_SHA256") == authority.baseline_file_sha256,
        "contract baseline file hash differs",
    )
    _require(
        contract.get("DRIVER_SHA256") == authority.driver_sha256, "contract driver hash differs"
    )
    _require(state.get("STATUS") == "SEARCHING", "legacy checkpoint status is unsupported")
    _require(
        state.get("SOURCE_SHA256") == authority.source_sha256, "checkpoint source hash differs"
    )
    _require(state.get("SOURCE_SNAPSHOT") == str(source_path), "checkpoint source snapshot differs")
    _require(
        state.get("BASELINE_SHA256") == authority.baseline_normalized_sha256,
        "checkpoint baseline digest differs",
    )
    _require(
        state.get("DRIVER_SHA256") == authority.driver_sha256, "checkpoint driver hash differs"
    )
    _require(
        state.get("COMPLETED_RAW_ATTEMPTS") == authority.completed_attempts,
        "checkpoint cursor differs",
    )
    _require(
        state.get("NEXT_RAW_ATTEMPT") == authority.completed_attempts + 1,
        "checkpoint next attempt differs",
    )
    _require(
        state.get("TOTAL_RAW_ATTEMPTS") == authority.total_attempts, "checkpoint total differs"
    )

    lock = _validate_writer_lock(writer_lock_bytes, TASK_ID)
    command_value = contract.get("PROTECTED_RUN_ARGV")
    _require(isinstance(command_value, list), "protected argv is invalid")
    command_items = cast(list[Any], command_value)
    _require(all(isinstance(value, str) for value in command_items), "protected argv is invalid")
    command_vector = cast(list[str], command_items)
    _require(command_vector.count("--") == 1, "protected argv boundary is ambiguous")
    expected_command = command_vector[command_vector.index("--") + 1 :]
    _require(bool(expected_command), "protected command is empty")

    execution_evidence: list[dict[str, Any]] = []
    captures: dict[str, dict[str, Any]] = {}
    for execution in authority.executions:
        record_path = (
            repo_root
            / ".fable"
            / "checkpoints"
            / TASK_ID
            / "executions"
            / f"{execution.execution_id}.json"
        )
        capture_path = (
            repo_root
            / ".fable"
            / "checkpoints"
            / TASK_ID
            / "captures"
            / f"{execution.execution_id}.json"
        )
        record_bytes = _read_stable(record_path, f"{execution.execution_id} execution record")
        capture_bytes = _read_stable(capture_path, f"{execution.execution_id} capture")
        record, capture = _validate_execution(
            execution, TASK_ID, record_bytes, capture_bytes, capture_path, expected_command
        )
        if execution.execution_id == RUN2_ID:
            _require(capture.get("exit_status") == 1, "RUN2 did not end at the verified pause exit")
        execution_evidence.append(
            {
                "execution_id": execution.execution_id,
                "record_path": str(record_path),
                "record_sha256": _sha256(record_bytes),
                "capture_path": str(capture_path),
                "capture_sha256": _sha256(capture_bytes),
                "record_status": record["status"],
                "capture_exit_status": capture["exit_status"],
            }
        )
        captures[execution.execution_id] = capture

    projected_journal, projected_rows, segments = _validate_journal(
        original_journal, state, contract, authority
    )
    projected_journal_sha = _sha256(projected_journal)
    projected_checkpoint = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "scientific_status": "PAUSED_RESUMABLE",
        "completed_attempts": authority.completed_attempts,
        "total_attempts": authority.total_attempts,
        "next_expected_attempt": authority.completed_attempts + 1,
        "journal_path": str(output_dir / JOURNAL_NAME),
        "journal_prefix_sha256": projected_journal_sha,
        "journal_record_count": len(projected_rows),
        "journal_execution_ids": [item.execution_id for item in authority.executions],
        "source_path": str(source_path),
        "source_sha256": authority.source_sha256,
        "baseline_path": str(baseline_path),
        "baseline_sha256": baseline_file_sha,
    }
    checkpoint_bytes = (json.dumps(projected_checkpoint, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    checkpoint_sha = _sha256(checkpoint_bytes)

    manifest = {
        "bridge_id": BRIDGE_ID,
        "bridge_scope": "TASK_LOCAL",
        "fable_contract_commit": FABLE_CONTRACT_COMMIT,
        "fable_contract_files_modified": False,
        "original_authority": {
            "task_id": TASK_ID,
            "run_root": str(run_root),
            "checkpoint": {
                "path": str(state_path),
                "sha256": _sha256(state_bytes),
                "legacy_status": state["STATUS"],
            },
            "journal": {
                "path": str(journal_path),
                "sha256": _sha256(original_journal),
                "bytes": len(original_journal),
                "records": len(lines := original_journal.splitlines()),
            },
            "execution_contract": {"path": str(contract_path), "sha256": _sha256(contract_bytes)},
            "executions": execution_evidence,
            "attempt_segments": segments,
            "source": {"path": str(source_path), "sha256": authority.source_sha256},
            "baseline_file": {
                "path": str(baseline_path),
                "sha256_file_bytes": baseline_file_sha,
                "normalized_tickets_sha256": authority.baseline_normalized_sha256,
                "digests_are_distinct": True,
            },
            "writer_lock": {
                "path": str(writer_lock_path),
                "sha256": _sha256(writer_lock_bytes),
                "write_ownership": lock["WRITE_OWNERSHIP"],
                "pid_observed_absent": True,
            },
        },
        "fable_projection": {
            "application_state_path": str(output_dir / CHECKPOINT_NAME),
            "application_state_sha256": checkpoint_sha,
            "journal_path": str(output_dir / JOURNAL_NAME),
            "journal_prefix_sha256": projected_journal_sha,
            "journal_record_count": len(projected_rows),
            "journal_execution_ids": [item.execution_id for item in authority.executions],
            "completed_attempts": authority.completed_attempts,
            "next_attempt": authority.completed_attempts + 1,
            "source_sha256": authority.source_sha256,
            "baseline_sha256_file_bytes": baseline_file_sha,
        },
        "original_driver_resume": {
            "driver_path": str(driver_path),
            "driver_sha256": authority.driver_sha256,
            "command_from_predecessor_capture": captures[RUN2_ID]["command"],
            "original_state_path": str(state_path),
            "original_journal_path": str(journal_path),
            "fable_projection_is_not_the_driver_input": True,
            "resume_from_attempt": authority.completed_attempts + 1,
            "first_uncompleted_group_index": authority.completed_attempts
            // authority.checkpoint_interval,
            "total_group_count": authority.total_attempts // authority.checkpoint_interval,
            "original_journal_record_count": len(lines),
            "actual_run3_started": False,
        },
        "mutation_boundary": {
            "original_checkpoint_modified": False,
            "original_journal_modified": False,
            "original_records_modified": False,
            "original_captures_modified": False,
            "actual_run3_started": False,
        },
    }
    provenance_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return BridgeBundle(
        checkpoint_bytes, projected_journal, provenance_bytes, checkpoint_sha, projected_journal_sha
    )


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            _require(written > 0, f"short write while creating {path.name}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bundle(paths: BridgePaths, bundle: BridgeBundle) -> None:
    _require(
        not paths.output_dir.exists() and not paths.output_dir.is_symlink(),
        "bridge-r2 output already exists",
    )
    paths.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    _write_exclusive(paths.output_dir / CHECKPOINT_NAME, bundle.checkpoint)
    _write_exclusive(paths.output_dir / JOURNAL_NAME, bundle.journal)
    _write_exclusive(paths.output_dir / PROVENANCE_NAME, bundle.provenance)
    directory_fd = os.open(paths.output_dir, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def main() -> None:
    paths = default_paths()
    bundle = derive_bundle(paths)
    write_bundle(paths, bundle)
    print(
        json.dumps(
            {
                "bridge": BRIDGE_ID,
                "application_state_path": str(paths.output_dir / CHECKPOINT_NAME),
                "application_state_sha256": bundle.checkpoint_sha256,
                "journal_path": str(paths.output_dir / JOURNAL_NAME),
                "journal_sha256": bundle.journal_sha256,
                "provenance_path": str(paths.output_dir / PROVENANCE_NAME),
                "run3_started": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
