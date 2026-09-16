"""Read-only, bounded evidence gates for an externally performed B649 cutover.

Run ``uv run python tools/b649_cutover_checkpoint.py --help`` for JSON usage.
Supply a phase and its required expectations; each invocation emits one JSON
object and exits 0 only on PASS (invalid input exits 2, failed evidence exits 1).
No scheduler modules are imported, no locks are acquired, and no repair is made.

Ownership is a conservative snapshot of the LaunchAgent user's process table,
commands, cwd/open files, and descendants. Role identities are literal markers
(repeat the flags for wrappers/extra hooks). Defaults cover the project entry
points. An ambiguous B649 process or incomplete observation fails closed. This
is evidence for the observation window, not a reservation against later starts.
An open primary/shadow lock is treated as ownership even without testing flock.

The DB gate only reads schema metadata, using mode=ro, immutable and query_only.
Journals, WAL headers/sidecars and concurrent file changes are refused; immutable
prevents SQLite from creating sidecars even if the database changes mid-check.
Health authority is the exact supplied local file, checked by label and schema;
freshness and acceptable states are explicit caller policy. Post-load inspects
both the on-disk plist and launchd's independently loaded binding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import sqlite3
import stat
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

PHASES = ("pre-cutover", "post-unload", "post-load")
COMMAND_TIMEOUT = 10
MAX_BYTES = 16 * 1024 * 1024
ROLE_DEFAULTS = {
    "primary": ["b649_operational_prediction_loop.py", "b649_forward_auto_cycle_adapter.py"],
    "scheduler": ["b649_goalc_local_scheduler.py"],
    "shadow": ["b649_pair_rule_forward_shadow.py", "run_shadow_predraw", "run_shadow_postdraw"],
}
type Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
type Record = dict[str, object]


class Unverifiable(ValueError):
    """A mandatory observation cannot establish the expected state."""


def run_command(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """The only command execution seam; callers supply fixed read-only verbs."""
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        timeout=COMMAND_TIMEOUT,
        env={**os.environ, "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"},
    )


def command(runner: Runner, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    result = runner(argv)
    if len(result.stdout) + len(result.stderr) > MAX_BYTES:
        raise Unverifiable(f"{argv[0]} observation exceeded the output bound")
    return result


def checked(runner: Runner, argv: Sequence[str]) -> str:
    result = command(runner, argv)
    if result.returncode != 0 or result.stderr.strip():
        raise Unverifiable(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def file_identity(s: os.stat_result) -> tuple[int, ...]:
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def read_bytes(path: Path) -> bytes:
    # Nonblocking open prevents a FIFO masquerading as evidence from hanging.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise Unverifiable(f"not a bounded regular evidence file: {path}")
        data = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)

    if len(data) > MAX_BYTES or file_identity(before) != file_identity(after):
        raise Unverifiable(f"evidence changed during observation: {path}")
    if file_identity(before) != file_identity(current):
        raise Unverifiable(f"evidence replaced during observation: {path}")
    return data


def object_record(value: object) -> Record:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise Unverifiable("expected an object with string keys")
    return cast(Record, value)


@dataclass
class Checks:
    phase: str
    checks: dict[str, Record] = field(default_factory=lambda: dict[str, Record]())
    failures: list[str] = field(default_factory=lambda: list[str]())

    def add(
        self,
        name: str,
        observe: Callable[[], object],
        *,
        accept: Callable[[object], bool] = lambda _: True,
        expected: object = None,
    ) -> object:
        try:
            observed = observe()
            passed = accept(observed)
            entry: Record = {"status": "PASS" if passed else "FAIL", "observed": observed}
        except Exception as exc:
            observed = None
            passed = False
            entry = {
                "status": "FAIL",
                "classification": "UNVERIFIABLE",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if expected is not None:
            entry["expected"] = expected
        self.checks[name] = entry
        if not passed:
            self.failures.append(name)
        return observed

    def equal(self, name: str, observe: Callable[[], object], expected: object) -> object:
        return self.add(name, observe, accept=lambda value: value == expected, expected=expected)

    def result(self) -> Record:
        return {
            "phase": self.phase,
            "status": "FAIL" if self.failures else "PASS",
            "checks": self.checks,
            "failures": self.failures,
        }


def git_value(runner: Runner, worktree: str, revision: str) -> str:
    return checked(
        runner,
        [
            "git",
            "--no-optional-locks",
            "-C",
            worktree,
            "rev-parse",
            "--verify",
            "--end-of-options",
            revision,
        ],
    ).strip()


def check_source(checks: Checks, args: argparse.Namespace, runner: Runner, role: str) -> None:
    worktree = cast(str, getattr(args, f"expected_{role}_worktree"))
    head = cast(str, getattr(args, f"expected_{role}_head"))
    checks.equal(f"{role}_worktree", lambda: Path(worktree).is_dir(), True)
    checks.equal(
        f"{role}_root",
        lambda: checked(
            runner, ["git", "--no-optional-locks", "-C", worktree, "rev-parse", "--show-toplevel"]
        ).strip(),
        worktree,
    )
    checks.equal(f"{role}_head", lambda: git_value(runner, worktree, "HEAD"), head)
    if role == "successor" and args.phase == "pre-cutover":
        checks.equal(
            "successor_ref_format",
            lambda: checked(
                runner, ["git", "check-ref-format", args.expected_successor_ref]
            ).strip(),
            "",
        )
        checks.equal(
            "successor_tree",
            lambda: git_value(runner, worktree, "HEAD^{tree}"),
            args.expected_successor_tree,
        )
        checks.equal(
            "successor_durable_ref",
            lambda: git_value(runner, worktree, args.expected_successor_ref + "^{commit}"),
            head,
        )


def plist_snapshot(path: Path) -> Record:
    data = read_bytes(path)
    # Plists may contain date/data values in informational fields. Keep the
    # evidence JSON serializable, and reject non-finite numbers before reporting.
    value = object_record(
        json.loads(json.dumps(plistlib.loads(data), default=str, allow_nan=False))
    )
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "binding": value}


def launch_snapshot(args: argparse.Namespace, runner: Runner) -> Record:
    target = f"{args.launch_domain}/{args.expected_label}"
    result = command(runner, ["launchctl", "print", target])
    if result.returncode == 0 and not result.stderr.strip():
        if not result.stdout.startswith(target + " = {"):
            raise Unverifiable("launchctl returned a different or malformed service")
        return {"state": "LOADED", "target": target, "raw": result.stdout}
    missing = re.fullmatch(
        r'Bad request\.\s+Could not find service "'
        + re.escape(args.expected_label)
        + r'" in domain for user '
        + re.escape(args.launch_domain.replace("/", ": "))
        + r"\s*",
        result.stderr,
    )
    if result.returncode == 113 and missing and not result.stdout.strip():
        return {"state": "UNLOADED", "target": target, "raw": result.stderr}
    raise Unverifiable(f"launchctl print failed ({result.returncode}): {result.stderr.strip()}")


def launch_fields(raw: str) -> dict[str, str | list[str]]:
    """Parse only direct service fields, preserving nested blocks for exact checks."""
    lines = raw.splitlines()
    fields: dict[str, str | list[str]] = {}
    depth = 1
    active: list[str] | None = None
    for line in lines[1:]:
        text = line.strip()
        if text == "}":
            depth -= 1
            if depth < 0:
                raise Unverifiable("unbalanced launchctl output")
            if depth == 1:
                active = None
            continue
        if depth < 1:
            if text:
                raise Unverifiable("trailing launchctl output")
            continue
        if depth == 1 and " = " in text:
            key, value = text.split(" = ", 1)
            if key in fields:
                raise Unverifiable(f"ambiguous launchctl field: {key}")
            if value == "{":
                active = []
                fields[key] = active
            else:
                fields[key] = value
        elif active is not None:
            active.append(text)
        if text.endswith("{"):
            depth += 1
    if depth != 0:
        raise Unverifiable("incomplete launchctl output")
    return fields


def enabled_snapshot(args: argparse.Namespace, runner: Runner) -> bool:
    raw = checked(runner, ["launchctl", "print-disabled", args.launch_domain])
    if not re.fullmatch(
        r'disabled services = \{\s*(?:"[^"\n]+" => (?:true|false|enabled|disabled)\s*)*}',
        raw.strip(),
    ):
        raise Unverifiable("unrecognized launchctl disabled-services output")
    values = re.findall(
        r'"' + re.escape(args.expected_label) + r'" => (true|false|enabled|disabled)', raw
    )
    if len(values) > 1:
        raise Unverifiable("duplicate disabled-service entry")
    # Boolean values describe the disabled override; words describe service state.
    return not values or values[0] in ("false", "enabled")


def database_metadata(path: Path) -> Record:
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise Unverifiable("database must be a regular, non-symlink file")
    sidecars = [str(path) + suffix for suffix in ("-wal", "-shm", "-journal")]
    if any(os.path.lexists(sidecar) for sidecar in sidecars):
        raise Unverifiable("database has journal/WAL sidecars; metadata inspection refused")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if file_identity(os.fstat(stream.fileno())) != file_identity(before):
            raise Unverifiable("database replaced before metadata inspection")
        header = stream.read(100)
    if header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
        raise Unverifiable("database header must identify a rollback-journal SQLite file")
    # https://www.sqlite.org/uri.html: immutable avoids all journal/SHM writes.
    # Since a live file is not intrinsically immutable, reject changes around
    # this bounded metadata read instead of trusting a potentially stale result.
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.set_progress_handler(lambda: 1, 100_000)
        mode = connection.execute("PRAGMA journal_mode").fetchone()
        if mode != ("delete",):
            raise Unverifiable("database must use DELETE journal mode")
        connection.execute("BEGIN")
        migrations = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version LIMIT 257"
        ).fetchall()
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name LIMIT 1025"
        ).fetchall()
        if not migrations or len(migrations) > 256 or len(tables) > 1024:
            raise Unverifiable("schema metadata missing or exceeds observation bound")
        if any(
            type(row[0]) is not int or any(type(value) is not str for value in row[1:])
            for row in migrations
        ):
            raise Unverifiable("schema migration metadata has invalid types")
        return {
            "path": str(path),
            "schema_version": migrations[-1][0],
            "migrations": [list(row) for row in migrations],
            "tables": [row[0] for row in tables],
            "journal_mode": mode[0],
        }
    finally:
        connection.close()
        if file_identity(before) != file_identity(path.stat(follow_symlinks=False)) or any(
            os.path.lexists(sidecar) for sidecar in sidecars
        ):
            raise Unverifiable("database changed during metadata inspection")


@dataclass
class Process:
    pid: int
    ppid: int
    uid: int
    command: str
    files: list[str] = field(default_factory=lambda: list[str]())
    cwd: str | None = None


def process_snapshot(args: argparse.Namespace, runner: Runner) -> Record:
    uid = int(args.launch_domain.split("/")[1])
    raw = checked(runner, ["ps", "-ww", "-axo", "pid=,ppid=,uid=,command="])
    processes: dict[int, Process] = {}
    for line in raw.splitlines():
        match = re.fullmatch(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(.+)", line)
        if match is None:
            raise Unverifiable("unparseable process table row")
        pid, ppid, owner, cmd = match.groups()
        if int(pid) in processes:
            raise Unverifiable("duplicate process table PID")
        processes[int(pid)] = Process(int(pid), int(ppid), int(owner), cmd)
    if not processes:
        raise Unverifiable("empty process table")
    # Only this invocation and its helper-launching ancestors are excluded.
    excluded = {os.getpid()}
    parent = os.getppid()
    while parent in processes and parent not in excluded:
        process = processes[parent]
        if "b649_cutover_checkpoint.py" not in process.command:
            break
        excluded.add(parent)
        parent = process.ppid
    files = checked(runner, ["lsof", "-nP", "-a", "-u", str(uid), "-F", "pfn"])
    current: Process | None = None
    descriptor = ""
    for line in files.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
            # Preserve positive path/lock evidence for a process that appeared
            # between ps and lsof, even though its argv was not in the first sample.
            current = processes.setdefault(pid, Process(pid, 0, uid, "<argv unavailable>"))
            descriptor = ""
        elif line.startswith("f"):
            descriptor = line[1:]
        elif line.startswith("n") and descriptor:
            if current is not None:
                current.files.append(line[1:])
                if descriptor == "cwd":
                    current.cwd = line[1:]
        else:
            raise Unverifiable("unparseable lsof ownership row")
    old = args.expected_rollback_worktree
    head = args.expected_rollback_head
    identities = {
        role: defaults + cast(list[str], getattr(args, f"old_{role}_identity") or [])
        for role, defaults in ROLE_DEFAULTS.items()
    }
    locks = {"primary": args.primary_lock_path, "shadow": args.shadow_lock_path}
    members: dict[str, set[int]] = {role: set() for role in ROLE_DEFAULTS}
    runtime: set[int] = set()
    unknown: list[str] = []
    for process in processes.values():
        if process.pid in excluded:
            continue
        if process.uid == uid and process.cwd is None:
            unknown.append(f"PID {process.pid}: cwd/open-file coverage unavailable")
        evidence = "\n".join([process.command, *process.files])
        path_pattern = re.escape(old) + r"(?=/|[\s\"']|$)"
        bound = bool(re.search(path_pattern, evidence)) or head in evidence
        roles = {
            role
            for role, markers in identities.items()
            if any(marker in evidence for marker in markers)
        }
        for role, lock in locks.items():
            if lock in process.files:
                roles.add(role)
                bound = True
        if bound:
            runtime.add(process.pid)
            for role in roles:
                members[role].add(process.pid)
        elif roles:
            # A relative script/import or wrapper cannot be assumed to be a successor.
            unknown.append(f"PID {process.pid}: runtime role has no verified old/source binding")
    # A child may outlive a scheduler and retain none of its parent's argv.
    pending = True
    while pending:
        pending = False
        for process in processes.values():
            if process.ppid in runtime and process.pid not in runtime | excluded:
                runtime.add(process.pid)
                pending = True

    def classification(pids: set[int]) -> str:
        return "PRESENT" if pids else "UNVERIFIABLE" if unknown else "ABSENT"

    result: Record = {
        "scope": f"user {uid}; argv, cwd/open files, descendant closure",
        "old_worktree": old,
        "old_head": head,
        "excluded_checkpoint_pids": sorted(excluded),
        "process_count": len(processes),
        "uncertainties": unknown,
        "runtime": {"classification": classification(runtime), "pids": sorted(runtime)},
        "processes": [
            {
                "pid": p.pid,
                "ppid": p.ppid,
                "uid": p.uid,
                "command": p.command,
                "cwd": p.cwd,
                "files": p.files,
            }
            for p in processes.values()
            if p.pid in runtime
        ],
    }
    for role, pids in members.items():
        result[role] = {"classification": classification(pids), "pids": sorted(pids)}
    return result


def ownership_checks(checks: Checks, args: argparse.Namespace, runner: Runner, job: object) -> None:
    snapshot = checks.add("process_snapshot", lambda: process_snapshot(args, runner))
    for role in (*ROLE_DEFAULTS, "runtime"):
        checks.add(
            f"old_{role}_ownership" if role != "runtime" else "old_runtime_process_ownership",
            lambda role=role: object_record(object_record(snapshot)[role]),
            accept=lambda value: (
                object_record(value).get("classification")
                in ({"ABSENT"} if args.phase == "post-unload" else {"PRESENT", "ABSENT"})
            ),
            expected="ABSENT" if args.phase == "post-unload" else "verifiable snapshot",
        )

    def full_ownership() -> Record:
        process: Record = (
            object_record(object_record(snapshot)["runtime"])
            if snapshot
            else {
                "classification": "UNVERIFIABLE",
                "pids": [],
            }
        )
        state = object_record(job)["state"] if job else "UNVERIFIABLE"
        classification = process["classification"]
        # A loaded recurring job is an owner between executions, even if ps is idle.
        if state == "LOADED" or classification == "PRESENT":
            classification = "PRESENT"
        elif state != "UNLOADED":
            classification = "UNVERIFIABLE"
        return {
            "classification": classification,
            "launchagent": state,
            "process_classification": process["classification"],
            "pids": process["pids"],
        }

    checks.add(
        "old_runtime_ownership",
        full_ownership,
        accept=lambda value: (
            object_record(value)["classification"]
            in ({"ABSENT"} if args.phase == "post-unload" else {"PRESENT", "ABSENT"})
        ),
        expected="ABSENT" if args.phase == "post-unload" else "verifiable snapshot",
    )


def pre_cutover(checks: Checks, args: argparse.Namespace, runner: Runner) -> None:
    check_source(checks, args, runner, "successor")
    check_source(checks, args, runner, "rollback")
    live = checks.add("live_plist", lambda: plist_snapshot(Path(args.plist_path)))
    checks.equal(
        "live_plist_label",
        lambda: object_record(object_record(live)["binding"])["Label"],
        args.expected_label,
    )
    if args.expected_plist_sha256:
        checks.equal(
            "live_plist_sha256", lambda: object_record(live)["sha256"], args.expected_plist_sha256
        )
    checks.equal(
        "rollback_backup_sha256",
        lambda: hashlib.sha256(read_bytes(Path(args.expected_rollback_backup_path))).hexdigest(),
        args.expected_rollback_backup_sha256,
    )
    job = checks.add("launchagent", lambda: launch_snapshot(args, runner))
    db = checks.add("db_metadata", lambda: database_metadata(Path(args.db_path)))
    checks.equal("db_schema", lambda: object_record(db)["schema_version"], args.expected_db_schema)
    ownership_checks(checks, args, runner, job)


def post_unload(checks: Checks, args: argparse.Namespace, runner: Runner) -> None:
    check_source(checks, args, runner, "rollback")
    snapshot = checks.add("launchagent", lambda: launch_snapshot(args, runner))
    checks.equal("launchagent_unloaded", lambda: object_record(snapshot)["state"], "UNLOADED")
    # This always runs, independently of the launchd result or primary lock state.
    ownership_checks(checks, args, runner, snapshot)


def health_snapshot(args: argparse.Namespace, now: datetime) -> Record:
    def invalid_constant(value: str) -> NoReturn:
        raise Unverifiable(f"non-JSON health constant: {value}")

    health = object_record(
        json.loads(
            read_bytes(Path(args.health_path)),
            parse_constant=invalid_constant,
        )
    )
    timestamp = health.get("finished_at")
    if health.get("current_status") == "RUNNING" and timestamp is None:
        timestamp = health.get("started_at")
    if not isinstance(timestamp, str):
        raise Unverifiable("health timestamp missing")
    recorded = datetime.fromisoformat(timestamp)
    if recorded.tzinfo is None:
        raise Unverifiable("health timestamp must have an explicit timezone")
    if "last_error" not in health and "error_message" not in health:
        raise Unverifiable("health error field missing")
    if type(health.get("ready_before_draw")) is not bool:
        raise Unverifiable("health readiness must be a boolean")
    for name in ("last_error", "error_message", "error_class"):
        if health.get(name) is not None and not isinstance(health[name], str):
            raise Unverifiable(f"health {name} must be text or null")
    return {
        "authority": args.health_path,
        "label": health.get("label"),
        "schema_version": health.get("schema_version"),
        "source_worktree": health.get("source_worktree"),
        "observed_source_head": health.get("observed_source_head"),
        "timestamp": timestamp,
        "age_seconds": (now - recorded).total_seconds(),
        "state": health.get("current_status"),
        "readiness": health.get("ready_before_draw"),
        "last_error": health.get("last_error") or health.get("error_message"),
        "error_class": health.get("error_class"),
    }


def post_load(checks: Checks, args: argparse.Namespace, runner: Runner, now: datetime) -> None:
    check_source(checks, args, runner, "successor")
    plist = checks.add("live_plist", lambda: plist_snapshot(Path(args.plist_path)))
    job = checks.add("launchagent", lambda: launch_snapshot(args, runner))
    checks.equal("launchagent_loaded", lambda: object_record(job)["state"], "LOADED")
    checks.equal("launchagent_enabled", lambda: enabled_snapshot(args, runner), True)
    loaded = checks.add("loaded_binding", lambda: launch_fields(str(object_record(job)["raw"])))
    expected_args = [args.expected_interpreter, args.expected_script_path, "run"]
    expected_plist = {
        "Label": args.expected_label,
        "WorkingDirectory": args.expected_successor_worktree,
        "ProgramArguments": expected_args,
        "StartInterval": args.expected_start_interval,
    }
    for key, expected in expected_plist.items():
        checks.equal(
            f"plist_{key}",
            lambda key=key: object_record(object_record(plist)["binding"])[key],
            expected,
        )
    checks.equal(
        "plist_enabled",
        lambda: object_record(object_record(plist)["binding"]).get("Disabled", False),
        False,
    )
    checks.equal(
        "plist_pythonpath",
        lambda: object_record(
            object_record(object_record(plist)["binding"])["EnvironmentVariables"]
        )["PYTHONPATH"],
        args.expected_pythonpath,
    )
    expected_loaded = {
        "path": args.plist_path,
        "working directory": args.expected_successor_worktree,
        "program": args.expected_interpreter,
        "arguments": expected_args,
        "run interval": f"{args.expected_start_interval} seconds",
    }
    for key, expected in expected_loaded.items():
        checks.equal(f"loaded_{key}", lambda key=key: object_record(loaded)[key], expected)
    checks.equal(
        "loaded_pythonpath",
        lambda: [
            line
            for line in cast(list[str], object_record(loaded)["environment"])
            if line.startswith("PYTHONPATH => ")
        ],
        [f"PYTHONPATH => {args.expected_pythonpath}"],
    )
    checks.add(
        "latest_exit",
        lambda: object_record(loaded).get("last exit code"),
        accept=lambda value: value in (None, "0", "(never exited)"),
        expected="0 or not yet available",
    )
    health = checks.add("health", lambda: health_snapshot(args, now))
    for key, expected in {
        "label": args.expected_label,
        "schema_version": args.expected_health_schema,
        "source_worktree": args.expected_successor_worktree,
        "observed_source_head": args.expected_successor_head,
    }.items():
        checks.equal(f"health_{key}", lambda key=key: object_record(health)[key], expected)
    checks.add(
        "health_fresh",
        lambda: object_record(health)["age_seconds"],
        accept=lambda value: (
            isinstance(value, (int, float)) and 0 <= value <= args.max_health_age_seconds
        ),
        expected=args.max_health_age_seconds,
    )
    checks.add(
        "health_state",
        lambda: object_record(health)["state"],
        accept=lambda value: value in args.expected_health_state,
        expected=args.expected_health_state,
    )
    checks.equal(
        "health_readiness",
        lambda: object_record(health)["readiness"],
        args.expected_readiness == "true",
    )
    checks.equal("health_last_error", lambda: object_record(health)["last_error"], None)
    checks.equal("health_error_class", lambda: object_record(health)["error_class"], None)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def parser() -> Parser:
    result = Parser(description=__doc__, add_help=False, allow_abbrev=False)
    result.add_argument("phase", choices=PHASES, nargs="?")
    result.add_argument("--help", action="store_true")
    result.add_argument("--launch-domain", default=f"gui/{os.getuid()}")
    common = [
        "expected-label",
        "plist-path",
        "expected-successor-worktree",
        "expected-successor-head",
        "expected-successor-tree",
        "expected-successor-ref",
        "expected-rollback-worktree",
        "expected-rollback-head",
        "expected-plist-sha256",
        "expected-rollback-backup-path",
        "expected-rollback-backup-sha256",
        "db-path",
        "primary-lock-path",
        "shadow-lock-path",
        "health-path",
        "expected-interpreter",
        "expected-script-path",
        "expected-pythonpath",
        "expected-health-schema",
    ]
    for name in common:
        result.add_argument("--" + name)
    for name in ("expected-db-schema", "expected-start-interval", "max-health-age-seconds"):
        result.add_argument("--" + name, type=int)
    result.add_argument("--expected-health-state", action="append")
    result.add_argument("--expected-readiness", choices=("true", "false"))
    for role in ROLE_DEFAULTS:
        result.add_argument(
            f"--old-{role}-identity",
            action="append",
            help=f"Additional literal {role} process/hook marker; repeatable.",
        )
    return result


def validate(args: argparse.Namespace) -> None:
    required = ["phase", "expected_label"]
    if args.phase in ("pre-cutover", "post-load"):
        required += ["expected_successor_worktree", "expected_successor_head", "plist_path"]
    if args.phase in ("pre-cutover", "post-unload"):
        required += [
            "expected_rollback_worktree",
            "expected_rollback_head",
            "primary_lock_path",
            "shadow_lock_path",
        ]
    if args.phase == "pre-cutover":
        required += [
            "expected_successor_tree",
            "expected_successor_ref",
            "expected_rollback_backup_path",
            "expected_rollback_backup_sha256",
            "db_path",
            "expected_db_schema",
        ]
    if args.phase == "post-load":
        required += [
            "health_path",
            "expected_interpreter",
            "expected_script_path",
            "expected_pythonpath",
            "expected_start_interval",
            "expected_health_schema",
            "expected_health_state",
            "expected_readiness",
            "max_health_age_seconds",
        ]
    missing = [name.replace("_", "-") for name in required if getattr(args, name) is None]
    if missing:
        raise ValueError("required for this phase: " + ", ".join(missing))
    if not re.fullmatch(r"(?:gui|user)/[0-9]+", args.launch_domain):
        raise ValueError("launch-domain must be gui/UID or user/UID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.expected_label):
        raise ValueError("invalid LaunchAgent label")
    for name, value in vars(args).items():
        if value is None:
            continue
        if (name.endswith(("_path", "_worktree")) or name == "expected_interpreter") and (
            not Path(value).is_absolute() or str(Path(value)) != value or ".." in Path(value).parts
        ):
            raise ValueError(f"{name} must be a normalized absolute path")
        if name.endswith(("_head", "_tree")) and not re.fullmatch(
            r"[0-9a-f]{40}|[0-9a-f]{64}", value
        ):
            raise ValueError(f"{name} must be an explicit full object ID")
        if name.endswith("sha256") and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{name} must be a SHA-256 hex digest")
        if (
            name in ("expected_db_schema", "expected_start_interval", "max_health_age_seconds")
            and value <= 0
        ):
            raise ValueError(f"{name} must be positive")
        if isinstance(value, str) and (not value or any(ord(c) < 32 for c in value)):
            raise ValueError(f"{name} contains an empty or control-character value")
        if isinstance(value, list) and any(not item for item in cast(list[str], value)):
            raise ValueError(f"{name} must contain nonempty identities/states")
    if args.expected_successor_ref and not args.expected_successor_ref.startswith(
        ("refs/heads/", "refs/tags/", "refs/remotes/")
    ):
        raise ValueError("expected-successor-ref must name a durable, fully qualified ref")


def main(
    argv: Sequence[str] | None = None, *, runner: Runner = run_command, now: datetime | None = None
) -> int:
    cli = parser()
    phase = "UNKNOWN"
    try:
        args = cli.parse_args(argv)
        phase = args.phase or phase
        if args.help:
            print(
                json.dumps(
                    {
                        "phase": phase,
                        "status": "PASS",
                        "checks": {"usage": cli.format_help()},
                        "failures": [],
                    }
                )
            )
            return 0
        validate(args)
    except ValueError as exc:
        print(json.dumps({"phase": phase, "status": "FAIL", "checks": {}, "failures": [str(exc)]}))
        return 2
    checks = Checks(phase)
    observed_at = now or datetime.now(UTC)
    if phase == "pre-cutover":
        pre_cutover(checks, args, runner)
    elif phase == "post-unload":
        post_unload(checks, args, runner)
    else:
        post_load(checks, args, runner, observed_at)
    result = checks.result()
    result["observed_at"] = observed_at.isoformat()
    result["completed_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, sort_keys=True))
    return 1 if checks.failures else 0


if __name__ == "__main__":
    sys.exit(main())
