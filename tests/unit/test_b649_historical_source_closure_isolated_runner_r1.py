"""Focused regression test suite for historical source closure isolation runner.

Verifies:
1. Exact 28 sealed SOURCE_PINS, separate runtime module records, and 7-vs-28 semantics.
2. Historical source files, tests, and sealed results remain strictly immutable.
3. Group 6 and Group 7 execute cleanly in isolated subprocesses.
4. Immunity to parent process sys.modules pollution (cross-test contamination).
5. Execution order independence (Group 6 -> Group 7 and Group 7 -> Group 6).
6. Non-masking fidelity of subprocess exit status (failures never rewritten to PASS).
7. Negative tamper rejection: original tamper tests and unhandled tamper cases reject bad sources.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.research import b649_historical_source_closure_isolated_runner_r1 as runner


@pytest.fixture(scope="module")
def root_path() -> Path:
    return runner.get_repo_root()


def test_sealed_pin_inventory_and_semantics(root_path: Path) -> None:
    """A02: Verify 28 sealed SOURCE_PINS and semantic resolution of 7 vs 28."""
    explanation = runner.explain_pin_count_semantics(root_path)
    assert explanation["SEALED_SOURCE_PIN_COUNT"] == 28
    assert explanation["PREVIOUS_PACKET_ASSUMED_COUNT"] == 7
    assert explanation["SEALED_SOURCE_INVENTORY_COUNT"] == 28
    assert (
        explanation["PREVIOUS_PACKET_ASSUMED_COUNT"] != explanation["SEALED_SOURCE_INVENTORY_COUNT"]
    )
    assert "runtime" in str(explanation["PREVIOUS_PACKET_ASSUMPTION_SEMANTICS"])
    assert "PROVENANCE.SOURCE_PINS" in str(explanation["SEALED_SOURCE_FIELD_SEMANTICS"])
    assert "sys.modules" in str(explanation["RUNTIME_LOADED_HELPERS_SEMANTICS"])
    assert explanation["STATUS"] == "RESOLVED"
    assert explanation["PINNED_INVENTORY_COUNT"] == 28

    pins = runner.verify_sealed_pin_inventory(root_path)
    assert len(pins) == 28
    assert set(pins.keys()) == set(runner.SEALED_28_PINS)

    # Cross-check sealed result JSON
    sealed_result_path = root_path / runner.SEALED_T249_RESULT_PATH
    data = json.loads(sealed_result_path.read_bytes())
    sealed_pins: dict[str, str] = data["PROVENANCE"]["SOURCE_PINS"]
    assert len(sealed_pins) == 28
    assert sealed_pins == pins
    assert explanation["SEALED_SOURCE_INVENTORY"] == [
        {"path": path, "sha256": digest} for path, digest in sorted(sealed_pins.items())
    ]


def _runtime_record(
    proc: subprocess.CompletedProcess[str], *, require_modules: bool = True
) -> runner.RuntimeLoadedHelpersRecord:
    record = runner.extract_runtime_loaded_helpers(proc.stdout)
    assert record["pytest_exit_code"] == proc.returncode
    assert record["process_id"] != os.getpid()
    modules = record["modules"]
    assert modules or not require_modules
    assert all(module["inside_worktree"] for module in modules)
    paths = [module["path"] for module in modules]
    assert len(paths) == len(set(paths))
    return record


def _runtime_paths(record: runner.RuntimeLoadedHelpersRecord) -> set[str]:
    return {module["path"] for module in record["modules"]}


def test_historical_sources_and_sealed_results_immutable(root_path: Path) -> None:
    """A03: Historical sources, tests, and sealed results remain untouched."""
    protected_paths = [
        runner.GROUP6_SOURCE_PATH,
        runner.GROUP7_SOURCE_PATH,
        runner.GROUP6_TEST_PATH,
        runner.GROUP7_TEST_PATH,
        runner.SEALED_T249_RESULT_PATH,
        runner.SEALED_TWO_TIED_RESULT_PATH,
    ]
    for rel_path in protected_paths:
        disk_bytes = (root_path / rel_path).read_bytes()
        head_bytes = subprocess.check_output(
            ["git", "-c", "core.fsmonitor=false", "show", f"HEAD:{rel_path}"],
            cwd=root_path,
        )
        assert disk_bytes == head_bytes, f"Protected historical path modified: {rel_path}"


def test_group6_isolated_subprocess_success(root_path: Path) -> None:
    """A04: Group 6 actual historical tests execute in an isolated subprocess."""
    proc = runner.run_group6(root=root_path)
    assert proc.returncode == 0, f"Group 6 tests failed: {proc.stderr}\n{proc.stdout}"
    assert "27 passed" in proc.stdout
    runtime = _runtime_record(proc)
    runtime_paths = _runtime_paths(runtime)
    assert runner.GROUP6_SOURCE_PATH in runtime_paths
    assert runtime_paths == set(runner.SEALED_28_PINS) | {runner.GROUP6_SOURCE_PATH}


def test_group7_isolated_subprocess_success(root_path: Path) -> None:
    """A05: Group 7 actual historical tests execute in an isolated subprocess."""
    proc = runner.run_group7(root=root_path)
    assert proc.returncode == 0, f"Group 7 tests failed: {proc.stderr}\n{proc.stdout}"
    assert "24 passed" in proc.stdout
    runtime = _runtime_record(proc)
    runtime_paths = _runtime_paths(runtime)
    assert runner.GROUP7_SOURCE_PATH in runtime_paths
    assert runtime_paths == set(runner.SEALED_28_PINS)


def test_parent_process_pollution_isolation(root_path: Path) -> None:
    """A06: Extraneous research modules loaded in parent process do not affect child."""
    # Deliberately pollute parent sys.modules with conflicting research modules
    import importlib

    parent_module = "lottolab.research.b649_min_s2_t249_dual_profile_composition_r1"
    importlib.import_module(parent_module)

    assert parent_module in sys.modules, "Parent process should have Group 6 research module loaded"

    # In a shared single process, Group 7 would fail due to provenance() discovering Group 6.
    # In an isolated subprocess, Group 7 must pass cleanly.
    proc7 = runner.run_group7(root=root_path)
    assert proc7.returncode == 0, f"Group 7 failed under parent pollution: {proc7.stderr}"
    assert "24 passed" in proc7.stdout
    group7_paths = _runtime_paths(_runtime_record(proc7))
    assert runner.GROUP6_SOURCE_PATH not in group7_paths

    proc6 = runner.run_group6(root=root_path)
    assert proc6.returncode == 0, f"Group 6 failed under parent pollution: {proc6.stderr}"
    assert "27 passed" in proc6.stdout
    group6_paths = _runtime_paths(_runtime_record(proc6))
    assert runner.GROUP6_SOURCE_PATH in group6_paths


def test_order_independence(root_path: Path) -> None:
    """A09: Verify order independence across separate subprocess runs."""
    res_6_7 = runner.run_isolated_suite(order=("group6", "group7"), root=root_path)
    assert res_6_7["group6"].returncode == 0
    assert res_6_7["group7"].returncode == 0
    group6_first = _runtime_record(res_6_7["group6"])
    group7_second = _runtime_record(res_6_7["group7"])

    res_7_6 = runner.run_isolated_suite(order=("group7", "group6"), root=root_path)
    assert res_7_6["group7"].returncode == 0
    assert res_7_6["group6"].returncode == 0
    group7_first = _runtime_record(res_7_6["group7"])
    group6_second = _runtime_record(res_7_6["group6"])

    assert _runtime_paths(group6_first) == _runtime_paths(group6_second)
    assert _runtime_paths(group7_first) == _runtime_paths(group7_second)
    process_ids = {
        group6_first["process_id"],
        group7_second["process_id"],
        group7_first["process_id"],
        group6_second["process_id"],
    }
    assert len(process_ids) == 4


def test_subprocess_exit_status_fidelity_and_non_masking(root_path: Path) -> None:
    """A08/A09: Failures, errors, and invalid invocations are never masked as PASS."""
    bad_proc = runner.run_isolated_pytest(
        runner.GROUP6_TEST_PATH,
        extra_args=["--non-existent-pytest-option-for-fidelity-check"],
        cwd=root_path,
    )
    assert bad_proc.returncode != 0, "Runner masked invalid pytest option failure"
    bad_record = _runtime_record(bad_proc, require_modules=False)
    assert bad_record["pytest_exit_code"] == bad_proc.returncode

    failing_target_proc = runner.run_isolated_pytest(
        "tests/unit/non_existent_test_file_regression_r1.py",
        cwd=root_path,
    )
    assert failing_target_proc.returncode != 0, "Runner masked non-existent test file error"
    missing_record = _runtime_record(failing_target_proc, require_modules=False)
    assert missing_record["pytest_exit_code"] == failing_target_proc.returncode

    runner_code = runner.main(
        ["--order", "group6", "--non-existent-pytest-option-for-fidelity-check"]
    )
    assert runner_code != 0, "Runner CLI masked child pytest failure"


def test_negative_tamper_rejection(root_path: Path) -> None:
    """A07/A08: Real tamper cases are rejected by historical verifiers."""
    # Run historical negative tests in Group 7 that verify tamper rejection
    proc7_tamper = runner.run_group7(
        extra_args=["-k", "test_source_identity_tamper or test_frozen_result_tamper"],
        root=root_path,
    )
    assert proc7_tamper.returncode == 0, (
        f"Group 7 tamper tests failed: {proc7_tamper.stderr}\n{proc7_tamper.stdout}"
    )

    # Run historical negative tests in Group 6 that verify tamper rejection
    proc6_tamper = runner.run_group6(
        extra_args=[
            "-k",
            "test_source_hash_and_missing_donor_fail_closed or "
            "test_mutated_certificate_fails_closed",
        ],
        root=root_path,
    )
    assert proc6_tamper.returncode == 0, (
        f"Group 6 tamper tests failed: {proc6_tamper.stderr}\n{proc6_tamper.stdout}"
    )

    # Verify that an unhandled tampered source hash is genuinely rejected with non-zero exit
    tamper_code = (
        "from lottolab.research import b649_min_s2_t249_dual_profile_composition_r1 as c; "
        "c.local_blob('src/lottolab/research/b649_min_s2_two_tied_owner_exact_cert_r1.py', '0'*64)"
    )
    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = "src"
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"
    res = subprocess.run(
        [sys.executable, "-B", "-c", tamper_code],
        cwd=root_path,
        env=run_env,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, "Unhandled tamper was unexpectedly accepted"
    assert "source-hash mismatch" in res.stderr
