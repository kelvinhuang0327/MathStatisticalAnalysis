from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from lottolab.application.use_cases.historical_draw_import import HistoricalDrawImportService
from lottolab.infrastructure.downloaded_draw_archive import DownloadedDrawArchiveParser
from lottolab.infrastructure.persistence.historical_draw_import_repository import (
    SQLiteHistoricalDrawImportRepository,
)
from lottolab.interfaces.api.app import create_app


def test_historical_import_api_supports_preview_commit_and_readback(tmp_path: Path) -> None:
    service = HistoricalDrawImportService(
        SQLiteHistoricalDrawImportRepository(tmp_path / "historical.db"),
        DownloadedDrawArchiveParser(),
    )
    client: Any = TestClient(create_app(historical_draw_import_service=service))
    csv = (
        "遊戲名稱,期別,開獎日期,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,第二區\n"
        "威力彩,1,2024/01/01,1,2,3,4,5,6,1\n"
    ).encode()
    request = {
        "files": [
            {
                "filename": "draws.csv",
                "content_base64": base64.b64encode(csv).decode("ascii"),
            }
        ],
        "lottery_filter": "POWER_LOTTO",
    }

    preview = client.post("/api/v1/historical-results/imports/preview", json=request)
    assert preview.status_code == 200
    assert preview.json()["status"] == "PREVIEW"
    assert preview.json()["summary"]["imported_rows"] == 0
    assert not (tmp_path / "historical.db").exists()

    committed = client.post("/api/v1/historical-results/imports", json=request)
    assert committed.status_code == 200
    payload = committed.json()
    assert payload["status"] == "COMPLETED"
    assert payload["summary"]["imported_rows"] == 1
    run_id = payload["run_id"]

    readback = client.get(f"/api/v1/historical-results/imports/{run_id}")
    assert readback.status_code == 200
    assert readback.json()["row_results"][0]["historical_run_id"]


def test_historical_import_api_is_explicitly_unconfigured_by_default() -> None:
    client: Any = TestClient(create_app())
    response = client.post(
        "/api/v1/historical-results/imports/preview",
        json={"files": [{"filename": "draws.csv", "content_base64": "YQ=="}]},
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "HISTORICAL_DRAW_IMPORT_NOT_CONFIGURED"
