"""Protected cutover acceptance: fake launchd, isolated files and real ClaimStore gates.

The fake Popen replaces only the operating-system process boundary. ClaimStore's
atomic acquisition, pipe gate, durable child metadata and release execute unchanged.
The existing ClaimStore suite additionally exercises these with real OS children.
"""

# Deliberate fault injection into the existing claim/I/O seams.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import multiprocessing
import os
import socket
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

import pytest
from tests.unit.test_b649_production_cutover import (
    NEW_HEAD,
    NEW_TREE,
    OLD_HEAD,
    OLD_TREE,
    UID,
    FakeLaunchd,
    Fixture,
    simulate_reboot,
)
from tools import b649_cutover_checkpoint as checkpoint
from tools import b649_production_cutover as cutover
from tools import b649_protected_cutover as protected
from tools import task_execution_claim as claims


@dataclass
class Harness:
    fixture: Fixture
    monkeypatch: pytest.MonkeyPatch
    action: str = "apply"
    launchd: FakeLaunchd = field(init=False)
    request: protected.Request | protected.RollbackRequest = field(init=False)
    owner: int = field(default_factory=os.getpid)
    child: int = 900071
    elapsed: float = 0
    sleeps: list[float] = field(default_factory=lambda: list[float]())
    stops: list[str] = field(default_factory=lambda: list[str]())
    launches: int = 0
    duplicates: list[int] = field(default_factory=lambda: list[int]())
    during_sleep: Callable[[], None] | None = None
    during_stop: Callable[[], None] | None = None
    after_child: Callable[[], None] | None = None
    exit_override: int | None = None
    exec_failed: bool = False
    process_stdout: bytes = b"bootstrap output\n"
    process_stderr: bytes = b"ModuleNotFoundError: protected child could not start\n"
    observed_started: protected.Record | None = None
    existing_plan: Path | None = None
    legacy_head: str = OLD_HEAD
    legacy_tree: str = OLD_TREE

    def __post_init__(self) -> None:
        self.launchd = FakeLaunchd(self.fixture)
        if self.action == "rollback":
            setup_runner = FakeLaunchd(self.fixture)
            plan = cutover.build_plan(self.fixture.config, runner=setup_runner)
            assert plan["status"] == "PASS"
            applied = cutover.apply(self.fixture.config, plan=plan, runner=setup_runner)
            assert applied["status"] == "SUCCESS"
            managed = json.loads(self.fixture.receipt_path.read_text(encoding="utf-8"))
            managed["status"] = "RECOVERY_REQUIRED"
            managed["phase"] = "RECOVERY_REQUIRED"
            self.fixture.receipt_path.write_text(protected.canonical(managed), encoding="utf-8")
            self.fixture.receipt_path.chmod(0o600)
            self.fixture.plist_path.write_bytes(self.fixture.old_plist_bytes)
            self.launchd.loaded = False
            self.launchd.loaded_source = self.fixture.old
            self.launchd.enabled = False
            path = None
        elif self.existing_plan is not None:
            path = self.existing_plan
        else:
            plan = cutover.build_plan(self.fixture.config, runner=self.launchd)
            assert plan["status"] == "PASS"
            path = self.fixture.root / "plan.json"
            path.write_text(protected.canonical(plan))
            path.chmod(0o600)
        self.fixture.scheduler_root.mkdir(mode=0o700, exist_ok=True)
        if self.action == "rollback":
            self.request = protected.make_rollback_request(
                self.fixture.config,
                self.fixture.old,
                OLD_HEAD,
                OLD_TREE,
                self.fixture.root / "claims",
            )
        else:
            assert path is not None
            self.request = protected.make_request(
                self.fixture.config,
                self.fixture.old,
                self.legacy_head,
                self.legacy_tree,
                path,
                self.fixture.root / "claims",
            )
        self.monkeypatch.setattr(
            protected, "repository_claim_root", lambda: self.request.claim_root
        )
        self.monkeypatch.setattr(
            protected,
            "control_identity",
            lambda: (
                cast(str, self.request.identity["control_head"]),
                cast(str, self.request.identity["control_tree"]),
            ),
        )
        self.monkeypatch.setattr(
            cutover,
            "control_version",
            lambda: {
                "head": self.request.identity["control_head"],
                "tree": self.request.identity["control_tree"],
            },
        )

        def config(_args: argparse.Namespace) -> cutover.CutoverConfig:
            return self.fixture.config

        def alive(pid: int) -> bool:
            return pid in {self.owner, self.child}

        self.monkeypatch.setattr(cutover, "protected_config", config)
        self.monkeypatch.setattr(claims, "_alive", alive)

        def image(_pid: int) -> Path:
            return Path(sys.executable).resolve()

        self.monkeypatch.setattr(checkpoint, "process_image", image)
        self.monkeypatch.setattr(subprocess, "Popen", self.popen)
        self.launchd.calls.clear()
        self.chain()

    def chain(self) -> None:
        self.launchd.process_rows = [
            f"{self.owner} 1 {UID} S {' '.join(self.request.owner_argv())}",
            f"{self.child} {self.owner} {UID} S {' '.join(self.request.managed_argv())}",
        ]
        self.launchd.file_rows = [
            f"p{pid}\nfcwd\nn{protected.CONTROL_ROOT}" for pid in (self.owner, self.child)
        ]

    def runner(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        args = list(argv)
        if args[:4] == ["git", "-c", "core.fsmonitor=false", "-C"]:
            self.launchd.calls.append(tuple(args))
            assert Path(args[4]) in {self.fixture.old, self.fixture.new}
            if args[5:] == ["fsmonitor--daemon", "stop"]:
                self.observed_started = protected.ReceiptFile(self.request.receipt_path).read()
                assert self.observed_started is not None
                assert self.observed_started["phase"] == "STARTED"
                expected_status = (
                    protected.ROLLBACK_INCOMPLETE
                    if self.request.action == "rollback"
                    else "INCOMPLETE_OR_AMBIGUOUS"
                )
                assert self.observed_started["status"] == expected_status
                assert (
                    claims.ClaimStore(self.request.claim_root).inspect(protected.TASK_KEY)[
                        "child_pid"
                    ]
                    == self.child
                )
                self.stops.append(args[4])
                if self.during_stop is not None:
                    self.during_stop()
                return subprocess.CompletedProcess(args, 0, "", "")
            assert args[5:] == ["rev-parse", "--show-toplevel"]
            return subprocess.CompletedProcess(args, 0, args[4] + "\n", "")
        return self.launchd(argv)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.elapsed += seconds
        if self.during_sleep is not None:
            self.during_sleep()

    def popen(
        self,
        argv: Sequence[str],
        *,
        pass_fds: tuple[int, ...],
        start_new_session: bool,
        stdout: int | None = None,
        stderr: int | None = None,
    ) -> FakeChild:
        self.launches += 1
        assert list(argv[:3]) == [sys.executable, "-c", claims._GATED_EXEC]
        wire = protected.record(json.loads(list(argv[4:])[-3]))
        identity = protected.record(wire["identity"])
        old_child_row = f"{self.child} {self.owner} {UID} S {' '.join(self.request.managed_argv())}"
        self.request = replace(
            self.request,
            reservation_id=cast(str | None, identity["reservation_id"]),
            owner_id_argument=cast(bool, identity["owner_id_argument"]),
        )
        new_child_row = f"{self.child} {self.owner} {UID} S {' '.join(self.request.managed_argv())}"
        self.launchd.process_rows = [
            new_child_row if row == old_child_row else row for row in self.launchd.process_rows
        ]
        assert list(argv[4:]) == self.request.managed_argv()
        assert start_new_session and pass_fds == (int(argv[3]),)
        state = claims.ClaimStore(self.request.claim_root).inspect(protected.TASK_KEY)
        assert state["owner_pid"] == self.owner and state["child_pid"] is None
        stdout_reader: BinaryIO | None = None
        stderr_reader: BinaryIO | None = None
        stdout_writer: int | None = None
        stderr_writer: int | None = None
        if stdout == subprocess.PIPE and stderr == subprocess.PIPE:
            stdout_read_fd, stdout_writer = os.pipe()
            stderr_read_fd, stderr_writer = os.pipe()
            stdout_reader = os.fdopen(stdout_read_fd, "rb", buffering=0)
            stderr_reader = os.fdopen(stderr_read_fd, "rb", buffering=0)
        return FakeChild(
            self,
            os.dup(pass_fds[0]),
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
            stdout_writer=stdout_writer,
            stderr_writer=stderr_writer,
        )

    def launch(self) -> protected.Record:
        protected.ReceiptFile(self.request.receipt_path).read()
        owner = cutover.inspect_control_owner(self.fixture.config)
        if self.request.reservation_id is None and (
            owner is None or owner.get("phase") == "RELEASED"
        ):
            version: cutover.Record = {
                "head": self.request.identity["control_head"],
                "tree": self.request.identity["control_tree"],
            }
            target = protected.request_owner_target(self.request)
            owner = cutover.acquire_control_owner(
                self.fixture.config,
                action=self.request.action,
                target=target,
                owner_kind="protected",
                version=version,
            )
            old_child_row = (
                f"{self.child} {self.owner} {UID} S {' '.join(self.request.managed_argv())}"
            )
            self.request = replace(
                self.request,
                reservation_id=str(owner["reservation_id"]),
            )
            new_child_row = (
                f"{self.child} {self.owner} {UID} S {' '.join(self.request.managed_argv())}"
            )
            self.launchd.process_rows = [
                new_child_row if row == old_child_row else row for row in self.launchd.process_rows
            ]
        if (
            owner is not None
            and owner.get("phase") in {"AUTHORIZATION_PENDING", "AUTHORIZED_PENDING"}
            and owner.get("reservation_id") == self.request.reservation_id
        ):
            version = {
                "head": self.request.identity["control_head"],
                "tree": self.request.identity["control_tree"],
            }
            owner = cutover.bind_control_owner(
                self.fixture.config,
                str(self.request.reservation_id),
                action=self.request.action,
                target=protected.request_owner_target(self.request),
                operation_id=str(self.request.identity["operation_id"]),
                managed_receipt_sha256=cast(
                    str | None,
                    self.request.identity["managed_receipt_sha256"],
                ),
                version=version,
            )
            authorization = protected.request_owner_authorization(self.request)
            if owner.get("authorization") is None:
                cutover.authorize_control_owner(
                    self.fixture.config,
                    str(self.request.reservation_id),
                    authorization,
                )
            elif owner.get("authorization") != authorization:
                raise AssertionError("test harness owner authorization drift")
        return protected.launch(self.request, runner=self.runner)

    def external(self, command: str, *, cwd: str | None = "/isolated") -> None:
        self.launchd.process_rows.append(f"900099 1 {UID} S {command}")
        if cwd is not None:
            self.launchd.file_rows.extend(["p900099", "fcwd", "n" + cwd])


@dataclass(frozen=True)
class StrandedIncident:
    request: protected.Request
    predecessor_sha256: str
    managed_sha256: str
    plan_sha256: str
    old_plist_bytes: bytes
    mutations_before: tuple[tuple[str, ...], ...]


def _preserve_legacy_prestart_result(
    _request: protected.Request | protected.RollbackRequest,
    _store: protected.ReceiptClaimStore,
    _staged: protected.Record,
    _exit_code: int,
    *,
    runner: cutover.Runner,
) -> protected.Record | None:
    del runner
    return None


def _make_stranded_prestart_incident(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    preserve_legacy_parent_behavior: bool,
    legacy_worktree: Path | None = None,
    legacy_head: str = NEW_HEAD,
    legacy_tree: str = NEW_TREE,
    terminal_exit_code: int = 127,
    predecessor_sha256_override: str | None = None,
) -> StrandedIncident:
    v5 = harness.launch()
    assert v5["status"] == "SUCCESS"
    prior_owner = cutover.inspect_control_owner(harness.fixture.config)
    assert prior_owner is not None and prior_owner["phase"] == "RELEASED"
    predecessor_bytes = harness.request.receipt_path.read_bytes()
    managed_bytes = harness.fixture.receipt_path.read_bytes()
    predecessor_sha256 = hashlib.sha256(predecessor_bytes).hexdigest()
    managed_sha256 = hashlib.sha256(managed_bytes).hexdigest()
    old_plist_bytes = harness.fixture.plist_path.read_bytes()
    mutations_before = tuple(harness.launchd.mutation_calls)
    harness.launchd.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    harness.launchd.file_rows = ["p424242", "fcwd", "n/tmp"]

    v6_head = "e" * 40
    v6_tree = "d" * 40
    v6_source = harness.fixture.worktree_parent / f"B649_PRODUCTION_{v6_head}"
    Fixture.make_source(v6_source)
    harness.launchd.worktree_identities[v6_source] = (v6_head, v6_tree, True)
    v6_config = replace(
        harness.fixture.config,
        source_worktree=v6_source,
        expected_head=v6_head,
        expected_tree=v6_tree,
        durable_ref=f"refs/heads/runtime/b649/{v6_head}",
        strict_release_layout=False,
    )
    plan = cutover.build_plan(v6_config, runner=harness.launchd)
    assert plan["status"] == "PASS", plan["failures"]
    plan_file = harness.fixture.root / "v6-plan.json"
    plan_file.write_text(protected.canonical(plan), encoding="utf-8")
    plan_file.chmod(0o600)

    original_control_head = "d32620eda04e3e01c1cb135d822bb21e41f0de34"
    original_control_tree = "1f8c8878dc6d108014028d9abf588ed7b4593d50"
    # Model the stranded operation as having been created by the packet's
    # original control checkout, even when these tests run from a later commit.
    monkeypatch.setattr(
        protected,
        "control_identity",
        lambda: (original_control_head, original_control_tree),
    )
    request = protected.make_request(
        v6_config,
        harness.fixture.new if legacy_worktree is None else legacy_worktree,
        legacy_head,
        legacy_tree,
        plan_file,
        harness.request.claim_root,
        reservation_id="fb748f08-cd90-4bec-89e1-31364d98143d",
        operation_id="27e1039be8f511114e06fcae200fcc2f",
        prior_execution_receipt_sha256=(
            predecessor_sha256
            if predecessor_sha256_override is None
            else predecessor_sha256_override
        ),
    )
    monkeypatch.setattr(cutover, "run_command", harness.runner)
    predecessor_proof = protected._require_released_success_evidence(request, prior_owner)
    owner = cutover.acquire_control_owner(
        v6_config,
        action="apply",
        target=protected.request_owner_target(request),
        owner_kind="protected",
        reservation_id=request.reservation_id,
        version={"head": original_control_head, "tree": original_control_tree},
        operation_id=request.operation_id,
        managed_receipt_sha256=request.managed_receipt_sha256,
        predecessor_release_evidence=predecessor_proof,
    )
    monkeypatch.setattr(
        cutover,
        "control_version",
        lambda: {"head": original_control_head, "tree": original_control_tree},
    )
    owner = cutover.bind_control_owner(
        v6_config,
        str(request.reservation_id),
        action="apply",
        target=protected.request_owner_target(request),
        operation_id=request.operation_id,
        managed_receipt_sha256=request.managed_receipt_sha256,
        version={"head": original_control_head, "tree": original_control_tree},
    )
    assert owner["phase"] == "AUTHORIZATION_PENDING"
    cutover.authorize_control_owner(
        v6_config,
        str(request.reservation_id),
        protected.request_owner_authorization(request),
    )
    harness.fixture.config = v6_config
    harness.request = request
    harness.chain()
    harness.exec_failed = True
    harness.exit_override = terminal_exit_code
    if preserve_legacy_parent_behavior:
        monkeypatch.setattr(
            protected,
            "_prestart_failure_evidence",
            _preserve_legacy_prestart_result,
        )
    result = harness.launch()
    assert result["exit_code"] == terminal_exit_code
    return StrandedIncident(
        request=request,
        predecessor_sha256=predecessor_sha256,
        managed_sha256=managed_sha256,
        plan_sha256=hashlib.sha256(plan_file.read_bytes()).hexdigest(),
        old_plist_bytes=old_plist_bytes,
        mutations_before=mutations_before,
    )


class _DigestOverride:
    def __init__(self, initial: bytes, overrides: dict[bytes, str]) -> None:
        self._bytes = bytearray(initial)
        self._real = hashlib.sha256(initial)
        self._overrides = overrides

    def update(self, value: bytes) -> None:
        self._bytes.extend(value)
        self._real.update(value)

    def hexdigest(self) -> str:
        return self._overrides.get(bytes(self._bytes), self._real.hexdigest())

    def digest(self) -> bytes:
        value = self.hexdigest()
        return bytes.fromhex(value)


class _FixtureHashlib:
    def __init__(self) -> None:
        self.overrides: dict[bytes, str] = {}

    def sha256(self, value: bytes = b"") -> _DigestOverride:
        return _DigestOverride(value, self.overrides)

    def bind(self, value: bytes, expected_sha256: str) -> None:
        self.overrides[value] = expected_sha256


def _prepare_exact_failed_terminal_bridge(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[StrandedIncident, protected.Request, _FixtureHashlib]:
    v5_config = replace(
        harness.fixture.config,
        expected_head=cutover.V5_SOURCE_HEAD,
        expected_tree=cutover.V5_SOURCE_TREE,
        durable_ref=f"refs/heads/runtime/b649/{cutover.V5_SOURCE_HEAD}",
        strict_release_layout=False,
    )
    harness.fixture.config = v5_config
    harness.launchd.worktree_identities[harness.fixture.new] = (
        cutover.V5_SOURCE_HEAD,
        cutover.V5_SOURCE_TREE,
        True,
    )
    harness.launchd.process_rows = ["1 0 0 S /sbin/launchd"]
    harness.launchd.file_rows = ["p1\nfcwd\nn/"]
    v5_plan = cutover.build_plan(v5_config, runner=harness.launchd)
    ownership = protected.record(v5_plan.get("ownership"))
    process_snapshot = protected.record(ownership.get("process"))
    assert v5_plan["status"] == "PASS", (
        v5_plan["failures"],
        ownership.get("runtime"),
        process_snapshot.get("processes"),
        process_snapshot.get("uncertainties"),
    )
    v5_plan_file = harness.fixture.root / "v5-plan.json"
    v5_plan_file.write_text(protected.canonical(v5_plan), encoding="utf-8")
    v5_plan_file.chmod(0o600)
    harness.request = protected.make_request(
        v5_config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        v5_plan_file,
        harness.fixture.root / "claims",
    )
    harness.chain()
    v5_result = harness.launch()
    assert v5_result["status"] == "SUCCESS"

    v5_receipt_file = protected.ReceiptFile(harness.request.receipt_path)
    v5_receipt = v5_receipt_file.read()
    assert v5_receipt is not None
    v5_receipt_before = v5_receipt
    v5_receipt = {
        **v5_receipt,
        "managed_receipt": {
            **protected.record(v5_receipt.get("managed_receipt")),
            "sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        },
    }
    v5_receipt_file.write(v5_receipt, expected=v5_receipt_before)
    managed_bytes = harness.fixture.receipt_path.read_bytes()
    v5_bytes = harness.request.receipt_path.read_bytes()
    owner_snapshot = cutover._read_control_owner(v5_config)  # pyright: ignore[reportPrivateUsage]
    assert owner_snapshot is not None
    v5_owner, owner_identity = owner_snapshot
    v5_owner["release_evidence"] = {
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "verified": True,
    }
    cutover._save_control_owner(  # pyright: ignore[reportPrivateUsage]
        v5_config, v5_owner, expected=owner_identity
    )

    fixture_hashlib = _FixtureHashlib()
    fixture_hashlib.bind(managed_bytes, cutover.V5_MANAGED_RECEIPT_SHA256)
    fixture_hashlib.bind(v5_bytes, cutover.V5_PROTECTED_RECEIPT_SHA256)
    monkeypatch.setattr(protected, "hashlib", fixture_hashlib)
    monkeypatch.setattr(cutover, "hashlib", fixture_hashlib)

    incident = _make_stranded_prestart_incident(
        harness,
        monkeypatch,
        preserve_legacy_parent_behavior=True,
        legacy_worktree=harness.fixture.new,
        legacy_head=cutover.V5_SOURCE_HEAD,
        legacy_tree=cutover.V5_SOURCE_TREE,
        terminal_exit_code=1,
        predecessor_sha256_override=cutover.V5_PROTECTED_RECEIPT_SHA256,
    )
    failed_file = protected.ReceiptFile(incident.request.receipt_path)
    failed = failed_file.read()
    assert failed is not None
    failed_before = failed
    failed = {**failed}
    failed["status"] = "FAILED"
    failed["phase"] = "COMPLETED"
    failed["exit_code"] = 1
    failed["result_status"] = "INCOMPLETE_OR_AMBIGUOUS"
    failed["child_exit_code"] = None
    for marker in ("child_started_at", "child_completed_at"):
        failed.pop(marker, None)
    required_receipt_fields = {
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
    }
    assert required_receipt_fields <= failed.keys(), sorted(required_receipt_fields - failed.keys())
    failed_file.write(failed, expected=failed_before)
    fixture_hashlib.bind(
        incident.request.receipt_path.read_bytes(),
        cutover.FAILED_TERMINAL_RECEIPT_SHA256,
    )
    cutover.release_control_owner(
        incident.request.config,
        str(incident.request.reservation_id),
        protected_receipt_path=incident.request.receipt_path,
    )

    v7_source = harness.fixture.worktree_parent / f"B649_PRODUCTION_{cutover.V7_SOURCE_HEAD}"
    Fixture.make_source(v7_source)
    harness.launchd.worktree_identities[v7_source] = (
        cutover.V7_SOURCE_HEAD,
        cutover.V7_SOURCE_TREE,
        True,
    )
    v7_config = replace(
        incident.request.config,
        source_worktree=v7_source,
        expected_head=cutover.V7_SOURCE_HEAD,
        expected_tree=cutover.V7_SOURCE_TREE,
        durable_ref=f"refs/heads/runtime/b649/{cutover.V7_SOURCE_HEAD}",
        strict_release_layout=False,
    )
    harness.fixture.config = v7_config
    harness.launchd.process_rows = ["1 0 0 S /sbin/launchd"]
    harness.launchd.file_rows = ["p1\nfcwd\nn/"]
    v7_plan = cutover.build_plan(v7_config, runner=harness.launchd)
    assert v7_plan["status"] == "PASS", v7_plan["failures"]
    v7_plan_file = harness.fixture.root / "v7-plan.json"
    v7_plan_file.write_text(protected.canonical(v7_plan), encoding="utf-8")
    v7_plan_file.chmod(0o600)
    harness.chain()
    request = protected.make_request(
        v7_config,
        harness.fixture.new,
        cutover.V5_SOURCE_HEAD,
        cutover.V5_SOURCE_TREE,
        v7_plan_file,
        incident.request.claim_root,
        reservation_id=str(uuid4()),
        prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
    )
    return incident, request, fixture_hashlib


def test_exact_failed_terminal_bridge_archives_then_reserves_with_v5_authority(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incident, request, _fixture_hashlib = _prepare_exact_failed_terminal_bridge(
        harness, monkeypatch
    )
    failed_path = incident.request.receipt_path
    failed_before = failed_path.read_bytes()
    v5_managed_before = request.config.receipt_path.read_bytes()
    owner_before = cutover._control_owner_path(request.config).read_bytes()  # pyright: ignore[reportPrivateUsage]
    failed = protected.ReceiptFile(failed_path).read()
    assert failed is not None
    assert (
        failed["status"],
        failed["phase"],
        failed["exit_code"],
        failed["result_status"],
    ) == ("FAILED", "COMPLETED", 1, "INCOMPLETE_OR_AMBIGUOUS")
    assert "child_started_at" not in failed and "child_completed_at" not in failed
    assert claims.ClaimStore(request.claim_root).inspect(protected.TASK_KEY)["status"] == "ABSENT"

    prior_owner = cutover.inspect_control_owner(request.config)
    assert prior_owner is not None and prior_owner["phase"] == "RELEASED"
    proof = protected._require_released_success_evidence(request, prior_owner)
    assert proof is not None
    assert proof["prior_protected_receipt_sha256"] == cutover.V5_PROTECTED_RECEIPT_SHA256
    assert proof["prior_managed_receipt_sha256"] == cutover.V5_MANAGED_RECEIPT_SHA256
    assert proof["prior_protected_receipt_sha256"] != cutover.FAILED_TERMINAL_RECEIPT_SHA256
    assert not failed_path.exists()
    archive_path = failed_path.with_name(
        f"{failed_path.stem}.{failed['execution_id']}.superseded.json"
    )
    assert archive_path.read_bytes() == failed_before
    assert request.config.receipt_path.read_bytes() == v5_managed_before
    assert cutover._control_owner_path(request.config).read_bytes() == owner_before  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(
        cutover.CutoverSafetyError,
        match="requires live predecessor revalidation",
    ):
        cutover.acquire_control_owner(
            request.config,
            action="apply",
            target=protected.request_owner_target(request),
            owner_kind="protected",
            reservation_id=str(request.reservation_id),
            version={"head": request.control_head, "tree": request.control_tree},
            operation_id=request.operation_id,
            managed_receipt_sha256=request.managed_receipt_sha256,
            predecessor_release_evidence=proof,
        )
    assert cutover._control_owner_path(request.config).read_bytes() == owner_before  # pyright: ignore[reportPrivateUsage]

    owner = cutover.acquire_control_owner(
        request.config,
        action="apply",
        target=protected.request_owner_target(request),
        owner_kind="protected",
        reservation_id=str(request.reservation_id),
        version={"head": request.control_head, "tree": request.control_tree},
        operation_id=request.operation_id,
        managed_receipt_sha256=request.managed_receipt_sha256,
        predecessor_release_evidence=proof,
        predecessor_live_verifier=protected._failed_terminal_bridge_live_verifier(
            request,
            prior_owner,
            proof,
            runner=harness.launchd,
        ),
    )
    assert owner["phase"] == "AUTHORIZATION_PENDING"
    saved_proof = protected.record(owner.get("predecessor_release_evidence"))
    assert saved_proof["prior_protected_receipt_sha256"] == cutover.V5_PROTECTED_RECEIPT_SHA256
    assert (
        saved_proof["retired_failed_terminal_evidence"] == proof["retired_failed_terminal_evidence"]
    )
    retirement = protected.record(saved_proof["retired_failed_terminal_evidence"])
    assert retirement["archive_status"] == "ARCHIVED_UNCHANGED"
    assert retirement["zero_mutation"] is True
    assert retirement["v5_protected_receipt_sha256"] == cutover.V5_PROTECTED_RECEIPT_SHA256
    assert claims.ClaimStore(request.claim_root).inspect(protected.TASK_KEY)["status"] == "ABSENT"


def test_failed_terminal_bridge_refuses_live_drift_before_owner_cas(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _incident, request, _fixture_hashlib = _prepare_exact_failed_terminal_bridge(
        harness, monkeypatch
    )
    prior_owner = cutover.inspect_control_owner(request.config)
    assert prior_owner is not None and prior_owner["phase"] == "RELEASED"
    proof = protected._require_released_success_evidence(request, prior_owner)
    assert proof is not None
    owner_path = cutover._control_owner_path(request.config)  # pyright: ignore[reportPrivateUsage]
    owner_before = owner_path.read_bytes()
    archive_paths_before = set(request.config.scheduler_root.glob("*.superseded.json"))

    harness.launchd.enabled = False
    with pytest.raises(protected.ProtectedError, match="live launch state differs"):
        cutover.acquire_control_owner(
            request.config,
            action="apply",
            target=protected.request_owner_target(request),
            owner_kind="protected",
            reservation_id=str(request.reservation_id),
            version={"head": request.control_head, "tree": request.control_tree},
            operation_id=request.operation_id,
            managed_receipt_sha256=request.managed_receipt_sha256,
            predecessor_release_evidence=proof,
            predecessor_live_verifier=protected._failed_terminal_bridge_live_verifier(
                request,
                prior_owner,
                proof,
                runner=harness.launchd,
            ),
        )

    assert owner_path.read_bytes() == owner_before
    assert cutover.inspect_control_owner(request.config) == prior_owner
    assert set(request.config.scheduler_root.glob("*.superseded.json")) == archive_paths_before


def test_exact_failed_terminal_operation_cannot_be_reacquired_without_successor_proof(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incident, request, _fixture_hashlib = _prepare_exact_failed_terminal_bridge(
        harness, monkeypatch
    )
    failed_path = incident.request.receipt_path
    owner_path = cutover._control_owner_path(request.config)  # pyright: ignore[reportPrivateUsage]
    owner = cutover.inspect_control_owner(request.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    before = _bridge_files_snapshot(request)

    with pytest.raises(cutover.CutoverSafetyError, match="requires a verified successor"):
        cutover.acquire_control_owner(
            request.config,
            action="apply",
            target=protected.request_owner_target(request),
            owner_kind="protected",
            reservation_id=cutover.FAILED_TERMINAL_RESERVATION_ID,
            version={"head": request.control_head, "tree": request.control_tree},
            operation_id=cutover.FAILED_TERMINAL_OPERATION_ID,
            managed_receipt_sha256=cutover.V5_MANAGED_RECEIPT_SHA256,
        )

    assert _bridge_files_snapshot(request) == before
    assert owner_path.read_bytes() == before[owner_path]
    assert failed_path.exists()


def _bridge_files_snapshot(request: protected.Request) -> dict[Path, bytes]:
    paths: set[Path] = set()
    for root in (request.config.scheduler_root, request.claim_root):
        if root.exists():
            paths.update(path for path in root.rglob("*") if path.is_file())
    return {path: path.read_bytes() for path in paths}


def _save_bridge_owner(
    request: protected.Request,
    changes: dict[str, object],
    *,
    bind_authorization: bool = False,
) -> protected.Record:
    snapshot = cutover._read_control_owner(request.config)  # pyright: ignore[reportPrivateUsage]
    assert snapshot is not None
    owner, identity = snapshot
    updated = {**owner, **changes}
    if bind_authorization:
        updated["authorization"] = cutover._owner_identity(updated)  # pyright: ignore[reportPrivateUsage]
    return cutover._save_control_owner(  # pyright: ignore[reportPrivateUsage]
        request.config, updated, expected=identity
    )


def _seed_active_bridge_claim(request: protected.Request) -> None:
    store = claims.ClaimStore(request.claim_root)
    now = datetime.now(UTC).isoformat()
    metadata = cast(
        claims.Metadata,
        {
            "schema_version": 1,
            "task_key": protected.TASK_KEY,
            "owner_id": str(uuid4()),
            "owner_pid": os.getpid(),
            "child_pid": None,
            "hostname": socket.gethostname(),
            "started_at_utc": now,
            "heartbeat_at_utc": now,
            "cwd": str(request.claim_root.parent),
            "command": [sys.executable, "-c", "pass"],
            "claim_root": str(request.claim_root),
        },
    )
    with store._transaction():  # pyright: ignore[reportPrivateUsage]
        store._write(metadata)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    "mismatch",
    [
        "failed_sha",
        "reservation",
        "operation",
        "owner_target",
        "release_evidence",
        "mutation_true",
        "mutation_unknown",
        "child_marker",
        "failed_managed_receipt",
        "claim_present",
        "v5_managed_sha",
        "v5_archive_sha",
        "v5_archive_link",
        "live_source",
        "live_plist",
        "live_enabled",
    ],
)
def test_exact_failed_bridge_mismatches_refuse_before_retirement_or_reservation(
    mismatch: str,
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incident, request, fixture_hashlib = _prepare_exact_failed_terminal_bridge(harness, monkeypatch)
    failed_path = incident.request.receipt_path
    failed_value = protected.ReceiptFile(failed_path).read()
    assert failed_value is not None
    failed_execution_id = protected.text(failed_value.get("execution_id"))
    expected_failed_archive_name = f"{failed_path.stem}.{failed_execution_id}.superseded.json"
    prior_owner: protected.Record
    if mismatch == "failed_sha":
        failed_file = protected.ReceiptFile(failed_path)
        failed = failed_file.read()
        assert failed is not None
        failed_file.write(
            {**failed, "process_stderr": "changed receipt bytes\n"},
            expected=failed,
        )
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    elif mismatch in {
        "reservation",
        "operation",
        "owner_target",
        "release_evidence",
        "mutation_true",
        "mutation_unknown",
    }:
        changes: dict[str, object]
        if mismatch == "reservation":
            updated_owner = cutover.inspect_control_owner(request.config)
            assert updated_owner is not None
            changes = {
                "reservation_id": str(uuid4()),
            }
        elif mismatch == "operation":
            changes = {"operation_id": "c" * 32}
        elif mismatch == "owner_target":
            stored_snapshot = cutover._read_control_owner(  # pyright: ignore[reportPrivateUsage]
                request.config
            )
            assert stored_snapshot is not None
            changed_target = {
                **protected.record(stored_snapshot[0]["target"]),
                "head": "a" * 40,
            }
            changes = {"target": changed_target}
        elif mismatch == "release_evidence":
            changes = {
                "release_evidence": {
                    "protected_receipt_sha256": cutover.FAILED_TERMINAL_RECEIPT_SHA256,
                    "managed_receipt_unchanged": True,
                    "verified": False,
                }
            }
        elif mismatch == "mutation_true":
            changes = {"mutation_started": True}
        else:
            changes = {"mutation_started": None}
        if mismatch in {"reservation", "operation", "owner_target"}:
            prior_owner = _save_bridge_owner(
                request,
                changes,
                bind_authorization=True,
            )
        else:
            prior_owner = _save_bridge_owner(request, changes)
    elif mismatch == "child_marker":
        failed_file = protected.ReceiptFile(failed_path)
        failed = failed_file.read()
        assert failed is not None
        failed_file.write(
            {**failed, "child_started_at": datetime.now(UTC).isoformat()},
            expected=failed,
        )
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    elif mismatch == "failed_managed_receipt":
        managed, identity, _ = cutover.read_control_json(request.config.receipt_path)
        managed["operation_id"] = cutover.FAILED_TERMINAL_OPERATION_ID
        cutover._write_json(  # pyright: ignore[reportPrivateUsage]
            request.config.receipt_path, managed, expected=identity
        )
        fixture_hashlib.bind(
            request.config.receipt_path.read_bytes(), cutover.V5_MANAGED_RECEIPT_SHA256
        )
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    elif mismatch == "claim_present":
        _seed_active_bridge_claim(request)
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    elif mismatch == "v5_managed_sha":
        managed, identity, _ = cutover.read_control_json(request.config.receipt_path)
        managed["status"] = "RECOVERY_REQUIRED"
        cutover._write_json(  # pyright: ignore[reportPrivateUsage]
            request.config.receipt_path, managed, expected=identity
        )
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    elif mismatch in {"v5_archive_sha", "v5_archive_link"}:
        archive = next(
            path
            for path in request.config.scheduler_root.glob(
                f"{request.receipt_path.stem}.*.superseded.json"
            )
            if path.name != expected_failed_archive_name
        )
        if mismatch == "v5_archive_sha":
            with archive.open("ab") as stream:
                stream.write(b" ")
        else:
            v5, identity, _ = cutover.read_control_json(archive)
            protected.record(v5.get("managed_receipt"))["sha256"] = "f" * 64
            unsigned = {key: value for key, value in v5.items() if key != "receipt_sha256"}
            v5["receipt_sha256"] = protected.digest(unsigned)
            cutover._write_json(  # pyright: ignore[reportPrivateUsage]
                archive, v5, expected=identity
            )
            fixture_hashlib.bind(archive.read_bytes(), cutover.V5_PROTECTED_RECEIPT_SHA256)
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
    else:
        prior_owner = cast(protected.Record, cutover.inspect_control_owner(request.config))
        if mismatch == "live_source":
            harness.launchd.loaded_source = harness.fixture.old
        elif mismatch == "live_plist":
            request.config.plist_path.write_bytes(b"changed plist bytes")
        else:
            harness.launchd.enabled = False

    assert prior_owner is not None
    before = _bridge_files_snapshot(request)
    with pytest.raises((protected.ProtectedError, cutover.CutoverSafetyError)):
        protected._require_released_success_evidence(request, prior_owner)
    assert _bridge_files_snapshot(request) == before
    assert failed_path.exists()
    assert not (request.config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_NAME).exists()


def _fresh_bridge_request(request: protected.Request) -> protected.Request:
    assert request.reservation_id is not None
    return protected.make_request(
        request.config,
        request.legacy_worktree,
        request.legacy_head,
        request.legacy_tree,
        request.plan_file,
        request.claim_root,
        reservation_id=request.reservation_id,
        prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
        managed_receipt_sha256=request.managed_receipt_sha256,
    )


def test_archive_interruption_fresh_retry_is_idempotent_and_keeps_v5_proof(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incident, request, _fixture_hashlib = _prepare_exact_failed_terminal_bridge(
        harness, monkeypatch
    )
    failed_path = incident.request.receipt_path
    failed_before = failed_path.read_bytes()
    failed_value = protected.ReceiptFile(failed_path).read()
    assert failed_value is not None
    failed_execution_id = protected.text(failed_value.get("execution_id"))
    prior_owner = cutover.inspect_control_owner(request.config)
    assert prior_owner is not None
    retirement_path = request.config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_NAME
    original_write = cutover._write_json  # pyright: ignore[reportPrivateUsage]

    def interrupt_before_sidecar(
        path: Path,
        value: cutover.Record,
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        if path == retirement_path:
            raise OSError("injected interruption after archive and before reservation")
        return original_write(path, value, expected=expected)

    with monkeypatch.context() as interruption:
        interruption.setattr(cutover, "_write_json", interrupt_before_sidecar)
        with pytest.raises(OSError, match="injected interruption"):
            protected._require_released_success_evidence(request, prior_owner)

    archive_path = failed_path.with_name(
        f"{failed_path.stem}.{failed_execution_id}.superseded.json"
    )
    assert archive_path.read_bytes() == failed_before
    assert not failed_path.exists()
    assert not retirement_path.exists()
    owner_after_interruption = cutover.inspect_control_owner(request.config)
    assert owner_after_interruption is not None
    assert owner_after_interruption["reservation_id"] == cutover.FAILED_TERMINAL_RESERVATION_ID
    assert owner_after_interruption["phase"] == "RELEASED"
    assert owner_after_interruption["mutation_started"] is False

    fresh_request = _fresh_bridge_request(request)
    proof = protected._require_released_success_evidence(fresh_request, owner_after_interruption)
    assert proof is not None
    second_proof = protected._require_released_success_evidence(
        fresh_request, owner_after_interruption
    )
    assert second_proof == proof
    assert archive_path.read_bytes() == failed_before
    assert (
        len(list(request.config.scheduler_root.glob(f"{failed_path.stem}.*.superseded.json"))) == 2
    )
    assert not failed_path.exists()
    assert proof["prior_protected_receipt_sha256"] == cutover.V5_PROTECTED_RECEIPT_SHA256
    assert proof["prior_managed_receipt_sha256"] == cutover.V5_MANAGED_RECEIPT_SHA256
    current_owner = cutover.inspect_control_owner(request.config)
    assert current_owner is not None
    assert current_owner["reservation_id"] == cutover.FAILED_TERMINAL_RESERVATION_ID


def test_two_candidate_reservations_cannot_both_acquire_the_failed_transition(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _incident, first, _fixture_hashlib = _prepare_exact_failed_terminal_bridge(harness, monkeypatch)
    first_id = cast(str, first.reservation_id)
    second = protected.make_request(
        first.config,
        first.legacy_worktree,
        first.legacy_head,
        first.legacy_tree,
        first.plan_file,
        first.claim_root,
        reservation_id=str(uuid4()),
        prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
        managed_receipt_sha256=first.managed_receipt_sha256,
    )
    failed_owner = cutover.inspect_control_owner(first.config)
    assert failed_owner is not None
    first_proof = protected._require_released_success_evidence(first, failed_owner)
    second_proof = protected._require_released_success_evidence(second, failed_owner)
    assert first_proof is not None and second_proof is not None
    barrier = threading.Barrier(2)

    def acquire(
        request: protected.Request,
        proof: protected.Record,
    ) -> tuple[str, protected.Record | str]:
        barrier.wait(timeout=5)
        try:
            owner = cutover.acquire_control_owner(
                request.config,
                action="apply",
                target=protected.request_owner_target(request),
                owner_kind="protected",
                reservation_id=cast(str, request.reservation_id),
                version={"head": request.control_head, "tree": request.control_tree},
                operation_id=request.operation_id,
                managed_receipt_sha256=request.managed_receipt_sha256,
                predecessor_release_evidence=proof,
                predecessor_live_verifier=protected._failed_terminal_bridge_live_verifier(
                    request,
                    failed_owner,
                    proof,
                    runner=harness.launchd,
                ),
            )
            return "ACQUIRED", owner
        except (cutover.CutoverSafetyError, cutover.CutoverAlreadyRunning) as exc:
            return "BLOCKED", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(acquire, first, first_proof)
        second_future = pool.submit(acquire, second, second_proof)
        outcomes = [first_future.result(), second_future.result()]
    acquired = [value for status, value in outcomes if status == "ACQUIRED"]
    blocked = [value for status, value in outcomes if status == "BLOCKED"]
    assert len(acquired) == 1 and len(blocked) == 1
    winning_id = protected.text(protected.record(acquired[0]).get("reservation_id"))
    assert winning_id in {first_id, cast(str, second.reservation_id)}
    current_owner = cutover.inspect_control_owner(first.config)
    assert current_owner is not None
    assert current_owner["reservation_id"] == winning_id
    assert current_owner["phase"] == "AUTHORIZATION_PENDING"
    assert claims.ClaimStore(first.claim_root).inspect(protected.TASK_KEY)["status"] == "ABSENT"


class FakeChild:
    def __init__(
        self,
        harness: Harness,
        gate: int,
        *,
        stdout_reader: BinaryIO | None,
        stderr_reader: BinaryIO | None,
        stdout_writer: int | None,
        stderr_writer: int | None,
    ):
        self.harness = harness
        self.gate = gate
        self.pid = harness.child
        self.stdout = stdout_reader
        self.stderr = stderr_reader
        self.stdout_writer = stdout_writer
        self.stderr_writer = stderr_writer

    def _write_process_streams(self, stdout: bytes, stderr: bytes) -> None:
        for descriptor, content in (
            (self.stdout_writer, stdout),
            (self.stderr_writer, stderr),
        ):
            if descriptor is not None:
                try:
                    if content:
                        os.write(descriptor, content)
                finally:
                    os.close(descriptor)

    def wait(self, *, timeout: float) -> int:
        assert timeout == claims.HEARTBEAT_SECONDS
        harness = self.harness
        try:
            assert os.read(self.gate, 1) == b"G"
        finally:
            os.close(self.gate)
        store = claims.ClaimStore(harness.request.claim_root)
        assert store.inspect(protected.TASK_KEY)["child_pid"] == self.pid
        # Competing launcher traverses the real acquisition check, but cannot spawn.
        with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
            protected.launch(harness.request)
        harness.duplicates.append(store.run(protected.TASK_KEY, harness.request.managed_argv()))
        if harness.exec_failed:
            self._write_process_streams(harness.process_stdout, harness.process_stderr)
            if harness.after_child:
                harness.after_child()
            return 127 if harness.exit_override is None else harness.exit_override
        if self.stdout_writer is None or self.stderr_writer is None:
            raise AssertionError("captured child streams are required by the harness")
        with (
            os.fdopen(self.stdout_writer, "w", encoding="utf-8") as child_stdout,
            os.fdopen(self.stderr_writer, "w", encoding="utf-8") as child_stderr,
            redirect_stdout(child_stdout),
            redirect_stderr(child_stderr),
            pytest.MonkeyPatch.context() as child_context,
        ):
            child_context.setattr(os, "getpid", lambda: harness.child)
            child_context.setattr(os, "getppid", lambda: harness.owner)
            try:
                args = cutover.parser().parse_args(harness.request.managed_argv()[2:])
                code = protected.run_managed_child(
                    args,
                    runner=harness.runner,
                    sleeper=harness.sleep,
                    clock=lambda: harness.elapsed,
                )
            except (protected.ProtectedError, checkpoint.Unverifiable, OSError) as exc:
                print(str(exc), file=sys.stderr)
                code = 1
        if harness.after_child:
            harness.after_child()
        return code if harness.exit_override is None else harness.exit_override


@pytest.fixture(autouse=True)
def no_real_launchctl(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test here may reach the real launchd; each must inject its fake runner."""
    real = cutover.run_command

    def guarded(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        assert Path(argv[0]).name != "launchctl", f"real launchctl reached: {list(argv)}"
        return real(argv)

    monkeypatch.setattr(cutover, "run_command", guarded)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(Fixture(tmp_path), monkeypatch)


@pytest.fixture
def rollback_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(Fixture(tmp_path, old_name="legacy-receipt-bound-old"), monkeypatch, "rollback")


def test_protected_rollback_restores_old_loaded_enabled_state_and_reuses_success(
    rollback_harness: Harness,
) -> None:
    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_SUCCESS
    assert result["result_status"] == protected.ROLLBACK_SUCCESS
    assert result["phase"] == "COMPLETED" and result["exit_code"] == 0
    assert rollback_harness.duplicates == [claims.REFUSED]
    assert (
        rollback_harness.fixture.plist_path.read_bytes() == rollback_harness.fixture.old_plist_bytes
    )
    assert rollback_harness.launchd.loaded is True
    assert rollback_harness.launchd.loaded_source == rollback_harness.fixture.old
    assert rollback_harness.launchd.enabled is True
    assert rollback_harness.sleeps == [5.0]
    assert rollback_harness.stops == [
        str(rollback_harness.fixture.old),
        str(rollback_harness.fixture.new),
    ]
    assert len(cast(list[object], result["quiescence"])) == 2
    assert rollback_harness.request.identity["action"] == "rollback"
    for identity_field in (
        "managed_receipt_sha256",
        "operation_id",
        "plan_digest",
        "prestate_digest",
        "old_durable_ref",
        "new_worktree",
        "new_head",
        "new_tree",
        "plist_path",
        "label",
        "control_worktree",
        "control_head",
        "control_tree",
        "protected_wrapper_schema",
    ):
        assert identity_field in rollback_harness.request.identity
    protected_receipt = protected.ReceiptFile(rollback_harness.request.receipt_path).read()
    assert protected_receipt is not None
    assert protected_receipt["status"] == protected.ROLLBACK_SUCCESS
    assert protected.record(protected_receipt["managed_receipt"])["status"] == "ROLLBACK_SUCCESS"
    assert rollback_harness.fixture.receipt_path.read_bytes() != b""
    assert all(
        path.read_bytes() == before
        for path, before in rollback_harness.fixture.business_state_before.items()
    )

    mutation_calls = list(rollback_harness.launchd.mutation_calls)
    reused = rollback_harness.launch()

    assert reused["status"] == protected.ROLLBACK_SUCCESS
    assert reused["reused"] is True
    assert rollback_harness.launches == 1
    assert rollback_harness.launchd.mutation_calls == mutation_calls


def test_protected_rollback_accepts_receipt_bound_old_layout_but_new_stays_strict(
    rollback_harness: Harness,
) -> None:
    strict_config = replace(rollback_harness.fixture.config, strict_release_layout=True)
    plan = cutover._receipt_to_plan(
        rollback_harness.fixture.config,
        json.loads(rollback_harness.fixture.receipt_path.read_text(encoding="utf-8")),
    )
    old_source = protected.record(protected.record(plan["source"])["old"])
    new_source = protected.record(protected.record(plan["source"])["new"])

    accepted = cutover._validate_bound_source(
        strict_config,
        old_source,
        rollback_harness.launchd,
        role="protected-old",
        legacy_prestate=True,
    )
    assert accepted["source_worktree"] == str(rollback_harness.fixture.old)
    with pytest.raises(cutover.CutoverSafetyError, match="production source directory"):
        cutover._validate_bound_source(
            strict_config,
            old_source,
            rollback_harness.launchd,
            role="protected-new",
        )
    accepted_new = cutover._validate_bound_source(
        strict_config,
        new_source,
        rollback_harness.launchd,
        role="protected-new",
    )
    assert accepted_new["source_worktree"] == str(rollback_harness.fixture.new)


def test_protected_rollback_receipt_sha_drift_blocks_before_mutation(
    rollback_harness: Harness,
) -> None:
    original = rollback_harness.fixture.receipt_path.read_bytes()
    rollback_harness.fixture.receipt_path.write_bytes(original + b"\n")
    rollback_harness.fixture.receipt_path.chmod(0o600)

    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_INCOMPLETE
    assert rollback_harness.launchd.mutation_calls == []
    assert (
        rollback_harness.fixture.plist_path.read_bytes() == rollback_harness.fixture.old_plist_bytes
    )


def test_protected_rollback_current_plist_must_be_receipt_bound_old_or_new(
    rollback_harness: Harness,
) -> None:
    rollback_harness.fixture.plist_path.write_bytes(b"not-a-receipt-bound-plist")
    rollback_harness.fixture.plist_path.chmod(0o600)

    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_FAILED
    assert rollback_harness.launchd.mutation_calls == []
    assert result["managed_receipt"] is not None


@pytest.mark.parametrize("field", ["plan_digest", "prestate_digest"])
def test_protected_rollback_plan_identity_drift_blocks_before_mutation(
    rollback_harness: Harness, field: str
) -> None:
    managed = json.loads(rollback_harness.fixture.receipt_path.read_text(encoding="utf-8"))
    managed[field] = "f" * 64
    rollback_harness.fixture.receipt_path.write_text(protected.canonical(managed), encoding="utf-8")
    rollback_harness.fixture.receipt_path.chmod(0o600)

    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_INCOMPLETE
    assert rollback_harness.launchd.mutation_calls == []


def test_protected_rollback_missing_managed_receipt_blocks_before_mutation(
    rollback_harness: Harness,
) -> None:
    rollback_harness.fixture.receipt_path.unlink()

    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_INCOMPLETE
    assert result["managed_receipt"] is None
    assert rollback_harness.launchd.mutation_calls == []


def test_protected_rollback_ambiguous_result_blocks_explicit_takeover(
    rollback_harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = protected.ReceiptFile.write

    def fail_started(
        self: protected.ReceiptFile, value: protected.Record, *, expected: protected.Record | None
    ) -> protected.Record:
        if value.get("phase") == "STARTED" and expected is not None:
            raise OSError("rollback start receipt interrupted")
        return original(self, value, expected=expected)

    monkeypatch.setattr(protected.ReceiptFile, "write", fail_started)
    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_INCOMPLETE
    rollback_harness.request = replace(rollback_harness.request, takeover_stale=True)
    with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
        rollback_harness.launch()
    assert rollback_harness.launches == 1


def test_protected_rollback_failure_preserves_existing_managed_linkage(
    rollback_harness: Harness,
) -> None:
    rollback_harness.exec_failed = True

    result = rollback_harness.launch()

    assert result["status"] == protected.ROLLBACK_INCOMPLETE
    assert result["result_status"] == protected.ROLLBACK_INCOMPLETE
    assert protected.record(result["managed_receipt"])["status"] == "RECOVERY_REQUIRED"
    assert rollback_harness.launchd.mutation_calls == []


def test_protected_rollback_preserves_prior_ambiguous_apply_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control_head, control_tree = protected.control_identity()
    fixture = Fixture(tmp_path, old_name="legacy-receipt-bound-old")
    harness = Harness(fixture, monkeypatch)
    assert harness.launch()["status"] == "SUCCESS"
    apply_receipt_path = harness.request.receipt_path
    apply_receipt_before = apply_receipt_path.read_bytes()
    managed = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    managed["status"] = "RECOVERY_REQUIRED"
    managed["phase"] = "RECOVERY_REQUIRED"
    fixture.receipt_path.write_text(protected.canonical(managed), encoding="utf-8")
    fixture.receipt_path.chmod(0o600)
    fixture.plist_path.write_bytes(fixture.old_plist_bytes)
    harness.launchd.loaded = False
    harness.launchd.loaded_source = fixture.old
    harness.launchd.enabled = False
    harness.launchd.calls.clear()
    monkeypatch.setattr(protected, "control_identity", lambda: (control_head, control_tree))
    harness.request = protected.make_rollback_request(
        fixture.config,
        fixture.old,
        OLD_HEAD,
        OLD_TREE,
        tmp_path / "claims",
    )
    harness.action = "rollback"
    harness.launches = 0
    harness.duplicates.clear()
    harness.sleeps.clear()
    harness.stops.clear()
    harness.elapsed = 0
    harness.chain()

    result = harness.launch()

    assert result["status"] == protected.ROLLBACK_SUCCESS
    assert apply_receipt_path.read_bytes() == apply_receipt_before
    prior_apply_receipt = protected.ReceiptFile(apply_receipt_path).read()
    assert prior_apply_receipt is not None
    assert protected.record(prior_apply_receipt["identity"])["action"] == "apply"


def test_once_gated_direct_child_durable_success_and_no_second_execution(harness: Harness) -> None:
    result = harness.launch()
    assert result["status"] == "SUCCESS"
    assert result["phase"] == "COMPLETED" and result["exit_code"] == 0
    assert harness.launches == 1 and harness.duplicates == [claims.REFUSED]
    assert harness.sleeps == [5.0]
    assert harness.stops == [str(harness.fixture.old), str(harness.fixture.new)]
    assert len(cast(list[object], result["quiescence"])) == 2
    assert result["direct_argv"] == harness.request.managed_argv()
    assert result["supervisor_pid"] == harness.owner and result["gated_child_pid"] == harness.child
    assert protected.record(result["claim_owner"])["owner_id"]
    assert result["started_at"] and result["completed_at"] and result["child_completed_at"]
    assert protected.record(result["stdout"])["sha256"]
    assert result["managed_receipt"] == protected.managed_link(harness.request)
    assert stat.S_IMODE(harness.request.receipt_path.stat().st_mode) == 0o600
    assert (
        claims.ClaimStore(harness.request.claim_root).inspect(protected.TASK_KEY)["status"]
        == "ABSENT"
    )
    mutations = list(harness.launchd.mutation_calls)
    reused = harness.launch()
    assert reused["status"] == "SUCCESS" and reused["reused"] is True
    assert harness.launches == 1 and harness.launchd.mutation_calls == mutations
    assert all(
        path.read_bytes() == before
        for path, before in harness.fixture.business_state_before.items()
    )


@pytest.mark.parametrize(
    "field",
    [
        "source_tree",
        "source_head",
        "source_worktree",
        "plan_digest",
        "label",
        "plist_path",
        "managed_receipt_path",
        "action",
    ],
)
def test_identity_digest_binds_every_load_bearing_field(harness: Harness, field: str) -> None:
    identity = harness.request.identity
    assert protected.digest(identity) == harness.request.execution_id
    identity[field] = "changed"
    assert protected.digest(identity) != harness.request.execution_id


def test_mismatched_identity_never_reuses_success(harness: Harness) -> None:
    harness.launch()
    harness.request = replace(harness.request, legacy_tree="f" * 40)
    with pytest.raises(protected.ProtectedError, match="identity mismatch"):
        harness.launch()
    assert harness.launches == 1


@pytest.mark.parametrize("point", ["STARTED", "CHILD_COMPLETED", "exit_mismatch"])
def test_interruption_and_ambiguous_terminal_block_even_explicit_takeover(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    original = protected.ReceiptFile.write

    def write(
        self: protected.ReceiptFile, value: protected.Record, *, expected: protected.Record | None
    ) -> protected.Record:
        if value.get("phase") == point and expected is not None:
            raise OSError("isolated receipt write interruption")
        if point == "STARTED" and value.get("phase") == "CHILD_COMPLETED":
            raise OSError("child terminal capture lost")
        return original(self, value, expected=expected)

    monkeypatch.setattr(protected.ReceiptFile, "write", write)
    if point == "exit_mismatch":
        harness.exit_override = 137
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    harness.request = replace(harness.request, takeover_stale=True)
    with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
        harness.launch()
    assert harness.launches == 1


def test_failed_precheck_is_terminal_and_has_no_cutover_mutation(harness: Harness) -> None:
    harness.launchd.status_by_path[harness.fixture.new] = " M dirty.py\n"
    result = harness.launch()
    assert result["status"] == "FAILED" and result["exit_code"] == 1
    assert "protected source status changed" in str(protected.record(result["stderr"])["text"])
    assert harness.launchd.mutation_calls == []
    assert not harness.fixture.receipt_path.exists()


@pytest.mark.parametrize(
    "takeover,owner_alive,child_alive,expected",
    [
        (False, False, False, claims.TAKEOVER_REQUIRED),
        (True, True, False, claims.REFUSED),
        (True, False, True, claims.REFUSED),
        (True, None, False, claims.UNVERIFIABLE),
        (True, False, None, claims.UNVERIFIABLE),
        (True, False, False, 0),
    ],
)
def test_stale_takeover_delegates_positive_death_and_explicit_authority(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    takeover: bool,
    owner_alive: bool | None,
    child_alive: bool | None,
    expected: int,
) -> None:
    store = claims.ClaimStore(harness.request.claim_root)
    old_stamp = (datetime.now(UTC) - timedelta(seconds=300)).isoformat()
    stale = claims.Metadata(
        schema_version=1,
        task_key=protected.TASK_KEY,
        owner_id=str(uuid4()),
        owner_pid=900081,
        child_pid=900082,
        hostname=socket.gethostname(),
        started_at_utc=old_stamp,
        heartbeat_at_utc=old_stamp,
        cwd=str(protected.CONTROL_ROOT),
        command=harness.request.managed_argv(),
        claim_root=str(store.root),
    )
    with store._transaction():
        store._write(stale)

    def alive(pid: int) -> bool | None:
        return {
            900081: owner_alive,
            900082: child_alive,
            harness.owner: True,
            harness.child: True,
        }.get(pid)

    monkeypatch.setattr(claims, "_alive", alive)
    harness.request = replace(harness.request, takeover_stale=takeover)
    harness.chain()
    result = harness.launch()
    assert result["exit_code"] == expected
    assert harness.launches == (1 if expected == 0 else 0)


@pytest.mark.parametrize(
    "defect", ["parent", "owner_command", "child_command", "owner_cwd", "missing_owner"]
)
def test_unverified_or_changed_execution_chain_blocks(harness: Harness, defect: str) -> None:
    if defect == "parent":
        harness.launchd.process_rows[1] = harness.launchd.process_rows[1].replace(
            f"{harness.child} {harness.owner}", f"{harness.child} 900088"
        )
    elif defect == "owner_command":
        harness.launchd.process_rows[0] += " --unchecked-pid 900099"
    elif defect == "child_command":
        harness.launchd.process_rows[1] += " --extra"
    elif defect == "owner_cwd":
        harness.launchd.file_rows[0] = f"p{harness.owner}\nfcwd\nn/unrelated"
    else:
        harness.launchd.process_rows.pop(0)
    result = harness.launch()
    assert result["status"] != "SUCCESS"
    assert harness.stops == [] and harness.launchd.mutation_calls == []


def test_changed_claim_owner_between_snapshots_blocks(harness: Harness) -> None:
    def change() -> None:
        harness.launchd.process_rows[1] += " --changed"

    harness.during_sleep = change
    result = harness.launch()
    assert result["status"] == "FAILED" and harness.sleeps == [5.0]
    assert harness.launchd.mutation_calls == []


@pytest.mark.parametrize("role", ["primary", "scheduler", "shadow", "unrelated", "uncertain"])
def test_any_external_owner_or_uncertainty_blocks(harness: Harness, role: str) -> None:
    markers = {
        "primary": "b649_operational_prediction_loop.py",
        "scheduler": "b649_goalc_local_scheduler.py",
        "shadow": "b649_pair_rule_forward_shadow.py",
    }
    harness.external(
        str(harness.fixture.new / markers.get(role, "other-tool.py")),
        cwd=None if role == "uncertain" else str(harness.fixture.new),
    )
    result = harness.launch()
    assert result["status"] == "FAILED"
    assert harness.launchd.mutation_calls == []


def test_business_lock_busy_blocks(harness: Harness) -> None:
    with harness.fixture.primary_lock_path.open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = harness.launch()
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    assert result["status"] == "FAILED"
    assert harness.launchd.mutation_calls == []


@pytest.mark.parametrize("change", ["status", "plist", "external", "lock_identity"])
def test_two_snapshots_reject_intervening_changes(harness: Harness, change: str) -> None:
    def mutate() -> None:
        if change == "status":
            harness.launchd.status_by_path[harness.fixture.old] = " M drift.py\n"
        elif change == "plist":
            harness.fixture.plist_path.touch()
        elif change == "external":
            harness.external("python " + str(harness.fixture.old / "external.py"))
        else:
            harness.fixture.primary_lock_path.touch()

    harness.during_sleep = mutate
    result = harness.launch()
    assert result["status"] == "FAILED" and harness.sleeps == [5.0]
    assert harness.launchd.mutation_calls == []


def test_short_clock_interval_cannot_authorize_execution(harness: Harness) -> None:
    harness.during_sleep = lambda: setattr(harness, "elapsed", 4.9)
    result = harness.launch()
    assert result["status"] == "FAILED"
    assert "interval" in str(protected.record(result["stderr"])["text"])


def test_owner_appearing_at_mutation_boundary_blocks_next_action(harness: Harness) -> None:
    def mutate(argv: tuple[str, ...]) -> None:
        if argv[1] == "disable":
            harness.external("python " + str(harness.fixture.new / "unrelated.py"))

    harness.launchd.after_mutation = mutate
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    assert [call[1] for call in harness.launchd.mutation_calls] == ["disable"]
    assert harness.fixture.plist_path.read_bytes() == harness.fixture.old_plist_bytes


def test_managed_receipt_change_blocks_success_reuse(harness: Harness) -> None:
    harness.launch()
    with harness.fixture.receipt_path.open("ab") as target:
        target.write(b"\n")
    with pytest.raises(protected.ProtectedError, match="linkage changed"):
        harness.launch()
    assert harness.launches == 1


@pytest.mark.parametrize(
    "defect", ["symlink", "dangling", "hardlink", "fifo", "mode", "size", "json", "digest"]
)
def test_unsafe_execution_receipt_is_fail_closed(harness: Harness, defect: str) -> None:
    path = harness.request.receipt_path
    apply_request = cast(protected.Request, harness.request)
    if defect == "symlink":
        path.symlink_to(apply_request.plan_file)
    elif defect == "dangling":
        path.symlink_to(harness.fixture.root / "missing")
    elif defect == "hardlink":
        os.link(apply_request.plan_file, path)
    elif defect == "fifo":
        os.mkfifo(path, 0o600)
    else:
        path.write_bytes(b"x" * (protected.MAX_RECEIPT_BYTES + 1) if defect == "size" else b"{}")
        path.chmod(0o644 if defect == "mode" else 0o600)
        if defect == "json":
            path.write_text('{"status":1,"status":2}')
    with pytest.raises((protected.ProtectedError, OSError, ValueError)):
        harness.launch()
    assert harness.launches == 0


def test_receipt_parent_symlink_and_nonprivate_directory_refused(harness: Harness) -> None:
    alias = harness.fixture.root / "alias"
    alias.symlink_to(harness.fixture.scheduler_root, target_is_directory=True)
    with pytest.raises(protected.ProtectedError, match="symlinks"):
        protected.ReceiptFile(alias / protected.RECEIPT_NAME).read()
    harness.fixture.scheduler_root.chmod(0o755)
    with pytest.raises(protected.ProtectedError, match="0700"):
        harness.launch()
    assert harness.launches == 0


def test_receipt_atomic_replace_failure_keeps_previous_state(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.launch()
    target = protected.ReceiptFile(harness.request.receipt_path)
    before = target.read()
    assert before is not None
    raw = harness.request.receipt_path.read_bytes()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("atomic replace failed")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="atomic replace"):
        target.write({**before, "status": "INCOMPLETE_OR_AMBIGUOUS"}, expected=before)
    assert harness.request.receipt_path.read_bytes() == raw
    assert not list(harness.fixture.scheduler_root.glob("*.tmp"))
    assert not list(harness.fixture.scheduler_root.glob(".*.tmp"))


def test_bounded_stream_hash_covers_truncated_bytes() -> None:
    stream = protected.BoundedStream()
    content = "觀測" * protected.MAX_STREAM_BYTES
    stream.write(content)
    evidence = stream.evidence()
    assert evidence["bytes"] == len(content.encode())
    assert evidence["sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert evidence["truncated"] is True
    assert len(str(evidence["text"]).encode()) <= protected.MAX_STREAM_BYTES + 3


def test_cli_offers_no_pid_exemption_or_arbitrary_action() -> None:
    for option in ("--allow-pid", "--exclude-pid", "--command", "--receipt-root"):
        assert option not in protected.parser().format_help()
    with pytest.raises(SystemExit):
        protected.parser().parse_args(["rollback"])
    parsed = protected.parser().parse_args(
        [
            "rollback",
            "--receipt-file",
            "/tmp/managed-receipt.json",
            "--legacy-worktree",
            "/tmp/legacy",
            "--legacy-head",
            "3" * 40,
            "--legacy-tree",
            "4" * 40,
        ]
    )
    assert parsed.action == "rollback"


def test_managed_cli_routes_exact_request_to_protected_child(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def child(args: argparse.Namespace, *, runner: cutover.Runner) -> int:
        assert runner == harness.runner
        seen.append(args.protected_execution)
        return 74

    monkeypatch.setattr(protected, "run_managed_child", child)
    assert cutover.main(harness.request.managed_argv()[2:], runner=harness.runner) == 74
    assert seen == [harness.request.execution_id]


def test_direct_unclaimed_child_cannot_exempt_parent(harness: Harness) -> None:
    args = cutover.parser().parse_args(harness.request.managed_argv()[2:])
    with pytest.raises(protected.ProtectedError):
        protected.run_managed_child(args, runner=harness.runner)
    assert harness.stops == [] and harness.launchd.mutation_calls == []


def test_supervisor_final_write_failure_retains_blocking_child_capture(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = protected.ReceiptFile.write

    def write(
        self: protected.ReceiptFile, value: protected.Record, *, expected: protected.Record | None
    ) -> protected.Record:
        if value.get("phase") == "COMPLETED":
            raise OSError("owner completion interrupted")
        return original(self, value, expected=expected)

    monkeypatch.setattr(protected.ReceiptFile, "write", write)
    with pytest.raises(OSError, match="owner completion"):
        harness.launch()
    saved = protected.ReceiptFile(harness.request.receipt_path).read()
    assert saved is not None and saved["phase"] == "CHILD_COMPLETED"
    assert saved["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
        harness.launch()


def test_generic_claim_cannot_be_used_as_protected_pid_exemption(harness: Harness) -> None:
    proof = checkpoint.ControlledExecution(
        harness.request.claim_root,
        "arbitrary-key",
        harness.request.execution_id,
        str(uuid4()),
        (sys.executable, "unrelated.py", "--protected-execution", harness.request.execution_id),
        (sys.executable, "anything.py"),
        str(protected.CONTROL_ROOT),
        harness.request.sources,
    )
    with pytest.raises(checkpoint.Unverifiable, match="only the protected B649 command"):
        proof.verify({}, UID)


def test_changed_execution_digest_cannot_control_ownership(harness: Harness) -> None:
    proof = checkpoint.ControlledExecution(
        harness.request.claim_root,
        protected.TASK_KEY,
        "e" * 64,
        str(uuid4()),
        tuple(harness.request.managed_argv()),
        tuple(harness.request.owner_argv()),
        str(protected.CONTROL_ROOT),
        harness.request.sources,
    )
    with pytest.raises(checkpoint.Unverifiable, match="immutable identity"):
        proof.verify({}, UID)


def test_base_parent_behavior_strands_prestart_exec_failure(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.exec_failed = True
    monkeypatch.setattr(protected, "_prestart_failure_evidence", _preserve_legacy_prestart_result)
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS" and result["exit_code"] == 127
    assert result["gated_child_pid"] == harness.child
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    saved = protected.ReceiptFile(harness.request.receipt_path).read()
    assert saved is not None and saved["completed_at"]
    with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
        harness.launch()
    assert harness.launches == 1 and harness.stops == []


@pytest.mark.parametrize("exec_failure_code", [126, 127])
def test_candidate_terminalizes_prestart_failure_and_captures_process_output(
    harness: Harness, exec_failure_code: int
) -> None:
    harness.exec_failed = True
    harness.exit_override = exec_failure_code
    result = harness.launch()
    assert result["status"] == "FAILED" and result["result_status"] == "FAILED"
    assert result["exit_code"] == exec_failure_code
    assert "child_started_at" not in result and "child_completed_at" not in result
    prestart_evidence = protected.record(result["prestart_failure_evidence"])
    process_stdout = protected.record(result["process_stdout"])
    process_stderr = protected.record(result["process_stderr"])
    assert prestart_evidence["classification"] == "PRESTART_FAILURE_NO_MUTATION"
    assert process_stdout["text"] == harness.process_stdout.decode()
    assert process_stderr["text"] == harness.process_stderr.decode()
    assert process_stdout["sha256"] == hashlib.sha256(harness.process_stdout).hexdigest()
    assert process_stderr["sha256"] == hashlib.sha256(harness.process_stderr).hexdigest()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    assert protected.record(owner["release_evidence"])["verified"] is True
    assert harness.fixture.plist_path.read_bytes() == harness.fixture.old_plist_bytes
    assert harness.launchd.mutation_calls == []


def test_unrelated_exit_one_is_not_a_prestart_failure_candidate() -> None:
    staged: protected.Record = {"phase": "GATED"}
    assert protected._is_prestart_failure_candidate(staged, 126)
    assert protected._is_prestart_failure_candidate(staged, 127)
    assert not protected._is_prestart_failure_candidate(staged, 1)


def test_started_marker_blocks_prestart_terminalization(harness: Harness) -> None:
    harness.exec_failed = True

    def inject_started_marker() -> None:
        receipt_file = protected.ReceiptFile(harness.request.receipt_path)
        staged = receipt_file.read()
        assert staged is not None and staged["phase"] == "GATED"
        receipt_file.write(
            {**staged, "child_started_at": "synthetic-start-marker"}, expected=staged
        )

    harness.after_child = inject_started_marker
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    assert result["result_status"] == "INCOMPLETE_OR_AMBIGUOUS"
    assert result["child_started_at"] == "synthetic-start-marker"
    assert "prestart_failure_evidence" not in result
    assert harness.launchd.mutation_calls == []


@pytest.mark.parametrize("defect", ["mutation_started", "old_live_state"])
def test_ambiguous_prestart_evidence_stays_incomplete(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    harness.exec_failed = True
    observed_mutated_owner: list[protected.Record] = []
    original_inspect_owner = cutover.inspect_control_owner

    def inject_ambiguity() -> None:
        if defect == "mutation_started":

            def report_mutation_started(config: cutover.CutoverConfig) -> protected.Record | None:
                owner = original_inspect_owner(config)
                if owner is None:
                    return None
                mutated = {**owner, "mutation_started": True}
                observed_mutated_owner.append(mutated)
                return mutated

            monkeypatch.setattr(cutover, "inspect_control_owner", report_mutation_started)
        else:
            harness.fixture.plist_path.write_bytes(b"drifted OLD plist")

    harness.after_child = inject_ambiguity
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    assert result.get("result_status") == "INCOMPLETE_OR_AMBIGUOUS"
    assert "prestart_failure_evidence" not in result
    monkeypatch.setattr(cutover, "inspect_control_owner", original_inspect_owner)
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None
    assert owner["phase"] == "AUTHORIZED_PENDING"
    if defect == "mutation_started":
        assert observed_mutated_owner and observed_mutated_owner[-1]["mutation_started"] is True
        assert owner["mutation_started"] is False
    assert harness.launchd.mutation_calls == []


def test_claimstore_captures_bounded_process_output(tmp_path: Path) -> None:
    root = tmp_path / "claims"
    root.mkdir(mode=0o700)
    stdout, stderr = bytearray(), bytearray()
    code = claims.ClaimStore(root).run(
        "capture-output",
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'child-out\\n'); "
            "sys.stderr.buffer.write(b'child-err\\n')",
        ],
        capture_output=lambda name, chunk: (stdout if name == "stdout" else stderr).extend(chunk),
    )
    assert code == 0
    assert bytes(stdout) == b"child-out\n"
    assert bytes(stderr) == b"child-err\n"


def _reconcile_prestart_argv(
    incident: StrandedIncident,
    *,
    recovery_head: str = "a" * 40,
    recovery_tree: str = "b" * 40,
) -> list[str]:
    request = incident.request
    return [
        "reconcile-prestart-failure",
        "--source-worktree",
        str(request.config.source_worktree),
        "--expected-head",
        str(request.config.expected_head),
        "--expected-tree",
        str(request.config.expected_tree),
        "--legacy-worktree",
        str(request.legacy_worktree),
        "--legacy-head",
        request.legacy_head,
        "--legacy-tree",
        request.legacy_tree,
        "--plan-file",
        str(request.plan_file),
        "--reservation-id",
        str(request.reservation_id),
        "--operation-id",
        request.operation_id,
        "--stranded-protected-receipt-sha256",
        hashlib.sha256(request.receipt_path.read_bytes()).hexdigest(),
        "--managed-receipt-sha256",
        incident.managed_sha256,
        "--predecessor-protected-receipt-sha256",
        incident.predecessor_sha256,
        "--original-control-head",
        "d32620eda04e3e01c1cb135d822bb21e41f0de34",
        "--original-control-tree",
        "1f8c8878dc6d108014028d9abf588ed7b4593d50",
        "--current-recovery-control-head",
        recovery_head,
        "--current-recovery-control-tree",
        recovery_tree,
        "--plan-sha256",
        incident.plan_sha256,
    ]


def _incident_reconciliation_argv(incident: StrandedIncident) -> list[str]:
    return _reconcile_prestart_argv(incident)


def _write_snapshot(harness: Harness, incident: StrandedIncident) -> dict[Path, bytes | None]:
    config = incident.request.config
    paths = {
        config.receipt_path,
        incident.request.receipt_path,
        protected._prestart_reconciliation_record_path(
            config, str(incident.request.reservation_id)
        ),
        cutover._control_owner_path(config),
        cutover._control_owner_lock_path(config),
        config.plist_path,
        incident.request.plan_file,
        *config.scheduler_root.glob("*.superseded.json"),
    }
    claim_location = claims.ClaimStore(incident.request.claim_root).location(protected.TASK_KEY)
    paths.add(claim_location)
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def _configure_reconcile_cli(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    incident: StrandedIncident,
    *,
    recovery_head: str = "a" * 40,
    recovery_tree: str = "b" * 40,
) -> None:
    def fixed_config(_args: argparse.Namespace, *, for_action: str) -> cutover.CutoverConfig:
        del for_action
        return incident.request.config

    monkeypatch.setattr(
        protected,
        "build_reservation_config",
        fixed_config,
    )
    monkeypatch.setattr(
        cutover,
        "control_version",
        lambda: {"head": recovery_head, "tree": recovery_tree},
    )
    monkeypatch.setattr(cutover, "run_command", harness.runner)


def test_historical_incident_reconciles_once_then_successor_binds_archived_v5(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    request = incident.request
    stranded = protected.ReceiptFile(request.receipt_path).read()
    assert stranded is not None and stranded["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    assert "child_started_at" not in stranded
    assert (
        hashlib.sha256(request.config.receipt_path.read_bytes()).hexdigest()
        == incident.managed_sha256
    )
    owner = cutover.inspect_control_owner(request.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert claims.ClaimStore(request.claim_root).inspect(protected.TASK_KEY)["status"] == "ABSENT"
    assert tuple(harness.launchd.mutation_calls) == incident.mutations_before

    _configure_reconcile_cli(harness, monkeypatch, incident)
    snapshot = _write_snapshot(harness, incident)
    argv = _incident_reconciliation_argv(incident)
    assert protected.main(argv) == 0
    first_result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert first_result["status"] == "RECONCILED"
    assert not request.receipt_path.exists()
    failed_archive = request.receipt_path.with_name(
        f"{request.receipt_path.stem}.{stranded['execution_id']}.superseded.json"
    )
    assert failed_archive.read_bytes() == protected.canonical(stranded).encode() + b"\n"
    reconciliation_path = protected._prestart_reconciliation_record_path(
        request.config, str(request.reservation_id)
    )
    reconciliation, reconciliation_identity = protected._load_prestart_reconciliation(
        reconciliation_path
    )
    assert reconciliation["reason"] == "PRESTART_FAILURE_NO_MUTATION"
    assert (
        reconciliation["stranded_protected_receipt_sha256"]
        == hashlib.sha256(failed_archive.read_bytes()).hexdigest()
    )
    assert reconciliation["predecessor_protected_receipt_sha256"] == incident.predecessor_sha256
    assert reconciliation["unchanged_managed_receipt_sha256"] == incident.managed_sha256
    released = cutover.inspect_control_owner(request.config)
    assert released is not None and released["phase"] == "RELEASED"
    release_evidence = protected.record(released["release_evidence"])
    assert release_evidence["kind"] == "PRESTART_FAILURE_NO_MUTATION"
    assert release_evidence["reconciliation_record_sha256"] == reconciliation_identity.sha256

    after_first = _write_snapshot(harness, incident)
    assert protected.main(argv) == 0
    replay = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert replay["status"] == "ALREADY_RECONCILED"
    assert _write_snapshot(harness, incident) == after_first
    assert snapshot != after_first
    assert tuple(harness.launchd.mutation_calls) == incident.mutations_before

    recovery_head, recovery_tree = "a" * 40, "b" * 40
    v7_head, v7_tree = "c" * 40, "9" * 40
    v7_source = harness.fixture.worktree_parent / f"B649_PRODUCTION_{v7_head}"
    Fixture.make_source(v7_source)
    harness.launchd.worktree_identities[v7_source] = (v7_head, v7_tree, True)
    harness.launchd.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    harness.launchd.file_rows = ["p424242", "fcwd", "n/tmp"]
    v7_config = replace(
        request.config,
        source_worktree=v7_source,
        expected_head=v7_head,
        expected_tree=v7_tree,
        durable_ref=f"refs/heads/runtime/b649/{v7_head}",
    )
    v7_plan = cutover.build_plan(v7_config, runner=harness.launchd)
    assert v7_plan["status"] == "PASS"
    v7_plan_file = harness.fixture.root / "v7-plan.json"
    v7_plan_file.write_text(protected.canonical(v7_plan), encoding="utf-8")
    v7_plan_file.chmod(0o600)
    monkeypatch.setattr(protected, "control_identity", lambda: (recovery_head, recovery_tree))
    successor = protected.make_request(
        v7_config,
        request.legacy_worktree,
        request.legacy_head,
        request.legacy_tree,
        v7_plan_file,
        request.claim_root,
        reservation_id=str(uuid4()),
        prior_execution_receipt_sha256=incident.predecessor_sha256,
    )
    successor_proof = protected._require_released_success_evidence(
        successor, cutover.inspect_control_owner(v7_config)
    )
    assert successor_proof is not None
    assert successor.prior_execution_receipt_sha256 == incident.predecessor_sha256
    assert successor_proof["prior_protected_receipt_sha256"] == incident.predecessor_sha256
    next_owner = cutover.acquire_control_owner(
        v7_config,
        action="apply",
        target=protected.request_owner_target(successor),
        owner_kind="protected",
        reservation_id=successor.reservation_id,
        version={"head": recovery_head, "tree": recovery_tree},
        operation_id=successor.operation_id,
        managed_receipt_sha256=successor.managed_receipt_sha256,
        predecessor_release_evidence=successor_proof,
    )
    assert next_owner["phase"] == "AUTHORIZATION_PENDING"
    next_predecessor_proof = protected.record(next_owner["predecessor_release_evidence"])
    assert next_predecessor_proof["prior_protected_receipt_sha256"] == incident.predecessor_sha256
    assert (
        next_predecessor_proof["prior_protected_receipt_sha256"]
        != hashlib.sha256(failed_archive.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "defect",
    ["reservation", "operation", "stranded_sha", "managed_sha", "predecessor_sha"],
)
def test_historical_reconciliation_wrong_exact_identity_is_zero_write(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    _configure_reconcile_cli(harness, monkeypatch, incident)
    argv = _incident_reconciliation_argv(incident)
    parameter = {
        "reservation": "11111111-1111-4111-8111-111111111111",
        "operation": "1" * 32,
        "stranded_sha": "2" * 64,
        "managed_sha": "3" * 64,
        "predecessor_sha": "4" * 64,
    }[defect]
    flag = {
        "reservation": "--reservation-id",
        "operation": "--operation-id",
        "stranded_sha": "--stranded-protected-receipt-sha256",
        "managed_sha": "--managed-receipt-sha256",
        "predecessor_sha": "--predecessor-protected-receipt-sha256",
    }[defect]
    argv[argv.index(flag) + 1] = parameter
    before = _write_snapshot(harness, incident)
    assert protected.main(argv) == claims.UNVERIFIABLE
    assert "INCOMPLETE_OR_AMBIGUOUS" in capsys.readouterr().out
    assert _write_snapshot(harness, incident) == before


def test_historical_reconciliation_refuses_mutating_owner_without_writes(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    _configure_reconcile_cli(harness, monkeypatch, incident)
    stored = cutover._read_control_owner(incident.request.config)
    assert stored is not None
    owner, identity = stored
    cutover._save_control_owner(
        incident.request.config,
        {**owner, "phase": "MUTATION_IN_PROGRESS", "mutation_started": True},
        expected=identity,
    )
    before = _write_snapshot(harness, incident)
    assert protected.main(_incident_reconciliation_argv(incident)) == claims.UNVERIFIABLE
    assert "INCOMPLETE_OR_AMBIGUOUS" in capsys.readouterr().out
    assert _write_snapshot(harness, incident) == before


def test_historical_reconciliation_refuses_archived_predecessor_sha_drift(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    _configure_reconcile_cli(harness, monkeypatch, incident)
    archived = protected._find_archived_prior_receipt(
        incident.request.receipt_path,
        lambda sha256: sha256 == incident.predecessor_sha256,
    )
    assert archived is not None
    archived_path = Path(str(protected.record(archived).get("path")))
    archived_path.write_bytes(archived_path.read_bytes() + b"\n")
    before = _write_snapshot(harness, incident)
    assert protected.main(_incident_reconciliation_argv(incident)) == claims.UNVERIFIABLE
    assert "INCOMPLETE_OR_AMBIGUOUS" in capsys.readouterr().out
    assert _write_snapshot(harness, incident) == before


def test_historical_reconciliation_refuses_claim_and_old_live_drift_without_writes(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    _configure_reconcile_cli(harness, monkeypatch, incident)
    argv = _incident_reconciliation_argv(incident)
    before_claim = _write_snapshot(harness, incident)
    with monkeypatch.context() as claim_patch:

        def active_claim(_store: claims.ClaimStore, _task_key: str) -> dict[str, object]:
            return {"status": "ACTIVE"}

        claim_patch.setattr(
            claims.ClaimStore,
            "inspect",
            active_claim,
        )
        assert protected.main(argv) == claims.UNVERIFIABLE
        capsys.readouterr()
    assert _write_snapshot(harness, incident) == before_claim

    incident.request.config.plist_path.write_bytes(b"drifted OLD plist")
    before_drift = _write_snapshot(harness, incident)
    assert protected.main(argv) == claims.UNVERIFIABLE
    assert _write_snapshot(harness, incident) == before_drift
    assert tuple(harness.launchd.mutation_calls) == incident.mutations_before


def test_cross_control_version_requires_exact_explicit_reconciliation(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = _make_stranded_prestart_incident(
        harness, monkeypatch, preserve_legacy_parent_behavior=True
    )
    recovery = {"head": "a" * 40, "tree": "b" * 40}
    _configure_reconcile_cli(harness, monkeypatch, incident)
    before = _write_snapshot(harness, incident)
    with pytest.raises(cutover.CutoverSafetyError, match="control version changed"):
        cutover.resume_control_owner(incident.request.config, str(incident.request.reservation_id))
    with pytest.raises(cutover.CutoverSafetyError, match="control version changed"):
        cutover.release_control_owner(
            incident.request.config,
            str(incident.request.reservation_id),
            protected_receipt_path=incident.request.receipt_path,
        )
    assert _write_snapshot(harness, incident) == before

    argv = _incident_reconciliation_argv(incident)
    wrong = argv.copy()
    wrong[wrong.index("--current-recovery-control-head") + 1] = "c" * 40
    assert protected.main(wrong) == claims.UNVERIFIABLE
    capsys.readouterr()
    assert _write_snapshot(harness, incident) == before
    assert protected.main(argv) == 0
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["status"] == "RECONCILED"
    record, _ = protected._load_prestart_reconciliation(
        protected._prestart_reconciliation_record_path(
            incident.request.config, str(incident.request.reservation_id)
        )
    )
    assert record["original_control_identity"] == {
        "head": "d32620eda04e3e01c1cb135d822bb21e41f0de34",
        "tree": "1f8c8878dc6d108014028d9abf588ed7b4593d50",
    }
    assert record["recovery_control_identity"] == recovery


def test_claimstore_acquisition_monitor_and_release_are_inherited() -> None:
    assert protected.ReceiptClaimStore.run is claims.ClaimStore.run
    assert protected.ReceiptClaimStore._monitor is claims.ClaimStore._monitor
    assert protected.ReceiptClaimStore._transaction is claims.ClaimStore._transaction
    assert protected.ReceiptClaimStore._release is claims.ClaimStore._release


@pytest.mark.parametrize(
    "field", ["claim_owner", "supervisor_pid", "gated_child_pid", "stdout", "started_at"]
)
def test_missing_receipt_provenance_cannot_reuse_success(harness: Harness, field: str) -> None:
    harness.launch()
    value = protected.record(json.loads(harness.request.receipt_path.read_text()))
    del value[field]
    del value["receipt_sha256"]
    value["receipt_sha256"] = protected.digest(value)
    harness.request.receipt_path.write_text(protected.canonical(value))
    with pytest.raises(protected.ProtectedError, match="provenance is incomplete"):
        harness.launch()
    assert harness.launches == 1


@pytest.mark.parametrize("confirmed", [True, False])
def test_already_stopped_fsmonitor_requires_exact_negative_status(confirmed: bool) -> None:
    worktree = "/isolated/exact-worktree"
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[-1] == "stop":
            return subprocess.CompletedProcess(
                argv, 128, "", "fatal: fsmonitor--daemon is not running\n"
            )
        return subprocess.CompletedProcess(
            argv, 1, f"fsmonitor-daemon is not watching '{worktree}'\n" if confirmed else "", ""
        )

    if confirmed:
        protected.stop_fsmonitor(worktree, runner)
    else:
        with pytest.raises(protected.ProtectedError, match="stop is unverified"):
            protected.stop_fsmonitor(worktree, runner)
    assert calls == [
        ["git", "-c", "core.fsmonitor=false", "-C", worktree, "fsmonitor--daemon", verb]
        for verb in ("stop", "status")
    ]


def _reserve_request_owner(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> protected.Request | protected.RollbackRequest:
    version = {
        "head": harness.request.identity["control_head"],
        "tree": harness.request.identity["control_tree"],
    }
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    reservation_id = str(uuid4())
    request = replace(
        harness.request,
        reservation_id=reservation_id,
        owner_id_argument=False,
    )
    cutover.acquire_control_owner(
        request.config,
        action=request.action,
        target=protected.request_owner_target(request),
        owner_kind="protected",
        reservation_id=reservation_id,
        version=version,
    )
    cutover.bind_control_owner(
        request.config,
        reservation_id,
        action=request.action,
        target=protected.request_owner_target(request),
        operation_id=str(request.identity["operation_id"]),
        managed_receipt_sha256=cast(str | None, request.identity["managed_receipt_sha256"]),
        version=version,
    )
    cutover.authorize_control_owner(
        request.config,
        reservation_id,
        protected.request_owner_authorization(request),
    )
    harness.request = request
    harness.chain()
    return request


def test_protected_apply_blocks_when_another_durable_owner_is_pending(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = {
        "head": harness.request.identity["control_head"],
        "tree": harness.request.identity["control_tree"],
    }
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    target = protected.request_owner_target(harness.request)
    owner = cutover.acquire_control_owner(
        harness.fixture.config,
        action="apply",
        target=target,
        owner_kind="protected",
        version=version,
    )
    owner = cutover.bind_control_owner(
        harness.fixture.config,
        str(owner["reservation_id"]),
        action="apply",
        target=target,
        operation_id=str(harness.request.identity["operation_id"]),
        managed_receipt_sha256=cast(str | None, harness.request.identity["managed_receipt_sha256"]),
        version=version,
    )
    cutover.authorize_control_owner(
        harness.fixture.config,
        str(owner["reservation_id"]),
        {
            "reservation_id": owner["reservation_id"],
            "operation_id": owner["operation_id"],
            "managed_receipt_sha256": owner["managed_receipt_sha256"],
            "control_head": owner["control_head"],
            "control_tree": owner["control_tree"],
            "action": owner["action"],
            "target": target,
        },
    )

    with pytest.raises(cutover.CutoverSafetyError, match="blocks takeover"):
        harness.launch()

    assert harness.launches == 0
    assert harness.launchd.mutation_calls == []
    assert not harness.fixture.receipt_path.exists()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"


def test_new_protected_request_waits_for_explicit_owner_authorization(
    harness: Harness,
) -> None:
    pending = protected.launch(harness.request)

    assert pending["status"] == "AUTHORIZATION_PENDING"
    assert (
        protected.record(pending["authorization"])["operation_id"]
        == harness.request.identity["operation_id"]
    )
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZATION_PENDING"
    assert harness.launches == 0 and harness.launchd.mutation_calls == []

    harness.request = replace(
        harness.request,
        reservation_id=str(pending["reservation_id"]),
    )
    harness.chain()
    authorized = cutover.authorize_control_owner(
        harness.fixture.config,
        str(pending["reservation_id"]),
        protected.request_owner_authorization(harness.request),
    )
    assert authorized["phase"] == "AUTHORIZED_PENDING"

    result = harness.launch()
    assert result["status"] == "SUCCESS"


def test_same_authorized_protected_owner_resumes_and_releases(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _reserve_request_owner(harness, monkeypatch)

    result = harness.launch()

    assert result["status"] == "SUCCESS"
    assert result["identity"] == request.identity
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    assert owner["reservation_id"] == request.reservation_id


def test_terminal_protected_receipt_can_release_owner_after_worker_interruption(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_release = cutover.release_control_owner
    calls = 0

    def fail_first_release(
        selected_config: cutover.CutoverConfig,
        reservation_id: str,
        *,
        protected_receipt_path: Path | None = None,
    ) -> protected.Record:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise cutover.CutoverSafetyError("injected interruption after terminal receipt")
        return original_release(
            selected_config,
            reservation_id,
            protected_receipt_path=protected_receipt_path,
        )

    monkeypatch.setattr(cutover, "release_control_owner", fail_first_release)
    with pytest.raises(cutover.CutoverSafetyError, match="injected interruption"):
        harness.launch()
    assert harness.request.receipt_path.exists()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "TERMINAL_CAPTURE_PENDING"

    result = harness.launch()

    assert result["status"] == "SUCCESS" and result["reused"] is True
    assert harness.launches == 1
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"


def _managed_rollback_for_closure(
    harness: Harness,
) -> tuple[Path, bytes, dict[str, object], bytes]:
    assert harness.launch()["status"] == "SUCCESS"
    apply_receipt_path = harness.request.receipt_path
    apply_receipt_bytes = apply_receipt_path.read_bytes()
    harness.launchd.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    harness.launchd.file_rows = ["p424242", "fcwd", "n/tmp"]
    before = json.loads(harness.fixture.receipt_path.read_text(encoding="utf-8"))
    rolled_back = cutover.rollback(
        harness.fixture.config,
        receipt=before,
        runner=harness.launchd,
    )
    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    managed, identity, managed_bytes = cutover.read_control_json(harness.fixture.receipt_path)
    assert managed["status"] == "ROLLBACK_SUCCESS"
    assert identity.sha256
    return apply_receipt_path, apply_receipt_bytes, managed, managed_bytes


def _external_runtime_verification(
    managed: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    prestate = protected.record(managed["prestate"])
    restored_source = protected.record(prestate["old_source"])
    after = protected.record(managed["after"])
    plist = protected.record(after["plist"])
    launchd = protected.record(after["launchd"])
    verification: dict[str, object] = {
        "kind": "independent-runtime-verification-v1",
        "verified": True,
        "observer": "isolated-test-inspector",
        "source": restored_source,
        "runtime": prestate["old_runtime"],
        "plist_sha256": plist["sha256"],
        "launch_state": launchd["state"],
        "enabled": after["enabled"],
    }
    return restored_source, verification


def test_managed_only_lifecycle_closure_is_truthful_idempotent_and_preserves_receipts(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_path, apply_before, managed, managed_before = _managed_rollback_for_closure(harness)
    managed_identity, _ = cutover._file_identity(harness.fixture.receipt_path, missing_ok=False)
    assert managed_identity is not None
    restored_source, verification = _external_runtime_verification(managed)
    rollback_path = harness.fixture.scheduler_root / protected.ROLLBACK_RECEIPT_NAME
    assert not rollback_path.exists()

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("managed-only closure must not execute apply or rollback")

    monkeypatch.setattr(cutover, "apply", forbidden)
    monkeypatch.setattr(cutover, "rollback", forbidden)
    monkeypatch.setattr(protected, "launch", forbidden)
    closed = protected.close_managed_only_lifecycle(
        harness.fixture.config,
        operation_id=str(managed["operation_id"]),
        managed_receipt_sha256=managed_identity.sha256,
        restored_source=restored_source,
        runtime_verification=verification,
    )
    repeated = protected.close_managed_only_lifecycle(
        harness.fixture.config,
        operation_id=str(managed["operation_id"]),
        managed_receipt_sha256=managed_identity.sha256,
        restored_source=restored_source,
        runtime_verification=verification,
    )

    assert closed == repeated
    assert closed["disposition"] == "MANAGED_ONLY_EXTERNALLY_COMPLETED"
    assert closed["provenance"] == "MANAGED_ONLY_CONFIRMED"
    assert closed["protected_wrapper_executed"] is False
    assert (
        protected.classify_execution_provenance(
            harness.fixture.config,
            operation_id=str(managed["operation_id"]),
            managed_receipt_sha256=managed_identity.sha256,
        )
        == "MANAGED_ONLY_CONFIRMED"
    )
    assert (harness.fixture.receipt_path.read_bytes()) == managed_before
    assert apply_path.read_bytes() == apply_before
    assert not rollback_path.exists()


@pytest.mark.parametrize(
    "defect", ["operation", "receipt_hash", "source", "nonterminal", "ambiguous"]
)
def test_managed_only_lifecycle_closure_rejects_mismatch_and_recovery_state(
    harness: Harness, defect: str
) -> None:
    _apply_path, _apply_before, managed, _managed_before = _managed_rollback_for_closure(harness)
    if defect == "nonterminal":
        managed["status"] = "RECOVERY_REQUIRED"
        managed["phase"] = "RECOVERY_REQUIRED"
        harness.fixture.receipt_path.write_text(protected.canonical(managed), encoding="utf-8")
        harness.fixture.receipt_path.chmod(0o600)
    if defect == "ambiguous":
        rollback_path = harness.fixture.scheduler_root / protected.ROLLBACK_RECEIPT_NAME
        rollback_path.write_text("ambiguous\n", encoding="utf-8")
        rollback_path.chmod(0o600)
    current, identity, _ = cutover.read_control_json(harness.fixture.receipt_path)
    restored_source, verification = _external_runtime_verification(current)
    operation_id = str(current["operation_id"])
    receipt_hash = identity.sha256
    if defect == "operation":
        operation_id = uuid4().hex
    elif defect == "receipt_hash":
        receipt_hash = "a" * 64
    elif defect == "source":
        restored_source = {**restored_source, "head": "0" * 40}

    with pytest.raises(protected.ProtectedError):
        protected.close_managed_only_lifecycle(
            harness.fixture.config,
            operation_id=operation_id,
            managed_receipt_sha256=receipt_hash,
            restored_source=restored_source,
            runtime_verification=verification,
        )


def _apply_plan_file(harness: Harness) -> Path:
    assert isinstance(harness.request, protected.Request)
    return harness.request.plan_file


def test_deterministic_operation_id_stable_across_fresh_calls(harness: Harness) -> None:
    reservation_id = str(uuid4())
    first = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=reservation_id,
    )
    second = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=reservation_id,
    )
    assert first.identity["operation_id"] == second.identity["operation_id"]
    assert first.identity["operation_id"] == protected.apply_operation_id(
        reservation_id, first.plan_sha256, None
    )
    assert first.identity["prior_execution_receipt_sha256"] is None


def test_deterministic_operation_id_changes_with_load_bearing_inputs(
    harness: Harness,
) -> None:
    reservation_id = str(uuid4())
    baseline = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=reservation_id,
    )

    different_reservation = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=str(uuid4()),
    )
    assert different_reservation.identity["operation_id"] != baseline.identity["operation_id"]

    with_prior_receipt = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=reservation_id,
        prior_execution_receipt_sha256="a" * 64,
    )
    assert with_prior_receipt.identity["operation_id"] != baseline.identity["operation_id"]

    plan = json.loads(_apply_plan_file(harness).read_text(encoding="utf-8"))
    plan["_test_marker"] = "different-plan-bytes"
    mutated_plan_path = harness.fixture.root / "mutated-plan.json"
    mutated_plan_path.write_text(protected.canonical(plan), encoding="utf-8")
    mutated_plan_path.chmod(0o600)
    different_plan = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        mutated_plan_path,
        harness.request.claim_root,
        reservation_id=reservation_id,
    )
    assert different_plan.identity["operation_id"] != baseline.identity["operation_id"]


def _authorization_envelope(pending: protected.Record) -> dict[str, object]:
    return protected.record(pending["authorization"])


def _last_json_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    # A real spawn also exercises FakeChild.wait()'s own competing-launcher
    # probe, which prints an unrelated ClaimStore state line; main()'s own
    # canonical(result) output is always the final line.
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    return protected.record(json.loads(lines[-1]))


def _fixed_reservation_config(
    harness: Harness,
) -> Callable[..., cutover.CutoverConfig]:
    def build(_args: argparse.Namespace, *, for_action: str) -> cutover.CutoverConfig:
        return harness.fixture.config

    return build


def test_protected_status_cli_is_read_only_and_reports_owner_and_receipts(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        protected,
        "build_reservation_config",
        _fixed_reservation_config(harness),
    )
    exit_code = protected.main(
        [
            "status",
            "--for",
            "apply",
            "--source-worktree",
            str(harness.fixture.config.source_worktree),
            "--expected-head",
            str(harness.fixture.config.expected_head),
            "--expected-tree",
            str(harness.fixture.config.expected_tree),
        ]
    )
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "OK"
    assert report["owner"] is None
    assert report["managed_receipt"]["exists"] is False
    assert report["protected_apply_receipt"]["exists"] is False
    assert report["protected_rollback_receipt"]["exists"] is False
    assert harness.launches == 0
    assert not (harness.fixture.scheduler_root / protected.RECEIPT_NAME).exists()
    assert not (harness.fixture.scheduler_root / protected.ROLLBACK_RECEIPT_NAME).exists()


def _drive_reserve_authorize(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[list[str], dict[str, object]]:
    monkeypatch.setattr(
        protected,
        "build_reservation_config",
        _fixed_reservation_config(harness),
    )
    argv = list(harness.request.owner_argv()[2:])
    exit_code = protected.main(argv)
    assert exit_code == claims.REFUSED
    reserved = json.loads(capsys.readouterr().out)
    assert reserved["status"] == "AUTHORIZATION_PENDING"
    authorization = _authorization_envelope(reserved)
    # `harness.request` was built eagerly (reservation_id=None), so its own
    # operation ID took the pre-reservation fallback path; resync it to the
    # deterministic value `main()` actually bound so the harness's own
    # argv/process-row bookkeeping matches what the CLI really spawns.
    harness.request = replace(
        harness.request,
        reservation_id=str(reserved["reservation_id"]),
        operation_id=str(authorization["operation_id"]),
    )
    harness.chain()
    return argv, authorization


def _authorize_argv(authorization: dict[str, object]) -> list[str]:
    target = protected.record(authorization["target"])
    argv = [
        "authorize",
        "--for",
        str(authorization["action"]),
        "--source-worktree",
        str(target["source_worktree"]),
        "--expected-head",
        str(target["head"]),
        "--expected-tree",
        str(target["tree"]),
        "--reservation-id",
        str(authorization["reservation_id"]),
        "--operation-id",
        str(authorization["operation_id"]),
        "--control-head",
        str(authorization["control_head"]),
        "--control-tree",
        str(authorization["control_tree"]),
        "--target-source-worktree",
        str(target["source_worktree"]),
        "--target-head",
        str(target["head"]),
        "--target-tree",
        str(target["tree"]),
    ]
    if target.get("durable_ref") is not None:
        argv += ["--target-durable-ref", str(target["durable_ref"])]
    if authorization.get("managed_receipt_sha256") is not None:
        argv += ["--managed-receipt-sha256", str(authorization["managed_receipt_sha256"])]
    return argv


def test_protected_main_end_to_end_reserve_authorize_resume_apply(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert harness.launches == 0
    assert harness.launchd.mutation_calls == []
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZATION_PENDING"

    # A repeated reservation attempt (still pending) performs zero mutation.
    exit_code = protected.main(argv)
    assert exit_code == claims.REFUSED
    still_pending = json.loads(capsys.readouterr().out)
    assert still_pending["status"] == "AUTHORIZATION_PENDING"
    assert still_pending["authorization"] == authorization
    assert harness.launches == 0

    exit_code = protected.main(_authorize_argv(authorization))
    assert exit_code == 0
    authorized = json.loads(capsys.readouterr().out)
    assert authorized["phase"] == "AUTHORIZED_PENDING"

    exit_code = protected.main(argv)
    result = _last_json_line(capsys)
    assert exit_code == 0
    assert result["status"] == "SUCCESS"
    assert harness.launches == 1
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"

    # An exact rerun after terminal success verifies and reuses; no second spawn.
    exit_code = protected.main(argv)
    replay = _last_json_line(capsys)
    assert exit_code == 0
    assert replay["status"] == "SUCCESS" and replay["reused"] is True
    assert harness.launches == 1


def test_authorize_cli_rejects_managed_receipt_sha_drift(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A managed receipt from a prior cutover cycle can already sit at the
    # shared receipt path before this reservation exists at all; bind to it
    # so the authorization envelope carries a real, non-null SHA and this
    # test exercises the live re-read (not merely the pre-existing
    # bind-time-vs-envelope comparison already covered elsewhere).
    harness.fixture.receipt_path.write_text('{"status": "SUCCESS"}\n', encoding="utf-8")
    harness.fixture.receipt_path.chmod(0o600)
    harness.request = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
    )
    harness.chain()

    _argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert authorization["managed_receipt_sha256"] is not None

    drifted = harness.fixture.receipt_path.read_bytes() + b"\n"
    harness.fixture.receipt_path.write_bytes(drifted)
    harness.fixture.receipt_path.chmod(0o600)

    exit_code = protected.main(_authorize_argv(authorization))
    assert exit_code == claims.UNVERIFIABLE
    error = json.loads(capsys.readouterr().out)
    assert "managed receipt" in str(error.get("error", ""))
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZATION_PENDING"

    # Restore the exact receipt bytes the reservation bound to and confirm a
    # correctly-supplied authorization now succeeds; proves the refusal
    # above was specifically about the drifted bytes, not the flow shape.
    harness.fixture.receipt_path.write_bytes(drifted[:-1])
    harness.fixture.receipt_path.chmod(0o600)
    exit_code = protected.main(_authorize_argv(authorization))
    assert exit_code == 0
    authorized = json.loads(capsys.readouterr().out)
    assert authorized["phase"] == "AUTHORIZED_PENDING"


@pytest.mark.parametrize(
    "field",
    [
        "reservation-id",
        "operation-id",
        "control-head",
        "control-tree",
        "target-source-worktree",
        "target-head",
        "target-tree",
        "target-durable-ref",
        "for",
    ],
)
def test_authorize_cli_rejects_any_envelope_field_drift(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
) -> None:
    _argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    forged = _authorize_argv(authorization)
    index = forged.index("--" + field) + 1
    forged[index] = (
        "rollback"
        if field == "for"
        else "0" * 40
        if "head" in field or "tree" in field
        else str(uuid4())
    )
    exit_code = protected.main(forged)
    assert exit_code == claims.UNVERIFIABLE
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZATION_PENDING"


def test_abandon_cli_before_mutation_releases_owner(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    abandon_argv = [
        "abandon",
        "--for",
        "apply",
        "--source-worktree",
        str(harness.fixture.config.source_worktree),
        "--expected-head",
        str(harness.fixture.config.expected_head),
        "--expected-tree",
        str(harness.fixture.config.expected_tree),
        "--reservation-id",
        str(authorization["reservation_id"]),
    ]
    exit_code = protected.main(abandon_argv)
    assert exit_code == 0
    released = json.loads(capsys.readouterr().out)
    assert released["phase"] == "RELEASED"
    assert released["release_evidence"] == {
        "kind": "EXPLICIT_ABANDON_NO_MUTATION",
        "verified": True,
    }

    # Repeating abandon on an already-released owner blocks (durable owner no
    # longer matches this reservation's exact pre-mutation phase set).
    exit_code = protected.main(abandon_argv)
    assert exit_code == claims.UNVERIFIABLE
    capsys.readouterr()
    assert harness.launches == 0
    assert not harness.request.receipt_path.exists()

    # A fresh reserve after the abandoned+released owner starts a clean cycle.
    exit_code = protected.main(argv)
    assert exit_code == claims.REFUSED
    fresh = json.loads(capsys.readouterr().out)
    assert fresh["status"] == "AUTHORIZATION_PENDING"
    assert fresh["reservation_id"] != authorization["reservation_id"]


def test_abandon_cli_refuses_after_mutation_started(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()

    # Interrupt the gated child's terminal capture write. By this point
    # cutover.apply has already run check_control_owner(begin_mutation=True)
    # and flipped the owner to MUTATION_IN_PROGRESS, exactly like the
    # existing point="CHILD_COMPLETED" interruption-injection test above.
    original_write = protected.ReceiptFile.write

    def write(
        self: protected.ReceiptFile,
        value: protected.Record,
        *,
        expected: protected.Record | None,
    ) -> protected.Record:
        if value.get("phase") == "CHILD_COMPLETED" and expected is not None:
            raise OSError("isolated receipt write interruption")
        return original_write(self, value, expected=expected)

    monkeypatch.setattr(protected.ReceiptFile, "write", write)

    exit_code = protected.main(argv)
    interrupted = _last_json_line(capsys)
    assert exit_code != 0
    assert interrupted["status"] == "INCOMPLETE_OR_AMBIGUOUS"
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None
    assert owner["mutation_started"] is True
    assert owner["phase"] in {"MUTATION_IN_PROGRESS", "TERMINAL_CAPTURE_PENDING"}

    abandon_argv = [
        "abandon",
        "--for",
        "apply",
        "--source-worktree",
        str(harness.fixture.config.source_worktree),
        "--expected-head",
        str(harness.fixture.config.expected_head),
        "--expected-tree",
        str(harness.fixture.config.expected_tree),
        "--reservation-id",
        str(authorization["reservation_id"]),
    ]
    exit_code = protected.main(abandon_argv)
    assert exit_code == claims.UNVERIFIABLE
    error = json.loads(capsys.readouterr().out)
    assert "started mutation" in str(error.get("error", ""))
    owner_after = cutover.inspect_control_owner(harness.fixture.config)
    assert owner_after is not None
    assert owner_after["phase"] == owner["phase"]
    assert owner_after["mutation_started"] is True


def test_stale_protected_receipt_is_superseded_by_new_eligible_operation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_receipt_path, apply_receipt_bytes, _managed, _managed_bytes = (
        _managed_rollback_for_closure(harness)
    )
    assert harness.launches == 1

    prior_execution_id = json.loads(apply_receipt_bytes)["execution_id"]

    # A second managed cycle has already moved past the sealed prior receipt
    # (apply -> rollback), so a fresh reservation targeting the same fixed
    # slot must be eligible to supersede it rather than hard-block.
    fresh_plan = cutover.build_plan(harness.fixture.config, runner=harness.launchd)
    assert fresh_plan["status"] == "PASS"
    plan_path = harness.fixture.root / "plan-cycle3.json"
    plan_path.write_text(protected.canonical(fresh_plan))
    plan_path.chmod(0o600)
    request3 = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        plan_path,
        harness.request.claim_root,
    )
    assert request3.identity["prior_execution_receipt_sha256"] is not None

    harness.request = request3
    authorized_request3 = _reserve_request_owner(harness, monkeypatch)

    result = harness.launch()

    assert result["status"] == "SUCCESS"
    assert harness.launches == 2
    superseded_path = apply_receipt_path.with_name(
        f"{apply_receipt_path.stem}.{prior_execution_id}.superseded.json"
    )
    assert superseded_path.exists()
    assert superseded_path.read_bytes() == apply_receipt_bytes
    new_receipt = json.loads(apply_receipt_path.read_bytes())
    assert new_receipt["execution_id"] != prior_execution_id
    assert new_receipt["identity"]["reservation_id"] == authorized_request3.reservation_id


def test_ineligible_prior_receipt_fails_closed_with_zero_spawn(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert harness.launch()["status"] == "SUCCESS"
    apply_receipt_path = harness.request.receipt_path
    apply_receipt_bytes = apply_receipt_path.read_bytes()
    assert harness.launches == 1

    # No intervening managed cycle occurred (the live state is already the
    # apply's own "new" target), so nothing proves the sealed prior receipt
    # is no longer the active execution authority: a fresh reservation must
    # fail closed rather than supersede or spawn. Reuse the original
    # old->new plan; its validity against the unchanged config is not what
    # this test is exercising.
    request3 = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
    )

    harness.request = request3
    _reserve_request_owner(harness, monkeypatch)

    with pytest.raises(protected.ProtectedError, match="execution identity mismatch"):
        harness.launch()

    assert harness.launches == 1
    assert apply_receipt_path.read_bytes() == apply_receipt_bytes
    assert not list(apply_receipt_path.parent.glob("*.superseded.json"))


def _supersession_cycle(harness: Harness) -> tuple[Path, bytes]:
    path, raw, _managed, _managed_bytes = _managed_rollback_for_closure(harness)
    plan = cutover.build_plan(harness.fixture.config, runner=harness.launchd)
    assert plan["status"] == "PASS"
    plan_path = harness.fixture.root / "next-plan.json"
    plan_path.write_text(protected.canonical(plan))
    plan_path.chmod(0o600)
    harness.request = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        plan_path,
        harness.request.claim_root,
    )
    harness.chain()
    return path, raw


def test_supersession_cli_reserves_before_archive_and_links_preserved_evidence(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _supersession_cycle(harness)
    capsys.readouterr()
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    assert authorization["operation_id"] == protected.apply_operation_id(
        str(authorization["reservation_id"]),
        hashlib.sha256(_apply_plan_file(harness).read_bytes()).hexdigest(),
        hashlib.sha256(raw).hexdigest(),
    )
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    assert path.read_bytes() == raw
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    prior_id = json.loads(raw)["execution_id"]
    archive = path.with_name(f"{path.stem}.{prior_id}.superseded.json")
    assert archive.read_bytes() == raw
    assert archive.stat().st_nlink == 1
    assert result["superseded_execution_receipt"] == {
        "path": str(archive),
        "execution_id": prior_id,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert harness.launches == 2
    assert protected.main(argv) == 0
    replay = _last_json_line(capsys)
    assert replay["reused"] is True
    assert replay["execution_id"] == result["execution_id"]
    assert harness.launches == 2
    assert archive.read_bytes() == raw


@pytest.mark.parametrize(
    "defect",
    [
        "nonterminal",
        "ambiguous",
        "active_claim",
        "prior_sha",
        "managed_phase",
        "managed_status",
        "managed_operation",
        "managed_plan",
        "managed_schema",
        "link_path",
        "link_missing",
        "archive_conflict",
    ],
)
def test_supersession_ineligible_variants_never_spawn(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    path, raw = _supersession_cycle(harness)
    prior = protected.record(json.loads(raw))
    if defect in {"nonterminal", "ambiguous", "link_path", "link_missing"}:
        if defect == "nonterminal":
            prior.update(phase="STARTED", status="INCOMPLETE_OR_AMBIGUOUS", completed_at=None)
        elif defect == "ambiguous":
            prior["status"] = "INCOMPLETE_OR_AMBIGUOUS"
        elif defect == "link_path":
            prior["managed_receipt"] = {
                **protected.record(prior["managed_receipt"]),
                "path": str(path),
            }
        else:
            prior["managed_receipt"] = {}
        protected.ReceiptFile(path).write(prior, expected=protected.ReceiptFile(path).read())
    if defect.startswith("managed_"):
        managed = protected.record(json.loads(harness.fixture.receipt_path.read_bytes()))
        field, value = {
            "managed_phase": ("phase", "RECOVERY_REQUIRED"),
            "managed_status": ("status", "SUCCESS"),
            "managed_operation": ("operation_id", "unrelated-operation"),
            "managed_plan": ("plan_digest", "f" * 64),
            "managed_schema": ("schema_version", "unknown"),
        }[defect]
        managed[field] = value
        harness.fixture.receipt_path.write_text(protected.canonical(managed))
    harness.request = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
    )
    if defect == "prior_sha":
        harness.request = replace(harness.request, prior_execution_receipt_sha256="f" * 64)
    _reserve_request_owner(harness, monkeypatch)
    store = claims.ClaimStore(harness.request.claim_root)
    claim_record = cast(claims.Metadata, prior["claim_owner"])
    if defect == "active_claim":
        store._write(claim_record)
    archive = path.with_name(f"{path.stem}.{prior['execution_id']}.superseded.json")
    if defect == "archive_conflict":
        archive.write_bytes(b"conflicting archive\n")
        archive.chmod(0o600)
    before = path.read_bytes()
    mutation_count = len(harness.launchd.mutation_calls)
    try:
        with pytest.raises((protected.ProtectedError, cutover.CutoverError)):
            protected.launch(harness.request)
        assert harness.launches == 1
        assert len(harness.launchd.mutation_calls) == mutation_count
        assert path.read_bytes() == before
        if defect == "archive_conflict":
            assert archive.read_bytes() == b"conflicting archive\n"
        else:
            assert not archive.exists()
    finally:
        if defect == "active_claim":
            store._release(claim_record)


def test_same_execution_is_never_superseded(harness: Harness) -> None:
    result = harness.launch()
    path = harness.request.receipt_path
    raw = path.read_bytes()
    assert (
        protected.supersede_prior_execution_receipt(
            harness.request, protected.ReceiptFile(path), result
        )
        is False
    )
    assert path.read_bytes() == raw
    assert harness.launch()["reused"] is True
    assert harness.launches == 1


def test_resume_rejects_plan_bytes_changed_after_authorization(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    path = _apply_plan_file(harness)
    path.write_bytes(path.read_bytes() + b"\n")
    assert protected.main(argv) == claims.UNVERIFIABLE
    error = _last_json_line(capsys)
    assert "operation" in str(error.get("error"))
    assert harness.launches == 0
    assert harness.launchd.mutation_calls == []


@pytest.mark.parametrize("authorized", [False, True])
def test_abandon_cli_records_explicit_live_drift_and_stale_pid_never_releases(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    authorized: bool,
) -> None:
    _argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    if authorized:
        assert protected.main(_authorize_argv(authorization)) == 0
        capsys.readouterr()

    def stale_pid(_pid: int) -> str:
        return "STALE_PROCESS"

    monkeypatch.setattr(cutover, "_pid_state", stale_pid)
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == (
        "AUTHORIZED_PENDING" if authorized else "AUTHORIZATION_PENDING"
    )
    assert owner["worker_state"] == "STALE_PROCESS"
    harness.fixture.receipt_path.write_text('{"drift":true}\n')
    harness.fixture.receipt_path.chmod(0o600)
    argv = ["abandon", "--for", "apply", "--reservation-id", str(authorization["reservation_id"])]
    assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    live_sha = hashlib.sha256(harness.fixture.receipt_path.read_bytes()).hexdigest()
    assert protected.main([*argv, "--observed-managed-receipt-sha256", live_sha]) == 0
    released = _last_json_line(capsys)
    assert released["phase"] == "RELEASED"
    evidence = harness.fixture.scheduler_root / (
        f"b649-control-owner-managed-receipt-drift.{authorization['reservation_id']}.json"
    )
    recorded = json.loads(evidence.read_bytes())
    assert recorded["observed_managed_receipt_sha256"] == live_sha
    assert recorded["expected_managed_receipt_sha256"] is None
    assert harness.launches == 0


def test_terminal_capture_resume_verifies_before_release_without_second_child(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    original_release = cutover.release_control_owner

    def interrupted(*_args: object, **_kwargs: object) -> cutover.Record:
        raise OSError("crash before terminal verification/release")

    with monkeypatch.context() as fault:
        fault.setattr(cutover, "release_control_owner", interrupted)
        assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "TERMINAL_CAPTURE_PENDING"
    raw = harness.fixture.receipt_path.read_bytes()
    harness.fixture.receipt_path.write_bytes(raw + b"\n")
    assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "TERMINAL_CAPTURE_PENDING"
    harness.fixture.receipt_path.write_bytes(raw)
    observed: list[str] = []

    def release(
        config: cutover.CutoverConfig,
        reservation_id: str,
        *,
        protected_receipt_path: Path | None = None,
    ) -> cutover.Record:
        before = cutover.inspect_control_owner(config)
        assert before is not None and before["phase"] == "TERMINAL_CAPTURE_PENDING"
        assert protected_receipt_path is not None
        terminal = protected.ReceiptFile(protected_receipt_path).read()
        assert terminal is not None and terminal["phase"] == "COMPLETED"
        observed.append("verified terminal before release")
        return original_release(
            config, reservation_id, protected_receipt_path=protected_receipt_path
        )

    monkeypatch.setattr(cutover, "release_control_owner", release)
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert result["reused"] is True
    assert observed == ["verified terminal before release"]
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    assert harness.launches == 1


def _fresh_cli_session(
    fixture: Fixture,
    plan_path: Path,
    argv: list[str],
    channel: Connection,
    identities: dict[Path, tuple[str, str, bool]] | None = None,
    legacy: tuple[str, str] | None = None,
    barrier: Barrier | None = None,
    boot: int = 0,
) -> None:
    """Spawned interpreter: only disk state, CLI argv and hermetic OS seams survive."""
    output, errors = io.StringIO(), io.StringIO()
    try:
        with (
            pytest.MonkeyPatch.context() as patches,
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            if boot:
                simulate_reboot(patches, fixture.root, boot)
            harness = Harness(
                fixture,
                patches,
                existing_plan=plan_path,
                legacy_head=legacy[0] if legacy else OLD_HEAD,
                legacy_tree=legacy[1] if legacy else OLD_TREE,
            )
            if identities is not None:
                # Current-success supersession reconciles live launchd state in the
                # supervising process; that must observe the fake, never launchctl.
                harness.launchd.worktree_identities.update(identities)
                patches.setattr(cutover, "run_command", harness.runner)
            patches.setattr(
                protected, "build_reservation_config", _fixed_reservation_config(harness)
            )
            original_launch = protected.launch

            def launch(request: protected.Request | protected.RollbackRequest) -> protected.Record:
                # Observe the real CLI reconstruction; no Request is carried
                # from the reserving interpreter to the resuming interpreter.
                harness.request = request
                harness.chain()
                return original_launch(request)

            patches.setattr(protected, "launch", launch)
            if barrier is not None:
                barrier.wait(30)
            code = protected.main(argv)
            owner = cutover.inspect_control_owner(fixture.config)
            channel.send(
                {
                    "code": code,
                    "output": output.getvalue(),
                    "errors": errors.getvalue(),
                    "pid": os.getpid(),
                    "launches": harness.launches,
                    "mutations": len(harness.launchd.mutation_calls),
                    "owner": owner,
                    "started": harness.observed_started,
                }
            )
    finally:
        channel.close()


def _invoke_fresh_cli(
    fixture: Fixture,
    plan_path: Path,
    argv: list[str],
    *,
    identities: dict[Path, tuple[str, str, bool]] | None = None,
    legacy: tuple[str, str] | None = None,
    boot: int = 0,
) -> protected.Record:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_fresh_cli_session,
        args=(fixture, plan_path, argv, sender, identities, legacy, None, boot),
    )
    process.start()
    sender.close()
    try:
        assert receiver.poll(30), "fresh CLI timed out"
        result = protected.record(receiver.recv())
        process.join(10)
        assert process.exitcode == 0
        return result
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(10)
        process.close()


def _invoke_fresh_cli_concurrently(
    fixture: Fixture,
    plan_path: Path,
    argv: list[str],
    *,
    count: int,
    identities: dict[Path, tuple[str, str, bool]],
    legacy: tuple[str, str],
) -> list[protected.Record]:
    """Start ``count`` real interpreters against one authorization at the same instant."""
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(count)
    started: list[tuple[Connection, BaseProcess]] = []
    for _ in range(count):
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_fresh_cli_session,
            args=(fixture, plan_path, argv, sender, identities, legacy, barrier),
        )
        process.start()
        sender.close()
        started.append((receiver, process))
    results: list[protected.Record] = []
    try:
        for receiver, process in started:
            assert receiver.poll(60), "concurrent fresh CLI timed out"
            results.append(protected.record(receiver.recv()))
            process.join(10)
            assert process.exitcode == 0
        return results
    finally:
        for receiver, process in started:
            receiver.close()
            if process.is_alive():
                process.terminate()
                process.join(10)
            process.close()


def test_fresh_process_cli_plan_reserve_authorize_apply_and_terminal_replay(
    tmp_path: Path,
) -> None:
    fixture = Fixture(tmp_path)
    runner = FakeLaunchd(fixture)
    before = {p: p.read_bytes() for p in fixture.root.rglob("*") if p.is_file()}
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    assert {p: p.read_bytes() for p in fixture.root.rglob("*") if p.is_file()} == before
    assert runner.mutation_calls == []
    plan_path = fixture.root / "plan.json"
    plan_path.write_text(protected.canonical(plan))
    plan_path.chmod(0o600)
    request = protected.make_request(
        fixture.config,
        fixture.old,
        OLD_HEAD,
        OLD_TREE,
        plan_path,
        fixture.root / "claims",
    )
    argv = request.owner_argv()[2:]
    reserve = _invoke_fresh_cli(fixture, plan_path, argv)
    pending = protected.record(json.loads(str(reserve["output"]).splitlines()[-1]))
    assert reserve["code"] == claims.REFUSED
    assert pending["status"] == "AUTHORIZATION_PENDING"
    assert reserve["launches"] == reserve["mutations"] == 0
    authorization = _authorization_envelope(pending)
    authorize = _invoke_fresh_cli(fixture, plan_path, _authorize_argv(authorization))
    assert authorize["code"] == 0
    assert protected.record(authorize["owner"])["phase"] == "AUTHORIZED_PENDING"
    assert authorize["launches"] == authorize["mutations"] == 0
    applied = _invoke_fresh_cli(fixture, plan_path, argv)
    assert applied["code"] == 0, applied["output"]
    assert applied["launches"] == 1 and cast(int, applied["mutations"]) > 0
    assert protected.record(applied["started"])["phase"] == "STARTED"
    owner = protected.record(applied["owner"])
    assert owner["phase"] == "RELEASED"
    assert protected.record(owner["release_evidence"])["verified"] is True
    assert owner["authorization"] == authorization
    receipt_path = fixture.scheduler_root / protected.RECEIPT_NAME
    terminal_before = receipt_path.read_bytes()
    replay = _invoke_fresh_cli(fixture, plan_path, argv)
    assert replay["code"] == 0, replay["output"]
    replayed = protected.record(json.loads(str(replay["output"]).splitlines()[-1]))
    assert replayed["reused"] is True
    assert protected.record(replayed["identity"])["operation_id"] == authorization["operation_id"]
    assert replay["launches"] == replay["mutations"] == 0
    assert receipt_path.read_bytes() == terminal_before
    assert len({run["pid"] for run in (reserve, authorize, applied, replay)}) == 4


def test_managed_receipt_drift_after_authorization_refuses_before_mutation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    harness.fixture.receipt_path.write_text('{"drift": true}\n')
    harness.fixture.receipt_path.chmod(0o600)
    code = protected.main(argv)
    error = _last_json_line(capsys)
    assert code == claims.UNVERIFIABLE
    assert "receipt" in str(error.get("error", error.get("status"))).lower()
    assert harness.launchd.mutation_calls == []
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["mutation_started"] is False


def test_abandon_cannot_treat_missing_live_receipt_as_explicit_drift_consent(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    harness.fixture.receipt_path.write_text('{"prior":true}\n')
    harness.fixture.receipt_path.chmod(0o600)
    _argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    harness.fixture.receipt_path.unlink()
    assert (
        protected.main(
            [
                "abandon",
                "--for",
                "apply",
                "--reservation-id",
                str(authorization["reservation_id"]),
            ]
        )
        == claims.UNVERIFIABLE
    )
    capsys.readouterr()
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZATION_PENDING"


def test_supersession_reuses_byte_identical_archive_without_overwriting_it(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, raw = _supersession_cycle(harness)
    prior_id = json.loads(raw)["execution_id"]
    archive = path.with_name(f"{path.stem}.{prior_id}.superseded.json")
    archive.write_bytes(raw)
    archive.chmod(0o600)
    before = archive.stat()
    _reserve_request_owner(harness, monkeypatch)
    assert harness.launch()["status"] == "SUCCESS"
    assert archive.read_bytes() == raw
    assert archive.stat().st_ino == before.st_ino
    assert archive.stat().st_mtime_ns == before.st_mtime_ns
    assert harness.launches == 2


def test_archive_rechecks_bound_sha_before_removing_original(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, raw = _supersession_cycle(harness)
    _reserve_request_owner(harness, monkeypatch)
    archive_to = protected.ReceiptFile.archive_to

    def changed(self: protected.ReceiptFile, name: str, *, expected_sha256: str) -> None:
        self.path.write_bytes(raw + b"\n")
        archive_to(self, name, expected_sha256=expected_sha256)

    monkeypatch.setattr(protected.ReceiptFile, "archive_to", changed)
    with pytest.raises(protected.ProtectedError, match="changed before archive"):
        harness.launch()
    assert path.read_bytes() == raw + b"\n"
    assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1


def test_released_owner_cannot_authorize_supersession(harness: Harness) -> None:
    path, raw = _supersession_cycle(harness)
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    harness.request = replace(harness.request, reservation_id=str(owner["reservation_id"]))
    with pytest.raises(protected.ProtectedError, match="execution identity mismatch"):
        protected.launch(harness.request)
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1


def test_supersession_validates_prior_release_separately_from_different_successor(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, raw = _supersession_cycle(harness)
    successor = harness.fixture.worktree_parent / f"B649_PRODUCTION_{'7' * 40}"
    Fixture.make_source(successor)
    harness.launchd.worktree_identities[successor] = ("7" * 40, "8" * 40, True)
    harness.fixture.new = successor
    harness.fixture.config = replace(
        harness.fixture.config,
        source_worktree=successor,
        expected_head="7" * 40,
        expected_tree="8" * 40,
        durable_ref=f"refs/heads/runtime/b649/{'7' * 40}",
    )
    harness.launchd.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    harness.launchd.file_rows = ["p424242", "fcwd", "n/tmp"]
    plan = cutover.build_plan(harness.fixture.config, runner=harness.launchd)
    assert plan["status"] == "PASS"
    plan_path = _apply_plan_file(harness)
    plan_path.write_text(protected.canonical(plan))
    harness.request = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        OLD_HEAD,
        OLD_TREE,
        plan_path,
        harness.request.claim_root,
    )
    _reserve_request_owner(harness, monkeypatch)
    result = harness.launch()
    assert result["status"] == "SUCCESS"
    assert harness.launches == 2
    assert harness.launchd.loaded_source == successor
    archive = Path(str(protected.record(result["superseded_execution_receipt"])["path"]))
    assert archive.read_bytes() == raw
    assert path.exists()
    assert harness.launch()["reused"] is True
    assert harness.launches == 2


@pytest.mark.parametrize("damage", [None, "archive_bytes", "archive_name", "missing", "plan"])
def test_fresh_process_resume_after_completed_archive_preserves_frozen_prior_sha(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    damage: str | None,
) -> None:
    path, raw = _supersession_cycle(harness)
    capsys.readouterr()
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    archive_to = protected.ReceiptFile.archive_to

    def interrupted(self: protected.ReceiptFile, name: str, *, expected_sha256: str) -> None:
        archive_to(self, name, expected_sha256=expected_sha256)
        raise OSError("process interrupted after durable archive")

    with monkeypatch.context() as fault:
        fault.setattr(protected.ReceiptFile, "archive_to", interrupted)
        assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    assert not path.exists()
    archive = path.with_name(f"{path.stem}.{json.loads(raw)['execution_id']}.superseded.json")
    assert archive.read_bytes() == raw
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert harness.launches == 1
    if damage == "archive_bytes":
        archive.write_bytes(raw + b"\n")
    elif damage == "archive_name":
        archive.rename(path.with_name(f"{path.stem}.{'f' * 64}.superseded.json"))
    elif damage == "missing":
        archive.unlink()
    elif damage == "plan":
        plan_path = _apply_plan_file(harness)
        plan_path.write_bytes(plan_path.read_bytes() + b"\n")
    # This invocation has no in-memory Request or supersession evidence.
    resumed = _invoke_fresh_cli(harness.fixture, _apply_plan_file(harness), argv)
    if damage is not None:
        assert resumed["code"] == claims.UNVERIFIABLE
        assert resumed["launches"] == resumed["mutations"] == 0
        assert protected.record(resumed["owner"])["phase"] == "AUTHORIZED_PENDING"
        return
    assert resumed["code"] == 0, resumed["output"]
    assert resumed["launches"] == 1
    result = protected.record(json.loads(str(resumed["output"]).splitlines()[-1]))
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]
    assert (
        protected.record(result["identity"])["prior_execution_receipt_sha256"]
        == hashlib.sha256(raw).hexdigest()
    )
    assert result["superseded_execution_receipt"] == {
        "path": str(archive),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "execution_id": json.loads(raw)["execution_id"],
    }
    assert protected.record(resumed["owner"])["phase"] == "RELEASED"
    replay = _invoke_fresh_cli(harness.fixture, _apply_plan_file(harness), argv)
    assert replay["code"] == 0 and replay["launches"] == replay["mutations"] == 0
    assert archive.read_bytes() == raw


SUCCESSOR_HEAD = "7" * 40
SUCCESSOR_TREE = "8" * 40
THIRD_HEAD = "a" * 40
THIRD_TREE = "b" * 40


def _advance_to_successor(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    legacy_head: str,
    legacy_tree: str,
    head: str,
    tree: str,
    name: str | None = None,
) -> None:
    """Point the fixture at the next chain link.

    What the last apply left live becomes the legacy side and ``head`` becomes the
    new target. The harness request is rebuilt eagerly from the resulting plan.
    """
    live = harness.fixture.new
    successor = harness.fixture.worktree_parent / (name or f"B649_PRODUCTION_{head}")
    Fixture.make_source(successor)
    harness.launchd.worktree_identities[successor] = (head, tree, True)
    harness.fixture.old = live
    harness.fixture.new = successor
    harness.fixture.config = replace(
        harness.fixture.config,
        source_worktree=successor,
        expected_head=head,
        expected_tree=tree,
        durable_ref=f"refs/heads/runtime/b649/{head}",
    )
    harness.launchd.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    harness.launchd.file_rows = ["p424242", "fcwd", "n/tmp"]
    plan = cutover.build_plan(harness.fixture.config, runner=harness.launchd)
    assert plan["status"] == "PASS", plan.get("failures")
    plan_path = harness.fixture.root / f"plan-{head}.json"
    plan_path.write_text(protected.canonical(plan))
    plan_path.chmod(0o600)
    harness.request = protected.make_request(
        harness.fixture.config,
        live,
        legacy_head,
        legacy_tree,
        plan_path,
        harness.request.claim_root,
    )
    harness.chain()
    # The pre-archive live reconciliation runs in the supervising process, so it
    # must observe the fake launchd and never the real one.
    monkeypatch.setattr(cutover, "run_command", harness.runner)


def _current_success_cycle(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    head: str = SUCCESSOR_HEAD,
    tree: str = SUCCESSOR_TREE,
    name: str | None = None,
) -> tuple[Path, bytes]:
    """OLD -> NEW succeeds and stays live; request NEW -> successor from that state."""
    assert harness.launch()["status"] == "SUCCESS"
    path = harness.request.receipt_path
    raw = path.read_bytes()
    _advance_to_successor(
        harness,
        monkeypatch,
        legacy_head=NEW_HEAD,
        legacy_tree=NEW_TREE,
        head=head,
        tree=tree,
        name=name,
    )
    return path, raw


def _reserve_and_authorize(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[list[str], dict[str, object]]:
    """The real reserve then authorize CLI, which is what freezes the release proof."""
    capsys.readouterr()
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    return argv, authorization


def _archive_path(path: Path, raw: bytes) -> Path:
    return path.with_name(f"{path.stem}.{json.loads(raw)['execution_id']}.superseded.json")


def test_current_success_receipt_is_superseded_by_next_authorized_apply(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    raw_sha = hashlib.sha256(raw).hexdigest()
    managed_before = harness.fixture.receipt_path.read_bytes()
    prior_owner = cutover.inspect_control_owner(harness.fixture.config)
    assert prior_owner is not None and prior_owner["phase"] == "RELEASED"
    assert "predecessor_release_evidence" not in prior_owner
    capsys.readouterr()
    argv, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    assert authorization["operation_id"] == protected.apply_operation_id(
        str(authorization["reservation_id"]),
        hashlib.sha256(_apply_plan_file(harness).read_bytes()).hexdigest(),
        raw_sha,
    )
    assert authorization["managed_receipt_sha256"] == hashlib.sha256(managed_before).hexdigest()
    assert path.read_bytes() == raw
    # The RELEASED owner is gone after reserve; its release proof now lives in the
    # durable reservation, bound to this exact reservation and operation.
    reserved = cutover.inspect_control_owner(harness.fixture.config)
    assert reserved is not None and reserved["phase"] == "AUTHORIZATION_PENDING"
    assert reserved["reservation_id"] != prior_owner["reservation_id"]
    proof = protected.record(reserved["predecessor_release_evidence"])
    assert proof["prior_reservation_id"] == prior_owner["reservation_id"]
    assert proof["prior_operation_id"] == prior_owner["operation_id"]
    assert proof["prior_release_evidence"] == prior_owner["release_evidence"]
    assert proof["prior_protected_receipt_sha256"] == raw_sha
    assert proof["prior_managed_receipt_sha256"] == hashlib.sha256(managed_before).hexdigest()
    assert proof["new_reservation_id"] == authorization["reservation_id"]
    assert proof["new_operation_id"] == authorization["operation_id"]
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    # Neither reserve nor authorize retires the prior receipt.
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1

    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    prior_id = json.loads(raw)["execution_id"]
    archive = _archive_path(path, raw)
    assert result["status"] == "SUCCESS"
    assert archive.read_bytes() == raw
    assert archive.stat().st_nlink == 1
    assert result["superseded_execution_receipt"] == {
        "path": str(archive),
        "execution_id": prior_id,
        "sha256": raw_sha,
    }
    assert protected.record(result["identity"])["prior_execution_receipt_sha256"] == raw_sha
    assert harness.launches == 2
    assert harness.launchd.loaded_source == harness.fixture.new
    managed = protected.record(json.loads(harness.fixture.receipt_path.read_bytes()))
    assert managed["status"] == "SUCCESS"
    assert managed["operation_id"] == authorization["operation_id"]
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    assert owner["predecessor_release_evidence"] == proof
    assert (
        protected.record(owner["release_evidence"])["protected_receipt_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )

    assert protected.main(argv) == 0
    replay = _last_json_line(capsys)
    assert replay["reused"] is True
    assert replay["execution_id"] == result["execution_id"]
    assert harness.launches == 2
    assert archive.read_bytes() == raw
    # The successor's rollback binds its own managed receipt, not the archive.
    rollback = protected.make_rollback_request(
        harness.fixture.config,
        harness.fixture.old,
        NEW_HEAD,
        NEW_TREE,
        harness.request.claim_root,
    )
    assert (
        rollback.managed_receipt_sha256
        == hashlib.sha256(harness.fixture.receipt_path.read_bytes()).hexdigest()
    )
    assert rollback.old_durable_ref == f"refs/heads/runtime/b649/{NEW_HEAD}"


def test_current_success_chain_retires_each_predecessor_exactly_once(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """old success -> new success -> another new success, in the real fixture."""
    path, first_raw = _current_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    assert protected.main(argv) == 0
    second = _last_json_line(capsys)
    assert second["status"] == "SUCCESS" and harness.launches == 2
    second_raw = path.read_bytes()
    assert second_raw != first_raw
    first_archive = _archive_path(path, first_raw)
    assert first_archive.read_bytes() == first_raw

    _advance_to_successor(
        harness,
        monkeypatch,
        legacy_head=SUCCESSOR_HEAD,
        legacy_tree=SUCCESSOR_TREE,
        head=THIRD_HEAD,
        tree=THIRD_TREE,
    )
    second_owner = cutover.inspect_control_owner(harness.fixture.config)
    assert second_owner is not None and second_owner["phase"] == "RELEASED"
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    assert path.read_bytes() == second_raw
    assert protected.main(argv) == 0
    third = _last_json_line(capsys)

    second_archive = _archive_path(path, second_raw)
    assert third["status"] == "SUCCESS" and harness.launches == 3
    assert second_archive.read_bytes() == second_raw
    assert first_archive.read_bytes() == first_raw
    assert first_archive != second_archive
    assert second_archive.stat().st_nlink == first_archive.stat().st_nlink == 1
    assert {second_archive, first_archive} == set(path.parent.glob("*.superseded.json"))
    assert protected.record(third["identity"])["prior_execution_receipt_sha256"] == (
        hashlib.sha256(second_raw).hexdigest()
    )
    assert protected.record(second["identity"])["prior_execution_receipt_sha256"] == (
        hashlib.sha256(first_raw).hexdigest()
    )
    assert harness.launchd.loaded_source == harness.fixture.new
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    proof = protected.record(owner["predecessor_release_evidence"])
    assert proof["prior_reservation_id"] == second_owner["reservation_id"]
    assert proof["new_reservation_id"] == authorization["reservation_id"]
    assert protected.main(argv) == 0
    assert _last_json_line(capsys)["reused"] is True
    assert harness.launches == 3


def _reseal_managed_link(path: Path, prior: protected.Record, sha256: str) -> None:
    prior["managed_receipt"] = {**protected.record(prior["managed_receipt"]), "sha256": sha256}
    protected.ReceiptFile(path).write(prior, expected=protected.ReceiptFile(path).read())


def _tamper_successor_old_source(plan_path: Path) -> None:
    plan = protected.record(json.loads(plan_path.read_bytes()))
    prestate = protected.record(plan["prestate"])
    source = protected.record(plan["source"])
    old = {
        **protected.record(prestate["old_source"]),
        "durable_ref": f"refs/heads/runtime/b649/{'e' * 40}",
    }
    prestate["old_source"] = old
    source["old"] = old
    plan["prestate_digest"] = cutover._prestate_digest(prestate)
    plan["plan_digest"] = cutover._sha256_json(
        {
            "schema_version": cutover.PLAN_SCHEMA_VERSION,
            "target": plan["target"],
            "prestate_digest": plan["prestate_digest"],
            "new_source": source["new"],
            "new_plist_sha256": prestate["new_plist_sha256"],
        }
    )
    plan_path.write_text(protected.canonical(plan))


_RESERVE_REFUSALS = {
    "legacy": "plan/legacy identity changed",
    "old_source": "not eligible for successor reservation",
    "same_target_head": "not eligible for successor reservation",
    "managed_link": "released owner evidence does not bind",
    "managed_operation": "released owner evidence does not bind",
    "managed_plan": "released owner evidence does not bind",
    "after_role": "released owner evidence does not bind",
    "missing_owner": "no matching RELEASED owner",
}


@pytest.mark.parametrize("defect", [None, *_RESERVE_REFUSALS])
def test_reserve_classifies_current_success_before_replacing_the_released_owner(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    defect: str | None,
) -> None:
    same_head = defect == "same_target_head"
    path, raw = _current_success_cycle(
        harness,
        monkeypatch,
        head=NEW_HEAD if same_head else SUCCESSOR_HEAD,
        tree=NEW_TREE if same_head else SUCCESSOR_TREE,
        name="B649_SAME_HEAD_SUCCESSOR" if same_head else None,
    )
    prior = protected.record(json.loads(raw))
    managed_path = harness.fixture.receipt_path
    owner_path = cutover._control_owner_path(harness.fixture.config)
    if defect == "managed_link":
        _reseal_managed_link(path, prior, "f" * 64)
    elif defect in {"managed_operation", "managed_plan", "after_role"}:
        managed = protected.record(json.loads(managed_path.read_bytes()))
        if defect == "managed_operation":
            managed["operation_id"] = "f" * 32
        elif defect == "managed_plan":
            managed["plan_digest"] = "f" * 64
        else:
            after = protected.record(managed["after"])
            after["source"] = {**protected.record(after["source"]), "role": "old"}
        managed_path.write_text(protected.canonical(managed))
        _reseal_managed_link(path, prior, hashlib.sha256(managed_path.read_bytes()).hexdigest())
    elif defect == "old_source":
        _tamper_successor_old_source(_apply_plan_file(harness))
    elif defect == "missing_owner":
        owner_path.unlink()
    harness.request = protected.make_request(
        harness.fixture.config,
        harness.fixture.old,
        NEW_HEAD,
        NEW_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
    )
    if defect == "legacy":
        harness.request = replace(
            harness.request,
            legacy_worktree=harness.fixture.worktree_parent / f"B649_PRODUCTION_{OLD_HEAD}",
            legacy_head=OLD_HEAD,
            legacy_tree=OLD_TREE,
        )
    monkeypatch.setattr(protected, "build_reservation_config", _fixed_reservation_config(harness))
    owner_before = owner_path.read_bytes() if owner_path.exists() else None
    receipt_before, managed_before = path.read_bytes(), managed_path.read_bytes()
    mutations = len(harness.launchd.mutation_calls)
    capsys.readouterr()
    code = protected.main(list(harness.request.owner_argv()[2:]))
    refused = _last_json_line(capsys)
    if defect is None:
        # The untampered control proves each variant below isolates its one defect.
        assert code == claims.REFUSED and refused["status"] == "AUTHORIZATION_PENDING"
        assert cutover.inspect_control_owner(harness.fixture.config) is not None
    else:
        assert code == claims.UNVERIFIABLE
        assert _RESERVE_REFUSALS[defect] in str(refused["error"])
        # The RELEASED owner was not replaced, so no proof was lost and nothing spawned.
        assert (owner_path.read_bytes() if owner_path.exists() else None) == owner_before
    assert path.read_bytes() == receipt_before
    assert managed_path.read_bytes() == managed_before
    assert not list(path.parent.glob("*.superseded.json"))
    assert len(harness.launchd.mutation_calls) == mutations
    assert harness.launches == 1


@pytest.mark.parametrize(
    "field",
    ["reservation_id", "operation_id", "protected_receipt_sha256", "managed_receipt_sha256"],
)
def test_reserve_refuses_a_successor_when_the_released_owner_does_not_bind_the_receipts(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    stored = cutover._read_control_owner(harness.fixture.config)
    assert stored is not None
    value, identity = stored
    assert value["phase"] == "RELEASED"
    if field in {"reservation_id", "operation_id"}:
        replacement = str(uuid4()) if field == "reservation_id" else "f" * 32
        changed = {
            **value,
            field: replacement,
            "authorization": {**protected.record(value["authorization"]), field: replacement},
        }
    else:
        changed = {
            **value,
            "release_evidence": {**protected.record(value["release_evidence"]), field: "f" * 64},
        }
    cutover._save_control_owner(harness.fixture.config, changed, expected=identity)
    owner_path = cutover._control_owner_path(harness.fixture.config)
    owner_before = owner_path.read_bytes()
    monkeypatch.setattr(protected, "build_reservation_config", _fixed_reservation_config(harness))
    capsys.readouterr()
    assert protected.main(list(harness.request.owner_argv()[2:])) == claims.UNVERIFIABLE
    refused = _last_json_line(capsys)
    assert "released owner evidence does not bind" in str(refused["error"])
    # No reservation replaced the prior owner, and nothing was archived or spawned.
    assert owner_path.read_bytes() == owner_before
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1


# The plist identity binds inode/mtime/ctime, so restoring bytes cannot restore an
# authorized identity: those two stay refused and need a fresh plan, not a resume.
_UNRECOVERABLE_DRIFT = {"plist_drift", "plist_metadata_drift"}
_LAUNCH_REFUSALS = {
    "plist_drift": "completed receipt",
    "plist_metadata_drift": "plist identity differs",
    "loaded_runtime_drift": "completed receipt",
    "enabled_drift": "completed receipt",
    "active_claim": "execution identity mismatch",
    "rollback_receipt": "execution identity mismatch",
    "archive_conflict": "conflicting bytes",
}


@pytest.mark.parametrize("defect", list(_LAUNCH_REFUSALS))
def test_current_success_fresh_revalidation_refuses_then_the_same_authorization_resumes(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    prior = protected.record(json.loads(raw))
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    archive = _archive_path(path, raw)
    managed_path = harness.fixture.receipt_path
    receipt_before, managed_before = path.read_bytes(), managed_path.read_bytes()
    plist_before = harness.fixture.plist_path.read_bytes()
    loaded_before = harness.launchd.loaded_source
    store = claims.ClaimStore(harness.request.claim_root)
    claim_record = cast(claims.Metadata, prior["claim_owner"])
    rollback_path = harness.fixture.scheduler_root / protected.ROLLBACK_RECEIPT_NAME
    if defect == "plist_drift":
        harness.fixture.plist_path.write_bytes(plist_before + b"\n")
    elif defect == "plist_metadata_drift":
        # Identical bytes, new mtime/ctime: the child would refuse this after the
        # archive unless the pre-archive revalidation refuses it first.
        harness.fixture.plist_path.write_bytes(plist_before)
    elif defect == "loaded_runtime_drift":
        harness.launchd.loaded_source = harness.fixture.worktree_parent / (
            f"B649_PRODUCTION_{OLD_HEAD}"
        )
    elif defect == "enabled_drift":
        harness.launchd.enabled = False
    elif defect == "active_claim":
        store._write(claim_record)
    elif defect == "rollback_receipt":
        rollback_path.write_bytes(b"{}\n")
        rollback_path.chmod(0o600)
    else:
        archive.write_bytes(b"conflicting archive\n")
        archive.chmod(0o600)
    mutations = len(harness.launchd.mutation_calls)

    assert protected.main(argv) == claims.UNVERIFIABLE
    refused = _last_json_line(capsys)
    assert _LAUNCH_REFUSALS[defect] in str(refused["error"])
    assert harness.launches == 1
    assert len(harness.launchd.mutation_calls) == mutations
    assert path.read_bytes() == receipt_before
    assert managed_path.read_bytes() == managed_before
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    if defect == "archive_conflict":
        assert archive.read_bytes() == b"conflicting archive\n"
    else:
        assert not list(path.parent.glob("*.superseded.json"))

    if defect in _UNRECOVERABLE_DRIFT:
        return
    # Remove exactly the one defect: the same authorization is still resumable.
    if defect == "loaded_runtime_drift":
        harness.launchd.loaded_source = loaded_before
    elif defect == "enabled_drift":
        harness.launchd.enabled = True
    elif defect == "active_claim":
        store._release(claim_record)
    elif defect == "rollback_receipt":
        rollback_path.unlink()
    else:
        archive.unlink()
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert result["status"] == "SUCCESS"
    assert harness.launches == 2
    assert archive.read_bytes() == raw
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "status",
        "result_status",
        "exit_code",
        "child_exit_code",
        "action",
        "seal",
        "schema",
        "task_key",
        "receipt_path",
    ],
)
def test_current_success_prior_receipt_gate_requires_sealed_apply_success(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    defect: str | None,
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    _reserve_and_authorize(harness, monkeypatch, capsys)
    prior = protected.record(json.loads(raw))
    if defect == "status":
        prior["status"] = "FAILED"
    elif defect == "result_status":
        prior["result_status"] = "FAILED"
    elif defect in {"exit_code", "child_exit_code"}:
        prior[defect] = 1
    elif defect == "schema":
        prior["schema_version"] = "unknown"
    elif defect in {"action", "task_key", "receipt_path"}:
        field, value = {
            "action": ("action", "rollback"),
            "task_key": ("task_key", "unrelated-task"),
            "receipt_path": ("execution_receipt_path", str(path.with_name("other.json"))),
        }[defect]
        identity = {**protected.record(prior["identity"]), field: value}
        prior["identity"] = identity
        prior["execution_id"] = protected.digest(identity)
    unsigned = {key: item for key, item in prior.items() if key != "receipt_sha256"}
    prior["receipt_sha256"] = "f" * 64 if defect == "seal" else protected.digest(unsigned)
    eligible = protected.supersede_prior_execution_receipt(
        harness.request, protected.ReceiptFile(path), prior
    )
    archive = _archive_path(path, raw)
    # The untampered control proves every other gate admits this exact state.
    assert eligible is (defect is None)
    if defect is None:
        assert archive.read_bytes() == raw
        assert not path.exists()
    else:
        assert path.read_bytes() == raw
        assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1


def test_current_success_supersession_requires_the_exact_authorized_owner(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    capsys.readouterr()
    _, authorization = _drive_reserve_authorize(harness, monkeypatch, capsys)
    prior = protected.record(json.loads(raw))
    request = harness.request
    assert isinstance(request, protected.Request)

    def attempt(candidate: protected.Request) -> bool:
        return protected.supersede_prior_execution_receipt(
            candidate, protected.ReceiptFile(path), prior
        )

    # Reserved but not yet authorized.
    assert attempt(request) is False
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    # Authorized, but the presented request is a different operation.
    assert attempt(replace(request, operation_id="f" * 32)) is False
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    # The exact authorized request is the only one admitted.
    assert attempt(request) is True
    assert _archive_path(path, raw).read_bytes() == raw
    assert not path.exists()
    assert harness.launches == 1


@pytest.mark.parametrize("variant", ["missing", "other_receipt", "other_predecessor"])
def test_current_success_supersession_requires_the_saved_predecessor_proof(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    variant: str,
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    _reserve_and_authorize(harness, monkeypatch, capsys)
    prior = protected.record(json.loads(raw))
    request = harness.request
    assert isinstance(request, protected.Request)
    stored = cutover._read_control_owner(harness.fixture.config)
    assert stored is not None
    original, identity = stored
    evidence = protected.record(original["predecessor_release_evidence"])
    if variant == "missing":
        damaged = {
            key: item for key, item in original.items() if key != "predecessor_release_evidence"
        }
    elif variant == "other_receipt":
        other = {
            **protected.record(evidence["prior_release_evidence"]),
            "protected_receipt_sha256": "e" * 64,
        }
        damaged = {
            **original,
            "predecessor_release_evidence": _resealed(
                {
                    **evidence,
                    "prior_protected_receipt_sha256": "e" * 64,
                    "prior_release_evidence": other,
                }
            ),
        }
    else:
        damaged = {
            **original,
            "predecessor_release_evidence": _resealed(
                {**evidence, "prior_reservation_id": str(uuid4())}
            ),
        }
    cutover._save_control_owner(harness.fixture.config, damaged, expected=identity)

    def attempt() -> bool:
        return protected.supersede_prior_execution_receipt(
            request, protected.ReceiptFile(path), prior
        )

    # The owner is otherwise exactly the authorized one, so only the proof differs.
    assert attempt() is False
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    damaged_stored = cutover._read_control_owner(harness.fixture.config)
    assert damaged_stored is not None
    cutover._save_control_owner(harness.fixture.config, original, expected=damaged_stored[1])
    assert attempt() is True
    assert _archive_path(path, raw).read_bytes() == raw
    assert harness.launches == 1


def test_current_success_resume_after_archive_interruption_keeps_frozen_prior_sha(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    raw_sha = hashlib.sha256(raw).hexdigest()
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    archive_to = protected.ReceiptFile.archive_to

    def interrupted(self: protected.ReceiptFile, name: str, *, expected_sha256: str) -> None:
        archive_to(self, name, expected_sha256=expected_sha256)
        raise OSError("process interrupted after durable archive")

    with monkeypatch.context() as fault:
        fault.setattr(protected.ReceiptFile, "archive_to", interrupted)
        assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    archive = _archive_path(path, raw)
    assert not path.exists()
    assert archive.read_bytes() == raw
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert harness.launches == 1
    # A fresh CLI invocation rebinds the same operation from the archived prior SHA.
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert result["status"] == "SUCCESS"
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]
    assert protected.record(result["identity"])["prior_execution_receipt_sha256"] == raw_sha
    assert result["superseded_execution_receipt"] == {
        "path": str(archive),
        "sha256": raw_sha,
        "execution_id": json.loads(raw)["execution_id"],
    }
    assert harness.launches == 2
    assert archive.read_bytes() == raw


def _interrupt_after_archive_link(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[Path, bytes, Path, list[str]]:
    """Authorize, then die between the archive hard link and the source unlink."""
    path, raw = _current_success_cycle(harness, monkeypatch)
    argv, _ = _reserve_and_authorize(harness, monkeypatch, capsys)
    archive = _archive_path(path, raw)
    real_unlink = os.unlink

    def unlink(target: str, *, dir_fd: int | None = None) -> None:
        if target == path.name:
            raise OSError("process interrupted after the archive link")
        real_unlink(target, dir_fd=dir_fd)

    with monkeypatch.context() as fault:
        fault.setattr(os, "unlink", unlink)
        assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    return path, raw, archive, argv


def test_current_success_link_created_before_unlink_is_completed_by_the_next_resume(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw, archive, argv = _interrupt_after_archive_link(harness, monkeypatch, capsys)
    # Both names are one inode holding the exact prior bytes; nothing was launched.
    assert path.stat().st_ino == archive.stat().st_ino and path.stat().st_nlink == 2
    assert path.read_bytes() == raw == archive.read_bytes()
    assert protected.ReceiptFile(path).read() is not None
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert harness.launches == 1

    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert result["status"] == "SUCCESS"
    assert harness.launches == 2
    assert archive.read_bytes() == raw and archive.stat().st_nlink == 1
    assert path.read_bytes() != raw
    assert result["superseded_execution_receipt"] == {
        "path": str(archive),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "execution_id": json.loads(raw)["execution_id"],
    }


@pytest.mark.parametrize("damage", ["foreign_link", "extra_link", "diverged_archive"])
def test_current_success_ambiguous_archive_link_fails_closed_preserving_all_evidence(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    damage: str,
) -> None:
    path, raw, archive, argv = _interrupt_after_archive_link(harness, monkeypatch, capsys)
    stray = path.with_name("stray-link.json")
    if damage == "foreign_link":
        # The second name is not the identity-qualified archive.
        archive.unlink()
        os.link(path, stray)
    elif damage == "extra_link":
        os.link(path, stray)
    else:
        archive.unlink()
        archive.write_bytes(raw + b"\n")
        archive.chmod(0o600)
    before = {p: p.read_bytes() for p in (path, archive, stray) if p.exists()}
    if damage != "diverged_archive":
        # An inexact hard-link pair is unreadable, not merely unarchivable.
        with pytest.raises(protected.ProtectedError):
            protected.ReceiptFile(path).read()
    assert protected.main(argv) == claims.UNVERIFIABLE
    capsys.readouterr()
    assert harness.launches == 1
    assert {p: p.read_bytes() for p in (path, archive, stray) if p.exists()} == before
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert path.exists()


def test_current_success_competing_resume_in_the_archive_window_launches_one_child(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    archive_to = protected.ReceiptFile.archive_to
    competing: list[int] = []

    def archive_then_compete(
        self: protected.ReceiptFile, name: str, *, expected_sha256: str
    ) -> None:
        archive_to(self, name, expected_sha256=expected_sha256)
        # A second resume runs to completion while the first is between the durable
        # archive and its own decision to spawn.
        with monkeypatch.context() as inner:
            inner.setattr(protected.ReceiptFile, "archive_to", archive_to)
            competing.append(protected.main(argv))

    with monkeypatch.context() as fault:
        fault.setattr(protected.ReceiptFile, "archive_to", archive_then_compete)
        assert protected.main(argv) == 0
    assert competing == [0]
    first = _last_json_line(capsys)
    # Exactly one new managed child ran, and the woken resume reuses its result.
    assert harness.launches == 2
    assert first["reused"] is True
    assert protected.record(first["identity"])["operation_id"] == authorization["operation_id"]
    assert _archive_path(path, raw).read_bytes() == raw
    assert len(list(path.parent.glob("*.superseded.json"))) == 1
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    assert protected.main(argv) == 0
    assert harness.launches == 2


def test_current_success_release_proof_survives_a_fresh_process_resume(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    identities = dict(harness.launchd.worktree_identities)
    legacy = (NEW_HEAD, NEW_TREE)
    plan_path = _apply_plan_file(harness)
    assert path.read_bytes() == raw
    # This interpreter has no in-memory request, owner or proof: only disk and argv.
    resumed = _invoke_fresh_cli(
        harness.fixture, plan_path, argv, identities=identities, legacy=legacy
    )
    assert resumed["code"] == 0, resumed["output"]
    assert resumed["launches"] == 1
    result = protected.record(json.loads(str(resumed["output"]).splitlines()[-1]))
    archive = _archive_path(path, raw)
    assert result["status"] == "SUCCESS"
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]
    assert archive.read_bytes() == raw
    assert protected.record(resumed["owner"])["phase"] == "RELEASED"
    replay = _invoke_fresh_cli(
        harness.fixture, plan_path, argv, identities=identities, legacy=legacy
    )
    assert replay["code"] == 0 and replay["launches"] == replay["mutations"] == 0
    assert archive.read_bytes() == raw


def test_current_success_concurrent_fresh_processes_launch_at_most_one_child(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, raw = _current_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    identities = dict(harness.launchd.worktree_identities)
    legacy = (NEW_HEAD, NEW_TREE)
    results = _invoke_fresh_cli_concurrently(
        harness.fixture,
        _apply_plan_file(harness),
        argv,
        count=3,
        identities=identities,
        legacy=legacy,
    )
    # Whatever the interleaving, at most one competing process spawned a child.
    assert sum(cast(int, result["launches"]) for result in results) == 1
    archive = _archive_path(path, raw)
    assert archive.read_bytes() == raw and archive.stat().st_nlink == 1
    assert list(path.parent.glob("*.superseded.json")) == [archive]
    receipt = protected.record(json.loads(path.read_bytes()))
    assert receipt["status"] == "SUCCESS"
    assert protected.record(receipt["identity"])["operation_id"] == authorization["operation_id"]
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"
    replay = _invoke_fresh_cli(
        harness.fixture, _apply_plan_file(harness), argv, identities=identities, legacy=legacy
    )
    assert replay["code"] == 0 and replay["launches"] == 0


_OWNER_LEGACY_KEYS = {
    "schema",
    "reservation_id",
    "owner_kind",
    "owner_pid",
    "action",
    "target",
    "control_head",
    "control_tree",
    "operation_id",
    "managed_receipt_sha256",
    "phase",
    "created_at",
    "updated_at",
    "authorization",
    "mutation_started",
    "terminal",
    "release_evidence",
    "record_sha256",
}


def test_owner_records_without_predecessor_proof_keep_the_legacy_key_set(
    harness: Harness,
) -> None:
    assert harness.launch()["status"] == "SUCCESS"
    stored = json.loads(cutover._control_owner_path(harness.fixture.config).read_bytes())
    assert stored["phase"] == "RELEASED"
    assert set(stored) == _OWNER_LEGACY_KEYS
    # A record in the exact pre-change shape is still readable and retains its seal.
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["record_sha256"] == stored["record_sha256"]


def _successor_reservation(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[protected.Record, cutover.FileIdentity]:
    _current_success_cycle(harness, monkeypatch)
    capsys.readouterr()
    _drive_reserve_authorize(harness, monkeypatch, capsys)
    stored = cutover._read_control_owner(harness.fixture.config)
    assert stored is not None
    assert "predecessor_release_evidence" in stored[0]
    return stored


def _resealed(evidence: protected.Record) -> protected.Record:
    unsigned = {key: item for key, item in evidence.items() if key != "evidence_sha256"}
    return {**unsigned, "evidence_sha256": cutover._sha256_json(unsigned)}


@pytest.mark.parametrize(
    "tamper",
    [
        "stale_seal",
        "schema",
        "extra_key",
        "new_reservation",
        "new_operation",
        "managed_receipt",
        "prior_unverified",
        "hash_shape",
    ],
)
def test_successor_owner_with_tampered_predecessor_proof_is_refused_on_read(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tamper: str,
) -> None:
    value, identity = _successor_reservation(harness, monkeypatch, capsys)
    evidence = dict(protected.record(value["predecessor_release_evidence"]))
    if tamper == "stale_seal":
        evidence["prior_operation_id"] = "changed"
    elif tamper == "schema":
        evidence = _resealed({**evidence, "schema": "b649-unknown-v1"})
    elif tamper == "extra_key":
        evidence = _resealed({**evidence, "unexpected": True})
    elif tamper == "new_reservation":
        evidence = _resealed({**evidence, "new_reservation_id": str(uuid4())})
    elif tamper == "new_operation":
        evidence = _resealed({**evidence, "new_operation_id": "f" * 32})
    elif tamper == "managed_receipt":
        evidence = _resealed({**evidence, "prior_managed_receipt_sha256": "f" * 64})
    elif tamper == "prior_unverified":
        prior_release = {**protected.record(evidence["prior_release_evidence"]), "verified": False}
        evidence = _resealed({**evidence, "prior_release_evidence": prior_release})
    else:
        evidence = _resealed({**evidence, "prior_authorization_sha256": "not-a-digest"})
    cutover._save_control_owner(
        harness.fixture.config,
        {**value, "predecessor_release_evidence": evidence},
        expected=identity,
    )
    with pytest.raises(cutover.CutoverSafetyError, match="predecessor release"):
        cutover.inspect_control_owner(harness.fixture.config)


@pytest.mark.parametrize("carrier", ["managed_owner", "rollback_owner"])
def test_only_a_protected_apply_owner_may_carry_predecessor_proof(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    carrier: str,
) -> None:
    value, identity = _successor_reservation(harness, monkeypatch, capsys)
    changed = (
        {**value, "owner_kind": "managed"}
        if carrier == "managed_owner"
        else {**value, "action": "rollback"}
    )
    cutover._save_control_owner(harness.fixture.config, changed, expected=identity)
    with pytest.raises(cutover.CutoverSafetyError):
        cutover.inspect_control_owner(harness.fixture.config)


@pytest.mark.parametrize(
    "defect",
    [None, "different_predecessor", "managed_owner", "different_reservation"],
)
def test_successor_reservation_accepts_proof_only_for_its_own_released_predecessor(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    defect: str | None,
) -> None:
    _current_success_cycle(harness, monkeypatch)
    config = harness.fixture.config
    released = cutover.inspect_control_owner(config)
    assert released is not None and released["phase"] == "RELEASED"
    reservation_id = str(uuid4())
    request = protected.make_request(
        config,
        harness.fixture.old,
        NEW_HEAD,
        NEW_TREE,
        _apply_plan_file(harness),
        harness.request.claim_root,
        reservation_id=reservation_id,
        owner_id_argument=False,
    )
    evidence = protected._require_released_success_evidence(request, released)
    assert evidence is not None
    owner_kind = "protected"
    if defect == "different_predecessor":
        evidence = _resealed({**evidence, "prior_reservation_id": str(uuid4())})
    elif defect == "managed_owner":
        owner_kind = "managed"
    elif defect == "different_reservation":
        reservation_id = str(uuid4())
    owner_path = cutover._control_owner_path(config)
    before = owner_path.read_bytes()

    def reserve() -> protected.Record:
        return cutover.acquire_control_owner(
            config,
            action="apply",
            target=protected.request_owner_target(request),
            owner_kind=owner_kind,
            reservation_id=reservation_id,
            version={
                "head": request.identity["control_head"],
                "tree": request.identity["control_tree"],
            },
            operation_id=request.operation_id,
            managed_receipt_sha256=request.managed_receipt_sha256,
            predecessor_release_evidence=evidence,
        )

    if defect is None:
        reserved = reserve()
        assert reserved["predecessor_release_evidence"] == evidence
        assert reserved["phase"] == "AUTHORIZATION_PENDING"
        return
    with pytest.raises(cutover.CutoverSafetyError, match="predecessor"):
        reserve()
    # The RELEASED predecessor is untouched, so its proof can still be frozen later.
    assert owner_path.read_bytes() == before


# A reboot renumbers st_dev and nothing else. The receipt a prior SUCCESS sealed
# keeps the old device, so the successor compares it without device; the plan it
# froze in this boot must still equal the live plist on the full key.


def _sealed_plist_identity(harness: Harness) -> cutover.FileIdentity:
    managed = protected.record(json.loads(harness.fixture.receipt_path.read_bytes()))
    plist = protected.record(protected.record(managed["after"])["plist"])
    return cutover.FileIdentity.from_value(plist["identity"])


def _planned_old_plist_identity(harness: Harness) -> cutover.FileIdentity:
    plan = protected.record(json.loads(_apply_plan_file(harness).read_bytes()))
    prestate = protected.record(plan["prestate"])
    return cutover.FileIdentity.from_value(prestate["old_plist_identity"])


def _live_plist_identity(harness: Harness) -> cutover.FileIdentity:
    identity, _ = cutover._file_identity(harness.fixture.plist_path, missing_ok=False)
    assert identity is not None
    return identity


def _rebooted_success_cycle(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    before_plan: Callable[[], None] | None = None,
) -> tuple[Path, bytes]:
    """OLD -> NEW succeeds, the machine reboots, then the successor plan is frozen."""
    assert harness.launch()["status"] == "SUCCESS"
    path = harness.request.receipt_path
    raw = path.read_bytes()
    simulate_reboot(monkeypatch, harness.fixture.root, 1)
    if before_plan is not None:
        before_plan()
    _advance_to_successor(
        harness,
        monkeypatch,
        legacy_head=NEW_HEAD,
        legacy_tree=NEW_TREE,
        head=SUCCESSOR_HEAD,
        tree=SUCCESSOR_TREE,
    )
    return path, raw


def _assert_nothing_retired(harness: Harness, path: Path, raw: bytes, mutations: int) -> None:
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))
    assert harness.launches == 1
    assert len(harness.launchd.mutation_calls) == mutations
    store = claims.ClaimStore(harness.request.claim_root)
    assert store.inspect(protected.TASK_KEY)["status"] == "ABSENT"


def _assert_retired_once(path: Path, raw: bytes, result: protected.Record) -> None:
    archive = _archive_path(path, raw)
    assert result["status"] == "SUCCESS"
    assert archive.read_bytes() == raw and archive.stat().st_nlink == 1
    assert list(path.parent.glob("*.superseded.json")) == [archive]
    assert protected.record(result["identity"])["prior_execution_receipt_sha256"] == (
        hashlib.sha256(raw).hexdigest()
    )


@pytest.mark.parametrize("resume", ["same_process", "fresh_process"])
def test_current_success_is_superseded_after_a_reboot_renumbers_the_plist_device(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    resume: str,
) -> None:
    """The v6 Stage A incident: reserve refused only because st_dev moved on reboot."""
    path, raw = _rebooted_success_cycle(harness, monkeypatch)
    sealed = _sealed_plist_identity(harness)
    planned = _planned_old_plist_identity(harness)
    assert planned.key() == _live_plist_identity(harness).key()
    assert planned.device != sealed.device
    assert {**planned.to_dict(), "device": sealed.device} == sealed.to_dict()
    monkeypatch.setattr(protected, "build_reservation_config", _fixed_reservation_config(harness))
    argv = list(harness.request.owner_argv()[2:])
    capsys.readouterr()
    code = protected.main(argv)
    reserved = _last_json_line(capsys)
    assert (code, reserved["status"]) == (claims.REFUSED, "AUTHORIZATION_PENDING"), reserved
    authorization = _authorization_envelope(reserved)
    harness.request = replace(
        harness.request,
        reservation_id=str(reserved["reservation_id"]),
        operation_id=str(authorization["operation_id"]),
    )
    harness.chain()
    assert protected.main(_authorize_argv(authorization)) == 0
    capsys.readouterr()
    assert path.read_bytes() == raw
    assert not list(path.parent.glob("*.superseded.json"))

    if resume == "same_process":
        assert protected.main(argv) == 0
        result = _last_json_line(capsys)
        launched = harness.launches - 1
    else:
        resumed = _invoke_fresh_cli(
            harness.fixture,
            _apply_plan_file(harness),
            argv,
            identities=dict(harness.launchd.worktree_identities),
            legacy=(NEW_HEAD, NEW_TREE),
            boot=1,
        )
        assert resumed["code"] == 0, resumed["output"]
        result = protected.record(json.loads(str(resumed["output"]).splitlines()[-1]))
        launched = cast(int, resumed["launches"])
    assert launched == 1
    _assert_retired_once(path, raw, result)
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "RELEASED"


_PLIST_METADATA_ATTACKS = (
    "replaced_file",
    "in_place_rewrite",
    "rewrite_restore_mtime",
    "chmod_round_trip",
    "hard_link_round_trip",
)


def _attack_plist(path: Path, attack: str) -> None:
    """Same bytes, same mode, one link: only inode or ctime can still tell."""
    raw = path.read_bytes()
    before = os.lstat(path)
    if attack == "replaced_file":
        replacement = path.with_name(f".{path.name}.replacement")
        replacement.write_bytes(raw)
        replacement.chmod(0o600)
        os.replace(replacement, path)
    elif attack == "in_place_rewrite":
        path.write_bytes(raw)
    elif attack == "rewrite_restore_mtime":
        path.write_bytes(raw)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif attack == "chmod_round_trip":
        path.chmod(0o644)
        path.chmod(0o600)
    else:
        link = path.with_name(f".{path.name}.link")
        os.link(path, link)
        link.unlink()
    after = os.lstat(path)
    assert path.read_bytes() == raw
    assert (stat.S_IMODE(after.st_mode), after.st_nlink) == (0o600, 1)
    assert after.st_ctime_ns != before.st_ctime_ns
    assert (after.st_ino != before.st_ino) is (attack == "replaced_file")
    if attack in {"rewrite_restore_mtime", "chmod_round_trip", "hard_link_round_trip"}:
        assert after.st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize("stage", ["before_plan", "after_authorization"])
@pytest.mark.parametrize("attack", _PLIST_METADATA_ATTACKS)
def test_rebooted_current_success_still_refuses_a_rewritten_identical_plist(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    attack: str,
    stage: str,
) -> None:
    plist = harness.fixture.plist_path

    def before_plan() -> None:
        if stage == "before_plan":
            _attack_plist(plist, attack)

    path, raw = _rebooted_success_cycle(harness, monkeypatch, before_plan=before_plan)
    owner_path = cutover._control_owner_path(harness.fixture.config)
    monkeypatch.setattr(protected, "build_reservation_config", _fixed_reservation_config(harness))
    if stage == "before_plan":
        # The fresh plan froze the attacked file, so only the sealed receipt can tell.
        assert _planned_old_plist_identity(harness).key() == _live_plist_identity(harness).key()
        owner_before = owner_path.read_bytes()
        mutations = len(harness.launchd.mutation_calls)
        capsys.readouterr()
        code = protected.main(list(harness.request.owner_argv()[2:]))
        refused = _last_json_line(capsys)
        assert code == claims.UNVERIFIABLE
        assert "not eligible for successor reservation" in str(refused["error"])
        assert owner_path.read_bytes() == owner_before
    else:
        argv, _ = _reserve_and_authorize(harness, monkeypatch, capsys)
        _attack_plist(plist, attack)
        mutations = len(harness.launchd.mutation_calls)
        assert protected.main(argv) == claims.UNVERIFIABLE
        refused = _last_json_line(capsys)
        assert "completed receipt plist identity differs" in str(refused["error"])
        owner = cutover.inspect_control_owner(harness.fixture.config)
        assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
        assert owner["mutation_started"] is False
    assert _live_plist_identity(harness).sha256 == _sealed_plist_identity(harness).sha256
    _assert_nothing_retired(harness, path, raw, mutations)


@pytest.mark.parametrize("sealed_before_reboot", [False, True])
def test_reboot_between_authorization_and_resume_refuses_before_the_archive(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sealed_before_reboot: bool,
) -> None:
    """The plan froze OLD in one boot; its child CAS binds that exact device."""
    if sealed_before_reboot:
        path, raw = _rebooted_success_cycle(harness, monkeypatch)
    else:
        path, raw = _current_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    planned = _planned_old_plist_identity(harness)
    simulate_reboot(monkeypatch, harness.fixture.root, 2)
    live = _live_plist_identity(harness)
    assert live.key() != planned.key()
    assert {**live.to_dict(), "device": planned.device} == planned.to_dict()
    mutations = len(harness.launchd.mutation_calls)

    assert protected.main(argv) == claims.UNVERIFIABLE
    refused = _last_json_line(capsys)
    assert "successor plan OLD plist identity differs" in str(refused["error"])
    _assert_nothing_retired(harness, path, raw, mutations)
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False
    assert owner["reservation_id"] == authorization["reservation_id"]

    # The device was the only defect: in the plan's own boot the same authorization resumes.
    simulate_reboot(monkeypatch, harness.fixture.root, 1 if sealed_before_reboot else 0)
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert harness.launches == 2
    _assert_retired_once(path, raw, result)
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]


@pytest.mark.parametrize("drift", ["loaded_runtime_drift", "enabled_drift"])
def test_rebooted_current_success_still_refuses_runtime_drift(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    drift: str,
) -> None:
    path, raw = _rebooted_success_cycle(harness, monkeypatch)
    argv, authorization = _reserve_and_authorize(harness, monkeypatch, capsys)
    loaded_before = harness.launchd.loaded_source
    if drift == "loaded_runtime_drift":
        harness.launchd.loaded_source = harness.fixture.worktree_parent / (
            f"B649_PRODUCTION_{OLD_HEAD}"
        )
    else:
        harness.launchd.enabled = False
    mutations = len(harness.launchd.mutation_calls)

    assert protected.main(argv) == claims.UNVERIFIABLE
    refused = _last_json_line(capsys)
    assert "completed receipt" in str(refused["error"])
    _assert_nothing_retired(harness, path, raw, mutations)
    owner = cutover.inspect_control_owner(harness.fixture.config)
    assert owner is not None and owner["phase"] == "AUTHORIZED_PENDING"
    assert owner["mutation_started"] is False

    if drift == "loaded_runtime_drift":
        harness.launchd.loaded_source = loaded_before
    else:
        harness.launchd.enabled = True
    assert protected.main(argv) == 0
    result = _last_json_line(capsys)
    assert harness.launches == 2
    _assert_retired_once(path, raw, result)
    assert protected.record(result["identity"])["operation_id"] == authorization["operation_id"]
