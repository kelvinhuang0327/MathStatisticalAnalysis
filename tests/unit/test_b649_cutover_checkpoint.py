"""Checkpoint acceptance using fixture files and an allowlisted observation runner."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
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


def _git_executable_path() -> str:
    git_executable = shutil.which("git")
    assert git_executable is not None
    return str(Path(git_executable).resolve(strict=True))


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
    process_rows: list[str] = field(
        default_factory=lambda: ["900001 1 501 S /usr/bin/fixture-shell"]
    )
    file_rows: list[str] = field(default_factory=lambda: ["p900001", "fcwd", "n/fixture-home"])
    rollback_path: Path | None = None
    vanished_pids: set[int] = field(default_factory=lambda: set[int]())

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
        elif len(args) == 5 and args[0] == "ps" and args[1] == "-p" and args[3:] == ("-o", "pid="):
            requested = {int(value) for value in args[2].split(",")}
            out = "\n".join(str(pid) for pid in sorted(requested - self.vanished_pids))
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


@pytest.mark.parametrize("state", ["Z", "Z+", "Zs"])
@pytest.mark.parametrize("stale_scheduler", [False, True])
def test_verified_zombie_without_files_is_absent(
    harness: Harness, capsys: pytest.CaptureFixture[str], state: str, stale_scheduler: bool
) -> None:
    harness.loaded = False
    command = (
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
        if stale_scheduler
        else "<defunct>"
    )
    pid = harness.add_process(command, state=state, cwd=None)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [pid]
    assert snapshot["uncertainties"] == []
    assert snapshot["processes"] == [
        {
            "pid": pid,
            "ppid": 1,
            "uid": 501,
            "command": command,
            "state": state,
            "cwd": None,
            "files": [],
        }
    ]
    for role in ("runtime", "primary", "scheduler", "shadow"):
        assert checkpoint.object_record(snapshot[role]) == {"classification": "ABSENT", "pids": []}


@pytest.mark.parametrize("state", ["S", "R"])
@pytest.mark.parametrize("stale_scheduler", [False, True])
def test_live_zombie_lookalike_is_not_exempt(
    harness: Harness, capsys: pytest.CaptureFixture[str], state: str, stale_scheduler: bool
) -> None:
    harness.loaded = False
    command = (
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
        if stale_scheduler
        else "<defunct>"
    )
    pid = harness.add_process(command, state=state, cwd=None)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == []
    assert snapshot["uncertainties"] == [f"PID {pid}: cwd/open-file coverage unavailable"]
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "PRESENT" if stale_scheduler else "UNVERIFIABLE",
        "pids": [pid] if stale_scheduler else [],
    }


def test_zombies_do_not_join_or_extend_active_descendant_closure(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    parent = harness.add_process(f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py")
    child = harness.add_process("python worker.py", ppid=parent)
    zombie = harness.add_process("<defunct>", state="Z", cwd=None, ppid=parent)
    harness.add_process("python unrelated.py", ppid=zombie)
    unrelated_zombie = harness.add_process("<defunct>", state="Z", cwd=None)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [zombie, unrelated_zombie]
    assert snapshot["uncertainties"] == []
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "PRESENT",
        "pids": [parent, child],
    }
    assert checkpoint.object_record(snapshot["scheduler"])["pids"] == [parent]


def test_zombie_parent_cannot_mask_live_runtime_child(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    command = f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py"
    parent = harness.add_process(command, state="Z", cwd=None)
    child = harness.add_process(command, ppid=parent)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [parent]
    assert snapshot["uncertainties"] == []
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "PRESENT",
        "pids": [child],
    }


@pytest.mark.parametrize("evidence", ["cwd", "old_cwd", "file", "old_file", "primary", "shadow"])
def test_zombie_with_live_file_evidence_is_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str], evidence: str
) -> None:
    harness.loaded = False
    cwd = {"cwd": "/fixture-home", "old_cwd": str(harness.rollback)}.get(evidence)
    file = {
        "file": "/fixture-home/other.txt",
        "old_file": str(harness.rollback / "src/mod.py"),
        "primary": str(harness.root / "primary.lock"),
        "shadow": str(harness.root / "shadow.lock"),
    }.get(evidence)
    pid = harness.add_process("<defunct>", state="Z", cwd=cwd, files=[file] if file else [])
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == [pid]
    assert snapshot["uncertainties"] == [
        f"PID {pid}: zombie has inconsistent cwd/open-file evidence"
    ]
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "UNVERIFIABLE",
        "pids": [],
    }
    process = checkpoint.object_record(cast(list[object], snapshot["processes"])[0])
    assert process["state"] == "Z"
    assert process["files"]


@pytest.mark.parametrize(
    "row",
    [
        "900002 1 501 <defunct>",
        "900002 1 501 python worker.py",
        "900002 1 501 Q <defunct>",
        "900002 1 501 Zgarbage <defunct>",
        "900002 1 501 Z",
        "900002 1 501 Z   ",
        "bad 1 501 Z <defunct>",
        "900001 1 501 Z <defunct>",  # Duplicate PID, even with a different state.
        "",
    ],
)
def test_malformed_process_state_fails_closed(
    harness: Harness, capsys: pytest.CaptureFixture[str], row: str
) -> None:
    harness.loaded = False
    harness.process_rows.append(row)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    entry = checkpoint.object_record(checkpoint.object_record(result["checks"])["process_snapshot"])
    assert entry["classification"] == "UNVERIFIABLE"
    assert "process table" in str(entry["error"])
    assert observation(result, "old_runtime_ownership")["classification"] == "UNVERIFIABLE"


def test_zombie_does_not_exempt_malformed_lsof(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process("<defunct>", state="Z", cwd=None)
    harness.file_rows.append("invalid ownership row")
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    entry = checkpoint.object_record(checkpoint.object_record(result["checks"])["process_snapshot"])
    assert entry["classification"] == "UNVERIFIABLE"
    assert "unparseable lsof" in str(entry["error"])


@pytest.mark.parametrize("bound", [False, True])
def test_process_appearing_after_ps_keeps_file_ownership_evidence(
    harness: Harness, capsys: pytest.CaptureFixture[str], bound: bool
) -> None:
    harness.loaded = False
    cwd = str(harness.rollback) if bound else "/fixture-home"
    harness.file_rows.extend(["p900002", "fcwd", f"n{cwd}"])
    code, result = execute(harness, capsys, "post-unload")
    assert code == (1 if bound else 0)
    snapshot = observation(result, "process_snapshot")
    assert snapshot["zombie_pids"] == []
    assert snapshot["uncertainties"] == []
    assert checkpoint.object_record(snapshot["runtime"])["classification"] == (
        "PRESENT" if bound else "ABSENT"
    )


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


def _protected_task_checkpoint_command(harness: Harness, *, run: bool = True) -> str:
    mode = "--run" if run else "--inspect"
    return (
        "ruby /opt/fable-method/scripts/task_checkpoint.rb "
        f"{mode} --repo /repo --worktree {harness.rollback} "
        "--task-id B649_CUTOVER_PROTECTED_WRAPPER_ANCESTOR_OWNERSHIP_REPAIR_R1 "
        "--execution-id focused-test -- "
        "python tools/b649_production_cutover.py rollback"
    )


def _target_git_admin_metadata(harness: Harness) -> tuple[Path, Path]:
    target = harness.use_production_rollback_worktree()
    git_admin = harness.root / ".git" / "worktrees" / target.name
    git_admin.mkdir(parents=True)
    (git_admin / "index").touch()
    (target / ".git").write_text(f"gitdir: {git_admin}\n", encoding="utf-8")
    return target, git_admin


def _add_protected_task_checkpoint_ancestor(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    command: str | None = None,
    live_scheduler_ancestor: bool = False,
    live_scheduler_parent: bool = False,
) -> int:
    wrapper_pid = 990001
    invocation_pid = 990002
    scheduler_pid = 990003
    parent_pid = scheduler_pid if live_scheduler_ancestor else wrapper_pid
    wrapper_parent_pid = scheduler_pid if live_scheduler_parent else 1
    scheduler_parent_pid = wrapper_pid if live_scheduler_ancestor else 1
    harness.process_rows.extend(
        [
            f"{invocation_pid} {parent_pid} 501 S python tools/b649_production_cutover.py rollback",
        ]
    )
    if live_scheduler_ancestor or live_scheduler_parent:
        harness.process_rows.append(
            f"{scheduler_pid} {scheduler_parent_pid} 501 S "
            f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
        )
    harness.process_rows.append(
        f"{wrapper_pid} {wrapper_parent_pid} 501 S "
        f"{command or _protected_task_checkpoint_command(harness)}"
    )
    harness.file_rows.extend(
        [
            f"p{invocation_pid}",
            "fcwd",
            "n/fixture-home",
            f"p{wrapper_pid}",
            "fcwd",
            "n/fixture-home",
        ]
    )
    if live_scheduler_ancestor or live_scheduler_parent:
        harness.file_rows.extend([f"p{scheduler_pid}", "fcwd", f"n{harness.rollback}"])
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: invocation_pid)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: parent_pid)
    return wrapper_pid


def test_protected_task_checkpoint_run_ancestor_is_not_runtime_owner(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _add_protected_task_checkpoint_ancestor(harness, monkeypatch)

    code, result = execute(harness, capsys, "post-unload")

    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "ABSENT", result
    assert code == 0, result
    assert runtime["pids"] == []


def test_non_ancestor_task_checkpoint_run_remains_runtime_owner(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    target, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid = harness.add_process(_protected_task_checkpoint_command(harness))
    fsmonitor_pid = harness.add_process(
        "git fsmonitor--daemon run",
        ppid=1,
        files=[str(git_admin / "index")],
        executable_file="/usr/bin/git",
    )
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 990002)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: 990003)

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert wrapper_pid in runtime_pids
    assert fsmonitor_pid not in runtime_pids
    assert target == harness.rollback



def test_task_checkpoint_ancestor_without_run_mode_falls_through_to_ancestor_rule(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without --run, the wrapper does not get the protected blanket skip; it
    # falls through to ordinary ancestor evaluation. It is still a genuine
    # ancestor with only argv-text (--worktree) evidence and no role/lock/cwd
    # binding of its own, so the general ancestor rule now (correctly) clears
    # it too, just through a different path than the --run-mode exemption.
    harness.loaded = False
    _add_protected_task_checkpoint_ancestor(
        harness,
        monkeypatch,
        command=_protected_task_checkpoint_command(harness, run=False),
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 0, result
    assert observation(result, "old_runtime_ownership")["classification"] == "ABSENT"


def test_protected_task_checkpoint_ancestor_does_not_hide_live_scheduler(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    scheduler_pid = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run",
        ppid=wrapper_pid,
    )
    fsmonitor_pid = harness.add_process(
        "git fsmonitor--daemon run",
        ppid=wrapper_pid,
        files=[str(git_admin / "index")],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert scheduler_pid in runtime_pids
    assert fsmonitor_pid not in runtime_pids



def test_actual_scheduler_ancestor_is_not_exempted_with_wrapper(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _add_protected_task_checkpoint_ancestor(
        harness,
        monkeypatch,
        live_scheduler_ancestor=True,
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert 990003 in runtime_pids


def test_live_runtime_ancestor_still_propagates_through_protected_wrapper(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    wrapper_pid = _add_protected_task_checkpoint_ancestor(
        harness,
        monkeypatch,
        live_scheduler_parent=True,
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert 990003 in runtime_pids
    assert wrapper_pid in runtime_pids


def test_protected_wrapper_fsmonitor_with_owner_lock_remains_present(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    fsmonitor_pid = harness.add_process(
        "git fsmonitor--daemon run",
        ppid=wrapper_pid,
        files=[str(git_admin / "index"), str(harness.root / "primary.lock")],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, "old_primary_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert fsmonitor_pid in runtime_pids


@pytest.mark.parametrize("role", ["primary", "shadow"])
def test_protected_wrapper_with_owner_lock_is_not_exempted(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    harness.loaded = False
    wrapper_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    lock_path = harness.root / f"{role}.lock"
    harness.file_rows.extend([f"p{wrapper_pid}", "f4", f"n{lock_path}"])

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    assert observation(result, f"old_{role}_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert wrapper_pid in runtime_pids


def test_protected_task_checkpoint_ancestor_keeps_missing_coverage_fail_closed(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    harness.add_process("python live-but-unobserved.py", cwd=None, ppid=wrapper_pid)
    fsmonitor_pid = harness.add_process(
        "git fsmonitor--daemon run",
        ppid=wrapper_pid,
        files=[str(git_admin / "index")],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "UNVERIFIABLE"
    assert runtime["process_classification"] == "UNVERIFIABLE"
    assert fsmonitor_pid not in cast(list[int], runtime["pids"])



def test_protected_task_checkpoint_ancestor_preserves_passive_fsmonitor_exemption(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    wrapper_pid = _add_protected_task_checkpoint_ancestor(harness, monkeypatch)
    harness.add_process(
        "git fsmonitor--daemon run",
        ppid=wrapper_pid,
        files=[str(git_admin / "index")],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    runtime = observation(result, "old_runtime_ownership")
    assert code == 0, result
    assert runtime["classification"] == "ABSENT"
    assert runtime["pids"] == []



@pytest.mark.parametrize(
    "command_style", ["absolute_git", "bare_git", "git_start", "git_c"]
)
def test_passive_git_fsmonitor_is_excluded_from_runtime_ownership(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    command_style: str,
) -> None:
    git_executable = _git_executable_path()
    command, executable_file = {
        "absolute_git": (
            f"{git_executable} fsmonitor--daemon run --detach --ipc-threads=8",
            git_executable,
        ),
        "bare_git": ("git fsmonitor--daemon run", git_executable),
        "git_start": (
            f"{git_executable} fsmonitor--daemon start --detach",
            git_executable,
        ),
        "git_c": ("git -C /Users/kelvin fsmonitor--daemon run", git_executable),
    }[command_style]
    harness.loaded = False
    harness.add_process(
        command, files=[str(harness.rollback)], executable_file=executable_file
    )
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result
    obs = observation(result, "old_runtime_ownership")
    assert obs["classification"] == "ABSENT"
    assert obs["pids"] == []



def test_passive_fsmonitor_allows_auxiliary_system_txt_mapping(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(
        "/usr/bin/git fsmonitor--daemon run",
        files=[str(harness.rollback)],
        executable_file="/usr/bin/git",
        additional_executable_files=(sys.executable,),
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 0, result
    assert observation(result, "old_runtime_ownership")["classification"] == "ABSENT"


@pytest.mark.parametrize("include_direct_worktree", [False, True])
@pytest.mark.parametrize(
    ("command", "executable_file"),
    [
        ("git fsmonitor--daemon run", "/usr/bin/git"),
        ("/usr/bin/git fsmonitor--daemon run", "/usr/bin/git"),
    ],
)
def test_passive_git_fsmonitor_ignores_target_git_metadata_head(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    include_direct_worktree: bool,
    command: str,
    executable_file: str,
) -> None:
    harness.loaded = False
    target = harness.use_production_rollback_worktree()
    git_admin = harness.root / ".git" / "worktrees" / target.name
    git_admin.mkdir(parents=True)
    (git_admin / "index").touch()
    (target / ".git").write_text(f"gitdir: {git_admin}\n", encoding="utf-8")
    files = [str(git_admin / "index")]
    if include_direct_worktree:
        files.append(str(target))
    harness.add_process(command, files=files, executable_file=executable_file)

    code, result = execute(harness, capsys, "post-unload")

    obs = observation(result, "old_runtime_ownership")
    assert obs["classification"] == "ABSENT", result
    assert obs["pids"] == []
    assert code == 0, result


def test_untrusted_absolute_git_with_target_metadata_remains_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    _, git_admin = _target_git_admin_metadata(harness)
    pid = harness.add_process(
        "/tmp/untrusted-bin/git fsmonitor--daemon run",
        files=[str(git_admin / "index")],
        executable_file="/tmp/untrusted-bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert runtime["pids"] == [pid]


def test_fsmonitor_metadata_with_matching_name_but_wrong_gitdir_is_not_exempt(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    target, _ = _target_git_admin_metadata(harness)
    unrelated_git_admin = harness.root / "unrelated-repo" / ".git" / "worktrees" / target.name
    unrelated_git_admin.mkdir(parents=True)
    (unrelated_git_admin / "index").touch()
    pid = harness.add_process(
        "git fsmonitor--daemon run",
        files=[str(unrelated_git_admin / "index")],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert runtime["pids"] == [pid]


def test_head_token_in_fsmonitor_command_is_not_exempt(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    target = harness.use_production_rollback_worktree()
    pid = harness.add_process(
        f"git fsmonitor--daemon run --head {OLD_HEAD}",
        files=[str(target)],
        executable_file="/usr/bin/git",
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert pid in cast(list[int], runtime["pids"])


def test_fsmonitor_executable_inside_target_worktree_is_not_exempt(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    target = harness.use_production_rollback_worktree()
    pid = harness.add_process(
        f"{target}/git fsmonitor--daemon run",
        files=[str(target)],
    )

    code, result = execute(harness, capsys, "post-unload")

    assert code == 1
    runtime = observation(result, "old_runtime_ownership")
    assert runtime["classification"] == "PRESENT"
    assert pid in cast(list[int], runtime["pids"])


def test_real_scheduler_owner_process_is_present(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run")
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_primary_owner_process_is_present(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(f"python {harness.rollback}/tools/b649_operational_prediction_loop.py")
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_primary_ownership")["classification"] == "PRESENT"
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_shadow_owner_process_is_present(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(f"python {harness.rollback}/tools/b649_pair_rule_forward_shadow.py")
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_shadow_ownership")["classification"] == "PRESENT"
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_lock_holder_process_is_present(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.add_process(
        "git fsmonitor--daemon run",
        files=[str(harness.rollback), str(harness.root / "primary.lock")],
    )
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_primary_ownership")["classification"] == "PRESENT"
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


@pytest.mark.parametrize(
    "cmd",
    [
        "python worker.py --fsmonitor",
        "python tools/custom_runner.py fsmonitor--daemon run",
        "fake-git fsmonitor--daemon run",
        "sh -c 'git fsmonitor--daemon run'",
    ],
)
def test_argv_spoof_with_fsmonitor_string_is_not_exempt(
    harness: Harness, capsys: pytest.CaptureFixture[str], cmd: str
) -> None:
    harness.loaded = False
    harness.add_process(cmd, cwd=str(harness.rollback))
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_runtime_ownership")["classification"] == "PRESENT"


def test_descendant_of_runtime_owner_remains_present(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    parent = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
    )
    child = harness.add_process("git fsmonitor--daemon run", ppid=parent)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert parent in pids
    assert child in pids


def test_ancestor_argv_only_worktree_path_is_not_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.loaded = False
    ancestor_pid = harness.add_process(
        "/bin/bash -c 'python tools/b649_production_cutover.py rollback "
        f"--expected-rollback-worktree {harness.rollback} "
        f"--expected-rollback-head {OLD_HEAD}'"
    )
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 999999)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: ancestor_pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result
    snapshot = observation(result, "process_snapshot")
    assert snapshot["uncertainties"] == []
    assert observation(result, "old_runtime_ownership")["classification"] == "ABSENT"


def test_non_ancestor_with_identical_command_remains_runtime_owner(
    harness: Harness, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.loaded = False
    unrelated_pid = harness.add_process(
        "/bin/bash -c 'python tools/b649_production_cutover.py rollback "
        f"--expected-rollback-worktree {harness.rollback} "
        f"--expected-rollback-head {OLD_HEAD}'"
    )
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 999999)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: 1)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert unrelated_pid in runtime_pids


def test_ancestor_running_real_scheduler_role_remains_present(
    harness: Harness, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.loaded = False
    ancestor_pid = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
    )
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 999999)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: ancestor_pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert ancestor_pid in runtime_pids


@pytest.mark.parametrize("role", ["primary", "shadow"])
def test_ancestor_holding_lock_remains_present(
    harness: Harness,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    harness.loaded = False
    lock_path = harness.root / f"{role}.lock"
    ancestor_pid = harness.add_process("/bin/bash -c 'sleep 100'", files=[str(lock_path)])
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 999999)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: ancestor_pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    assert observation(result, f"old_{role}_ownership")["classification"] == "PRESENT"
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert ancestor_pid in runtime_pids


def test_ancestor_with_cwd_inside_target_worktree_remains_present(
    harness: Harness, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.loaded = False
    ancestor_pid = harness.add_process("/bin/bash -c 'sleep 100'", cwd=str(harness.rollback))
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: 999999)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: ancestor_pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    runtime_pids = cast(list[int], observation(result, "old_runtime_ownership")["pids"])
    assert ancestor_pid in runtime_pids


def test_transient_coverage_gap_reconciled_as_vanished_is_not_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    pid = harness.add_process("python worker.py", cwd=None)
    harness.vanished_pids.add(pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 0, result
    snapshot = observation(result, "process_snapshot")
    assert snapshot["uncertainties"] == []
    assert checkpoint.object_record(snapshot["runtime"]) == {"classification": "ABSENT", "pids": []}


def test_persistent_coverage_gap_remains_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    pid = harness.add_process("python worker.py", cwd=None)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["uncertainties"] == [f"PID {pid}: cwd/open-file coverage unavailable"]
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "UNVERIFIABLE",
        "pids": [],
    }


def test_reconciliation_does_not_erase_positive_owner_evidence(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    owner = harness.add_process(
        f"python {harness.rollback}/tools/b649_goalc_local_scheduler.py run"
    )
    gap_pid = harness.add_process("python worker.py", cwd=None)
    harness.vanished_pids.add(gap_pid)
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    snapshot = observation(result, "process_snapshot")
    assert snapshot["uncertainties"] == []
    assert checkpoint.object_record(snapshot["runtime"]) == {
        "classification": "PRESENT",
        "pids": [owner],
    }
    assert observation(result, "old_scheduler_ownership")["classification"] == "PRESENT"


def test_unverifiable_fail_closed_remains_unverifiable(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.loaded = False
    harness.file_rows = []
    code, result = execute(harness, capsys, "post-unload")
    assert code == 1
    entry = checkpoint.object_record(
        checkpoint.object_record(result["checks"])["old_runtime_ownership"]
    )
    assert entry["status"] == "FAIL"
    assert observation(result, "old_runtime_ownership")["classification"] == "UNVERIFIABLE"


def test_is_git_fsmonitor_command_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_executable = _git_executable_path()
    mac_git_core = Path(
        "/Library/Developer/CommandLineTools/usr/libexec/git-core"
    )
    mac_git = mac_git_core / "git"
    mac_git_fsmonitor_executable = mac_git_core / "git-fsmonitor--daemon"
    untrusted_git = Path("/tmp/untrusted-bin/git")
    native_resolve = Path.resolve
    controlled_macos_paths = {
        mac_git_core,
        mac_git,
        mac_git_fsmonitor_executable,
        untrusted_git,
    }

    def resolve_with_macos_git_paths(path: Path, strict: bool = False) -> Path:
        if path in controlled_macos_paths:
            assert strict
            return path
        return native_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_with_macos_git_paths)

    assert checkpoint.is_git_fsmonitor_command(
        f"{git_executable} fsmonitor--daemon run --detach --ipc-threads=8",
        executable_files=(git_executable,),
    )
    assert checkpoint.is_git_fsmonitor_command(
        "git fsmonitor--daemon run", executable_files=(git_executable,)
    )
    assert checkpoint.is_git_fsmonitor_command(
        "git fsmonitor--daemon run",
        executable_files=(git_executable, sys.executable),
    )
    assert checkpoint.is_git_fsmonitor_command(
        f"{git_executable} fsmonitor--daemon start",
        executable_files=(git_executable,),
    )
    assert checkpoint.is_git_fsmonitor_command(
        f"{mac_git} fsmonitor--daemon run --detach --ipc-threads=8",
        executable_files=(str(mac_git),),
    )
    assert checkpoint.is_git_fsmonitor_command(
        f"{mac_git_fsmonitor_executable} run",
        executable_files=(str(mac_git_fsmonitor_executable),),
    )
    assert checkpoint.is_git_fsmonitor_command(
        "git -C /some/path fsmonitor--daemon run",
        executable_files=(git_executable,),
    )
    assert not checkpoint.is_git_fsmonitor_command("git status")
    assert not checkpoint.is_git_fsmonitor_command("git fsmonitor--daemon status")
    assert not checkpoint.is_git_fsmonitor_command("git fsmonitor--daemon stop")
    assert not checkpoint.is_git_fsmonitor_command("python worker.py --fsmonitor")
    assert not checkpoint.is_git_fsmonitor_command(
        "fake-git fsmonitor--daemon run", executable_files=("/tmp/fake-git",)
    )
    assert not checkpoint.is_git_fsmonitor_command(
        f"{untrusted_git} fsmonitor--daemon run",
        executable_files=(str(untrusted_git),),
    )
    assert not checkpoint.is_git_fsmonitor_command("sh -c 'git fsmonitor--daemon run'")
    assert not checkpoint.is_git_fsmonitor_command(
        "/Users/kelvin/old/git fsmonitor--daemon run", old_worktree="/Users/kelvin/old"
    )



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
