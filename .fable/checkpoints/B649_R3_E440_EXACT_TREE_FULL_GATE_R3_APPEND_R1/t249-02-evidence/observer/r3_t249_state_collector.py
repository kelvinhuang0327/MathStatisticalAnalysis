"""Observe parent-process OR-Tools imports during the T249 isolation pytest run."""
import importlib.abc
import json
import os
import sys
import time

TAG = os.environ.get("FABLE_R3_RUN_TAG", "unknown")
REPORT = os.environ.get("FABLE_R3_T249_PARENT_STATE_REPORT")
IMPORT_ATTEMPTS = []
SNAPSHOTS = []
NODE_IDS = []
REPORTS = []


def _solver_modules():
    return sorted(name for name in sys.modules if name == "ortools" or name.startswith("ortools."))


def _snapshot(stage):
    SNAPSHOTS.append({"stage": stage, "monotonic_ns": time.monotonic_ns(), "solver_modules": _solver_modules()})


class _OrtoolsImportAttemptObserver(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ortools" or fullname.startswith("ortools."):
            IMPORT_ATTEMPTS.append({"fullname": fullname, "monotonic_ns": time.monotonic_ns()})
        return None


_PREEXISTING = _solver_modules()
sys.meta_path.insert(0, _OrtoolsImportAttemptObserver())
_snapshot("collector_import")


def pytest_collection_finish(session):
    NODE_IDS[:] = [item.nodeid for item in session.items]
    _snapshot("collection_finish")


def pytest_runtest_logreport(report):
    REPORTS.append({"node_id": report.nodeid, "when": report.when, "outcome": report.outcome,
                    "wasxfail": getattr(report, "wasxfail", None)})
    if report.when in ("setup", "call", "teardown"):
        _snapshot("runtest_" + report.when + ":" + report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    del session
    _snapshot("session_finish")
    payload = {
        "schema_version": 1,
        "run_tag": TAG,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "pytest_exit_code": int(exitstatus),
        "collected_node_ids": NODE_IDS,
        "pytest_reports": REPORTS,
        "preexisting_solver_modules_at_collector_import": _PREEXISTING,
        "solver_modules_final": _solver_modules(),
        "solver_modules_observed_union": sorted({name for item in SNAPSHOTS for name in item["solver_modules"]}),
        "solver_import_attempts": IMPORT_ATTEMPTS,
        "state_snapshots": SNAPSHOTS,
        "report_path": REPORT,
    }
    if not REPORT:
        raise RuntimeError("FABLE_R3_T249_PARENT_STATE_REPORT is unset")
    fd = os.open(REPORT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
