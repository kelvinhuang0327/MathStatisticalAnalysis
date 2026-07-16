"""Opt-in real lifecycle test for the two persistent localhost services."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lottolab.application.local_runtime import LocalRuntimePolicy, ServiceRole

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


def test_real_start_status_smoke_stop_lifecycle() -> None:
    if listening(8000) or listening(5173):
        pytest.skip("fixed local runtime port already has a listener")

    started = False
    policy = LocalRuntimePolicy.for_repository(ROOT)
    try:
        start = run_local("start")
        assert start.returncode == 0, start.stderr
        started = True
        assert "state=running" in start.stdout

        status = run_local("status")
        assert status.returncode == 0, status.stderr
        assert "ownership=verified" in status.stdout
        assert "revision_match=yes" in status.stdout

        smoke = run_local("smoke")
        assert smoke.returncode == 0, smoke.stderr
        assert "smoke=pass" in smoke.stdout
        assert "listeners=localhost-only" in smoke.stdout

        stop = run_local("stop")
        assert stop.returncode == 0, stop.stderr
        started = False
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
    finally:
        if started:
            run_local("stop")

    assert not listening(8000)
    assert not listening(5173)
