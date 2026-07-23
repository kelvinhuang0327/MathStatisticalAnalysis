"""Opt-in real lifecycle test for the two persistent localhost services."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
from pytest import MonkeyPatch
from tests.fixtures.historical.local_workspace_builder import (
    persist_local_workspace_source,
)

from lottolab.application.local_runtime import LocalRuntimePolicy, ServiceRole
from lottolab.interfaces.api.local_app import HISTORICAL_RESULTS_DB_ENV

ROOT = Path(__file__).resolve().parents[2]
RUN_REAL = os.environ.get("LOTTOLAB_RUN_LOCAL_RUNTIME_INTEGRATION") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_REAL,
    reason="set LOTTOLAB_RUN_LOCAL_RUNTIME_INTEGRATION=1 for the real service lifecycle",
)


def run_local(*arguments: str) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    assert uv is not None
    return subprocess.run(
        [uv, "run", "--no-sync", "lottolab", "local", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def listening(port: int) -> bool:
    lsof = shutil.which("lsof")
    assert lsof is not None
    completed = subprocess.run(
        [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return bool(completed.stdout.strip())


def json_get(path: str, params: dict[str, object] | None = None) -> tuple[int, dict[str, Any]]:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"http://127.0.0.1:8000{path}{query}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, cast(dict[str, Any], json.loads(response.read()))
    except HTTPError as error:
        return error.code, cast(dict[str, Any], json.loads(error.read()))


def _assert_started_and_smoke_passes() -> None:
    start = run_local("start")
    assert start.returncode == 0, start.stderr
    assert "state=running" in start.stdout

    status = run_local("status")
    assert status.returncode == 0, status.stderr
    assert "ownership=verified" in status.stdout
    assert "revision_match=yes" in status.stdout

    smoke = run_local("smoke")
    assert smoke.returncode == 0, smoke.stderr
    assert "smoke=pass" in smoke.stdout
    assert "listeners=localhost-only" in smoke.stdout


def _stop_and_assert_safe(policy: LocalRuntimePolicy) -> None:
    stop = run_local("stop")
    assert stop.returncode == 0, stop.stderr
    assert "state=stopped" in stop.stdout
    assert not policy.state_path.exists()
    for role in (ServiceRole.BACKEND, ServiceRole.FRONTEND):
        log_path = policy.log_path(role)
        assert log_path.is_file()
        assert log_path.stat().st_mode & 0o777 == 0o600

    final_status = run_local("status")
    assert final_status.returncode == 0, final_status.stderr
    assert "state=stopped" in final_status.stdout

    repeated_stop = run_local("stop")
    assert repeated_stop.returncode == 0, repeated_stop.stderr


def test_real_unconfigured_and_configured_start_status_smoke_stop_lifecycle(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    if listening(8000) or listening(5173):
        pytest.skip("fixed local runtime port already has a listener")

    started = False
    policy = LocalRuntimePolicy.for_repository(ROOT)
    try:
        monkeypatch.delenv(HISTORICAL_RESULTS_DB_ENV, raising=False)
        _assert_started_and_smoke_passes()
        started = True
        runs_status, runs_body = json_get("/api/v1/historical-results/runs")
        windows_status, windows_body = json_get(
            "/api/v1/historical-prefix-success-windows",
            {
                "import_identity_sha256": "a" * 64,
                "prefix_count": 1,
                "criterion": "M3_PLUS",
            },
        )
        matrix_status, matrix_body = json_get(
            (
                "/api/v1/historical-prefix-success-windows/strategies/"
                "strategy-a/v1/1/matrix"
            ),
            {"import_identity_sha256": "a" * 64},
        )
        assert runs_status == 503
        assert runs_body["error_code"] == "HISTORICAL_RESULTS_NOT_CONFIGURED"
        assert windows_status == 503
        assert windows_body["error_code"] == (
            "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED"
        )
        assert matrix_status == 503
        assert matrix_body["error_code"] == (
            "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED"
        )
        _stop_and_assert_safe(policy)
        started = False

        database = tmp_path / "historical.db"
        run_import, _commit = persist_local_workspace_source(database)
        database_before = database.read_bytes()
        sidecars_before = {path.name for path in tmp_path.glob("historical.db-*")}
        monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, str(database))
        _assert_started_and_smoke_passes()
        started = True
        configured_runs_status, configured_runs = json_get(
            "/api/v1/historical-results/runs"
        )
        assert configured_runs_status == 200
        assert configured_runs["items"][0]["import_identity_sha256"] == (
            run_import.import_identity_sha256
        )
        configured_windows_status, configured_windows = json_get(
            "/api/v1/historical-prefix-success-windows",
            {
                "import_identity_sha256": run_import.import_identity_sha256,
                "prefix_count": 1,
                "criterion": "M3_PLUS",
                "limit": 50,
                "offset": 0,
            },
        )
        assert configured_windows_status == 200
        assert configured_windows["metadata"]["import_identity_sha256"] == (
            run_import.import_identity_sha256
        )
        first_strategy = configured_windows["items"][0]["strategy"]
        configured_matrix_status, configured_matrix = json_get(
            (
                "/api/v1/historical-prefix-success-windows/strategies/"
                f"{first_strategy['strategy_id']}/{first_strategy['strategy_version']}/"
                f"{first_strategy['replicate']}/matrix"
            ),
            {"import_identity_sha256": run_import.import_identity_sha256},
        )
        assert configured_matrix_status == 200
        assert configured_matrix["cell_count"] == len(configured_matrix["cells"]) == 64
        assert database.read_bytes() == database_before
        assert {path.name for path in tmp_path.glob("historical.db-*")} == sidecars_before
        _stop_and_assert_safe(policy)
        started = False
    finally:
        if started:
            run_local("stop")

    assert not listening(8000)
    assert not listening(5173)
