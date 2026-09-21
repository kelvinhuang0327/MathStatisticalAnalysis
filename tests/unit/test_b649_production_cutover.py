"""Hermetic tests for the B649 production cutover entrypoint."""

from __future__ import annotations

import argparse
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
import tools.b649_goalc_local_scheduler as scheduler
import tools.b649_production_cutover as cutover

NEW_HEAD = "1" * 40
NEW_TREE = "2" * 40
OLD_HEAD = "3" * 40
OLD_TREE = "4" * 40
LEGACY_HEAD = "5" * 40
LEGACY_TREE = "6" * 40
DRIFTED_HEAD = "7" * 40
DRIFTED_TREE = "8" * 40
UID = os.getuid()
DOMAIN = f"gui/{UID}"
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

    def make_legacy_old(self, *, name: str = LEGACY_WORKTREE_NAME) -> Path:
        """Build an OLD/PRESTATE worktree matching the real pre-managed-cutover shape:

        a directory name that is not ``B649_PRODUCTION_<HEAD>``, and a
        ``.venv/bin/python`` whose realpath escapes the worktree (an
        already-running venv predating this convention, symlinked to a
        system/Homebrew Python). It has no dedicated runtime ref -- callers
        register it with ``FakeLaunchd.worktree_identities`` and
        ``durable_ref=False`` rather than any git ref existing for it.
        """

        path = self.worktree_parent / name
        self._make_source(path)
        external = self.root / "external-legacy-python"
        if not external.exists():
            external.write_text("#!/bin/sh\n", encoding="utf-8")
            external.chmod(0o700)
        interpreter = path / ".venv/bin/python"
        interpreter.unlink()
        interpreter.symlink_to(external)
        return path

    def make_bare_worktree(self, name: str) -> Path:
        """Build a plain, otherwise-well-formed worktree under worktree_parent."""

        path = self.worktree_parent / name
        self._make_source(path)
        return path


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
    fail_command_once: tuple[str, ...] | None = None
    after_mutation: Callable[[tuple[str, ...]], None] | None = None
    # path -> (head, tree, has_durable_ref). has_durable_ref=False simulates a
    # legacy worktree with no refs/heads/runtime/b649/<HEAD> ref: git rev-parse
    # for that ref fails exactly as it would against a real repository
    # lacking it, instead of a hard test-harness assertion error.
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

    runner.process_rows = [f"424242 1 {UID} /usr/bin/fixture-shell"]
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
                f"424242 1 {UID} {fixture.old}/tools/b649_goalc_local_scheduler.py"
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


def test_apply_post_replace_failure_is_counted_and_recovered(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeLaunchd(fixture)
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
    names = [action["name"] for action in _objects(result["actions"])]
    assert "install-plist" in names
    assert "restore-plist" in names
    install = next(
        action for action in _objects(result["actions"]) if action["name"] == "install-plist"
    )
    assert install["after_observation"] == "OBSERVED"
    assert _object(install["after"])["sha256"] == _object(plan["prestate"])["new_plist_sha256"]
    _assert_business_state_unchanged(fixture)
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


def test_apply_race_after_bootstrap_is_detected_before_enable(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"

    def make_scheduler_active(args: tuple[str, ...]) -> None:
        if args[1] == "bootstrap":
            runner.process_rows = [
                f"424242 1 {UID} {fixture.new}/tools/b649_goalc_local_scheduler.py"
            ]

    runner.after_mutation = make_scheduler_active
    result = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    assert not any(call[1] == "enable" for call in runner.mutation_calls)
    assert not any(call[1] == "kill" for call in runner.mutation_calls)


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


# --- Legacy/prestate OLD-role compatibility -------------------------------
#
# The tests below cover an OLD/PRESTATE source that predates the managed
# cutover's conventions: a worktree name that is not B649_PRODUCTION_<HEAD>,
# a .venv/bin/python whose realpath escapes the worktree (Homebrew-style),
# and no refs/heads/runtime/b649/<HEAD> durable ref. They prove this legacy
# shape is accepted for the OLD role only, while the NEW role keeps every
# strict requirement unchanged.


def _scheduler_config_for(fixture: Fixture, source: Path) -> scheduler.SchedulerConfig:
    """Build the SchedulerConfig for an arbitrary source worktree.

    Mirrors exactly how ``Fixture.__post_init__`` builds its own old/new
    scheduler configs, parametrized only by the source worktree.
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


def _install_plist(fixture: Fixture, plist_bytes: bytes) -> None:
    fixture.plist_path.write_bytes(plist_bytes)
    fixture.plist_path.chmod(0o600)


def _legacy_setup(fixture: Fixture) -> tuple[Path, bytes, FakeLaunchd]:
    """Install a legacy OLD/PRESTATE plist and return (legacy, its bytes, runner)."""

    legacy = fixture.make_legacy_old()
    legacy_bytes = scheduler.build_launchd_plist(_scheduler_config_for(fixture, legacy))
    _install_plist(fixture, legacy_bytes)
    runner = FakeLaunchd(fixture, loaded_source=legacy)
    runner.worktree_identities[legacy] = (LEGACY_HEAD, LEGACY_TREE, False)
    return legacy, legacy_bytes, runner


def test_plan_passes_for_legacy_old_prestate_while_new_release_remains_strict(
    fixture: Fixture,
) -> None:
    legacy, _legacy_bytes, runner = _legacy_setup(fixture)

    # fixture.config's NEW side is unchanged: same worktree, same durable
    # ref, same strict runtime-tuple containment -- only the OLD side (read
    # from the installed plist) is the legacy shape.
    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "PASS", result["failures"]
    old_source = _object(_object(result["source"])["old"])
    assert old_source["source_worktree"] == str(legacy)
    assert old_source["head"] == LEGACY_HEAD
    assert old_source["tree"] == LEGACY_TREE
    assert old_source["durable_ref"] is None
    assert old_source["clean"] is True
    new_source = _object(_object(result["source"])["new"])
    assert new_source["source_worktree"] == str(fixture.new)
    assert new_source["head"] == NEW_HEAD
    # NEW's durable ref is still actively required and verified, not merely
    # defaulted: it resolves because fixture.new is genuinely registered
    # with one, not because the check was skipped.
    assert new_source["durable_ref"] == f"refs/heads/runtime/b649/{NEW_HEAD}"
    assert runner.mutation_calls == []


def test_plan_fails_for_new_release_missing_durable_ref(fixture: Fixture) -> None:
    runner = FakeLaunchd(fixture)
    runner.worktree_identities[fixture.new] = (NEW_HEAD, NEW_TREE, False)

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("new_source" in str(failure) for failure in failures)
    assert runner.mutation_calls == []


def test_plan_fails_for_new_release_with_invalid_strict_layout(fixture: Fixture) -> None:
    # CutoverConfig.strict_release_layout=True also gates _validate_config's
    # exact-production-path checks (plist/scheduler/data roots, ...), which
    # only ever match real production paths and so cannot be exercised
    # hermetically through build_plan. Call _validate_source directly to
    # isolate exactly the release-directory-naming check this test targets.
    # (_source_layout_error itself reads config.strict_release_layout, so it
    # must be set on the config, not only passed as the call's own override.)
    validate_source = cast(Callable[..., dict[str, object]], vars(cutover)["_validate_source"])
    mismatched = fixture.make_bare_worktree("not-the-strict-layout-name")
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


def test_apply_and_rollback_accept_and_restore_the_legacy_old_prestate(fixture: Fixture) -> None:
    legacy, legacy_bytes, runner = _legacy_setup(fixture)

    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS", plan["failures"]

    applied = cutover.apply(fixture.config, plan=plan, runner=runner)

    assert applied["status"] == "SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == fixture.new
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() != legacy_bytes
    _assert_business_state_unchanged(fixture)
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "SUCCESS"

    rolled_back = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert runner.loaded is True
    assert runner.loaded_source == legacy
    assert runner.enabled is True
    assert fixture.plist_path.read_bytes() == legacy_bytes
    assert rolled_back["business_state"] == "UNCHANGED"
    _assert_business_state_unchanged(fixture)


@pytest.mark.parametrize("drift", ["head", "tree"])
def test_rollback_fails_closed_on_legacy_old_identity_drift(fixture: Fixture, drift: str) -> None:
    legacy, legacy_bytes, runner = _legacy_setup(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    before_mutations = len(runner.mutation_calls)

    if drift == "head":
        runner.worktree_identities[legacy] = (DRIFTED_HEAD, LEGACY_TREE, False)
    else:
        runner.worktree_identities[legacy] = (LEGACY_HEAD, DRIFTED_TREE, False)

    with pytest.raises(cutover.CutoverSafetyError, match="drifted"):
        cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    # The drift is caught before any mutation: the plist is still the
    # applied "new" bytes, not the frozen legacy "old" bytes.
    assert len(runner.mutation_calls) == before_mutations
    assert fixture.plist_path.read_bytes() != legacy_bytes


def test_rollback_fails_closed_when_legacy_old_loaded_runtime_drifts_after_bootstrap(
    fixture: Fixture,
) -> None:
    _legacy, legacy_bytes, runner = _legacy_setup(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    def corrupt_after_bootstrap(args: tuple[str, ...]) -> None:
        if args[1] == "bootstrap":
            # Simulate launchd binding a runtime that differs from the plist
            # it was just handed -- the frozen old runtime must still win.
            runner.loaded_source = fixture.new

    runner.after_mutation = corrupt_after_bootstrap
    result = cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert result["status"] == "RECOVERY_REQUIRED"
    failures = cast(list[object], result["failures"])
    assert any("runtime tuple differs" in str(failure) for failure in failures)
    assert fixture.plist_path.read_bytes() == legacy_bytes


def test_rollback_fails_closed_on_legacy_old_plist_identity_drift(fixture: Fixture) -> None:
    _legacy, legacy_bytes, runner = _legacy_setup(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    # An out-of-band rewrite of the installed plist: neither the frozen old
    # bytes nor the frozen new bytes.
    binding = plistlib.loads(legacy_bytes)
    binding["ProgramArguments"][0] = str(fixture.new / ".venv/bin/python")
    fixture.plist_path.write_bytes(plistlib.dumps(binding))
    fixture.plist_path.chmod(0o600)

    with pytest.raises(cutover.CutoverSafetyError, match="current plist differs"):
        cutover.rollback(fixture.config, receipt=receipt, runner=runner)


def test_rollback_fails_closed_when_legacy_pythonpath_escapes_after_plan(
    fixture: Fixture,
) -> None:
    legacy, _legacy_bytes, runner = _legacy_setup(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    applied_plist_bytes = fixture.plist_path.read_bytes()
    before_mutations = len(runner.mutation_calls)

    # PYTHONPATH must stay contained even for the legacy role -- unlike the
    # interpreter, it is never in the escape-allowed set.
    pythonpath = legacy / "src"
    pythonpath.rmdir()
    external = fixture.root / "external-src"
    external.mkdir()
    pythonpath.symlink_to(external)

    # Caught by rollback's own pre-flight revalidation of the frozen OLD
    # worktree, before any launchd or plist mutation -- same shape as
    # test_rollback_old_release_drift_fails_before_launchd_mutation.
    with pytest.raises(cutover.CutoverSafetyError, match="PYTHONPATH"):
        cutover.rollback(fixture.config, receipt=receipt, runner=runner)

    assert len(runner.mutation_calls) == before_mutations
    assert fixture.plist_path.read_bytes() == applied_plist_bytes


def test_legacy_old_prestate_still_requires_the_interpreter_to_exist(fixture: Fixture) -> None:
    legacy, _legacy_bytes, runner = _legacy_setup(fixture)
    # Legacy prestate relaxes only the interpreter's realpath containment: a
    # wholly missing interpreter (no symlink at all) fails to resolve at all.
    (legacy / ".venv/bin/python").unlink()

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("interpreter cannot be resolved" in str(failure) for failure in failures)


def test_legacy_old_prestate_still_requires_the_interpreter_to_be_executable(
    fixture: Fixture,
) -> None:
    legacy, _legacy_bytes, runner = _legacy_setup(fixture)
    # Point the (still legacy-escaping) interpreter symlink at a real but
    # non-executable file: realpath containment is relaxed, executability
    # is not.
    interpreter = legacy / ".venv/bin/python"
    interpreter.unlink()
    non_executable = fixture.root / "external-non-executable"
    non_executable.write_text("#!/bin/sh\n", encoding="utf-8")
    non_executable.chmod(0o600)
    interpreter.symlink_to(non_executable)

    result = cutover.build_plan(fixture.config, runner=runner)

    assert result["status"] == "FAIL"
    failures = cast(list[object], result["failures"])
    assert any("interpreter is unavailable" in str(failure) for failure in failures)


def test_apply_reconciles_a_completed_legacy_rollback_receipt_for_the_next_cutover(
    fixture: Fixture,
) -> None:
    """_reconcile_completed_receipt's legacy_prestate=True branch, end to end.

    A receipt whose "after" side is the legacy OLD prestate (i.e. the most
    recent completed operation was a rollback onto it) must reconcile -- and
    must be proven to actually take the reconciliation path, not the
    already-applied fast path.
    """

    _legacy, legacy_bytes, runner = _legacy_setup(fixture)
    first_plan = cutover.build_plan(fixture.config, runner=runner)
    assert first_plan["status"] == "PASS"
    first = cutover.apply(fixture.config, plan=first_plan, runner=runner)
    assert first["status"] == "SUCCESS"
    first_receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))

    rolled_back = cutover.rollback(fixture.config, receipt=first_receipt, runner=runner)
    assert rolled_back["status"] == "ROLLBACK_SUCCESS"
    assert fixture.plist_path.read_bytes() == legacy_bytes
    receipt_after_rollback = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt_after_rollback["status"] == "ROLLBACK_SUCCESS"
    assert _object(receipt_after_rollback["after"])["source"] == _object(
        _object(receipt_after_rollback["prestate"])["old_source"]
    )

    second_plan = cutover.build_plan(fixture.config, runner=runner)
    assert second_plan["status"] == "PASS"
    # Prove the next apply() cannot take the "matches existing receipt"
    # fast path -- the plist's replaced-file identity (inode/mtime) changed
    # across the apply+rollback cycle, so this plan_digest genuinely differs
    # and _reconcile_completed_receipt must run.
    assert receipt_after_rollback["plan_digest"] != second_plan["plan_digest"]

    second = cutover.apply(fixture.config, plan=second_plan, runner=runner)

    assert second["status"] == "SUCCESS"
    assert runner.loaded_source == fixture.new
    receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
    assert receipt["plan_digest"] == second_plan["plan_digest"]
    assert receipt["status"] == "SUCCESS"


def test_reconcile_completed_receipt_fails_closed_when_after_source_matches_neither_side(
    fixture: Fixture,
) -> None:
    _legacy, _legacy_bytes, runner = _legacy_setup(fixture)
    plan = cutover.build_plan(fixture.config, runner=runner)
    assert plan["status"] == "PASS"
    applied = cutover.apply(fixture.config, plan=plan, runner=runner)
    assert applied["status"] == "SUCCESS"

    reconcile = cast(Callable[..., None], vars(cutover)["_reconcile_completed_receipt"])
    receipt = _object(json.loads(fixture.receipt_path.read_text(encoding="utf-8")))
    after = _object(receipt["after"])
    tampered_source = dict(_object(after["source"]))
    tampered_source["source_worktree"] = str(fixture.root / "not-either-prestate-side")
    after["source"] = tampered_source

    with pytest.raises(cutover.CutoverSafetyError, match="matches neither prestate side"):
        reconcile(fixture.config, receipt, runner=runner)


def test_validate_bound_source_does_not_reapply_strict_layout_to_legacy_old(
    fixture: Fixture,
) -> None:
    """_validate_bound_source's OLD-role strict_release_layout relaxation,

    under strict_release_layout=True -- the real CLI's actual, hardcoded
    setting (_config_from_args always passes strict_release_layout=True) --
    isolated from the ref/interpreter dimensions already covered elsewhere by
    giving this legacy source a genuinely resolvable ref.
    """

    validate_bound_source = cast(
        Callable[..., dict[str, object]], vars(cutover)["_validate_bound_source"]
    )
    legacy = fixture.make_legacy_old()
    runner = FakeLaunchd(fixture, loaded_source=legacy)
    runner.worktree_identities[legacy] = (LEGACY_HEAD, LEGACY_TREE, True)
    config = replace(fixture.config, strict_release_layout=True)
    old_source_record: dict[str, object] = {
        "source_worktree": str(legacy),
        "head": LEGACY_HEAD,
        "tree": LEGACY_TREE,
        "durable_ref": f"refs/heads/runtime/b649/{LEGACY_HEAD}",
    }

    # legacy_prestate=True: config.strict_release_layout=True must NOT be
    # reapplied to the legacy (mismatched-directory-name) OLD source.
    result = validate_bound_source(
        config, old_source_record, runner, role="bootstrap-old", legacy_prestate=True
    )
    assert result["source_worktree"] == str(legacy)

    # Control: the identical source and strict config, but legacy_prestate=
    # False, must still fail the layout-naming check -- proving the
    # exemption above is real and specifically gated by legacy_prestate,
    # not by something incidental to this source or config.
    with pytest.raises(cutover.CutoverSafetyError, match="B649_PRODUCTION_"):
        validate_bound_source(
            config, old_source_record, runner, role="bootstrap-old", legacy_prestate=False
        )
