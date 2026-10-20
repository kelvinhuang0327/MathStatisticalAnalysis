"""Fail-closed local execution claims shared by a repository's linked worktrees.

SESSION_TERMINATED != EXECUTION_TERMINATED. A live child keeps its claim active
even without its owner or a recent heartbeat. PID probes use only signal 0;
permission errors, PID reuse and other uncertainty conservatively block reuse.

The permanent .coordination.lock serializes short metadata transactions, never
the computation. Do not unlink that lock: replacing its inode defeats flock.
A gated exec child cannot start the requested command before its PID is durable.
This protects the launch window as well as an already-running orphan child.
Requires a local POSIX filesystem with flock and atomic rename support. Commands
must remain in the foreground; detached descendants are outside this guard.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast

HEARTBEAT_SECONDS = 5.0
STALE_SECONDS = 30.0
REFUSED = 75
TAKEOVER_REQUIRED = 76
UNVERIFIABLE = 74
MAX_METADATA_BYTES = 1024 * 1024

# exec preserves the recorded PID. EOF means the owner died before authorizing
# launch. No shell, new daemon, signal forwarding, or process termination.
_GATED_EXEC = """
import os, sys
fd = int(sys.argv[1])
go = os.read(fd, 1)
os.close(fd)
if go != b'G':
    sys.exit(125)
try:
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
except OSError as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(127 if isinstance(exc, FileNotFoundError) else 126)
"""


class ClaimError(RuntimeError):
    """Ownership or repository authority could not be proven safe."""


class Metadata(TypedDict):
    schema_version: int
    task_key: str
    owner_id: str
    owner_pid: int
    child_pid: int | None
    hostname: str
    started_at_utc: str
    heartbeat_at_utc: str
    cwd: str
    command: list[str]
    claim_root: str


def _git(cwd: Path, *args: str) -> str:
    # Ambient Git overrides must not redirect authority to a different repo.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClaimError("Cannot establish Git common repository authority") from exc
    return result.stdout.strip()


def _check_path(path: Path) -> None:
    if not path.is_absolute() or path != path.resolve():
        raise ClaimError("Claim authority must be absolute and must not traverse symlinks")


def resolve_claim_root(cwd: Path | None = None) -> Path:
    """Resolve the canonical non-bare checkout; never use a cwd/home/tmp fallback."""
    context = (cwd if cwd is not None else Path.cwd()).resolve()
    if _git(context, "--is-bare-repository") != "false":
        raise ClaimError("A canonical non-bare repository is required")
    common = Path(_git(context, "--path-format=absolute", "--git-common-dir"))
    _check_path(common)
    if common.name != ".git" or not common.is_dir():
        raise ClaimError("Cannot prove a canonical checkout for this Git common directory")
    canonical = common.parent
    if Path(_git(canonical, "--show-toplevel")) != canonical:
        raise ClaimError("Canonical checkout identity mismatch")
    if Path(_git(canonical, "--path-format=absolute", "--git-common-dir")) != common:
        raise ClaimError("Canonical Git common directory mismatch")
    root = canonical / ".task-data" / "execution-claims"
    _check_path(root)
    return root


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("Timestamp must include UTC timezone")
    return parsed


def _alive(pid: int) -> bool | None:
    """Non-destructive existence probe; only ESRCH proves death."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return None
    return True


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata key")
        result[key] = value
    return result


class ClaimStore:
    """Explicit root injection is for callers/tests; the CLI always resolves Git."""

    def __init__(self, root: Path):
        _check_path(root)
        self.root = root

    def location(self, task_key: str) -> Path:
        # Hash exact UTF-8 bytes: no normalization or key-dependent path segments.
        identity = hashlib.sha256(task_key.encode("utf-8")).hexdigest()
        return self.root / f"{identity}.json"

    @contextmanager
    def _transaction(self) -> Generator[None]:
        _check_path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            self.root / ".coordination.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ClaimError("Unsafe coordination lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _read(self, task_key: str) -> Metadata | None:
        _check_path(self.root)
        try:
            fd = os.open(self.location(task_key), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            # A reader can hold the complete previous inode after atomic rename
            # unlinks it. Zero links is safe for this already-open snapshot.
            if not stat.S_ISREG(info.st_mode) or info.st_nlink not in (0, 1):
                raise ClaimError("Unsafe claim metadata file")
            payload = source.read(MAX_METADATA_BYTES + 1)
        if len(payload) > MAX_METADATA_BYTES:
            raise ClaimError("Oversized claim metadata")
        raw: object = json.loads(payload, object_pairs_hook=_unique_object)
        if not isinstance(raw, dict):
            raise ClaimError("Claim metadata must be an object")
        data = cast(dict[str, object], raw)
        required = set(Metadata.__required_keys__)
        if set(data) != required:
            raise ClaimError("Incomplete or unsupported claim metadata")
        string_keys = (
            "task_key",
            "owner_id",
            "hostname",
            "started_at_utc",
            "heartbeat_at_utc",
            "cwd",
            "claim_root",
        )
        if any(not isinstance(data[key], str) for key in string_keys):
            raise ClaimError("Invalid metadata string field")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ClaimError("Unsupported schema version")
        for key in ("owner_pid", "child_pid"):
            value = data[key]
            if key == "child_pid" and value is None:
                continue
            if type(value) is not int or not 0 < value <= 2**31 - 1:
                raise ClaimError("Invalid PID")
        command = data["command"]
        if not isinstance(command, list) or not command:
            raise ClaimError("Invalid command")
        if any(not isinstance(arg, str) or "\0" in arg for arg in cast(list[object], command)):
            raise ClaimError("Invalid command argument")
        record = cast(Metadata, data)
        if record["task_key"] != task_key or record["claim_root"] != str(self.root):
            raise ClaimError("Claim identity mismatch")
        if (
            not record["hostname"]
            or not record["command"][0]
            or not Path(record["cwd"]).is_absolute()
        ):
            raise ClaimError("Incomplete execution identity")
        if str(uuid.UUID(record["owner_id"])) != record["owner_id"]:
            raise ClaimError("Invalid owner identity")
        if _timestamp(record["heartbeat_at_utc"]) < _timestamp(record["started_at_utc"]):
            raise ClaimError("Heartbeat precedes start")
        return record

    def inspect(self, task_key: str) -> dict[str, object]:
        """Read-only snapshot; timestamps alone never establish safe takeover."""
        result: dict[str, object] = {
            "task_key": task_key,
            "claim_location": str(self.location(task_key)),
            "claim_root": str(self.root),
            "status": "UNVERIFIABLE",
            "takeover_allowed": False,
        }
        try:
            record = self._read(task_key)
            if record is None:
                return {**result, "status": "ABSENT"}
            result.update(record)
            if record["hostname"] != socket.gethostname():
                return {**result, "status": "STALE_UNPROVEN", "reason": "Different host"}
            owner_alive = _alive(record["owner_pid"])
            child_pid = record["child_pid"]
            child_alive = False if child_pid is None else _alive(child_pid)
            result.update(owner_alive=owner_alive, child_alive=child_alive)
            if owner_alive is True or child_alive is True:
                status = "ACTIVE_ORPHAN_CHILD" if owner_alive is False and child_alive else "ACTIVE"
                return {**result, "status": status}
            age = (datetime.now(UTC) - _timestamp(record["heartbeat_at_utc"])).total_seconds()
            result["heartbeat_age_seconds"] = age
            if owner_alive is None or child_alive is None or age <= STALE_SECONDS:
                return {**result, "status": "STALE_UNPROVEN"}
            return {**result, "status": "STALE_CONFIRMED", "takeover_allowed": True}
        except (ClaimError, OSError, ValueError, OverflowError) as exc:
            return {**result, "status": "UNVERIFIABLE", "reason": str(exc)}

    def _sync_root(self) -> None:
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write(self, record: Metadata) -> None:
        temporary = self.root / f".{record['owner_id']}.{uuid.uuid4().hex}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                json.dump(record, target, ensure_ascii=True)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.location(record["task_key"]))
            self._sync_root()
        finally:
            temporary.unlink(missing_ok=True)

    def _assert_owner(self, record: Metadata) -> None:
        current = self._read(record["task_key"])
        if current is None or current["owner_id"] != record["owner_id"]:
            raise ClaimError("Ownership changed; preserving claim")

    def _release(self, record: Metadata) -> None:
        self._assert_owner(record)
        self.location(record["task_key"]).unlink()
        self._sync_root()

    def _monitor(self, child: subprocess.Popen[bytes], record: Metadata) -> int:
        while True:
            try:
                code = child.wait(timeout=HEARTBEAT_SECONDS)
                break
            except subprocess.TimeoutExpired:
                with self._transaction():
                    self._assert_owner(record)
                    record["heartbeat_at_utc"] = _now()
                    self._write(record)
        with self._transaction():
            self._release(record)
        return code if code >= 0 else 128 - code

    def run(
        self,
        task_key: str,
        command: Sequence[str],
        *,
        takeover_stale: bool = False,
        expected_predecessor_owner_id: str | None = None,
        prepare_takeover: Callable[[Metadata, Metadata], None] | None = None,
    ) -> int:
        """Optionally admit an exact predecessor transfer inside the transaction.

        The trusted preparation hook must durably prepare successor state before
        returning. Failure leaves predecessor ownership unchanged. Copies keep a
        callback from accidentally changing the gate's ownership/command metadata.
        """
        if not command or not command[0] or any("\0" in arg for arg in command):
            raise ClaimError("A valid foreground command is required")
        if (expected_predecessor_owner_id is None) != (prepare_takeover is None):
            raise ClaimError("Expected predecessor and preparation must be supplied together")
        if expected_predecessor_owner_id is not None:
            if str(uuid.UUID(expected_predecessor_owner_id)) != expected_predecessor_owner_id:
                raise ClaimError("Invalid expected predecessor owner")
            if not takeover_stale:
                print(json.dumps({"reason": "Explicit --takeover-stale required"}))
                return TAKEOVER_REQUIRED
        record: Metadata
        child: subprocess.Popen[bytes]
        with self._transaction():
            state = self.inspect(task_key)
            status = state["status"]
            if status == "STALE_CONFIRMED" and not takeover_stale:
                print(json.dumps({**state, "reason": "Explicit --takeover-stale required"}))
                return TAKEOVER_REQUIRED
            if status == "STALE_CONFIRMED" and takeover_stale:
                # Fresh PID and timestamp checks while holding the same lock that
                # guards replacement; competing takers cannot use stale evidence.
                state = self.inspect(task_key)
                status = state["status"]
            if status != "ABSENT" and not (status == "STALE_CONFIRMED" and takeover_stale):
                print(json.dumps(state))
                return REFUSED if str(status).startswith("ACTIVE") else UNVERIFIABLE
            if expected_predecessor_owner_id is not None and (
                status != "STALE_CONFIRMED"
                or state.get("owner_id") != expected_predecessor_owner_id
            ):
                print(json.dumps({**state, "reason": "Expected predecessor no longer owns claim"}))
                return UNVERIFIABLE
            stamp = _now()
            record = Metadata(
                schema_version=1,
                task_key=task_key,
                owner_id=str(uuid.uuid4()),
                owner_pid=os.getpid(),
                child_pid=None,
                hostname=socket.gethostname(),
                started_at_utc=stamp,
                heartbeat_at_utc=stamp,
                cwd=str(Path.cwd()),
                command=list(command),
                claim_root=str(self.root),
            )
            if prepare_takeover is not None:
                predecessor = self._read(task_key)
                if predecessor is None or predecessor["owner_id"] != expected_predecessor_owner_id:
                    raise ClaimError("Expected predecessor changed before preparation")
                prepare_takeover(deepcopy(predecessor), deepcopy(record))
            self._write(record)
            read_fd, write_fd = os.pipe()
            try:
                child = subprocess.Popen(
                    [sys.executable, "-c", _GATED_EXEC, str(read_fd), *command],
                    pass_fds=(read_fd,),
                    start_new_session=True,
                )
                record["child_pid"] = child.pid
                self._write(record)
                os.write(write_fd, b"G")
            finally:
                os.close(read_fd)
                os.close(write_fd)
            # On unexpected failure retain metadata; pipe EOF prevents an
            # unrecorded child from running. Never clean up an ambiguous owner.
        return self._monitor(child, record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)
    inspect_parser = operations.add_parser("inspect", help="Read ownership without creating files")
    inspect_parser.add_argument("--task-key", required=True)
    inspect_parser.add_argument("--format", choices=("text", "json"), default="text")
    run_parser = operations.add_parser(
        "run", help="Run one foreground command under a shared claim"
    )
    run_parser.add_argument("--task-key", required=True)
    run_parser.add_argument("--takeover-stale", action="store_true")
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        store = ClaimStore(resolve_claim_root())
        if args.operation == "inspect":
            state = store.inspect(args.task_key)
            if args.format == "json":
                print(json.dumps(state, indent=2))
            else:
                print("\n".join(f"{key}: {value}" for key, value in state.items()))
            return UNVERIFIABLE if state["status"] == "UNVERIFIABLE" else 0
        command: list[str] = args.command
        if not command or command[0] != "--" or len(command) == 1:
            parser.error("run requires -- COMMAND [ARGS...]")
        return store.run(args.task_key, command[1:], takeover_stale=args.takeover_stale)
    except (ClaimError, OSError, ValueError, OverflowError) as exc:
        print(json.dumps({"status": "UNVERIFIABLE", "reason": str(exc)}), file=sys.stderr)
        return UNVERIFIABLE


if __name__ == "__main__":
    sys.exit(main())
