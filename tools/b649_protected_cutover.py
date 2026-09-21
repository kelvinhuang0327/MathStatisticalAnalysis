"""One foreground, claim-owned B649 apply; production execution needs Owner authority.

Future command contract (run from this control-plane checkout, using absolute paths)::

    <python> <checkout>/tools/b649_protected_cutover.py apply \
        --source-worktree <successor> --expected-head <HEAD> --expected-tree <TREE> \
        --legacy-worktree <legacy> --legacy-head <HEAD> --legacy-tree <TREE> \
        --plan-file <owner-only-plan.json> [--takeover-stale]

The argument order above is canonical. No PID exemptions, arbitrary commands,
receipt-root overrides, or automatic retries are accepted by the CLI. The fixed
task key serializes every plan for this LaunchAgent in the repository ClaimStore.
The execution digest binds the exact plan and source/target identities. A stale
claim can be taken only by ClaimStore's explicit positive-death protocol; any
existing non-success execution receipt still blocks. Reconciliation is separate.

ClaimStore gates the actual b649_production_cutover.py process. That child records
STARTED before quiescence or apply, and stages bounded output before returning.
Only the foreground claim owner seals a terminal result after wait/exit. Owner or
child loss, missing terminal capture, or receipt I/O failure stays incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout, suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import b649_cutover_checkpoint as checkpoint
from tools import b649_production_cutover as cutover
from tools import task_execution_claim as claims

SCHEMA = "b649-protected-cutover-execution-receipt-v1"
TASK_KEY = checkpoint.PROTECTED_TASK_KEY
RECEIPT_NAME = "b649-protected-cutover-execution-receipt.json"
CONTROL_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = CONTROL_ROOT / "tools/b649_protected_cutover.py"
MANAGED = CONTROL_ROOT / "tools/b649_production_cutover.py"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_STREAM_BYTES = 32 * 1024
QUIESCENCE_SECONDS = 5.0
type Record = dict[str, object]


class ProtectedError(RuntimeError):
    """An execution must not start or be automatically retried."""


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


def unique_object(pairs: list[tuple[str, object]]) -> Record:
    result: Record = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedError("duplicate JSON key")
        result[key] = value
    return result


def record(value: object) -> Record:
    return checkpoint.object_record(value)


def text(value: object) -> str:
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ProtectedError("invalid identity string")
    return value


def repository_claim_root() -> Path:
    """Use the existing repository ClaimStore authority with fsmonitor disabled."""
    canonical_repo = cutover.CANONICAL_REPOSITORY
    for worktree in (CONTROL_ROOT, canonical_repo):
        common = checkpoint.checked(
            cutover.run_command,
            [
                "git",
                "-C",
                str(worktree),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
        ).strip()
        if common != str(canonical_repo / ".git"):
            raise ProtectedError("control-plane checkout has different repository authority")
    root = canonical_repo / ".task-data/execution-claims"
    claims.ClaimStore(root)  # Reuse ClaimStore's canonical-path guard, without creating state.
    return root


@dataclass(frozen=True)
class Request:
    config: cutover.CutoverConfig
    legacy_worktree: Path
    legacy_head: str
    legacy_tree: str
    plan_file: Path
    plan_digest: str
    plan_sha256: str
    claim_root: Path
    takeover_stale: bool = False

    @property
    def receipt_path(self) -> Path:
        return self.config.scheduler_root / RECEIPT_NAME

    @property
    def sources(self) -> tuple[tuple[str, str, str], ...]:
        return (
            (str(self.legacy_worktree), self.legacy_head, self.legacy_tree),
            (
                str(self.config.source_worktree),
                text(self.config.expected_head),
                text(self.config.expected_tree),
            ),
        )

    @property
    def identity(self) -> Record:
        return {
            "task_key": TASK_KEY,
            "action": "apply",
            "source_worktree": str(self.config.source_worktree),
            "source_head": self.config.expected_head,
            "source_tree": self.config.expected_tree,
            "legacy_worktree": str(self.legacy_worktree),
            "legacy_head": self.legacy_head,
            "legacy_tree": self.legacy_tree,
            "plan_digest": self.plan_digest,
            "plan_file": str(self.plan_file),
            "plan_sha256": self.plan_sha256,
            "label": self.config.label,
            "launch_domain": self.config.launch_domain,
            "plist_path": str(self.config.plist_path),
            "managed_receipt_path": str(self.config.receipt_path),
            "execution_receipt_path": str(self.receipt_path),
            "claim_root": str(self.claim_root),
            "control_worktree": str(CONTROL_ROOT),
            "interpreter": sys.executable,
        }

    @property
    def execution_id(self) -> str:
        return digest(self.identity)

    def owner_argv(self) -> list[str]:
        return [
            sys.executable,
            str(LAUNCHER),
            "apply",
            "--source-worktree",
            str(self.config.source_worktree),
            "--expected-head",
            text(self.config.expected_head),
            "--expected-tree",
            text(self.config.expected_tree),
            "--legacy-worktree",
            str(self.legacy_worktree),
            "--legacy-head",
            self.legacy_head,
            "--legacy-tree",
            self.legacy_tree,
            "--plan-file",
            str(self.plan_file),
            *(["--takeover-stale"] if self.takeover_stale else []),
        ]

    def managed_argv(self) -> list[str]:
        wire = {"identity": self.identity, "takeover_stale": self.takeover_stale}
        return [
            sys.executable,
            str(MANAGED),
            "apply",
            "--source-worktree",
            str(self.config.source_worktree),
            "--expected-head",
            text(self.config.expected_head),
            "--expected-tree",
            text(self.config.expected_tree),
            "--durable-ref",
            text(self.config.durable_ref),
            "--launch-domain",
            self.config.launch_domain,
            "--plist-path",
            str(self.config.plist_path),
            "--receipt-path",
            str(self.config.receipt_path),
            "--cutover-lock-path",
            str(self.config.cutover_lock_path),
            "--primary-lock-path",
            str(self.config.primary_lock_path),
            "--shadow-lock-path",
            str(self.config.shadow_lock_path),
            "--plan-file",
            str(self.plan_file),
            "--protected-request",
            canonical(wire),
            "--protected-execution",
            self.execution_id,
        ]

    def load_plan(self) -> Record:
        plan, identity, _ = cutover.read_control_json(self.plan_file)
        cutover.validate_protected_plan(self.config, plan)
        old = record(record(plan["source"])["old"])
        if (
            identity.sha256 != self.plan_sha256
            or plan.get("plan_digest") != self.plan_digest
            or (old.get("source_worktree"), old.get("head"), old.get("tree")) != self.sources[0]
            or record(plan["prestate"]).get("old_source") != old
        ):
            raise ProtectedError("plan/legacy identity changed")
        return plan


def make_request(
    config: cutover.CutoverConfig,
    legacy_worktree: Path,
    legacy_head: str,
    legacy_tree: str,
    plan_file: Path,
    claim_root: Path,
    *,
    takeover_stale: bool = False,
) -> Request:
    for path in (
        config.source_worktree,
        legacy_worktree,
        plan_file,
        claim_root,
        config.scheduler_root,
        config.receipt_path,
        config.plist_path,
    ):
        if not path.is_absolute() or path != path.resolve() or ".." in path.parts:
            raise ProtectedError("execution paths must be canonical and must not traverse symlinks")
    for value in (legacy_head, legacy_tree, config.expected_head, config.expected_tree):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ProtectedError("full exact HEAD/tree required")
    if legacy_worktree == config.source_worktree:
        raise ProtectedError("legacy and successor worktrees must differ")
    plan, identity, _ = cutover.read_control_json(plan_file)
    request = Request(
        config,
        legacy_worktree,
        legacy_head,
        legacy_tree,
        plan_file,
        text(plan.get("plan_digest")),
        identity.sha256,
        claim_root,
        takeover_stale,
    )
    if request.receipt_path in {config.receipt_path, config.plist_path, plan_file}:
        raise ProtectedError("execution receipt must have its own canonical path")
    request.load_plan()
    return request


class ReceiptFile:
    """One existing scheduler directory, pinned by fd; no hierarchy or claim of its own."""

    def __init__(self, path: Path):
        self.path = path

    def _directory(self) -> int:
        if not self.path.is_absolute() or self.path.parent != self.path.parent.resolve():
            raise ProtectedError("receipt parent must not traverse symlinks")
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in self.path.parent.parts[1:]:
                next_descriptor = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
                os.close(descriptor)
                descriptor = next_descriptor
        except BaseException:
            os.close(descriptor)
            raise
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
            os.close(descriptor)
            raise ProtectedError("receipt directory must be existing owner-only mode 0700")
        return descriptor

    def _read(self, directory: int) -> Record | None:
        try:
            descriptor = os.open(
                self.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size > MAX_RECEIPT_BYTES
            ):
                raise ProtectedError("receipt must be bounded, owner-only, regular and single-link")
            raw = stream.read(MAX_RECEIPT_BYTES + 1)
            after = os.fstat(stream.fileno())
        current = os.stat(self.path.name, dir_fd=directory, follow_symlinks=False)

        def file_key(value: os.stat_result) -> tuple[int, ...]:
            return (*checkpoint.file_identity(value), value.st_mode, value.st_uid, value.st_nlink)

        if (
            len(raw) > MAX_RECEIPT_BYTES
            or file_key(before) != file_key(after)
            or file_key(after) != file_key(current)
        ):
            raise ProtectedError("receipt changed during read")
        value = record(json.loads(raw, object_pairs_hook=unique_object))
        required = {
            "schema_version",
            "identity",
            "execution_id",
            "task_key",
            "claim_owner",
            "supervisor_pid",
            "gated_child_pid",
            "direct_argv",
            "phase",
            "status",
            "started_at",
            "completed_at",
            "exit_code",
            "child_exit_code",
            "stdout",
            "stderr",
            "managed_receipt",
            "result_status",
            "receipt_sha256",
        }
        if not required.issubset(value):
            raise ProtectedError("execution receipt provenance is incomplete")
        unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if (
            value.get("schema_version") != SCHEMA
            or value.get("receipt_sha256") != digest(unsigned)
            or value.get("execution_id") != digest(value.get("identity"))
            or value.get("status") not in ("SUCCESS", "FAILED", "INCOMPLETE_OR_AMBIGUOUS")
        ):
            raise ProtectedError("receipt schema/integrity is invalid")
        identity, owner = record(value["identity"]), record(value["claim_owner"])
        if (
            value["task_key"] != TASK_KEY
            or identity.get("task_key") != TASK_KEY
            or identity.get("execution_receipt_path") != str(self.path)
            or owner.get("task_key") != TASK_KEY
            or owner.get("claim_root") != identity.get("claim_root")
            or owner.get("command") != value["direct_argv"]
            or owner.get("owner_pid") != value["supervisor_pid"]
            or owner.get("child_pid") != value["gated_child_pid"]
            or str(UUID(text(owner.get("owner_id")))) != owner.get("owner_id")
            or value["phase"] not in ("CLAIMED", "GATED", "STARTED", "CHILD_COMPLETED", "COMPLETED")
        ):
            raise ProtectedError("execution receipt owner/phase identity differs")
        for field in ("supervisor_pid", "gated_child_pid"):
            pid = value[field]
            if field == "gated_child_pid" and pid is None and value["phase"] == "CLAIMED":
                continue
            if type(pid) is not int or pid <= 0:
                raise ProtectedError("execution receipt PID is invalid")
        started = datetime.fromisoformat(text(value["started_at"]))
        if started.utcoffset() != datetime.now(UTC).utcoffset():
            raise ProtectedError("execution start must be UTC")
        if value["completed_at"] is not None:
            completed = datetime.fromisoformat(text(value["completed_at"]))
            if completed.utcoffset() != started.utcoffset() or completed < started:
                raise ProtectedError("execution completion timestamp differs")
        if value["status"] in {"SUCCESS", "FAILED"} and (
            value.get("phase") != "COMPLETED"
            or not value.get("completed_at")
            or type(value.get("exit_code")) is not int
        ):
            raise ProtectedError("terminal receipt is incomplete")
        if value["status"] == "SUCCESS" and (
            value.get("exit_code") != 0
            or value.get("child_exit_code") != 0
            or value.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
            or not isinstance(value.get("managed_receipt"), dict)
        ):
            raise ProtectedError("success receipt lacks terminal evidence")
        return value

    def read(self) -> Record | None:
        directory = self._directory()
        try:
            return self._read(directory)
        finally:
            os.close(directory)

    def write(self, value: Record, *, expected: Record | None) -> Record:
        unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
        saved = {**unsigned, "receipt_sha256": digest(unsigned)}
        data = (canonical(saved) + "\n").encode()
        if len(data) > MAX_RECEIPT_BYTES:
            raise ProtectedError("execution receipt exceeds bound")
        directory = self._directory()
        temporary = f".{self.path.name}.{uuid4().hex}.tmp"
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self._read(directory) != expected:
                raise ProtectedError("execution receipt changed before write")
            if expected is None:
                os.link(
                    temporary,
                    self.path.name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
                os.unlink(temporary, dir_fd=directory)
            else:
                os.replace(temporary, self.path.name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
            if self._read(directory) != saved:
                raise ProtectedError("execution receipt readback differs")
            return saved
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory)
            os.close(directory)


class BoundedStream(io.TextIOBase):
    def __init__(self) -> None:
        self.prefix = bytearray()
        self.sha = hashlib.sha256()
        self.size = 0

    def write(self, s: str) -> int:
        raw = s.encode("utf-8", errors="replace")
        self.sha.update(raw)
        self.size += len(raw)
        self.prefix.extend(raw[: max(0, MAX_STREAM_BYTES - len(self.prefix))])
        return len(s)

    def evidence(self) -> Record:
        return {
            "text": self.prefix.decode("utf-8", errors="replace"),
            "sha256": self.sha.hexdigest(),
            "bytes": self.size,
            "truncated": self.size > len(self.prefix),
        }


class ReceiptClaimStore(claims.ClaimStore):
    """Mirror claim writes before its existing gate; acquire/run/wait/release are inherited.

    A child that cannot import or exec must still leave a durable ambiguous
    result. Mirroring at this seam also binds completion to this exact owner
    UUID, including competing callers within one supervisor process.
    """

    def __init__(self, request: Request):
        super().__init__(request.claim_root)
        self.request = request
        self.owner_record: claims.Metadata | None = None
        self.gated = False

    def _write(self, record: claims.Metadata) -> None:
        value = record
        receipt_file = ReceiptFile(self.request.receipt_path)
        initial = self.owner_record is None
        if initial and receipt_file.read() is not None:
            raise ProtectedError("execution receipt appeared before claim acquisition")
        super()._write(value)
        self.owner_record = value.copy()
        if not initial and (self.gated or value["child_pid"] is None):
            return  # Ordinary ClaimStore heartbeat; never overwrite child capture.
        previous = receipt_file.read()
        if not initial and (
            previous is None
            or previous.get("phase") != "CLAIMED"
            or checkpoint.object_record(previous.get("claim_owner")).get("owner_id")
            != value["owner_id"]
        ):
            raise ProtectedError("claim receipt changed before gated child release")
        receipt_file.write(
            {
                "schema_version": SCHEMA,
                "identity": self.request.identity,
                "execution_id": self.request.execution_id,
                "task_key": TASK_KEY,
                "claim_owner": value,
                "supervisor_pid": value["owner_pid"],
                "gated_child_pid": value["child_pid"],
                "direct_argv": self.request.managed_argv(),
                "phase": "CLAIMED" if initial else "GATED",
                "status": "INCOMPLETE_OR_AMBIGUOUS",
                "started_at": value["started_at_utc"],
                "completed_at": None,
                "exit_code": None,
                "child_exit_code": None,
                "stdout": None,
                "stderr": None,
                "managed_receipt": None,
                "result_status": None,
            },
            expected=previous,
        )
        self.gated = not initial


def managed_link(request: Request) -> Record | None:
    if not os.path.lexists(request.config.receipt_path):
        return None
    value, identity, _ = cutover.read_control_json(request.config.receipt_path)
    if (
        value.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or value.get("task") != cutover.TASK_ID
        or value.get("plan_digest") != request.plan_digest
        or record(value.get("target")).get("plist_path") != str(request.config.plist_path)
        or record(record(value.get("source"))["new"]).get("source_worktree")
        != str(request.config.source_worktree)
    ):
        raise ProtectedError("managed receipt identity differs")
    return {
        "path": str(request.config.receipt_path),
        "sha256": identity.sha256,
        "status": value.get("status"),
    }


def quiesce(
    request: Request,
    config: cutover.CutoverConfig,
    plan: Record,
    runner: cutover.Runner,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> list[Record]:
    # Establish the exact roots/HEADs before even stopping their watchers.
    for worktree, head, tree in request.sources:
        root = checkpoint.checked(runner, ["git", "-C", worktree, "rev-parse", "--show-toplevel"])
        if root.strip() != worktree:
            raise ProtectedError("fsmonitor target is not the exact worktree")
        if (
            checkpoint.git_value(runner, worktree, "HEAD") != head
            or checkpoint.git_value(runner, worktree, "HEAD^{tree}") != tree
        ):
            raise ProtectedError("fsmonitor target HEAD/tree differs")
    for worktree, _, _ in request.sources:
        stop_fsmonitor(worktree, runner)
    first = cutover.protected_snapshot(config, plan, runner)
    started = clock()
    sleeper(QUIESCENCE_SECONDS)
    if clock() - started < QUIESCENCE_SECONDS:
        raise ProtectedError("quiescence observation interval was too short")
    second = cutover.protected_snapshot(config, plan, runner)
    if first != second:
        raise ProtectedError("quiescence snapshots changed")
    return [first, second]


def stop_fsmonitor(worktree: str, runner: cutover.Runner) -> None:
    stopped = checkpoint.command(runner, ["git", "-C", worktree, "fsmonitor--daemon", "stop"])
    if stopped.returncode == 0 and not stopped.stderr.strip():
        return
    if (
        stopped.returncode == 128
        and not stopped.stdout.strip()
        and stopped.stderr == "fatal: fsmonitor--daemon is not running\n"
    ):
        status = checkpoint.command(runner, ["git", "-C", worktree, "fsmonitor--daemon", "status"])
        if (
            status.returncode == 1
            and not status.stderr.strip()
            and status.stdout == f"fsmonitor-daemon is not watching '{worktree}'\n"
        ):
            return
    raise ProtectedError("exact-worktree fsmonitor stop is unverified")


def child_request(args: argparse.Namespace) -> Request:
    wire = record(json.loads(text(args.protected_request), object_pairs_hook=unique_object))
    identity = record(wire.get("identity"))
    if type(wire.get("takeover_stale")) is not bool:
        raise ProtectedError("invalid takeover flag")
    config = cutover.protected_config(args)
    request = make_request(
        config,
        Path(text(identity.get("legacy_worktree"))),
        text(identity.get("legacy_head")),
        text(identity.get("legacy_tree")),
        Path(text(args.plan_file)),
        repository_claim_root(),
        takeover_stale=bool(wire["takeover_stale"]),
    )
    if request.identity != identity or request.execution_id != args.protected_execution:
        raise ProtectedError("protected request identity differs")
    return request


def run_managed_child(
    args: argparse.Namespace,
    *,
    runner: cutover.Runner = cutover.run_command,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    request = child_request(args)
    store = claims.ClaimStore(request.claim_root)
    claim = store.inspect(TASK_KEY)
    execution = checkpoint.ControlledExecution(
        request.claim_root,
        TASK_KEY,
        request.execution_id,
        text(claim.get("owner_id")),
        tuple(request.managed_argv()),
        tuple(request.owner_argv()),
        str(CONTROL_ROOT),
        request.sources,
    )
    config = replace(request.config, protected_execution=execution)
    # This snapshot validates the real parent/child before trusting any claimed PID.
    checkpoint.process_snapshot(
        argparse.Namespace(
            launch_domain=config.launch_domain,
            expected_rollback_worktree=str(request.legacy_worktree),
            expected_rollback_head=request.legacy_head,
            primary_lock_path=str(config.primary_lock_path),
            shadow_lock_path=str(config.shadow_lock_path),
            old_primary_identity=None,
            old_scheduler_identity=None,
            old_shadow_identity=None,
        ),
        runner,
        execution=execution,
    )
    receipt_file = ReceiptFile(request.receipt_path)
    gated = receipt_file.read()
    if (
        gated is None
        or gated.get("phase") != "GATED"
        or gated.get("identity") != request.identity
        or record(gated.get("claim_owner")).get("owner_id") != claim.get("owner_id")
        or gated.get("supervisor_pid") != os.getppid()
        or gated.get("gated_child_pid") != os.getpid()
    ):
        raise ProtectedError("child requires its exact durable gated receipt")
    receipt = receipt_file.write(
        {
            **gated,
            "phase": "STARTED",
            "child_started_at": now(),
        },
        expected=gated,
    )
    output, errors = BoundedStream(), BoundedStream()
    result: Record = {}
    invoked = False
    snapshots: list[Record] = []
    with redirect_stdout(output), redirect_stderr(errors):
        try:
            plan = request.load_plan()
            snapshots = quiesce(request, config, plan, runner, sleeper=sleeper, clock=clock)
            invoked = True
            result = cutover.apply(config, plan=plan, runner=runner)
            print(canonical(result))
        except BaseException as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            result = {"status": "INCOMPLETE_OR_AMBIGUOUS" if invoked else "FAILED"}
    code = 0 if result.get("status") in {"SUCCESS", "ALREADY_APPLIED"} else 1
    link = managed_link(request)
    receipt_file.write(
        {
            **receipt,
            "phase": "CHILD_COMPLETED",
            "child_completed_at": now(),
            "child_exit_code": code,
            "stdout": output.evidence(),
            "stderr": errors.evidence(),
            "result_status": result.get("status"),
            "managed_receipt": link,
            "quiescence": snapshots,
        },
        expected=receipt,
    )
    print(output.evidence()["text"], end="")
    print(errors.evidence()["text"], end="", file=sys.stderr)
    return code


def launch(request: Request) -> Record:
    """Compose ClaimStore.run unchanged; the child owns all pre-action preparation."""
    if Path.cwd() != CONTROL_ROOT:
        raise ProtectedError("launch from the exact control-plane checkout")
    store = ReceiptClaimStore(request)
    receipt_file = ReceiptFile(request.receipt_path)
    prior = receipt_file.read()
    if prior is not None:
        if prior.get("identity") != request.identity:
            raise ProtectedError("execution identity mismatch; prior result cannot be reused")
        if prior.get("status") != "SUCCESS":
            raise ProtectedError("incomplete/failed execution blocks automatic rerun")
        if store.inspect(TASK_KEY)["status"] != "ABSENT":
            raise ProtectedError("claim is still owned or uncertain")
        if prior.get("managed_receipt") != managed_link(request):
            raise ProtectedError("managed receipt linkage changed")
        return {**prior, "reused": True}
    code = store.run(TASK_KEY, request.managed_argv(), takeover_stale=request.takeover_stale)
    if store.owner_record is None:
        return {"status": "INCOMPLETE_OR_AMBIGUOUS", "exit_code": code or claims.UNVERIFIABLE}
    staged = receipt_file.read()
    if staged is None or staged.get("supervisor_pid") != os.getpid():
        return {"status": "INCOMPLETE_OR_AMBIGUOUS", "exit_code": code or claims.UNVERIFIABLE}
    if (
        staged.get("identity") != request.identity
        or staged.get("direct_argv") != request.managed_argv()
        or record(staged.get("claim_owner")).get("owner_pid") != os.getpid()
        or record(staged.get("claim_owner")).get("owner_id") != store.owner_record["owner_id"]
    ):
        raise ProtectedError("terminal owner identity differs")
    status = "INCOMPLETE_OR_AMBIGUOUS"
    if staged.get("phase") == "CHILD_COMPLETED" and staged.get("child_exit_code") == code:
        link = managed_link(request)
        if staged.get("managed_receipt") != link:
            raise ProtectedError("managed terminal receipt changed")
        if (
            code == 0
            and staged.get("result_status") in {"SUCCESS", "ALREADY_APPLIED"}
            and link is not None
            and link.get("status") == "SUCCESS"
        ):
            status = "SUCCESS"
        elif code != 0 and staged.get("result_status") in {"FAILED", "NOT_STARTED", "RECOVERED"}:
            status = "FAILED"
    saved = receipt_file.write(
        {
            **staged,
            "status": status,
            "phase": "COMPLETED",
            "completed_at": now(),
            "exit_code": code,
        },
        expected=staged,
    )
    return {**saved, "reused": False}


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    cli.add_argument("action", choices=("apply",))
    for name in (
        "source-worktree",
        "expected-head",
        "expected-tree",
        "legacy-worktree",
        "legacy-head",
        "legacy-tree",
        "plan-file",
    ):
        cli.add_argument("--" + name, required=True)
    cli.add_argument("--takeover-stale", action="store_true")
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    selected = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(selected)
    try:
        config = cutover.CutoverConfig(
            source_worktree=Path(args.source_worktree),
            expected_head=args.expected_head,
            expected_tree=args.expected_tree,
            durable_ref=f"refs/heads/runtime/b649/{args.expected_head}",
            strict_release_layout=True,
        )
        request = make_request(
            config,
            Path(args.legacy_worktree),
            args.legacy_head,
            args.legacy_tree,
            Path(args.plan_file),
            repository_claim_root(),
            takeover_stale=args.takeover_stale,
        )
        if selected != request.owner_argv()[2:]:
            raise ProtectedError("use the canonical argument order shown by --help")
        result = launch(request)
        print(canonical(result))
        return (
            0
            if result["status"] == "SUCCESS"
            else int(cast(int, result.get("exit_code", 74))) or 74
        )
    except (OSError, ValueError, ProtectedError, cutover.CutoverError, claims.ClaimError) as exc:
        print(canonical({"status": "INCOMPLETE_OR_AMBIGUOUS", "error": str(exc)}))
        return claims.UNVERIFIABLE


if __name__ == "__main__":
    raise SystemExit(main())
