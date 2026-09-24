"""One foreground, claim-owned B649 cutover action; production execution needs Owner authority.

Future command contract (run from this control-plane checkout, using absolute paths)::

    <python> <checkout>/tools/b649_protected_cutover.py apply \
        --source-worktree <successor> --expected-head <HEAD> --expected-tree <TREE> \
        --legacy-worktree <legacy> --legacy-head <HEAD> --legacy-tree <TREE> \
        --plan-file <owner-only-plan.json> [--takeover-stale]

    <python> <checkout>/tools/b649_protected_cutover.py rollback \
        --receipt-file <exact-managed-receipt> \
        --legacy-worktree <legacy-worktree> --legacy-head <HEAD> --legacy-tree <TREE> \
        [--takeover-stale]

The argument order above is canonical. No PID exemptions, arbitrary commands,
receipt-root overrides, or automatic retries are accepted by the CLI. The fixed
task key serializes every plan for this LaunchAgent in the repository ClaimStore.
The execution digest binds the exact plan or managed receipt and source/target
identities. A stale claim can be taken only by ClaimStore's explicit
positive-death protocol; any existing non-success execution receipt still
blocks. Reconciliation is separate.

ClaimStore gates the actual b649_production_cutover.py process. That child records
STARTED before quiescence or apply/rollback, and stages bounded output before returning.
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
ROLLBACK_RECEIPT_NAME = "b649-protected-rollback-execution-receipt.json"
LIFECYCLE_RECEIPT_NAME = "b649-control-lifecycle-reconciliation.json"
LIFECYCLE_SCHEMA = "b649-control-lifecycle-reconciliation-v1"
CONTROL_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = CONTROL_ROOT / "tools/b649_protected_cutover.py"
MANAGED = CONTROL_ROOT / "tools/b649_production_cutover.py"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_STREAM_BYTES = 32 * 1024
QUIESCENCE_SECONDS = 5.0
ROLLBACK_SUCCESS = "ROLLBACK_SUCCESS"
ROLLBACK_FAILED = "ROLLBACK_FAILED"
ROLLBACK_INCOMPLETE = "ROLLBACK_INCOMPLETE_OR_AMBIGUOUS"
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
    reservation_id: str | None = None
    operation_id: str = ""
    managed_receipt_sha256: str | None = None
    control_head: str = ""
    control_tree: str = ""
    owner_id_argument: bool = False

    @property
    def action(self) -> str:
        return "apply"

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
            "control_head": self.control_head,
            "control_tree": self.control_tree,
            "reservation_id": self.reservation_id,
            "operation_id": self.operation_id,
            "managed_receipt_sha256": self.managed_receipt_sha256,
            "owner_id_argument": self.owner_id_argument,
            "target": {
                "source_worktree": str(self.config.source_worktree),
                "head": self.config.expected_head,
                "tree": self.config.expected_tree,
                "durable_ref": self.config.durable_ref,
            },
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
            *(["--owner-id", text(self.reservation_id)] if self.owner_id_argument else []),
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
    reservation_id: str | None = None,
    owner_id_argument: bool = False,
    operation_id: str | None = None,
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
    managed: Record | None = None
    managed_identity: cutover.FileIdentity | None = None
    if os.path.lexists(config.receipt_path):
        managed, managed_identity, _ = cutover.read_control_json(config.receipt_path)
    control_head, control_tree = control_identity()
    selected_operation_id = operation_id or (
        text(managed.get("operation_id"))
        if managed is not None and managed.get("plan_digest") == plan.get("plan_digest")
        else uuid4().hex
    )
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
        reservation_id,
        selected_operation_id,
        None if managed_identity is None else managed_identity.sha256,
        control_head,
        control_tree,
        owner_id_argument,
    )
    if request.receipt_path in {config.receipt_path, config.plist_path, plan_file}:
        raise ProtectedError("execution receipt must have its own canonical path")
    request.load_plan()
    return request


def control_identity() -> tuple[str, str]:
    return (
        checkpoint.git_value(cutover.run_command, str(CONTROL_ROOT), "HEAD"),
        checkpoint.git_value(cutover.run_command, str(CONTROL_ROOT), "HEAD^{tree}"),
    )


@dataclass(frozen=True)
class RollbackRequest:
    config: cutover.CutoverConfig
    legacy_worktree: Path
    legacy_head: str
    legacy_tree: str
    managed_receipt_sha256: str
    operation_id: str
    plan_digest: str
    prestate_digest: str
    old_durable_ref: str
    new_durable_ref: str
    control_head: str
    control_tree: str
    claim_root: Path
    takeover_stale: bool = False
    reservation_id: str | None = None
    owner_id_argument: bool = False

    @property
    def action(self) -> str:
        return "rollback"

    @property
    def receipt_path(self) -> Path:
        return self.config.scheduler_root / ROLLBACK_RECEIPT_NAME

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
            "action": self.action,
            "managed_receipt_path": str(self.config.receipt_path),
            "managed_receipt_sha256": self.managed_receipt_sha256,
            "operation_id": self.operation_id,
            "plan_digest": self.plan_digest,
            "prestate_digest": self.prestate_digest,
            "legacy_worktree": str(self.legacy_worktree),
            "legacy_head": self.legacy_head,
            "legacy_tree": self.legacy_tree,
            "old_durable_ref": self.old_durable_ref,
            "new_worktree": str(self.config.source_worktree),
            "new_head": self.config.expected_head,
            "new_tree": self.config.expected_tree,
            "new_durable_ref": self.new_durable_ref,
            "plist_path": str(self.config.plist_path),
            "launch_domain": self.config.launch_domain,
            "label": self.config.label,
            "control_worktree": str(CONTROL_ROOT),
            "control_head": self.control_head,
            "control_tree": self.control_tree,
            "reservation_id": self.reservation_id,
            "owner_id_argument": self.owner_id_argument,
            "target": {
                "source_worktree": str(self.legacy_worktree),
                "head": self.legacy_head,
                "tree": self.legacy_tree,
                "durable_ref": self.old_durable_ref,
            },
            "protected_wrapper_schema": SCHEMA,
            "claim_root": str(self.claim_root),
            "execution_receipt_path": str(self.receipt_path),
            "interpreter": sys.executable,
        }

    @property
    def execution_id(self) -> str:
        return digest(self.identity)

    def owner_argv(self) -> list[str]:
        return [
            sys.executable,
            str(LAUNCHER),
            "rollback",
            "--receipt-file",
            str(self.config.receipt_path),
            "--legacy-worktree",
            str(self.legacy_worktree),
            "--legacy-head",
            self.legacy_head,
            "--legacy-tree",
            self.legacy_tree,
            *(["--owner-id", text(self.reservation_id)] if self.owner_id_argument else []),
            *( ["--takeover-stale"] if self.takeover_stale else []),
        ]

    def managed_argv(self) -> list[str]:
        wire = {"identity": self.identity, "takeover_stale": self.takeover_stale}
        return [
            sys.executable,
            str(MANAGED),
            "rollback",
            "--receipt-file",
            str(self.config.receipt_path),
            "--protected-request",
            canonical(wire),
            "--protected-execution",
            self.execution_id,
        ]

    def load_receipt(self) -> Record:
        receipt, identity, _ = cutover.read_control_json(self.config.receipt_path)
        if identity.sha256 != self.managed_receipt_sha256:
            raise ProtectedError("managed receipt SHA256 changed")
        if (
            text(receipt.get("operation_id")) != self.operation_id
            or text(receipt.get("plan_digest")) != self.plan_digest
            or text(receipt.get("prestate_digest")) != self.prestate_digest
        ):
            raise ProtectedError("managed receipt identity changed")
        return receipt

    def load_plan(self) -> Record:
        return cutover.receipt_to_plan(self.config, self.load_receipt())


def make_rollback_request(
    config: cutover.CutoverConfig,
    legacy_worktree: Path,
    legacy_head: str,
    legacy_tree: str,
    claim_root: Path,
    *,
    takeover_stale: bool = False,
    reservation_id: str | None = None,
    owner_id_argument: bool = False,
) -> RollbackRequest:
    for path in (
        config.source_worktree,
        legacy_worktree,
        config.receipt_path,
        claim_root,
        config.scheduler_root,
        config.plist_path,
    ):
        if not path.is_absolute() or path != path.resolve() or ".." in path.parts:
            raise ProtectedError("execution paths must be canonical and must not traverse symlinks")
    for value in (legacy_head, legacy_tree, config.expected_head, config.expected_tree):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ProtectedError("full exact HEAD/tree required")
    if legacy_worktree == config.source_worktree:
        raise ProtectedError("legacy and successor worktrees must differ")
    receipt, identity, _ = cutover.read_control_json(config.receipt_path)
    if receipt.get("status") == ROLLBACK_SUCCESS:
        raise ProtectedError(
            "managed rollback already completed; use managed-only lifecycle closure"
        )
    plan = cutover.receipt_to_plan(config, receipt)
    cutover.validate_protected_plan(config, plan)
    if receipt.get("status") not in {
        "SUCCESS",
        "PARTIAL",
        "RECOVERY_REQUIRED",
        "RECOVERED",
        "ROLLBACK_IN_PROGRESS",
        "IN_PROGRESS",
    }:
        raise ProtectedError("managed receipt is not eligible for explicit rollback")
    prestate = record(receipt.get("prestate"))
    old_source = record(prestate.get("old_source"))
    new_source = record(prestate.get("new_source"))
    receipt_sources = record(receipt.get("source"))
    if (
        record(receipt_sources.get("old")) != old_source
        or record(receipt_sources.get("new")) != new_source
        or (str(old_source.get("source_worktree")), old_source.get("head"), old_source.get("tree"))
        != (str(legacy_worktree), legacy_head, legacy_tree)
        or str(new_source.get("source_worktree")) != str(config.source_worktree)
        or new_source.get("head") != config.expected_head
        or new_source.get("tree") != config.expected_tree
        or new_source.get("durable_ref") != config.durable_ref
    ):
        raise ProtectedError("receipt/legacy identity differs")
    control_head, control_tree = control_identity()
    return RollbackRequest(
        config=config,
        legacy_worktree=legacy_worktree,
        legacy_head=legacy_head,
        legacy_tree=legacy_tree,
        managed_receipt_sha256=identity.sha256,
        operation_id=text(receipt.get("operation_id")),
        plan_digest=text(receipt.get("plan_digest")),
        prestate_digest=text(receipt.get("prestate_digest")),
        old_durable_ref=text(old_source.get("durable_ref")),
        new_durable_ref=text(new_source.get("durable_ref")),
        control_head=control_head,
        control_tree=control_tree,
        claim_root=claim_root,
        takeover_stale=takeover_stale,
        reservation_id=reservation_id,
        owner_id_argument=owner_id_argument,
    )


def request_owner_target(request: Request | RollbackRequest) -> Record:
    if request.action == "apply":
        return {
            "source_worktree": str(request.config.source_worktree),
            "head": text(request.config.expected_head),
            "tree": text(request.config.expected_tree),
            "durable_ref": text(request.config.durable_ref),
        }
    rollback_request = cast(RollbackRequest, request)
    return {
        "source_worktree": str(rollback_request.legacy_worktree),
        "head": rollback_request.legacy_head,
        "tree": rollback_request.legacy_tree,
        "durable_ref": rollback_request.old_durable_ref,
    }


def request_owner_authorization(request: Request | RollbackRequest) -> Record:
    identity = request.identity
    if identity.get("reservation_id") is None:
        raise ProtectedError("request is missing its durable reservation id")
    return {
        "reservation_id": identity["reservation_id"],
        "operation_id": identity["operation_id"],
        "managed_receipt_sha256": identity["managed_receipt_sha256"],
        "control_head": identity["control_head"],
        "control_tree": identity["control_tree"],
        "action": identity["action"],
        "target": request_owner_target(request),
    }


@dataclass(frozen=True)
class RollbackControlledExecution(checkpoint.ControlledExecution):
    """The existing process-snapshot proof specialized to protected rollback."""

    def verify(
        self, processes: dict[int, checkpoint.Process], uid: int
    ) -> Record:
        root = Path(__file__).resolve().parents[1]
        if (
            self.task_key != TASK_KEY
            or self.child_argv[:3]
            != (sys.executable, str(MANAGED), "rollback")
            or self.child_argv[-4:-3] != ("--protected-request",)
        ):
            raise checkpoint.Unverifiable("only the protected B649 rollback can control ownership")
        wire = record(json.loads(self.child_argv[-3], object_pairs_hook=unique_object))
        identity = record(wire.get("identity"))
        identity_digest = digest(identity)
        expected_owner = (
            sys.executable,
            str(LAUNCHER),
            "rollback",
            "--receipt-file",
            identity.get("managed_receipt_path"),
            "--legacy-worktree",
            identity.get("legacy_worktree"),
            "--legacy-head",
            identity.get("legacy_head"),
            "--legacy-tree",
            identity.get("legacy_tree"),
            *( ["--takeover-stale"] if wire.get("takeover_stale") is True else []),
        )
        if (
            identity_digest != self.execution_id
            or identity.get("task_key") != self.task_key
            or identity.get("action") != "rollback"
            or identity.get("protected_wrapper_schema") != SCHEMA
            or identity.get("claim_root") != str(self.claim_root)
            or identity.get("control_worktree") != str(root)
            or self.owner_cwd != str(root)
            or self.owner_argv != expected_owner
            or self.sources
            != (
                (
                    identity.get("legacy_worktree"),
                    identity.get("legacy_head"),
                    identity.get("legacy_tree"),
                ),
                (
                    identity.get("new_worktree"),
                    identity.get("new_head"),
                    identity.get("new_tree"),
                ),
            )
        ):
            raise checkpoint.Unverifiable(
                "protected rollback proof is not bound to its immutable identity"
            )
        claim = claims.ClaimStore(self.claim_root).inspect(self.task_key)
        child, owner = os.getpid(), os.getppid()
        if (
            claim.get("status") != "ACTIVE"
            or claim.get("owner_alive") is not True
            or claim.get("child_alive") is not True
            or claim.get("owner_id") != self.owner_id
            or claim.get("owner_pid") != owner
            or claim.get("child_pid") != child
            or claim.get("command") != list(self.child_argv)
            or claim.get("cwd") != self.owner_cwd
            or not re.fullmatch(r"[0-9a-f]{64}", self.execution_id)
            or "--protected-execution" not in self.child_argv
            or self.child_argv[-1] != self.execution_id
        ):
            raise checkpoint.Unverifiable(
                "protected rollback claim/identity does not match this child"
            )
        for pid, argv in ((owner, self.owner_argv), (child, self.child_argv)):
            process = processes.get(pid)
            if (
                process is None
                or process.uid != uid
                or not checkpoint.interpreter_command_matches(process, argv)
                or process.cwd != self.owner_cwd
            ):
                raise checkpoint.Unverifiable("protected rollback process identity is unverified")
        if processes[child].ppid != owner or owner == child:
            raise checkpoint.Unverifiable("protected rollback parent/child chain changed")
        return {
            "execution_id": self.execution_id,
            "owner_id": self.owner_id,
            "supervisor_pid": owner,
            "gated_child_pid": child,
        }


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
        identity, owner = record(value["identity"]), record(value["claim_owner"])
        action = identity.get("action")
        if (
            value.get("schema_version") != SCHEMA
            or value.get("receipt_sha256") != digest(unsigned)
            or value.get("execution_id") != digest(value.get("identity"))
            or action not in {"apply", "rollback"}
            or value.get("status")
            not in {
                "SUCCESS",
                "FAILED",
                "INCOMPLETE_OR_AMBIGUOUS",
                ROLLBACK_SUCCESS,
                ROLLBACK_FAILED,
                ROLLBACK_INCOMPLETE,
            }
        ):
            raise ProtectedError("receipt schema/integrity is invalid")
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
        if value["status"] in {"SUCCESS", "FAILED", ROLLBACK_SUCCESS, ROLLBACK_FAILED} and (
            value.get("phase") != "COMPLETED"
            or not value.get("completed_at")
            or type(value.get("exit_code")) is not int
        ):
            raise ProtectedError("terminal receipt is incomplete")
        if action == "apply" and value["status"] == "SUCCESS" and (
            value.get("exit_code") != 0
            or value.get("child_exit_code") != 0
            or value.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
            or not isinstance(value.get("managed_receipt"), dict)
        ):
            raise ProtectedError("success receipt lacks terminal evidence")
        if action == "rollback" and value["status"] == ROLLBACK_SUCCESS and (
            value.get("exit_code") != 0
            or value.get("child_exit_code") != 0
            or value.get("result_status") not in {ROLLBACK_SUCCESS, "ALREADY_ROLLED_BACK"}
            or not isinstance(value.get("managed_receipt"), dict)
        ):
            raise ProtectedError("rollback success receipt lacks terminal evidence")
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


def _lifecycle_path(config: cutover.CutoverConfig) -> Path:
    return config.scheduler_root / LIFECYCLE_RECEIPT_NAME


def _lifecycle_record(config: cutover.CutoverConfig) -> tuple[Record, cutover.FileIdentity] | None:
    path = _lifecycle_path(config)
    if not os.path.lexists(path):
        return None
    value, identity, _ = cutover.read_control_json(path)
    unsigned = {key: item for key, item in value.items() if key != "record_sha256"}
    if (
        value.get("schema") != LIFECYCLE_SCHEMA
        or value.get("record_sha256") != digest(unsigned)
        or value.get("disposition") != "MANAGED_ONLY_EXTERNALLY_COMPLETED"
        or value.get("provenance") != "MANAGED_ONLY_CONFIRMED"
        or value.get("protected_wrapper_executed") is not False
    ):
        raise ProtectedError("lifecycle reconciliation evidence is invalid")
    return value, identity


def _lifecycle_source_identity(value: object) -> Record:
    source = record(value)
    return {
        key: text(source.get(key))
        for key in ("source_worktree", "head", "tree", "durable_ref")
    }


def close_managed_only_lifecycle(
    config: cutover.CutoverConfig,
    *,
    operation_id: str,
    managed_receipt_sha256: str,
    restored_source: Record,
    runtime_verification: Record,
) -> Record:
    """Close verified external rollback history without running or claiming execution."""
    if re.fullmatch(r"[0-9a-f]{64}", managed_receipt_sha256) is None:
        raise ProtectedError("managed receipt SHA256 is invalid")
    path = _lifecycle_path(config)
    rollback_path = config.scheduler_root / ROLLBACK_RECEIPT_NAME
    apply_path = config.scheduler_root / RECEIPT_NAME
    with cutover.CutoverLock(config.cutover_lock_path):
        owner = cutover.inspect_control_owner(config)
        if owner is not None and owner.get("phase") != "RELEASED":
            raise ProtectedError("durable control owner requires reconciliation before closure")
        if os.path.lexists(rollback_path):
            raise ProtectedError("protected rollback receipt already exists; closure is ambiguous")
        managed, managed_identity, managed_bytes = cutover.read_control_json(config.receipt_path)
        if (
            managed_identity.sha256 != managed_receipt_sha256
            or managed.get("operation_id") != operation_id
            or managed.get("status") != ROLLBACK_SUCCESS
            or managed.get("phase") != "COMPLETED"
        ):
            raise ProtectedError("managed rollback is not the exact terminal success")
        plan = cutover.receipt_to_plan(config, managed)
        prestate = record(managed.get("prestate"))
        expected_source = record(prestate.get("old_source"))
        source = {
            key: expected_source.get(key)
            for key in ("source_worktree", "head", "tree", "durable_ref")
        }
        if _lifecycle_source_identity(restored_source) != source:
            raise ProtectedError("restored source differs from the managed receipt")
        after = record(managed.get("after"))
        after_source = record(after.get("source"))
        old_runtime = record(prestate.get("old_runtime"))
        after_runtime = record(after.get("runtime"))
        after_plist = record(after.get("plist"))
        after_launchd = record(after.get("launchd"))
        observer = runtime_verification.get("observer")
        if (
            runtime_verification.get("kind") != "independent-runtime-verification-v1"
            or runtime_verification.get("verified") is not True
            or not isinstance(observer, str)
            or observer == "managed-receipt"
            or _lifecycle_source_identity(runtime_verification.get("source")) != source
            or record(runtime_verification.get("runtime")) != old_runtime
            or runtime_verification.get("plist_sha256") != after_plist.get("sha256")
            or runtime_verification.get("launch_state") != after_launchd.get("state")
            or runtime_verification.get("enabled") is not after.get("enabled")
            or _lifecycle_source_identity(after_source) != source
            or after_runtime != old_runtime
            or _lifecycle_source_identity(record(plan.get("source")).get("old")) != source
        ):
            raise ProtectedError("independent restored-runtime verification differs")
        apply_before = cutover.inspect_control_file(apply_path, missing_ok=True)[0]
        existing = _lifecycle_record(config)
        control = cutover.control_version()
        closure_identity: Record = {
            "control_head": control["head"],
            "control_tree": control["tree"],
            "operation_id": operation_id,
            "managed_receipt_sha256": managed_receipt_sha256,
            "restored_source": source,
            "runtime_verification_sha256": digest(runtime_verification),
        }
        if existing is not None:
            saved, _ = existing
            if saved.get("identity") != closure_identity:
                raise ProtectedError("a different lifecycle closure already exists")
            result = saved
        else:
            unsigned: Record = {
                "schema": LIFECYCLE_SCHEMA,
                "disposition": "MANAGED_ONLY_EXTERNALLY_COMPLETED",
                "provenance": "MANAGED_ONLY_CONFIRMED",
                "protected_wrapper_executed": False,
                "operation_id": operation_id,
                "managed_receipt_sha256": managed_receipt_sha256,
                "managed_status": ROLLBACK_SUCCESS,
                "protected_rollback_receipt": None,
                "identity": closure_identity,
                "runtime_verification": runtime_verification,
                "closed_at": now(),
            }
            result = {**unsigned, "record_sha256": digest(unsigned)}
            cutover.write_control_json(path, result, expected=None)
        readback, _, _ = cutover.read_control_json(path)
        if readback != result:
            raise ProtectedError("lifecycle closure readback differs")
        managed_after, managed_identity_after, managed_bytes_after = cutover.read_control_json(
            config.receipt_path
        )
        apply_after = cutover.inspect_control_file(apply_path, missing_ok=True)[0]
        if (
            managed_identity_after.sha256 != managed_identity.sha256
            or managed_bytes_after != managed_bytes
            or managed_after != managed
            or (None if apply_before is None else apply_before.key())
            != (None if apply_after is None else apply_after.key())
            or os.path.lexists(rollback_path)
        ):
            raise ProtectedError("control evidence changed while lifecycle closure was written")
        return result


def classify_execution_provenance(
    config: cutover.CutoverConfig,
    *,
    operation_id: str,
    managed_receipt_sha256: str,
) -> str:
    """Keep protected execution distinct from external managed completion."""
    rollback_path = config.scheduler_root / ROLLBACK_RECEIPT_NAME
    if os.path.lexists(rollback_path):
        receipt = ReceiptFile(rollback_path).read()
        if receipt is None:
            raise ProtectedError("protected rollback receipt disappeared")
        identity = record(receipt.get("identity"))
        link_value = receipt.get("managed_receipt")
        link = record(link_value) if link_value is not None else {}
        if (
            receipt.get("status") == ROLLBACK_SUCCESS
            and receipt.get("phase") == "COMPLETED"
            and identity.get("operation_id") == operation_id
            and link.get("sha256") == managed_receipt_sha256
        ):
            return "PROTECTED_WRAPPER_CONFIRMED"
        return "PROTECTED_EXECUTION_NOT_CONFIRMED"
    lifecycle = _lifecycle_record(config)
    if lifecycle is not None:
        value, _ = lifecycle
        identity = record(value.get("identity"))
        if (
            identity.get("operation_id") == operation_id
            and identity.get("managed_receipt_sha256") == managed_receipt_sha256
        ):
            return "MANAGED_ONLY_CONFIRMED"
    return "PROVENANCE_NOT_ESTABLISHED"


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

    def __init__(self, request: Request | RollbackRequest):
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
                "status": (
                    ROLLBACK_INCOMPLETE
                    if self.request.action == "rollback"
                    else "INCOMPLETE_OR_AMBIGUOUS"
                ),
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


def managed_link(request: Request | RollbackRequest) -> Record | None:
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
    request: Request | RollbackRequest,
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
    first = cutover.protected_snapshot(
        config,
        plan,
        runner,
        rollback=request.action == "rollback",
    )
    started = clock()
    sleeper(QUIESCENCE_SECONDS)
    if clock() - started < QUIESCENCE_SECONDS:
        raise ProtectedError("quiescence observation interval was too short")
    second = cutover.protected_snapshot(
        config,
        plan,
        runner,
        rollback=request.action == "rollback",
    )
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


def child_request(args: argparse.Namespace) -> Request | RollbackRequest:
    wire = record(json.loads(text(args.protected_request), object_pairs_hook=unique_object))
    identity = record(wire.get("identity"))
    if type(wire.get("takeover_stale")) is not bool:
        raise ProtectedError("invalid takeover flag")
    if type(identity.get("owner_id_argument")) is not bool:
        raise ProtectedError("invalid owner-id argument binding")
    reservation_id_value = identity.get("reservation_id")
    reservation_id = None if reservation_id_value is None else text(reservation_id_value)
    try:
        config = cutover.protected_config(args)
        if identity.get("action") == "rollback":
            request = make_rollback_request(
                config,
                Path(text(identity.get("legacy_worktree"))),
                text(identity.get("legacy_head")),
                text(identity.get("legacy_tree")),
                repository_claim_root(),
                takeover_stale=bool(wire["takeover_stale"]),
                reservation_id=reservation_id,
                owner_id_argument=bool(identity["owner_id_argument"]),
            )
        else:
            request = make_request(
                config,
                Path(text(identity.get("legacy_worktree"))),
                text(identity.get("legacy_head")),
                text(identity.get("legacy_tree")),
                Path(text(args.plan_file)),
                repository_claim_root(),
                takeover_stale=bool(wire["takeover_stale"]),
                reservation_id=reservation_id,
                owner_id_argument=bool(identity["owner_id_argument"]),
                operation_id=text(identity.get("operation_id")),
            )
    except (OSError, ValueError, cutover.CutoverError) as exc:
        raise ProtectedError(f"protected request cannot be revalidated: {exc}") from exc
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
    execution_type = (
        RollbackControlledExecution
        if request.action == "rollback"
        else checkpoint.ControlledExecution
    )
    execution = execution_type(
        request.claim_root,
        TASK_KEY,
        request.execution_id,
        text(claim.get("owner_id")),
        tuple(request.managed_argv()),
        tuple(request.owner_argv()),
        str(CONTROL_ROOT),
        request.sources,
    )
    config = replace(
        request.config,
        protected_execution=execution,
        control_owner_id=request.reservation_id,
        control_owner_kind="protected",
        operation_id=text(request.identity.get("operation_id")),
    )
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
            if isinstance(request, RollbackRequest):
                managed_receipt: Record | None = request.load_receipt()
                plan = cutover.receipt_to_plan(config, managed_receipt)
            else:
                managed_receipt = None
                plan = request.load_plan()
            snapshots = quiesce(request, config, plan, runner, sleeper=sleeper, clock=clock)
            invoked = True
            if isinstance(request, RollbackRequest):
                result = cutover.rollback(
                    config,
                    receipt=managed_receipt,
                    runner=runner,
                )
                raw_status = result.get("status")
                protected_status = (
                    ROLLBACK_SUCCESS
                    if raw_status in {ROLLBACK_SUCCESS, "ALREADY_ROLLED_BACK"}
                    else ROLLBACK_FAILED
                    if raw_status in {"ROLLBACK_BLOCKED_ACTIVE_CYCLE", "NOT_STARTED"}
                    else ROLLBACK_INCOMPLETE
                )
                result = {**result, "protected_status": protected_status}
            else:
                result = cutover.apply(config, plan=plan, runner=runner)
            print(canonical(result))
        except BaseException as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            if request.action == "rollback":
                failure_status = ROLLBACK_INCOMPLETE if invoked else ROLLBACK_FAILED
            else:
                failure_status = "INCOMPLETE_OR_AMBIGUOUS" if invoked else "FAILED"
            result = {"status": failure_status}
    protected_status = cast(str, result.get("protected_status", result.get("status")))
    code = 0 if protected_status in {"SUCCESS", "ALREADY_APPLIED", ROLLBACK_SUCCESS} else 1
    link = managed_link(request)
    receipt_file.write(
        {
            **receipt,
            "phase": "CHILD_COMPLETED",
            "child_completed_at": now(),
            "child_exit_code": code,
            "stdout": output.evidence(),
            "stderr": errors.evidence(),
            "result_status": protected_status,
            "managed_receipt": link,
            "quiescence": snapshots,
        },
        expected=receipt,
    )
    print(output.evidence()["text"], end="")
    print(errors.evidence()["text"], end="", file=sys.stderr)
    return code


def launch(request: Request | RollbackRequest) -> Record:
    """Compose ClaimStore.run unchanged; the child owns all pre-action preparation."""
    if Path.cwd() != CONTROL_ROOT:
        raise ProtectedError("launch from the exact control-plane checkout")
    receipt_file = ReceiptFile(request.receipt_path)
    receipt_parent = request.receipt_path.parent
    if receipt_parent != receipt_parent.resolve(strict=False):
        raise ProtectedError("receipt parent must not traverse symlinks")
    receipt_metadata = os.lstat(receipt_parent)
    if (
        not stat.S_ISDIR(receipt_metadata.st_mode)
        or receipt_metadata.st_uid != os.getuid()
        or stat.S_IMODE(receipt_metadata.st_mode) != 0o700
    ):
        raise ProtectedError("receipt directory must be existing owner-only mode 0700")
    version = {"head": request.identity["control_head"], "tree": request.identity["control_tree"]}
    owner = cutover.inspect_control_owner(request.config)
    if owner is not None and owner.get("phase") == "RELEASED":
        released_id = text(owner.get("reservation_id"))
        execution_exists = os.path.lexists(request.receipt_path)
        if request.reservation_id is None:
            candidate = replace(request, reservation_id=released_id)
            if (
                execution_exists
                and cutover.control_owner_authorization(owner)
                == request_owner_authorization(candidate)
            ):
                request = candidate
            elif execution_exists:
                raise ProtectedError("a different completed owner identity blocks receipt reuse")
        elif request.reservation_id == released_id:
            if not execution_exists:
                request = replace(request, reservation_id=None)
        elif execution_exists:
            raise ProtectedError("a different completed owner identity blocks receipt reuse")
        else:
            request = replace(request, reservation_id=None)
    if request.reservation_id is None:
        owner = cutover.acquire_control_owner(
            request.config,
            action=request.action,
            target=request_owner_target(request),
            owner_kind="protected",
            version=version,
        )
        request = replace(request, reservation_id=text(owner.get("reservation_id")))
        owner = cutover.bind_control_owner(
            request.config,
            text(request.reservation_id),
            action=request.action,
            target=request_owner_target(request),
            operation_id=text(request.identity.get("operation_id")),
            managed_receipt_sha256=cast(
                str | None,
                request.identity.get("managed_receipt_sha256"),
            ),
            version=version,
        )
    else:
        owner = cutover.inspect_control_owner(request.config)
        if owner is None or owner.get("reservation_id") != request.reservation_id:
            raise ProtectedError("durable control owner is absent or changed")
        if owner.get("phase") != "RELEASED":
            owner = cutover.bind_control_owner(
                request.config,
                text(request.reservation_id),
                action=request.action,
                target=request_owner_target(request),
                operation_id=text(request.identity.get("operation_id")),
                managed_receipt_sha256=cast(
                    str | None,
                    request.identity.get("managed_receipt_sha256"),
                ),
                version=version,
            )
    if owner.get("phase") != "RELEASED":
        authorization = request_owner_authorization(request)
        if owner.get("authorization") is None:
            return {
                "status": "AUTHORIZATION_PENDING",
                "reservation_id": request.reservation_id,
                "authorization": authorization,
                "owner_phase": owner.get("phase"),
            }
        if owner.get("authorization") != authorization:
            raise ProtectedError("durable owner authorization differs from this request")
    success_status = ROLLBACK_SUCCESS if request.action == "rollback" else "SUCCESS"
    incomplete_status = (
        ROLLBACK_INCOMPLETE
        if request.action == "rollback"
        else "INCOMPLETE_OR_AMBIGUOUS"
    )
    store = ReceiptClaimStore(request)
    prior = receipt_file.read()
    if prior is not None:
        if prior.get("identity") != request.identity:
            raise ProtectedError("execution identity mismatch; prior result cannot be reused")
        if prior.get("status") != success_status:
            raise ProtectedError("incomplete/failed execution blocks automatic rerun")
        if store.inspect(TASK_KEY)["status"] != "ABSENT":
            raise ProtectedError("claim is still owned or uncertain")
        if prior.get("managed_receipt") != managed_link(request):
            raise ProtectedError("managed receipt linkage changed")
        current_owner = cutover.inspect_control_owner(request.config)
        if (
            current_owner is not None
            and current_owner.get("reservation_id") == request.reservation_id
            and current_owner.get("phase") == "TERMINAL_CAPTURE_PENDING"
        ):
            cutover.release_control_owner(
                request.config,
                text(request.reservation_id),
                protected_receipt_path=request.receipt_path,
            )
        return {**prior, "reused": True}
    if owner.get("phase") in {"MUTATION_IN_PROGRESS", "TERMINAL_CAPTURE_PENDING"}:
        raise ProtectedError(
            "started owner has no reusable protected terminal receipt; reconcile exact evidence"
        )
    code = store.run(TASK_KEY, request.managed_argv(), takeover_stale=request.takeover_stale)
    if store.owner_record is None:
        return {"status": incomplete_status, "exit_code": code or claims.UNVERIFIABLE}
    staged = receipt_file.read()
    if staged is None or staged.get("supervisor_pid") != os.getpid():
        return {"status": incomplete_status, "exit_code": code or claims.UNVERIFIABLE}
    if (
        staged.get("identity") != request.identity
        or staged.get("direct_argv") != request.managed_argv()
        or record(staged.get("claim_owner")).get("owner_pid") != os.getpid()
        or record(staged.get("claim_owner")).get("owner_id") != store.owner_record["owner_id"]
    ):
        raise ProtectedError("terminal owner identity differs")
    status = incomplete_status
    terminal = staged
    link: Record | None
    try:
        link = managed_link(request)
    except (OSError, ValueError, ProtectedError, cutover.CutoverError):
        # A changed or missing managed receipt cannot be relinked.  The
        # protected terminal result remains durable and blocks retry, but does
        # not treat changed bytes as authoritative linkage.
        link = None
    if staged.get("phase") == "CHILD_COMPLETED" and staged.get("child_exit_code") == code:
        if staged.get("managed_receipt") != link:
            raise ProtectedError("managed terminal receipt changed")
        if request.action == "rollback":
            if (
                code == 0
                and staged.get("result_status") == ROLLBACK_SUCCESS
                and link is not None
                and link.get("status") in {"ROLLBACK_SUCCESS", "SUCCESS"}
            ):
                status = ROLLBACK_SUCCESS
            elif code != 0 and staged.get("result_status") == ROLLBACK_FAILED:
                status = ROLLBACK_FAILED
        elif (
            code == 0
            and staged.get("result_status") in {"SUCCESS", "ALREADY_APPLIED"}
            and link is not None
            and link.get("status") == "SUCCESS"
        ):
            status = "SUCCESS"
        elif code != 0 and staged.get("result_status") in {"FAILED", "NOT_STARTED", "RECOVERED"}:
            status = "FAILED"
    else:
        # ClaimStore can observe a child that never reached the protected
        # wrapper (for example, an interpreter/exec failure).  Preserve the
        # current receipt-bound managed link when it is still readable while
        # recording the protected result as incomplete.
        terminal = {
            **staged,
            "result_status": incomplete_status,
            "managed_receipt": link,
        }
    saved = receipt_file.write(
        {
            **terminal,
            "status": status,
            "phase": "COMPLETED",
            "completed_at": now(),
            "exit_code": code,
        },
        expected=staged,
    )
    readback = receipt_file.read()
    if readback != saved:
        raise ProtectedError("protected terminal receipt verification failed")
    try:
        cutover.release_control_owner(
            request.config,
            text(request.reservation_id),
            protected_receipt_path=request.receipt_path,
        )
    except cutover.CutoverSafetyError as exc:
        owner_after = cutover.inspect_control_owner(request.config)
        if (
            status not in {"SUCCESS", ROLLBACK_SUCCESS}
            and owner_after is not None
            and owner_after.get("reservation_id") == request.reservation_id
            and owner_after.get("phase")
            in {"AUTHORIZED_PENDING", "MUTATION_IN_PROGRESS", "TERMINAL_CAPTURE_PENDING"}
        ):
            return {
                **saved,
                "reused": False,
                "owner_release": "RETAINED_FOR_RECONCILIATION",
                "owner_release_error": str(exc),
            }
        raise
    return {**saved, "reused": False}


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = cli.add_subparsers(dest="action", required=True)
    apply_parser = commands.add_parser("apply", allow_abbrev=False)
    for name in (
        "source-worktree",
        "expected-head",
        "expected-tree",
        "legacy-worktree",
        "legacy-head",
        "legacy-tree",
        "plan-file",
    ):
        apply_parser.add_argument("--" + name, required=True)
    apply_parser.add_argument("--takeover-stale", action="store_true")
    rollback_parser = commands.add_parser("rollback", allow_abbrev=False)
    for name in ("receipt-file", "legacy-worktree", "legacy-head", "legacy-tree"):
        rollback_parser.add_argument("--" + name, required=True)
    rollback_parser.add_argument("--takeover-stale", action="store_true")
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    selected = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(selected)
    try:
        version = cutover.control_version()
        if args.action == "rollback":
            receipt_path = Path(args.receipt_file)
            reservation_config = cutover.CutoverConfig(
                source_worktree=Path(args.legacy_worktree),
                receipt_path=receipt_path,
                strict_release_layout=True,
            )
            reservation_target: cutover.Record = {
                "source_worktree": args.legacy_worktree,
                "head": args.legacy_head,
                "tree": args.legacy_tree,
            }
        else:
            config = cutover.CutoverConfig(
                source_worktree=Path(args.source_worktree),
                expected_head=args.expected_head,
                expected_tree=args.expected_tree,
                durable_ref=f"refs/heads/runtime/b649/{args.expected_head}",
                strict_release_layout=True,
            )
            reservation_config = config
            reservation_target = {
                "source_worktree": args.source_worktree,
                "head": args.expected_head,
                "tree": args.expected_tree,
                "durable_ref": config.durable_ref,
            }
        prior_owner = cutover.inspect_control_owner(reservation_config)
        prior_execution_path = reservation_config.scheduler_root / (
            ROLLBACK_RECEIPT_NAME if args.action == "rollback" else RECEIPT_NAME
        )
        if prior_owner is not None and prior_owner.get("phase") != "RELEASED":
            reservation_id = text(prior_owner.get("reservation_id"))
            owner = cutover.acquire_control_owner(
                reservation_config,
                action=args.action,
                target=reservation_target,
                owner_kind="protected",
                reservation_id=reservation_id,
                version=version,
            )
            owner = cutover.resume_control_owner(
                reservation_config,
                reservation_id,
                version=version,
            )
        elif prior_owner is not None and os.path.lexists(prior_execution_path):
            reservation_id = text(prior_owner.get("reservation_id"))
            owner = prior_owner
        else:
            owner = cutover.acquire_control_owner(
                reservation_config,
                action=args.action,
                target=reservation_target,
                owner_kind="protected",
                version=version,
            )
            reservation_id = text(owner.get("reservation_id"))
        if args.action == "rollback":
            receipt_path = Path(args.receipt_file)
            managed, _, _ = cutover.read_control_json(receipt_path)
            new_source = record(
                record(record(managed.get("prestate")).get("new_source"))
            )
            config = cutover.CutoverConfig(
                source_worktree=Path(text(new_source.get("source_worktree"))),
                expected_head=text(new_source.get("head")),
                expected_tree=text(new_source.get("tree")),
                durable_ref=text(new_source.get("durable_ref")),
                receipt_path=receipt_path,
                strict_release_layout=True,
            )
            request = make_rollback_request(
                config,
                Path(args.legacy_worktree),
                args.legacy_head,
                args.legacy_tree,
                repository_claim_root(),
                takeover_stale=args.takeover_stale,
                reservation_id=reservation_id,
                owner_id_argument=False,
            )
        else:
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
                reservation_id=reservation_id,
                owner_id_argument=False,
            )
        if owner.get("phase") != "RELEASED":
            owner = cutover.bind_control_owner(
                reservation_config,
                reservation_id,
                action=request.action,
                target=request_owner_target(request),
                operation_id=text(request.identity.get("operation_id")),
                managed_receipt_sha256=cast(
                    str | None,
                    request.identity.get("managed_receipt_sha256"),
                ),
                version=version,
            )
        authorization = request_owner_authorization(request)
        if owner.get("phase") != "RELEASED":
            if owner.get("authorization") is None:
                print(
                    canonical(
                        {
                            "status": "AUTHORIZATION_PENDING",
                            "reservation_id": reservation_id,
                            "authorization": authorization,
                        }
                    )
                )
                return claims.REFUSED
            if owner.get("authorization") != authorization:
                raise ProtectedError("owner authorization is bound to different identities")
        if selected != request.owner_argv()[2:]:
            raise ProtectedError("use the canonical argument order shown by --help")
        result = launch(request)
        print(canonical(result))
        return (
            0
            if result["status"] in {"SUCCESS", ROLLBACK_SUCCESS}
            else int(cast(int, result.get("exit_code", 74))) or 74
        )
    except (OSError, ValueError, ProtectedError, cutover.CutoverError, claims.ClaimError) as exc:
        status = (
            ROLLBACK_INCOMPLETE
            if "args" in locals() and args.action == "rollback"
            else "INCOMPLETE_OR_AMBIGUOUS"
        )
        print(canonical({"status": status, "error": str(exc)}))
        return claims.UNVERIFIABLE


if __name__ == "__main__":
    raise SystemExit(main())
