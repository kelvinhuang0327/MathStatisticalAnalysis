# pyright: reportPrivateUsage=false
"""Focused isolation, source-rejection, and subprocess-contract checks for T249."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
import test_b649_min_s2_t249_dual_profile_composition_r1 as t249
from _pytest.reports import TestReport

from lottolab.research import b649_min_s2_t249_dual_profile_composition_r1 as c

_PRELOAD_MODULE = "lottolab.research.b649_min_s2_advanced_11row_exact_adoption_r1"
_PRELOAD_SOURCE = "src/lottolab/research/b649_min_s2_advanced_11row_exact_adoption_r1.py"
_PRELOAD_ENV = "B649_T249_PRELOAD_PARENT_RESEARCH"
_REVERSE_ENV = "B649_T249_REVERSE_ORDER"
_REPORT_PATH_ENV = "B649_T249_CHILD_REPORT_PATH"
_CHILD_NODE_IDS: list[str] = []
_CHILD_OUTCOMES: dict[str, dict[str, object]] = {}
parent_closure_diagnostic: dict[str, object] | None = None


def _capture_parent_preload() -> dict[str, object]:
    global parent_closure_diagnostic
    importlib.import_module(_PRELOAD_MODULE)
    expected = t249._sealed_source_paths()
    actual = t249.research_source_paths()
    diagnostic: dict[str, object] = {
        "expected_pin_count": len(expected),
        "preloaded_module": _PRELOAD_MODULE,
        "extra": sorted(actual - expected),
        "missing": sorted(expected - actual),
    }
    assert diagnostic["extra"] == [_PRELOAD_SOURCE]
    assert diagnostic["missing"] == []
    parent_closure_diagnostic = diagnostic
    print("T249_PARENT_CLOSURE_DIAGNOSTIC=" + json.dumps(diagnostic, sort_keys=True))
    return diagnostic


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    del session, config
    if os.environ.get(_PRELOAD_ENV) == "1":
        _capture_parent_preload()
        preload_items = [
            item
            for item in items
            if item.nodeid.endswith("::test_parent_preload_closure_difference_is_rejected")
        ]
        if preload_items:
            items[:] = preload_items + [item for item in items if item not in preload_items]

    target_items = [
        item for item in items if item.nodeid.startswith(f"{t249._TEST_PATH}::")
    ]
    if os.environ.get(_REVERSE_ENV) == "1" and target_items:
        other_items = [item for item in items if item not in target_items]
        items[:] = [*reversed(target_items), *other_items]
        print(
            "T249_REVERSE_NODE_ORDER="
            + json.dumps([item.nodeid for item in reversed(target_items)])
        )

    if target_items:
        _CHILD_NODE_IDS[:] = [item.nodeid for item in items if item in target_items]


def pytest_runtest_logreport(report: TestReport) -> None:
    nodeid = report.nodeid
    when = report.when
    outcome = report.outcome
    if not nodeid.startswith(f"{t249._TEST_PATH}::"):
        return
    if when != "call" and outcome == "passed":
        return
    _CHILD_OUTCOMES[nodeid] = {
        "outcome": outcome,
        "wasxfail": getattr(report, "wasxfail", None),
        "longrepr": str(getattr(report, "longrepr", "")) if outcome != "passed" else "",
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del session
    report_path = os.environ.get(_REPORT_PATH_ENV)
    if report_path is None:
        return
    solver_modules = sorted(
        name for name in sys.modules if name == "ortools" or name.startswith("ortools.")
    )
    payload: dict[str, Any] = {
        "collected_node_ids": _CHILD_NODE_IDS,
        "outcomes": _CHILD_OUTCOMES,
        "solver_modules": solver_modules,
        "pytest_exit_code": exitstatus,
    }
    Path(report_path).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_parent_preload_closure_difference_is_rejected() -> None:
    diagnostic = parent_closure_diagnostic or _capture_parent_preload()
    assert diagnostic["expected_pin_count"] == 28
    assert diagnostic["extra"] == [_PRELOAD_SOURCE]
    assert diagnostic["missing"] == []

    base = json.loads(c.local_blob(c.BASE_RESULT, c.BASE_RESULT_SHA))
    with pytest.raises(AssertionError, match="loaded research source closure differs"):
        c.source_pins(base)


def test_wrong_source_sha_blob_and_result_are_rejected() -> None:
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.local_blob(c.SOURCE, "0" * 64)
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.blob(c.BASE_HEAD, c.BASE_RESULT, "0" * 64)
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.local_blob(f"{c.SOURCES}/donor-result.json", "0" * 64)


def test_real_solver_loaded_guard_rejects_without_running_solver() -> None:
    task_root = t249._task_temp_root()
    child_tmp = task_root / "tmp"
    if not child_tmp.exists():
        t249._private_directory(child_tmp)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(c.ROOT / "src")
    env["TMPDIR"] = str(child_tmp)
    env["XDG_CACHE_HOME"] = str(task_root / "app-data")
    env["XDG_DATA_HOME"] = str(task_root / "app-data")
    program = "\n".join(
        (
            "import json",
            "import sys",
            "import ortools",
            "from lottolab.research import b649_min_s2_t249_dual_profile_composition_r1 as c",
            "base = json.loads((c.ROOT / c.BASE_RESULT).read_bytes())",
            "assert any(name == 'ortools' or name.startswith('ortools.') for name in sys.modules)",
            "try:",
            "    c.source_pins(base)",
            "except AssertionError as error:",
            "    assert str(error) == 'solver loaded'",
            "    print('T249_SOLVER_GUARD_REJECTED=solver loaded')",
            "else:",
            "    raise AssertionError('source_pins accepted an imported OR-Tools package')",
        )
    )
    result = t249._run_bounded_subprocess(
        [sys.executable, "-c", program], c.ROOT, env, timeout_seconds=30
    )
    t249._assert_child_success(result)
    assert "T249_SOLVER_GUARD_REJECTED=solver loaded" in result.stdout


def test_subprocess_exit_timeout_and_stderr_are_not_hidden() -> None:
    env = os.environ.copy()
    failed = t249._run_bounded_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('expected-child-stderr', file=sys.stderr); sys.exit(17)",
        ],
        c.ROOT,
        env,
        timeout_seconds=5,
    )
    with pytest.raises(AssertionError, match="exit=17") as failed_error:
        t249._assert_child_success(failed)
    assert "expected-child-stderr" in str(failed_error.value)

    stderr_only = t249._run_bounded_subprocess(
        [sys.executable, "-c", "import sys; print('expected-child-stderr', file=sys.stderr)"],
        c.ROOT,
        env,
        timeout_seconds=5,
    )
    with pytest.raises(AssertionError, match="unexpected stderr") as stderr_error:
        t249._assert_child_success(stderr_only)
    assert "expected-child-stderr" in str(stderr_error.value)

    with pytest.raises(AssertionError, match="timed out") as timeout_error:
        t249._run_bounded_subprocess(
            [
                sys.executable,
                "-c",
                "import time; print('expected-timeout-output', flush=True); time.sleep(5)",
            ],
            c.ROOT,
            env,
            timeout_seconds=0.5,
        )
    assert "expected-timeout-output" in str(timeout_error.value)
