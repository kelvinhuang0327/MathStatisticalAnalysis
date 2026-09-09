"""A1-A6: real launcher/guard processes, hermetic Git, bounded voluntary exits.

Instrumentation is appended ONLY to launcher copies in pytest temporary Git
repositories. The shipped launcher has no test mode or arbitrary child API.
"""

# White-box fault injection and independent serialization inspect private seams.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import itertools
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Generator
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from tools import run_expected_max_main_matches_exact_1exchange_ascent as launcher
from tools import task_execution_claim as claims

from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import (
    iterative_exact_1exchange_expected_max_ascent,
)

_ENTRY = "tools/run_expected_max_main_matches_exact_1exchange_ascent.py"
_INSTRUMENTATION = """
# Installed only in this test's disposable launcher copy.
import time
from tools import task_execution_claim as test_claims
test_claims.HEARTBEAT_SECONDS = 0.05

def test_wait(path):
    deadline = time.monotonic() + 8
    while not path.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("Test release deadline expired")
        time.sleep(0.01)

test_real_compute = iterative_exact_1exchange_expected_max_ascent
def test_compute(*args, **kwargs):
    if sys.argv[1:2] != ["_child"]:
        return test_real_compute(*args, **kwargs)
    control = Path(os.environ["LAUNCHER_TEST_CONTROL"])
    with (control / "entries").open("a") as stream:
        stream.write(str(os.getpid()) + "\\n")
    if os.environ.get("LAUNCHER_TEST_HOLD") == "1":
        test_wait(control / "finish")
    if os.environ.get("LAUNCHER_TEST_FAIL") == "compute":
        raise RuntimeError("Injected scientific failure")
    return test_real_compute(*args, **kwargs)
iterative_exact_1exchange_expected_max_ascent = test_compute

test_real_replace = os.replace
def test_replace(source, destination):
    control = Path(os.environ["LAUNCHER_TEST_CONTROL"])
    destination = Path(destination)
    if destination.name in ("result.json", "receipt.json", "input.json"):
        # The pending inode is complete JSON before atomic publication.
        payload = json.loads(Path(source).read_text())
        if destination.name == "result.json":
            assert not destination.exists()
            if destination.with_name("receipt.json").exists():
                saved_receipt = json.loads(destination.with_name("receipt.json").read_text())
                assert saved_receipt["outcome"] == "PREPARED"
            if os.environ.get("LAUNCHER_TEST_FAIL") == "persistence":
                raise OSError("Injected result publication failure")
            if os.environ.get("LAUNCHER_TEST_PUBLISH_HOLD") == "1":
                (control / "result_ready").write_text(str(destination))
                test_wait(control / "publish")
        if destination.name == "receipt.json" and payload["successful_completion"]:
            assert destination.with_name("result.json").is_file()
            result = json.loads(destination.with_name("result.json").read_text())
            assert result["iterations"][-1]["accepted_move"] is False
        with (control / "publications").open("a") as stream:
            stream.write(destination.name + "\\n")
    return test_real_replace(source, destination)
os.replace = test_replace

from lottolab.research import expected_max_main_matches_exact_1exchange_ascent as test_science
test_real_evaluate = test_science.evaluate_expected_max_one_exchange_neighborhood
def test_evaluate(*args):
    validating = sys._getframe(1).f_code.co_name == "__post_init__"
    phase = "VALIDATION_RESCAN" if validating else "CONTINUATION"
    control = Path(os.environ["LAUNCHER_TEST_CONTROL"])
    with (control / "scans").open("a") as stream:
        stream.write(json.dumps({"phase": phase, "pid": os.getpid()}) + "\\n")
    return test_real_evaluate(*args)
test_science.evaluate_expected_max_one_exchange_neighborhood = test_evaluate

test_real_atomic = _atomic_json
test_destination = None
test_payload = None
def test_atomic(destination, value):
    global test_destination, test_payload
    test_destination, test_payload = destination, value
    try:
        test_real_atomic(destination, value)
    finally:
        test_destination = test_payload = None
    if (sys.argv[1:2] == ["_child"] and destination.name == "checkpoint.json"
            and str(value["sequence"]) == os.environ.get("LAUNCHER_TEST_CRASH_SEQ")):
        (Path(os.environ["LAUNCHER_TEST_CONTROL"]) / "crashed").write_text(str(os.getpid()))
        os._exit(23)  # Voluntary, test-owned process exit after directory fsync.
_atomic_json = test_atomic

def test_fault(kind):
    return (test_destination is not None and test_destination.name == "checkpoint.json"
        and test_payload["sequence"] == 2 and sys.argv[1:2] == ["_child"]
        and os.environ.get("LAUNCHER_TEST_CHECKPOINT_FAULT") == kind)
test_original_fdopen = os.fdopen
class TestPartialWriter:
    def __init__(self, stream): self.stream = stream
    def __enter__(self): return self
    def __exit__(self, *args): self.stream.close()
    def write(self, payload):
        self.stream.write(payload[:len(payload)//2])
        raise OSError("Injected partial temp write")
def test_fdopen(fd, *args, **kwargs):
    stream = test_original_fdopen(fd, *args, **kwargs)
    return TestPartialWriter(stream) if test_fault("temp_write") else stream
os.fdopen = test_fdopen
test_original_fsync = os.fsync
def test_fsync(fd):
    mode = os.fstat(fd).st_mode
    if ((test_fault("file_fsync") and stat.S_ISREG(mode))
            or (test_fault("directory_fsync") and stat.S_ISDIR(mode))):
        raise OSError("Injected checkpoint fsync failure")
    return test_original_fsync(fd)
os.fsync = test_fsync
test_checkpoint_replace = os.replace
def test_fault_replace(source, destination):
    if test_fault("rename"):
        raise OSError("Injected checkpoint rename failure")
    return test_checkpoint_replace(source, destination)
os.replace = test_fault_replace

test_original_write = test_claims.ClaimStore._write
def test_transfer_write(self, record):
    crash = os.environ.get("LAUNCHER_TEST_TRANSFER_CRASH")
    if crash and record["child_pid"] is None:
        (Path(os.environ["LAUNCHER_TEST_CONTROL"]) / "successor").write_text(record["owner_id"])
        if crash == "before": os._exit(21)
        test_original_write(self, record)
        os._exit(22)
    return test_original_write(self, record)
test_claims.ClaimStore._write = test_transfer_write

test_original_run = test_claims.ClaimStore.run
def test_run(self, key, command, **kwargs):
    if os.environ.get("LAUNCHER_TEST_SELECT") == "1":
        control = Path(os.environ["LAUNCHER_TEST_CONTROL"])
        (control / "selected").touch()
        test_wait(control / "admit")
    return test_original_run(self, key, command, **kwargs)
test_claims.ClaimStore.run = test_run

if os.environ.get("LAUNCHER_TEST_ORPHAN") == "1":
    def test_exit_wrapper(self, child, record):
        # The existing run gate has durably recorded the actual child PID.
        durable = self._read(record["task_key"])
        assert durable["child_pid"] == child.pid
        os._exit(0)
    test_claims.ClaimStore._monitor = test_exit_wrapper

test_real_main = main
def main(argv=None):
    control = Path(os.environ["LAUNCHER_TEST_CONTROL"])
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["run"] and os.environ.get("LAUNCHER_TEST_START") == "1":
        (control / ("ready-" + str(os.getpid()))).touch()
        test_wait(control / "start")
    return test_real_main(argv)
"""


def _input(**changes: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "method_id": launcher.METHOD_ID,
        "lottery_id": "SYNTHETIC",
        "pool_size": 10,
        "draw_size": 3,
        "k": 2,
        "seed_portfolio": [[1, 2, 3], [1, 2, 4]],
        **changes,
    }


def _wait(predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < deadline, "Bounded test observation timed out"
        time.sleep(0.01)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    ).strip()


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        self.control = root / "control"
        self.repo.mkdir()
        self.control.mkdir()
        self.processes: list[subprocess.Popen[bytes]] = []
        for rel in launcher.COMPATIBILITY_PATHS:
            if not (launcher.CHECKOUT / rel).exists():
                continue
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            text = (launcher.CHECKOUT / rel).read_text()
            if rel == _ENTRY:
                text = text.replace(
                    '\nif __name__ == "__main__":',
                    _INSTRUMENTATION + '\nif __name__ == "__main__":',
                )
            path.write_text(text)
        (self.repo / ".gitignore").write_text(".task-data/\n")
        _git(self.repo, "init", "--initial-branch=main")
        _git(self.repo, "add", ".")
        _git(
            self.repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "hermetic fixture",
        )
        self.input = root / "input.json"
        self.input.write_text(json.dumps(_input()))
        self.snapshot = launcher.read_input(self.input)
        self.store = claims.ClaimStore(claims.resolve_claim_root(self.repo))
        self.attempts = launcher._attempts_root(self.store.root, self.snapshot)

    def linked(self, name: str) -> Path:
        path = self.root / name
        _git(self.repo, "worktree", "add", "--detach", str(path))
        return path

    def start(
        self,
        *args: str,
        checkout: Path | None = None,
        input_path: Path | None = None,
        flags: tuple[str, ...] = (),
    ) -> subprocess.Popen[bytes]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "LAUNCHER_TEST_"))}
        env.update(PYTHONDONTWRITEBYTECODE="1", LAUNCHER_TEST_CONTROL=str(self.control))
        for flag in flags:
            key, value = flag.split("=", 1)
            env["LAUNCHER_TEST_" + key] = value
        command = [sys.executable, "-I", "-B", str((checkout or self.repo) / _ENTRY), *args]
        if args[0] in ("run", "inspect"):
            command.extend(["--input", str(input_path or self.input)])
        process = subprocess.Popen(
            command,
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(process)
        return process

    def run(self, *args: str) -> tuple[int, str, str]:
        process = self.start(*args)
        out, err = process.communicate(timeout=10)
        return cast(int, process.returncode), out.decode(), err.decode()

    def count(self) -> int:
        marker = self.control / "entries"
        return len(marker.read_text().splitlines()) if marker.exists() else 0

    def receipts(self) -> list[Path]:
        return sorted(self.attempts.glob("*/receipt.json"))

    def close(self) -> None:
        # Only voluntary releases. Even a failed assertion cannot leave held children.
        for name in ("start", "finish", "publish", "admit"):
            (self.control / name).touch()
        for process in self.processes:
            # communicate also observes EOF from any surviving orphan child.
            process.communicate(timeout=10)


@pytest.fixture
def box(tmp_path: Path) -> Generator[Sandbox]:
    sandbox = Sandbox(tmp_path)
    try:
        yield sandbox
    finally:
        sandbox.close()


def _seed(box: Sandbox, **changes: object) -> claims.Metadata:
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    assert dead.wait(timeout=10) == 0
    assert claims._alive(dead.pid) is False
    old = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    record = cast(
        claims.Metadata,
        {
            "schema_version": 1,
            "task_key": box.snapshot.task_key,
            "owner_id": str(uuid.uuid4()),
            "owner_pid": dead.pid,
            "child_pid": None,
            "hostname": socket.gethostname(),
            "started_at_utc": old,
            "heartbeat_at_utc": old,
            "cwd": str(box.root),
            "command": [sys.executable, "-c", "pass"],
            "claim_root": str(box.store.root),
            **changes,
        },
    )
    with box.store._transaction():
        box.store._write(record)
    return record


def _expected_json(value: object) -> object:
    """Independent full-result encoder; never uses the launcher's serializer."""
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _expected_json(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_expected_json(item) for item in cast(tuple[object, ...], value)]
    return value


def test_a1_normalization_and_identity_bytes(tmp_path: Path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "another.json"
    first.write_text(json.dumps(_input()))
    second.write_text(json.dumps(_input(seed_portfolio=[[4, 2, 1], [3, 1, 2]]), indent=4))
    a, b = launcher.read_input(first), launcher.read_input(second)
    assert a == b and a.task_key == b.task_key
    identity = {
        "method_id": "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1",
        "lottery_id": "SYNTHETIC",
        "pool_size": 10,
        "draw_size": 3,
        "draw_model": "UNIFORM_MAIN_WITHOUT_REPLACEMENT_V1",
        "k": 2,
        "seed_sha256": hashlib.sha256(b"[[1,2,3],[1,2,4]]").hexdigest(),
        "semantics_id": "EXACT_FULL_1EXCHANGE_STRICT_BEST_LEX_UNTIL_LOCAL_OPTIMUM_V1",
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    assert a.identity == identity
    assert a.h == digest and a.task_key == launcher.METHOD_ID + ":" + digest
    for changes in (
        {"seed_portfolio": [[1, 2, 3], [4, 5, 6]]},
        {"k": 3, "seed_portfolio": [[1, 2, 3], [1, 2, 4], [1, 2, 5]]},
        {"pool_size": 9},
        {"draw_size": 2, "seed_portfolio": [[1, 2], [1, 3]]},
    ):
        assert launcher.validate_input(_input(**changes)).task_key != a.task_key


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("method_id", "unsupported"),
        ("pool_size", True),
        ("pool_size", 0),
        ("pool_size", 65),
        ("pool_size", 11),
        ("draw_size", True),
        ("draw_size", 0),
        ("draw_size", 11),
        ("draw_size", 10),
        ("k", True),
        ("k", 0),
        ("k", 4),
        ("k", 21),
        ("k", 3),
        ("k", 2.0),
        ("lottery_id", "OTHER"),
        ("lottery_id", "BIG_LOTTO"),
        ("seed_portfolio", [[True, 2, 3], [1, 2, 4]]),
        ("seed_portfolio", [[1, 2.0, 3], [1, 2, 4]]),
        ("seed_portfolio", [[0, 2, 3], [1, 2, 4]]),
        ("seed_portfolio", [[1, 2, 11], [1, 2, 4]]),
        ("seed_portfolio", [[1, 1, 3], [1, 2, 4]]),
        ("seed_portfolio", [[1, 2, 3], [3, 2, 1]]),
        ("seed_portfolio", [[1, 2], [1, 2, 4]]),
        ("seed_portfolio", "invalid"),
    ],
)
def test_a1_invalid_input_is_never_repaired(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        launcher.validate_input(_input(**{field: value}))


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        {**_input(), "extra": 1},
        _input(pool_size=3, draw_size=1, k=3, seed_portfolio=[[1], [2], [3]]),
    ],
)
def test_a1_invalid_objects_and_no_exchange(raw: object) -> None:
    with pytest.raises(ValueError):
        launcher.validate_input(raw)


def test_a1_duplicate_json_keys_and_immutable_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        launcher.read_input(path)
    raw = _input()
    snapshot = launcher.validate_input(raw)
    before = snapshot.payload
    cast(list[list[int]], raw["seed_portfolio"])[0][0] = 9
    snapshot.identity["k"] = 20
    snapshot.canonical_input["k"] = 20
    assert snapshot.payload == before
    with pytest.raises(AttributeError):
        snapshot.k = 20  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize("k", [2, 3, 5, 10, 20])
def test_a1_all_production_k_use_guard_once_without_computation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    k: int,
) -> None:
    path = tmp_path / "input.json"
    seed = list(itertools.islice(itertools.combinations(range(1, 50), 6), k))
    path.write_text(
        json.dumps(
            _input(lottery_id="BIG_LOTTO", pool_size=49, draw_size=6, k=k, seed_portfolio=seed)
        )
    )
    calls: list[tuple[str, list[str]]] = []
    reads = 0
    original_read = Path.read_bytes

    def read_once(self: Path) -> bytes:
        nonlocal reads
        assert self == path
        reads += 1
        return original_read(self)

    def guarded(
        self: claims.ClaimStore, key: str, command: list[str], *, takeover_stale: bool = False
    ) -> int:
        assert self.root == tmp_path / "claims"
        assert not takeover_stale
        calls.append((key, command))
        path.write_text("mutated after validation")
        assert json.loads(command[5])["k"] == k
        assert str(path) not in command
        return 75  # No lottery-scale child is launched in this routing test.

    def claim_root(cwd: Path) -> Path:
        return tmp_path / "claims"

    monkeypatch.setattr(Path, "read_bytes", read_once)
    monkeypatch.setattr(launcher, "resolve_claim_root", claim_root)
    monkeypatch.setattr(claims.ClaimStore, "run", guarded)
    assert launcher.main(["run", "--input", str(path)]) == 75
    assert reads == 1 and len(calls) == 1
    assert calls[0][1][4] == "_child"
    assert not (tmp_path / "claims").exists()


def test_inspect_read_only_and_identity_excludes_source_provenance(box: Sandbox) -> None:
    first = box.linked("first")
    second = box.linked("second")
    (second / "unrelated.txt").write_text("dirty")
    _git(
        second,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-m",
        "different source",
    )
    states: list[dict[str, object]] = []
    for checkout in (first, second):
        process = box.start("inspect", checkout=checkout)
        out, err = process.communicate(timeout=10)
        assert process.returncode == 0, err
        states.append(json.loads(out))
    assert states[0] == states[1]
    assert states[0]["status"] == "ABSENT"
    assert not box.store.root.exists() and not box.attempts.exists()


@pytest.mark.parametrize("stale", [False, True])
def test_a2_a4_cross_worktree_competing_launchers(box: Sandbox, stale: bool) -> None:
    first, second = box.linked("first"), box.linked("second")
    assert claims.resolve_claim_root(first) == claims.resolve_claim_root(second) == box.store.root
    if stale:
        _seed(box)
    reordered = box.root / "reordered.json"
    reordered.write_text(json.dumps(_input(seed_portfolio=[[4, 2, 1], [3, 2, 1]]), indent=3))
    args = ("run", "--takeover-stale") if stale else ("run",)
    one = box.start(*args, checkout=first, flags=("START=1", "HOLD=1"))
    two = box.start(*args, checkout=second, input_path=reordered, flags=("START=1", "HOLD=1"))
    _wait(lambda: len(list(box.control.glob("ready-*"))) == 2)
    (box.control / "start").touch()
    _wait(lambda: box.count() == 1 and (one.poll() is not None or two.poll() is not None))
    loser = one if one.poll() is not None else two
    winner = two if loser is one else one
    assert loser.wait(timeout=10) == 75
    out, _ = loser.communicate(timeout=10)
    assert json.loads(out)["status"] == "ACTIVE"
    assert winner.poll() is None and box.count() == 1
    (box.control / "finish").touch()
    assert winner.wait(timeout=10) == 0
    assert box.count() == 1 and len(box.receipts()) == 1


@pytest.mark.parametrize("expired", [False, True])
def test_a3_orphan_protected_and_publishes_complete_result(box: Sandbox, expired: bool) -> None:
    owner = box.start("run", flags=("ORPHAN=1", "HOLD=1"))
    _wait(lambda: box.count() == 1)
    assert owner.wait(timeout=10) == 0
    if expired:
        with box.store._transaction():
            record = box.store._read(box.snapshot.task_key)
            assert record is not None
            old = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
            box.store._write({**record, "started_at_utc": old, "heartbeat_at_utc": old})
    state = box.store.inspect(box.snapshot.task_key)
    assert state["status"] == "ACTIVE_ORPHAN_CHILD"
    child_pid = cast(int, state["child_pid"])
    before = box.store.location(box.snapshot.task_key).read_bytes()
    for options in (("run",), ("run", "--takeover-stale")):
        code, out, _ = box.run(*options)
        assert code == 75 and json.loads(out)["status"] == "ACTIVE_ORPHAN_CHILD"
    assert claims._alive(child_pid) is True
    assert box.store.location(box.snapshot.task_key).read_bytes() == before
    assert box.count() == 1 and not box.receipts()
    (box.control / "finish").touch()
    owner.communicate(timeout=10)  # EOF includes the voluntarily completed orphan.
    assert box.count() == 1 and len(box.receipts()) == 1
    receipt = json.loads(box.receipts()[0].read_text())
    assert receipt["successful_completion"] is True and receipt["child_pid"] == child_pid
    result = json.loads(box.receipts()[0].with_name("result.json").read_text())
    assert result == _expected_json(
        iterative_exact_1exchange_expected_max_ascent(10, 3, ((1, 2, 3), (1, 2, 4)))
    )


def test_a4_stale_requires_explicit_takeover_and_new_attempts(box: Sandbox) -> None:
    previous = _seed(box)
    old_attempt = box.attempts / previous["owner_id"]
    old_attempt.mkdir(parents=True)
    for name in ("input.json", "result.json", "receipt.json"):
        (old_attempt / name).write_text("old attempt preserved")
    before = box.store.location(box.snapshot.task_key).read_bytes()
    assert box.run("run")[0] == 76 and box.count() == 0
    assert box.store.location(box.snapshot.task_key).read_bytes() == before
    assert box.run("run", "--takeover-stale")[0] == 0
    assert box.run("run")[0] == 0
    assert box.count() == 2 and len(box.receipts()) == 3
    assert all(path.read_text() == "old attempt preserved" for path in old_attempt.iterdir())


@pytest.mark.parametrize("kind", ["malformed", "cross_host", "ambiguous"])
def test_a4_fail_closed_at_launcher(box: Sandbox, kind: str) -> None:
    if kind == "malformed":
        box.store.root.mkdir(parents=True)
        box.store.location(box.snapshot.task_key).write_text("{")
    elif kind == "cross_host":
        _seed(box, hostname="other-" + socket.gethostname())
    else:
        # Dead PID plus a fresh heartbeat is not proven stale.
        _seed(box, heartbeat_at_utc=datetime.now(UTC).isoformat())
    before = box.store.location(box.snapshot.task_key).read_bytes()
    for args in (("run",), ("run", "--takeover-stale")):
        assert box.run(*args)[0] == 74
    assert box.count() == 0 and not box.attempts.exists()
    assert box.store.location(box.snapshot.task_key).read_bytes() == before


def test_a4_direct_child_bypass_computes_nothing(box: Sandbox) -> None:
    process = box.start(
        "_child", box.snapshot.payload, str(uuid.uuid4()), str(os.getpid()), str(box.root)
    )
    _, err = process.communicate(timeout=10)
    assert process.returncode == 74 and b"matching active execution claim" in err
    assert box.count() == 0 and not box.store.root.exists() and not box.attempts.exists()


@pytest.mark.parametrize("field", ["owner_pid", "child_pid", "command", "cwd", "root", "key"])
def test_a4_child_rejects_mismatched_invocation(
    box: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    nonce, owner = str(uuid.uuid4()), os.getpid()
    command = launcher._command(box.snapshot, nonce, owner, str(box.root))
    _seed(box, owner_pid=owner, child_pid=owner, command=command)
    record = box.store._read(box.snapshot.task_key)
    assert record is not None
    changes: dict[str, object] = {
        "owner_pid": owner + 1,
        "child_pid": owner + 1,
        "command": ["wrong"],
        "cwd": str(box.repo),
        "root": str(box.root / "wrong"),
        "key": "wrong",
    }
    mapped = {"root": "claim_root", "key": "task_key"}.get(field, field)
    box.store.location(box.snapshot.task_key).write_text(
        json.dumps({**record, mapped: changes[field]})
    )

    def claim_root(cwd: Path) -> Path:
        return box.store.root

    monkeypatch.setattr(launcher, "resolve_claim_root", claim_root)
    monkeypatch.setattr(sys, "orig_argv", command)
    with pytest.raises(claims.ClaimError):
        launcher._child(box.snapshot, nonce, owner, str(box.root))
    assert box.count() == 0 and not box.attempts.exists()


def test_framework_python_argv0_preserves_guard_binding(
    box: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nonce, owner = str(uuid.uuid4()), os.getpid()
    command = launcher._command(box.snapshot, nonce, owner, str(box.root))
    _seed(box, owner_pid=owner, child_pid=owner, command=command)

    def claim_root(cwd: Path) -> Path:
        return box.store.root

    monkeypatch.setattr(launcher, "resolve_claim_root", claim_root)
    monkeypatch.setattr(sys, "orig_argv", ["framework-python", *command[1:]])
    assert launcher._verify_child(box.snapshot, nonce, owner, str(box.root))["child_pid"] == owner
    monkeypatch.setattr(sys, "orig_argv", ["framework-python", *command[1:], "unexpected"])
    with pytest.raises(claims.ClaimError):
        launcher._verify_child(box.snapshot, nonce, owner, str(box.root))
    assert box.count() == 0 and not box.attempts.exists()


def test_a5_actual_scientific_parity_snapshot_and_atomic_publication(box: Sandbox) -> None:
    child = box.start("run", flags=("HOLD=1", "PUBLISH_HOLD=1"))
    _wait(lambda: box.count() == 1)
    box.input.write_text("external input was replaced after validation")
    (box.control / "finish").touch()
    _wait(lambda: (box.control / "result_ready").exists())
    result_path = Path((box.control / "result_ready").read_text())
    assert not result_path.exists() and not box.receipts()
    pending = json.loads(next(result_path.parent.glob(".result.json.*.tmp")).read_text())
    pure = iterative_exact_1exchange_expected_max_ascent(10, 3, ((1, 2, 3), (1, 2, 4)))
    expected = _expected_json(pure)
    assert pending == expected
    (box.control / "publish").touch()
    assert child.wait(timeout=10) == 0
    assert json.loads(result_path.read_text()) == expected
    receipt = json.loads(result_path.with_name("receipt.json").read_text())
    saved = json.loads(result_path.with_name("input.json").read_text())
    assert saved["canonical_input"] == _input()
    assert saved["identity"] == box.snapshot.identity and saved["H"] == box.snapshot.h
    assert receipt["canonical_input"] == _input() == receipt["replay"]["input"]
    assert receipt["identity"] == box.snapshot.identity
    assert receipt["replay"]["rng"] == "NONE"
    assert receipt["replay"]["argv"][-2] == "--input"
    assert receipt["successful_completion"] is True and receipt["outcome"] == "COMPLETED"
    assert receipt["claim_owner_id"] == result_path.parent.name == receipt["attempt_id"]
    assert receipt["started_at_utc"] <= receipt["ended_at_utc"]
    argv = receipt["actual_executable_argv"]
    assert argv[0] and argv[1:4] == ["-I", "-B", str(box.repo / _ENTRY)]
    assert receipt["guarded_executable_argv"] == [sys.executable, *argv[1:]]
    assert json.loads(argv[5]) == _input()
    provenance = receipt["provenance"]
    assert provenance["source_commit"] == _git(box.repo, "rev-parse", "HEAD")
    assert provenance["source_tree"] == _git(box.repo, "rev-parse", "HEAD^{tree}")
    assert provenance["dirty"] is False
    for rel, digest in provenance["source_sha256"].items():
        assert digest == hashlib.sha256((box.repo / rel).read_bytes()).hexdigest()
    assert sorted(p.name for p in result_path.parent.iterdir()) == [
        "checkpoint.json",
        "input.json",
        "lineage.json",
        "receipt.json",
        "result.json",
    ]
    assert (box.control / "publications").read_text().splitlines() == [
        "input.json",
        "result.json",
        "receipt.json",
    ]


@pytest.mark.parametrize("failure", ["compute", "persistence"])
def test_a5_failure_never_claims_success(box: Sandbox, failure: str) -> None:
    process = box.start("run", flags=("FAIL=" + failure,))
    assert process.wait(timeout=10) == 1
    assert box.count() == 1 and len(box.receipts()) == 1
    receipt_path = box.receipts()[0]
    receipt = json.loads(receipt_path.read_text())
    assert receipt["successful_completion"] is False and receipt["outcome"] == "FAILED"
    assert "Injected" in receipt["error"]
    assert not receipt_path.with_name("result.json").exists()
    assert not list(receipt_path.parent.glob("*.tmp"))
    assert box.store.inspect(box.snapshot.task_key)["status"] == "ABSENT"


@pytest.mark.parametrize(
    "option", ["--task-key", "--claim-root", "--child-command", "--skip-guard", "--semantics-id"]
)
def test_a6_no_public_bypass_options(box: Sandbox, option: str) -> None:
    code, _, _ = box.run("run", option, "untrusted")
    assert code == 2 and box.count() == 0
    assert not box.store.root.exists() and not box.attempts.exists()


def _raw(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def _expire_dead_claim(box: Sandbox) -> claims.Metadata:
    record = box.store._read(box.snapshot.task_key)
    assert record is not None
    _wait(lambda: claims._alive(record["owner_pid"]) is False)
    if record["child_pid"] is not None:
        _wait(lambda: claims._alive(cast(int, record["child_pid"])) is False)
    old = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    with box.store._transaction():
        box.store._write({**record, "started_at_utc": old, "heartbeat_at_utc": old})
    assert box.store.inspect(box.snapshot.task_key)["status"] == "STALE_CONFIRMED"
    return record


def _selection(box: Sandbox) -> Path:
    record = box.store._read(box.snapshot.task_key)
    assert record is not None
    checkpoint = _raw(box.attempts / record["owner_id"] / "checkpoint.json")
    descriptor = box.root / ("resume-" + str(uuid.uuid4()) + ".json")
    descriptor.write_text(
        json.dumps(
            {
                "predecessor_attempt_id": record["owner_id"],
                "sequence": checkpoint["sequence"],
                "checkpoint_id": checkpoint["checkpoint_id"],
            }
        )
    )
    return descriptor


def _crash(box: Sandbox, sequence: int, descriptor: Path | None = None) -> Path:
    (box.control / "crashed").unlink(missing_ok=True)
    args = (
        ("run",)
        if descriptor is None
        else ("run", "--takeover-stale", "--resume-from", str(descriptor))
    )
    process = box.start(*args, flags=("ORPHAN=1", f"CRASH_SEQ={sequence}"))
    _, err = process.communicate(timeout=10)
    assert process.returncode == 0, err
    assert (box.control / "crashed").exists(), err.decode()
    record = _expire_dead_claim(box)
    attempt = box.attempts / record["owner_id"]
    assert _raw(attempt / "checkpoint.json")["sequence"] == sequence
    assert not (attempt / "result.json").exists()
    return attempt


def _scans(box: Sandbox, phase: str) -> int:
    path = box.control / "scans"
    return (
        sum(json.loads(line)["phase"] == phase for line in path.read_text().splitlines())
        if path.exists()
        else 0
    )


def _expected(box: Sandbox) -> object:
    return _expected_json(
        iterative_exact_1exchange_expected_max_ascent(
            box.snapshot.pool_size, box.snapshot.draw_size, box.snapshot.seed_portfolio
        )
    )


def _assert_result(box: Sandbox, expected: object) -> dict[str, Any]:
    successes = [path for path in box.receipts() if _raw(path)["successful_completion"]]
    assert len(successes) == 1
    receipt = _raw(successes[0])
    result = _raw(successes[0].with_name("result.json"))
    assert result == expected
    assert len(result["iterations"]) == result["move_count"] + 1
    assert result["total_neighbor_evaluations"] == sum(
        r["unique_legal_neighbor_count"] for r in result["iterations"]
    )
    # Independent hashes of every seed/input/selected/terminal portfolio.
    expected_result = cast(dict[str, Any], expected)
    for key in ("seed_portfolio", "terminal_portfolio"):
        assert (
            hashlib.sha256(json.dumps(result[key], separators=(",", ":")).encode()).hexdigest()
            == hashlib.sha256(
                json.dumps(expected_result[key], separators=(",", ":")).encode()
            ).hexdigest()
        )
    for row, other in zip(result["iterations"], expected_result["iterations"], strict=True):
        for key in ("input_portfolio", "best_neighbor_portfolio"):
            assert (
                hashlib.sha256(json.dumps(row[key], separators=(",", ":")).encode()).digest()
                == hashlib.sha256(json.dumps(other[key], separators=(",", ":")).encode()).digest()
            )
    assert not result["iterations"][-1]["accepted_move"]
    return receipt


def test_b_through_g_repeated_crash_resume_preserves_complete_science(box: Sandbox) -> None:
    expected = _expected(box)
    originals: dict[Path, bytes] = {}
    for sequence in (1, 2, 3):
        descriptor = None if sequence == 1 else _selection(box)
        attempt = _crash(box, sequence, descriptor)
        for name in ("input.json", "lineage.json", "checkpoint.json"):
            path = attempt / name
            originals[path] = path.read_bytes()
        checkpoint = _raw(attempt / "checkpoint.json")
        assert set(checkpoint) == launcher.CHECKPOINT_FIELDS
        assert checkpoint["iterations"] == cast(dict[str, Any], expected)["iterations"][:sequence]
        lineage = _raw(attempt / "lineage.json")
        assert lineage["resume_iteration"] == sequence - 1
        assert lineage["attempt_id"] == attempt.name
        if descriptor is not None:
            previous = _raw(descriptor)
            assert lineage["resumed_from_attempt_id"] == previous["predecessor_attempt_id"]
            assert lineage["resumed_from_checkpoint_id"] == previous["checkpoint_id"]
        before = box.store.location(box.snapshot.task_key).read_bytes()
        assert box.run("run", "--resume-from", str(_selection(box)))[0] == 76
        assert box.store.location(box.snapshot.task_key).read_bytes() == before
        assert box.count() == sequence
    terminal_descriptor = _selection(box)
    continuation_before = _scans(box, "CONTINUATION")
    validation_before = _scans(box, "VALIDATION_RESCAN")
    assert box.run("run", "--takeover-stale", "--resume-from", str(terminal_descriptor))[0] == 0
    assert _scans(box, "CONTINUATION") == continuation_before == 3
    assert _scans(box, "VALIDATION_RESCAN") - validation_before == 6
    receipt = _assert_result(box, expected)
    assert [v["completed_scan_count"] for v in receipt["validation"]] == [3, 3]
    assert all(v["physical_neighbor_evaluations"] == 124 for v in receipt["validation"])
    assert all(v["outcome"] == "PASSED" for v in receipt["validation"])
    assert all(path.read_bytes() == data for path, data in originals.items())
    assert box.store.inspect(box.snapshot.task_key)["status"] == "ABSENT"
    count = box.count()
    assert box.run("run", "--takeover-stale", "--resume-from", str(terminal_descriptor))[0] == 74
    assert box.count() == count


def test_revised_g_already_terminal_resume_has_no_continuation(box: Sandbox) -> None:
    box.input.write_text(json.dumps(_input(seed_portfolio=[[1, 2, 3], [4, 5, 6]])))
    box.snapshot = launcher.read_input(box.input)
    box.attempts = launcher._attempts_root(box.store.root, box.snapshot)
    expected = _expected(box)
    _crash(box, 1)
    assert box.run("run", "--takeover-stale", "--resume-from", str(_selection(box)))[0] == 0
    assert _scans(box, "CONTINUATION") == 1
    assert _scans(box, "VALIDATION_RESCAN") == 2
    receipt = _assert_result(box, expected)
    assert [v["iteration_indices"] for v in receipt["validation"]] == [[0], [0]]


@pytest.mark.parametrize("fault", ["temp_write", "file_fsync", "rename", "directory_fsync"])
def test_h_checkpoint_faults_recover_only_complete_old_or_new(box: Sandbox, fault: str) -> None:
    process = box.start("run", flags=("ORPHAN=1", "CHECKPOINT_FAULT=" + fault))
    _, err = process.communicate(timeout=10)
    assert process.returncode == 0, err
    record = _expire_dead_claim(box)
    attempt = box.attempts / record["owner_id"]
    checkpoint = _raw(attempt / "checkpoint.json")
    assert checkpoint["sequence"] == (2 if fault == "directory_fsync" else 1)
    assert _scans(box, "CONTINUATION") == 2  # Failure prevents the third scan.
    assert _raw(attempt / "receipt.json")["successful_completion"] is False
    assert not (attempt / "result.json").exists()
    # A complete-looking staging file cannot become resume authority.
    (attempt / ".checkpoint.json.abandoned.tmp").write_text('{"partial":')
    assert box.run("run", "--takeover-stale", "--resume-from", str(_selection(box)))[0] == 0
    _assert_result(box, _expected(box))


@pytest.mark.parametrize("side", ["before", "after"])
def test_h_crash_at_successor_claim_publication(box: Sandbox, side: str) -> None:
    old_attempt = _crash(box, 1)
    descriptor = _selection(box)
    old_claim = box.store.location(box.snapshot.task_key).read_bytes()
    process = box.start(
        "run",
        "--takeover-stale",
        "--resume-from",
        str(descriptor),
        flags=("TRANSFER_CRASH=" + side,),
    )
    _, err = process.communicate(timeout=10)
    assert process.returncode == (21 if side == "before" else 22), err
    successor_id = (box.control / "successor").read_text()
    successor = box.attempts / successor_id
    assert (
        _raw(successor / "checkpoint.json")["iterations"]
        == _raw(old_attempt / "checkpoint.json")["iterations"]
    )
    assert _raw(successor / "lineage.json")["resumed_from_attempt_id"] == old_attempt.name
    assert _raw(successor / "input.json")["canonical_input"] == _input()
    assert box.count() == 1
    if side == "before":
        assert box.store.location(box.snapshot.task_key).read_bytes() == old_claim
    else:
        record = _expire_dead_claim(box)
        assert record["owner_id"] == successor_id and record["child_pid"] is None
    assert box.run("run", "--takeover-stale", "--resume-from", str(_selection(box)))[0] == 0
    _assert_result(box, _expected(box))


def _rewrite_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    body = {k: v for k, v in checkpoint.items() if k != "checkpoint_id"}
    checkpoint["checkpoint_id"] = hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()
    path.write_text(json.dumps(checkpoint))


@pytest.mark.parametrize(
    "defect",
    [
        "checksum",
        "truncated",
        "duplicate",
        "extra",
        "schema",
        "identity",
        "seed",
        "fraction",
        "unreduced",
        "float",
        "gap",
        "sequence",
        "transition",
        "score",
        "count",
        "delta",
        "after_terminal",
        "lineage",
        "missing",
        "wrong_tie",
        "false_terminal",
    ],
)
def test_i_reject_corrupt_checkpoint_even_with_recomputed_digest(box: Sandbox, defect: str) -> None:
    attempt = _crash(box, 3)
    path = attempt / "checkpoint.json"
    checkpoint = _raw(path)
    rows = checkpoint["iterations"]
    if defect == "extra":
        checkpoint["extra"] = 0
    elif defect == "schema":
        checkpoint["schema_version"] = True
    elif defect == "identity":
        checkpoint["identity"]["semantics_id"] = "wrong"
    elif defect == "seed":
        checkpoint["seed_portfolio"] = [[1, 2, 3], [1, 2, 5]]
    elif defect == "fraction":
        rows[0]["input_expected_max"]["denominator"] = 0
    elif defect == "unreduced":
        rows[0]["input_expected_max"] = {"numerator": 34, "denominator": 30}
    elif defect == "float":
        rows[0]["input_expected_max"]["numerator"] = 17.0
    elif defect == "gap":
        rows[1]["iteration_index"] = 2
    elif defect == "sequence":
        checkpoint["sequence"] = 2
    elif defect == "transition":
        rows[0]["best_neighbor_portfolio"] = [[1, 2, 3], [7, 8, 9]]
    elif defect == "score":
        rows[0]["input_expected_max"] = {"numerator": 1, "denominator": 1}
    elif defect == "count":
        rows[0]["unique_legal_neighbor_count"] = 41
    elif defect == "delta":
        rows[0]["delta"] = {"numerator": 1, "denominator": 1}
    elif defect == "after_terminal":
        rows.append({**rows[-1], "iteration_index": 3})
        checkpoint["sequence"] = 4
    elif defect == "wrong_tie":
        rows[-1]["best_neighbor_portfolio"] = [[1, 2, 3], [4, 5, 8]]
    elif defect == "false_terminal":
        checkpoint["iterations"] = [
            {
                **rows[0],
                "best_neighbor_portfolio": [[1, 2, 3], [1, 2, 5]],
                "best_neighbor_expected_max": rows[0]["input_expected_max"],
                "delta": {"numerator": 0, "denominator": 1},
                "accepted_move": False,
            }
        ]
        checkpoint["sequence"] = 1
    _rewrite_checkpoint(path, checkpoint)
    descriptor = _selection(box)
    if defect == "checksum":
        checkpoint["created_at_utc"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(checkpoint))
    elif defect == "truncated":
        path.write_text("{")
    elif defect == "duplicate":
        path.write_text(path.read_text().replace("{", '{"schema_version":1,', 1))
    elif defect == "lineage":
        (attempt / "lineage.json").write_text("{}")
    elif defect == "missing":
        path.unlink()
    before = box.store.location(box.snapshot.task_key).read_bytes()
    scans = _scans(box, "CONTINUATION")
    code, _, err = box.run("run", "--takeover-stale", "--resume-from", str(descriptor))
    assert code == 74
    assert box.count() == 1 and _scans(box, "CONTINUATION") == scans
    assert box.store.location(box.snapshot.task_key).read_bytes() == before
    assert len(list(box.attempts.iterdir())) == 1 and not box.receipts()
    if defect in ("wrong_tie", "false_terminal"):
        assert "Scientific resume validation failed" in err
        assert "VALIDATION_RESCAN" in err and "FAILED" in err


def test_j_live_orphan_resume_blocked_even_with_expired_heartbeat(box: Sandbox) -> None:
    # Resume descriptor may be stale or forged: a live orphan blocks before parsing state.
    owner = box.start("run", flags=("ORPHAN=1", "HOLD=1"))
    _wait(lambda: box.count() == 1)
    assert owner.wait(timeout=10) == 0
    record = box.store._read(box.snapshot.task_key)
    assert record is not None and record["child_pid"] is not None
    old = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    with box.store._transaction():
        box.store._write({**record, "started_at_utc": old, "heartbeat_at_utc": old})
    descriptor = box.root / "live-resume.json"
    descriptor.write_text(
        json.dumps(
            {"predecessor_attempt_id": record["owner_id"], "sequence": 1, "checkpoint_id": "0" * 64}
        )
    )
    before = box.store.location(box.snapshot.task_key).read_bytes()
    code, out, _ = box.run("run", "--takeover-stale", "--resume-from", str(descriptor))
    assert code == 75 and json.loads(out)["status"] == "ACTIVE_ORPHAN_CHILD"
    assert box.store.location(box.snapshot.task_key).read_bytes() == before
    assert claims._alive(record["child_pid"]) is True and box.count() == 1
    (box.control / "finish").touch()
    owner.communicate(timeout=10)


@pytest.mark.parametrize("rel", launcher.COMPATIBILITY_PATHS)
def test_k_each_compatibility_source_independently_blocks_resume(box: Sandbox, rel: str) -> None:
    _crash(box, 1)
    descriptor = _selection(box)
    path = box.repo / rel
    path.write_text((path.read_text() if path.exists() else "") + "\n# source drift\n")
    before = box.store.location(box.snapshot.task_key).read_bytes()
    assert box.run("run", "--takeover-stale", "--resume-from", str(descriptor))[0] == 74
    assert box.count() == 1
    assert box.store.location(box.snapshot.task_key).read_bytes() == before


def test_k_unrelated_commit_and_dirty_file_remain_compatible(box: Sandbox) -> None:
    _crash(box, 1)
    (box.repo / "unrelated.txt").write_text("unrelated commit")
    _git(box.repo, "add", "unrelated.txt")
    _git(
        box.repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "unrelated",
    )
    (box.repo / "another.txt").write_text("unrelated dirty state")
    assert box.run("run", "--takeover-stale", "--resume-from", str(_selection(box)))[0] == 0
    _assert_result(box, _expected(box))


def test_l_linked_worktree_resume_contenders_start_one_successor(box: Sandbox) -> None:
    _crash(box, 1)
    first, second = box.linked("first"), box.linked("second")
    descriptor = _selection(box)
    args = ("run", "--takeover-stale", "--resume-from", str(descriptor))
    one = box.start(*args, checkout=first, flags=("START=1", "HOLD=1"))
    two = box.start(*args, checkout=second, flags=("START=1", "HOLD=1"))
    _wait(lambda: len(list(box.control.glob("ready-*"))) == 2)
    (box.control / "start").touch()
    _wait(lambda: box.count() == 2 and (one.poll() is not None or two.poll() is not None))
    loser = one if one.poll() is not None else two
    winner = two if loser is one else one
    assert loser.wait(timeout=10) == 75
    assert winner.poll() is None
    (box.control / "finish").touch()
    _, err = winner.communicate(timeout=10)
    assert winner.returncode == 0, err
    assert box.count() == 2
    _assert_result(box, _expected(box))


@pytest.mark.parametrize("outcome", ["active", "new_stale", "completed", "changed_checkpoint"])
def test_m_frozen_selection_never_follows_newer_ownership_or_checkpoint(
    box: Sandbox,
    outcome: str,
) -> None:
    original = _crash(box, 1)
    descriptor = _selection(box)
    args = ("run", "--takeover-stale", "--resume-from", str(descriptor))
    contender = box.start(*args, flags=("SELECT=1",))
    _wait(lambda: (box.control / "selected").exists())
    winner: subprocess.Popen[bytes] | None = None
    if outcome == "active":
        winner = box.start(*args, flags=("HOLD=1",))
        _wait(lambda: box.count() == 2)
        assert winner.poll() is None
    elif outcome == "new_stale":
        _crash(box, 2, descriptor)
    elif outcome == "completed":
        assert box.run(*args)[0] == 0
        assert box.store.inspect(box.snapshot.task_key)["status"] == "ABSENT"
    else:
        checkpoint = _raw(original / "checkpoint.json")
        checkpoint["iterations"] = cast(dict[str, Any], _expected(box))["iterations"][:2]
        checkpoint["sequence"] = 2
        _rewrite_checkpoint(original / "checkpoint.json", checkpoint)
    location = box.store.location(box.snapshot.task_key)
    before = location.read_bytes() if location.exists() else None
    entries = box.count()
    (box.control / "admit").touch()
    contender.communicate(timeout=10)
    assert contender.returncode == (75 if outcome == "active" else 74)
    assert box.count() == entries
    after = location.read_bytes() if location.exists() else None
    if outcome != "active":  # A live winner may legitimately update its heartbeat.
        assert after == before
    if outcome == "active":
        assert winner is not None
        (box.control / "finish").touch()
        winner.communicate(timeout=10)
        assert winner.returncode == 0


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "only_temp"])
def test_unsafe_checkpoint_never_becomes_authority(box: Sandbox, kind: str) -> None:
    attempt = _crash(box, 1)
    descriptor = _selection(box)
    checkpoint = attempt / "checkpoint.json"
    saved = box.root / "preserved-checkpoint.json"
    checkpoint.rename(saved)
    if kind == "symlink":
        checkpoint.symlink_to(saved)
    elif kind == "hardlink":
        os.link(saved, checkpoint)
    elif kind == "fifo":
        os.mkfifo(checkpoint)
    else:
        (attempt / ".checkpoint.json.temp").write_bytes(saved.read_bytes())
    before = box.store.location(box.snapshot.task_key).read_bytes()
    assert box.run("run", "--takeover-stale", "--resume-from", str(descriptor))[0] == 74
    assert box.count() == 1 and box.store.location(box.snapshot.task_key).read_bytes() == before


@pytest.mark.parametrize("contradictory", [False, True])
def test_success_receipt_blocks_resume(box: Sandbox, contradictory: bool) -> None:
    attempt = _crash(box, 3)
    (attempt / "result.json").write_text(json.dumps(_expected(box)))
    receipt = {
        "task_key": box.snapshot.task_key,
        "attempt_id": attempt.name,
        "claim_owner_id": attempt.name,
        "successful_completion": True,
        "outcome": "COMPLETED",
    }
    (attempt / "receipt.json").write_text(json.dumps(receipt))
    if contradictory:
        (attempt / "result.json").write_text("{}")
    code, _, err = box.run("run", "--takeover-stale", "--resume-from", str(_selection(box)))
    assert code == 74 and box.count() == 1
    assert ("Contradictory" if contradictory else "ALREADY_COMPLETE") in err
