"""Hermetic tests for the B649 production cutover entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
import tools.b649_goalc_local_scheduler as scheduler
import tools.b649_production_cutover as cutover

NEW_HEAD = "1" * 40
NEW_TREE = "2" * 40
OLD_HEAD = "3" * 40
OLD_TREE = "4" * 40
UID = os.getuid()
DOMAIN = f"gui/{UID}"


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _objects(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    items = cast(list[object], value)
    assert all(isinstance(item, dict) for item in items)
    return cast(list[dict[str, object]], items)


def _completed(
    argv: Sequence[str],
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(tuple(argv), returncode, stdout, stderr)


@dataclass
class Fixture:
    root: Path
    canonical: Path = field(init=False)
    worktree_parent: Path = field(init=False)
    new: Path = field(init=False)
    old: Path = field(init=False)
    operation_root: Path = field(init=False)
    scheduler_root: Path = field(init=False)
    data_root: Path = field(init=False)
    plist_path: Path = field(init=False)
    primary_lock_path: Path = field(init=False)
    shadow_lock_path: Path = field(init=False)
    cutover_lock_path: Path = field(init=False)
    receipt_path: Path = field(init=False)
    config: cutover.CutoverConfig = field(init=False)
    old_plist_bytes: bytes = field(init=False)

    def __post_init__(self) -> None:
        self.canonical = self.root / "MathStatisticalAnalysis"
        self.canonical.mkdir()
        self.worktree_parent = self.root / ".worktrees" / self.canonical.name
        self.new = self.worktree_parent / f"B649_PRODUCTION_{NEW_HEAD}"
        self.old = self.worktree_parent / f"B649_PRODUCTION_{OLD_HEAD}"
        self._make_source(self.new)
        self._make_source(self.old)

        self.operation_root = self.root / "operation"
        self.scheduler_root = self.operation_root / "scheduler"
        self.data_root = self.root / "data"
        launch_agents = self.root / "Library" / "LaunchAgents"
        launch_agents.mkdir(mode=0o700, parents=True)
        self.plist_path = launch_agents / f"{cutover.LABEL}.plist"
        self.primary_lock_path = self.scheduler_root / "primary.lock"
        self.shadow_lock_path = self.root / "runtime" / "shadow.lock"
        self.cutover_lock_path = self.scheduler_root / "cutover.lock"
        self.receipt_path = self.scheduler_root / "receipt.json"

        self.config = cutover.CutoverConfig(
            source_worktree=self.new,
            launch_domain=DOMAIN,
            plist_path=self.plist_path,
            canonical_repository=self.canonical,
            operation_root=self.operation_root,
            scheduler_root=self.scheduler_root,
            data_root=self.data_root,
            database=self.data_root / "lottolab.db",
            announcement=self.data_root / "pre-outcome-target-announcements-v1.json",
            health_path=self.scheduler_root / "health.json",
            stdout_path=self.scheduler_root / "launchd.stdout.log",
            stderr_path=self.scheduler_root / "launchd.stderr.log",
            primary_lock_path=self.primary_lock_path,
            shadow_lock_path=self.shadow_lock_path,
            cutover_lock_path=self.cutover_lock_path,
            receipt_path=self.receipt_path,
            expected_head=NEW_HEAD,
            expected_tree=NEW_TREE,
            durable_ref=f"refs/heads/runtime/b649/{NEW_HEAD}",
            strict_release_layout=False,
        )
        old_scheduler_config = scheduler.SchedulerConfig(
            label=cutover.LABEL,
            version=scheduler.TASK_VERSION,
            canonical_repository=self.canonical,
            source_worktree=self.old,
            python_executable=self.old / ".venv/bin/python",
            script_path=self.old / "tools/b649_goalc_local_scheduler.py",
            operation_root=self.operation_root,
            data_root=self.data_root,
            database=self.data_root / "lottolab.db",
            announcement=self.data_root / "pre-outcome-target-announcements-v1.json",
            scheduler_root=self.scheduler_root,
            lock_path=self.primary_lock_path,
            health_path=self.scheduler_root / "health.json",
            stdout_path=self.scheduler_root / "launchd.stdout.log",
            stderr_path=self.scheduler_root / "launchd.stderr.log",
            plist_path=self.plist_path,
        )
        self.old_plist_bytes = scheduler.build_launchd_plist(old_scheduler_config)
        self.plist_path.write_bytes(self.old_plist_bytes)
        self.plist_path.chmod(0o600)

    @staticmethod
    def _make_source(path: Path) -> None:
        (path / ".venv" / "bin").mkdir(mode=0o700, parents=True)
        interpreter = path / ".venv" / "bin" / "python"
        interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
        interpreter.chmod(0o700)
        (path / "tools").mkdir(mode=0o700)
        (path / "tools" / "b649_goalc_local_scheduler.py").write_text(
            "# fixture scheduler\n",
            encoding="utf-8",
        )
        (path / "src").mkdir(mode=0o700)


@dataclass
class FakeLaunchd:
    fixture: Fixture
    loaded: bool = True
    loaded_source: Path | None = None
    enabled: bool = True
    calls: list[tuple[str, ...]] = field(default_factory=lambda: list[tuple[str, ...]]())
    status_by_path: dict[Path, str] = field(default_factory=lambda: dict[Path, str]())
    process_rows: list[str] = field(
        default_factory=lambda: [f"424242 1 {UID} /usr/bin/fixture-shell"]
    )
    file_rows: list[str] = field(default_factory=lambda: ["p424242", "fcwd", "n/tmp"])
    fail_bootstrap_new_once: bool = False
    after_mutation: Callable[[tuple[str, ...]], None] | None = None

    def __post_init__(self) -> None:
        if self.loaded_source is None:
            self.loaded_source = self.fixture.old

    @property
    def mutation_calls(self) -> list[tuple[str, ...]]:
        verbs = {"disable", "bootout", "bootstrap", "enable", "kickstart", "kill"}
        return [
            call
            for call in self.calls
            if len(call) > 1 and call[0] == "launchctl" and call[1] in verbs
        ]

    def _launch_text(self) -> str:
        assert self.loaded_source is not None
        source = self.loaded_source
        interpreter = source / ".venv/bin/python"
        script = source / "tools/b649_goalc_local_scheduler.py"
        return f"""{DOMAIN}/{cutover.LABEL} = {{
    path = {self.fixture.plist_path}
    type = LaunchAgent
    state = not running
    program = {interpreter}
    arguments = {{
        {interpreter}
        {script}
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

    def _after(self, args: tuple[str, ...]) -> None:
        if self.after_mutation is not None:
            self.after_mutation(args)

    def __call__(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        args = tuple(argv)
        self.calls.append(args)
        if args[:2] == ("git", "--no-optional-locks"):
            worktree = Path(args[3])
            assert worktree in {self.fixture.new, self.fixture.old}
            if args[4] == "status":
                return _completed(args, self.status_by_path.get(worktree, ""))
            assert args[4] == "rev-parse"
            if args[5:] == ("--show-toplevel",):
                return _completed(args, str(worktree) + "\n")
            assert args[5:7] == ("--verify", "--end-of-options")
            revision = args[7]
            if worktree == self.fixture.new:
                values = {
                    "HEAD": NEW_HEAD,
                    "HEAD^{tree}": NEW_TREE,
                    f"refs/heads/runtime/b649/{NEW_HEAD}^{{commit}}": NEW_HEAD,
                }
            else:
                values = {
                    "HEAD": OLD_HEAD,
                    "HEAD^{tree}": OLD_TREE,
                    f"refs/heads/runtime/b649/{OLD_HEAD}^{{commit}}": OLD_HEAD,
                }
            assert revision in values
            return _completed(args, values[revision] + "\n")
        if args[:2] == ("git", "check-ref-format"):
            return _completed(args)
        if args == ("launchctl", "print", f"{DOMAIN}/{cutover.LABEL}"):
            if not self.loaded:
                return _completed(
                    args,
                    stderr=(
                        "Bad request.\n"
                        f'Could not find service "{cutover.LABEL}" in domain for user '
                        f"gui: {UID}\n"
                    ),
                    returncode=113,
                )
            return _completed(args, self._launch_text())
        if args == ("launchctl", "print-disabled", DOMAIN):
            return _completed(
                args,
                "disabled services = {\n"
                f'    "{cutover.LABEL}" => {str(not self.enabled).lower()}\n'
                "}\n",
            )
        if args == ("ps", "-ww", "-axo", "pid=,ppid=,uid=,command="):
            return _completed(args, "\n".join(self.process_rows) + "\n")
        if args == ("lsof", "-nP", "-a", "-u", str(UID), "-F", "pfn"):
            return _completed(args, "\n".join(self.file_rows) + "\n")
        if args == ("launchctl", "disable", f"{DOMAIN}/{cutover.LABEL}"):
            self.enabled = False
            self._after(args)
            return _completed(args)
        if args == ("launchctl", "enable", f"{DOMAIN}/{cutover.LABEL}"):
            self.enabled = True
            self._after(args)
            return _completed(args)
        if args == ("launchctl", "bootout", f"{DOMAIN}/{cutover.LABEL}"):
            self.loaded = False
            self._after(args)
            return _completed(args)
        if args == ("launchctl", "bootstrap", DOMAIN, str(self.fixture.plist_path)):
            binding = plistlib.loads(self.fixture.plist_path.read_bytes())
            source = Path(binding["WorkingDirectory"])
            if source == self.fixture.new and self.fail_bootstrap_new_once:
                self.fail_bootstrap_new_once = False
                return _completed(args, stderr="fake bootstrap failure", returncode=1)
            self.loaded = True
            self.loaded_source = source
            self._after(args)
            return _completed(args)
        raise AssertionError(f"unexpected command (possible forbidden mutation): {args}")


@pytest.fixture
def fixture(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path)


def test_plan_is_read_only_and_reports_exact_runtime(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    before_paths = {
        fixture.scheduler_root,
        fixture.cutover_lock_path,
        fixture.receipt_path,
        fixture.primary_lock_path,
        fixture.shadow_lock_path,
    }

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "PASS"
    assert result["target"] == {
        "label": cutover.LABEL,
        "launch_domain": DOMAIN,
        "launch_target": f"{DOMAIN}/{cutover.LABEL}",
        "plist_path": str(fixture.plist_path),
    }
    runtime = _object(result["runtime"])
    assert runtime["new"] == {
        "working_directory": str(fixture.new),
        "interpreter": str(fixture.new / ".venv/bin/python"),
        "script": str(fixture.new / "tools/b649_goalc_local_scheduler.py"),
        "pythonpath": str(fixture.new / "src"),
        "arguments": [
            str(fixture.new / ".venv/bin/python"),
            str(fixture.new / "tools/b649_goalc_local_scheduler.py"),
            "run",
        ],
    }
    assert runner.mutation_calls == []
    assert all(not path.exists() for path in before_paths)


@pytest.mark.parametrize("drift", ["source", "plist"])
def test_plan_fails_closed_on_source_or_plist_drift(fixture: Fixture, drift: str) -> None:
    runner = FakeLaunchd(fixture)
    if drift == "source":
        runner.status_by_path[fixture.new] = " M drifted.py\n"
    else:
        binding = plistlib.loads(fixture.old_plist_bytes)
        binding["ProgramArguments"][0] = str(fixture.new / ".venv/bin/python")
        fixture.plist_path.write_bytes(plistlib.dumps(binding))
        fixture.plist_path.chmod(0o600)

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    assert result["failures"]
    assert runner.mutation_calls == []
    assert not fixture.cutover_lock_path.exists()
    assert not fixture.receipt_path.exists()


def test_plan_reports_malformed_loaded_service_as_structured_failure(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)

    def malformed_launch(
        _args: argparse.Namespace, _runner: cutover.checkpoint.Runner
    ) -> dict[str, object]:
        return {
            "state": "LOADED",
            "target": f"{DOMAIN}/{cutover.LABEL}",
            "raw": f"{DOMAIN}/{cutover.LABEL} = {{\n    malformed\n}}\n",
        }

    monkeypatch.setattr(
        cutover.checkpoint,
        "launch_snapshot",
        malformed_launch,
    )

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("old_state" in str(failure) for failure in failures)
    assert _object(result["launchd"])["loaded_binding"] is None
    assert runner.mutation_calls == []


def test_apply_duplicate_and_receipt_bound_rollback_are_hermetic(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    applied = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert applied["status"] == "SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == fixture.new
    assert runner.enabled is True
    after = _object(applied["after"])
    plist = _object(after["plist"])
    assert plist["sha256"] == hashlib.sha256(fixture.plist_path.read_bytes()).hexdigest()
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "SUCCESS"
    assert stat.S_IMODE(fixture.receipt_path.stat().st_mode) == 0o600
    mutation_count = len(runner.mutation_calls)

    duplicate = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert duplicate["status"] == "ALREADY_APPLIED"
    assert len(runner.mutation_calls) == mutation_count
    assert all(
        call[1] in {"disable", "bootout", "bootstrap", "enable"} for call in runner.mutation_calls
    )
    assert runner.mutation_calls == [
        ("launchctl", "disable", f"{DOMAIN}/{cutover.LABEL}"),
        ("launchctl", "bootout", f"{DOMAIN}/{cutover.LABEL}"),
        ("launchctl", "bootstrap", DOMAIN, str(fixture.plist_path)),
        ("launchctl", "enable", f"{DOMAIN}/{cutover.LABEL}"),
    ]

    rolled_back = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == fixture.old
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert rolled_back["business_state"] == "UNCHANGED"
    rollback_after = _object(rolled_back["after"])
    assert (
        _object(rollback_after["plist"])["sha256"]
        == hashlib.sha256(fixture.old_plist_bytes).hexdigest()
    )
    rolled_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert rolled_receipt["status"] == "ROLLBACK_SUCCESS"

    duplicate_rollback = cutover.rollback(fixture.config, runner=runner)
    assert duplicate_rollback["status"] == "ALREADY_ROLLED_BACK"


def test_concurrent_apply_is_rejected_by_the_serialization_lock(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    with cutover.CutoverLock(fixture.config.cutover_lock_path):
        result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "NOT_STARTED"
    failures = cast(list[object], result["failures"])
    assert any("CONCURRENT_APPLY" in str(failure) for failure in failures)
    assert runner.mutation_calls == []
    assert not fixture.receipt_path.exists()


def test_apply_and_rollback_preserve_unloaded_disabled_prestate(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture, loaded=False, enabled=False)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    assert _object(plan["launchd"])["old_state"] == "UNLOADED"
    assert _object(plan["launchd"])["old_enabled"] is False

    applied = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert applied["status"] == "SUCCESS"
    assert runner.loaded is False
    assert runner.enabled is False
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    rolled_back = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is False
    assert runner.enabled is False
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes


def test_plan_rejects_active_shadow_before_any_mutation(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    runner.process_rows = [f"424242 1 {UID} {fixture.old}/tools/b649_pair_rule_forward_shadow.py"]

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("old_state" in str(failure) for failure in failures)
    ownership = _object(result["ownership"])
    assert _object(ownership["shadow"])["classification"] == "PRESENT"
    assert _object(ownership["primary_lock"])["state"] == "IDLE"
    assert runner.mutation_calls == []


def test_apply_race_after_disable_becomes_recovery_required_without_kill(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    def make_scheduler_active(args: tuple[str, ...]) -> None:
        if args[1] == "disable":
            runner.process_rows = [
                f"424242 1 {UID} {fixture.old}/tools/b649_goalc_local_scheduler.py"
            ]

    runner.after_mutation = make_scheduler_active
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    mutation_summary = _object(result["mutation_summary"])
    assert mutation_summary["launchd"] is True
    assert mutation_summary["plist"] is False
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert not any(
        call[1] in {"bootout", "bootstrap", "enable", "kill"}
        for call in runner.calls
        if call[0] == "launchctl"
    )
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "RECOVERY_REQUIRED"
    assert receipt["mutation_summary"]["launchd"] is True


def test_apply_bootstrap_failure_has_explicit_recovery(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture, fail_bootstrap_new_once=True)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERED"
    assert runner.loaded is True
    assert runner.loaded_source == fixture.old
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    names = [action["name"] for action in _objects(result["actions"])]
    assert "bootstrap-new" in names
    assert "restore-plist" in names
    assert result["mutation_summary"] == {
        "launchd": True,
        "plist": True,
        "control_files": True,
    }


def test_rollback_blocks_when_new_release_cycle_is_active(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    runner.process_rows = [f"424242 1 {UID} {fixture.new}/tools/b649_goalc_local_scheduler.py"]
    before_mutations = len(runner.mutation_calls)

    result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert result["status"] == "ROLLBACK_BLOCKED_ACTIVE_CYCLE"
    assert result["kill_attempted"] is False
    assert len(runner.mutation_calls) == before_mutations
    assert fixture.plist_path.read_bytes() != fixture.old_plist_bytes


def test_rollback_old_release_drift_fails_before_launchd_mutation(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    runner.status_by_path[fixture.old] = " M old-release.py\n"
    before_mutations = len(runner.mutation_calls)

    with pytest.raises(cutover.CutoverSafetyError):
        cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert len(runner.mutation_calls) == before_mutations
    assert fixture.plist_path.read_bytes() != fixture.old_plist_bytes
