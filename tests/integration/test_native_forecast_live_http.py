"""Exercise the native current route over HTTP against an isolated populated SQLite store."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from tests.unit.test_b649_native_forecast_api import (
    _snapshot,  # pyright: ignore[reportPrivateUsage]
)
from tests.unit.test_research_live_forecast import native as native


def test_native_current_success_over_real_http(native: Any) -> None:
    service, generate, captured = native
    run = generate("native-current-live-http-fixture")
    forecast = captured["native-current-live-http-fixture"]
    database = service.repository.paths.database
    before = _snapshot(database)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    env["LOTTOLAB_DATA_DIR"] = str(database.parent)
    env.pop("LOTTOLAB_REPLAY_BACKFILL_DB", None)
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "lottolab.interfaces.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 25
        while True:
            assert process.poll() is None, "fixture server exited before readiness"
            try:
                with urlopen(base + "/openapi.json", timeout=2) as response:
                    assert response.status == 200
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        query = urlencode(
            {"target_draw_number": forecast.scope[1], "target_draw_date": forecast.scope[2]}
        )
        with urlopen(base + "/api/b649/native-forecast/current?" + query, timeout=15) as response:
            assert response.status == 200
            body = json.load(response)
        assert body["scope"]["forecast_stream_id"] == "B649_NEXT_UNDRAWN_FORECAST"
        assert body["scope"]["forecast_stream_version"] == "B649_FULL_OFFICIAL_ANY_PRIZE_R1"
        assert body["request_identity"]["run_id"] == run.run_id
        assert body["payload"] == json.loads(forecast.payload_bytes)
        assert _snapshot(database) == before
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
