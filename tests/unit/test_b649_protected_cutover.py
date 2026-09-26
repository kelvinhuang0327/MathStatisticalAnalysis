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
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from tests.unit.test_b649_production_cutover import (
    OLD_HEAD,
    OLD_TREE,
    UID,
    FakeLaunchd,
    Fixture,
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
    observed_started: protected.Record | None = None
    existing_plan: Path | None = None

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
                OLD_HEAD,
                OLD_TREE,
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
        self, argv: Sequence[str], *, pass_fds: tuple[int, ...], start_new_session: bool
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
        return FakeChild(self, os.dup(pass_fds[0]))

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
        return protected.launch(self.request)

    def external(self, command: str, *, cwd: str | None = "/isolated") -> None:
        self.launchd.process_rows.append(f"900099 1 {UID} S {command}")
        if cwd is not None:
            self.launchd.file_rows.extend(["p900099", "fcwd", "n" + cwd])


class FakeChild:
    def __init__(self, harness: Harness, gate: int):
        self.harness = harness
        self.gate = gate
        self.pid = harness.child

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
            return 127
        with pytest.MonkeyPatch.context() as child_context:
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


def test_exec_failure_before_child_code_leaves_durable_ambiguous_result(harness: Harness) -> None:
    harness.exec_failed = True
    result = harness.launch()
    assert result["status"] == "INCOMPLETE_OR_AMBIGUOUS" and result["exit_code"] == 127
    assert result["gated_child_pid"] == harness.child
    saved = protected.ReceiptFile(harness.request.receipt_path).read()
    assert saved is not None and saved["completed_at"]
    with pytest.raises(protected.ProtectedError, match="blocks automatic rerun"):
        harness.launch()
    assert harness.launches == 1 and harness.stops == []


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
) -> None:
    """Spawned interpreter: only disk state, CLI argv and hermetic OS seams survive."""
    output, errors = io.StringIO(), io.StringIO()
    try:
        with (
            pytest.MonkeyPatch.context() as patches,
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            harness = Harness(fixture, patches, existing_plan=plan_path)
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


def _invoke_fresh_cli(fixture: Fixture, plan_path: Path, argv: list[str]) -> protected.Record:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_fresh_cli_session, args=(fixture, plan_path, argv, sender))
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
