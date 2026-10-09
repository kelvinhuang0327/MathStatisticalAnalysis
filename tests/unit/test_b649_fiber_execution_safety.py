"""Focused source-authority and heavy-ownership contract tests; no solver is started."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from lottolab.research import b649_fiber_execution_safety as safety
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_certificate_reuse as reuse

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def authorized_clean_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv(safety.AUTHORITY_HEAD_ENV, head)
    monkeypatch.setenv(safety.AUTHORITY_TREE_ENV, tree)
    monkeypatch.setattr(safety, "_process_table", lambda: ())
    monkeypatch.setattr(
        safety, "DEFAULT_HEAVY_LOCK_PATH", tmp_path / "machine-lock" / "b649-heavy.lock"
    )
    git_output = safety._git_output  # pyright: ignore[reportPrivateUsage]

    def clean_test_status(root: Path, *args: str) -> str:
        if args and args[0] == "status":
            return ""
        return git_output(root, *args)

    monkeypatch.setattr(safety, "_git_output", clean_test_status)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("variable", "bad_value"),
    [
        (safety.AUTHORITY_HEAD_ENV, "0" * 40),
        (safety.AUTHORITY_TREE_ENV, "0" * 40),
    ],
)
def test_wrong_head_or_tree_fails_closed(
    monkeypatch: pytest.MonkeyPatch, variable: str, bad_value: str
) -> None:
    monkeypatch.setenv(variable, bad_value)
    with pytest.raises(safety.SafetyGateError, match="HEAD/TREE differs"):
        reuse.source_identity_preflight(ROOT, process_lines=())


def test_missing_external_authority_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(safety.AUTHORITY_HEAD_ENV)
    with pytest.raises(safety.SafetyGateError, match="explicit execution authority"):
        reuse.source_identity_preflight(ROOT, process_lines=())


def test_wrong_engine_sha_fails_closed() -> None:
    spec = replace(reuse.execution_source_spec(ROOT), engine_sha256="0" * 64)
    with pytest.raises(safety.SafetyGateError, match="engine SHA-256"):
        safety.preflight_source_identity(spec, process_lines=())


def test_stale_import_path_from_another_worktree_fails_closed() -> None:
    spec = reuse.execution_source_spec(ROOT)
    modules = dict(spec.module_files)
    modules["engine"] = (
        ROOT.parents[2] / "MathStatisticalAnalysis" / "src/lottolab/research/"
        "b649_k20_fiber_near_top_s3_census.py",
        "src/lottolab/research/b649_k20_fiber_near_top_s3_census.py",
    )
    with pytest.raises(safety.SafetyGateError, match="engine module __file__"):
        safety.preflight_source_identity(replace(spec, module_files=modules), process_lines=())


def test_dirty_tracked_source_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = safety._git_output  # pyright: ignore[reportPrivateUsage]

    def dirty_status(root: Path, *args: str) -> str:
        if args and args[0] == "status":
            return " M src/lottolab/research/example.py"
        return original(root, *args)

    monkeypatch.setattr(safety, "_git_output", dirty_status)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(safety.SafetyGateError, match="tracked source is dirty"):
        reuse.source_identity_preflight(ROOT, process_lines=())


def test_r30_tag_and_result_pin_are_separate_from_the_frozen_census_root(
    tmp_path: Path,
) -> None:
    spec = reuse.execution_source_spec(ROOT)
    with pytest.raises(safety.SafetyGateError, match="R30 source tag"):
        safety.preflight_source_identity(
            replace(spec, r30_source_tag="wrong-source-tag"), process_lines=()
        )
    with pytest.raises(safety.SafetyGateError, match="R30 tagged result SHA-256"):
        safety.preflight_source_identity(
            replace(spec, r30_result_sha256="0" * 64), process_lines=()
        )
    frozen_name = Path(census.DURABLE_RELATIVE).name
    with pytest.raises(safety.SafetyGateError, match="frozen census RUN1 result"):
        safety.preflight_source_identity(
            spec, durable_root=tmp_path / frozen_name, process_lines=()
        )


def test_valid_exact_source_authority_passes_pure_preflight() -> None:
    identity = reuse.source_identity_preflight(ROOT, process_lines=())
    assert identity.head
    assert identity.tree
    assert (
        identity.engine_sha256
        == "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276"
    )
    assert (
        identity.manifest_sha256
        == "4b1df0503ab0c4a780e56b6189821f1d2f9080c2124dc6951d8663580e79e64f"
    )
    assert (
        identity.overlay_sha256
        == "6c44200780ea742efadb1e5d161744a7665f99b13822b1613a07fc804d016b19"
    )
    assert (
        identity.r30_result_sha256
        == "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
    )
    assert not safety.DEFAULT_HEAVY_LOCK_PATH.exists()


def test_global_lock_collision_fails_and_claim_fd_matches_path_inode(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "b649-heavy.lock"
    owner = safety.acquire_machine_heavy_claim(lock_path)
    try:
        owner.assert_path_matches_fd()
        descriptor_info = owner.path.stat()
        held_info = os.fstat(owner.descriptor)
        assert (descriptor_info.st_dev, descriptor_info.st_ino) == (
            held_info.st_dev,
            held_info.st_ino,
        )
        with pytest.raises(safety.LockCollisionError, match="another B649 heavy writer"):
            safety.acquire_machine_heavy_claim(lock_path)
    finally:
        owner.release()


def test_released_global_lock_can_be_acquired_again(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "b649-heavy.lock"
    first = safety.acquire_machine_heavy_claim(lock_path)
    first.release()
    second = safety.acquire_machine_heavy_claim(lock_path)
    try:
        second.assert_path_matches_fd()
    finally:
        second.release()


def test_replaced_lock_path_is_rejected(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "b649-heavy.lock"
    owner = safety.acquire_machine_heavy_claim(lock_path)
    lock_path.unlink()
    lock_path.write_text("replacement", encoding="utf-8")
    with pytest.raises(safety.LockIntegrityError, match="no longer names the inode"):
        owner.assert_path_matches_fd()
    with pytest.raises(safety.LockIntegrityError):
        owner.release()


def test_detached_fable_lock_inode_does_not_hide_live_legacy_engine(
    tmp_path: Path,
) -> None:
    fable_lock = tmp_path / ".fable" / "checkpoints" / "legacy" / "execution.lock"
    fable_lock.parent.mkdir(parents=True)
    old_descriptor = os.open(fable_lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(old_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fable_lock.unlink()
        assert not fable_lock.exists()
        process = (
            f"999999 1 {sys.executable} -u -m "
            f"{safety.LEGACY_CENSUS_MODULE} run"
        )
        with pytest.raises(safety.SafetyGateError, match="RUN1 predecessor is still live"):
            reuse.source_identity_preflight(ROOT, process_lines=(process,))
    finally:
        os.close(old_descriptor)


def test_legacy_launcher_and_its_child_are_both_live_owners() -> None:
    init = "1 0 /sbin/launchd"
    launcher = (
        "777001 1 ruby task_checkpoint.rb --run "
        f"--task-id {safety.LEGACY_CENSUS_TASK_ID} "
        f"--execution-id {safety.LEGACY_CENSUS_TASK_ID}_SLICE1_RUN1"
    )
    child = f"777002 777001 {sys.executable} -u -c child_worker"
    unrelated = "777003 1 /usr/bin/unrelated"
    assert safety._live_legacy_pids((init, launcher, child, unrelated)) == (  # pyright: ignore[reportPrivateUsage]
        777001,
        777002,
    )


def test_orphaned_legacy_engine_child_is_rejected_after_launcher_exit() -> None:
    child = (
        f"777002 1 {sys.executable} -u -m "
        f"{safety.LEGACY_CENSUS_MODULE} run"
    )
    with pytest.raises(safety.SafetyGateError, match="RUN1 predecessor is still live"):
        reuse.source_identity_preflight(ROOT, process_lines=(child,))


def test_unparseable_live_legacy_owner_fails_closed() -> None:
    process = f"unknown-pid ruby --task-id {safety.LEGACY_CENSUS_TASK_ID}"
    with pytest.raises(safety.SafetyGateError, match="cannot parse live legacy census ownership"):
        safety._live_legacy_pids((process,))  # pyright: ignore[reportPrivateUsage]


def test_entrypoint_gate_runs_before_manifest_model_or_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(safety.AUTHORITY_HEAD_ENV)
    calls: list[str] = []

    def forbidden_load() -> census.Manifest:
        calls.append("manifest")
        raise AssertionError("model preparation must not start before the authority gate")

    monkeypatch.setattr(census, "load_manifest", forbidden_load)
    with pytest.raises(safety.SafetyGateError, match="explicit execution authority"):
        reuse.main(["run"])
    assert calls == []
