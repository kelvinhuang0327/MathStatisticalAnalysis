"""Regression checks verifying subprocess isolation for ortools in R14.

Guarantees:
- ortools is executed strictly inside an isolated subprocess.
- Parent pytest process never retains ortools modules in sys.modules.
- Adjacent legacy certificate tests requiring solver-free environments pass cleanly.
- Genuine solver loading is rejected by historical source_authority guards.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.unit.test_b649_k20_min_s2_successive_class_dominance_r14 import (
    run_isolated_feasible_solver_check,
    test_feasible_solver_status_uses_only_best_bound_floor,
)

from lottolab.research.b649_min_s2_owner_655555555555410_t238_exact_authority_r1 import (
    source_authority,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_t03_t04_r14_feasible_solver_isolates_ortools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T03 & T04: Test logic runs in subprocess; parent never retains ortools in sys.modules."""
    modules_before = set(sys.modules.keys())
    assert not any(m.startswith("ortools") for m in modules_before)

    test_feasible_solver_status_uses_only_best_bound_floor(monkeypatch)

    modules_after = set(sys.modules.keys())
    new_ortools = [m for m in modules_after if m.startswith("ortools")]
    assert new_ortools == [], f"ortools leaked into parent process: {new_ortools}"
    assert not any(m.startswith("ortools") for m in sys.modules)


def test_t02_r14_feasible_solver_payload_and_semantics() -> None:
    """T02: Verify FeasibleSolver monkeypatch semantics and floor bound calculation."""
    relaxation = run_isolated_feasible_solver_check()
    assert relaxation["SOLVER_STATUS"] == "FEASIBLE"
    assert relaxation["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"] == 7
    assert isinstance(relaxation.get("SOLVER_WALL_TIME_SECONDS"), (int, float))
    assert isinstance(relaxation.get("DEGREE_CLASSES"), list)


def test_t05_adjacent_historical_source_authority_passes_after_r14(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T05: In the same process, running R14 does not pollute legacy solver-loaded guard."""
    assert not any(m.startswith("ortools") for m in sys.modules)

    test_feasible_solver_status_uses_only_best_bound_floor(monkeypatch)

    assert not any(m.startswith("ortools") for m in sys.modules)

    provenance = source_authority()
    assert provenance["BASE_HEAD"] == "2bdf3a6843800b1a1c818bd4e168585a7971611a"
    assert "SOURCE_PINS" in provenance
    assert not any(m.startswith("ortools") for m in sys.modules)


def test_t06_negative_genuine_solver_loaded_is_rejected_by_legacy_guard() -> None:
    """T06: When ortools is genuinely loaded, legacy source_authority raises ValueError."""
    child_code = """
import importlib
import json
import sys

# Genuinely import ortools
importlib.import_module("ortools.sat.python.cp_model")
assert any(m.startswith("ortools") for m in sys.modules)

from lottolab.research.b649_min_s2_owner_655555555555410_t238_exact_authority_r1 import (
    source_authority,
)

try:
    source_authority()
    result = {"status": "UNEXPECTED_PASS"}
except ValueError as exc:
    result = {"status": "REJECTED_AS_EXPECTED", "error": str(exc)}
except Exception as exc:
    result = {"status": "UNEXPECTED_EXCEPTION", "error": str(exc)}

print(json.dumps(result))
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPOSITORY_ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, f"Probe child failed: {completed.stderr}"
    output = json.loads(completed.stdout.strip().splitlines()[-1])
    assert output["status"] == "REJECTED_AS_EXPECTED"
    assert "solver loaded" in output.get("error", "")
    assert not any(m.startswith("ortools") for m in sys.modules)
