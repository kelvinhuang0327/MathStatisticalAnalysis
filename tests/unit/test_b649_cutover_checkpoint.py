"""Checkpoint acceptance using fixture files and an allowlisted observation runner."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shlex
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest
import tools.b649_cutover_checkpoint as checkpoint

NOW = datetime(2026, 9, 9, 3, 0, tzinfo=UTC)
HEAD = "1" * 40
TREE = "2" * 40
OLD_HEAD = "3" * 40
LABEL = "com.lottolab.checkpoint-fixture"
DOMAIN = "gui/501"
HEALTH_SCHEMA = "b649-goalc-local-scheduler-health-v1"


@dataclass
class Harness:
    root: Path
    calls: list[tuple[str, ...]] = field(default_factory=lambda: list[tuple[str, ...]]())
    loaded: bool = True
    disabled: bool = False
    disabled_output: str | None = None
    loaded_old: bool = False
    process_error: bool = False
    lsof_error: bool = False
    job_error: bool = False
    rollback_path: Path | None = None
    process_rows: list[str] = field(
        default_factory=lambda: ["900001 1 501 S /usr/bin/fixture-shell"]
    )
    file_rows: list[str] = field(default_factory=lambda: ["p900001", "fcwd", "n/fixture-home"])

    @property
    def successor(self) -> Path:
        return self.root / "successor with spaces"

    @property
    def rollback(self) -> Path:
        return self.rollback_path or self.root / "rollback"

    def use_production_rollback_worktree(self, head: str = OLD_HEAD) -> Path:
        target = self.root / f"B649_PRODUCTION_{head}"
        target.mkdir()
        self.rollback_path = target
        return target

    @property
    def backup(self) -> Path:
        return self.root / "rollback.plist"

    @property
    def plist(self) -> Path:
        return self.root / "live.plist"

    @property
    def health(self) -> Path:
        return self.root / "health.json"

    @property
    def database(self) -> Path:
        return self.root / "fixture.db"

    @property
    def interpreter(self) -> str:
        return str(self.root / "venv/bin/python")

    def binding(self, source: Path | None = None) -> dict[str, object]:
        source = source or self.successor
        return {
            "Label": LABEL,
            "WorkingDirectory": str(source),
            "ProgramArguments": [
                self.interpreter,
                str(source / "tools/b649_goalc_local_scheduler.py"),
                "run",
            ],
            "StartInterval": 300,
            "EnvironmentVariables": {"PYTHONPATH": str(source / "src")},
        }

    def launch_text(self) -> str:
        source = self.rollback if self.loaded_old else self.successor
        return f"""{DOMAIN}/{LABEL} = {{
    path = {self.plist}
    type = LaunchAgent
    state = not running
    program = {self.interpreter}
    arguments = {{
        {self.interpreter}
        {source}/tools/b649_goalc_local_scheduler.py
        run
    }}
    environment = {{
        PYTHONPATH => {source}/src
        PYTHONDONTWRITEBYTECODE => 1
    }}
    working directory = {source}
    last exit code = 0
    run interval = 300 seconds
}}
"""

    def __call__(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        args = tuple(argv)
        self.calls.append(args)
        if args[0] == "git":
            assert args[1:3] == ("-c", "core.fsmonitor=false")
            args = ("git", *args[3:])
        if args[:2] == ("git", "--no-optional-locks"):
            assert args[2] == "-C"
            assert args[4] == "rev-parse"
            assert Path(args[3]) in (self.successor, self.rollback)
            if args[5:] == ("--show-toplevel",):
                out = args[3]
            else:
                assert args[5:7] == ("--verify", "--end-of-options")
                assert args[7] in ("HEAD", "HEAD^{tree}", "refs/heads/successor^{commit}")
                out = (
                    OLD_HEAD
                    if Path(args[3]) == self.rollback
                    else (TREE if args[7] == "HEAD^{tree}" else HEAD)
                )
        elif args == ("git", "check-ref-format", "refs/heads/successor"):
            out = ""
        elif args == ("launchctl", "print", f"{DOMAIN}/{LABEL}"):
            if self.job_error:
                return subprocess.CompletedProcess(args, 1, "", "Operation not permitted")
            if not self.loaded:
                return subprocess.CompletedProcess(
                    args,
                    113,
                    "",
                    f'Bad request.\nCould not find service "{LABEL}" in domain for user gui: 501\n',
                )
            out = self.launch_text()
        elif args == ("launchctl", "print-disabled", DOMAIN):
            out = (
                self.disabled_output
                if self.disabled_output is not None
                else f'disabled services = {{\n    "{LABEL}" => {str(self.disabled).lower()}\n}}\n'
            )
        elif args == ("ps", "-ww", "-axo", "pid=,ppid=,uid=,stat=,command="):
            if self.process_error:
                return subprocess.CompletedProcess(args, 1, "", "process enumeration denied")
            out = "\n".join(self.process_rows)
        elif args == ("lsof", "-nP", "-a", "-u", "501", "-F", "pfn"):
            if self.lsof_error:
                return subprocess.CompletedProcess(args, 0, "", "lsof: cannot stat filesystem")
            out = "\n".join(self.file_rows)
        else:
            raise AssertionError(f"unexpected command (possible mutation): {args}")
        return subprocess.CompletedProcess(args, 0, out + "\n", "")

    def argv(self, phase: str) -> list[str]:
        values: dict[str, str] = {"expected-label": LABEL, "launch-domain": DOMAIN}
        if phase in ("pre-cutover", "post-load"):
            values.update(
                {
                    "expected-successor-worktree": str(self.successor),
                    "expected-successor-head": HEAD,
                    "plist-path": str(self.plist),
                }
            )
        if phase in ("pre-cutover", "post-unload"):
            values.update(
                {
                    "expected-rollback-worktree": str(self.rollback),
                    "expected-rollback-head": OLD_HEAD,
                    "primary-lock-path": str(self.root / "primary.lock"),
                    "shadow-lock-path": str(self.root / "shadow.lock"),
                }
            )
        if phase == "pre-cutover":
            values.update(
                {
                    "expected-successor-tree": TREE,
                    "expected-successor-ref": "refs/heads/successor",
                    "expected-rollback-backup-path": str(self.backup),
                    "expected-rollback-backup-sha256": hashlib.sha256(
                        plistlib.dumps(self.binding(self.rollback))
                    ).hexdigest(),
                    "expected-db-schema": "3",
                    "db-path": str(self.database),
                }
            )
        if phase == "post-load":
            values.update(
                {
                    "health-path": str(self.health),
                    "expected-interpreter": self.interpreter,
                    "expected-script-path": str(
                        self.successor / "tools/b649_goalc_local_scheduler.py"
                    ),
                    "expected-pythonpath": str(self.successor / "src"),
                    "expected-start-interval": "300",
                    "expected-health-schema": HEALTH_SCHEMA,
                    "expected-health-state": "PREDRAW_READY",
                    "expected-readiness": "true",
                    "max-health-age-seconds": "900",
                }
            )
        return [phase, *(part for key, value in values.items() for part in ("--" + key, value))]

    def add_process(
        self,
        command: str,
        *,
        state: str = "S",
        cwd: str | None = "/fixture-home",
        ppid: int = 1,
        files: Sequence[str] = (),
        executable_file: str | None = None,
        additional_executable_files: Sequence[str] = (),
    ) -> int:
        pid = 900001 + len(self.process_rows)
        self.process_rows.append(f"{pid} {ppid} 501 {state} {command}")
        if cwd is not None or files or executable_file is not None or additional_executable_files:
            self.file_rows.append(f"p{pid}")
        if cwd is not None:
            self.file_rows.extend(["fcwd", f"n{cwd}"])
        if executable_file is not None:
            self.file_rows.extend(["ftxt", f"n{executable_file}"])
        for path in additional_executable_files:
            self.file_rows.extend(["ftxt", f"n{path}"])
        for path in files:
            self.file_rows.extend(["f3", f"n{path}"])
        return pid


def _git_executable_path() -> str:
    git_executable = shutil.which("git")
    assert git_executable is not None
    return str(Path(git_executable).resolve(strict=True))


def _target_git_admin_metadata(harness: Harness) -> tuple[Path, Path]:
    target = harness.use_production_rollback_worktree()
    git_admin = harness.root / ".git" / "worktrees" / target.name
    git_admin.mkdir(parents=True)
    (git_admin / "index").touch()
    (target / ".git").write_text(f"gitdir: {git_admin}\n", encoding="utf-8")
    return target, git_admin


def _protected_task_checkpoint_command(harness: Harness, *, run: bool = True) -> str:
    mode = "--run" if run else "--inspect"
    return (
        "ruby /opt/fable-method/scripts/task_checkpoint.rb "
        f"{mode} --repo /repo --worktree {harness.rollback} "
        "--task-id B649_TEST_WRAPPER_ANCESTOR "
        "--execution-id focused-test -- "
        "python tools/b649_protected_cutover.py rollback"
    )


def _add_protected_task_checkpoint_ancestor(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    command: str | None = None,
) -> tuple[int, int]:
    wrapper_pid = 990001
    invocation_pid = 990002
    supervisor_pid = 990003
    harness.process_rows.extend(
        [
            f"{invocation_pid} {supervisor_pid} 501 S python tools/b649_cutover_checkpoint.py",
            f"{supervisor_pid} {wrapper_pid} 501 S "
            "python tools/b649_protected_cutover.py rollback",
            f"{wrapper_pid} 1 501 S {command or _protected_task_checkpoint_command(harness)}",
        ]
    )
    harness.file_rows.extend(
        [
            f"p{invocation_pid}",
            "fcwd",
            "n/fixture-home",
            f"p{supervisor_pid}",
            "fcwd",
            "n/fixture-home",
            f"p{wrapper_pid}",
            "fcwd",
            "n/fixture-home",
        ]
    )
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: invocation_pid)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: supervisor_pid)
    return wrapper_pid, supervisor_pid


def _verified_protected_execution(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    supervisor_pid: int,
) -> checkpoint.ControlledExecution:
    owner_command = _protected_task_checkpoint_command(harness).split(" -- ", maxsplit=1)[1]
    execution = checkpoint.ControlledExecution(
        claim_root=harness.root,
        task_key=checkpoint.PROTECTED_TASK_KEY,
        execution_id="e" * 64,
        owner_id="fixture-owner",
        child_argv=(),
        owner_argv=tuple(shlex.split(owner_command)),
        owner_cwd="/fixture-home",
        sources=((str(harness.rollback), OLD_HEAD, TREE),),
    )

    def verify_fixture_execution(
        _self: checkpoint.ControlledExecution,
        _processes: dict[int, checkpoint.Process],
        _uid: int,
    ) -> checkpoint.Record:
        return {"supervisor_pid": supervisor_pid}

    monkeypatch.setattr(
        checkpoint.ControlledExecution,
        "verify",
        verify_fixture_execution,
    )
    return execution


def _protected_process_snapshot(
    harness: Harness, execution: checkpoint.ControlledExecution
) -> checkpoint.Record:
    args = checkpoint.parser().parse_args(harness.argv("post-unload"))
    return checkpoint.process_snapshot(args, harness, execution=execution)


@pytest.fixture
def harness() -> Iterator[Harness]:
    # Pytest's existing cache is the only parent used for temporary fixtures;
    # the context manager removes the entire fixture, including SQLite sidecars.
    cache = Path(__file__).resolve().parents[2] / ".pytest_cache"
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="b649-checkpoint-", dir=cache) as temporary:
        fixture = Harness(Path(temporary))
        fixture.successor.mkdir()
        fixture.rollback.mkdir()
        fixture.plist.write_bytes(plistlib.dumps(fixture.binding()))
        fixture.backup.write_bytes(plistlib.dumps(fixture.binding(fixture.rollback)))
        fixture.health.write_text(
            json.dumps(
                {
                    "label": LABEL,
                    "schema_version": HEALTH_SCHEMA,
                    "source_worktree": str(fixture.successor),
                    "observed_source_head": HEAD,
                    "finished_at": NOW.isoformat(),
                    "current_status": "PREDRAW_READY",
                    "ready_before_draw": True,
                    "error_message": None,
                    "error_class": None,
                }
            )
        )
        connection = sqlite3.connect(fixture.database)
        try:
            connection.execute("CREATE TABLE schema_migrations (version INTEGER, name, checksum)")
            connection.execute("INSERT INTO schema_migrations VALUES (3, 'fixture', 'checksum')")
            connection.execute("CREATE TABLE draws (private_value)")
            connection.execute("INSERT INTO draws VALUES ('must never be inspected')")
            connection.commit()
        finally:
            connection.close()
        yield fixture


def execute(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    phase: str,
    *,
    argv: list[str] | None = None,
) -> tuple[int, checkpoint.Record]:
    code = checkpoint.main(argv or harness.argv(phase), runner=harness, now=NOW)
    output = capsys.readouterr()
    assert not output.err
    result = checkpoint.object_record(json.loads(output.out))
    assert result["phase"] == phase
    assert (code == 0) == (result["status"] == "PASS")
    assert isinstance(result["checks"], dict)
    assert isinstance(result["failures"], list)
    return code, result


def observation(result: checkpoint.Record, name: str) -> checkpoint.Record:
    entry = checkpoint.object_record(checkpoint.object_record(result["checks"])[name])
    return checkpoint.object_record(entry["observed"])


def test_pre_cutover_exact_backup_pass(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    code, result = execute(harness, capsys, "pre-cutover")
    assert code == 0, result
    assert observation(result, "db_metadata")["schema_version"] == 3
    assert (
        observation(result, "live_plist")["sha256"]
        == hashlib.sha256(harness.plist.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("defect", ["missing", "hash"])
def test_pre_cutover_rollback_gate(
    harness: Harness, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    if defect == "missing":
        harness.backup.unlink()
    else:
        harness.backup.write_bytes(b"wrong backup")
    code, result = execute(harness, capsys, "pre-cutover")
    assert code == 1
    assert "rollback_backup_sha256" in cast(list[str], result["failures"])


def test_required_backup_hash_cannot_be_omitted(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    args = harness.argv("pre-cutover")
    index = args.index("--expected-rollback-backup-sha256")
    del args[index : index + 2]
    code, _ = execute(harness, capsys, "pre-cutover", argv=args)
    assert code == 2
    assert not harness.calls


def test_post_unload_absent_pass(harness: Harness, capsys: pytest.CaptureFixture[str]) -> None:
    harness.loaded = False
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result
    for role in ("primary", "scheduler", "shadow", "runtime"):
        assert observation(result, f"old_{role}_ownership")["classification"] == "ABSENT"
    assert {call[0] for call in harness.calls} == {"git", "launchctl", "ps", "lsof"}


@pytest.mark.parametrize(
    ("role", "script"),
    [
        ("primary", "b649_operational_prediction_loop.py"),
        ("scheduler", "b649_goalc_local_scheduler.py"),
        ("shadow", "b649_pair_rule_forward_shadow.py"),
    ],
)
def test_post_unload_old_process_remains(
    harness: Harness, capsys: pytest.CaptureFixture[str], role: str, script: str
) -> None:
    harness.loaded = False
    harness.add_process(f"python {harness.rollback}/tools/{script}")
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, f"old_{role}_ownership")["classification"] == "PRESENT"
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_shadow_after_primary_lock_release(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run",
        files=[str(harness.root / "shadow.lock")],
    )
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_primary_ownership")["classification"] == "ABSENT"
    assert observation(result, "old_shadow_ownership")["classification"] == "PRESENT"


@pytest.mark.parametrize("defect", ["ps", "lsof", "coverage", "relative", "malformed"])
def test_unverifiable_ownership_fails(
    harness: Harness, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    harness.loaded = False
    if defect == "ps":
        harness.process_error = True
    elif defect == "lsof":
        harness.lsof_error = True
    elif defect == "coverage":
        harness.file_rows = []
    elif defect == "relative":
        harness.add_process("python tools/b649_goalc_local_scheduler.py run")
    else:
        harness.process_rows = ["malformed process output"]
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    entry = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["old_runtime_ownership"]
    )
    assert entry["status"] == "FAIL"


def test_cwd_open_files_descendants_and_custom_identity(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    parent = harness.add_process("python -m custom_hook", cwd=str(harness.rollback))
    child = harness.add_process("python worker.py", ppid=parent)
    opened = harness.add_process("python wrapper.py", files=[str(harness.rollback / "src/mod.py")])
    args = [*harness.argv("post-unload"), "--old-shadow-identity", "custom_hook"]
    code, result = execute(harness, capsys, "post-unload", argv=args)
    assert code == 1
    assert observation(result, "old_shadow_ownership")["pids"] == [parent]
    assert observation(result, "old_runtime_ownership")["pids"] == [parent, child, opened]


def test_passive_git_fsmonitor_on_legacy_worktree_is_not_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    target, git_admin = _target_git_admin_metadata(harness)
    git_executable = _git_executable_path()
    pid = harness.add_process(
        f"git -C {target} fsmonitor--daemon run",
        files=[str(git_admin / "index")],
        executable_file=git_executable,
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 0, result
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "ABSENT"
    assert runtime["pids"] == []
    assert pid not in cast(list[int], runtime["pids"])


def test_fsmonitor_metadata_with_wrong_worktree_link_remains_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    target, _ = _target_git_admin_metadata(harness)
    wrong_admin = harness.root / "unrelated" / target.name
    wrong_admin.mkdir(parents=True)
    (wrong_admin / "index").touch()
    pid = harness.add_process(
        "git fsmonitor--daemon run",
        files=[str(wrong_admin / "index")],
        executable_file=_git_executable_path(),
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert pid in cast(list[int], runtime["pids"])


def test_fsmonitor_with_incomplete_cwd_evidence_remains_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    harness.add_process(
        "git fsmonitor--daemon run",
        cwd=None,
        files=[str(git_admin / "index")],
        executable_file=_git_executable_path(),
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_runtime_ownership")["classification"] == "UNVERIFIABLE"


@pytest.mark.parametrize(
    "command",
    [
        "python -c 'git fsmonitor--daemon run'",
        "/tmp/fake-git fsmonitor--daemon run",
        "git-fsmonitor--daemon run",
    ],
)
def test_spoofed_fsmonitor_command_remains_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    harness.loaded = False
    pid = harness.add_process(command, cwd=str(harness.rollback))

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert pid in cast(list[int], runtime["pids"])


def test_verified_zombie_does_not_create_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    command = f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
    pid = harness.add_process(command, state="Z+", cwd=None)

    code, result = execute(harness, capsys, "post-unload")

    assert code == 0, result
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [pid]
    assert snapshot["processes"] == [
        {
            "pid": pid,
            "ppid": 1,
            "uid": 501,
            "command": command,
            "state": "Z+",
            "cwd": None,
            "files": [],
        }
    ]
    assert observation(result, "old_runtime_ownership")["classification"] == "ABSENT"


def test_live_defunct_argv_is_not_treated_as_zombie(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    pid = harness.add_process("<defunct>", state="S", cwd=str(harness.rollback))

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert pid in cast(list[int], runtime["pids"])


def test_zombie_with_open_file_evidence_remains_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    pid = harness.add_process(
        "<defunct>", state="Z", cwd=None, files=[str(harness.rollback / "src/mod.py")]
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [pid]
    assert snapshot["uncertainties"] == [
        f"PID {pid}: zombie has inconsistent cwd/open-file evidence"
    ]
    assert observation(result, "old_runtime_ownership")["classification"] == "UNVERIFIABLE"


def test_zombie_parent_does_not_propagate_runtime_ownership(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    zombie = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run",
        state="Z",
        cwd=None,
    )
    harness.add_process("python worker.py", ppid=zombie)

    code, result = execute(harness, capsys, "post-unload")

    assert code == 0, result
    assert observation(result, "old_runtime_ownership")["classification"] == "ABSENT"


def test_malformed_process_state_fails_closed(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.process_rows.append("900099 1 501 ? /usr/bin/fixture-shell")

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    snapshot_check = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["process_snapshot"]
    )
    assert snapshot_check["status"] == "FAIL"
    assert "process table" in str(snapshot_check["error"])
    assert observation(result, "old_runtime_ownership")["classification"] == "UNVERIFIABLE"


def test_task_checkpoint_run_ancestor_needs_claim_bound_owner_proof(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    spoofed_command = _protected_task_checkpoint_command(harness).replace(
        "/opt/fable-method/scripts/task_checkpoint.rb",
        "/tmp/untrusted/task_checkpoint.rb",
    )
    wrapper_pid, _ = _add_protected_task_checkpoint_ancestor(
        harness, monkeypatch, command=spoofed_command
    )

    code, result = execute(harness, capsys, "post-unload")

    runtime = observation(result, "old_runtime_ownership")
    assert code == 1, result
    assert runtime["classification"] == "PRESENT"
    assert wrapper_pid in cast(list[int], runtime["pids"])


def test_claim_bound_task_checkpoint_run_ancestor_is_not_runtime_owner(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper_pid, supervisor_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    execution = _verified_protected_execution(
        harness, monkeypatch, supervisor_pid=supervisor_pid
    )

    snapshot = _protected_process_snapshot(harness, execution)

    runtime = checkpoint.object_record(snapshot["runtime"])
    assert runtime["classification"] == "ABSENT"
    assert wrapper_pid not in cast(list[int], runtime["pids"])


def test_non_ancestor_task_checkpoint_run_string_remains_runtime_owner(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    wrapper_pid = harness.add_process(_protected_task_checkpoint_command(harness))
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 990002)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: 990003)

    code, result = execute(harness, capsys, "post-unload")

    runtime = observation(result, "old_runtime_ownership")
    assert code == 1
    assert runtime["classification"] == "PRESENT"
    assert wrapper_pid in cast(list[int], runtime["pids"])


def test_task_checkpoint_ancestor_without_run_mode_remains_runtime_owner(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _add_protected_task_checkpoint_ancestor(
        harness, monkeypatch, command=_protected_task_checkpoint_command(harness, run=False)
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_protected_wrapper_does_not_hide_live_scheduler(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    wrapper_pid, _ = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    scheduler_pid = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run", ppid=wrapper_pid
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    assert scheduler_pid in cast(
        list[int], observation(result, "old_runtime_ownership")["pids"]
    )


def test_protected_wrapper_preserves_passive_fsmonitor_exemption(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid, supervisor_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    harness.add_process(
        "git fsmonitor--daemon run",
        ppid=wrapper_pid,
        files=[str(git_admin / "index")],
        executable_file=_git_executable_path(),
    )

    execution = _verified_protected_execution(
        harness, monkeypatch, supervisor_pid=supervisor_pid
    )
    snapshot = _protected_process_snapshot(harness, execution)

    assert checkpoint.object_record(snapshot["runtime"])["classification"] == "ABSENT"


def test_checkpoint_own_argv_is_excluded(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.process_rows.append(
        f"{os.getpid()} 1 501 S python b649_cutover_checkpoint.py "
        f"--expected-rollback-worktree {harness.rollback}"
    )
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result


@pytest.mark.parametrize("failed_job", [False, True])
def test_job_failure_does_not_skip_process_snapshot(
    harness: Harness, capsys: pytest.CaptureFixture[str], failed_job: bool
) -> None:
    harness.job_error = failed_job
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert "process_snapshot" in checkpoint.object_record(result["checks"])
    assert any(call[0] == "lsof" for call in harness.calls)
    assert observation(result, "old_runtime_process_ownership")["classification"] == "ABSENT"
    assert observation(result, "old_runtime_ownership")["classification"] == (
        "UNVERIFIABLE" if failed_job else "PRESENT"
    )


def test_post_load_exact_pass(harness: Harness, capsys: pytest.CaptureFixture[str]) -> None:
    code, result = execute(harness, capsys, "post-load")
    assert code == 0, result
    assert observation(result, "health")["last_error"] is None
    assert not any(call[0] in ("ps", "lsof") for call in harness.calls)


@pytest.mark.parametrize("old_disk", [False, True])
def test_post_load_old_binding_fails(
    harness: Harness, capsys: pytest.CaptureFixture[str], old_disk: bool
) -> None:
    harness.loaded_old = True
    if old_disk:
        harness.plist.write_bytes(plistlib.dumps(harness.binding(harness.rollback)))
    code, result = execute(harness, capsys, "post-load")
    assert code == 1
    assert "loaded_working directory" in cast(list[str], result["failures"])
    assert "loaded_arguments" in cast(list[str], result["failures"])
    assert "loaded_pythonpath" in cast(list[str], result["failures"])


@pytest.mark.parametrize(
    ("key", "value", "failure"),
    [
        ("observed_source_head", OLD_HEAD, "health_observed_source_head"),
        ("source_worktree", "/old/runtime", "health_source_worktree"),
        ("label", "wrong.authority", "health_label"),
        ("schema_version", "wrong-schema", "health_schema_version"),
        ("current_status", "ERROR", "health_state"),
        ("ready_before_draw", False, "health_readiness"),
        ("error_message", "scheduler failed", "health_last_error"),
        ("finished_at", (NOW - timedelta(seconds=901)).isoformat(), "health_fresh"),
        ("finished_at", (NOW + timedelta(seconds=1)).isoformat(), "health_fresh"),
        ("finished_at", "invalid", "health"),
    ],
)
def test_health_mismatch_fails(
    harness: Harness, capsys: pytest.CaptureFixture[str], key: str, value: object, failure: str
) -> None:
    health = checkpoint.object_record(json.loads(harness.health.read_text()))
    health[key] = value
    harness.health.write_text(json.dumps(health))
    code, result = execute(harness, capsys, "post-load")
    assert code == 1
    assert failure in cast(list[str], result["failures"])


def test_disabled_job_fails(harness: Harness, capsys: pytest.CaptureFixture[str]) -> None:
    harness.disabled = True
    code, result = execute(harness, capsys, "post-load")
    assert code == 1
    assert "launchagent_enabled" in cast(list[str], result["failures"])


@pytest.mark.parametrize(
    ("token", "enabled"),
    [("false", True), ("enabled", True), ("true", False), ("disabled", False)],
)
def test_disabled_service_tokens(
    harness: Harness, capsys: pytest.CaptureFixture[str], token: str, enabled: bool
) -> None:
    harness.disabled_output = f'''\n\tdisabled services = {{
        "unrelated.boolean" => true
        "{LABEL}" => {token}
        "unrelated.native" => enabled
    }}\n'''
    code, result = execute(harness, capsys, "post-load")
    assert code == (0 if enabled else 1), result
    entry = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["launchagent_enabled"]
    )
    assert entry["observed"] is enabled
    assert result["failures"] == ([] if enabled else ["launchagent_enabled"])


@pytest.mark.parametrize(
    "entries",
    [
        "",
        f'''"{LABEL}.other" => disabled
        "prefix.{LABEL}" => true
        "{LABEL.replace(".", "x")}" => disabled
        "unrelated.enabled" => enabled
        "unrelated.boolean" => false''',
    ],
)
def test_absent_disabled_service_keeps_default_enabled(
    harness: Harness, capsys: pytest.CaptureFixture[str], entries: str
) -> None:
    harness.disabled_output = f"disabled services = {{\n{entries}\n}}"
    code, result = execute(harness, capsys, "post-load")
    assert code == 0, result
    entry = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["launchagent_enabled"]
    )
    assert entry["observed"] is True


@pytest.mark.parametrize(
    "raw",
    [
        "",
        f'disabled services = {{ "{LABEL}" => unknown }}',
        f'disabled services = {{ "{LABEL}" => enabled-extra }}',
        f'disabled services = {{ "{LABEL}" => FALSE }}',
        f'disabled services = {{ "{LABEL}" => 0 }}',
        f'disabled services = {{ "{LABEL}" => enabled',
        f'disabled services = {{ "{LABEL}" => enabled }} trailing',
        f'disabled services = {{ "{LABEL}" => enabled "other" => unknown }}',
        f'disabled services = {{ "{LABEL}" => false "{LABEL}" => false }}',
        f'disabled services = {{ "{LABEL}" => enabled "{LABEL}" => enabled }}',
        f'disabled services = {{ "{LABEL}" => enabled "{LABEL}" => false }}',
        f'disabled services = {{ "{LABEL}" => enabled "{LABEL}" => disabled }}',
    ],
)
def test_unverifiable_disabled_services_fail_closed(
    harness: Harness, capsys: pytest.CaptureFixture[str], raw: str
) -> None:
    harness.disabled_output = raw
    code, result = execute(harness, capsys, "post-load")
    assert code == 1
    assert result["failures"] == ["launchagent_enabled"]
    entry = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["launchagent_enabled"]
    )
    assert entry["classification"] == "UNVERIFIABLE"


@pytest.mark.parametrize("phase", checkpoint.PHASES)
def test_failed_checks_never_mutate(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    args = harness.argv(phase)
    if phase == "pre-cutover":
        harness.backup.write_bytes(b"wrong")
    elif phase == "post-load":
        harness.loaded_old = True
    before = {path: path.read_bytes() for path in harness.root.iterdir() if path.is_file()}

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("runtime mutation attempted")

    monkeypatch.setattr(os, "kill", forbidden)
    monkeypatch.setattr(os, "replace", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)
    code, _ = execute(harness, capsys, phase, argv=args)
    assert code == 1
    assert before == {path: path.read_bytes() for path in harness.root.iterdir() if path.is_file()}
    assert all(call[0] in ("git", "launchctl", "ps", "lsof") for call in harness.calls)


def test_database_is_metadata_only_read_only(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_connect = sqlite3.connect
    statements: list[str] = []

    def connect(database: str, *, uri: bool, timeout: float) -> sqlite3.Connection:
        assert database == harness.database.as_uri() + "?mode=ro&immutable=1"
        assert uri and timeout == 2
        connection = real_connect(database, uri=uri, timeout=timeout)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(checkpoint.sqlite3, "connect", connect)
    before = harness.database.read_bytes()
    metadata = checkpoint.database_metadata(harness.database)
    assert metadata["schema_version"] == 3
    assert harness.database.read_bytes() == before
    assert statements == [
        "PRAGMA query_only = ON",
        "PRAGMA journal_mode",
        "BEGIN",
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version LIMIT 257",
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name LIMIT 1025",
    ]


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_database_sidecars_fail_before_open(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    Path(str(harness.database) + suffix).touch()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("sidecar database was opened")

    monkeypatch.setattr(checkpoint.sqlite3, "connect", forbidden)
    with pytest.raises(checkpoint.Unverifiable, match="sidecars"):
        checkpoint.database_metadata(harness.database)


@pytest.mark.parametrize("defect", ["schema", "successor-head", "successor-tree", "rollback-head"])
def test_pre_expected_identity_mismatch(
    harness: Harness, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    args = harness.argv("pre-cutover")
    flag = "--expected-db-schema" if defect == "schema" else "--expected-" + defect
    args[args.index(flag) + 1] = "4" if defect == "schema" else "f" * 40
    code, _ = execute(harness, capsys, "pre-cutover", argv=args)
    assert code == 1


@pytest.mark.parametrize(
    ("phase", "token"),
    [
        ("pre-cutover", "false"),
        ("post-unload", "false"),
        ("post-load", "false"),
        ("post-load", "enabled"),
        ("post-load", "true"),
        ("post-load", "disabled"),
    ],
)
@pytest.mark.parametrize("fail", [False, True])
def test_real_entrypoint_json_and_exit(
    harness: Harness, phase: str, token: str, fail: bool
) -> None:
    harness.loaded = phase != "post-unload"
    harness.disabled_output = f'disabled services = {{ "{LABEL}" => {token} }}'
    if fail:
        harness.job_error = True
    args = harness.argv(phase)
    # Capture fixtures once, then exercise __main__ in a separate interpreter.
    checkpoint.main(args, runner=harness, now=NOW)
    responses = {
        json.dumps(call): [result.returncode, result.stdout, result.stderr]
        for call in list(harness.calls)
        for result in [harness(call)]
    }
    source = """
import json, runpy, subprocess, sys
from datetime import UTC, datetime
responses = json.loads(sys.argv[1])
script = sys.argv[2]
sys.argv = sys.argv[2:]
def runner(argv, **kwargs):
    code, out, err = responses[json.dumps(tuple(argv))]
    return subprocess.CompletedProcess(argv, code, out, err)
subprocess.run = runner
runpy.run_path(script, run_name='__main__')
"""
    # Health freshness for the child uses its real clock.
    health = checkpoint.object_record(json.loads(harness.health.read_text()))
    health["finished_at"] = datetime.now(UTC).isoformat()
    harness.health.write_text(json.dumps(health))
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            source,
            json.dumps(responses),
            str(Path(checkpoint.__file__).resolve()),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    expected_fail = fail or (phase == "post-load" and token in ("true", "disabled"))
    assert completed.returncode == (1 if expected_fail else 0), completed.stdout + completed.stderr
    assert not completed.stderr
    result = checkpoint.object_record(json.loads(completed.stdout))
    assert result["phase"] == phase
    assert result["status"] == ("FAIL" if expected_fail else "PASS")


@pytest.mark.parametrize("args", [[], ["post-unload"], ["invalid-phase"], ["--unknown"]])
def test_invalid_cli_is_json(args: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, "-B", checkpoint.__file__, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 2
    assert not completed.stderr
    assert json.loads(completed.stdout)["status"] == "FAIL"


def test_lsof_only_old_process_is_not_dropped(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.file_rows.extend(
        ["p999001", "fcwd", f"n{harness.rollback}", "f3", f"n{harness.root}/shadow.lock"]
    )
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_runtime_ownership")["pids"] == [999001]
    assert observation(result, "old_shadow_ownership")["classification"] == "PRESENT"


@pytest.mark.parametrize("defect", ["nan", "error-type", "readiness-type", "missing-finished"])
def test_malformed_health_fails_closed(
    harness: Harness, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    health = checkpoint.object_record(json.loads(harness.health.read_text()))
    if defect == "nan":
        health["error_message"] = float("nan")
    elif defect == "error-type":
        health["last_error"] = []
    elif defect == "readiness-type":
        health["ready_before_draw"] = 1
    else:
        health.pop("finished_at")
        health["started_at"] = NOW.isoformat()
    harness.health.write_text(json.dumps(health))
    code, result = execute(harness, capsys, "post-load")
    assert code == 1
    assert "health" in cast(list[str], result["failures"])


def test_plist_date_remains_json_serializable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    binding = harness.binding()
    binding["InformationalDate"] = NOW.replace(tzinfo=None)
    harness.plist.write_bytes(plistlib.dumps(binding))
    code, result = execute(harness, capsys, "post-load")
    assert code == 0, result


@pytest.mark.parametrize("problem", ["missing", "timeout"])
def test_observation_error_preserves_json(
    harness: Harness, capsys: pytest.CaptureFixture[str], problem: str
) -> None:
    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "ps":
            if problem == "missing":
                raise FileNotFoundError("fixture tool missing")
            raise subprocess.TimeoutExpired(argv, checkpoint.COMMAND_TIMEOUT)
        return harness(argv)

    assert checkpoint.main(harness.argv("post-unload"), runner=runner, now=NOW) == 1
    result = checkpoint.object_record(json.loads(capsys.readouterr().out))
    entry = checkpoint.object_record(checkpoint.object_record(result["checks"])["process_snapshot"])
    assert entry["classification"] == "UNVERIFIABLE"


@pytest.mark.parametrize("defect", ["arguments", "program", "run interval", "environment"])
def test_independent_loaded_binding_mismatches(
    harness: Harness, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        result = harness(argv)
        if tuple(argv) == ("launchctl", "print", f"{DOMAIN}/{LABEL}"):
            changes = {
                "arguments": ("\n        run\n", "\n        status\n"),
                "program": (f"program = {harness.interpreter}", "program = /wrong/python"),
                "run interval": ("run interval = 300 seconds", "run interval = 600 seconds"),
                "environment": (f"PYTHONPATH => {harness.successor}/src", "PYTHONPATH => /old"),
            }
            before, after = changes[defect]
            result.stdout = result.stdout.replace(before, after)
        return result

    assert checkpoint.main(harness.argv("post-load"), runner=runner, now=NOW) == 1
    result = checkpoint.object_record(json.loads(capsys.readouterr().out))
    name = "loaded_pythonpath" if defect == "environment" else "loaded_" + defect
    assert name in cast(list[str], result["failures"])


def test_revision_expression_is_not_a_durable_ref(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    args = harness.argv("pre-cutover")
    args[args.index("--expected-successor-ref") + 1] = "refs/heads/successor~1"

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if tuple(argv[:2]) == ("git", "check-ref-format"):
            return subprocess.CompletedProcess(argv, 1, "", "")
        if argv[-1] == "refs/heads/successor~1^{commit}":
            return subprocess.CompletedProcess(argv, 0, HEAD + "\n", "")
        return harness(argv)

    assert checkpoint.main(args, runner=runner, now=NOW) == 1
    result = checkpoint.object_record(json.loads(capsys.readouterr().out))
    assert "successor_ref_format" in cast(list[str], result["failures"])


def test_wal_header_without_sidecars_is_refused_before_sqlite_open(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = bytearray(harness.database.read_bytes())
    data[18:20] = b"\x02\x02"
    harness.database.write_bytes(data)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("WAL database was opened")

    monkeypatch.setattr(checkpoint.sqlite3, "connect", forbidden)
    with pytest.raises(checkpoint.Unverifiable, match="header"):
        checkpoint.database_metadata(harness.database)
    assert not list(harness.root.glob("fixture.db-*"))


def test_concurrent_database_change_invalidates_metadata(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_connect = sqlite3.connect

    def connect(database: str, *, uri: bool, timeout: float) -> sqlite3.Connection:
        connection = real_connect(database, uri=uri, timeout=timeout)
        connection.set_trace_callback(lambda _: harness.database.touch())
        return connection

    monkeypatch.setattr(checkpoint.sqlite3, "connect", connect)
    with pytest.raises(checkpoint.Unverifiable, match="changed during"):
        checkpoint.database_metadata(harness.database)


@pytest.mark.parametrize(
    "override",
    [
        ["-c", "core.fsmonitor=true"],
        ["-ccore.fsmonitor=true"],
        ["--config-env=core.fsmonitor=WATCHER"],
    ],
)
def test_git_command_seam_cannot_enable_fsmonitor(override: list[str]) -> None:
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    with pytest.raises(checkpoint.Unverifiable, match="overrides"):
        checkpoint.checked(runner, ["git", *override, "status"])
    assert calls == []
    checkpoint.checked(runner, ["git", "status", "--porcelain=v1"])
    assert calls == [["git", "-c", "core.fsmonitor=false", "status", "--porcelain=v1"]]


def test_temporary_git_reads_do_not_start_configured_fsmonitor(tmp_path: Path) -> None:
    # Every command is scoped to this newly-created repository. Never inspect or
    # stop a watcher in either of the real production worktrees.
    root = tmp_path / "isolated-git"
    root.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False, timeout=10
        )

    assert git("init").returncode == 0
    assert git("config", "core.fsmonitor", "true").returncode == 0
    assert git("config", "fsmonitor.socketDir", str(root)).returncode == 0
    assert git("-c", "core.fsmonitor=false", "fsmonitor--daemon", "status").returncode == 1
    try:
        for _ in range(2):
            assert (
                checkpoint.checked(
                    checkpoint.run_command, ["git", "-C", str(root), "status", "--porcelain=v1"]
                )
                == ""
            )
            assert checkpoint.checked(
                checkpoint.run_command, ["git", "-C", str(root), "rev-parse", "--show-toplevel"]
            ).strip() == str(root)
            assert git("-c", "core.fsmonitor=false", "fsmonitor--daemon", "status").returncode == 1
    finally:
        stopped = git("-c", "core.fsmonitor=false", "fsmonitor--daemon", "stop")
        assert stopped.returncode == 0 or (
            stopped.returncode == 128
            and stopped.stderr == "fatal: fsmonitor--daemon is not running\n"
        )


def test_checkpoint_named_ancestor_is_not_an_exemption(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.process_rows.append(
        f"{os.getppid()} 1 501 S python b649_cutover_checkpoint.py {harness.rollback}"
    )
    harness.file_rows.extend([f"p{os.getppid()}", "fcwd", f"n{harness.rollback}"])
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1 and result["status"] == "FAIL"


def test_kernel_python_image_matches_real_process_command() -> None:
    raw = subprocess.run(
        ["ps", "-ww", "-p", str(os.getpid()), "-o", "command="],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    process = checkpoint.Process(os.getpid(), os.getppid(), os.getuid(), raw)
    argv = (sys.executable, *sys.orig_argv[1:])
    assert checkpoint.interpreter_command_matches(process, argv)
    assert not checkpoint.interpreter_command_matches(process, (*argv, "--forged"))
