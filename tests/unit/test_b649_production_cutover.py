"""Hermetic tests for the B649 production cutover entrypoint."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import plistlib
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

import pytest
import tools.b649_cutover_checkpoint as checkpoint
import tools.b649_goalc_local_scheduler as scheduler
import tools.b649_production_cutover as cutover

NEW_HEAD = "1" * 40
NEW_TREE = "2" * 40
OLD_HEAD = "3" * 40
OLD_TREE = "4" * 40
LEGACY_HEAD = "5" * 40
LEGACY_TREE = "6" * 40
UID = os.getuid()
DOMAIN = f"gui/{UID}"
# A receipt-bound OLD/PRESTATE worktree name that predates the
# B649_PRODUCTION_<HEAD> release-materialization convention -- the real
# production shape this fixture's default new/old pair (both named
# B649_PRODUCTION_<HEAD>) never exercises. See b649-cutover-plan-old-runtime-
# durable-ref-missing / b649-cutover-plan-old-interpreter-outside-worktree.
LEGACY_WORKTREE_NAME = "B649_V5_ACTIVATION_PREREQUISITE_SUCCESSOR_CONSTRUCTION_R1"


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
    business_state_paths: tuple[Path, ...] = field(init=False)
    business_state_before: dict[Path, bytes] = field(init=False)
    business_state_before_hashes: dict[Path, str] = field(init=False)

    def __post_init__(self) -> None:
        self.canonical = self.root / "MathStatisticalAnalysis"
        self.canonical.mkdir()
        self.worktree_parent = self.root / ".worktrees" / self.canonical.name
        self.new = self.worktree_parent / f"B649_PRODUCTION_{NEW_HEAD}"
        self.old = self.worktree_parent / f"B649_PRODUCTION_{OLD_HEAD}"
        self.make_source(self.new)
        self.make_source(self.old)

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
        self.business_state_paths = (
            self.config.database,
            self.operation_root / "scheduler-health-state.json",
            self.operation_root / "predictions" / "forecast.json",
            self.operation_root / "reports" / "score-report.json",
        )
        business_state_bytes = (
            b"SQLite format 3\x00B649 fixture business state\n",
            b'{"scheduler":"healthy","last_run":"fixture"}\n',
            b'{"prediction_id":"fixture","forecast":[1,2,3]}\n',
            b'{"report_id":"fixture","score":42,"task_data":{"case":"B649"}}\n',
        )
        for path, data in zip(self.business_state_paths, business_state_bytes, strict=True):
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o600)
        self.business_state_before = {path: path.read_bytes() for path in self.business_state_paths}
        self.business_state_before_hashes = {
            path: hashlib.sha256(data).hexdigest()
            for path, data in self.business_state_before.items()
        }

    @staticmethod
    def make_source(path: Path) -> None:
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
        default_factory=lambda: [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    )
    file_rows: list[str] = field(default_factory=lambda: ["p424242", "fcwd", "n/tmp"])
    fail_bootstrap_new_once: bool = False
    fail_command_once: tuple[str, ...] | None = None
    after_mutation: Callable[[tuple[str, ...]], None] | None = None
    # worktree -> (head, tree, has_durable_ref). Defaults to exactly the prior
    # hardcoded new/old pair; a test registers an additional (e.g. legacy-
    # layout) worktree by adding an entry. has_durable_ref=False simulates a
    # worktree with no resolvable refs/heads/runtime/b649/<HEAD> ref -- the
    # git call fails exactly as it would live, instead of a harness assertion.
    worktree_identities: dict[Path, tuple[str, str, bool]] = field(
        default_factory=lambda: dict[Path, tuple[str, str, bool]]()
    )

    def __post_init__(self) -> None:
        if self.loaded_source is None:
            self.loaded_source = self.fixture.old
        if not self.worktree_identities:
            self.worktree_identities = {
                self.fixture.new: (NEW_HEAD, NEW_TREE, True),
                self.fixture.old: (OLD_HEAD, OLD_TREE, True),
            }

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
        if self.fail_command_once == args:
            self.fail_command_once = None
            return _completed(args, stderr="fake mutation failure", returncode=1)
        if args[:2] == ("git", "--no-optional-locks"):
            worktree = Path(args[3])
            assert worktree in self.worktree_identities, f"unregistered worktree: {worktree}"
            head, tree, has_ref = self.worktree_identities[worktree]
            if args[4] == "status":
                return _completed(args, self.status_by_path.get(worktree, ""))
            assert args[4] == "rev-parse"
            if args[5:] == ("--show-toplevel",):
                return _completed(args, str(worktree) + "\n")
            assert args[5:7] == ("--verify", "--end-of-options")
            revision = args[7]
            values = {"HEAD": head, "HEAD^{tree}": tree}
            if has_ref:
                values[f"refs/heads/runtime/b649/{head}^{{commit}}"] = head
            if revision not in values:
                return _completed(
                    args,
                    stderr=f"fatal: ambiguous argument '{revision}': unknown revision or path\n",
                    returncode=128,
                )
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
        if args == ("ps", "-ww", "-axo", "pid=,ppid=,uid=,stat=,command="):
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
            if not self.enabled:
                return _completed(args, stderr="service is disabled", returncode=5)
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


def test_fake_launchd_rejects_bootstrap_while_disabled(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture, loaded=False, enabled=False)
    result = runner(("launchctl", "bootstrap", DOMAIN, str(fixture.plist_path)))

    assert result.returncode == 5
    assert result.stderr == "service is disabled"
    assert runner.loaded is False
    assert runner.enabled is False


def test_source_validation_fsmonitor_metadata_is_passive_before_ownership_snapshot(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    git_admin = fixture.canonical / ".git" / "worktrees" / fixture.new.name
    git_admin.mkdir(parents=True)
    (git_admin / "index").touch()
    (fixture.new / ".git").write_text(f"gitdir: {git_admin}\n", encoding="utf-8")
    fsmonitor_pid = 424243
    status_call = (
        "git",
        "--no-optional-locks",
        "-C",
        str(fixture.new),
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )

    def runner_after_source_validation(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        result = runner(argv)
        if tuple(argv) == status_call:
            runner.process_rows.append(
                f"{fsmonitor_pid} 1 {UID} S git fsmonitor--daemon run"
            )
            runner.file_rows.extend(
                [
                    f"p{fsmonitor_pid}",
                    "fcwd",
                    "n/tmp",
                    "ftxt",
                    "n/usr/bin/git",
                    "f3",
                    f"n{git_admin / 'index'}",
                ]
            )
        return result

    validate_source = cast(Callable[..., dict[str, object]], vars(cutover)["_validate_source"])
    ownership_snapshot = cast(
        Callable[..., dict[str, object]], vars(cutover)["_ownership_snapshot"]
    )
    source = validate_source(
        fixture.config,
        runner_after_source_validation,
        role="new",
        expected_head=NEW_HEAD,
        expected_tree=NEW_TREE,
        expected_ref=fixture.config.durable_ref,
    )
    assert any(row.startswith(f"{fsmonitor_pid} ") for row in runner.process_rows)

    ownership = ownership_snapshot(fixture.config, runner_after_source_validation, source)

    runtime = _object(ownership["runtime"])
    process_calls = runner.calls
    assert process_calls.index(status_call) < process_calls.index(
        ("ps", "-ww", "-axo", "pid=,ppid=,uid=,stat=,command=")
    )
    assert runtime["classification"] == "ABSENT"
    assert runtime["pids"] == []


def _assert_business_state_unchanged(fixture: Fixture) -> None:
    for path in fixture.business_state_paths:
        current = path.read_bytes()
        assert current == fixture.business_state_before[path]
        assert hashlib.sha256(current).hexdigest() == fixture.business_state_before_hashes[path]


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


def test_plan_rejects_a_venv_interpreter_that_resolves_outside_the_release(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    external = fixture.root / "external-python"
    external.write_text("#!/bin/sh\n", encoding="utf-8")
    external.chmod(0o700)
    interpreter = fixture.new / ".venv/bin/python"
    interpreter.unlink()
    interpreter.symlink_to(external)

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("outside the source worktree" in str(failure) for failure in failures)
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
    _assert_business_state_unchanged(fixture)
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
        ("launchctl", "enable", f"{DOMAIN}/{cutover.LABEL}"),
        ("launchctl", "bootstrap", DOMAIN, str(fixture.plist_path)),
    ]

    rolled_back = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == fixture.old
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert rolled_back["business_state"] == "UNCHANGED"
    _assert_business_state_unchanged(fixture)
    rollback_after = _object(rolled_back["after"])
    assert (
        _object(rollback_after["plist"])["sha256"]
        == hashlib.sha256(fixture.old_plist_bytes).hexdigest()
    )
    rolled_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert rolled_receipt["status"] == "ROLLBACK_SUCCESS"

    duplicate_rollback = cutover.rollback(fixture.config, runner=runner)
    assert duplicate_rollback["status"] == "ALREADY_ROLLED_BACK"


def test_duplicate_apply_revalidates_the_receipt_bound_source(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    mutation_count = len(runner.mutation_calls)
    runner.status_by_path[fixture.new] = " M drifted-after-apply.py\n"

    with pytest.raises(cutover.CutoverSafetyError, match="existing-new source is not clean"):
        cutover.apply(fixture.config, plan=plan, runner=runner)

    assert len(runner.mutation_calls) == mutation_count


def test_apply_rejects_a_plan_that_differs_from_the_existing_receipt(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    different_plan = copy.deepcopy(plan)
    different_prestate = _object(different_plan["prestate"])
    different_prestate["old_enabled"] = False
    prestate_digest = cast(Callable[[dict[str, object]], str], vars(cutover)["_prestate_digest"])(
        different_prestate
    )
    different_plan["prestate_digest"] = prestate_digest
    target = _object(different_plan["target"])
    new_source = _object(_object(different_plan["source"])["new"])
    plan_digest = cast(Callable[[object], str], vars(cutover)["_sha256_json"])(
        {
            "schema_version": cutover.PLAN_SCHEMA_VERSION,
            "target": target,
            "prestate_digest": prestate_digest,
            "new_source": new_source,
            "new_plist_sha256": different_prestate["new_plist_sha256"],
        }
    )
    different_plan["plan_digest"] = plan_digest
    mutation_count = len(runner.mutation_calls)

    with pytest.raises(cutover.CutoverSafetyError, match="plan prestate drifted"):
        cutover.apply(fixture.config, plan=different_plan, runner=runner)

    assert len(runner.mutation_calls) == mutation_count


def test_apply_reconciles_a_completed_receipt_for_the_next_cutover(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    first_plan = cutover.build_plan(fixture.config, runner=runner)
    first = cutover.apply(fixture.config, plan=first_plan, runner=runner)
    assert first["status"] == "SUCCESS"

    next_config = replace(
        fixture.config,
        source_worktree=fixture.old,
        expected_head=OLD_HEAD,
        expected_tree=OLD_TREE,
        durable_ref=f"refs/heads/runtime/b649/{OLD_HEAD}",
    )
    next_plan = cutover.build_plan(next_config, runner=runner)
    assert next_plan["status"] == "PASS"

    second = cutover.apply(next_config, plan=next_plan, runner=runner)

    assert second["status"] == "SUCCESS"
    assert runner.loaded_source == fixture.old
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["plan_digest"] == next_plan["plan_digest"]


def test_apply_recovery_is_not_reported_as_cli_success(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_config(
        _args: argparse.Namespace, *, source_worktree: Path | None = None
    ) -> cutover.CutoverConfig:
        del source_worktree
        return fixture.config

    def recovered_apply(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"status": "RECOVERED"}

    monkeypatch.setattr(cutover, "_config_from_args", fake_config)
    monkeypatch.setattr(cutover, "apply", recovered_apply)

    exit_code = cutover.main(
        ["apply", "--source-worktree", str(fixture.new)], runner=FakeLaunchd(fixture)
    )

    assert exit_code == 1
    assert '"status":"RECOVERED"' in capsys.readouterr().out


def test_cli_receipt_file_is_compared_to_the_canonical_receipt(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    forged = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    forged["operation_id"] = "forged-receipt"
    alternate = fixture.root / "forged-receipt.json"
    alternate.write_text(json.dumps(forged), encoding="utf-8")
    alternate.chmod(0o600)

    def fake_config(
        _args: argparse.Namespace, *, source_worktree: Path | None = None
    ) -> cutover.CutoverConfig:
        del source_worktree
        return fixture.config

    monkeypatch.setattr(cutover, "_config_from_args", fake_config)

    exit_code = cutover.main(["rollback", "--receipt-file", str(alternate)], runner=runner)

    assert exit_code == 1
    assert "supplied receipt differs from the durable receipt" in capsys.readouterr().out
    assert len(runner.mutation_calls) == 4


def test_apply_isolated_to_the_exact_b649_launchagent_target(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    allowed_mutations = {
        ("launchctl", "disable", fixture.config.target),
        ("launchctl", "bootout", fixture.config.target),
        ("launchctl", "bootstrap", fixture.config.launch_domain, str(fixture.plist_path)),
        ("launchctl", "enable", fixture.config.target),
    }

    def guarded_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        args = tuple(argv)
        if (
            args[:2] == ("launchctl", "disable")
            or args[:2]
            == (
                "launchctl",
                "bootout",
            )
            or args[:2] == ("launchctl", "bootstrap")
            or args[:2] == ("launchctl", "enable")
        ):
            assert args in allowed_mutations
        return runner(args)

    plan = cutover.build_plan(fixture.config, runner=guarded_runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=guarded_runner)

    assert applied["status"] == "SUCCESS"
    assert set(runner.mutation_calls) <= allowed_mutations
    assert all(
        call[-1] == fixture.config.target
        for call in runner.mutation_calls
        if call[1] in {"disable", "bootout", "enable"}
    )


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


@pytest.mark.parametrize(
    ("loaded", "enabled", "verbs"),
    [
        (True, True, ["disable", "bootout", "enable", "bootstrap"]),
        (True, False, ["bootout", "enable", "bootstrap", "disable"]),
        (False, True, ["disable", "enable"]),
        (False, False, []),
    ],
)
def test_apply_and_rollback_preserve_loaded_and_enabled_prestate(
    fixture: Fixture, loaded: bool, enabled: bool, verbs: list[str]
) -> None:
    runner = FakeLaunchd(fixture, loaded=loaded, enabled=enabled)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    assert _object(plan["launchd"])["old_state"] == ("LOADED" if loaded else "UNLOADED")
    assert _object(plan["launchd"])["old_enabled"] is enabled

    applied = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert applied["status"] == "SUCCESS"
    assert runner.loaded is loaded
    assert runner.enabled is enabled
    assert [call[1] for call in runner.mutation_calls] == verbs
    mutation_count = len(runner.mutation_calls)
    after = _object(applied["after"])
    assert _object(after["launchd"])["state"] == ("LOADED" if loaded else "UNLOADED")
    assert after["enabled"] is enabled
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    rolled_back = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is loaded
    assert runner.enabled is enabled
    assert [call[1] for call in runner.mutation_calls[mutation_count:]] == verbs
    after = _object(rolled_back["after"])
    assert _object(after["launchd"])["state"] == ("LOADED" if loaded else "UNLOADED")
    assert after["enabled"] is enabled
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    _assert_business_state_unchanged(fixture)


@pytest.mark.parametrize("with_zombie", [False, True])
def test_plan_rejects_active_shadow_before_any_mutation(
    fixture: Fixture, with_zombie: bool
) -> None:
    runner = FakeLaunchd(fixture)
    runner.process_rows = [f"424242 1 {UID} S {fixture.old}/tools/b649_pair_rule_forward_shadow.py"]
    if with_zombie:
        runner.process_rows.append(f"424243 1 {UID} Z <defunct>")

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("old_state" in str(failure) for failure in failures)
    ownership = _object(result["ownership"])
    assert _object(ownership["shadow"])["classification"] == "PRESENT"
    assert _object(ownership["primary_lock"])["state"] == "IDLE"
    assert runner.mutation_calls == []


@pytest.mark.parametrize("state", ["Z", "Z+"])
@pytest.mark.parametrize("stale_scheduler", [False, True])
def test_plan_passes_with_verified_zombie_only(
    fixture: Fixture, state: str, stale_scheduler: bool
) -> None:
    runner = FakeLaunchd(fixture)
    command = (
        f"python {fixture.old}/tools/b649_goalc_local_scheduler.py run"
        if stale_scheduler
        else "<defunct>"
    )
    runner.process_rows.append(f"424243 1 {UID} {state} {command}")
    result = cutover.build_plan(fixture.config, runner=runner)
    assert result["status"] == "PASS", result["failures"]
    assert result["failures"] == []
    ownership = _object(result["ownership"])
    for role in ("runtime", "primary", "scheduler", "shadow"):
        assert _object(ownership[role]) == {"classification": "ABSENT", "pids": []}
    process = _object(ownership["process"])
    assert process["zombie_pids"] == [424243]
    assert process["uncertainties"] == []
    assert runner.mutation_calls == []
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert not fixture.receipt_path.exists()
    assert not fixture.cutover_lock_path.exists()
    _assert_business_state_unchanged(fixture)


@pytest.mark.parametrize("state", ["S", "R"])
@pytest.mark.parametrize("stale_scheduler", [False, True])
def test_plan_still_blocks_live_zombie_lookalike(
    fixture: Fixture, state: str, stale_scheduler: bool
) -> None:
    runner = FakeLaunchd(fixture)
    command = (
        f"python {fixture.old}/tools/b649_goalc_local_scheduler.py run"
        if stale_scheduler
        else "<defunct>"
    )
    runner.process_rows.append(f"424243 1 {UID} {state} {command}")
    result = cutover.build_plan(fixture.config, runner=runner)
    expected = "PRESENT" if stale_scheduler else "UNVERIFIABLE"
    assert result["status"] == "FAIL"
    assert result["failures"] == [
        f"old_state: ActiveCycleError: runtime ownership is not idle: {expected}"
    ]
    assert runner.mutation_calls == []


@pytest.mark.parametrize("evidence", ["cwd", "primary", "shadow"])
def test_plan_blocks_zombie_with_inconsistent_evidence(fixture: Fixture, evidence: str) -> None:
    runner = FakeLaunchd(fixture)
    runner.process_rows.append(f"424243 1 {UID} Z <defunct>")
    path = {
        "cwd": fixture.old,
        "primary": fixture.primary_lock_path,
        "shadow": fixture.shadow_lock_path,
    }[evidence]
    runner.file_rows.extend(["p424243", "fcwd" if evidence == "cwd" else "f3", f"n{path}"])
    result = cutover.build_plan(fixture.config, runner=runner)
    assert result["status"] == "FAIL"
    assert result["failures"] == [
        "old_state: ActiveCycleError: runtime ownership is not idle: UNVERIFIABLE"
    ]
    assert runner.mutation_calls == []


@pytest.mark.parametrize("state", ["", "Zinvalid"])
def test_plan_blocks_missing_or_malformed_process_state(fixture: Fixture, state: str) -> None:
    runner = FakeLaunchd(fixture)
    runner.process_rows.append(f"424243 1 {UID} {state} <defunct>")
    result = cutover.build_plan(fixture.config, runner=runner)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["old_state: Unverifiable: unparseable process table row"]
    assert runner.mutation_calls == []


def test_plan_passes_when_only_passive_git_fsmonitor_daemon_is_present(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    runner.process_rows = [
        (
            f"10793 1 {UID} S /Library/Developer/CommandLineTools/usr/libexec/git-core/git "
            "fsmonitor--daemon run --detach --ipc-threads=8"
        )
    ]
    runner.file_rows = [
        "p10793",
        "fcwd",
        "n/Users/kelvin",
        "ftxt",
        "n/Library/Developer/CommandLineTools/usr/libexec/git-core/git",
        "ftxt",
        "n/usr/lib/dyld",
        "f4",
        f"n{fixture.old}",
    ]

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "PASS", result.get("failures")
    assert result["failures"] == []
    ownership = _object(result["ownership"])
    assert _object(ownership["runtime"])["classification"] == "ABSENT"
    assert _object(ownership["primary"])["classification"] == "ABSENT"
    assert _object(ownership["scheduler"])["classification"] == "ABSENT"
    assert _object(ownership["shadow"])["classification"] == "ABSENT"
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
                f"424242 1 {UID} S {fixture.old}/tools/b649_goalc_local_scheduler.py"
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

    runner.process_rows = [f"424242 1 {UID} S /usr/bin/fixture-shell"]
    recovered = cutover.rollback(fixture.config, runner=runner)

    assert recovered["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded_source == fixture.old
    assert runner.enabled is True


def test_apply_unloaded_enabled_race_is_detected_before_plist_replacement(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture, loaded=False, enabled=True)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    def make_scheduler_active(args: tuple[str, ...]) -> None:
        if args[1] == "disable":
            runner.process_rows = [
                f"424242 1 {UID} S {fixture.old}/tools/b649_goalc_local_scheduler.py"
            ]

    runner.after_mutation = make_scheduler_active
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert runner.mutation_calls == [
        ("launchctl", "disable", fixture.config.target),
    ]
    assert not any(action["name"] == "install-plist" for action in _objects(result["actions"]))


def test_apply_interruption_after_launchd_mutation_leaves_started_receipt(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    staged_statuses: list[object] = []

    def interrupt_after_disable(args: tuple[str, ...]) -> None:
        if args[1] == "disable":
            staged_statuses.append(
                json.loads(fixture.receipt_path.read_text(encoding="utf-8"))["status"]
            )
            runner.after_mutation = None
            raise KeyboardInterrupt("synthetic interruption after disable")

    runner.after_mutation = interrupt_after_disable
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERED"
    assert staged_statuses == ["IN_PROGRESS"]
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "RECOVERED"
    assert receipt["phase"] == "COMPLETED"
    interrupted = next(
        action for action in _objects(result["actions"]) if action["name"] == "disable-before-apply"
    )
    assert interrupted["status"] == "INTERRUPTED"
    assert interrupted["interrupted"] is True
    assert interrupted["mutation"] is True
    assert runner.enabled is True
    assert runner.loaded_source == fixture.old
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    _assert_business_state_unchanged(fixture)


@pytest.mark.parametrize("verb", ["disable", "bootout", "enable"])
def test_apply_launchd_mutation_boundary_failures_are_explicit(fixture: Fixture, verb: str) -> None:
    runner = FakeLaunchd(
        fixture,
        fail_command_once=("launchctl", verb, fixture.config.target),
    )
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    expected_status = "RECOVERED"
    assert result["status"] == expected_status
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == expected_status
    assert all(
        call[0] == "launchctl"
        and (
            (call[1] in {"disable", "bootout", "enable"} and call[2] == fixture.config.target)
            or (
                call[1] == "bootstrap"
                and call[2] == fixture.config.launch_domain
                and call[3] == str(fixture.plist_path)
            )
        )
        for call in runner.mutation_calls
    )
    assert not any(call[1] == "kill" for call in runner.mutation_calls)


@pytest.mark.parametrize("loaded", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_apply_post_replace_failure_is_counted_and_recovered(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, loaded: bool, enabled: bool
) -> None:
    runner = FakeLaunchd(fixture, loaded=loaded, enabled=enabled)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    original_atomic_write = cast(
        Callable[..., cutover.FileIdentity], vars(cutover)["_atomic_write"]
    )
    raised = False

    def replace_then_raise(
        path: Path,
        data: bytes,
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        nonlocal raised
        identity = original_atomic_write(path, data, expected=expected)
        if path == fixture.plist_path and data != fixture.old_plist_bytes and not raised:
            raised = True
            raise OSError("failure after plist replace")
        return identity

    monkeypatch.setattr(cutover, "_atomic_write", replace_then_raise)
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERED"
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert runner.loaded_source == fixture.old
    assert runner.loaded is loaded
    assert runner.enabled is enabled
    after = _object(result["after"])
    assert _object(after["launchd"])["state"] == ("LOADED" if loaded else "UNLOADED")
    assert after["enabled"] is enabled
    names = [action["name"] for action in _objects(result["actions"])]
    assert "install-plist" in names
    assert "restore-plist" in names
    install = next(
        action for action in _objects(result["actions"]) if action["name"] == "install-plist"
    )
    assert install["after_observation"] == "OBSERVED"
    assert _object(install["after"])["sha256"] == _object(plan["prestate"])["new_plist_sha256"]
    _assert_business_state_unchanged(fixture)
    assert bool(runner.mutation_calls) is (loaded or enabled)
    assert result["mutation_summary"] == {
        "launchd": True,
        "plist": True,
        "control_files": True,
    }


def test_apply_source_drift_after_plist_install_blocks_new_bootstrap(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    original_atomic_write = cast(
        Callable[..., cutover.FileIdentity], vars(cutover)["_atomic_write"]
    )

    def install_then_drift(
        path: Path,
        data: bytes,
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        identity = original_atomic_write(path, data, expected=expected)
        if path == fixture.plist_path and data != fixture.old_plist_bytes:
            runner.status_by_path[fixture.new] = " M drifted-before-bootstrap.py\n"
        return identity

    monkeypatch.setattr(cutover, "_atomic_write", install_then_drift)
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERED"
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    assert runner.loaded_source == fixture.old
    assert not any(action["name"] == "bootstrap-new" for action in _objects(result["actions"]))


def test_apply_active_cycle_after_enable_blocks_bootstrap(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    def make_scheduler_active(args: tuple[str, ...]) -> None:
        if args[1] == "enable":
            runner.process_rows = [
                f"424242 1 {UID} S {fixture.new}/tools/b649_goalc_local_scheduler.py"
            ]

    runner.after_mutation = make_scheduler_active
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    assert any(call[1] == "enable" for call in runner.mutation_calls)
    assert not any(call[1] == "bootstrap" for call in runner.mutation_calls)
    assert not any(call[1] == "kill" for call in runner.mutation_calls)


@pytest.mark.parametrize("operation", ["apply", "recovery", "rollback"])
@pytest.mark.parametrize("enabled", [False, True])
def test_transition_accepts_run_at_load_activity(
    fixture: Fixture, operation: str, enabled: bool
) -> None:
    runner = FakeLaunchd(fixture, enabled=enabled)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    if operation == "rollback":
        assert cutover.apply(fixture.config, plan=plan, runner=runner)["status"] == "SUCCESS"
    runner.fail_bootstrap_new_once = operation == "recovery"

    def run_at_load(args: tuple[str, ...]) -> None:
        if args[1] == "bootstrap":
            runner.process_rows = [
                f"424242 1 {UID} S {runner.loaded_source}/tools/b649_goalc_local_scheduler.py"
            ]

    runner.after_mutation = run_at_load
    result = (
        cutover.rollback(fixture.config, runner=runner)
        if operation == "rollback"
        else cutover.apply(fixture.config, plan=plan, runner=runner)
    )

    assert result["status"] == {
        "apply": "SUCCESS",
        "recovery": "RECOVERED",
        "rollback": "ROLLBACK_SUCCESS",
    }[operation]
    expected_source = fixture.new if operation == "apply" else fixture.old
    assert runner.loaded is True
    assert runner.loaded_source == expected_source
    assert runner.enabled is enabled
    assert runner.process_rows == [
        f"424242 1 {UID} S {expected_source}/tools/b649_goalc_local_scheduler.py"
    ]
    after = _object(result["after"])
    assert _object(after["launchd"])["state"] == "LOADED"
    assert after["enabled"] is enabled
    assert not any(call[1] in {"kickstart", "kill"} for call in runner.mutation_calls)
    _assert_business_state_unchanged(fixture)


@pytest.mark.parametrize("operation", ["apply", "recovery", "rollback"])
def test_transition_rejects_wrong_loaded_binding_after_bootstrap(
    fixture: Fixture, operation: str
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    if operation == "rollback":
        assert cutover.apply(fixture.config, plan=plan, runner=runner)["status"] == "SUCCESS"
    runner.fail_bootstrap_new_once = operation == "recovery"

    def load_wrong_source(args: tuple[str, ...]) -> None:
        if args[1] == "bootstrap":
            runner.loaded_source = fixture.old if operation == "apply" else fixture.new

    runner.after_mutation = load_wrong_source
    result = (
        cutover.rollback(fixture.config, runner=runner)
        if operation == "rollback"
        else cutover.apply(fixture.config, plan=plan, runner=runner)
    )

    assert result["status"] == "RECOVERY_REQUIRED"
    failures = cast(list[object], result["failures"])
    assert any("loaded LaunchAgent runtime tuple differs" in str(f) for f in failures)
    assert not any(call[1] in {"kickstart", "kill"} for call in runner.mutation_calls)
    _assert_business_state_unchanged(fixture)


def test_same_root_resolves_parent_escape_paths(fixture: Fixture) -> None:
    same_root = cast(
        Callable[[dict[str, object], dict[str, object]], bool], vars(cutover)["_same_root"]
    )
    runtime: dict[str, object] = {
        "working_directory": str(fixture.old),
        "interpreter": str(fixture.old / ".venv/bin/python"),
        "script": str(fixture.old / "tools/b649_goalc_local_scheduler.py"),
        "pythonpath": str(fixture.old / "src"),
    }
    escaped = dict(runtime)
    escaped["script"] = str(fixture.old / "../outside-scheduler.py")
    source: dict[str, object] = {"source_worktree": str(fixture.old)}

    assert same_root(runtime, source) is True
    assert same_root(escaped, source) is False


def test_apply_receipt_prestage_write_failure_has_no_runtime_mutation(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    def fail_save(
        _config: cutover.CutoverConfig,
        _receipt: dict[str, object],
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        del expected
        raise OSError("receipt unavailable")

    monkeypatch.setattr(cutover, "_save_receipt", fail_save)
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "NOT_STARTED"
    assert runner.mutation_calls == []
    assert not fixture.receipt_path.exists()


def test_apply_final_receipt_write_failure_persists_recovery_provenance(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    original_save = cast(Callable[..., cutover.FileIdentity], vars(cutover)["_save_receipt"])
    save_count = 0

    def fail_final_save(
        config: cutover.CutoverConfig,
        receipt: dict[str, object],
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        nonlocal save_count
        save_count += 1
        if save_count == 2:
            raise OSError("final receipt unavailable")
        return original_save(config, receipt, expected=expected)

    monkeypatch.setattr(cutover, "_save_receipt", fail_final_save)
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    assert runner.loaded_source == fixture.new
    assert fixture.plist_path.read_bytes() != fixture.old_plist_bytes
    durable_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert durable_receipt["status"] == "RECOVERY_REQUIRED"
    assert durable_receipt["after"] == result["after"]


def test_rollback_receipt_prestage_failure_is_structured(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    mutation_count = len(runner.mutation_calls)

    def fail_save(
        _config: cutover.CutoverConfig,
        _receipt: dict[str, object],
        *,
        expected: cutover.FileIdentity | None,
    ) -> cutover.FileIdentity:
        del expected
        raise OSError("rollback receipt unavailable")

    monkeypatch.setattr(cutover, "_save_receipt", fail_save)
    result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    assert len(runner.mutation_calls) == mutation_count
    assert fixture.plist_path.read_bytes() != fixture.old_plist_bytes


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
    _assert_business_state_unchanged(fixture)
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
    runner.process_rows = [f"424242 1 {UID} S {fixture.new}/tools/b649_goalc_local_scheduler.py"]
    before_mutations = len(runner.mutation_calls)

    result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert result["status"] == "ROLLBACK_BLOCKED_ACTIVE_CYCLE"
    assert result["kill_attempted"] is False
    assert len(runner.mutation_calls) == before_mutations
    assert fixture.plist_path.read_bytes() != fixture.old_plist_bytes


def test_rollback_passes_wrapper_only_ownership_gate_without_mutating_fake(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    receipt, new_plist_bytes = _prepare_recovery_required_new_release(fixture, runner)
    _set_protected_task_checkpoint_ancestor(fixture, runner, monkeypatch)

    def stop_after_ownership_gate(
        config: cutover.CutoverConfig,
        gate_runner: FakeLaunchd,
        source: dict[str, object],
        expected_runtime: dict[str, object],
    ) -> dict[str, object]:
        raise cutover.CutoverSafetyError("test stopped after rollback ownership gate")

    monkeypatch.setattr(cutover, "_assert_runtime_binding", stop_after_ownership_gate)

    try:
        result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)
    except cutover.CutoverSafetyError as exc:
        assert "stopped after rollback ownership gate" in str(exc)
    else:
        pytest.fail(f"rollback stopped before the post-gate sentinel: {result!r}")

    assert runner.mutation_calls == []
    assert fixture.plist_path.read_bytes() == new_plist_bytes
    persisted_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert persisted_receipt["status"] == "RECOVERY_REQUIRED"


def test_rollback_still_blocks_scheduler_with_protected_wrapper_ancestor(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
    receipt, new_plist_bytes = _prepare_recovery_required_new_release(fixture, runner)
    _set_protected_task_checkpoint_ancestor(
        fixture,
        runner,
        monkeypatch,
        live_scheduler=True,
    )

    result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert result["status"] == "ROLLBACK_BLOCKED_ACTIVE_CYCLE"
    assert "runtime ownership is not idle: PRESENT" in cast(list[str], result["failures"])[0]
    assert runner.mutation_calls == []
    assert fixture.plist_path.read_bytes() == new_plist_bytes
    persisted_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert persisted_receipt["status"] == "RECOVERY_REQUIRED"


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


# --- Receipt-bound OLD/PRESTATE legacy-layout compatibility ---------------
#
# _validate_bound_source used to reapply config.strict_release_layout's
# B649_PRODUCTION_<HEAD> release-materialization naming to every role,
# including the OLD/PRESTATE side during automatic recovery, explicit
# rollback, and completed-receipt reconciliation -- even though build_plan's
# and rollback's own inline OLD-role checks already correctly pass
# strict_release_layout=False for that side. A real production OLD runtime
# predates that naming convention (see b649-cutover-plan-old-runtime-durable-
# ref-missing), so those bootstrap-time re-validations rejected it. The tests
# below cover the fix: an OLD/PRESTATE source with a same-root runtime tuple
# that resembles the real historical shape -- valid HEAD/tree/durable-ref/
# cleanliness, only its directory name is not B649_PRODUCTION_<HEAD> -- is
# now accepted for the OLD role only; the NEW role's layout requirement, and
# every other OLD-role guard (durable ref, drift, containment), is unchanged.


def _scheduler_config_for(fixture: Fixture, source: Path) -> scheduler.SchedulerConfig:
    """Build the SchedulerConfig for an arbitrary source worktree.

    Mirrors exactly how ``Fixture.__post_init__`` builds its own old
    scheduler config, parametrized only by the source worktree.
    """

    return scheduler.SchedulerConfig(
        label=cutover.LABEL,
        version=scheduler.TASK_VERSION,
        canonical_repository=fixture.canonical,
        source_worktree=source,
        python_executable=source / ".venv/bin/python",
        script_path=source / "tools/b649_goalc_local_scheduler.py",
        operation_root=fixture.operation_root,
        data_root=fixture.data_root,
        database=fixture.data_root / "lottolab.db",
        announcement=fixture.data_root / "pre-outcome-target-announcements-v1.json",
        scheduler_root=fixture.scheduler_root,
        lock_path=fixture.primary_lock_path,
        health_path=fixture.scheduler_root / "health.json",
        stdout_path=fixture.scheduler_root / "launchd.stdout.log",
        stderr_path=fixture.scheduler_root / "launchd.stderr.log",
        plist_path=fixture.plist_path,
    )


def _install_legacy_old(
    fixture: Fixture, *, name: str = LEGACY_WORKTREE_NAME
) -> tuple[Path, bytes]:
    """Materialize a legacy-layout OLD/PRESTATE worktree and install its plist.

    Built with the same ``Fixture.make_source`` as ``fixture.old`` -- a
    same-root, ordinary in-worktree interpreter -- so only the directory name
    differs from the ``B649_PRODUCTION_<HEAD>`` convention. Interpreter/
    PYTHONPATH containment is unchanged by this task and stays out of scope.
    """

    legacy = fixture.worktree_parent / name
    Fixture.make_source(legacy)
    legacy_bytes = scheduler.build_launchd_plist(_scheduler_config_for(fixture, legacy))
    fixture.plist_path.write_bytes(legacy_bytes)
    fixture.plist_path.chmod(0o600)
    return legacy, legacy_bytes


def _legacy_runner(fixture: Fixture, legacy: Path) -> FakeLaunchd:
    runner = FakeLaunchd(fixture, loaded_source=legacy)
    runner.worktree_identities[legacy] = (LEGACY_HEAD, LEGACY_TREE, True)
    return runner


def _patch_production_paths(monkeypatch: pytest.MonkeyPatch, fixture: Fixture) -> None:
    """Make strict_release_layout=True's exact-production-path gate in
    ``_validate_config`` match this hermetic fixture.

    ``strict_release_layout=True`` is the real CLI's actual, hardcoded
    setting (``_config_from_args``), and it gates two independent things: the
    ``B649_PRODUCTION_<HEAD>`` release-directory naming this task's fix is
    about (``_source_layout_error``, keyed only off ``config.
    canonical_repository``/``source_worktree`` and already hermetic), and a
    separate exact-path check against real production constants (plist,
    scheduler/data roots, locks, receipt -- see ``_validate_config``). Only
    the latter needs patching to exercise strict mode end to end without
    touching real production paths.
    """

    monkeypatch.setattr(cutover, "DEFAULT_PLIST_PATH", fixture.plist_path)
    monkeypatch.setattr(cutover, "DEFAULT_OPERATION_ROOT", fixture.operation_root)
    monkeypatch.setattr(cutover, "DEFAULT_RECEIPT_PATH", fixture.receipt_path)
    monkeypatch.setattr(cutover, "DEFAULT_CUTOVER_LOCK_PATH", fixture.cutover_lock_path)
    monkeypatch.setattr(cutover, "DEFAULT_PRIMARY_LOCK_PATH", fixture.primary_lock_path)
    monkeypatch.setattr(cutover, "DEFAULT_SHADOW_LOCK_PATH", fixture.shadow_lock_path)
    # scheduler.production_config() builds its own bare SchedulerConfig from
    # these same-family module globals before _scheduler_config()'s replace()
    # ever overrides it with config's fields, and SchedulerConfig.__post_init__
    # validates that bare construction's internal root/child relationships
    # immediately -- so GOALC_ROOT and LOCK_PATH must move together with
    # SCHEDULER_ROOT or that first construction raises before the override.
    monkeypatch.setattr(scheduler, "GOALC_ROOT", fixture.operation_root)
    monkeypatch.setattr(scheduler, "SCHEDULER_ROOT", fixture.scheduler_root)
    monkeypatch.setattr(scheduler, "LOCK_PATH", fixture.primary_lock_path)
    monkeypatch.setattr(scheduler, "DATA_ROOT", fixture.data_root)
    monkeypatch.setattr(scheduler, "DATABASE_PATH", fixture.config.database)
    monkeypatch.setattr(scheduler, "ANNOUNCEMENT_PATH", fixture.config.announcement)
    monkeypatch.setattr(scheduler, "HEALTH_PATH", fixture.config.health_path)
    monkeypatch.setattr(scheduler, "STDOUT_PATH", fixture.config.stdout_path)
    monkeypatch.setattr(scheduler, "STDERR_PATH", fixture.config.stderr_path)


def test_validate_bound_source_relaxes_layout_only_for_legacy_prestate(
    fixture: Fixture,
) -> None:
    """The exact seam this fix adds, isolated from the rest of build_plan/apply.

    legacy_prestate=True must relax only the B649_PRODUCTION_<HEAD> layout
    check, and only when the caller explicitly sets it -- proven by a control
    call with the identical source and config but legacy_prestate=False.
    """

    legacy = fixture.worktree_parent / LEGACY_WORKTREE_NAME
    Fixture.make_source(legacy)
    runner = FakeLaunchd(fixture)
    runner.worktree_identities[legacy] = (LEGACY_HEAD, LEGACY_TREE, True)
    config = replace(fixture.config, strict_release_layout=True)
    validate_bound_source = cast(
        Callable[..., dict[str, object]], vars(cutover)["_validate_bound_source"]
    )
    source_record: dict[str, object] = {
        "source_worktree": str(legacy),
        "head": LEGACY_HEAD,
        "tree": LEGACY_TREE,
        "durable_ref": f"refs/heads/runtime/b649/{LEGACY_HEAD}",
    }

    result = validate_bound_source(
        config, source_record, runner, role="bootstrap-old", legacy_prestate=True
    )

    assert result["source_worktree"] == str(legacy)

    with pytest.raises(cutover.CutoverSafetyError, match="B649_PRODUCTION_"):
        validate_bound_source(
            config, source_record, runner, role="bootstrap-old", legacy_prestate=False
        )


def test_validate_bound_source_legacy_prestate_still_requires_a_durable_ref(
    fixture: Fixture,
) -> None:
    """legacy_prestate=True relaxes only the layout-naming check: the durable-
    ref requirement (and everything else _validate_source checks) stays
    exactly as strict as it is for a NEW role."""

    legacy = fixture.worktree_parent / LEGACY_WORKTREE_NAME
    Fixture.make_source(legacy)
    runner = FakeLaunchd(fixture)
    runner.worktree_identities[legacy] = (LEGACY_HEAD, LEGACY_TREE, False)
    config = replace(fixture.config, strict_release_layout=True)
    validate_bound_source = cast(
        Callable[..., dict[str, object]], vars(cutover)["_validate_bound_source"]
    )
    source_record: dict[str, object] = {
        "source_worktree": str(legacy),
        "head": LEGACY_HEAD,
        "tree": LEGACY_TREE,
        "durable_ref": f"refs/heads/runtime/b649/{LEGACY_HEAD}",
    }

    with pytest.raises(cutover.CutoverSafetyError, match="git failed"):
        validate_bound_source(
            config, source_record, runner, role="bootstrap-old", legacy_prestate=True
        )


def test_plan_fails_for_new_release_with_mismatched_strict_layout_name(
    fixture: Fixture,
) -> None:
    """NEW's release-directory naming requirement is unaffected by this fix.

    ``strict_release_layout=True`` also gates ``_validate_config``'s exact-
    production-path checks (plist/scheduler/data roots, ...), which only
    match real production paths and so cannot be exercised through
    ``build_plan`` without patching them (see
    ``test_apply_automatic_recovery_restores_a_legacy_layout_old_prestate`` and
    siblings). Calling ``_validate_source`` directly isolates exactly the
    release-directory-naming check this test targets.
    """

    validate_source = cast(Callable[..., dict[str, object]], vars(cutover)["_validate_source"])
    mismatched = fixture.worktree_parent / "not-the-strict-layout-name"
    Fixture.make_source(mismatched)
    runner = FakeLaunchd(fixture)
    runner.worktree_identities[mismatched] = (NEW_HEAD, NEW_TREE, True)
    config = replace(fixture.config, source_worktree=mismatched, strict_release_layout=True)

    with pytest.raises(cutover.CutoverSafetyError, match="B649_PRODUCTION_"):
        validate_source(
            config,
            runner,
            role="new",
            expected_head=NEW_HEAD,
            expected_tree=NEW_TREE,
            expected_ref=config.durable_ref,
            strict_release_layout=True,
        )

    assert runner.mutation_calls == []


def test_apply_automatic_recovery_restores_a_legacy_layout_old_prestate(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_production_paths(monkeypatch, fixture)
    legacy, legacy_bytes = _install_legacy_old(fixture)
    runner = _legacy_runner(fixture, legacy)
    runner.fail_bootstrap_new_once = True
    config = replace(fixture.config, strict_release_layout=True)
    plan = cutover.build_plan(config, runner=runner)
    assert plan["status"] == "PASS", plan["failures"]

    result = cutover.apply(config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERED"
    assert runner.loaded is True
    assert runner.loaded_source == legacy
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == legacy_bytes
    _assert_business_state_unchanged(fixture)
    names = [action["name"] for action in _objects(result["actions"])]
    assert "bootstrap-new" in names
    assert "restore-plist" in names


def test_apply_and_explicit_rollback_accept_a_legacy_layout_old_prestate(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_production_paths(monkeypatch, fixture)
    legacy, legacy_bytes = _install_legacy_old(fixture)
    runner = _legacy_runner(fixture, legacy)
    config = replace(fixture.config, strict_release_layout=True)
    plan = cutover.build_plan(config, runner=runner)
    assert plan["status"] == "PASS", plan["failures"]

    applied = cutover.apply(config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    assert runner.loaded_source == fixture.new
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    rolled_back = cutover.rollback(config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == legacy
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == legacy_bytes
    assert rolled_back["business_state"] == "UNCHANGED"
    _assert_business_state_unchanged(fixture)


def test_apply_reconciles_a_completed_legacy_rollback_receipt_for_the_next_cutover(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_reconcile_completed_receipt's legacy_prestate=True branch, end to end.

    A receipt whose "after" side is the legacy OLD prestate (the most recent
    completed operation was a rollback onto it) must reconcile -- and must be
    proven to actually take the reconciliation path, not the already-applied
    fast path.
    """

    _patch_production_paths(monkeypatch, fixture)
    legacy, legacy_bytes = _install_legacy_old(fixture)
    runner = _legacy_runner(fixture, legacy)
    config = replace(fixture.config, strict_release_layout=True)
    first_plan = cutover.build_plan(config, runner=runner)
    assert first_plan["status"] == "PASS", first_plan["failures"]
    first = cutover.apply(config, plan=first_plan, runner=runner)
    assert first["status"] == "SUCCESS"
    first_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    rolled_back = cutover.rollback(config, receipt=first_receipt, runner=runner)
    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert fixture.plist_path.read_bytes() == legacy_bytes
    receipt_after_rollback = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt_after_rollback["status"] == "ROLLBACK_SUCCESS"
    assert _object(receipt_after_rollback["after"])["source"] == _object(
        _object(receipt_after_rollback["prestate"])["old_source"]
    )

    second_plan = cutover.build_plan(config, runner=runner)
    assert second_plan["status"] == "PASS", second_plan["failures"]
    assert receipt_after_rollback["plan_digest"] != second_plan["plan_digest"]

    second = cutover.apply(config, plan=second_plan, runner=runner)

    assert second["status"] == "SUCCESS"
    assert runner.loaded_source == fixture.new
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["plan_digest"] == second_plan["plan_digest"]
    assert receipt["status"] == "SUCCESS"


def test_reconcile_completed_receipt_fails_closed_when_after_source_matches_neither_side(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_production_paths(monkeypatch, fixture)
    runner = FakeLaunchd(fixture)
    config = replace(fixture.config, strict_release_layout=True)
    plan = cutover.build_plan(config, runner=runner)
    assert plan["status"] == "PASS", plan["failures"]
    applied = cutover.apply(config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"

    reconcile = cast(Callable[..., None], vars(cutover)["_reconcile_completed_receipt"])
    receipt = _object(json.loads(fixture.receipt_path.read_text(encoding="utf-8")))
    after = _object(receipt["after"])
    tampered_source = dict(_object(after["source"]))
    tampered_source["source_worktree"] = str(fixture.root / "not-either-prestate-side")
    after["source"] = tampered_source

    with pytest.raises(cutover.CutoverSafetyError, match="matches neither prestate side"):
        reconcile(config, receipt, runner=runner)


# --- reconcile-restored: already-restored receipt finalization ------------
#
# reconcile-restored finalizes a RECOVERY_REQUIRED receipt when live state has
# already independently returned to the receipt-bound OLD prestate, without
# ever calling launchctl or replacing the plist. Its cases below mirror the
# fixture's default (never-mutated) state, which already *is* exactly the OLD
# prestate -- new/loaded_source default to `fixture.old`/`fixture.old_plist_
# bytes` -- so most cases need no extra FakeLaunchd setup for the OLD side.

RECONCILE_OPERATION_ID = "b649-reconcile-fixture-operation-id-0001"


def _recovery_required_receipt(
    fixture: Fixture, plan: dict[str, object], *, operation_id: str = RECONCILE_OPERATION_ID
) -> dict[str, object]:
    """Build a RECOVERY_REQUIRED receipt the way a failed apply() would leave one."""

    receipt_base = cast(Callable[..., dict[str, object]], vars(cutover)["_receipt_base"])
    receipt = receipt_base(fixture.config, plan, operation_id)
    receipt["status"] = "RECOVERY_REQUIRED"
    receipt["phase"] = "RECOVERY_REQUIRED"
    receipt["failures"] = ["simulated: prior apply attempt left the target mid-recovery"]
    return receipt


def _write_receipt(fixture: Fixture, receipt: dict[str, object]) -> str:
    """Persist a receipt exactly like the tool would and return its sha256."""

    fixture.receipt_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_json = cast(Callable[..., cutover.FileIdentity], vars(cutover)["_write_json"])
    write_json(fixture.receipt_path, receipt, expected=None)
    return hashlib.sha256(fixture.receipt_path.read_bytes()).hexdigest()


def _prepare_recovery_required_new_release(
    fixture: Fixture, runner: FakeLaunchd
) -> tuple[dict[str, object], bytes]:
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS", plan["failures"]
    receipt = _recovery_required_receipt(fixture, plan)
    prestate = _object(receipt["prestate"])
    new_plist_bytes = base64.b64decode(
        cast(str, prestate["new_plist_bytes_b64"]),
        validate=True,
    )
    fixture.plist_path.write_bytes(new_plist_bytes)
    _write_receipt(fixture, receipt)
    return receipt, new_plist_bytes


def _set_protected_task_checkpoint_ancestor(
    fixture: Fixture,
    runner: FakeLaunchd,
    monkeypatch: pytest.MonkeyPatch,
    *,
    live_scheduler: bool = False,
) -> int:
    wrapper_pid = 952001
    invocation_pid = 952002
    runner.process_rows = [
        f"{invocation_pid} {wrapper_pid} {UID} S python tools/b649_production_cutover.py rollback",
        f"{wrapper_pid} 1 {UID} S ruby /opt/fable-method/scripts/task_checkpoint.rb "
        f"--run --repo {fixture.canonical} --worktree {fixture.new} "
        "--task-id B649_CUTOVER_PROTECTED_WRAPPER_ANCESTOR_OWNERSHIP_REPAIR_R1 "
        "--execution-id integration-test -- "
        "python tools/b649_production_cutover.py rollback",
    ]
    runner.file_rows = [
        f"p{invocation_pid}",
        "fcwd",
        "n/tmp",
        f"p{wrapper_pid}",
        "fcwd",
        "n/tmp",
    ]
    if live_scheduler:
        scheduler_pid = 952003
        runner.process_rows.append(
            f"{scheduler_pid} {wrapper_pid} {UID} S "
            f"python {fixture.new}/tools/b649_goalc_local_scheduler.py run"
        )
        runner.file_rows.extend([f"p{scheduler_pid}", "fcwd", f"n{fixture.new}"])
    monkeypatch.setattr(checkpoint.os, "getpid", lambda: invocation_pid)
    monkeypatch.setattr(checkpoint.os, "getppid", lambda: wrapper_pid)
    return wrapper_pid


def test_reconcile_restored_finalizes_an_already_restored_recovery_required_receipt(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)

    result = cutover.reconcile_restored(
        fixture.config,
        expected_operation_id=RECONCILE_OPERATION_ID,
        expected_receipt_sha256=receipt_sha256,
        runner=runner,
    )

    assert result["status"] == "ROLLBACK_SUCCESS"
    assert result["operation_id"] == RECONCILE_OPERATION_ID
    assert result["business_state"] == "UNCHANGED"
    assert runner.mutation_calls == []
    assert runner.loaded is True
    assert runner.loaded_source == fixture.old
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == fixture.old_plist_bytes
    _assert_business_state_unchanged(fixture)
    mutation_summary = _object(result["mutation_summary"])
    assert mutation_summary == {"launchd": False, "plist": False, "control_files": True}
    stored = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert stored["status"] == "ROLLBACK_SUCCESS"
    assert stored["phase"] == "COMPLETED"
    assert stored["operation_id"] == RECONCILE_OPERATION_ID
    assert stored["prestate"] == receipt["prestate"]
    assert stat.S_IMODE(fixture.receipt_path.stat().st_mode) == 0o600
    after = _object(stored["after"])
    assert (
        _object(after["plist"])["sha256"]
        == hashlib.sha256(fixture.old_plist_bytes).hexdigest()
    )


def test_reconcile_restored_preserves_an_unloaded_disabled_old_prestate(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture, loaded=False, enabled=False)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    assert _object(plan["launchd"])["old_state"] == "UNLOADED"
    assert _object(plan["launchd"])["old_enabled"] is False
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)

    result = cutover.reconcile_restored(
        fixture.config,
        expected_operation_id=RECONCILE_OPERATION_ID,
        expected_receipt_sha256=receipt_sha256,
        runner=runner,
    )

    assert result["status"] == "ROLLBACK_SUCCESS"
    assert runner.mutation_calls == []
    assert runner.loaded is False
    assert runner.enabled is False


@pytest.mark.parametrize("drift", ["plist", "enabled", "loaded"])
def test_reconcile_restored_fails_closed_on_state_drift(fixture: Fixture, drift: str) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)
    before_receipt_bytes = fixture.receipt_path.read_bytes()

    if drift == "plist":
        binding = plistlib.loads(fixture.old_plist_bytes)
        binding["ProgramArguments"][0] = str(fixture.new / ".venv/bin/python")
        fixture.plist_path.write_bytes(plistlib.dumps(binding))
        fixture.plist_path.chmod(0o600)
    elif drift == "enabled":
        runner.enabled = False
    else:
        runner.loaded = False

    with pytest.raises(cutover.CutoverSafetyError):
        cutover.reconcile_restored(
            fixture.config,
            expected_operation_id=RECONCILE_OPERATION_ID,
            expected_receipt_sha256=receipt_sha256,
            runner=runner,
        )

    assert runner.mutation_calls == []
    assert fixture.receipt_path.read_bytes() == before_receipt_bytes


@pytest.mark.parametrize("mismatch", ["operation_id", "sha256"])
def test_reconcile_restored_fails_closed_on_receipt_identity_mismatch(
    fixture: Fixture, mismatch: str
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)
    before_receipt_bytes = fixture.receipt_path.read_bytes()
    expected_operation_id = (
        "wrong-operation-id" if mismatch == "operation_id" else RECONCILE_OPERATION_ID
    )
    expected_receipt_sha256 = "0" * 64 if mismatch == "sha256" else receipt_sha256

    with pytest.raises(cutover.CutoverSafetyError):
        cutover.reconcile_restored(
            fixture.config,
            expected_operation_id=expected_operation_id,
            expected_receipt_sha256=expected_receipt_sha256,
            runner=runner,
        )

    assert runner.mutation_calls == []
    assert fixture.receipt_path.read_bytes() == before_receipt_bytes


def test_reconcile_restored_fails_closed_when_ownership_is_not_idle(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)
    before_receipt_bytes = fixture.receipt_path.read_bytes()
    runner.process_rows = [f"424242 1 {UID} S {fixture.old}/tools/b649_goalc_local_scheduler.py"]

    with pytest.raises(cutover.ActiveCycleError):
        cutover.reconcile_restored(
            fixture.config,
            expected_operation_id=RECONCILE_OPERATION_ID,
            expected_receipt_sha256=receipt_sha256,
            runner=runner,
        )

    assert runner.mutation_calls == []
    assert fixture.receipt_path.read_bytes() == before_receipt_bytes


def test_reconcile_restored_is_idempotent_when_already_reconciled(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)

    first = cutover.reconcile_restored(
        fixture.config,
        expected_operation_id=RECONCILE_OPERATION_ID,
        expected_receipt_sha256=receipt_sha256,
        runner=runner,
    )
    assert first["status"] == "ROLLBACK_SUCCESS"
    mutation_count_after_first = len(runner.mutation_calls)
    stored_bytes = fixture.receipt_path.read_bytes()

    second = cutover.reconcile_restored(
        fixture.config,
        expected_operation_id=RECONCILE_OPERATION_ID,
        expected_receipt_sha256=hashlib.sha256(stored_bytes).hexdigest(),
        runner=runner,
    )

    assert second["status"] == "ALREADY_RECONCILED"
    assert len(runner.mutation_calls) == mutation_count_after_first
    assert fixture.receipt_path.read_bytes() == stored_bytes


def test_reconcile_restored_fails_closed_when_completed_receipt_no_longer_matches_live_state(
    fixture: Fixture,
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)
    first = cutover.reconcile_restored(
        fixture.config,
        expected_operation_id=RECONCILE_OPERATION_ID,
        expected_receipt_sha256=receipt_sha256,
        runner=runner,
    )
    assert first["status"] == "ROLLBACK_SUCCESS"
    stored_bytes = fixture.receipt_path.read_bytes()
    runner.enabled = False

    with pytest.raises(cutover.CutoverSafetyError):
        cutover.reconcile_restored(
            fixture.config,
            expected_operation_id=RECONCILE_OPERATION_ID,
            expected_receipt_sha256=hashlib.sha256(stored_bytes).hexdigest(),
            runner=runner,
        )

    assert runner.mutation_calls == []
    assert fixture.receipt_path.read_bytes() == stored_bytes


def test_cli_reconcile_restored_finalizes_and_reports_success(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    receipt = _recovery_required_receipt(fixture, plan)
    receipt_sha256 = _write_receipt(fixture, receipt)

    def fake_config(
        _args: argparse.Namespace, *, source_worktree: Path | None = None
    ) -> cutover.CutoverConfig:
        del source_worktree
        return fixture.config

    monkeypatch.setattr(cutover, "_config_from_args", fake_config)

    exit_code = cutover.main(
        [
            "reconcile-restored",
            "--receipt-file",
            str(fixture.receipt_path),
            "--expected-operation-id",
            RECONCILE_OPERATION_ID,
            "--expected-receipt-sha256",
            receipt_sha256,
        ],
        runner=runner,
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ROLLBACK_SUCCESS"
    assert runner.mutation_calls == []
