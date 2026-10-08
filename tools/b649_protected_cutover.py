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
from collections.abc import Callable, Mapping, Sequence
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
APPLY_OPERATION_SCHEMA = "b649-protected-apply-operation-v1"
CONTROL_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = CONTROL_ROOT / "tools/b649_protected_cutover.py"
MANAGED = CONTROL_ROOT / "tools/b649_production_cutover.py"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_STREAM_BYTES = 32 * 1024
PRESTART_EXEC_FAILURE_CODES = frozenset({126, 127})
PRESTART_SUCCESSOR_RELEASE_SCHEMA = "b649-protected-prestart-successor-release-v1"
PRESTART_NOT_STARTED_RECONCILIATION_SCHEMA = (
    "b649-protected-prestart-not-started-reconciliation-v1"
)
PRESTART_NOT_STARTED_RELEASE_KIND = "PRESTART_NOT_STARTED_NO_MUTATION"
QUIESCENCE_SECONDS = 5.0
ROLLBACK_SUCCESS = "ROLLBACK_SUCCESS"
ROLLBACK_FAILED = "ROLLBACK_FAILED"
ROLLBACK_INCOMPLETE = "ROLLBACK_INCOMPLETE_OR_AMBIGUOUS"
type Record = dict[str, object]


class _Unset:
    """Marker distinguishing 'caller did not supply this' from an explicit None."""


_UNSET = _Unset()


class ProtectedError(RuntimeError):
    """An execution must not start or be automatically retried."""


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def apply_operation_id(
    reservation_id: str, plan_sha256: str, prior_execution_receipt_sha256: str | None
) -> str:
    """Derive the deterministic protected-apply operation identity.

    The same frozen reservation, plan and prior protected receipt must derive
    the same operation ID across a fresh process/session so that resume can
    rebind to the exact durable owner instead of minting an incompatible one.
    """
    return digest(
        {
            "schema": APPLY_OPERATION_SCHEMA,
            "reservation_id": reservation_id,
            "plan_sha256": plan_sha256,
            "prior_execution_receipt_sha256": prior_execution_receipt_sha256,
        }
    )[:32]


def _existing_receipt_sha256(path: Path) -> str | None:
    if not os.path.lexists(path):
        return None
    _, identity, _ = cutover.read_control_json(path)
    return identity.sha256


def _existing_prior_receipt_sha256(path: Path, reservation_id: str | None) -> str | None:
    """The prior protected receipt's file hash, excluding this reservation's own.

    A receipt already bound to the reservation being computed for is this
    operation's own in-flight or terminal result, not a distinct prior
    execution. Folding it into the operation-identity input would make the
    deterministic operation ID shift under its own output, breaking resume
    and reuse for the exact reservation that produced it.
    """
    if not os.path.lexists(path):
        return None
    value, sha256 = ReceiptFile(path).read_with_sha256()
    if value is None or sha256 is None:
        raise ProtectedError("prior protected execution receipt disappeared")
    try:
        owner_reservation = record(value.get("identity")).get("reservation_id")
    except checkpoint.Unverifiable:
        owner_reservation = None
    if reservation_id is not None and owner_reservation == reservation_id:
        prior_sha = record(value.get("identity")).get("prior_execution_receipt_sha256")
        return None if prior_sha is None else text(prior_sha)
    return sha256


def _find_archived_prior_receipt(path: Path, matches_sha: Callable[[str], bool]) -> Record | None:
    """Recover only sealed archive bytes matching the caller's frozen binding."""
    found: Record | None = None
    for index, archive in enumerate(path.parent.glob(f"{path.stem}.*.superseded.json")):
        if index >= 1024:
            raise ProtectedError("superseded receipt lookup exceeds bound")
        value, file_identity, _ = cutover.read_control_json(archive)
        if not matches_sha(file_identity.sha256):
            continue
        identity = record(value.get("identity"))
        execution_id = digest(identity)
        unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if (
            archive.name != f"{path.stem}.{execution_id}.superseded.json"
            or value.get("schema_version") != SCHEMA
            or value.get("receipt_sha256") != digest(unsigned)
            or value.get("execution_id") != execution_id
            or value.get("phase") != "COMPLETED"
            or value.get("status") not in {"SUCCESS", "FAILED"}
            or identity.get("execution_receipt_path") != str(path)
            or identity.get("task_key") != TASK_KEY
        ):
            raise ProtectedError("bound superseded receipt integrity differs")
        if found is not None:
            raise ProtectedError("bound superseded receipt is ambiguous")
        found = {"path": str(archive), "execution_id": execution_id, "sha256": file_identity.sha256}
    return found


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
    prior_execution_receipt_sha256: str | None = None

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
            "prior_execution_receipt_sha256": self.prior_execution_receipt_sha256,
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
    prior_execution_receipt_sha256: str | None | _Unset = _UNSET,
    managed_receipt_sha256: str | None | _Unset = _UNSET,
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
    resolved_prior_receipt_sha: str | None = (
        _existing_prior_receipt_sha256(config.scheduler_root / RECEIPT_NAME, reservation_id)
        if isinstance(prior_execution_receipt_sha256, _Unset)
        else prior_execution_receipt_sha256
    )
    if (
        isinstance(prior_execution_receipt_sha256, _Unset)
        and reservation_id is not None
        and not os.path.lexists(config.scheduler_root / RECEIPT_NAME)
    ):
        owner = cutover.inspect_control_owner(config)
        if owner is not None and owner.get("reservation_id") == reservation_id:
            bound_operation = owner.get("operation_id")
            if bound_operation is not None and bound_operation != apply_operation_id(
                reservation_id, identity.sha256, None
            ):
                evidence = _find_archived_prior_receipt(
                    config.scheduler_root / RECEIPT_NAME,
                    lambda sha: (
                        apply_operation_id(reservation_id, identity.sha256, sha) == bound_operation
                    ),
                )
                if evidence is None:
                    raise ProtectedError("bound operation has no matching prior receipt archive")
                resolved_prior_receipt_sha = text(evidence["sha256"])
    # A reservation that has already bound a managed-receipt snapshot must
    # keep it fixed: the managed receipt this very operation later writes
    # (on success) would otherwise be picked up as a "fresh" read on the next
    # resume/replay call, shifting the identity under its own output.
    resolved_managed_receipt_sha256: str | None = (
        (None if managed_identity is None else managed_identity.sha256)
        if isinstance(managed_receipt_sha256, _Unset)
        else managed_receipt_sha256
    )
    if operation_id is not None:
        selected_operation_id = operation_id
    elif reservation_id is not None:
        # Deterministic so that a fresh process resuming the same reservation
        # against the same plan and prior protected receipt rebinds to the
        # exact durable owner instead of minting an incompatible identity.
        selected_operation_id = apply_operation_id(
            reservation_id, identity.sha256, resolved_prior_receipt_sha
        )
    else:
        selected_operation_id = (
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
        resolved_managed_receipt_sha256,
        control_head,
        control_tree,
        owner_id_argument,
        resolved_prior_receipt_sha,
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
            *(["--takeover-stale"] if self.takeover_stale else []),
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

    def verify(self, processes: dict[int, checkpoint.Process], uid: int) -> Record:
        root = Path(__file__).resolve().parents[1]
        if (
            self.task_key != TASK_KEY
            or self.child_argv[:3] != (sys.executable, str(MANAGED), "rollback")
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
            *(["--takeover-stale"] if wire.get("takeover_stale") is True else []),
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

    def _verify_linked_archive_pair(
        self,
        directory: int,
        archive_name: str,
        source_metadata: os.stat_result,
        raw: bytes,
    ) -> None:
        try:
            descriptor = os.open(
                archive_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except OSError as exc:
            raise ProtectedError("interrupted receipt archive link is unverifiable") from exc
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            archive_raw = stream.read(MAX_RECEIPT_BYTES + 1)
            after = os.fstat(stream.fileno())
        source_now = os.stat(self.path.name, dir_fd=directory, follow_symlinks=False)
        archive_now = os.stat(archive_name, dir_fd=directory, follow_symlinks=False)

        def key(item: os.stat_result) -> tuple[int, ...]:
            return (item.st_dev, item.st_ino, item.st_mode, item.st_uid, item.st_nlink)

        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 2
            or key(before) != key(after)
            or key(after) != key(source_metadata)
            or key(after) != key(source_now)
            or key(after) != key(archive_now)
            or archive_raw != raw
        ):
            raise ProtectedError("interrupted receipt archive link is not an exact hard-link pair")

    def _read(self, directory: int, *, allow_linked_archive: bool = False) -> Record | None:
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
                or (before.st_nlink != 1 and not (allow_linked_archive and before.st_nlink == 2))
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
        if after.st_nlink == 2:
            if not allow_linked_archive:
                raise ProtectedError("receipt must be a single-link file")
            archive_name = f"{self.path.stem}.{value['execution_id']}.superseded.json"
            self._verify_linked_archive_pair(directory, archive_name, after, raw)
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
        if (
            action == "apply"
            and value["status"] == "SUCCESS"
            and (
                value.get("exit_code") != 0
                or value.get("child_exit_code") != 0
                or value.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
                or not isinstance(value.get("managed_receipt"), dict)
            )
        ):
            raise ProtectedError("success receipt lacks terminal evidence")
        if (
            action == "rollback"
            and value["status"] == ROLLBACK_SUCCESS
            and (
                value.get("exit_code") != 0
                or value.get("child_exit_code") != 0
                or value.get("result_status") not in {ROLLBACK_SUCCESS, "ALREADY_ROLLED_BACK"}
                or not isinstance(value.get("managed_receipt"), dict)
            )
        ):
            raise ProtectedError("rollback success receipt lacks terminal evidence")
        return value

    def read(self) -> Record | None:
        directory = self._directory()
        try:
            return self._read(directory, allow_linked_archive=True)
        finally:
            os.close(directory)

    def read_with_sha256(self) -> tuple[Record | None, str | None]:
        """Read a sealed receipt and its file hash, including a recoverable archive pair."""
        directory = self._directory()
        try:
            value = self._read(directory, allow_linked_archive=True)
            if value is None:
                return None, None
            descriptor = os.open(
                self.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as stream:
                before = os.fstat(stream.fileno())
                raw = stream.read(MAX_RECEIPT_BYTES + 1)
                after = os.fstat(stream.fileno())
            current = os.stat(self.path.name, dir_fd=directory, follow_symlinks=False)

            def key(item: os.stat_result) -> tuple[int, ...]:
                return (item.st_dev, item.st_ino, item.st_mode, item.st_uid, item.st_nlink)

            if (
                len(raw) > MAX_RECEIPT_BYTES
                or not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or key(before) != key(after)
                or key(after) != key(current)
                or record(json.loads(raw, object_pairs_hook=unique_object)) != value
            ):
                raise ProtectedError("receipt changed while computing its file hash")
            if after.st_nlink == 2:
                self._verify_linked_archive_pair(
                    directory,
                    f"{self.path.stem}.{value['execution_id']}.superseded.json",
                    after,
                    raw,
                )
            return value, hashlib.sha256(raw).hexdigest()
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

    def archive_to(self, destination_name: str, *, expected_sha256: str) -> None:
        """Move this receipt to a sibling name via link-then-unlink; never delete content.

        Idempotent when the destination already holds byte-identical content;
        refuses (leaving both paths untouched) when it exists with conflicting
        bytes, so a superseded receipt is always recoverable under its own
        identity-qualified name.
        """
        if (
            "/" in destination_name
            or destination_name in {".", ".."}
            or re.fullmatch(
                re.escape(self.path.stem) + r"\.[0-9a-f]{64}\.superseded\.json",
                destination_name,
            )
            is None
        ):
            raise ProtectedError("superseded receipt archive name is invalid")
        directory = self._directory()
        try:
            descriptor = os.open(
                self.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as stream:
                before = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink not in {1, 2}
                    or before.st_uid != os.getuid()
                    or stat.S_IMODE(before.st_mode) != 0o600
                ):
                    raise ProtectedError("prior receipt metadata is invalid")
                source_key = (before.st_dev, before.st_ino)
                raw = stream.read(MAX_RECEIPT_BYTES + 1)
                after = os.fstat(stream.fileno())
            source_now = os.stat(self.path.name, dir_fd=directory, follow_symlinks=False)
            if (after.st_dev, after.st_ino) != source_key or (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_uid,
                after.st_nlink,
            ) != (
                source_now.st_dev,
                source_now.st_ino,
                source_now.st_mode,
                source_now.st_uid,
                source_now.st_nlink,
            ):
                raise ProtectedError("prior receipt changed before archive")
            if len(raw) > MAX_RECEIPT_BYTES or hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ProtectedError("prior receipt changed before archive")
            try:
                existing_descriptor: int | None = os.open(
                    destination_name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=directory,
                )
            except FileNotFoundError:
                existing_descriptor = None
            if existing_descriptor is not None:
                with os.fdopen(existing_descriptor, "rb") as stream:
                    archive_stat = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(archive_stat.st_mode)
                        or archive_stat.st_nlink not in {1, 2}
                        or archive_stat.st_uid != os.getuid()
                        or stat.S_IMODE(archive_stat.st_mode) != 0o600
                    ):
                        raise ProtectedError("superseded receipt archive metadata is invalid")
                    existing_raw = stream.read(MAX_RECEIPT_BYTES + 1)
                if existing_raw != raw:
                    raise ProtectedError(
                        "superseded receipt archive path already exists with conflicting bytes"
                    )
                if archive_stat.st_nlink == 2:
                    self._verify_linked_archive_pair(directory, destination_name, after, raw)
                elif after.st_nlink != 1:
                    raise ProtectedError("prior receipt has unexpected archive links")
                os.unlink(self.path.name, dir_fd=directory)
            else:
                if after.st_nlink != 1:
                    raise ProtectedError("prior receipt has an unbound hard link")
                os.link(
                    self.path.name,
                    destination_name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
                os.unlink(self.path.name, dir_fd=directory)
            os.fsync(directory)
        finally:
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
        key: text(source.get(key)) for key in ("source_worktree", "head", "tree", "durable_ref")
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
        self.write_bytes(raw)
        return len(s)

    def write_bytes(self, raw: bytes) -> None:
        self.sha.update(raw)
        self.size += len(raw)
        self.prefix.extend(raw[: max(0, MAX_STREAM_BYTES - len(self.prefix))])

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
        self.superseded_receipt: Record | None = None
        self.process_stdout = BoundedStream()
        self.process_stderr = BoundedStream()

    def capture_process_output(self, stream: str, chunk: bytes) -> None:
        if stream == "stdout":
            self.process_stdout.write_bytes(chunk)
        elif stream == "stderr":
            self.process_stderr.write_bytes(chunk)
        else:
            raise ProtectedError("unknown child output stream")

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
                "superseded_execution_receipt": self.superseded_receipt,
            },
            expected=previous,
        )
        self.gated = not initial


def _prove_plan_old_live(
    config: cutover.CutoverConfig,
    plan: Record,
    runner: cutover.Runner,
) -> Record:
    prestate = record(plan.get("prestate"))
    sources = record(plan.get("source"))
    old_source = record(sources.get("old"))
    new_source = record(sources.get("new"))
    old_runtime = record(record(plan.get("runtime")).get("old"))
    new_runtime = record(record(plan.get("runtime")).get("new"))
    if (
        old_source.get("source_worktree") == new_source.get("source_worktree")
        or old_runtime == new_runtime
    ):
        raise ProtectedError("plan OLD and target identities are not distinct")
    cutover._validate_bound_source(  # pyright: ignore[reportPrivateUsage]
        config,
        old_source,
        runner,
        role="prestart-old",
        legacy_prestate=True,
    )
    old_plist_bytes = cutover._decode_bytes(  # pyright: ignore[reportPrivateUsage]
        prestate.get("old_plist_bytes_b64"), "old plist"
    )
    old_plist_identity = cutover._identity_from_record(  # pyright: ignore[reportPrivateUsage]
        prestate.get("old_plist_identity"), "old plist identity"
    )
    live_plist_identity, _ = cutover._assert_expected_plist(  # pyright: ignore[reportPrivateUsage]
        config.plist_path,
        old_plist_identity,
        expected_bytes=old_plist_bytes,
    )
    launch = cutover._assert_runtime_binding(  # pyright: ignore[reportPrivateUsage]
        config, runner, old_source, old_runtime
    )
    enabled = cutover._enabled_snapshot(config, runner)  # pyright: ignore[reportPrivateUsage]
    if launch.get("state") != prestate.get("old_launch_state") or enabled is not prestate.get(
        "old_enabled"
    ):
        raise ProtectedError("live launch state differs from plan OLD state")
    return {
        "source": old_source,
        "runtime": old_runtime,
        "plist_identity": live_plist_identity.to_dict(),
        "launch_state": launch.get("state"),
        "enabled": enabled,
        "target_source": new_source,
        "target_runtime": new_runtime,
    }


def _is_prestart_failure_candidate(staged: Record, exit_code: int) -> bool:
    """Recognize only a gated exec failure that never entered the child wrapper."""
    return (
        exit_code in PRESTART_EXEC_FAILURE_CODES
        and staged.get("phase") == "GATED"
        and "child_started_at" not in staged
        and "child_completed_at" not in staged
    )


def _prestart_failure_evidence(
    request: Request | RollbackRequest,
    store: ReceiptClaimStore,
    staged: Record,
    exit_code: int,
    *,
    runner: cutover.Runner,
) -> Record | None:
    if (
        not isinstance(request, Request)
        or not _is_prestart_failure_candidate(staged, exit_code)
        or store.owner_record is None
    ):
        return None
    claim_owner = store.owner_record
    child_pid = claim_owner.get("child_pid")
    if (
        type(child_pid) is not int
        or child_pid <= 0
        or staged.get("gated_child_pid") != child_pid
        or staged.get("supervisor_pid") != claim_owner.get("owner_pid")
        or record(staged.get("claim_owner")) != claim_owner
    ):
        raise ProtectedError("spawned child identity is not bound to the gated receipt")

    claim_state = claims.ClaimStore(request.claim_root).inspect(TASK_KEY)
    if claim_state.get("status") != "ABSENT":
        raise ProtectedError("ClaimStore is not absent after the child exit")

    if request.reservation_id is None:
        raise ProtectedError("pre-start failure has no durable reservation")
    owner = cutover.inspect_control_owner(request.config)
    expected_identity = {
        "reservation_id": request.reservation_id,
        "operation_id": request.operation_id,
        "managed_receipt_sha256": request.managed_receipt_sha256,
        "control_head": request.control_head,
        "control_tree": request.control_tree,
        "action": "apply",
        "target": request_owner_target(request),
    }
    live_control = cutover.control_version()
    if (
        owner is None
        or cutover._owner_identity(owner) != expected_identity  # pyright: ignore[reportPrivateUsage]
        or owner.get("owner_kind") != "protected"
        or owner.get("phase") != "AUTHORIZED_PENDING"
        or owner.get("mutation_started") is not False
        or owner.get("authorization") != expected_identity
        or (live_control.get("head"), live_control.get("tree"))
        != (request.control_head, request.control_tree)
    ):
        raise ProtectedError("durable owner does not prove an unstarted authorized operation")

    managed: Record | None = None
    managed_sha256: str | None = None
    if os.path.lexists(request.config.receipt_path):
        managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
        managed_sha256 = managed_identity.sha256
        if managed.get("operation_id") == request.operation_id:
            raise ProtectedError("managed receipt exists for the protected operation")
    if managed_sha256 != request.managed_receipt_sha256 or managed_sha256 != owner.get(
        "managed_receipt_sha256"
    ):
        raise ProtectedError("managed receipt changed after protected authorization")

    plan = request.load_plan()
    old_live = _prove_plan_old_live(request.config, plan, runner)
    managed_link_value: Record | None = None
    if managed is not None:
        managed_link_value = {
            "path": str(request.config.receipt_path),
            "sha256": managed_sha256,
            "status": managed.get("status"),
        }
    return {
        "classification": "PRESTART_FAILURE_NO_MUTATION",
        "child_spawned": True,
        "child_exited": True,
        "child_pid": child_pid,
        "child_exit_code": exit_code,
        "child_started": False,
        "owner_phase": "AUTHORIZED_PENDING",
        "owner_mutation_started": False,
        "claim_store_status": "ABSENT",
        "operation_managed_receipt_present": False,
        "unchanged_managed_receipt_sha256": managed_sha256,
        "managed_receipt": managed_link_value,
        "old_live_state": old_live,
    }


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


def managed_receipt_links(
    request: Request | RollbackRequest,
) -> tuple[Record | None, Record | None]:
    """Separate this operation's receipt link from its unchanged predecessor."""
    if not os.path.lexists(request.config.receipt_path):
        return None, None
    if not isinstance(request, Request):
        return managed_link(request), None

    try:
        value, identity, _ = cutover.read_control_json(request.config.receipt_path)
    except Exception:
        # The child result has already been captured. If the managed receipt
        # cannot be read, there is no safe link to record, but that must not
        # replace the result with a receipt-linking error.
        return None, None
    if value.get("operation_id") == request.operation_id:
        # Preserve strict identity validation for an actual operation receipt.
        return managed_link(request), None

    try:
        owner = cutover.inspect_control_owner(request.config)
        expected_owner = request_owner_authorization(request)
        unchanged_predecessor = (
            request.managed_receipt_sha256 is not None
            and identity.sha256 == request.managed_receipt_sha256
            and owner is not None
            and owner.get("owner_kind") == "protected"
            and owner.get("action") == "apply"
            and owner.get("phase") == "AUTHORIZED_PENDING"
            and owner.get("mutation_started") is False
            and owner.get("reservation_id") == request.reservation_id
            and owner.get("operation_id") == request.operation_id
            and owner.get("managed_receipt_sha256") == identity.sha256
            and owner.get("authorization") == expected_owner
            and cutover._owner_identity(owner)  # pyright: ignore[reportPrivateUsage]
            == expected_owner
        )
    except Exception:
        unchanged_predecessor = False
    if not unchanged_predecessor:
        # A different or unreadable receipt is not this operation's receipt
        # and is not proven predecessor evidence. Preserve the child terminal.
        return None, None
    return None, {
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
            prior_receipt_sha_value = identity.get("prior_execution_receipt_sha256")
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
                # Trust the wire snapshot: by the time this child re-validates,
                # a parent-side supersession may have already archived the
                # prior receipt slot, which would change what a fresh disk
                # read observes.
                prior_execution_receipt_sha256=(
                    None if prior_receipt_sha_value is None else text(prior_receipt_sha_value)
                ),
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
    link, unchanged_predecessor_link = managed_receipt_links(request)
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
            **(
                {"unchanged_predecessor_managed_receipt": unchanged_predecessor_link}
                if unchanged_predecessor_link is not None
                else {}
            ),
            "quiescence": snapshots,
        },
        expected=receipt,
    )
    print(output.evidence()["text"], end="")
    print(errors.evidence()["text"], end="", file=sys.stderr)
    return code


def supersede_prior_execution_receipt(
    request: Request | RollbackRequest,
    receipt_file: ReceiptFile,
    prior: Record,
) -> bool:
    """Archive a stale, sealed prior protected receipt so a new operation can proceed.

    Only ``Request`` (apply) carries the ``prior_execution_receipt_sha256``
    identity input the CTO-frozen contract requires; rollback's operation
    identity is receipt-derived and unchanged, so a differing rollback
    receipt is never eligible here. A managed receipt that is still SUCCESS
    is eligible only through ``_supersede_current_success_receipt``. Returns
    True when the prior receipt was archived; the caller must fail closed on
    False rather than reuse or delete anything.
    """
    if not isinstance(request, Request):
        return False
    # Prior receipt is not sealed/terminal.
    if prior.get("phase") != "COMPLETED" or prior.get("status") not in {"SUCCESS", "FAILED"}:
        return False
    prior_identity = record(prior.get("identity"))
    # Prior receipt is the current execution; nothing to supersede.
    if prior_identity == request.identity:
        return False
    prior_execution_id = prior.get("execution_id")
    # Prior receipt identity digest is invalid.
    if not isinstance(prior_execution_id, str) or digest(prior_identity) != prior_execution_id:
        return False
    owner = cutover.inspect_control_owner(request.config)
    if (
        owner is None
        or owner.get("phase") != "AUTHORIZED_PENDING"
        or owner.get("owner_kind") != "protected"
        or owner.get("authorization") != request_owner_authorization(request)
    ):
        return False
    # A claim is still owned or uncertain.
    if claims.ClaimStore(request.claim_root).inspect(TASK_KEY).get("status") != "ABSENT":
        return False
    bound_prior_sha = request.identity.get("prior_execution_receipt_sha256")
    # Prior receipt disappeared before supersession could bind its SHA.
    if not os.path.lexists(request.receipt_path):
        return False
    _, current_slot_sha256 = receipt_file.read_with_sha256()
    if current_slot_sha256 is None:
        return False
    # Prior receipt SHA is not part of the authorized operation identity.
    if bound_prior_sha != current_slot_sha256:
        return False
    managed_receipt_sha = cast(str | None, request.identity.get("managed_receipt_sha256"))
    # No terminal managed receipt is bound to the new operation.
    if managed_receipt_sha is None or not os.path.lexists(request.config.receipt_path):
        return False
    managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
    if managed.get("status") == "SUCCESS":
        return _supersede_current_success_receipt(
            request,
            receipt_file,
            prior,
            managed=managed,
            managed_sha256=managed_identity.sha256,
            slot_sha256=current_slot_sha256,
            owner=owner,
        )
    # Current managed receipt is not a verified terminal success.
    if (
        managed_identity.sha256 != managed_receipt_sha
        or managed.get("phase") != "COMPLETED"
        or managed.get("status") not in {ROLLBACK_SUCCESS, "RECOVERED"}
        or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("operation_id") != prior_identity.get("operation_id")
        or managed.get("plan_digest") != prior_identity.get("plan_digest")
    ):
        return False
    prior_link_value = prior.get("managed_receipt")
    prior_link = record(prior_link_value) if prior_link_value is not None else {}
    # Managed receipt evidence does not prove the prior execution is superseded.
    if (
        prior_link.get("path") != str(request.config.receipt_path)
        or re.fullmatch(r"[0-9a-f]{64}", str(prior_link.get("sha256"))) is None
        or prior_link.get("sha256") == managed_identity.sha256
    ):
        return False
    prior_config = replace(
        request.config,
        source_worktree=Path(text(prior_identity.get("source_worktree"))),
        expected_head=text(prior_identity.get("source_head")),
        expected_tree=text(prior_identity.get("source_tree")),
        durable_ref=text(record(prior_identity.get("target")).get("durable_ref")),
    )
    cutover.validate_protected_plan(prior_config, cutover.receipt_to_plan(prior_config, managed))
    destination_name = f"{request.receipt_path.stem}.{prior_execution_id}.superseded.json"
    receipt_file.archive_to(destination_name, expected_sha256=current_slot_sha256)
    return True


def _supersede_current_success_receipt(
    request: Request,
    receipt_file: ReceiptFile,
    prior: Record,
    *,
    managed: Record,
    managed_sha256: str,
    slot_sha256: str,
    owner: Record | None,
    archive: bool = True,
    require_saved_proof: bool = True,
) -> bool:
    """Archive a prior protected SUCCESS whose exact runtime is still the live state.

    This is the recurring upgrade shape: the prior protected apply and the
    managed receipt it produced are both terminal SUCCESS, and the authorized
    operation is the next link of the same chain -- its legacy side is exactly
    the prior target, which is still what launchd runs. A replay of the prior
    plan, a different legacy, unlinked managed evidence or drifted live state
    never retires the prior receipt. The caller has already bound the exact
    AUTHORIZED_PENDING owner, the absent claim and the prior receipt SHA.
    """
    prior_identity = record(prior.get("identity"))
    prior_target = record(prior_identity.get("target"))
    if require_saved_proof and not _saved_predecessor_proof_matches(
        request,
        prior,
        owner=owner,
        managed_sha256=managed_sha256,
        slot_sha256=slot_sha256,
    ):
        return False
    unsigned = {key: item for key, item in prior.items() if key != "receipt_sha256"}
    # Prior receipt is not a sealed, recoverable protected apply success.
    if (
        prior.get("schema_version") != SCHEMA
        or prior.get("receipt_sha256") != digest(unsigned)
        or prior.get("status") != "SUCCESS"
        or prior.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
        or type(prior.get("exit_code")) is not int
        or prior.get("exit_code") != 0
        or type(prior.get("child_exit_code")) is not int
        or prior.get("child_exit_code") != 0
        or prior_identity.get("action") != "apply"
        or prior_identity.get("task_key") != TASK_KEY
        or prior_identity.get("execution_receipt_path") != str(request.receipt_path)
    ):
        return False
    # A protected rollback exists or may still be continuing.
    if os.path.lexists(request.config.scheduler_root / ROLLBACK_RECEIPT_NAME):
        return False
    prior_link_value = prior.get("managed_receipt")
    prior_link = record(prior_link_value) if prior_link_value is not None else {}
    # The live managed receipt is not exactly the prior execution's own success.
    if (
        managed_sha256 != request.identity.get("managed_receipt_sha256")
        or managed.get("phase") != "COMPLETED"
        or managed.get("status") != "SUCCESS"
        or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("operation_id") != prior_identity.get("operation_id")
        or managed.get("plan_digest") != prior_identity.get("plan_digest")
        or prior_link.get("path") != str(request.config.receipt_path)
        or prior_link.get("sha256") != managed_sha256
        or prior_link.get("status") != "SUCCESS"
    ):
        return False
    # The new operation's legacy side is not exactly the prior target.
    if (str(request.legacy_worktree), request.legacy_head, request.legacy_tree) != (
        prior_target.get("source_worktree"),
        prior_target.get("head"),
        prior_target.get("tree"),
    ):
        return False
    after_source = record(record(managed.get("after")).get("source"))
    after = record(managed.get("after"))
    after_plist = record(after.get("plist"))
    after_launchd = record(after.get("launchd"))
    successor_plan = request.load_plan()
    successor_prestate = record(successor_plan.get("prestate"))
    old_source = record(successor_prestate.get("old_source"))
    old_plist_identity = record(successor_prestate.get("old_plist_identity"))
    # The new operation does not continue from exactly what the prior one left live.
    # Source records differ only in their side label: "new" after the prior apply,
    # "old" in the successor plan's prestate. The prior receipt may predate a reboot,
    # which renumbers st_dev, so its plist identity is compared without the device.
    if (
        after_source.get("role") != "new"
        or old_source != {**after_source, "role": "old"}
        or record(successor_prestate.get("old_runtime")) != record(after.get("runtime"))
        or not cutover.successor_plist_identity_matches(
            old_plist_identity, after_plist.get("identity")
        )
        or successor_prestate.get("old_launch_state") != after_launchd.get("state")
        or successor_prestate.get("old_enabled") is not after.get("enabled")
        or record(successor_prestate.get("old_binding")) != record(after_plist.get("binding"))
        or request.plan_digest == prior_identity.get("plan_digest")
        or request.operation_id == prior_identity.get("operation_id")
        or request.config.expected_head == prior_target.get("head")
    ):
        return False
    prior_config = replace(
        request.config,
        source_worktree=Path(text(prior_target.get("source_worktree"))),
        expected_head=text(prior_target.get("head")),
        expected_tree=text(prior_target.get("tree")),
        durable_ref=text(prior_target.get("durable_ref")),
    )
    cutover.validate_protected_plan(prior_config, cutover.receipt_to_plan(prior_config, managed))
    # Read-only; raises unless plist, loaded runtime and enabled state are exactly
    # the prior after-state and the live plist is exactly the plan's frozen OLD,
    # device included, so a reboot since the plan refuses before the archive.
    cutover.verify_completed_receipt_live(
        prior_config,
        managed,
        successor_old_plist_identity=old_plist_identity,
        runner=cutover.run_command,
    )
    prior_execution_id = text(prior.get("execution_id"))
    destination_name = f"{request.receipt_path.stem}.{prior_execution_id}.superseded.json"
    if archive:
        receipt_file.archive_to(destination_name, expected_sha256=slot_sha256)
    return True


def _saved_predecessor_proof_matches(
    request: Request,
    prior: Record,
    *,
    owner: Record | None,
    managed_sha256: str,
    slot_sha256: str,
) -> bool:
    if owner is None:
        return False
    value = owner.get("predecessor_release_evidence")
    proof = record(value) if value is not None else {}
    unsigned = {key: item for key, item in proof.items() if key != "evidence_sha256"}
    prior_identity = record(prior.get("identity"))
    release_value = proof.get("prior_release_evidence")
    release = record(release_value) if release_value is not None else {}
    expected_old_authorization = {
        "reservation_id": prior_identity.get("reservation_id"),
        "operation_id": prior_identity.get("operation_id"),
        "managed_receipt_sha256": prior_identity.get("managed_receipt_sha256"),
        "control_head": prior_identity.get("control_head"),
        "control_tree": prior_identity.get("control_tree"),
        "action": "apply",
        "target": record(prior_identity.get("target")),
    }
    return (
        set(proof)
        == {
            "schema",
            "prior_reservation_id",
            "prior_operation_id",
            "prior_authorization_sha256",
            "prior_release_evidence",
            "prior_protected_receipt_sha256",
            "prior_managed_receipt_sha256",
            "new_reservation_id",
            "new_operation_id",
            "evidence_sha256",
        }
        and proof.get("schema") == cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA
        and proof.get("evidence_sha256") == digest(unsigned)
        and proof.get("prior_reservation_id") == prior_identity.get("reservation_id")
        and proof.get("prior_operation_id") == prior_identity.get("operation_id")
        and proof.get("prior_authorization_sha256") == digest(expected_old_authorization)
        and proof.get("prior_protected_receipt_sha256") == slot_sha256
        and proof.get("prior_managed_receipt_sha256") == managed_sha256
        and proof.get("new_reservation_id") == request.reservation_id
        and proof.get("new_operation_id") == request.operation_id
        and owner.get("reservation_id") == request.reservation_id
        and owner.get("operation_id") == request.operation_id
        and owner.get("managed_receipt_sha256") == managed_sha256
        and owner.get("action") == "apply"
        and owner.get("owner_kind") == "protected"
        and owner.get("phase") == "AUTHORIZED_PENDING"
        and owner.get("authorization") == request_owner_authorization(request)
        and release.get("verified") is True
        and release.get("protected_receipt_sha256") == slot_sha256
        and release.get("managed_receipt_sha256") == managed_sha256
    )


def _prestart_reconciliation_record_path(
    config: cutover.CutoverConfig,
    reservation_id: str,
) -> Path:
    return config.scheduler_root / f"b649-prestart-reconciliation-{reservation_id}.json"


def _load_prestart_reconciliation(path: Path) -> tuple[Record, cutover.FileIdentity]:
    value, identity, _ = cutover._load_json(path)  # pyright: ignore[reportPrivateUsage]
    unsigned = {key: item for key, item in value.items() if key != "record_sha256"}
    expected_schema = {
        "PRESTART_FAILURE_NO_MUTATION": "b649-protected-prestart-failure-reconciliation-v1",
        PRESTART_NOT_STARTED_RELEASE_KIND: PRESTART_NOT_STARTED_RECONCILIATION_SCHEMA,
    }.get(text(value.get("reason")))
    if expected_schema is None or value.get("schema") != expected_schema or value.get(
        "record_sha256"
    ) != digest(unsigned):
        raise ProtectedError("pre-start reconciliation record seal is invalid")
    return value, identity


def _prestart_successor_release_record_path(
    config: cutover.CutoverConfig,
    reservation_id: str,
) -> Path:
    return config.scheduler_root / f"b649-prestart-successor-release-{reservation_id}.json"


def _is_prestart_successor_released_owner(owner: Record | None) -> bool:
    if owner is None or owner.get("phase") != "RELEASED":
        return False
    release_evidence = owner.get("release_evidence")
    return (
        isinstance(release_evidence, Mapping)
        and cast(Mapping[str, object], release_evidence).get("kind")
        == "PRESTART_SUCCESSOR_NO_MUTATION"
    )


def _prestart_successor_release_context(
    config: cutover.CutoverConfig,
    owner: Record | None,
    *,
    claim_root: Path,
    runner: cutover.Runner,
) -> Record | None:
    """Load a sealed no-mutation successor release and recover its v5 receipt link."""
    if owner is None or not _is_prestart_successor_released_owner(owner):
        return None
    release_evidence = record(owner.get("release_evidence"))

    live_owner_snapshot = cutover._read_control_owner(  # pyright: ignore[reportPrivateUsage]
        config
    )
    if live_owner_snapshot is None:
        raise ProtectedError("released successor owner is absent")
    live_owner, _owner_file_identity = live_owner_snapshot
    supplied_owner = {key: value for key, value in owner.items() if key != "worker_state"}
    if live_owner != supplied_owner:
        raise ProtectedError("released successor owner changed before predecessor recovery")
    owner_unsigned = cutover._owner_unsigned(live_owner)  # pyright: ignore[reportPrivateUsage]
    if (
        live_owner.get("schema") != cutover.CONTROL_OWNER_SCHEMA
        or live_owner.get("record_sha256") != cutover._sha256_json(owner_unsigned)  # pyright: ignore[reportPrivateUsage]
        or live_owner.get("owner_kind") != "protected"
        or live_owner.get("action") != "apply"
        or live_owner.get("phase") != "RELEASED"
        or live_owner.get("mutation_started") is not False
        or live_owner.get("authorization") != cutover._owner_identity(live_owner)  # pyright: ignore[reportPrivateUsage]
    ):
        raise ProtectedError("released successor owner integrity or identity is invalid")

    reservation_id = text(live_owner.get("reservation_id"))
    operation_id = text(live_owner.get("operation_id"))
    record_path = _prestart_successor_release_record_path(config, reservation_id)
    expected_evidence_keys = {
        "kind",
        "verified",
        "release_record_path",
        "release_record_sha256",
        "managed_receipt_sha256",
        "protected_receipt_absent_for_operation",
        "claim_absent",
        "mutation_started",
    }
    if (
        set(release_evidence) != expected_evidence_keys
        or release_evidence.get("verified") is not True
        or release_evidence.get("release_record_path") != str(record_path)
        or release_evidence.get("managed_receipt_sha256")
        != live_owner.get("managed_receipt_sha256")
        or release_evidence.get("protected_receipt_absent_for_operation") is not True
        or release_evidence.get("claim_absent") is not True
        or release_evidence.get("mutation_started") is not False
    ):
        raise ProtectedError("released successor evidence fields or owner binding are invalid")

    release_record, release_identity, _ = cutover.read_control_json(record_path)
    expected_record_keys = {
        "schema",
        "reservation_id",
        "operation_id",
        "original_control_identity",
        "recovery_control_identity",
        "owner_authorization",
        "plan_sha256",
        "plan_digest",
        "target",
        "managed_receipt_sha256",
        "protected_execution_receipt",
        "claim_absent",
        "rollback_receipt_absent",
        "mutation_started",
        "live_old_state",
        "record_sha256",
    }
    release_unsigned = {
        key: value for key, value in release_record.items() if key != "record_sha256"
    }
    expected_target = cutover._normalized_owner_target(  # pyright: ignore[reportPrivateUsage]
        live_owner.get("target")
    )
    owner_authorization = cutover._owner_identity(live_owner)  # pyright: ignore[reportPrivateUsage]
    original_control = {
        "head": live_owner.get("control_head"),
        "tree": live_owner.get("control_tree"),
    }
    recovery_control = record(release_record.get("recovery_control_identity"))
    if (
        set(release_record) != expected_record_keys
        or release_record.get("schema") != PRESTART_SUCCESSOR_RELEASE_SCHEMA
        or release_record.get("record_sha256") != digest(release_unsigned)
        or release_identity.sha256 != release_evidence.get("release_record_sha256")
        or release_record.get("reservation_id") != reservation_id
        or release_record.get("operation_id") != operation_id
        or release_record.get("original_control_identity") != original_control
        or set(recovery_control) != {"head", "tree"}
        or any(
            re.fullmatch(r"[0-9a-f]{40}", str(recovery_control.get(key))) is None
            for key in ("head", "tree")
        )
        or release_record.get("owner_authorization") != live_owner.get("authorization")
        or release_record.get("owner_authorization") != owner_authorization
        or re.fullmatch(r"[0-9a-f]{64}", str(release_record.get("plan_sha256"))) is None
        or re.fullmatch(r"[0-9a-f]{64}", str(release_record.get("plan_digest"))) is None
        or release_record.get("target") != expected_target
        or release_record.get("managed_receipt_sha256") != live_owner.get("managed_receipt_sha256")
        or release_record.get("managed_receipt_sha256")
        != release_evidence.get("managed_receipt_sha256")
        or release_record.get("claim_absent") is not True
        or release_record.get("rollback_receipt_absent") is not True
        or release_record.get("mutation_started") is not False
    ):
        raise ProtectedError("sealed successor release record is invalid or mismatched")

    managed, managed_identity, _ = cutover.read_control_json(config.receipt_path)
    if (
        managed_identity.sha256 != live_owner.get("managed_receipt_sha256")
        or managed_identity.sha256 != release_record.get("managed_receipt_sha256")
        or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("phase") != "COMPLETED"
        or managed.get("status") != "SUCCESS"
        or managed.get("operation_id") == operation_id
    ):
        raise ProtectedError("unchanged managed SUCCESS receipt differs from successor release")

    receipt_path = config.scheduler_root / RECEIPT_NAME
    snapshot = record(release_record.get("protected_execution_receipt"))
    if (
        set(snapshot)
        != {
            "path",
            "exists",
            "sha256",
            "execution_id",
            "reservation_id",
            "operation_id",
            "status",
        }
        or snapshot.get("path") != str(receipt_path)
        or snapshot.get("exists") is not True
        or not os.path.lexists(receipt_path)
    ):
        raise ProtectedError("saved protected predecessor snapshot is absent or malformed")
    stranded, stranded_identity, _ = cutover.read_control_json(receipt_path)
    stranded_sha = stranded_identity.sha256
    stranded_identity_record = record(stranded.get("identity"))
    if (
        stranded_identity_record.get("reservation_id") == reservation_id
        or stranded_identity_record.get("operation_id") == operation_id
    ):
        raise ProtectedError("released successor already has a protected execution receipt")
    if (
        stranded_sha != snapshot.get("sha256")
        or stranded.get("execution_id") != snapshot.get("execution_id")
        or stranded_identity_record.get("reservation_id") != snapshot.get("reservation_id")
        or stranded_identity_record.get("operation_id") != snapshot.get("operation_id")
        or stranded.get("status") != snapshot.get("status")
        or stranded_identity_record.get("reservation_id") == reservation_id
        or stranded_identity_record.get("operation_id") == operation_id
        or stranded_identity_record.get("action") != "apply"
    ):
        raise ProtectedError("protected receipt no longer matches the sealed release snapshot")
    stranded_owner_identity = {
        key: stranded_identity_record.get(key)
        for key in (
            "reservation_id",
            "operation_id",
            "managed_receipt_sha256",
            "control_head",
            "control_tree",
            "action",
            "target",
        )
    }
    stranded_success = stranded.get("status") == "SUCCESS"
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        stranded,
        path=receipt_path,
        bound_identity=stranded_owner_identity,
        successful=stranded_success,
    )

    if stranded_success:
        predecessor = stranded
        predecessor_sha = stranded_sha
        predecessor_path = receipt_path
    else:
        if stranded.get("status") != "FAILED":
            raise ProtectedError("saved protected receipt is not a successful or failed apply")
        predecessor_sha = text(stranded_identity_record.get("prior_execution_receipt_sha256"))
        if re.fullmatch(r"[0-9a-f]{64}", predecessor_sha) is None:
            raise ProtectedError("saved failed receipt has no exact predecessor SHA")
        archived = _find_archived_prior_receipt(
            receipt_path, lambda value: value == predecessor_sha
        )
        if archived is None:
            raise ProtectedError("sealed predecessor protected SUCCESS archive is absent")
        predecessor_path = Path(text(archived.get("path")))
        predecessor, predecessor_identity, _ = cutover.read_control_json(predecessor_path)
        if predecessor_identity.sha256 != predecessor_sha:
            raise ProtectedError("sealed predecessor protected receipt SHA drifted")

    predecessor_identity_record = record(predecessor.get("identity"))
    predecessor_target = cutover._normalized_owner_target(  # pyright: ignore[reportPrivateUsage]
        predecessor_identity_record.get("target")
    )
    old_state = record(release_record.get("live_old_state"))
    old_source = record(old_state.get("source"))
    target_source = record(old_state.get("target_source"))
    old_runtime = record(old_state.get("runtime"))
    target_runtime = record(old_state.get("target_runtime"))
    if (
        set(old_state)
        != {
            "source",
            "runtime",
            "plist_identity",
            "launch_state",
            "enabled",
            "target_source",
            "target_runtime",
        }
        or old_state.get("launch_state") != "LOADED"
        or old_state.get("enabled") is not True
        or old_source.get("role") != "old"
        or old_source.get("clean") is not True
        or any(old_source.get(key) != value for key, value in predecessor_target.items())
        or target_source.get("role") != "new"
        or target_source.get("clean") is not True
        or any(target_source.get(key) != value for key, value in expected_target.items())
        or target_source.get("runtime_tuple") != target_runtime
        or old_runtime == target_runtime
    ):
        raise ProtectedError("sealed OLD/target runtime identities are not distinct and exact")

    predecessor_link = record(predecessor.get("managed_receipt"))
    after = record(managed.get("after"))
    after_source = record(after.get("source"))
    after_runtime = record(after.get("runtime"))
    after_plist = record(after.get("plist"))
    after_launchd = record(after.get("launchd"))
    if (
        predecessor.get("status") != "SUCCESS"
        or predecessor.get("phase") != "COMPLETED"
        or predecessor.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
        or predecessor_link.get("path") != str(config.receipt_path)
        or predecessor_link.get("sha256") != managed_identity.sha256
        or predecessor_link.get("status") != "SUCCESS"
        or predecessor_identity_record.get("operation_id") != managed.get("operation_id")
        or predecessor_identity_record.get("plan_digest") != managed.get("plan_digest")
        or after_source.get("source_worktree") != predecessor_target.get("source_worktree")
        or after_source.get("head") != predecessor_target.get("head")
        or after_source.get("tree") != predecessor_target.get("tree")
        or old_state.get("runtime") != after_runtime
        or not cutover.successor_plist_identity_matches(
            old_state.get("plist_identity"), after_plist.get("identity")
        )
        or old_state.get("launch_state") != after_launchd.get("state")
        or old_state.get("enabled") is not after.get("enabled")
    ):
        raise ProtectedError("managed SUCCESS does not bind the sealed protected predecessor")

    target_config = replace(
        config,
        source_worktree=Path(text(expected_target.get("source_worktree"))),
        expected_head=text(expected_target.get("head")),
        expected_tree=text(expected_target.get("tree")),
        durable_ref=text(expected_target.get("durable_ref")),
        strict_release_layout=False,
    )
    current_target_source = cutover._validate_source(  # pyright: ignore[reportPrivateUsage]
        target_config,
        runner,
        role="new",
        expected_head=text(expected_target.get("head")),
        expected_tree=text(expected_target.get("tree")),
        expected_ref=text(expected_target.get("durable_ref")),
        strict_release_layout=False,
    )
    if (
        current_target_source != target_source
        or current_target_source.get("runtime_tuple") == old_runtime
    ):
        raise ProtectedError("released successor target is no longer the exact inactive target")

    if claims.ClaimStore(claim_root).inspect(TASK_KEY).get("status") != "ABSENT":
        raise ProtectedError("ClaimStore is not absent for the released successor")
    if os.path.lexists(config.scheduler_root / ROLLBACK_RECEIPT_NAME):
        raise ProtectedError("protected rollback receipt makes predecessor authority ambiguous")

    receipt_archive_glob = f"{receipt_path.stem}.*.superseded.json"
    for index, archive_path in enumerate(receipt_path.parent.glob(receipt_archive_glob)):
        if index >= 1024:
            raise ProtectedError("protected successor archive lookup exceeds bound")
        archived_value, _, _ = cutover.read_control_json(archive_path)
        archived_identity = record(archived_value.get("identity"))
        if (
            archived_identity.get("reservation_id") == reservation_id
            or archived_identity.get("operation_id") == operation_id
        ):
            raise ProtectedError("released successor already has a protected receipt archive")

    return {
        "owner": live_owner,
        "release_record": release_record,
        "managed": managed,
        "managed_sha256": managed_identity.sha256,
        "stranded": stranded,
        "predecessor": predecessor,
        "predecessor_sha256": predecessor_sha,
        "predecessor_path": str(predecessor_path),
        "predecessor_target": predecessor_target,
        "old_state": old_state,
    }


def _prestart_successor_predecessor_receipt_sha256(
    config: cutover.CutoverConfig,
    owner: Record | None,
    *,
    claim_root: Path,
    runner: cutover.Runner,
) -> str | None:
    context = _prestart_successor_release_context(
        config, owner, claim_root=claim_root, runner=runner
    )
    return None if context is None else text(context.get("predecessor_sha256"))


def _reconciled_predecessor_receipt_sha256(
    config: cutover.CutoverConfig,
    owner: Record | None,
) -> str | None:
    if owner is None or owner.get("phase") != "RELEASED":
        return None
    release = record(owner.get("release_evidence"))
    release_kind = release.get("kind")
    expected_reason = {
        "PRESTART_FAILURE_NO_MUTATION": "PRESTART_FAILURE_NO_MUTATION",
        PRESTART_NOT_STARTED_RELEASE_KIND: PRESTART_NOT_STARTED_RELEASE_KIND,
    }.get(text(release_kind))
    if expected_reason is None:
        return None
    stored_owner = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
    if stored_owner is None:
        raise ProtectedError("released reconciliation owner is absent")
    live_owner, _owner_file_identity = stored_owner
    supplied_owner = {key: value for key, value in owner.items() if key != "worker_state"}
    if live_owner != supplied_owner:
        raise ProtectedError("released reconciliation owner changed before predecessor recovery")
    owner_unsigned = cutover._owner_unsigned(live_owner)  # pyright: ignore[reportPrivateUsage]
    if (
        live_owner.get("schema") != cutover.CONTROL_OWNER_SCHEMA
        or live_owner.get("record_sha256")
        != cutover._sha256_json(owner_unsigned)  # pyright: ignore[reportPrivateUsage]
        or live_owner.get("owner_kind") != "protected"
        or live_owner.get("action") != "apply"
        or live_owner.get("phase") != "RELEASED"
        or live_owner.get("mutation_started") is not False
        or live_owner.get("authorization")
        != cutover._owner_identity(live_owner)  # pyright: ignore[reportPrivateUsage]
    ):
        raise ProtectedError("released reconciliation owner integrity or identity is invalid")
    owner = live_owner
    release = record(owner.get("release_evidence"))
    reservation_id = text(owner.get("reservation_id"))
    reconciliation_path = _prestart_reconciliation_record_path(config, reservation_id)
    if release.get("reconciliation_record_path") != str(reconciliation_path):
        raise ProtectedError("released pre-start owner points to a different reconciliation record")
    reconciliation, reconciliation_identity = _load_prestart_reconciliation(reconciliation_path)
    if (
        release.get("reconciliation_record_sha256") != reconciliation_identity.sha256
        or reconciliation.get("reservation_id") != reservation_id
        or reconciliation.get("operation_id") != owner.get("operation_id")
        or reconciliation.get("reason") != expected_reason
    ):
        raise ProtectedError("released pre-start owner does not bind its reconciliation record")
    if (
        release_kind == PRESTART_NOT_STARTED_RELEASE_KIND
        and reconciliation.get("owner_mutation_started") is not False
    ):
        raise ProtectedError(
            "released NOT_STARTED reconciliation does not prove owner mutation was not started"
        )
    predecessor = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
        owner.get("predecessor_release_evidence"), owner
    )
    predecessor_sha = text(predecessor.get("prior_protected_receipt_sha256"))
    if (
        reconciliation.get("predecessor_protected_receipt_sha256") != predecessor_sha
        or reconciliation.get("unchanged_managed_receipt_sha256")
        != predecessor.get("prior_managed_receipt_sha256")
        or release.get("predecessor_protected_receipt_sha256") != predecessor_sha
    ):
        raise ProtectedError("reconciled predecessor proof does not match the v5 receipt")
    cross_control_identity_valid = True
    if release_kind == PRESTART_NOT_STARTED_RELEASE_KIND:
        has_cross_control_identity = any(
            key in reconciliation
            for key in ("original_control_identity", "recovery_control_identity")
        )
        if has_cross_control_identity:
            original_control = record(reconciliation.get("original_control_identity"))
            recovery_control = record(reconciliation.get("recovery_control_identity"))
            owner_control = {
                "head": owner.get("control_head"),
                "tree": owner.get("control_tree"),
            }
            cross_control_identity_valid = (
                set(original_control) == {"head", "tree"}
                and original_control == owner_control
                and set(recovery_control) == {"head", "tree"}
                and all(
                    re.fullmatch(r"[0-9a-f]{40}", str(recovery_control.get(key))) is not None
                    for key in ("head", "tree")
                )
                and recovery_control != original_control
            )
    if release_kind == PRESTART_NOT_STARTED_RELEASE_KIND and (
        reconciliation.get("stranded_protected_receipt_sha256")
        != release.get("stranded_protected_receipt_sha256")
        or release.get("protected_receipt_sha256") != predecessor_sha
        or release.get("managed_receipt_sha256")
        != predecessor.get("prior_managed_receipt_sha256")
        or reconciliation.get("owner_authorization") != owner.get("authorization")
        or reconciliation.get("control_identity")
        != {
            "head": owner.get("control_head"),
            "tree": owner.get("control_tree"),
        }
        or not cross_control_identity_valid
    ):
        raise ProtectedError("released NOT_STARTED evidence differs from its sealed reconciliation")
    if release_kind == PRESTART_NOT_STARTED_RELEASE_KIND:
        stranded_sha = text(reconciliation.get("stranded_protected_receipt_sha256"))
        stranded_receipt_path = config.scheduler_root / RECEIPT_NAME
        if reconciliation.get("stranded_protected_receipt_path") != str(
            stranded_receipt_path
        ):
            raise ProtectedError("released NOT_STARTED evidence points to a different receipt slot")
        stranded_archive = Path(text(reconciliation.get("stranded_protected_receipt_archive")))
        if stranded_archive.parent != stranded_receipt_path.parent:
            raise ProtectedError("released NOT_STARTED archive is outside the receipt directory")
        stranded, stranded_identity, _ = cutover.read_control_json(stranded_archive)
        stranded_operation = record(stranded.get("identity"))
        stranded_unsigned = {
            key: value for key, value in stranded.items() if key != "receipt_sha256"
        }
        captured_terminal = (
            stranded.get("status") == "FAILED"
            and stranded.get("result_status") == "NOT_STARTED"
        )
        legacy_terminal = (
            stranded.get("status") == "INCOMPLETE_OR_AMBIGUOUS"
            and stranded.get("result_status") == "INCOMPLETE_OR_AMBIGUOUS"
        )
        if (
            stranded_identity.sha256 != stranded_sha
            or stranded_archive
            != stranded_receipt_path.with_name(
                f"{stranded_receipt_path.stem}.{stranded.get('execution_id')}.superseded.json"
            )
            or stranded.get("schema_version") != SCHEMA
            or stranded.get("task_key") != TASK_KEY
            or stranded.get("phase") != "COMPLETED"
            or stranded.get("receipt_sha256") != digest(stranded_unsigned)
            or stranded.get("execution_id") != digest(stranded_operation)
            or (stranded_operation.get("reservation_id"), stranded_operation.get("operation_id"))
            != (reservation_id, owner.get("operation_id"))
            or stranded_operation.get("action") != "apply"
            or stranded_operation.get("task_key") != TASK_KEY
            or stranded_operation.get("execution_receipt_path") != str(stranded_receipt_path)
            or stranded_operation.get("managed_receipt_path") != str(config.receipt_path)
            or stranded_operation.get("managed_receipt_sha256")
            != reconciliation.get("unchanged_managed_receipt_sha256")
            or stranded_operation.get("prior_execution_receipt_sha256") != predecessor_sha
            or stranded_operation.get("plan_sha256") != reconciliation.get("plan_sha256")
            or stranded_operation.get("plan_digest") != reconciliation.get("plan_digest")
            or stranded_operation.get("control_head") != owner.get("control_head")
            or stranded_operation.get("control_tree") != owner.get("control_tree")
            or stranded.get("managed_receipt") is not None
            or not (captured_terminal or legacy_terminal)
        ):
            raise ProtectedError("released NOT_STARTED archive differs from its sealed operation")
    return predecessor_sha


def _require_reconciled_success_evidence(
    request: Request,
    prior_owner: Record,
) -> Record:
    predecessor_sha = _reconciled_predecessor_receipt_sha256(request.config, prior_owner)
    if predecessor_sha is None or request.prior_execution_receipt_sha256 != predecessor_sha:
        raise ProtectedError("successor is not bound to the archived protected predecessor")
    predecessor_proof = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
        prior_owner.get("predecessor_release_evidence"), prior_owner
    )
    managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
    expected_managed_sha = text(predecessor_proof.get("prior_managed_receipt_sha256"))
    if (
        managed_identity.sha256 != expected_managed_sha
        or managed_identity.sha256 != request.managed_receipt_sha256
        or managed.get("status") != "SUCCESS"
        or managed.get("phase") != "COMPLETED"
        or managed.get("operation_id") != predecessor_proof.get("prior_operation_id")
    ):
        raise ProtectedError(
            "unchanged managed SUCCESS receipt differs from the archived predecessor"
        )
    archived = _find_archived_prior_receipt(
        request.receipt_path,
        lambda sha: sha == predecessor_sha,
    )
    if archived is None:
        raise ProtectedError("archived protected SUCCESS predecessor is absent")
    prior_path = Path(text(archived.get("path")))
    prior, archived_identity, _ = cutover.read_control_json(prior_path)
    if archived_identity.sha256 != predecessor_sha:
        raise ProtectedError("archived protected predecessor SHA changed")
    identity = record(prior.get("identity"))
    prior_target = record(identity.get("target"))
    prior_owner_identity = {
        "reservation_id": identity.get("reservation_id"),
        "operation_id": identity.get("operation_id"),
        "managed_receipt_sha256": identity.get("managed_receipt_sha256"),
        "control_head": identity.get("control_head"),
        "control_tree": identity.get("control_tree"),
        "action": "apply",
        "target": prior_target,
    }
    expected_prior_authorization = {
        key: item for key, item in prior_owner_identity.items() if key != "owner_kind"
    }
    if (
        prior.get("status") != "SUCCESS"
        or prior.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
        or identity.get("reservation_id") != predecessor_proof.get("prior_reservation_id")
        or identity.get("operation_id") != predecessor_proof.get("prior_operation_id")
        or identity.get("action") != "apply"
        or identity.get("execution_receipt_path") != str(request.receipt_path)
        or predecessor_proof.get("prior_authorization_sha256")
        != digest(expected_prior_authorization)
    ):
        raise ProtectedError("archived predecessor identity differs from its saved release proof")
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        prior,
        path=request.receipt_path,
        bound_identity=prior_owner_identity,
        successful=True,
    )
    prior_link = record(prior.get("managed_receipt"))
    if (
        managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("plan_digest") != identity.get("plan_digest")
        or managed.get("operation_id") != identity.get("operation_id")
        or prior_link.get("path") != str(request.config.receipt_path)
        or prior_link.get("sha256") != managed_identity.sha256
        or prior_link.get("status") != "SUCCESS"
    ):
        raise ProtectedError("managed SUCCESS receipt is not linked to the archived predecessor")
    if not _supersede_current_success_receipt(
        request,
        ReceiptFile(request.receipt_path),
        prior,
        managed=managed,
        managed_sha256=managed_identity.sha256,
        slot_sha256=predecessor_sha,
        owner=None,
        archive=False,
        require_saved_proof=False,
    ):
        raise ProtectedError("archived protected SUCCESS is not the live plan OLD predecessor")
    owner_authorization = record(prior_owner.get("authorization"))
    owner_release = record(prior_owner.get("release_evidence"))
    if (
        owner_release.get("kind")
        not in {"PRESTART_FAILURE_NO_MUTATION", PRESTART_NOT_STARTED_RELEASE_KIND}
        or owner_release.get("verified") is not True
        or owner_release.get("protected_receipt_sha256") != predecessor_sha
        or owner_release.get("managed_receipt_sha256") != expected_managed_sha
    ):
        raise ProtectedError("reconciled owner does not preserve the archived SUCCESS binding")
    unsigned = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": prior_owner["reservation_id"],
        "prior_operation_id": prior_owner["operation_id"],
        "prior_authorization_sha256": digest(owner_authorization),
        "prior_release_evidence": owner_release,
        "prior_protected_receipt_sha256": predecessor_sha,
        "prior_managed_receipt_sha256": expected_managed_sha,
        "new_reservation_id": request.reservation_id,
        "new_operation_id": request.operation_id,
    }
    return {**unsigned, "evidence_sha256": digest(unsigned)}


def _require_prestart_successor_success_evidence(
    request: Request,
    prior_owner: Record,
    *,
    runner: cutover.Runner | None,
) -> Record:
    selected_runner = cutover.run_command if runner is None else runner
    context = _prestart_successor_release_context(
        request.config,
        prior_owner,
        claim_root=request.claim_root,
        runner=selected_runner,
    )
    if context is None:
        raise ProtectedError("released owner has no validated pre-start successor evidence")
    predecessor = record(context.get("predecessor"))
    predecessor_identity = record(predecessor.get("identity"))
    predecessor_target = record(context.get("predecessor_target"))
    predecessor_sha = text(context.get("predecessor_sha256"))
    managed = record(context.get("managed"))
    managed_sha = text(context.get("managed_sha256"))
    released_owner = record(context.get("owner"))
    if (
        request.reservation_id is None
        or request.prior_execution_receipt_sha256 != predecessor_sha
        or request.managed_receipt_sha256 != managed_sha
        or (str(request.legacy_worktree), request.legacy_head, request.legacy_tree)
        != (
            predecessor_target.get("source_worktree"),
            predecessor_target.get("head"),
            predecessor_target.get("tree"),
        )
    ):
        raise ProtectedError("fresh successor is not bound to the exact released v5 predecessor")
    if not _supersede_current_success_receipt(
        request,
        ReceiptFile(request.receipt_path),
        predecessor,
        managed=managed,
        managed_sha256=managed_sha,
        slot_sha256=predecessor_sha,
        owner=None,
        archive=False,
        require_saved_proof=False,
    ):
        raise ProtectedError("released v5 predecessor is not eligible for a fresh successor")

    prior_release = record(released_owner.get("release_evidence"))
    predecessor_link = {
        "schema": cutover.PRESTART_SUCCESSOR_PREDECESSOR_SCHEMA,
        "release_record_sha256": prior_release.get("release_record_sha256"),
        "predecessor_reservation_id": predecessor_identity.get("reservation_id"),
        "predecessor_operation_id": predecessor_identity.get("operation_id"),
        "protected_receipt_sha256": predecessor_sha,
        "managed_receipt_sha256": managed_sha,
    }
    unsigned = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": released_owner.get("reservation_id"),
        "prior_operation_id": released_owner.get("operation_id"),
        "prior_authorization_sha256": digest(released_owner.get("authorization")),
        "prior_release_evidence": prior_release,
        "prior_protected_receipt_sha256": predecessor_sha,
        "prior_managed_receipt_sha256": managed_sha,
        "new_reservation_id": request.reservation_id,
        "new_operation_id": request.operation_id,
        "prestart_successor_predecessor_evidence": predecessor_link,
    }
    return {**unsigned, "evidence_sha256": digest(unsigned)}


def _released_v7_intermediate_context(
    config: cutover.CutoverConfig,
    observed_owner: Record,
) -> tuple[Record, cutover.FileIdentity, Record, cutover.FileIdentity]:
    owner_snapshot = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
    if owner_snapshot is None:
        raise ProtectedError("released v7 intermediate owner is absent")
    owner, owner_identity = owner_snapshot
    observed = {key: value for key, value in observed_owner.items() if key != "worker_state"}
    expected_target = {
        "source_worktree": cutover.RELEASED_INTERMEDIATE_TARGET_WORKTREE,
        "head": cutover.RELEASED_INTERMEDIATE_TARGET_HEAD,
        "tree": cutover.RELEASED_INTERMEDIATE_TARGET_TREE,
        "durable_ref": cutover.RELEASED_INTERMEDIATE_TARGET_REF,
    }
    release_path = config.scheduler_root / (
        f"b649-prestart-successor-release-{cutover.RELEASED_INTERMEDIATE_RESERVATION_ID}.json"
    )
    expected_release_evidence = {
        "claim_absent": True,
        "kind": "PRESTART_SUCCESSOR_NO_MUTATION",
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "mutation_started": False,
        "protected_receipt_absent_for_operation": True,
        "release_record_path": str(release_path),
        "release_record_sha256": cutover.RELEASED_INTERMEDIATE_RELEASE_RECORD_FILE_SHA256,
        "verified": True,
    }
    if (
        observed != owner
        or owner.get("schema") != cutover.CONTROL_OWNER_SCHEMA
        or owner.get("reservation_id") != cutover.RELEASED_INTERMEDIATE_RESERVATION_ID
        or owner.get("operation_id") != cutover.RELEASED_INTERMEDIATE_OPERATION_ID
        or owner.get("owner_kind") != "protected"
        or owner.get("action") != "apply"
        or owner.get("phase") != "RELEASED"
        or owner.get("control_head") != cutover.V7_SOURCE_HEAD
        or owner.get("control_tree") != cutover.V7_SOURCE_TREE
        or owner.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or owner.get("mutation_started") is not False
        or owner.get("authorization") != cutover._owner_identity(owner)  # pyright: ignore[reportPrivateUsage]
        or owner.get("target") != expected_target
        or owner.get("release_evidence") != expected_release_evidence
        or owner.get("predecessor_release_evidence") is not None
        or owner.get("record_sha256") != cutover.RELEASED_INTERMEDIATE_OWNER_RECORD_SHA256
        or owner_identity.sha256 != cutover.RELEASED_INTERMEDIATE_OWNER_FILE_SHA256
    ):
        raise ProtectedError("released owner is not the exact frozen v7 zero-mutation intermediate")

    release, release_identity, _ = cutover._load_json(release_path)  # pyright: ignore[reportPrivateUsage]
    release_unsigned = {key: value for key, value in release.items() if key != "record_sha256"}
    failed_receipt_path = config.scheduler_root / RECEIPT_NAME
    expected_failed_binding = {
        "execution_id": cutover.FAILED_TERMINAL_EXECUTION_ID,
        "exists": True,
        "operation_id": cutover.FAILED_TERMINAL_OPERATION_ID,
        "path": str(failed_receipt_path),
        "reservation_id": cutover.FAILED_TERMINAL_RESERVATION_ID,
        "sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        "status": "FAILED",
    }
    live_old = record(release.get("live_old_state"))
    live_source = record(live_old.get("source"))
    if (
        release_identity.sha256 != cutover.RELEASED_INTERMEDIATE_RELEASE_RECORD_FILE_SHA256
        or release.get("schema") != "b649-protected-prestart-successor-release-v1"
        or release.get("record_sha256") != cutover.RELEASED_INTERMEDIATE_RELEASE_RECORD_SHA256
        or release.get("record_sha256") != digest(release_unsigned)
        or release.get("reservation_id") != cutover.RELEASED_INTERMEDIATE_RESERVATION_ID
        or release.get("operation_id") != cutover.RELEASED_INTERMEDIATE_OPERATION_ID
        or release.get("owner_authorization") != owner.get("authorization")
        or release.get("target") != expected_target
        or release.get("original_control_identity")
        != {"head": cutover.V7_SOURCE_HEAD, "tree": cutover.V7_SOURCE_TREE}
        or release.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or release.get("mutation_started") is not False
        or release.get("claim_absent") is not True
        or release.get("rollback_receipt_absent") is not True
        or release.get("protected_execution_receipt") != expected_failed_binding
        or live_source.get("head") != cutover.V5_SOURCE_HEAD
        or live_source.get("tree") != cutover.V5_SOURCE_TREE
    ):
        raise ProtectedError("released v7 intermediate evidence seal or identity differs")
    return owner, owner_identity, release, release_identity


def _read_exact_failed_terminal_receipt(
    request: Request,
) -> tuple[Record, cutover.FileIdentity, Path, bool]:
    receipt_path = request.receipt_path
    archive_path = receipt_path.with_name(
        f"{receipt_path.stem}.{cutover.FAILED_TERMINAL_EXECUTION_ID}.superseded.json"
    )
    active_exists = os.path.lexists(receipt_path)
    archived_exists = os.path.lexists(archive_path)
    if active_exists == archived_exists:
        raise ProtectedError("exact v6 FAILED receipt must exist in one terminal location")
    selected_path = receipt_path if active_exists else archive_path
    failed, failed_file_identity, _ = cutover._load_json(selected_path)  # pyright: ignore[reportPrivateUsage]
    failed_identity = record(failed.get("identity"))
    failed_target = record(failed_identity.get("target"))
    bound_identity = {
        "reservation_id": cutover.FAILED_TERMINAL_RESERVATION_ID,
        "operation_id": cutover.FAILED_TERMINAL_OPERATION_ID,
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "control_head": failed_identity.get("control_head"),
        "control_tree": failed_identity.get("control_tree"),
        "action": "apply",
        "target": failed_target,
    }
    if (
        failed_file_identity.sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256
        or failed.get("execution_id") != cutover.FAILED_TERMINAL_EXECUTION_ID
        or failed.get("receipt_sha256")
        != digest({key: value for key, value in failed.items() if key != "receipt_sha256"})
        or failed.get("execution_id") != digest(failed_identity)
        or failed.get("schema_version") != SCHEMA
        or failed.get("task_key") != TASK_KEY
        or failed.get("status") != "FAILED"
        or failed.get("phase") != "COMPLETED"
        or type(failed.get("exit_code")) is not int
        or failed.get("exit_code") != 1
        or failed.get("result_status") != "INCOMPLETE_OR_AMBIGUOUS"
        or failed.get("child_exit_code") is not None
        or "child_started_at" in failed
        or "child_completed_at" in failed
        or failed_identity.get("reservation_id") != cutover.FAILED_TERMINAL_RESERVATION_ID
        or failed_identity.get("operation_id") != cutover.FAILED_TERMINAL_OPERATION_ID
        or failed_identity.get("action") != "apply"
        or failed_identity.get("execution_receipt_path") != str(receipt_path)
        or failed_identity.get("managed_receipt_path") != str(request.config.receipt_path)
        or failed_identity.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or failed_identity.get("prior_execution_receipt_sha256")
        != cutover.V5_PROTECTED_RECEIPT_SHA256
        or failed_identity.get("source_head") != cutover.FAILED_TERMINAL_SOURCE_HEAD
        or failed_identity.get("source_tree") != cutover.FAILED_TERMINAL_SOURCE_TREE
        or failed_identity.get("control_head") != cutover.FAILED_TERMINAL_CONTROL_HEAD
        or failed_identity.get("control_tree") != cutover.FAILED_TERMINAL_CONTROL_TREE
    ):
        raise ProtectedError("v6 FAILED receipt is not the exact frozen zero-mutation incident")
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        failed,
        path=receipt_path,
        bound_identity=bound_identity,
        successful=False,
    )
    failed_link = failed.get("managed_receipt")
    if isinstance(failed_link, dict) and cast(Record, failed_link).get("operation_id") == (
        cutover.FAILED_TERMINAL_OPERATION_ID
    ):
        raise ProtectedError("failed v6 operation has a protected managed receipt")
    return failed, failed_file_identity, archive_path, active_exists


def _require_reconstructed_v5_proof(
    request: Request,
) -> tuple[Record, Record, Record, Path]:
    archive = _find_archived_prior_receipt(
        request.receipt_path,
        lambda sha: sha == cutover.V5_PROTECTED_RECEIPT_SHA256,
    )
    if archive is None:
        raise ProtectedError("archived v5 protected SUCCESS predecessor is absent")
    archive_path = Path(text(archive.get("path")))
    expected_archive = request.receipt_path.with_name(
        f"{request.receipt_path.stem}.{cutover.V5_EXECUTION_ID}.superseded.json"
    )
    if archive_path != expected_archive:
        raise ProtectedError("v5 protected SUCCESS is not at its exact archive identity")
    v5, v5_identity, _ = cutover.read_control_json(archive_path)
    identity = record(v5.get("identity"))
    target = record(identity.get("target"))
    v5_owner_identity = {
        "reservation_id": identity.get("reservation_id"),
        "operation_id": identity.get("operation_id"),
        "managed_receipt_sha256": identity.get("managed_receipt_sha256"),
        "control_head": identity.get("control_head"),
        "control_tree": identity.get("control_tree"),
        "action": "apply",
        "target": target,
    }
    release = {
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "verified": True,
    }
    unsigned: Record = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": identity.get("reservation_id"),
        "prior_operation_id": identity.get("operation_id"),
        "prior_authorization_sha256": digest(v5_owner_identity),
        "prior_release_evidence": release,
        "prior_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "prior_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "new_reservation_id": cutover.FAILED_TERMINAL_RESERVATION_ID,
        "new_operation_id": cutover.FAILED_TERMINAL_OPERATION_ID,
    }
    proof = {**unsigned, "evidence_sha256": digest(unsigned)}
    managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
    link = record(v5.get("managed_receipt"))
    if (
        v5_identity.sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
        or v5.get("schema_version") != SCHEMA
        or v5.get("task_key") != TASK_KEY
        or v5.get("status") != "SUCCESS"
        or v5.get("phase") != "COMPLETED"
        or type(v5.get("exit_code")) is not int
        or v5.get("exit_code") != 0
        or v5.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
        or identity.get("reservation_id") != cutover.V5_RESERVATION_ID
        or identity.get("operation_id") != cutover.V5_OPERATION_ID
        or identity.get("action") != "apply"
        or identity.get("execution_receipt_path") != str(request.receipt_path)
        or identity.get("source_head") != cutover.V5_SOURCE_HEAD
        or identity.get("source_tree") != cutover.V5_SOURCE_TREE
        or v5.get("execution_id") != digest(identity)
        or proof.get("prior_authorization_sha256") != cutover.V5_AUTHORIZATION_SHA256
        or proof.get("evidence_sha256") != cutover.V5_RECONSTRUCTED_PREDECESSOR_PROOF_SHA256
        or request.prior_execution_receipt_sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
        or request.managed_receipt_sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
        or request.legacy_head != cutover.V5_SOURCE_HEAD
        or request.legacy_tree != cutover.V5_SOURCE_TREE
        or managed_identity.sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
        or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("status") != "SUCCESS"
        or managed.get("phase") != "COMPLETED"
        or managed.get("operation_id") != cutover.V5_OPERATION_ID
        or managed.get("plan_digest") != identity.get("plan_digest")
        or link.get("path") != str(request.config.receipt_path)
        or link.get("sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or link.get("status") != "SUCCESS"
    ):
        raise ProtectedError(
            "v5 protected and managed SUCCESS do not reconstruct frozen predecessor proof"
        )
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        v5,
        path=request.receipt_path,
        bound_identity=v5_owner_identity,
        successful=True,
    )
    return proof, v5, managed, archive_path


def _recover_v2_successor_request(
    config: cutover.CutoverConfig,
    legacy_worktree: Path,
    legacy_head: str,
    legacy_tree: str,
    plan_file: Path,
    claim_root: Path,
    prior_owner: Record | None,
    *,
    prior_execution_receipt_sha256: str | None | _Unset,
    takeover_stale: bool = False,
) -> Request | None:
    """Rebuild only the successor identity sealed by matching v2 retirement evidence.

    This path is read-only. It validates the durable transition and all of its
    historical inputs before constructing a request with the persisted
    reservation; callers never supply either recovered identity.
    """
    retirement_path = config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    if not os.path.lexists(retirement_path):
        return None
    retirement, _, _ = cutover._load_json(retirement_path)  # pyright: ignore[reportPrivateUsage]
    cutover._validate_failed_terminal_retirement_v2_evidence(  # pyright: ignore[reportPrivateUsage]
        retirement
    )
    candidate_reservation_id = text(retirement.get("candidate_reservation_id"))
    candidate_operation_id = text(retirement.get("candidate_operation_id"))
    if (
        prior_owner is not None
        and prior_owner.get("reservation_id") == candidate_reservation_id
        and prior_owner.get("operation_id") == candidate_operation_id
    ):
        predecessor = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
            prior_owner.get("predecessor_release_evidence"),
            prior_owner,
        )
        if (
            prior_owner.get("owner_kind") == "protected"
            and prior_owner.get("action") == "apply"
            and prior_owner.get("managed_receipt_sha256") == cutover.V5_MANAGED_RECEIPT_SHA256
            and prior_owner.get("target") == retirement.get("candidate_target")
            and predecessor.get("new_reservation_id") == candidate_reservation_id
            and predecessor.get("new_operation_id") == candidate_operation_id
            and predecessor.get("retired_failed_terminal_evidence") == retirement
        ):
            if prior_owner.get("phase") == "RELEASED":
                # The exact successor already completed; normal handling may
                # now consider a later transition from its released owner.
                return None
            if (
                prior_owner.get("phase")
                not in {
                    "AUTHORIZATION_PENDING",
                    "AUTHORIZED_PENDING",
                    "MUTATION_IN_PROGRESS",
                    "TERMINAL_CAPTURE_PENDING",
                }
                or prior_execution_receipt_sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
                or (legacy_head, legacy_tree) != (cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
                or retirement.get("claim_root") != str(claim_root)
            ):
                raise ProtectedError(
                    "v2 retirement successor owner is outside its exact pending retry"
                )
            expected_target = {
                "source_worktree": str(config.source_worktree),
                "head": config.expected_head,
                "tree": config.expected_tree,
                "durable_ref": config.durable_ref,
            }
            if retirement.get("candidate_target") != expected_target:
                raise ProtectedError(
                    "v2 retirement evidence belongs to a different successor target"
                )
            request = make_request(
                config,
                legacy_worktree,
                legacy_head,
                legacy_tree,
                plan_file,
                claim_root,
                takeover_stale=takeover_stale,
                reservation_id=candidate_reservation_id,
                prior_execution_receipt_sha256=prior_execution_receipt_sha256,
                managed_receipt_sha256=cast(
                    str | None,
                    prior_owner.get("managed_receipt_sha256"),
                ),
            )
            if (
                request.plan_sha256 != retirement.get("candidate_plan_sha256")
                or request.managed_receipt_sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
                or request.operation_id != candidate_operation_id
                or request_owner_target(request) != expected_target
                or (request.control_head, request.control_tree)
                != (prior_owner.get("control_head"), prior_owner.get("control_tree"))
            ):
                raise ProtectedError(
                    "v2 retirement successor identity does not match its pending owner"
                )
            _failed, _failed_identity, failed_archive_path, failed_is_active = (
                _read_exact_failed_terminal_receipt(request)
            )
            if failed_is_active or str(failed_archive_path) != retirement.get("archive_path"):
                raise ProtectedError("v2 retirement failed receipt archive changed")
            predecessor_proof, _v5, _managed, v5_archive_path = _require_reconstructed_v5_proof(
                request
            )
            if predecessor_proof != retirement.get("v5_predecessor_release_evidence") or str(
                v5_archive_path
            ) != retirement.get("v5_protected_receipt_archive_path"):
                raise ProtectedError("v2 retirement v5 predecessor evidence changed")
            release_path = Path(text(retirement.get("intermediate_release_record_path")))
            release, release_identity, _ = cutover._load_json(  # pyright: ignore[reportPrivateUsage]
                release_path
            )
            if (
                str(release_path) != retirement.get("intermediate_release_record_path")
                or release != retirement.get("intermediate_release_record")
                or release_identity.sha256
                != retirement.get("intermediate_release_record_file_sha256")
            ):
                raise ProtectedError("v2 retirement intermediate release evidence changed")
            plan, _, _ = cutover.read_control_json(plan_file)
            plan_source = record(plan.get("source"))
            plan_old = record(plan_source.get("old"))
            plan_new = record(plan_source.get("new"))
            if (
                plan_old.get("head") != cutover.V5_SOURCE_HEAD
                or plan_old.get("tree") != cutover.V5_SOURCE_TREE
                or plan_new.get("head") != cutover.V7_SOURCE_HEAD
                or plan_new.get("tree") != cutover.V7_SOURCE_TREE
                or plan_new.get("source_worktree") != str(config.source_worktree)
            ):
                raise ProtectedError(
                    "v2 retirement evidence belongs to a different successor transition"
                )
            if (
                prior_owner.get("phase") in {"AUTHORIZATION_PENDING", "AUTHORIZED_PENDING"}
                and claims.ClaimStore(claim_root).inspect(TASK_KEY).get("status") != "ABSENT"
            ):
                raise ProtectedError("ClaimStore changed before the v2 successor started mutation")
            # This durable owner has consumed the sealed identity. Its exact
            # inputs have been checked before normal resume can update the owner.
            return None
        raise ProtectedError("v2 retirement evidence conflicts with its current successor owner")

    if (
        prior_owner is None
        or prior_owner.get("reservation_id") != cutover.RELEASED_INTERMEDIATE_RESERVATION_ID
        or prior_owner.get("operation_id") != cutover.RELEASED_INTERMEDIATE_OPERATION_ID
        or prior_execution_receipt_sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
        or (legacy_head, legacy_tree) != (cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
    ):
        raise ProtectedError(
            "v2 retirement evidence is outside the exact released-intermediate retry"
        )

    if retirement.get("claim_root") != str(claim_root):
        raise ProtectedError("v2 retirement evidence belongs to a different ClaimStore")
    expected_target = {
        "source_worktree": str(config.source_worktree),
        "head": config.expected_head,
        "tree": config.expected_tree,
        "durable_ref": config.durable_ref,
    }
    if retirement.get("candidate_target") != expected_target:
        raise ProtectedError("v2 retirement evidence belongs to a different successor target")
    plan, plan_identity, _ = cutover.read_control_json(plan_file)
    if plan_identity.sha256 != retirement.get("candidate_plan_sha256"):
        raise ProtectedError("v2 retirement evidence belongs to a different successor plan")
    plan_source = record(plan.get("source"))
    plan_old = record(plan_source.get("old"))
    plan_new = record(plan_source.get("new"))
    if (
        plan_old.get("head") != cutover.V5_SOURCE_HEAD
        or plan_old.get("tree") != cutover.V5_SOURCE_TREE
        or plan_new.get("head") != cutover.V7_SOURCE_HEAD
        or plan_new.get("tree") != cutover.V7_SOURCE_TREE
        or plan_new.get("source_worktree") != str(config.source_worktree)
    ):
        raise ProtectedError("v2 retirement evidence belongs to a different successor transition")

    cutover._verify_failed_terminal_retirement_v2_inputs(  # pyright: ignore[reportPrivateUsage]
        config,
        retirement,
    )
    owner, owner_identity, release, release_identity = _released_v7_intermediate_context(
        config, prior_owner
    )
    if (
        retirement.get("intermediate_owner_record") != owner
        or retirement.get("intermediate_owner_file_sha256") != owner_identity.sha256
        or retirement.get("intermediate_release_record") != release
        or retirement.get("intermediate_release_record_file_sha256") != release_identity.sha256
    ):
        raise ProtectedError("v2 retirement evidence does not match the released control lineage")

    request = make_request(
        config,
        legacy_worktree,
        legacy_head,
        legacy_tree,
        plan_file,
        claim_root,
        takeover_stale=takeover_stale,
        reservation_id=candidate_reservation_id,
        prior_execution_receipt_sha256=prior_execution_receipt_sha256,
    )
    if (
        request.plan_sha256 != retirement.get("candidate_plan_sha256")
        or request.managed_receipt_sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
        or request.operation_id != candidate_operation_id
        or request_owner_target(request) != expected_target
    ):
        raise ProtectedError("v2 retirement successor identity does not match its sealed inputs")
    return request


def _failed_terminal_predecessor_receipt_sha256(
    owner: Record | None,
    config: cutover.CutoverConfig | None = None,
) -> str | None:
    if owner is None:
        return None
    intermediate_signature = (
        owner.get("reservation_id") == cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
        owner.get("operation_id") == cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
    )
    if any(intermediate_signature) and not all(intermediate_signature):
        raise ProtectedError("released v7 intermediate owner identity differs")
    if all(intermediate_signature):
        expected_target = {
            "source_worktree": cutover.RELEASED_INTERMEDIATE_TARGET_WORKTREE,
            "head": cutover.RELEASED_INTERMEDIATE_TARGET_HEAD,
            "tree": cutover.RELEASED_INTERMEDIATE_TARGET_TREE,
            "durable_ref": cutover.RELEASED_INTERMEDIATE_TARGET_REF,
        }
        release_value = owner.get("release_evidence")
        release_evidence = cast(Record, release_value) if isinstance(release_value, dict) else {}
        intermediate_owner_candidate = (
            owner.get("target") == expected_target
            or owner.get("record_sha256") == cutover.RELEASED_INTERMEDIATE_OWNER_RECORD_SHA256
            or release_evidence.get("release_record_sha256")
            == cutover.RELEASED_INTERMEDIATE_RELEASE_RECORD_FILE_SHA256
        )
        if intermediate_owner_candidate:
            if config is None:
                raise ProtectedError("exact intermediate recognition requires its protected config")
            _released_v7_intermediate_context(config, owner)
            return cutover.V5_PROTECTED_RECEIPT_SHA256
    matches = (
        owner.get("reservation_id") == cutover.FAILED_TERMINAL_RESERVATION_ID,
        owner.get("operation_id") == cutover.FAILED_TERMINAL_OPERATION_ID,
    )
    if any(matches) and not all(matches):
        raise ProtectedError("exact failed terminal owner identity differs")
    if not all(matches):
        return None
    release = record(owner.get("release_evidence"))
    if release.get("kind") == "PRESTART_FAILURE_NO_MUTATION":
        return None
    if release != {
        "protected_receipt_sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        "managed_receipt_unchanged": True,
        "verified": True,
    }:
        raise ProtectedError(
            "failed terminal owner release evidence differs from the frozen incident"
        )
    if owner.get("phase") != "RELEASED" or owner.get("mutation_started") is not False:
        raise ProtectedError("failed terminal owner is not a released zero-mutation incident")
    predecessor = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
        owner.get("predecessor_release_evidence"), owner
    )
    if (
        predecessor.get("prior_protected_receipt_sha256") != cutover.V5_PROTECTED_RECEIPT_SHA256
        or predecessor.get("prior_managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
    ):
        raise ProtectedError("failed terminal owner does not preserve the exact v5 predecessor")
    return text(predecessor.get("prior_protected_receipt_sha256"))


def _require_released_v7_intermediate_successor_evidence(
    request: Request,
    prior_owner: Record,
    *,
    runner: cutover.Runner | None,
) -> Record:
    selected_runner = cutover.run_command if runner is None else runner
    if (
        request.reservation_id is None
        or request.reservation_id
        in {
            cutover.V5_RESERVATION_ID,
            cutover.FAILED_TERMINAL_RESERVATION_ID,
            cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
        }
        or request.operation_id
        in {
            cutover.V5_OPERATION_ID,
            cutover.FAILED_TERMINAL_OPERATION_ID,
            cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
        }
        or re.fullmatch(r"[0-9a-f]{32}", request.operation_id) is None
        or (request.config.expected_head, request.config.expected_tree)
        != (cutover.V7_SOURCE_HEAD, cutover.V7_SOURCE_TREE)
        or request.prior_execution_receipt_sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
    ):
        raise ProtectedError(
            "released intermediate permits only a fresh exact canonical v7 successor"
        )

    owner, owner_identity, release, release_identity = _released_v7_intermediate_context(
        request.config, prior_owner
    )
    _failed, _failed_identity, failed_archive_path, active_failed = (
        _read_exact_failed_terminal_receipt(request)
    )
    # The intermediate operation itself never wrote a protected execution receipt.
    if os.path.lexists(request.receipt_path) and not active_failed:
        raise ProtectedError("intermediate execution receipt is present in the protected slot")
    for archived_path in request.config.scheduler_root.glob(
        f"{request.receipt_path.stem}.*.superseded.json"
    ):
        archived, _, _ = cutover._load_json(archived_path)  # pyright: ignore[reportPrivateUsage]
        archived_identity = record(archived.get("identity"))
        if (
            archived_identity.get("reservation_id") == cutover.RELEASED_INTERMEDIATE_RESERVATION_ID
            or archived_identity.get("operation_id") == cutover.RELEASED_INTERMEDIATE_OPERATION_ID
        ):
            raise ProtectedError(
                "released intermediate unexpectedly has a protected execution receipt"
            )

    v5_proof, v5_receipt, managed, v5_archive_path = _require_reconstructed_v5_proof(request)
    if os.path.lexists(request.config.scheduler_root / ROLLBACK_RECEIPT_NAME):
        raise ProtectedError("rollback receipt makes the v5 predecessor history ambiguous")
    claim_state = claims.ClaimStore(request.claim_root).inspect(TASK_KEY)
    if claim_state.get("status") != "ABSENT":
        raise ProtectedError("ClaimStore is not absent for the v5 successor")

    candidate_plan = request.load_plan()
    plan_source = record(candidate_plan.get("source"))
    plan_old = record(plan_source.get("old"))
    plan_new = record(plan_source.get("new"))
    if (
        plan_old.get("head") != cutover.V5_SOURCE_HEAD
        or plan_old.get("tree") != cutover.V5_SOURCE_TREE
        or plan_new.get("head") != cutover.V7_SOURCE_HEAD
        or plan_new.get("tree") != cutover.V7_SOURCE_TREE
        or plan_new.get("clean") is not True
        or plan_new.get("source_worktree") != str(request.config.source_worktree)
        or request.plan_digest == record(v5_receipt.get("identity")).get("plan_digest")
        or request.operation_id == record(v5_receipt.get("identity")).get("operation_id")
        or (request.legacy_head, request.legacy_tree)
        != (cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
    ):
        raise ProtectedError("candidate plan does not target canonical v7 from exact v5 OLD")

    old_live = _prove_plan_old_live(request.config, candidate_plan, selected_runner)
    if (
        record(old_live.get("source")) != plan_old
        or record(old_live.get("target_source")) == plan_old
    ):
        raise ProtectedError(
            "live state does not prove exact v5 OLD and inactive canonical v7 target"
        )
    v5_identity = record(v5_receipt.get("identity"))
    v5_target = record(v5_identity.get("target"))
    v5_config = replace(
        request.config,
        source_worktree=Path(text(v5_target.get("source_worktree"))),
        expected_head=text(v5_target.get("head")),
        expected_tree=text(v5_target.get("tree")),
        durable_ref=text(v5_target.get("durable_ref")),
    )
    cutover.validate_protected_plan(v5_config, cutover.receipt_to_plan(v5_config, managed))
    cutover.verify_completed_receipt_live(
        v5_config,
        managed,
        successor_old_plist_identity=record(
            record(candidate_plan.get("prestate")).get("old_plist_identity")
        ),
        runner=selected_runner,
    )

    retirement_path = request.config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    unsigned_retirement: Record = {
        "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
        "receipt_path": str(request.receipt_path),
        "archive_path": str(failed_archive_path),
        "execution_id": cutover.FAILED_TERMINAL_EXECUTION_ID,
        "receipt_sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        "reservation_id": cutover.FAILED_TERMINAL_RESERVATION_ID,
        "operation_id": cutover.FAILED_TERMINAL_OPERATION_ID,
        "status": "FAILED",
        "phase": "COMPLETED",
        "exit_code": 1,
        "result_status": "INCOMPLETE_OR_AMBIGUOUS",
        "child_started": False,
        "child_completed": False,
        "mutation_started": False,
        "zero_mutation": True,
        "v5_predecessor_release_evidence": v5_proof,
        "v5_predecessor_proof_sha256": cutover.V5_RECONSTRUCTED_PREDECESSOR_PROOF_SHA256,
        "v5_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "v5_protected_receipt_archive_path": str(v5_archive_path),
        "v5_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "v5_managed_receipt_path": str(request.config.receipt_path),
        "v5_source_head": cutover.V5_SOURCE_HEAD,
        "v5_source_tree": cutover.V5_SOURCE_TREE,
        "v5_live_state": {"verified": True, **old_live},
        "intermediate_owner_record": owner,
        "intermediate_owner_file_sha256": owner_identity.sha256,
        "intermediate_release_record_path": str(
            request.config.scheduler_root
            / f"b649-prestart-successor-release-{cutover.RELEASED_INTERMEDIATE_RESERVATION_ID}.json"
        ),
        "intermediate_release_record_file_sha256": release_identity.sha256,
        "intermediate_release_record": release,
        "intermediate_reservation_id": cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
        "intermediate_operation_id": cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
        "intermediate_target": record(owner.get("target")),
        "candidate_plan_sha256": request.plan_sha256,
        "candidate_reservation_id": request.reservation_id,
        "candidate_operation_id": request.operation_id,
        "candidate_target": request_owner_target(request),
        "candidate_method": cutover.V7_TARGET_METHOD,
        "candidate_k20_sha256": cutover.V7_TARGET_K20_SHA256,
        "claim_root": str(request.claim_root),
        "claim_store_status": "ABSENT",
        "rollback_receipt_absent": True,
        "intermediate_execution_receipt_absent": True,
        "failed_operation_managed_receipt_present": False,
        "archive_status": "ARCHIVED_UNCHANGED",
    }
    retirement = {
        **unsigned_retirement,
        "record_sha256": digest(unsigned_retirement),
    }
    cutover._validate_failed_terminal_retirement_v2_evidence(  # pyright: ignore[reportPrivateUsage]
        retirement
    )

    stored_retirement: Record | None = None
    if os.path.lexists(retirement_path):
        stored_retirement, _, _ = cutover._load_json(retirement_path)  # pyright: ignore[reportPrivateUsage]
        if stored_retirement != retirement:
            raise ProtectedError("v2 retirement evidence exists with conflicting successor proof")
        if active_failed:
            raise ProtectedError("v2 retirement evidence exists before exact v6 receipt archival")

    # Repeat OLD proof at the write boundary. The archive is the first durable
    # mutation; on retry, the evidence file or owner CAS is the first mutation.
    repeated_live = _prove_plan_old_live(request.config, candidate_plan, selected_runner)
    if repeated_live != old_live:
        raise ProtectedError("live v5 OLD state changed immediately before retirement write")
    cutover.verify_completed_receipt_live(
        v5_config,
        managed,
        successor_old_plist_identity=record(
            record(candidate_plan.get("prestate")).get("old_plist_identity")
        ),
        runner=selected_runner,
    )
    latest_owner, latest_owner_identity, latest_release, latest_release_identity = (
        _released_v7_intermediate_context(request.config, prior_owner)
    )
    if (
        latest_owner != owner
        or latest_owner_identity.sha256 != owner_identity.sha256
        or latest_release != release
        or latest_release_identity.sha256 != release_identity.sha256
    ):
        raise ProtectedError("released intermediate evidence changed before retirement write")

    if active_failed:
        ReceiptFile(request.receipt_path).archive_to(
            failed_archive_path.name,
            expected_sha256=cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        )
        archived, archived_identity, _ = cutover.read_control_json(failed_archive_path)
        if (
            archived_identity.sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256
            or archived != _failed
            or os.path.lexists(request.receipt_path)
        ):
            raise ProtectedError("v6 FAILED receipt archive readback differs")
    else:
        archived, archived_identity, _ = cutover.read_control_json(failed_archive_path)
        if (
            archived_identity.sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256
            or archived != _failed
        ):
            raise ProtectedError("archived v6 FAILED receipt changed before v2 retirement")

    if stored_retirement is None:
        cutover._write_json(  # pyright: ignore[reportPrivateUsage]
            retirement_path,
            retirement,
            expected=None,
        )
        readback, _, _ = cutover._load_json(retirement_path)  # pyright: ignore[reportPrivateUsage]
        if readback != retirement:
            raise ProtectedError("v2 retirement evidence readback differs")
    cutover._verify_failed_terminal_retirement_v2_inputs(  # pyright: ignore[reportPrivateUsage]
        request.config,
        retirement,
    )

    unsigned: Record = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": v5_proof["prior_reservation_id"],
        "prior_operation_id": v5_proof["prior_operation_id"],
        "prior_authorization_sha256": v5_proof["prior_authorization_sha256"],
        "prior_release_evidence": v5_proof["prior_release_evidence"],
        "prior_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "prior_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "new_reservation_id": request.reservation_id,
        "new_operation_id": request.operation_id,
        "retired_failed_terminal_evidence": retirement,
    }
    proof = {**unsigned, "evidence_sha256": digest(unsigned)}
    cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
        proof,
        {
            "reservation_id": request.reservation_id,
            "operation_id": request.operation_id,
            "managed_receipt_sha256": request.managed_receipt_sha256,
            "target": request_owner_target(request),
        },
    )
    return proof


def _require_released_success_evidence(
    request: Request,
    prior_owner: Record | None,
    *,
    runner: cutover.Runner | None = None,
) -> Record | None:
    """Classify current-success eligibility and freeze its release proof pre-reservation.

    When the protected apply receipt and the managed receipt are both SUCCESS,
    the RELEASED owner is the only record that this exact pair was verified at
    release. Return an integrity-sealed copy bound to the candidate reservation
    and operation before the RELEASED owner is replaced.
    """
    failed_predecessor_sha = _failed_terminal_predecessor_receipt_sha256(
        prior_owner, request.config
    )
    if failed_predecessor_sha is not None:
        if (
            prior_owner is not None
            and prior_owner.get("reservation_id") == cutover.RELEASED_INTERMEDIATE_RESERVATION_ID
        ):
            return _require_released_v7_intermediate_successor_evidence(
                request, prior_owner, runner=runner
            )
        return _require_failed_terminal_successor_evidence(
            request, cast(Record, prior_owner), runner=runner
        )
    if prior_owner is not None and _is_prestart_successor_released_owner(prior_owner):
        return _require_prestart_successor_success_evidence(request, prior_owner, runner=runner)
    if not os.path.lexists(request.receipt_path):
        if not os.path.lexists(request.config.receipt_path):
            return None
        recovered_sha = _reconciled_predecessor_receipt_sha256(request.config, prior_owner)
        if recovered_sha is not None:
            return _require_reconciled_success_evidence(request, cast(Record, prior_owner))
        return None
    if not os.path.lexists(request.config.receipt_path):
        return None
    prior, slot_sha256 = ReceiptFile(request.receipt_path).read_with_sha256()
    if prior is not None and prior.get("status") == "FAILED":
        raise ProtectedError("failed protected receipt is outside the exact successor bridge")
    managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
    if prior is None or prior.get("status") != "SUCCESS" or managed.get("status") != "SUCCESS":
        return None
    if prior_owner is None or prior_owner.get("phase") != "RELEASED":
        raise ProtectedError("current protected success has no matching RELEASED owner")
    identity = record(prior.get("identity"))
    target = record(identity.get("target"))
    evidence_value = prior_owner.get("release_evidence")
    evidence = record(evidence_value) if evidence_value is not None else {}
    expected_target = {
        "source_worktree": target.get("source_worktree"),
        "head": target.get("head"),
        "tree": target.get("tree"),
        "durable_ref": target.get("durable_ref"),
    }
    # The prior operation was authorized against the managed receipt that existed
    # *before* it ran (None for a first apply); the receipt it produced is bound
    # separately, by the release evidence.
    expected_authorization = {
        "reservation_id": identity.get("reservation_id"),
        "operation_id": identity.get("operation_id"),
        "managed_receipt_sha256": identity.get("managed_receipt_sha256"),
        "control_head": identity.get("control_head"),
        "control_tree": identity.get("control_tree"),
        "action": "apply",
        "target": expected_target,
    }
    if (
        prior_owner.get("owner_kind") != "protected"
        or prior_owner.get("action") != "apply"
        or prior_owner.get("reservation_id") != identity.get("reservation_id")
        or prior_owner.get("operation_id") != identity.get("operation_id")
        or prior_owner.get("managed_receipt_sha256") != identity.get("managed_receipt_sha256")
        or prior_owner.get("target") != expected_target
        or prior_owner.get("authorization") != expected_authorization
        or prior_owner.get("control_head") != identity.get("control_head")
        or prior_owner.get("control_tree") != identity.get("control_tree")
        or evidence.get("verified") is not True
        or evidence.get("protected_receipt_sha256") != slot_sha256
        or evidence.get("managed_receipt_sha256") != managed_identity.sha256
    ):
        raise ProtectedError("released owner evidence does not bind the current success receipts")
    if slot_sha256 is None or request.reservation_id is None:
        raise ProtectedError("candidate successor identity is incomplete")
    if claims.ClaimStore(request.claim_root).inspect(TASK_KEY).get("status") != "ABSENT":
        raise ProtectedError("protected execution claim is still owned or uncertain")
    if not _supersede_current_success_receipt(
        request,
        ReceiptFile(request.receipt_path),
        prior,
        managed=managed,
        managed_sha256=managed_identity.sha256,
        slot_sha256=slot_sha256,
        owner=prior_owner,
        archive=False,
        require_saved_proof=False,
    ):
        raise ProtectedError("current protected success is not eligible for successor reservation")
    unsigned = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": prior_owner["reservation_id"],
        "prior_operation_id": prior_owner["operation_id"],
        "prior_authorization_sha256": digest(prior_owner["authorization"]),
        "prior_release_evidence": evidence,
        "prior_protected_receipt_sha256": slot_sha256,
        "prior_managed_receipt_sha256": managed_identity.sha256,
        "new_reservation_id": request.reservation_id,
        "new_operation_id": request.operation_id,
    }
    return {**unsigned, "evidence_sha256": digest(unsigned)}


def _require_failed_terminal_successor_evidence(
    request: Request,
    prior_owner: Record,
    *,
    runner: cutover.Runner | None,
) -> Record:
    selected_runner = cutover.run_command if runner is None else runner
    if (
        request.reservation_id is None
        or request.reservation_id == cutover.FAILED_TERMINAL_RESERVATION_ID
        or request.operation_id == cutover.FAILED_TERMINAL_OPERATION_ID
        or (request.config.expected_head, request.config.expected_tree)
        != (cutover.V7_SOURCE_HEAD, cutover.V7_SOURCE_TREE)
    ):
        raise ProtectedError("failed terminal incident permits only a fresh exact v7 successor")

    owner_snapshot = cutover._read_control_owner(request.config)  # pyright: ignore[reportPrivateUsage]
    if owner_snapshot is None:
        raise ProtectedError("exact failed terminal owner is absent")
    failed_owner, owner_file_identity = owner_snapshot
    if (
        failed_owner.get("reservation_id") != cutover.FAILED_TERMINAL_RESERVATION_ID
        or failed_owner.get("operation_id") != cutover.FAILED_TERMINAL_OPERATION_ID
        or failed_owner.get("owner_kind") != "protected"
        or failed_owner.get("action") != "apply"
        or failed_owner.get("phase") != "RELEASED"
        or failed_owner.get("mutation_started") is not False
        or failed_owner.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or failed_owner.get("authorization") != cutover._owner_identity(failed_owner)  # pyright: ignore[reportPrivateUsage]
        or prior_owner.get("record_sha256") != failed_owner.get("record_sha256")
        or prior_owner.get("release_evidence") != failed_owner.get("release_evidence")
    ):
        raise ProtectedError(
            "released owner does not match the exact zero-mutation failed incident"
        )
    failed_release = record(failed_owner.get("release_evidence"))
    if failed_release != {
        "protected_receipt_sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        "managed_receipt_unchanged": True,
        "verified": True,
    }:
        raise ProtectedError("failed owner release evidence does not verify the frozen incident")

    v5_proof = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
        failed_owner.get("predecessor_release_evidence"), failed_owner
    )
    if (
        v5_proof.get("prior_protected_receipt_sha256") != cutover.V5_PROTECTED_RECEIPT_SHA256
        or v5_proof.get("prior_managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
    ):
        raise ProtectedError("failed v6 owner lost the exact v5 predecessor proof")

    receipt_file = ReceiptFile(request.receipt_path)
    receipt_exists = os.path.lexists(request.receipt_path)
    failed: Record | None
    failed_sha256: str | None
    if receipt_exists:
        failed, failed_sha256 = receipt_file.read_with_sha256()
        if failed is None or failed_sha256 is None:
            raise ProtectedError("failed terminal receipt disappeared before retirement")
    else:
        failed_archive = _find_archived_prior_receipt(
            request.receipt_path,
            lambda value: value == cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        )
        if failed_archive is None:
            raise ProtectedError("exact failed terminal receipt or its archive is absent")
        failed_archive_path = Path(text(failed_archive.get("path")))
        failed, failed_identity, _ = cutover.read_control_json(failed_archive_path)
        failed_sha256 = failed_identity.sha256

    failed_identity = record(failed.get("identity"))
    failed_execution_id = text(failed.get("execution_id"))
    if re.fullmatch(r"[0-9a-f]{64}", failed_execution_id) is None:
        raise ProtectedError("failed terminal receipt execution identity is malformed")
    failed_archive_path = request.receipt_path.with_name(
        f"{request.receipt_path.stem}.{failed_execution_id}.superseded.json"
    )
    if (
        failed.get("schema_version") != SCHEMA
        or failed.get("task_key") != TASK_KEY
        or failed.get("receipt_sha256")
        != digest({key: value for key, value in failed.items() if key != "receipt_sha256"})
        or failed_execution_id != digest(failed_identity)
        or failed.get("status") != "FAILED"
        or failed.get("phase") != "COMPLETED"
        or type(failed.get("exit_code")) is not int
        or failed.get("exit_code") != 1
        or failed.get("result_status") != "INCOMPLETE_OR_AMBIGUOUS"
        or failed.get("child_exit_code") is not None
        or "child_started_at" in failed
        or "child_completed_at" in failed
        or failed_identity.get("reservation_id") != cutover.FAILED_TERMINAL_RESERVATION_ID
        or failed_identity.get("operation_id") != cutover.FAILED_TERMINAL_OPERATION_ID
        or failed_identity.get("action") != "apply"
        or failed_identity.get("task_key") != TASK_KEY
        or failed_identity.get("execution_receipt_path") != str(request.receipt_path)
        or failed_identity.get("managed_receipt_path") != str(request.config.receipt_path)
        or failed_identity.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or failed_identity.get("prior_execution_receipt_sha256")
        != cutover.V5_PROTECTED_RECEIPT_SHA256
        or failed_identity.get("claim_root") != str(request.claim_root)
        or failed_identity.get("target") != failed_owner.get("target")
        or failed_identity.get("source_worktree")
        != record(failed_owner.get("target")).get("source_worktree")
        or failed_identity.get("source_head") != record(failed_owner.get("target")).get("head")
        or failed_identity.get("source_tree") != record(failed_owner.get("target")).get("tree")
    ):
        raise ProtectedError("protected receipt does not match the frozen FAILED terminal shape")
    if failed_sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256:
        raise ProtectedError("protected FAILED receipt SHA differs from the frozen incident")
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        failed,
        path=request.receipt_path,
        bound_identity=cutover._owner_identity(failed_owner),  # pyright: ignore[reportPrivateUsage]
        successful=False,
    )
    failed_link = failed.get("managed_receipt")
    if isinstance(failed_link, dict):
        failed_link_record = cast(Record, failed_link)
        if failed_link_record.get("operation_id") == failed_identity.get("operation_id"):
            raise ProtectedError("failed v6 operation has a managed receipt")

    if os.path.lexists(request.config.scheduler_root / ROLLBACK_RECEIPT_NAME):
        raise ProtectedError(
            "a protected rollback receipt makes failed predecessor history ambiguous"
        )
    managed, managed_identity, _ = cutover.read_control_json(request.config.receipt_path)
    if (
        managed_identity.sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
        or request.managed_receipt_sha256 != cutover.V5_MANAGED_RECEIPT_SHA256
        or failed_owner.get("managed_receipt_sha256") != managed_identity.sha256
        or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
        or managed.get("task") != cutover.TASK_ID
        or managed.get("phase") != "COMPLETED"
        or managed.get("status") != "SUCCESS"
        or managed.get("operation_id") == cutover.FAILED_TERMINAL_OPERATION_ID
        or managed.get("operation_id") != v5_proof.get("prior_operation_id")
    ):
        raise ProtectedError("unchanged v5 managed SUCCESS differs from the frozen predecessor")

    v5_archive = _find_archived_prior_receipt(
        request.receipt_path,
        lambda value: value == cutover.V5_PROTECTED_RECEIPT_SHA256,
    )
    if v5_archive is None:
        raise ProtectedError("archived v5 protected SUCCESS predecessor is absent")
    v5_archive_path = Path(text(v5_archive.get("path")))
    v5_receipt, v5_identity, _ = cutover.read_control_json(v5_archive_path)
    v5_receipt_identity = record(v5_receipt.get("identity"))
    v5_target = record(v5_receipt_identity.get("target"))
    v5_owner_identity = {
        "reservation_id": v5_receipt_identity.get("reservation_id"),
        "operation_id": v5_receipt_identity.get("operation_id"),
        "managed_receipt_sha256": v5_receipt_identity.get("managed_receipt_sha256"),
        "control_head": v5_receipt_identity.get("control_head"),
        "control_tree": v5_receipt_identity.get("control_tree"),
        "action": "apply",
        "target": v5_target,
    }
    expected_v5_authorization = {
        key: value for key, value in v5_owner_identity.items() if key != "owner_kind"
    }
    v5_release = record(v5_proof.get("prior_release_evidence"))
    v5_link = record(v5_receipt.get("managed_receipt"))
    if (
        v5_identity.sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256
        or v5_receipt.get("status") != "SUCCESS"
        or v5_receipt.get("result_status") not in {"SUCCESS", "ALREADY_APPLIED"}
        or v5_receipt_identity.get("reservation_id") != v5_proof.get("prior_reservation_id")
        or v5_receipt_identity.get("operation_id") != v5_proof.get("prior_operation_id")
        or v5_receipt_identity.get("action") != "apply"
        or v5_receipt_identity.get("execution_receipt_path") != str(request.receipt_path)
        or v5_target.get("head") != cutover.V5_SOURCE_HEAD
        or v5_target.get("tree") != cutover.V5_SOURCE_TREE
        or v5_proof.get("prior_authorization_sha256") != digest(expected_v5_authorization)
        or v5_release.get("verified") is not True
        or v5_release.get("protected_receipt_sha256") != cutover.V5_PROTECTED_RECEIPT_SHA256
        or v5_release.get("managed_receipt_sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or v5_link.get("path") != str(request.config.receipt_path)
        or v5_link.get("sha256") != cutover.V5_MANAGED_RECEIPT_SHA256
        or v5_link.get("status") != "SUCCESS"
        or managed.get("plan_digest") != v5_receipt_identity.get("plan_digest")
    ):
        raise ProtectedError("archived v5 SUCCESS does not match its saved release authority")
    cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
        v5_receipt,
        path=request.receipt_path,
        bound_identity=v5_owner_identity,
        successful=True,
    )

    candidate_plan = request.load_plan()
    plan_source = record(candidate_plan.get("source"))
    plan_old = record(plan_source.get("old"))
    plan_new = record(plan_source.get("new"))
    prestate = record(candidate_plan.get("prestate"))
    v5_after = record(managed.get("after"))
    v5_after_source = record(v5_after.get("source"))
    v5_after_plist = record(v5_after.get("plist"))
    v5_after_launchd = record(v5_after.get("launchd"))
    if (
        (str(request.legacy_worktree), request.legacy_head, request.legacy_tree)
        != (v5_target.get("source_worktree"), cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
        or plan_old.get("source_worktree") != v5_target.get("source_worktree")
        or plan_old.get("head") != cutover.V5_SOURCE_HEAD
        or plan_old.get("tree") != cutover.V5_SOURCE_TREE
        or plan_new.get("role") != "new"
        or plan_new.get("source_worktree") != str(request.config.source_worktree)
        or plan_new.get("head") != cutover.V7_SOURCE_HEAD
        or plan_new.get("tree") != cutover.V7_SOURCE_TREE
        or plan_new.get("clean") is not True
        or v5_after_source.get("role") != "new"
        or plan_old != {**v5_after_source, "role": "old"}
        or record(prestate.get("old_runtime")) != record(v5_after.get("runtime"))
        or not cutover.successor_plist_identity_matches(
            record(prestate.get("old_plist_identity")), v5_after_plist.get("identity")
        )
        or prestate.get("old_launch_state") != v5_after_launchd.get("state")
        or prestate.get("old_enabled") is not v5_after.get("enabled")
        or record(prestate.get("old_binding")) != record(v5_after_plist.get("binding"))
        or request.plan_digest == v5_receipt_identity.get("plan_digest")
        or request.operation_id == v5_receipt_identity.get("operation_id")
    ):
        raise ProtectedError("candidate v7 plan is not the exact live v5 successor")

    claim_state = claims.ClaimStore(request.claim_root).inspect(TASK_KEY)
    if claim_state.get("status") != "ABSENT":
        raise ProtectedError("ClaimStore is not absent")
    old_live = _prove_plan_old_live(request.config, candidate_plan, selected_runner)
    if (
        record(old_live.get("source")) != plan_old
        or record(old_live.get("runtime"))
        != record(record(candidate_plan.get("runtime")).get("old"))
        or record(old_live.get("target_source")) == record(old_live.get("source"))
        or record(old_live.get("target_runtime")) == record(old_live.get("runtime"))
    ):
        raise ProtectedError("live state does not prove v5 OLD runtime and inactive v7 target")
    v5_config = replace(
        request.config,
        source_worktree=Path(text(v5_target.get("source_worktree"))),
        expected_head=text(v5_target.get("head")),
        expected_tree=text(v5_target.get("tree")),
        durable_ref=text(v5_target.get("durable_ref")),
    )
    cutover.validate_protected_plan(v5_config, cutover.receipt_to_plan(v5_config, managed))
    cutover.verify_completed_receipt_live(
        v5_config,
        managed,
        successor_old_plist_identity=prestate.get("old_plist_identity"),
        runner=selected_runner,
    )

    if request.prior_execution_receipt_sha256 != cutover.V5_PROTECTED_RECEIPT_SHA256:
        raise ProtectedError("candidate v7 operation is not bound to archived v5 SUCCESS")
    if os.path.lexists(failed_archive_path):
        archived, archived_identity, _ = cutover.read_control_json(failed_archive_path)
        if archived_identity.sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256 or archived != failed:
            raise ProtectedError("failed receipt archive path already holds conflicting bytes")
    existing_failed_archive = _find_archived_prior_receipt(
        request.receipt_path,
        lambda value: value == cutover.FAILED_TERMINAL_RECEIPT_SHA256,
    )
    if existing_failed_archive is not None and Path(text(existing_failed_archive.get("path"))) != (
        failed_archive_path
    ):
        raise ProtectedError("failed terminal receipt has more than one matching archive")

    candidate_target = request_owner_target(request)
    unsigned_retirement: Record = {
        "schema": cutover.FAILED_TERMINAL_RETIREMENT_SCHEMA,
        "receipt_path": str(request.receipt_path),
        "archive_path": str(failed_archive_path),
        "execution_id": failed_execution_id,
        "receipt_sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        "reservation_id": cutover.FAILED_TERMINAL_RESERVATION_ID,
        "operation_id": cutover.FAILED_TERMINAL_OPERATION_ID,
        "status": "FAILED",
        "phase": "COMPLETED",
        "exit_code": 1,
        "result_status": "INCOMPLETE_OR_AMBIGUOUS",
        "child_started": False,
        "child_completed": False,
        "mutation_started": False,
        "zero_mutation": True,
        "owner_record": failed_owner,
        "owner_file_sha256": owner_file_identity.sha256,
        "v5_predecessor_release_evidence": v5_proof,
        "v5_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "v5_protected_receipt_archive_path": str(v5_archive_path),
        "v5_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "v5_managed_receipt_path": str(request.config.receipt_path),
        "v5_source_head": cutover.V5_SOURCE_HEAD,
        "v5_source_tree": cutover.V5_SOURCE_TREE,
        "v5_live_state": {"verified": True, **old_live},
        "candidate_plan_sha256": request.plan_sha256,
        "candidate_target": candidate_target,
        "claim_root": str(request.claim_root),
        "claim_store_status": "ABSENT",
        "failed_operation_managed_receipt_present": False,
        "archive_status": "ARCHIVED_UNCHANGED",
    }
    retirement = {
        **unsigned_retirement,
        "record_sha256": digest(unsigned_retirement),
    }
    retirement_path = request.config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_NAME
    existing_retirement: Record | None = None
    if os.path.lexists(retirement_path):
        existing_retirement, _, _ = cutover._load_json(  # pyright: ignore[reportPrivateUsage]
            retirement_path
        )
        if existing_retirement != retirement:
            raise ProtectedError(
                "failed terminal retirement evidence exists with conflicting proof"
            )

    if receipt_exists:
        receipt_file.archive_to(
            failed_archive_path.name,
            expected_sha256=cutover.FAILED_TERMINAL_RECEIPT_SHA256,
        )
    archived, archived_identity, _ = cutover.read_control_json(failed_archive_path)
    if (
        archived_identity.sha256 != cutover.FAILED_TERMINAL_RECEIPT_SHA256
        or archived != failed
        or os.path.lexists(request.receipt_path)
    ):
        raise ProtectedError("failed terminal receipt archive readback differs")
    if existing_retirement is None:
        cutover._write_json(  # pyright: ignore[reportPrivateUsage]
            retirement_path, retirement, expected=None
        )
        readback, _, _ = cutover._load_json(retirement_path)  # pyright: ignore[reportPrivateUsage]
        if readback != retirement:
            raise ProtectedError("failed terminal retirement evidence readback differs")

    unsigned = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": v5_proof["prior_reservation_id"],
        "prior_operation_id": v5_proof["prior_operation_id"],
        "prior_authorization_sha256": v5_proof["prior_authorization_sha256"],
        "prior_release_evidence": v5_proof["prior_release_evidence"],
        "prior_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "prior_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "new_reservation_id": request.reservation_id,
        "new_operation_id": request.operation_id,
        "retired_failed_terminal_evidence": retirement,
    }
    return {**unsigned, "evidence_sha256": digest(unsigned)}


def _failed_terminal_bridge_live_verifier(
    request: Request,
    prior_owner: Record,
    expected_proof: Record,
    *,
    runner: cutover.Runner,
) -> Callable[[], None]:
    """Rebuild exact failed-successor proof at the serialized owner CAS boundary."""

    def verify() -> None:
        current_proof = _require_released_success_evidence(
            request,
            prior_owner,
            runner=runner,
        )
        if current_proof != expected_proof:
            raise ProtectedError(
                "failed terminal predecessor or live state changed before owner reservation"
            )

    return verify


def cmd_reconcile_prestart_failure(
    args: argparse.Namespace,
    *,
    runner: cutover.Runner | None = None,
) -> Record:
    """Retire one explicitly identified pre-STARTED failure after full proof.

    The command is the sole cross-control-version exception. It validates the
    original owner version and the currently running recovery version, then
    archives the stranded slot, seals proof, and releases that exact owner.
    Every proof is complete before the first evidence write.
    """
    selected_runner = cutover.run_command if runner is None else runner
    config = build_reservation_config(args, for_action="apply")
    reservation_id = text(args.reservation_id)
    operation_id = text(args.operation_id)
    try:
        if str(UUID(reservation_id)) != reservation_id:
            raise ValueError
    except ValueError as exc:
        raise ProtectedError("reservation ID must be a canonical UUID") from exc
    if re.fullmatch(r"[0-9a-f]{32}", operation_id) is None:
        raise ProtectedError("operation ID must be a lowercase 32-character digest")
    supplied_hashes = {
        "stranded_protected_receipt_sha256": text(args.stranded_protected_receipt_sha256),
        "managed_receipt_sha256": text(args.managed_receipt_sha256),
        "predecessor_protected_receipt_sha256": text(args.predecessor_protected_receipt_sha256),
        "plan_sha256": text(args.plan_sha256),
    }
    for label, value in supplied_hashes.items():
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ProtectedError(f"{label} must be a lowercase SHA256")
    original_control = {
        "head": text(args.original_control_head),
        "tree": text(args.original_control_tree),
    }
    recovery_control = {
        "head": text(args.current_recovery_control_head),
        "tree": text(args.current_recovery_control_tree),
    }
    for identity in (original_control, recovery_control):
        if any(re.fullmatch(r"[0-9a-f]{40}", str(value)) is None for value in identity.values()):
            raise ProtectedError("control identities must be exact lowercase HEAD/tree values")
    running_control = cutover.control_version()
    if running_control != recovery_control or recovery_control == original_control:
        raise ProtectedError("running recovery control identity differs from explicit arguments")

    receipt_path = config.scheduler_root / RECEIPT_NAME
    receipt_file = ReceiptFile(receipt_path)
    reservation_record_path = _prestart_reconciliation_record_path(config, reservation_id)
    with cutover.CutoverLock(  # pyright: ignore[reportPrivateUsage]
        cutover._control_owner_lock_path(config)  # pyright: ignore[reportPrivateUsage]
    ):
        owner_snapshot = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
        if owner_snapshot is None:
            raise ProtectedError("durable owner is absent")
        owner, owner_file_identity = owner_snapshot
        if (
            owner.get("reservation_id") != reservation_id
            or owner.get("operation_id") != operation_id
            or owner.get("owner_kind") != "protected"
            or owner.get("action") != "apply"
            or owner.get("phase") not in {"AUTHORIZED_PENDING", "RELEASED"}
            or owner.get("mutation_started") is not False
            or (owner.get("control_head"), owner.get("control_tree"))
            != (original_control["head"], original_control["tree"])
            or owner.get("managed_receipt_sha256") != supplied_hashes["managed_receipt_sha256"]
        ):
            raise ProtectedError("durable owner does not match the exact pre-start operation")

        target = {
            "source_worktree": str(config.source_worktree),
            "head": config.expected_head,
            "tree": config.expected_tree,
            "durable_ref": config.durable_ref,
        }
        expected_owner_identity = {
            "reservation_id": reservation_id,
            "operation_id": operation_id,
            "managed_receipt_sha256": supplied_hashes["managed_receipt_sha256"],
            "control_head": original_control["head"],
            "control_tree": original_control["tree"],
            "action": "apply",
            "target": target,
        }
        if (
            cutover._owner_identity(owner) != expected_owner_identity  # pyright: ignore[reportPrivateUsage]
            or owner.get("authorization") != expected_owner_identity
        ):
            raise ProtectedError("durable owner authorization differs from explicit identities")

        slot_value: Record | None = None
        slot_sha: str | None = None
        archived_stranded_path: Path | None = None
        if os.path.lexists(receipt_path):
            slot_value, slot_sha = receipt_file.read_with_sha256()
        if (
            slot_value is not None
            and slot_sha != supplied_hashes["stranded_protected_receipt_sha256"]
        ):
            raise ProtectedError("fixed protected receipt SHA differs from the explicit value")
        if slot_value is not None:
            stranded = slot_value
            observed_stranded_sha = slot_sha
        else:
            # A prior interrupted reconciliation may have completed the
            # archive but not yet sealed its owner-release record.
            archive_candidate: Record | None = None
            for child in config.scheduler_root.glob(f"{receipt_path.stem}.*.superseded.json"):
                try:
                    archived, archived_file_identity, _ = cutover.read_control_json(child)
                except (OSError, ValueError, cutover.CutoverError):
                    continue
                archived_identity = record(archived.get("identity"))
                archived_unsigned = {
                    key: value for key, value in archived.items() if key != "receipt_sha256"
                }
                archived_execution_id = digest(archived_identity)
                if (
                    archived_file_identity.sha256
                    == supplied_hashes["stranded_protected_receipt_sha256"]
                    and child.name == f"{receipt_path.stem}.{archived_execution_id}.superseded.json"
                    and archived.get("schema_version") == SCHEMA
                    and archived.get("receipt_sha256") == digest(archived_unsigned)
                    and archived.get("execution_id") == archived_execution_id
                    and archived_identity.get("execution_receipt_path") == str(receipt_path)
                ):
                    archive_candidate = archived
                    archived_stranded_path = child
                    break
            if archive_candidate is None:
                raise ProtectedError("stranded protected receipt or its exact archive is absent")
            stranded = archive_candidate
            observed_stranded_sha = supplied_hashes["stranded_protected_receipt_sha256"]

        stranded_identity = record(stranded.get("identity"))
        execution_id = text(stranded.get("execution_id"))
        archive_path = receipt_path.with_name(f"{receipt_path.stem}.{execution_id}.superseded.json")
        if (
            stranded.get("schema_version") != SCHEMA
            or stranded.get("task_key") != TASK_KEY
            or stranded.get("receipt_sha256")
            != digest({key: item for key, item in stranded.items() if key != "receipt_sha256"})
            or execution_id != digest(stranded_identity)
            or observed_stranded_sha != supplied_hashes["stranded_protected_receipt_sha256"]
            or stranded.get("phase") != "COMPLETED"
            or stranded.get("status") != "INCOMPLETE_OR_AMBIGUOUS"
            or stranded.get("result_status") != "INCOMPLETE_OR_AMBIGUOUS"
            or type(stranded.get("exit_code")) is not int
            or cast(int, stranded.get("exit_code")) not in PRESTART_EXEC_FAILURE_CODES
            or stranded.get("child_exit_code") is not None
            or "child_started_at" in stranded
            or "child_completed_at" in stranded
            or type(stranded.get("gated_child_pid")) is not int
            or cast(int, stranded.get("gated_child_pid")) <= 0
            or record(stranded.get("claim_owner")).get("child_pid")
            != stranded.get("gated_child_pid")
        ):
            raise ProtectedError("stranded receipt is not a proven completed pre-STARTED failure")
        if (
            stranded_identity.get("reservation_id") != reservation_id
            or stranded_identity.get("operation_id") != operation_id
            or stranded_identity.get("action") != "apply"
            or stranded_identity.get("task_key") != TASK_KEY
            or stranded_identity.get("execution_receipt_path") != str(receipt_path)
            or stranded_identity.get("managed_receipt_path") != str(config.receipt_path)
            or stranded_identity.get("source_worktree") != str(config.source_worktree)
            or stranded_identity.get("source_head") != config.expected_head
            or stranded_identity.get("source_tree") != config.expected_tree
            or stranded_identity.get("legacy_worktree") != str(Path(args.legacy_worktree))
            or stranded_identity.get("legacy_head") != args.legacy_head
            or stranded_identity.get("legacy_tree") != args.legacy_tree
            or stranded_identity.get("plan_file") != str(Path(args.plan_file))
            or stranded_identity.get("plan_sha256") != supplied_hashes["plan_sha256"]
            or stranded_identity.get("managed_receipt_sha256")
            != supplied_hashes["managed_receipt_sha256"]
            or stranded_identity.get("prior_execution_receipt_sha256")
            != supplied_hashes["predecessor_protected_receipt_sha256"]
            or (stranded_identity.get("control_head"), stranded_identity.get("control_tree"))
            != (original_control["head"], original_control["tree"])
            or stranded_identity.get("target") != target
        ):
            raise ProtectedError("stranded receipt identity differs from explicit arguments")

        plan, plan_identity, _ = cutover.read_control_json(Path(args.plan_file))
        if plan_identity.sha256 != supplied_hashes["plan_sha256"]:
            raise ProtectedError("stranded plan SHA differs from the explicit value")
        cutover.validate_protected_plan(config, plan)
        plan_old = record(record(plan.get("source")).get("old"))
        plan_new = record(record(plan.get("source")).get("new"))
        if (
            plan.get("plan_digest") != stranded_identity.get("plan_digest")
            or plan_new.get("role") != "new"
            or plan_new.get("source_worktree") != str(config.source_worktree)
            or plan_new.get("head") != config.expected_head
            or plan_new.get("tree") != config.expected_tree
            or plan_new.get("durable_ref") != config.durable_ref
            or plan_new.get("clean") is not True
            or (plan_old.get("source_worktree"), plan_old.get("head"), plan_old.get("tree"))
            != (str(Path(args.legacy_worktree)), args.legacy_head, args.legacy_tree)
        ):
            raise ProtectedError("stranded plan does not bind the exact OLD and target sources")

        claim_root = repository_claim_root()
        if stranded_identity.get("claim_root") != str(claim_root):
            raise ProtectedError("stranded receipt claim root differs from repository authority")
        claim_state = claims.ClaimStore(claim_root).inspect(TASK_KEY)
        if claim_state.get("status") != "ABSENT":
            raise ProtectedError("ClaimStore is not absent")

        managed, managed_identity, _ = cutover.read_control_json(config.receipt_path)
        if (
            managed_identity.sha256 != supplied_hashes["managed_receipt_sha256"]
            or managed_identity.sha256 != owner.get("managed_receipt_sha256")
            or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
            or managed.get("task") != cutover.TASK_ID
            or managed.get("phase") != "COMPLETED"
            or managed.get("status") != "SUCCESS"
            or managed.get("operation_id") == operation_id
        ):
            raise ProtectedError("current managed receipt is not the unchanged prior SUCCESS")

        predecessor_evidence = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
            owner.get("predecessor_release_evidence"), owner
        )
        predecessor_sha = supplied_hashes["predecessor_protected_receipt_sha256"]
        if (
            predecessor_evidence.get("prior_protected_receipt_sha256") != predecessor_sha
            or predecessor_evidence.get("prior_managed_receipt_sha256") != managed_identity.sha256
        ):
            raise ProtectedError("durable predecessor proof differs from the exact v5 hashes")
        predecessor_archive = _find_archived_prior_receipt(
            receipt_path, lambda value: value == predecessor_sha
        )
        if predecessor_archive is None:
            raise ProtectedError("archived v5 protected SUCCESS predecessor is absent")
        predecessor_path = Path(text(predecessor_archive.get("path")))
        predecessor, predecessor_identity, _ = cutover.read_control_json(predecessor_path)
        predecessor_identity_record = record(predecessor.get("identity"))
        predecessor_target = record(predecessor_identity_record.get("target"))
        predecessor_owner_identity = {
            "reservation_id": predecessor_identity_record.get("reservation_id"),
            "operation_id": predecessor_identity_record.get("operation_id"),
            "managed_receipt_sha256": predecessor_identity_record.get("managed_receipt_sha256"),
            "control_head": predecessor_identity_record.get("control_head"),
            "control_tree": predecessor_identity_record.get("control_tree"),
            "action": "apply",
            "target": predecessor_target,
        }
        expected_predecessor_authorization = {
            key: value for key, value in predecessor_owner_identity.items() if key != "owner_kind"
        }
        prior_release = record(predecessor_evidence.get("prior_release_evidence"))
        predecessor_link = record(predecessor.get("managed_receipt"))
        if (
            predecessor_identity.sha256 != predecessor_sha
            or predecessor_identity_record.get("reservation_id")
            != predecessor_evidence.get("prior_reservation_id")
            or predecessor_identity_record.get("operation_id")
            != predecessor_evidence.get("prior_operation_id")
            or predecessor_identity_record.get("plan_digest") != managed.get("plan_digest")
            or predecessor_identity_record.get("operation_id") != managed.get("operation_id")
            or predecessor_evidence.get("prior_authorization_sha256")
            != digest(expected_predecessor_authorization)
            or prior_release.get("verified") is not True
            or prior_release.get("protected_receipt_sha256") != predecessor_sha
            or prior_release.get("managed_receipt_sha256") != managed_identity.sha256
            or predecessor_link.get("path") != str(config.receipt_path)
            or predecessor_link.get("sha256") != managed_identity.sha256
            or predecessor_link.get("status") != "SUCCESS"
            or plan_old.get("source_worktree") != predecessor_target.get("source_worktree")
            or plan_old.get("head") != predecessor_target.get("head")
            or plan_old.get("tree") != predecessor_target.get("tree")
        ):
            raise ProtectedError("archived v5 SUCCESS does not match its saved owner proof")
        cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
            predecessor,
            path=receipt_path,
            bound_identity=predecessor_owner_identity,
            successful=True,
        )
        if managed.get("plan_digest") != predecessor_identity_record.get(
            "plan_digest"
        ) or managed.get("operation_id") != predecessor_identity_record.get("operation_id"):
            raise ProtectedError("managed SUCCESS is not the archived v5 operation")

        old_live = _prove_plan_old_live(config, plan, selected_runner)
        if (
            record(old_live.get("source")) != plan_old
            or record(old_live.get("runtime")) != record(record(plan.get("runtime")).get("old"))
            or record(old_live.get("target_source")) == record(old_live.get("source"))
            or record(old_live.get("target_runtime")) == record(old_live.get("runtime"))
        ):
            raise ProtectedError("live state does not prove OLD runtime with target still inactive")
        prior_config = replace(
            config,
            source_worktree=Path(text(predecessor_target.get("source_worktree"))),
            expected_head=text(predecessor_target.get("head")),
            expected_tree=text(predecessor_target.get("tree")),
            durable_ref=text(predecessor_target.get("durable_ref")),
        )
        cutover.validate_protected_plan(
            prior_config, cutover.receipt_to_plan(prior_config, managed)
        )
        cutover.verify_completed_receipt_live(
            prior_config,
            managed,
            successor_old_plist_identity=record(plan.get("prestate")).get("old_plist_identity"),
            runner=selected_runner,
        )

        expected_archive_path = receipt_path.with_name(
            f"{receipt_path.stem}.{execution_id}.superseded.json"
        )
        if archive_path != expected_archive_path:
            raise ProtectedError("stranded receipt archive identity differs")
        if slot_value is None and archived_stranded_path != archive_path:
            raise ProtectedError("stranded receipt is not at its execution-identity archive path")
        if os.path.lexists(archive_path) and os.path.lexists(receipt_path):
            archive_metadata = os.lstat(archive_path)
            if archive_metadata.st_nlink == 1:
                archive_value, archive_identity, _ = cutover.read_control_json(archive_path)
                if (
                    archive_identity.sha256 != supplied_hashes["stranded_protected_receipt_sha256"]
                    or archive_value != stranded
                ):
                    raise ProtectedError("stranded archive path contains conflicting evidence")

        if os.path.lexists(config.scheduler_root / ROLLBACK_RECEIPT_NAME):
            raise ProtectedError("a protected rollback receipt makes predecessor history ambiguous")

        unsigned_reconciliation: Record = {
            "schema": "b649-protected-prestart-failure-reconciliation-v1",
            "reason": "PRESTART_FAILURE_NO_MUTATION",
            "stranded_protected_receipt_sha256": supplied_hashes[
                "stranded_protected_receipt_sha256"
            ],
            "stranded_protected_receipt_path": str(receipt_path),
            "stranded_protected_receipt_archive": str(archive_path),
            "reservation_id": reservation_id,
            "operation_id": operation_id,
            "plan_sha256": supplied_hashes["plan_sha256"],
            "original_control_identity": original_control,
            "recovery_control_identity": recovery_control,
            "predecessor_protected_receipt_sha256": predecessor_sha,
            "unchanged_managed_receipt_sha256": managed_identity.sha256,
            "old_live_state": old_live,
        }
        existing_reconciliation: Record | None = None
        if os.path.lexists(reservation_record_path):
            existing_reconciliation, _reconciliation_identity = _load_prestart_reconciliation(
                reservation_record_path
            )
            if any(
                existing_reconciliation.get(key) != value
                for key, value in unsigned_reconciliation.items()
            ):
                raise ProtectedError("reconciliation record exists with conflicting proof")
        reconciliation_file_sha256: str
        if existing_reconciliation is None:
            reconciliation_unsigned = {
                **unsigned_reconciliation,
                "reconciled_at": now(),
            }
            reconciliation = {
                **reconciliation_unsigned,
                "record_sha256": digest(reconciliation_unsigned),
            }
            reconciliation_file_sha256 = hashlib.sha256(
                (canonical(reconciliation) + "\n").encode("utf-8")
            ).hexdigest()
        else:
            reconciliation, reconciliation_file_identity = _load_prestart_reconciliation(
                reservation_record_path
            )
            reconciliation_file_sha256 = reconciliation_file_identity.sha256

        release_evidence: Record = {
            "kind": "PRESTART_FAILURE_NO_MUTATION",
            "verified": True,
            "reconciliation_record_path": str(reservation_record_path),
            "reconciliation_record_sha256": reconciliation_file_sha256,
            "stranded_protected_receipt_sha256": supplied_hashes[
                "stranded_protected_receipt_sha256"
            ],
            "protected_receipt_sha256": predecessor_sha,
            "predecessor_protected_receipt_sha256": predecessor_sha,
            "managed_receipt_sha256": managed_identity.sha256,
        }

        current_control = cutover.control_version()
        if current_control != recovery_control:
            raise ProtectedError("recovery control identity changed during reconciliation proof")
        if owner.get("phase") == "RELEASED":
            if owner.get("release_evidence") != release_evidence:
                raise ProtectedError("owner was released with different reconciliation evidence")
            if existing_reconciliation is None:
                raise ProtectedError("released owner has no sealed reconciliation record")
            return {"status": "ALREADY_RECONCILED", **release_evidence}

        if not os.path.lexists(archive_path):
            # archive_to verifies the exact source bytes and uses a durable
            # link/unlink sequence, so the failed attempt remains recoverable.
            receipt_file.archive_to(
                archive_path.name,
                expected_sha256=supplied_hashes["stranded_protected_receipt_sha256"],
            )
        elif os.path.lexists(receipt_path):
            receipt_file.archive_to(
                archive_path.name,
                expected_sha256=supplied_hashes["stranded_protected_receipt_sha256"],
            )

        if existing_reconciliation is None:
            cutover._write_json(  # pyright: ignore[reportPrivateUsage]
                reservation_record_path, reconciliation, expected=None
            )
            readback, _ = _load_prestart_reconciliation(reservation_record_path)
            if readback != reconciliation:
                raise ProtectedError("reconciliation record readback differs")
        else:
            _, reconciliation_file_identity = _load_prestart_reconciliation(reservation_record_path)
            if (
                reconciliation_file_identity.sha256
                != release_evidence["reconciliation_record_sha256"]
            ):
                raise ProtectedError("existing reconciliation file SHA changed")

        current_control = cutover.control_version()
        if current_control != recovery_control:
            raise ProtectedError("recovery control identity changed before owner release")
        latest = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
        if latest is None or latest[1].key() != owner_file_identity.key():
            raise ProtectedError("durable owner changed after reconciliation proof")
        released = cutover._save_control_owner(  # pyright: ignore[reportPrivateUsage]
            config,
            {**owner, "phase": "RELEASED", "release_evidence": release_evidence},
            expected=owner_file_identity,
        )
        return {"status": "RECONCILED", "owner": released, **release_evidence}


def _validate_cross_control_historical_provenance(
    stranded: Record,
    stranded_identity: Record,
    original_control_head: str,
    original_control_tree: str,
) -> str:
    """Validate the sealed historical control checkout without requiring it to exist."""
    unsigned_receipt = {
        key: value for key, value in stranded.items() if key != "receipt_sha256"
    }
    execution_id = text(stranded.get("execution_id"))
    if (
        execution_id != digest(stranded_identity)
        or stranded.get("receipt_sha256") != digest(unsigned_receipt)
    ):
        raise ProtectedError("historical protected receipt seal or execution identity is invalid")

    try:
        historical_worktree_value = text(stranded_identity.get("control_worktree"))
    except ProtectedError as exc:
        raise ProtectedError("historical control worktree provenance is absent") from exc
    historical_worktree = Path(historical_worktree_value)
    try:
        canonical_worktree = str(historical_worktree.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProtectedError("historical control worktree provenance is not canonical") from exc
    if (
        not historical_worktree.is_absolute()
        or ".." in historical_worktree.parts
        or canonical_worktree != historical_worktree_value
    ):
        raise ProtectedError("historical control worktree provenance is not canonical")

    raw_direct_argv = stranded.get("direct_argv")
    if not isinstance(raw_direct_argv, list):
        raise ProtectedError("historical direct argv provenance is invalid")
    argv_values = cast(list[object], raw_direct_argv)
    if len(argv_values) < 2 or any(not isinstance(argument, str) for argument in argv_values):
        raise ProtectedError("historical direct argv provenance is invalid")
    direct_argv = cast(list[str], argv_values)
    expected_managed_script = str(
        historical_worktree / "tools" / "b649_production_cutover.py"
    )
    if direct_argv[1] != expected_managed_script:
        raise ProtectedError("historical direct argv managed script differs from its control root")
    if stranded_identity.get("interpreter") != direct_argv[0]:
        raise ProtectedError("historical interpreter differs from direct argv")

    def option_value(option: str) -> str:
        indexes = [index for index, value in enumerate(direct_argv[:-1]) if value == option]
        if len(indexes) != 1:
            raise ProtectedError(f"historical direct argv must contain one {option}")
        return direct_argv[indexes[0] + 1]

    try:
        protected_request = json.loads(
            option_value("--protected-request"), object_pairs_hook=unique_object
        )
    except (TypeError, ValueError, ProtectedError) as exc:
        raise ProtectedError("historical protected request is invalid") from exc
    if not isinstance(protected_request, dict):
        raise ProtectedError("historical protected request is invalid")
    protected_request_record = cast(Record, protected_request)
    if (
        set(protected_request_record) != {"identity", "takeover_stale"}
        or type(protected_request_record.get("takeover_stale")) is not bool
        or protected_request_record.get("identity") != stranded_identity
        or option_value("--protected-execution") != execution_id
    ):
        raise ProtectedError("historical protected request differs from the sealed receipt")
    if (
        stranded_identity.get("control_head") != original_control_head
        or stranded_identity.get("control_tree") != original_control_tree
    ):
        raise ProtectedError("historical control identity differs from explicit original version")
    return historical_worktree_value


def cmd_reconcile_prestart_not_started(
    args: argparse.Namespace,
    *,
    runner: cutover.Runner | None = None,
) -> Record:
    """Seal and release one exact same-control or explicitly cross-control incident."""
    selected_runner = cutover.run_command if runner is None else runner
    config = build_reservation_config(args, for_action="apply")
    reservation_id = text(args.reservation_id)
    operation_id = text(args.operation_id)
    try:
        if str(UUID(reservation_id)) != reservation_id:
            raise ValueError
    except ValueError as exc:
        raise ProtectedError("reservation ID must be a canonical UUID") from exc
    if re.fullmatch(r"[0-9a-f]{32}", operation_id) is None:
        raise ProtectedError("operation ID must be a lowercase 32-character digest")
    supplied_hashes = {
        "stranded_protected_receipt_sha256": text(args.stranded_protected_receipt_sha256),
        "managed_receipt_sha256": text(args.managed_receipt_sha256),
        "predecessor_protected_receipt_sha256": text(
            args.predecessor_protected_receipt_sha256
        ),
        "plan_sha256": text(args.plan_sha256),
    }
    for label, value in supplied_hashes.items():
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ProtectedError(f"{label} must be a lowercase SHA256")
    plan_digest = text(args.plan_digest)
    if re.fullmatch(r"[0-9a-f]{64}", plan_digest) is None:
        raise ProtectedError("plan digest must be a lowercase SHA256")

    control_arguments = (
        getattr(args, "original_control_head", None),
        getattr(args, "original_control_tree", None),
        getattr(args, "current_recovery_control_head", None),
        getattr(args, "current_recovery_control_tree", None),
    )
    supplied_control_arguments = tuple(value is not None for value in control_arguments)
    if any(supplied_control_arguments) and not all(supplied_control_arguments):
        raise ProtectedError("cross-control reconciliation requires all four control identities")
    cross_control = all(supplied_control_arguments)
    if cross_control:
        original_control_identity = {
            "head": text(control_arguments[0]),
            "tree": text(control_arguments[1]),
        }
        recovery_control_identity = {
            "head": text(control_arguments[2]),
            "tree": text(control_arguments[3]),
        }
        for identity in (original_control_identity, recovery_control_identity):
            if any(
                re.fullmatch(r"[0-9a-f]{40}", value) is None
                for value in identity.values()
            ):
                raise ProtectedError("control identities must be exact lowercase HEAD/tree values")
        running_control = cutover.control_version()
        source_control_identity = control_identity()
        if (
            original_control_identity == recovery_control_identity
            or running_control != recovery_control_identity
            or source_control_identity
            != (recovery_control_identity["head"], recovery_control_identity["tree"])
        ):
            raise ProtectedError(
                "running recovery control differs from explicit cross-control identities"
            )
    else:
        control = cutover.control_version()
        original_control_identity = {
            "head": control.get("head"),
            "tree": control.get("tree"),
        }
        if any(
            re.fullmatch(r"[0-9a-f]{40}", str(value)) is None
            for value in original_control_identity.values()
        ) or original_control_identity != {
            "head": control_identity()[0],
            "tree": control_identity()[1],
        }:
            raise ProtectedError("same-control reconciliation source identity is invalid")
        recovery_control_identity = dict(original_control_identity)
    control_identity_value = original_control_identity

    receipt_path = config.scheduler_root / RECEIPT_NAME
    receipt_file = ReceiptFile(receipt_path)
    reconciliation_path = _prestart_reconciliation_record_path(config, reservation_id)
    with cutover.CutoverLock(  # pyright: ignore[reportPrivateUsage]
        cutover._control_owner_lock_path(config)  # pyright: ignore[reportPrivateUsage]
    ):
        owner_snapshot = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
        if owner_snapshot is None:
            raise ProtectedError("durable owner is absent")
        owner, owner_file_identity = owner_snapshot
        target = {
            "source_worktree": str(config.source_worktree),
            "head": config.expected_head,
            "tree": config.expected_tree,
            "durable_ref": config.durable_ref,
        }
        expected_owner_identity = {
            "reservation_id": reservation_id,
            "operation_id": operation_id,
            "managed_receipt_sha256": supplied_hashes["managed_receipt_sha256"],
            "control_head": control_identity_value["head"],
            "control_tree": control_identity_value["tree"],
            "action": "apply",
            "target": target,
        }
        if (
            owner.get("reservation_id") != reservation_id
            or owner.get("operation_id") != operation_id
            or owner.get("owner_kind") != "protected"
            or owner.get("action") != "apply"
            or owner.get("phase") not in {"AUTHORIZED_PENDING", "RELEASED"}
            or owner.get("mutation_started") is not False
            or (owner.get("control_head"), owner.get("control_tree"))
            != (control_identity_value["head"], control_identity_value["tree"])
            or owner.get("managed_receipt_sha256")
            != supplied_hashes["managed_receipt_sha256"]
            or cutover._owner_identity(owner)  # pyright: ignore[reportPrivateUsage]
            != expected_owner_identity
            or owner.get("authorization") != expected_owner_identity
        ):
            raise ProtectedError("durable owner does not match the exact same-control operation")

        slot_value: Record | None = None
        slot_sha: str | None = None
        if os.path.lexists(receipt_path):
            slot_value, slot_sha = receipt_file.read_with_sha256()
            if slot_sha != supplied_hashes["stranded_protected_receipt_sha256"]:
                raise ProtectedError("fixed protected receipt SHA differs from the explicit value")
        else:
            for index, archived_path in enumerate(
                receipt_path.parent.glob(f"{receipt_path.stem}.*.superseded.json")
            ):
                if index >= 1024:
                    raise ProtectedError("protected receipt archive lookup exceeds bound")
                try:
                    archived_value, archived_identity, _ = cutover.read_control_json(archived_path)
                except (OSError, ValueError, cutover.CutoverError):
                    continue
                archived_identity_record = record(archived_value.get("identity"))
                if (
                    archived_identity.sha256
                    == supplied_hashes["stranded_protected_receipt_sha256"]
                    and archived_path.name
                    == f"{receipt_path.stem}.{archived_value.get('execution_id')}.superseded.json"
                    and archived_value.get("execution_id") == digest(archived_identity_record)
                    and archived_identity_record.get("reservation_id") == reservation_id
                    and archived_identity_record.get("operation_id") == operation_id
                ):
                    slot_value = archived_value
                    slot_sha = archived_identity.sha256
                    break
            if slot_value is None:
                raise ProtectedError("stranded protected receipt or its exact archive is absent")

        if slot_value is None:
            raise ProtectedError("stranded protected receipt is absent")
        stranded = slot_value
        stranded_identity = record(stranded.get("identity"))
        owner_id_argument = stranded_identity.get("owner_id_argument")
        if type(owner_id_argument) is not bool:
            raise ProtectedError("stranded receipt owner-id argument binding is invalid")
        predecessor_proof = cutover._validate_predecessor_release_evidence(  # pyright: ignore[reportPrivateUsage]
            owner.get("predecessor_release_evidence"), owner
        )
        predecessor_sha = text(predecessor_proof.get("prior_protected_receipt_sha256"))
        if predecessor_sha != supplied_hashes["predecessor_protected_receipt_sha256"]:
            raise ProtectedError("durable v5 predecessor SHA differs from the explicit value")

        plan_file = Path(text(args.plan_file))
        claim_root = repository_claim_root()
        request = make_request(
            config,
            Path(text(args.legacy_worktree)),
            text(args.legacy_head),
            text(args.legacy_tree),
            plan_file,
            claim_root,
            reservation_id=reservation_id,
            operation_id=operation_id,
            prior_execution_receipt_sha256=predecessor_sha,
            managed_receipt_sha256=supplied_hashes["managed_receipt_sha256"],
            owner_id_argument=owner_id_argument,
        )
        expected_stranded_identity = {
            **request.identity,
            "control_head": original_control_identity["head"],
            "control_tree": original_control_identity["tree"],
        }
        if cross_control:
            expected_stranded_identity["control_worktree"] = (
                _validate_cross_control_historical_provenance(
                    stranded,
                    stranded_identity,
                    text(original_control_identity["head"]),
                    text(original_control_identity["tree"]),
                )
            )
        plan, plan_identity, _ = cutover.read_control_json(plan_file)
        if (
            plan_identity.sha256 != supplied_hashes["plan_sha256"]
            or plan.get("plan_digest") != plan_digest
            or request.plan_sha256 != supplied_hashes["plan_sha256"]
            or request.plan_digest != plan_digest
            or expected_stranded_identity != stranded_identity
        ):
            raise ProtectedError("stranded operation identity or exact plan differs")
        cutover.validate_protected_plan(config, plan)
        plan_old = record(record(plan.get("source")).get("old"))
        plan_new = record(record(plan.get("source")).get("new"))
        if (
            plan_new.get("role") != "new"
            or plan_new.get("source_worktree") != str(config.source_worktree)
            or plan_new.get("head") != config.expected_head
            or plan_new.get("tree") != config.expected_tree
            or plan_new.get("durable_ref") != config.durable_ref
            or plan_new.get("clean") is not True
            or (plan_old.get("source_worktree"), plan_old.get("head"), plan_old.get("tree"))
            != (str(request.legacy_worktree), request.legacy_head, request.legacy_tree)
        ):
            raise ProtectedError("stranded plan does not bind the exact OLD and target sources")

        execution_id = text(stranded.get("execution_id"))
        archive_path = receipt_path.with_name(
            f"{receipt_path.stem}.{execution_id}.superseded.json"
        )
        old_incomplete = (
            stranded.get("status") == "INCOMPLETE_OR_AMBIGUOUS"
            and stranded.get("result_status") == "INCOMPLETE_OR_AMBIGUOUS"
            and type(stranded.get("exit_code")) is int
            and stranded.get("child_exit_code") is None
            and "child_started_at" in stranded
            and "child_completed_at" not in stranded
        )
        captured_not_started = (
            stranded.get("status") == "FAILED"
            and stranded.get("result_status") == "NOT_STARTED"
            and type(stranded.get("exit_code")) is int
            and stranded.get("exit_code") != 0
            and stranded.get("child_exit_code") == stranded.get("exit_code")
            and "child_completed_at" in stranded
        )
        if (
            stranded.get("schema_version") != SCHEMA
            or stranded.get("task_key") != TASK_KEY
            or stranded.get("phase") != "COMPLETED"
            or stranded.get("receipt_sha256")
            != digest({key: value for key, value in stranded.items() if key != "receipt_sha256"})
            or execution_id != digest(stranded_identity)
            or slot_sha != supplied_hashes["stranded_protected_receipt_sha256"]
            or not (old_incomplete or captured_not_started)
            or stranded.get("managed_receipt") is not None
            or (stranded_identity.get("reservation_id"), stranded_identity.get("operation_id"))
            != (reservation_id, operation_id)
            or stranded_identity.get("action") != "apply"
            or stranded_identity.get("task_key") != TASK_KEY
            or stranded_identity.get("execution_receipt_path") != str(receipt_path)
            or stranded_identity.get("managed_receipt_path") != str(config.receipt_path)
            or stranded_identity.get("managed_receipt_sha256")
            != supplied_hashes["managed_receipt_sha256"]
            or stranded_identity.get("prior_execution_receipt_sha256") != predecessor_sha
            or stranded_identity.get("plan_sha256") != supplied_hashes["plan_sha256"]
            or stranded_identity.get("plan_digest") != plan_digest
            or stranded_identity.get("claim_root") != str(claim_root)
            or stranded_identity.get("control_head") != control_identity_value["head"]
            or stranded_identity.get("control_tree") != control_identity_value["tree"]
        ):
            raise ProtectedError(
                "protected receipt is not the exact no-mutation NOT_STARTED terminal"
            )
        saved_predecessor_link = stranded.get("unchanged_predecessor_managed_receipt")
        if saved_predecessor_link is not None and saved_predecessor_link != {
            "path": str(config.receipt_path),
            "sha256": supplied_hashes["managed_receipt_sha256"],
            "status": "SUCCESS",
        }:
            raise ProtectedError("protected receipt predecessor link differs from the v5 receipt")
        legacy_missing_mutation_summary = False
        if captured_not_started or old_incomplete:
            stream_name = "stdout" if captured_not_started else "process_stdout"
            output_evidence = record(stranded.get(stream_name))
            output_text_value = output_evidence.get("text")
            if (
                not isinstance(output_text_value, str)
                or output_evidence.get("truncated") is not False
                or output_evidence.get("bytes") != len(output_text_value.encode("utf-8"))
                or output_evidence.get("sha256")
                != hashlib.sha256(output_text_value.encode("utf-8")).hexdigest()
            ):
                raise ProtectedError("captured NOT_STARTED stdout is absent")
            output_text = output_text_value
            operation_result: Record | None = None
            for line in reversed(output_text.splitlines()):
                try:
                    candidate = record(json.loads(line))
                except (TypeError, ValueError):
                    continue
                if candidate.get("status") == "NOT_STARTED":
                    operation_result = candidate
                    break
            if (
                operation_result is None
                or operation_result.get("command") != "apply"
                or operation_result.get("task") != cutover.TASK_ID
                or operation_result.get("actions") != []
            ):
                raise ProtectedError("captured NOT_STARTED result does not prove zero mutation")
            if "mutation_summary" not in operation_result:
                if not old_incomplete:
                    raise ProtectedError(
                        "captured NOT_STARTED result does not prove zero mutation"
                    )
                # Historical old_incomplete captures predate mutation_summary on
                # every NOT_STARTED exit. Accept this classification only after
                # the durable and live no-mutation proof below has completed.
                legacy_missing_mutation_summary = True
            else:
                mutation_summary = record(operation_result.get("mutation_summary"))
                expected_mutation_summary = {
                    "launchd": False,
                    "plist": False,
                    "control_files": False,
                }
                if mutation_summary != expected_mutation_summary or any(
                    type(mutation_summary.get(field)) is not bool
                    for field in expected_mutation_summary
                ):
                    raise ProtectedError(
                        "captured NOT_STARTED result does not prove zero mutation"
                    )

        if stranded_identity.get("target") != expected_owner_identity["target"]:
            raise ProtectedError("stranded protected receipt target differs from the owner")
        if claims.ClaimStore(claim_root).inspect(TASK_KEY).get("status") != "ABSENT":
            raise ProtectedError("ClaimStore is not absent")
        if os.path.lexists(config.scheduler_root / ROLLBACK_RECEIPT_NAME):
            raise ProtectedError("protected rollback receipt makes predecessor history ambiguous")

        managed, managed_identity, _ = cutover.read_control_json(config.receipt_path)
        if (
            managed_identity.sha256 != supplied_hashes["managed_receipt_sha256"]
            or managed_identity.sha256 != owner.get("managed_receipt_sha256")
            or managed.get("schema_version") != cutover.RECEIPT_SCHEMA_VERSION
            or managed.get("task") != cutover.TASK_ID
            or managed.get("phase") != "COMPLETED"
            or managed.get("status") != "SUCCESS"
            or managed.get("operation_id") == operation_id
        ):
            raise ProtectedError("current managed receipt is not the unchanged prior SUCCESS")
        if managed.get("operation_id") != predecessor_proof.get("prior_operation_id"):
            raise ProtectedError("current managed SUCCESS does not match the sealed predecessor")

        predecessor_archive = _find_archived_prior_receipt(
            receipt_path, lambda value: value == predecessor_sha
        )
        if predecessor_archive is None:
            raise ProtectedError("archived v5 protected SUCCESS predecessor is absent")
        predecessor_path = Path(text(predecessor_archive.get("path")))
        predecessor, predecessor_identity, _ = cutover.read_control_json(predecessor_path)
        predecessor_identity_record = record(predecessor.get("identity"))
        predecessor_target = record(predecessor_identity_record.get("target"))
        predecessor_owner_identity = {
            "reservation_id": predecessor_identity_record.get("reservation_id"),
            "operation_id": predecessor_identity_record.get("operation_id"),
            "managed_receipt_sha256": predecessor_identity_record.get("managed_receipt_sha256"),
            "control_head": predecessor_identity_record.get("control_head"),
            "control_tree": predecessor_identity_record.get("control_tree"),
            "action": "apply",
            "target": predecessor_target,
        }
        expected_predecessor_authorization = {
            key: value for key, value in predecessor_owner_identity.items() if key != "owner_kind"
        }
        predecessor_release = record(predecessor_proof.get("prior_release_evidence"))
        predecessor_link = record(predecessor.get("managed_receipt"))
        if (
            predecessor_identity.sha256 != predecessor_sha
            or predecessor_identity_record.get("reservation_id")
            != predecessor_proof.get("prior_reservation_id")
            or predecessor_identity_record.get("operation_id")
            != predecessor_proof.get("prior_operation_id")
            or predecessor_identity_record.get("plan_digest") != managed.get("plan_digest")
            or predecessor_identity_record.get("operation_id") != managed.get("operation_id")
            or predecessor_proof.get("prior_authorization_sha256")
            != digest(expected_predecessor_authorization)
            or predecessor_release.get("verified") is not True
            or predecessor_release.get("protected_receipt_sha256") != predecessor_sha
            or predecessor_release.get("managed_receipt_sha256") != managed_identity.sha256
            or predecessor_link.get("path") != str(config.receipt_path)
            or predecessor_link.get("sha256") != managed_identity.sha256
            or predecessor_link.get("status") != "SUCCESS"
            or (plan_old.get("source_worktree"), plan_old.get("head"), plan_old.get("tree"))
            != (
                predecessor_target.get("source_worktree"),
                predecessor_target.get("head"),
                predecessor_target.get("tree"),
            )
        ):
            raise ProtectedError("archived v5 SUCCESS does not match its saved owner proof")
        cutover._verify_protected_owner_receipt(  # pyright: ignore[reportPrivateUsage]
            predecessor,
            path=receipt_path,
            bound_identity=predecessor_owner_identity,
            successful=True,
        )
        if managed.get("plan_digest") != predecessor_identity_record.get("plan_digest"):
            raise ProtectedError("managed SUCCESS is not the archived v5 operation")

        old_live = _prove_plan_old_live(config, plan, selected_runner)
        if (
            record(old_live.get("source")) != plan_old
            or record(old_live.get("runtime")) != record(record(plan.get("runtime")).get("old"))
            or record(old_live.get("target_source")) == record(old_live.get("source"))
            or record(old_live.get("target_runtime")) == record(old_live.get("runtime"))
        ):
            raise ProtectedError("live state does not prove OLD runtime with target still inactive")
        prior_config = replace(
            config,
            source_worktree=Path(text(predecessor_target.get("source_worktree"))),
            expected_head=text(predecessor_target.get("head")),
            expected_tree=text(predecessor_target.get("tree")),
            durable_ref=text(predecessor_target.get("durable_ref")),
        )
        cutover.validate_protected_plan(
            prior_config, cutover.receipt_to_plan(prior_config, managed)
        )
        cutover.verify_completed_receipt_live(
            prior_config,
            managed,
            successor_old_plist_identity=record(plan.get("prestate")).get("old_plist_identity"),
            runner=selected_runner,
        )

        if legacy_missing_mutation_summary and not old_incomplete:
            raise ProtectedError("legacy NOT_STARTED capture shape is not exact")

        if archive_path != receipt_path.with_name(
            f"{receipt_path.stem}.{execution_id}.superseded.json"
        ):
            raise ProtectedError("stranded receipt archive identity differs")
        unsigned_reconciliation: Record = {
            "schema": PRESTART_NOT_STARTED_RECONCILIATION_SCHEMA,
            "reason": PRESTART_NOT_STARTED_RELEASE_KIND,
            "stranded_protected_receipt_sha256": supplied_hashes[
                "stranded_protected_receipt_sha256"
            ],
            "stranded_protected_receipt_path": str(receipt_path),
            "stranded_protected_receipt_archive": str(archive_path),
            "reservation_id": reservation_id,
            "operation_id": operation_id,
            "plan_sha256": supplied_hashes["plan_sha256"],
            "plan_digest": plan_digest,
            "control_identity": control_identity_value,
            "predecessor_protected_receipt_sha256": predecessor_sha,
            "unchanged_managed_receipt_sha256": managed_identity.sha256,
            "owner_authorization": expected_owner_identity,
            "claim_store_status": "ABSENT",
            "rollback_receipt_absent": True,
            "owner_mutation_started": False,
            "old_live_state": old_live,
        }
        if cross_control:
            unsigned_reconciliation.update(
                {
                    "original_control_identity": original_control_identity,
                    "recovery_control_identity": recovery_control_identity,
                }
            )
        existing_reconciliation: Record | None = None
        if os.path.lexists(reconciliation_path):
            existing_reconciliation, _ = _load_prestart_reconciliation(reconciliation_path)
            if any(
                existing_reconciliation.get(key) != value
                for key, value in unsigned_reconciliation.items()
            ):
                raise ProtectedError("reconciliation record exists with conflicting proof")
        if existing_reconciliation is None:
            reconciliation_unsigned = {**unsigned_reconciliation, "reconciled_at": now()}
            reconciliation = {
                **reconciliation_unsigned,
                "record_sha256": digest(reconciliation_unsigned),
            }
            cutover._write_json(  # pyright: ignore[reportPrivateUsage]
                reconciliation_path, reconciliation, expected=None
            )
            readback, reconciliation_identity = _load_prestart_reconciliation(reconciliation_path)
            if readback != reconciliation:
                raise ProtectedError("NOT_STARTED reconciliation readback differs")
        else:
            reconciliation, reconciliation_identity = _load_prestart_reconciliation(
                reconciliation_path
            )

        release_evidence: Record = {
            "kind": PRESTART_NOT_STARTED_RELEASE_KIND,
            "verified": True,
            "reconciliation_record_path": str(reconciliation_path),
            "reconciliation_record_sha256": reconciliation_identity.sha256,
            "stranded_protected_receipt_sha256": supplied_hashes[
                "stranded_protected_receipt_sha256"
            ],
            "protected_receipt_sha256": predecessor_sha,
            "predecessor_protected_receipt_sha256": predecessor_sha,
            "managed_receipt_sha256": managed_identity.sha256,
        }

        if not os.path.lexists(archive_path) or os.path.lexists(receipt_path):
            receipt_file.archive_to(
                archive_path.name,
                expected_sha256=supplied_hashes["stranded_protected_receipt_sha256"],
            )
        archived_stranded, archived_identity, _ = cutover.read_control_json(archive_path)
        if (
            archived_identity.sha256 != supplied_hashes["stranded_protected_receipt_sha256"]
            or archived_stranded != stranded
            or os.path.lexists(receipt_path)
        ):
            raise ProtectedError("stranded protected receipt was not archived unchanged")

        current_control = cutover.control_version()
        if current_control != recovery_control_identity:
            raise ProtectedError("recovery control identity changed before owner release")
        if cross_control and control_identity() != (
            recovery_control_identity["head"],
            recovery_control_identity["tree"],
        ):
            raise ProtectedError("recovery source identity changed before owner release")
        if claims.ClaimStore(claim_root).inspect(TASK_KEY).get("status") != "ABSENT":
            raise ProtectedError("ClaimStore appeared before owner release")
        if os.path.lexists(config.scheduler_root / ROLLBACK_RECEIPT_NAME):
            raise ProtectedError("rollback receipt appeared before owner release")
        _, managed_identity_after, _ = cutover.read_control_json(config.receipt_path)
        old_live_after = _prove_plan_old_live(config, plan, selected_runner)
        if (
            managed_identity_after.sha256 != supplied_hashes["managed_receipt_sha256"]
            or old_live_after != old_live
        ):
            raise ProtectedError("OLD live authority changed before owner release")
        latest = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
        if latest is None or latest[1].key() != owner_file_identity.key():
            raise ProtectedError("durable owner changed after reconciliation proof")
        if owner.get("phase") == "RELEASED":
            if owner.get("release_evidence") != release_evidence:
                raise ProtectedError("owner was released with different NOT_STARTED evidence")
            return {"status": "ALREADY_RECONCILED", **release_evidence}
        released = cutover._save_control_owner(  # pyright: ignore[reportPrivateUsage]
            config,
            {**owner, "phase": "RELEASED", "release_evidence": release_evidence},
            expected=owner_file_identity,
        )
        return {"status": "RECONCILED", "owner": released, **release_evidence}


def launch(
    request: Request | RollbackRequest,
    *,
    runner: cutover.Runner = cutover.run_command,
) -> Record:
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
            if execution_exists and cutover.control_owner_authorization(
                owner
            ) == request_owner_authorization(candidate):
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
    if (
        isinstance(request, Request)
        and owner.get("phase") == "AUTHORIZED_PENDING"
        and _existing_receipt_sha256(request.config.receipt_path) != request.managed_receipt_sha256
    ):
        raise ProtectedError("managed receipt changed after authorization")
    success_status = ROLLBACK_SUCCESS if request.action == "rollback" else "SUCCESS"
    incomplete_status = (
        ROLLBACK_INCOMPLETE if request.action == "rollback" else "INCOMPLETE_OR_AMBIGUOUS"
    )
    store = ReceiptClaimStore(request)
    prior = receipt_file.read()
    if (
        prior is not None
        and prior.get("identity") != request.identity
        and supersede_prior_execution_receipt(request, receipt_file, prior)
    ):
        store.superseded_receipt = {
            "path": str(
                request.receipt_path.with_name(
                    f"{request.receipt_path.stem}.{prior['execution_id']}.superseded.json"
                )
            ),
            "execution_id": prior["execution_id"],
            "sha256": request.identity["prior_execution_receipt_sha256"],
        }
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
    if isinstance(request, Request) and request.prior_execution_receipt_sha256 is not None:
        store.superseded_receipt = _find_archived_prior_receipt(
            request.receipt_path, lambda sha: sha == request.prior_execution_receipt_sha256
        )
        if store.superseded_receipt is None:
            raise ProtectedError("authorized prior receipt archive is absent or changed")
    if owner.get("phase") in {"MUTATION_IN_PROGRESS", "TERMINAL_CAPTURE_PENDING"}:
        raise ProtectedError(
            "started owner has no reusable protected terminal receipt; reconcile exact evidence"
        )
    code = store.run(
        TASK_KEY,
        request.managed_argv(),
        takeover_stale=request.takeover_stale,
        capture_output=store.capture_process_output,
    )
    process_stdout = store.process_stdout.evidence()
    process_stderr = store.process_stderr.evidence()
    sys.stdout.write(cast(str, process_stdout["text"]))
    sys.stderr.write(cast(str, process_stderr["text"]))
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
    prestart_evidence: Record | None = None
    prestart_error: str | None = None
    if isinstance(request, Request) and _is_prestart_failure_candidate(staged, code):
        try:
            prestart_evidence = _prestart_failure_evidence(
                request,
                store,
                staged,
                code,
                runner=runner,
            )
        except Exception as exc:
            prestart_error = f"{type(exc).__name__}: {exc}"
    link: Record | None
    unchanged_predecessor_link: Record | None = None
    if prestart_evidence is not None:
        link_value = prestart_evidence.get("managed_receipt")
        link = None if link_value is None else record(link_value)
        terminal = {
            **staged,
            "result_status": "FAILED",
            "managed_receipt": link,
            "prestart_failure_evidence": prestart_evidence,
        }
        status = "FAILED"
    else:
        try:
            link, unchanged_predecessor_link = managed_receipt_links(request)
        except (OSError, ValueError, ProtectedError, cutover.CutoverError):
            # A changed or missing managed receipt cannot be relinked. The
            # protected terminal result remains durable but its linkage is not
            # promoted to authority.
            link = None
            unchanged_predecessor_link = None
    if (
        prestart_evidence is None
        and staged.get("phase") == "CHILD_COMPLETED"
        and staged.get("child_exit_code") == code
    ):
        if staged.get("managed_receipt") != link:
            raise ProtectedError("managed terminal receipt changed")
        if staged.get("unchanged_predecessor_managed_receipt") != unchanged_predecessor_link:
            raise ProtectedError("unchanged managed predecessor receipt changed")
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
    elif prestart_evidence is None:
        # ClaimStore can observe a child that never reached the protected
        # wrapper (for example, an interpreter/exec failure).  Preserve the
        # current receipt-bound managed link when it is still readable while
        # recording the protected result as incomplete.
        terminal = {
            **staged,
            "result_status": incomplete_status,
            "managed_receipt": link,
        }
        if unchanged_predecessor_link is not None:
            terminal["unchanged_predecessor_managed_receipt"] = unchanged_predecessor_link
        if prestart_error is not None:
            terminal["prestart_failure_classification"] = "INCOMPLETE_OR_AMBIGUOUS"
            terminal["prestart_failure_reason"] = prestart_error[:MAX_STREAM_BYTES]
    saved = receipt_file.write(
        {
            **terminal,
            "status": status,
            "phase": "COMPLETED",
            "completed_at": now(),
            "exit_code": code,
            "process_stdout": process_stdout,
            "process_stderr": process_stderr,
        },
        expected=staged,
    )
    readback = receipt_file.read()
    if readback != saved:
        raise ProtectedError("protected terminal receipt verification failed")
    predecessor_link_value = saved.get("unchanged_predecessor_managed_receipt")
    predecessor_link = (
        {} if predecessor_link_value is None else record(predecessor_link_value)
    )
    if (
        isinstance(request, Request)
        and status == "FAILED"
        and saved.get("result_status") == "NOT_STARTED"
        and saved.get("managed_receipt") is None
        and predecessor_link.get("sha256") == request.managed_receipt_sha256
    ):
        return {
            **saved,
            "reused": False,
            "owner_release": "RETAINED_FOR_RECONCILIATION",
        }
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


def build_reservation_config(args: argparse.Namespace, *, for_action: str) -> cutover.CutoverConfig:
    """Hermetic seam: the durable-owner-keyed config CLI commands reserve/inspect against.

    Tests redirect the whole two-stage lifecycle to temporary paths by
    monkeypatching this one function, exactly as ``cutover.protected_config``
    already redirects the gated child's own config construction.
    """
    if for_action == "rollback":
        if args.legacy_worktree is None or args.receipt_file is None:
            raise ProtectedError(
                "--legacy-worktree and --receipt-file are required for --for rollback"
            )
        return cutover.CutoverConfig(
            source_worktree=Path(args.legacy_worktree),
            receipt_path=Path(args.receipt_file),
            strict_release_layout=True,
        )
    if args.source_worktree is None or args.expected_head is None or args.expected_tree is None:
        raise ProtectedError(
            "--source-worktree, --expected-head and --expected-tree are required for --for apply"
        )
    return cutover.CutoverConfig(
        source_worktree=Path(args.source_worktree),
        expected_head=args.expected_head,
        expected_tree=args.expected_tree,
        durable_ref=f"refs/heads/runtime/b649/{args.expected_head}",
        strict_release_layout=True,
    )


def status_report(config: cutover.CutoverConfig) -> Record:
    """Read-only owner/receipt snapshot; performs no mutation of any kind."""
    owner = cutover.inspect_control_owner(config)
    managed_sha = _existing_receipt_sha256(config.receipt_path)
    apply_sha = _existing_receipt_sha256(config.scheduler_root / RECEIPT_NAME)
    rollback_sha = _existing_receipt_sha256(config.scheduler_root / ROLLBACK_RECEIPT_NAME)
    return {
        "status": "OK",
        "owner": owner,
        "managed_receipt": {
            "path": str(config.receipt_path),
            "sha256": managed_sha,
            "exists": managed_sha is not None,
        },
        "protected_apply_receipt": {
            "path": str(config.scheduler_root / RECEIPT_NAME),
            "sha256": apply_sha,
            "exists": apply_sha is not None,
        },
        "protected_rollback_receipt": {
            "path": str(config.scheduler_root / ROLLBACK_RECEIPT_NAME),
            "sha256": rollback_sha,
            "exists": rollback_sha is not None,
        },
    }


def cmd_status(args: argparse.Namespace) -> Record:
    config = build_reservation_config(args, for_action=text(args.target_action))
    return status_report(config)


def cmd_authorize(args: argparse.Namespace) -> Record:
    config = build_reservation_config(args, for_action=text(args.target_action))
    reservation_id = text(args.reservation_id)
    target: Record = {
        "source_worktree": text(args.target_source_worktree),
        "head": text(args.target_head),
        "tree": text(args.target_tree),
    }
    if args.target_durable_ref is not None:
        target["durable_ref"] = text(args.target_durable_ref)
    authorization: Record = {
        "reservation_id": reservation_id,
        "operation_id": text(args.operation_id),
        "managed_receipt_sha256": args.managed_receipt_sha256,
        "control_head": text(args.control_head),
        "control_tree": text(args.control_tree),
        "action": text(args.target_action),
        "target": target,
    }
    # Live re-verification the durable owner alone does not perform: the
    # authorization must match the managed receipt's actual current bytes,
    # not merely the bind-time snapshot the owner file already carries.
    live_managed_sha = _existing_receipt_sha256(config.receipt_path)
    if live_managed_sha != authorization["managed_receipt_sha256"]:
        raise ProtectedError(
            "owner authorization managed receipt SHA differs from the live managed receipt"
        )
    return cutover.authorize_control_owner(config, reservation_id, authorization)


def cmd_abandon(args: argparse.Namespace) -> Record:
    config = build_reservation_config(args, for_action=text(args.target_action))
    reservation_id = text(args.reservation_id)
    owner = cutover.inspect_control_owner(config)
    if owner is None or owner.get("reservation_id") != reservation_id:
        raise ProtectedError("durable control owner is absent or a different reservation")
    live_control = cutover.control_version()
    if owner.get("phase") != "ABANDONED":
        cutover.reconcile_control_owner(
            config,
            reservation_id,
            disposition="ABANDON_BEFORE_MUTATION",
            version=live_control,
            observed_managed_receipt_sha256=cast(str | None, args.observed_managed_receipt_sha256),
        )
    return cutover.reconcile_control_owner(
        config,
        reservation_id,
        disposition="RELEASE_ABANDONED",
        version=live_control,
    )


def _add_reservation_lookup_arguments(sub: argparse.ArgumentParser) -> None:
    """Explicit, non-defaulting reservation identity: caller states which target.

    Every field here is optional at the argparse level because exactly one
    shape (apply or rollback) is required depending on ``--for``; the
    required subset is enforced by ``build_reservation_config`` so that
    nothing silently falls back to the current owner, latest receipt, or
    current target.
    """
    sub.add_argument("--for", dest="target_action", choices=("apply", "rollback"), required=True)
    sub.add_argument("--source-worktree")
    sub.add_argument("--expected-head")
    sub.add_argument("--expected-tree")
    sub.add_argument("--legacy-worktree")
    sub.add_argument("--receipt-file")


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
    status_parser = commands.add_parser("status", allow_abbrev=False)
    _add_reservation_lookup_arguments(status_parser)
    authorize_parser = commands.add_parser("authorize", allow_abbrev=False)
    _add_reservation_lookup_arguments(authorize_parser)
    for name in (
        "reservation-id",
        "operation-id",
        "control-head",
        "control-tree",
        "target-source-worktree",
        "target-head",
        "target-tree",
    ):
        authorize_parser.add_argument("--" + name, required=True)
    authorize_parser.add_argument("--managed-receipt-sha256")
    authorize_parser.add_argument("--target-durable-ref")
    abandon_parser = commands.add_parser("abandon", allow_abbrev=False)
    _add_reservation_lookup_arguments(abandon_parser)
    abandon_parser.add_argument("--reservation-id", required=True)
    abandon_parser.add_argument("--observed-managed-receipt-sha256")
    reconcile_parser = commands.add_parser("reconcile-prestart-failure", allow_abbrev=False)
    for name in (
        "source-worktree",
        "expected-head",
        "expected-tree",
        "legacy-worktree",
        "legacy-head",
        "legacy-tree",
        "plan-file",
        "reservation-id",
        "operation-id",
        "stranded-protected-receipt-sha256",
        "managed-receipt-sha256",
        "predecessor-protected-receipt-sha256",
        "original-control-head",
        "original-control-tree",
        "current-recovery-control-head",
        "current-recovery-control-tree",
        "plan-sha256",
    ):
        reconcile_parser.add_argument("--" + name, required=True)
    not_started_parser = commands.add_parser("reconcile-prestart-not-started", allow_abbrev=False)
    for name in (
        "source-worktree",
        "expected-head",
        "expected-tree",
        "legacy-worktree",
        "legacy-head",
        "legacy-tree",
        "plan-file",
        "reservation-id",
        "operation-id",
        "stranded-protected-receipt-sha256",
        "managed-receipt-sha256",
        "predecessor-protected-receipt-sha256",
        "plan-sha256",
        "plan-digest",
    ):
        not_started_parser.add_argument("--" + name, required=True)
    for name in (
        "original-control-head",
        "original-control-tree",
        "current-recovery-control-head",
        "current-recovery-control-tree",
    ):
        not_started_parser.add_argument("--" + name)
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    selected = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(selected)
    try:
        if args.action == "status":
            print(canonical(cmd_status(args)))
            return 0
        if args.action == "authorize":
            print(canonical(cmd_authorize(args)))
            return 0
        if args.action == "abandon":
            print(canonical(cmd_abandon(args)))
            return 0
        if args.action == "reconcile-prestart-failure":
            result = cmd_reconcile_prestart_failure(args)
            print(canonical(result))
            return 0 if result["status"] in {"RECONCILED", "ALREADY_RECONCILED"} else 74
        if args.action == "reconcile-prestart-not-started":
            result = cmd_reconcile_prestart_not_started(args)
            print(canonical(result))
            return 0 if result["status"] in {"RECONCILED", "ALREADY_RECONCILED"} else 74
        version = cutover.control_version()
        if args.action == "rollback":
            reservation_config = build_reservation_config(args, for_action="rollback")
            reservation_target: cutover.Record = {
                "source_worktree": args.legacy_worktree,
                "head": args.legacy_head,
                "tree": args.legacy_tree,
            }
        else:
            reservation_config = build_reservation_config(args, for_action="apply")
            reservation_target = {
                "source_worktree": args.source_worktree,
                "head": args.expected_head,
                "tree": args.expected_tree,
                "durable_ref": reservation_config.durable_ref,
            }
        prior_owner = cutover.inspect_control_owner(reservation_config)
        retired_v2_request: Request | None = None
        retirement_v2_path = (
            reservation_config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
        )
        if os.path.lexists(retirement_v2_path):
            if args.action != "apply":
                raise ProtectedError(
                    "v2 retirement evidence permits only its exact apply successor"
                )
            retired_v2_request = _recover_v2_successor_request(
                reservation_config,
                Path(args.legacy_worktree),
                args.legacy_head,
                args.legacy_tree,
                Path(args.plan_file),
                repository_claim_root(),
                prior_owner,
                prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
                takeover_stale=args.takeover_stale,
            )
        prior_execution_path = reservation_config.scheduler_root / (
            ROLLBACK_RECEIPT_NAME if args.action == "rollback" else RECEIPT_NAME
        )
        failed_predecessor_sha: str | None = None
        prestart_successor_predecessor_sha: str | None = None
        prior_execution: Record | None = None
        if args.action == "apply":
            failed_predecessor_sha = _failed_terminal_predecessor_receipt_sha256(
                prior_owner, reservation_config
            )
            prestart_successor_predecessor_sha: str | None = None
            if failed_predecessor_sha is None:
                prestart_successor_predecessor_sha = _prestart_successor_predecessor_receipt_sha256(
                    reservation_config,
                    prior_owner,
                    claim_root=repository_claim_root(),
                    runner=cutover.run_command,
                )
            if os.path.lexists(prior_execution_path):
                prior_execution = ReceiptFile(prior_execution_path).read()
                if prior_execution is None:
                    raise ProtectedError("prior execution disappeared before reservation")
                if (
                    prior_execution.get("status") == "FAILED"
                    and failed_predecessor_sha is None
                    and prestart_successor_predecessor_sha is None
                ):
                    raise ProtectedError(
                        "failed protected receipt is outside the exact successor bridge"
                    )
        released_replay = prior_owner is not None and os.path.lexists(prior_execution_path)
        if released_replay and args.action == "apply" and prior_owner is not None:
            if prior_execution is None:
                raise ProtectedError("prior execution disappeared before reservation")
            prior_link = prior_execution.get("managed_receipt")
            prior_identity = record(prior_execution.get("identity"))
            released_replay = (
                prior_identity.get("reservation_id") == prior_owner.get("reservation_id")
                and prior_identity.get("plan_sha256")
                == _existing_receipt_sha256(Path(args.plan_file))
                and isinstance(prior_link, dict)
                and cast(Record, prior_link).get("sha256")
                == _existing_receipt_sha256(reservation_config.receipt_path)
            )
        if failed_predecessor_sha is not None:
            released_replay = False
        prepared_request: Request | None = None
        predecessor_release_evidence: Record | None = None
        recovered_predecessor_sha: str | None | _Unset = _UNSET
        if args.action == "apply" and failed_predecessor_sha is not None:
            recovered_predecessor_sha = failed_predecessor_sha
        elif args.action == "apply" and prestart_successor_predecessor_sha is not None:
            recovered_predecessor_sha = prestart_successor_predecessor_sha
        elif args.action == "apply" and not os.path.lexists(prior_execution_path):
            recovered_predecessor_sha = _reconciled_predecessor_receipt_sha256(
                reservation_config, prior_owner
            )
        if args.action == "apply" and (
            prior_owner is None or (prior_owner.get("phase") == "RELEASED" and not released_replay)
        ):
            if retired_v2_request is not None:
                prepared_request = retired_v2_request
            else:
                reservation_id = str(uuid4())
                prepared_request = make_request(
                    reservation_config,
                    Path(args.legacy_worktree),
                    args.legacy_head,
                    args.legacy_tree,
                    Path(args.plan_file),
                    repository_claim_root(),
                    takeover_stale=args.takeover_stale,
                    reservation_id=reservation_id,
                    owner_id_argument=False,
                    prior_execution_receipt_sha256=recovered_predecessor_sha,
                )
            predecessor_release_evidence = _require_released_success_evidence(
                prepared_request, prior_owner
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
        elif prior_owner is not None and released_replay:
            reservation_id = text(prior_owner.get("reservation_id"))
            owner = prior_owner
        else:
            if prepared_request is not None:
                predecessor_live_verifier: Callable[[], None] | None = None
                if (
                    prior_owner is not None
                    and predecessor_release_evidence is not None
                    and predecessor_release_evidence.get("retired_failed_terminal_evidence")
                    is not None
                ):
                    predecessor_live_verifier = _failed_terminal_bridge_live_verifier(
                        prepared_request,
                        prior_owner,
                        predecessor_release_evidence,
                        runner=cutover.run_command,
                    )
                owner = cutover.acquire_control_owner(
                    reservation_config,
                    action=args.action,
                    target=reservation_target,
                    owner_kind="protected",
                    reservation_id=text(prepared_request.reservation_id),
                    version=version,
                    operation_id=prepared_request.operation_id,
                    managed_receipt_sha256=prepared_request.managed_receipt_sha256,
                    predecessor_release_evidence=predecessor_release_evidence,
                    predecessor_live_verifier=predecessor_live_verifier,
                )
                reservation_id = text(owner.get("reservation_id"))
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
            new_source = record(record(record(managed.get("prestate")).get("new_source")))
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
            config = reservation_config
            # Once this reservation has already bound an operation identity,
            # keep it and its managed-receipt snapshot fixed rather than
            # re-deriving from current disk state: a successful mutation
            # writes its own managed receipt, which a fresh read on the next
            # resume/replay call would otherwise mistake for new input. A
            # bound managed-receipt SHA of None is itself meaningful (no
            # managed receipt existed yet at first bind) and must still be
            # held fixed, so the gate is whether binding already happened
            # (operation_id set), not whether the value itself is None.
            bound_operation_id = owner.get("operation_id")
            already_bound = bound_operation_id is not None
            if prepared_request is not None:
                request = prepared_request
            else:
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
                    managed_receipt_sha256=(
                        cast(str | None, owner.get("managed_receipt_sha256"))
                        if already_bound
                        else _UNSET
                    ),
                )
            if already_bound and request.operation_id != bound_operation_id:
                raise ProtectedError("bound operation identity differs from plan/prior receipt")
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
