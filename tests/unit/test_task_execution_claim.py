"""Hermetic ownership regressions; all children finish via input/normal exit."""

# White-box fault injection intentionally exercises private ownership seams.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import ast
import json
import os
import select
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from tools import task_execution_claim as claims

_MODULE_ROOT = Path(claims.__file__).resolve().parents[1]
_HOLD_CHILD = """
import os, select, sys
with open(sys.argv[1], 'a') as output:
    output.write(str(os.getpid()) + '\\n')
print('CHILD_READY', flush=True)
if select.select([sys.stdin], [], [], 8)[0]:
    sys.stdin.readline()
"""
_RUNNER = """
import os, sys
from pathlib import Path
from tools import task_execution_claim as claims
claims.HEARTBEAT_SECONDS = 0.02
store = claims.ClaimStore(Path(sys.argv[1]))
if sys.argv[3] == 'orphan':
    def exit_owner(child, record):
        os._exit(0)
    store._monitor = exit_owner
if sys.argv[3] == 'launch_crash':
    original_write = store._write
    def crash_before_child_record(record):
        if record['child_pid'] is not None:
            os._exit(0)
        original_write(record)
    store._write = crash_before_child_record
print('WRAPPER_READY', flush=True)
sys.stdin.readline()
code = store.run(sys.argv[2], [sys.executable, '-c', sys.argv[5], sys.argv[6]],
                 takeover_stale=sys.argv[4] == 'yes')
print('RESULT ' + str(code), flush=True)
sys.exit(code)
"""


def _environment() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(_MODULE_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}


def _line(process: subprocess.Popen[bytes]) -> str:
    assert process.stdout is not None
    deadline = time.monotonic() + 10
    result = bytearray()
    while time.monotonic() < deadline:
        remaining = max(0, deadline - time.monotonic())
        assert select.select([process.stdout], [], [], remaining)[0], "Child output timed out"
        value = os.read(process.stdout.fileno(), 1)
        assert value, f"Unexpected EOF: {bytes(result)!r}"
        if value == b"\n":
            return result.decode()
        result.extend(value)
    pytest.fail("Child output timed out")


def _start(
    root: Path,
    key: str,
    marker: Path,
    *,
    kind: str = "normal",
    takeover: bool = False,
) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _RUNNER,
            str(root),
            key,
            kind,
            "yes" if takeover else "no",
            _HOLD_CHILD,
            str(marker),
        ],
        cwd=root.parent,
        env=_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert _line(process) == "WRAPPER_READY"
    return process


def _go(process: subprocess.Popen[bytes]) -> None:
    assert process.stdin is not None
    process.stdin.write(b"go\n")
    process.stdin.flush()


@contextmanager
def _children() -> Generator[list[subprocess.Popen[bytes]]]:
    processes: list[subprocess.Popen[bytes]] = []
    try:
        yield processes
    finally:
        # A voluntary input event releases only these test-owned children.
        # Even assertion failures need no process signal; each child also has a
        # bounded input timeout and exits normally if its test disappears.
        for process in processes:
            if process.stdin is not None:
                try:
                    process.stdin.write(b"finish\n")
                    process.stdin.flush()
                except BrokenPipeError:
                    pass
        for process in processes:
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def _seed(store: claims.ClaimStore, key: str = "task", **changes: object) -> claims.Metadata:
    expired = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    started = (datetime.now(UTC) - timedelta(seconds=300)).isoformat()
    data: dict[str, object] = {
        "schema_version": 1,
        "task_key": key,
        "owner_id": str(uuid.uuid4()),
        "owner_pid": os.getpid(),
        "child_pid": None,
        "hostname": socket.gethostname(),
        "started_at_utc": started,
        "heartbeat_at_utc": expired,
        "cwd": str(store.root.parent),
        "command": [sys.executable, "-c", "pass"],
        "claim_root": str(store.root),
        **changes,
    }
    record = cast(claims.Metadata, data)
    with store._transaction():
        store._write(record)
    return record


@pytest.fixture
def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    assert process.wait(timeout=10) == 0
    assert claims._alive(process.pid) is False
    return process.pid


def test_inspect_absent_is_read_only(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    assert store.inspect("task")["status"] == "ABSENT"
    assert not store.root.exists()


@pytest.mark.parametrize("code", [0, 7, 42])
def test_acquisition_completion_and_exit_status(tmp_path: Path, code: int) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    assert store.run("task", [sys.executable, "-c", f"raise SystemExit({code})"]) == code
    assert store.inspect("task")["status"] == "ABSENT"
    assert sorted(path.name for path in store.root.iterdir()) == [".coordination.lock"]


def test_live_claim_metadata_heartbeat_and_duplicate_refusal(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    marker = tmp_path / "started"
    with _children() as processes:
        first = _start(store.root, "task", marker)
        processes.append(first)
        _go(first)
        assert _line(first) == "CHILD_READY"
        state = store.inspect("task")
        assert state["status"] == "ACTIVE"
        assert state["owner_pid"] == first.pid
        assert state["child_pid"] == int(marker.read_text())
        for field in claims.Metadata.__required_keys__:
            assert field in state
        heartbeat = state["heartbeat_at_utc"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            state = store.inspect("task")
            assert state["status"] == "ACTIVE"  # No partial replacement is visible.
            if state["heartbeat_at_utc"] != heartbeat:
                break
        assert state["heartbeat_at_utc"] != heartbeat
        second = _start(store.root, "task", marker)
        processes.append(second)
        _go(second)
        assert json.loads(_line(second))["status"] == "ACTIVE"
        assert second.wait(timeout=10) == claims.REFUSED
        assert marker.read_text().splitlines() == [str(state["child_pid"])]
        assert first.poll() is None
        assert claims._alive(cast(int, state["child_pid"])) is True
    assert store.inspect("task")["status"] == "ABSENT"


@pytest.mark.parametrize("stale", [False, True])
def test_competing_acquisitions_launch_only_one_child(
    tmp_path: Path,
    dead_pid: int,
    stale: bool,
) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    marker = tmp_path / "started"
    if stale:
        _seed(store, owner_pid=dead_pid, child_pid=dead_pid)
    with _children() as processes:
        for _ in range(2):
            processes.append(_start(store.root, "task", marker, takeover=stale))
        for process in processes:
            _go(process)
        lines = [_line(process) for process in processes]
        assert lines.count("CHILD_READY") == 1
        loser = processes[1 - lines.index("CHILD_READY")]
        assert loser.wait(timeout=10) == claims.REFUSED
        assert len(marker.read_text().splitlines()) == 1
    assert store.inspect("task")["status"] == "ABSENT"


def test_different_keys_run_simultaneously(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    with _children() as processes:
        for key in ("alpha", "beta"):
            processes.append(_start(store.root, key, tmp_path / key))
        for process in processes:
            _go(process)
        assert [_line(process) for process in processes] == ["CHILD_READY", "CHILD_READY"]
        assert all(process.poll() is None for process in processes)
        assert all(store.inspect(key)["status"] == "ACTIVE" for key in ("alpha", "beta"))
    assert all(store.inspect(key)["status"] == "ABSENT" for key in ("alpha", "beta"))


@pytest.mark.parametrize("expired", [False, True])
def test_real_owner_exits_but_child_remains_protected(tmp_path: Path, expired: bool) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    marker = tmp_path / "started"
    with _children() as processes:
        owner = _start(store.root, "task", marker, kind="orphan")
        processes.append(owner)
        _go(owner)
        assert _line(owner) == "CHILD_READY"
        assert owner.wait(timeout=10) == 0  # Voluntary os._exit, no signal.
        if expired:
            with store._transaction():
                record = store._read("task")
                assert record is not None
                old = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
                store._write({**record, "started_at_utc": old, "heartbeat_at_utc": old})
        state = store.inspect("task")
        assert state["status"] == "ACTIVE_ORPHAN_CHILD"
        child_pid = cast(int, state["child_pid"])
        assert claims._alive(child_pid) is True
        for takeover in (False, True):
            refused = _start(store.root, "task", marker, takeover=takeover)
            processes.append(refused)
            _go(refused)
            assert json.loads(_line(refused))["status"] == "ACTIVE_ORPHAN_CHILD"
            assert refused.wait(timeout=10) == claims.REFUSED
        assert marker.read_text().splitlines() == [str(child_pid)]
        assert claims._alive(child_pid) is True
        # Let the actual orphan finish normally and observe its output pipe EOF.
        _go(owner)
        assert owner.stdout is not None
        assert select.select([owner.stdout], [], [], 10)[0]
        assert owner.stdout.read() == b""


def test_owner_crash_before_durable_child_pid_never_launches_command(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    marker = tmp_path / "started"
    with _children() as processes:
        owner = _start(store.root, "task", marker, kind="launch_crash")
        processes.append(owner)
        _go(owner)
        assert owner.wait(timeout=10) == 0
        assert owner.stdout is not None
        assert select.select([owner.stdout], [], [], 10)[0]
        assert owner.stdout.read() == b""
        assert not marker.exists()
        assert store.inspect("task")["status"] == "STALE_UNPROVEN"


@pytest.mark.parametrize(
    ("owner", "child", "expired", "expected"),
    [
        (True, False, True, "ACTIVE"),
        (False, True, True, "ACTIVE_ORPHAN_CHILD"),
        (False, True, False, "ACTIVE_ORPHAN_CHILD"),
        (False, False, True, "STALE_CONFIRMED"),
        (False, False, False, "STALE_UNPROVEN"),
        (None, False, True, "STALE_UNPROVEN"),
        (False, None, True, "STALE_UNPROVEN"),
        (None, True, True, "ACTIVE"),
    ],
)
def test_liveness_and_staleness_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner: bool | None,
    child: bool | None,
    expired: bool,
    expected: str,
) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    heartbeat = datetime.now(UTC) - timedelta(seconds=120 if expired else 0)
    _seed(store, owner_pid=100001, child_pid=100002, heartbeat_at_utc=heartbeat.isoformat())

    def liveness(pid: int) -> bool | None:
        return owner if pid == 100001 else child

    monkeypatch.setattr(claims, "_alive", liveness)
    assert store.inspect("task")["status"] == expected
    if expected.startswith("ACTIVE"):
        assert (
            store.run("task", [sys.executable, "-c", "pass"], takeover_stale=True) == claims.REFUSED
        )


def test_stale_requires_explicit_takeover(tmp_path: Path, dead_pid: int) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    original = _seed(store, owner_pid=dead_pid, child_pid=dead_pid)
    before = store.location("task").read_bytes()
    assert store.inspect("task")["status"] == "STALE_CONFIRMED"
    assert store.run("task", original["command"]) == claims.TAKEOVER_REQUIRED
    assert store.location("task").read_bytes() == before
    assert store.run("task", original["command"], takeover_stale=True) == 0
    assert store.inspect("task")["status"] == "ABSENT"


def test_takeover_freshly_revalidates_pid_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dead_pid: int,
) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    original = _seed(store, owner_pid=dead_pid)
    probes = iter([False, True])

    def liveness(pid: int) -> bool:
        return next(probes)

    monkeypatch.setattr(claims, "_alive", liveness)
    assert store.run("task", original["command"], takeover_stale=True) == claims.REFUSED
    assert store._read("task") == original


def test_cross_host_claim_never_probes_or_takes_over(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dead_pid: int,
) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    original = _seed(store, owner_pid=dead_pid, hostname="different-" + socket.gethostname())

    def forbidden_probe(pid: int) -> bool:
        pytest.fail(f"Cross-host PID {pid} must not be probed")

    monkeypatch.setattr(claims, "_alive", forbidden_probe)
    assert store.inspect("task")["status"] == "STALE_UNPROVEN"
    assert store.run("task", original["command"], takeover_stale=True) == claims.UNVERIFIABLE
    assert store._read("task") == original


@pytest.mark.parametrize("payload", ["{", "{}", "[]", '{"task_key":"x","task_key":"y"}'])
def test_malformed_claim_fails_closed(tmp_path: Path, payload: str) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    store.root.mkdir()
    store.location("task").write_text(payload)
    assert store.inspect("task")["status"] == "UNVERIFIABLE"
    assert (
        store.run("task", [sys.executable, "-c", "pass"], takeover_stale=True)
        == claims.UNVERIFIABLE
    )
    assert store.location("task").read_text() == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("child_pid", -1),
        ("owner_pid", True),
        ("child_pid", 2**50),
        ("owner_pid", 0),
        ("heartbeat_at_utc", "2026-01-01"),
        ("owner_id", "unknown"),
        ("schema_version", True),
        ("command", []),
        ("command", [42]),
        ("claim_root", "/invalid"),
        ("task_key", "other"),
    ],
)
def test_invalid_metadata_fields_fail_closed(tmp_path: Path, field: str, value: object) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    original = _seed(store)
    store.location("task").write_text(json.dumps({**original, field: value}))
    assert store.inspect("task")["status"] == "UNVERIFIABLE"


def test_release_and_heartbeat_never_overwrite_another_owner(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    previous = _seed(store)
    replacement = _seed(store)
    with store._transaction(), pytest.raises(claims.ClaimError, match="Ownership changed"):
        store._release(previous)
    with pytest.raises(claims.ClaimError, match="Ownership changed"):
        store._assert_owner(previous)
    assert store._read("task") == replacement


def test_atomic_write_failure_preserves_previous_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    original = _seed(store)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("Injected replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with store._transaction(), pytest.raises(OSError, match="Injected replacement failure"):
        store._write({**original, "owner_id": str(uuid.uuid4())})
    assert store._read("task") == original
    assert not list(store.root.glob("*.tmp"))


def test_task_keys_cannot_escape_root_and_retain_exact_identity(tmp_path: Path) -> None:
    store = claims.ClaimStore(tmp_path / "claims")
    keys = ["../outside", "/absolute", "a/b", "a\\b", "", "é", "e\u0301", "../" * 1000]
    paths = [store.location(key) for key in keys]
    assert len(set(paths)) == len(keys)
    for key, path in zip(keys, paths, strict=True):
        assert path.parent == store.root
        assert len(path.name) == 69
        _seed(store, key)
        assert store.inspect(key)["task_key"] == key


def test_symlink_authority_and_metadata_fail_closed(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(destination, target_is_directory=True)
    with pytest.raises(claims.ClaimError, match="symlinks"):
        claims.ClaimStore(alias)
    store = claims.ClaimStore(destination)
    target = tmp_path / "untouched"
    target.write_text("original")
    store.location("task").symlink_to(target)
    assert store.inspect("task")["status"] == "UNVERIFIABLE"
    assert store.run("task", [sys.executable, "-c", "pass"]) == claims.UNVERIFIABLE
    assert target.read_text() == "original"


def _git_at(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.PIPE,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    ).strip()


def test_linked_worktrees_share_canonical_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = tmp_path / "repository"
    canonical.mkdir()
    _git_at(canonical, "init", "--initial-branch=main")
    _git_at(
        canonical,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    linked = tmp_path / "linked"
    other = tmp_path / "other"
    _git_at(canonical, "worktree", "add", "--detach", str(linked))
    _git_at(canonical, "worktree", "add", "--detach", str(other))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-repository"))
    expected = canonical / ".task-data" / "execution-claims"
    assert claims.resolve_claim_root(canonical) == expected
    assert claims.resolve_claim_root(linked) == expected
    assert claims.resolve_claim_root(other) == expected
    assert not expected.exists()  # Resolver itself is read-only.
    store = claims.ClaimStore(expected)
    _seed(store)
    assert (
        claims.ClaimStore(claims.resolve_claim_root(linked)).inspect("task")["status"] == "ACTIVE"
    )
    assert claims.ClaimStore(claims.resolve_claim_root(other)).inspect("task")["status"] == "ACTIVE"


def test_unresolvable_authority_has_no_fallback(tmp_path: Path) -> None:
    # tmp_path can itself live inside a repository. A broken Git boundary keeps
    # this test independent of ancestor discovery and real runtime authority.
    boundary = tmp_path / ".git"
    boundary.write_text("gitdir: missing-git-directory\n")
    with pytest.raises(claims.ClaimError, match="Git common repository authority"):
        claims.resolve_claim_root(tmp_path)
    assert list(tmp_path.iterdir()) == [boundary]


def test_only_signal_zero_and_ambiguous_probe_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = os.kill
    observed: list[int] = []

    def probe(pid: int, sig: int) -> None:
        observed.append(sig)
        assert sig == 0
        original(pid, sig)

    monkeypatch.setattr(os, "kill", probe)
    assert claims._alive(os.getpid()) is True
    assert observed == [0]

    def denied(pid: int, sig: int) -> None:
        assert sig == 0
        raise PermissionError("Ambiguous PID")

    monkeypatch.setattr(os, "kill", denied)
    assert claims._alive(os.getpid()) is None
    tree = ast.parse(Path(claims.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"terminate", "send_signal", "killpg"}
                if node.func.attr == "kill":
                    assert isinstance(node.args[1], ast.Constant) and node.args[1].value == 0
            assert not any(keyword.arg == "shell" for keyword in node.keywords)


def test_cli_inspect_is_read_only_and_run_requires_separator(tmp_path: Path) -> None:
    canonical = tmp_path / "repository"
    canonical.mkdir()
    _git_at(canonical, "init")
    cli = [sys.executable, str(Path(claims.__file__).resolve())]
    inspected = subprocess.run(
        [*cli, "inspect", "--task-key", "task", "--format", "json"],
        cwd=canonical,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspected.returncode == 0
    assert json.loads(inspected.stdout)["status"] == "ABSENT"
    assert not (canonical / ".task-data").exists()
    invalid = subprocess.run(
        [*cli, "run", "--task-key", "task", sys.executable, "-c", "pass"],
        cwd=canonical,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode == 2
    assert not (canonical / ".task-data").exists()
