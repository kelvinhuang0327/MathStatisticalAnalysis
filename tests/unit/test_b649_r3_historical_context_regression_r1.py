"""Regression checks for exact historical Git context and R14 import isolation."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_advanced_11row_exact_adoption_r1 as v

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OBJECT_REPOSITORY = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
TEST_TEMP_ROOT = Path("/private/tmp/mathstat-b649-r3-exact-candidate-context-compat-r1")
HISTORICAL_PARENT = "69d2d3fe2696623d75e876e5cd96085297da821c"
HISTORICAL_CHILD = "b280d90be0c35b8c5b1ca7798a394332194f8887"
CANDIDATE_BASE = "3033009550d35023d6d33171c27adc70fbb3af0a"
PARENT_ERROR = "candidate is not Base or its single local child"
TIED_OWNER_SOURCE_PIN_TEST_ID = (
    "tests/unit/test_b649_min_s2_two_tied_owner_exact_cert_r1.py::test_exact_source_pins"
)
HISTORICAL_CONTEXT_TEST_IDS = (
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_analytic_step5_certificate",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_split_identity_bounds_and_coverage_on_realizations[STEP_3]",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_split_identity_bounds_and_coverage_on_realizations[STEP_4]",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_identities_judges_and_original_dispositions",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_selection_is_derived_and_weaker_values_rejected",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_actual_sources_and_nonregression_vs_641173",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_relaxation_domains_recounted_against_donor_evidence",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_every_load_bearing_envelope_and_rounding",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_t264_only_floors_and_universal_cap_separation",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_negative_cap_swap_scope_leakage_and_rounding",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_negative_ledger_mutations",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_family_replay",
    "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_incorrect_source_sha_or_tree_rejected",
    "tests/unit/test_b649_min_s2_owner_ab_exact_family_composition_r1.py::test_wrong_source_identity_rejected",
    "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py::test_reject_incorrect_source_identity[head]",
    "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py::test_reject_incorrect_source_identity[tree]",
    "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py::test_reject_incorrect_source_identity[result]",
    "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py::test_reject_incorrect_source_identity[source]",
    "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py::test_reject_incorrect_source_identity[judge]",
    "tests/unit/test_b649_min_s2_two_bonf5_owners_exact_composition_r1.py::test_rejects_cursor_mutation[SOURCE_IDENTITY]",
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _assert_subprocess_success(
    completed: subprocess.CompletedProcess[str], purpose: str
) -> None:
    assert completed.returncode == 0, (
        f"{purpose} returned {completed.returncode}:\n"
        f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )


@pytest.fixture(scope="session")
def historical_context_worktrees() -> Iterator[dict[str, Path]]:
    if TEST_TEMP_ROOT.is_symlink():
        raise AssertionError(f"Task temporary root must not be a symlink: {TEST_TEMP_ROOT}")
    TEST_TEMP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if TEST_TEMP_ROOT.stat().st_mode & 0o777 != 0o700:
        raise AssertionError(f"Task temporary root must be mode 0700: {TEST_TEMP_ROOT}")

    with tempfile.TemporaryDirectory(
        prefix="historical-context-", dir=TEST_TEMP_ROOT
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        roots = {
            "historical_child": temporary_root / "historical-child",
            "candidate_base": temporary_root / "candidate-base",
        }
        for name, commit in (
            ("historical_child", HISTORICAL_CHILD),
            ("candidate_base", CANDIDATE_BASE),
        ):
            completed = subprocess.run(
                [
                    "git",
                    "clone",
                    "--no-hardlinks",
                    "--no-checkout",
                    str(OBJECT_REPOSITORY),
                    str(roots[name]),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            assert completed.returncode == 0, completed.stderr
            assert not (roots[name] / ".git/objects/info/alternates").exists()
            completed = subprocess.run(
                ["git", "-C", str(roots[name]), "checkout", "--detach", commit],
                capture_output=True,
                check=False,
                text=True,
            )
            assert completed.returncode == 0, completed.stderr

        assert _git(roots["historical_child"], "rev-parse", "HEAD") == HISTORICAL_CHILD
        assert _git(roots["historical_child"], "rev-parse", "HEAD^") == HISTORICAL_PARENT
        assert _git(roots["candidate_base"], "rev-parse", "HEAD") == CANDIDATE_BASE
        yield roots


def test_certified_historical_child_is_accepted(
    historical_context_worktrees: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v, "ROOT", historical_context_worktrees["historical_child"])
    v.verify_candidate()


def test_candidate_with_wrong_historical_parent_is_rejected(
    historical_context_worktrees: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v, "ROOT", historical_context_worktrees["candidate_base"])
    assert _git(v.ROOT, "rev-parse", "HEAD^") != HISTORICAL_PARENT

    with pytest.raises(ValueError, match=PARENT_ERROR):
        v.verify_candidate()


def test_historical_source_test_and_result_blobs_match_candidate_base(
    historical_context_worktrees: dict[str, Path],
) -> None:
    historical_root = historical_context_worktrees["historical_child"]
    candidate_root = historical_context_worktrees["candidate_base"]
    loaded_source = Path(v.__file__).read_bytes()
    pinned_source = subprocess.run(
        ["git", "-C", str(historical_root), "show", f"{HISTORICAL_CHILD}:{v.SOURCE}"],
        capture_output=True,
        check=True,
    ).stdout
    assert loaded_source == pinned_source

    for relative_path in (v.SOURCE, v.TEST, v.RESULT):
        historical_blob = _git(
            historical_root, "rev-parse", f"{HISTORICAL_CHILD}:{relative_path}"
        )
        candidate_blob = _git(
            candidate_root, "rev-parse", f"{CANDIDATE_BASE}:{relative_path}"
        )
        assert historical_blob == candidate_blob


def test_historical_identity_cases_run_at_the_certified_child(
    historical_context_worktrees: dict[str, Path],
) -> None:
    historical_root = historical_context_worktrees["historical_child"]
    env = {
        **os.environ,
        "PYTHONPATH": str(historical_root / "src")
        + os.pathsep
        + str(historical_root),
        "TMPDIR": str(TEST_TEMP_ROOT),
    }
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(
        prefix="historical-pytest-", dir=TEST_TEMP_ROOT
    ) as pytest_temp:
        env["PYTHONPYCACHEPREFIX"] = str(Path(pytest_temp) / "pycache")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--basetemp={Path(pytest_temp) / 'basetemp'}",
                "-o",
                f"cache_dir={Path(pytest_temp) / 'pytest-cache'}",
                *HISTORICAL_CONTEXT_TEST_IDS,
            ],
            cwd=historical_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    _assert_subprocess_success(completed, "Certified historical-context tests")
    assert "20 passed" in completed.stdout
    print(completed.stdout)


def test_tied_owner_source_pin_check_runs_in_an_independent_process(
    historical_context_worktrees: dict[str, Path],
) -> None:
    historical_root = historical_context_worktrees["historical_child"]
    env = {
        **os.environ,
        "PYTHONPATH": str(historical_root / "src")
        + os.pathsep
        + str(historical_root),
        "TMPDIR": str(TEST_TEMP_ROOT),
    }
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(
        prefix="historical-pytest-", dir=TEST_TEMP_ROOT
    ) as pytest_temp:
        env["PYTHONPYCACHEPREFIX"] = str(Path(pytest_temp) / "pycache")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--basetemp={Path(pytest_temp) / 'basetemp'}",
                "-o",
                f"cache_dir={Path(pytest_temp) / 'pytest-cache'}",
                TIED_OWNER_SOURCE_PIN_TEST_ID,
            ],
            cwd=historical_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    _assert_subprocess_success(completed, "Isolated historical source-pin test")
    assert "1 passed" in completed.stdout
    print(completed.stdout)


def test_r14_does_not_misattribute_preloaded_ortools_in_an_independent_process() -> None:
    child_code = """
import importlib
import sys

importlib.import_module("ortools.sat.python.cp_model")
assert any(name.startswith("ortools") for name in sys.modules)

from tests.unit.test_b649_k20_min_s2_successive_class_dominance_r14 import (
    test_feasible_solver_status_uses_only_best_bound_floor,
)

test_feasible_solver_status_uses_only_best_bound_floor(None)
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPOSITORY_ROOT)
        + os.pathsep
        + str(REPOSITORY_ROOT / "src")
        + os.pathsep
        + os.environ.get("PYTHONPATH", ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    _assert_subprocess_success(completed, "Preloaded OR-Tools child test")


def test_nonzero_subprocess_cannot_be_accepted_as_pass() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "raise SystemExit(17)"],
        capture_output=True,
        check=False,
        text=True,
    )
    with pytest.raises(AssertionError, match="returned 17"):
        _assert_subprocess_success(completed, "intentional child failure")
