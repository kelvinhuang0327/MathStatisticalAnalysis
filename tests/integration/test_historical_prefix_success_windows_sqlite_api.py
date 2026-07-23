"""End-to-end SQLite-to-HTTP tests for Historical Prefix success windows."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    TARGET_DRAW_NUMBER,
    TARGET_MAIN_NUMBERS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_envelope,
    build_portfolio,
    build_tickets,
    envelope_bytes,
)

from lottolab.domain.historical_results import HistoricalRunImport
from lottolab.infrastructure.persistence.historical_prefix_success_window_reader import (
    SQLiteHistoricalPrefixSuccessWindowSourceReader,
)
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultRepository,
)
from lottolab.interfaces.api.app import create_app
from lottolab.normalization.historical_import import (
    verify_and_normalize_historical_import,
)

LIST_PATH = "/api/v1/historical-prefix-success-windows"


def _persist_valid_source(database: Path) -> HistoricalRunImport:
    baseline = build_baseline_envelope()
    target_special = (49,)
    envelope: dict[str, Any] = build_envelope(
        strategy_descriptors=baseline["strategy_descriptors"],
        draw_snapshots=[
            build_draw_snapshot(
                draw_number=CUTOFF_DRAW_NUMBER,
                draw_date="2026-01-01",
                main_numbers=CUTOFF_MAIN_NUMBERS,
                special_numbers=CUTOFF_SPECIAL_NUMBERS,
            ),
            build_draw_snapshot(
                draw_number=TARGET_DRAW_NUMBER,
                draw_date="2026-01-10",
                main_numbers=TARGET_MAIN_NUMBERS,
                special_numbers=target_special,
            ),
        ],
        portfolios=[
            build_portfolio(
                strategy_id=str(descriptor["strategy_id"]),
                strategy_version=str(descriptor["strategy_version"]),
                replicate=int(descriptor["replicate"]),
                tickets=build_tickets(
                    target_main=TARGET_MAIN_NUMBERS,
                    target_special=target_special,
                ),
            )
            for descriptor in baseline["strategy_descriptors"]
        ],
    )
    verified = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert verified.normalized_import is not None
    SQLiteHistoricalResultRepository(database).commit_import(verified.normalized_import)
    return verified.normalized_import


def _client(database: Path) -> TestClient:
    return TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=lambda: (
                SQLiteHistoricalPrefixSuccessWindowSourceReader(database)
            )
        )
    )


def _params(import_identity_sha256: str) -> dict[str, object]:
    return {
        "import_identity_sha256": import_identity_sha256,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }


def test_exact_persisted_import_flows_read_only_from_sqlite_to_both_http_routes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist_valid_source(database)
    before = database.read_bytes()
    client = _client(database)

    page_response = client.get(
        LIST_PATH,
        params=_params(run_import.import_identity_sha256),
    )
    exact_response = client.get(
        f"{LIST_PATH}/strategies/SYNTHETIC_ALIAS_B/v1/1",
        params=_params(run_import.import_identity_sha256),
    )

    assert page_response.status_code == 200
    assert exact_response.status_code == 200
    assert page_response.json()["total_count"] == len(run_import.strategy_descriptors)
    assert [
        item["strategy"]["strategy_id"] for item in page_response.json()["items"]
    ] == [item.strategy_id for item in run_import.strategy_descriptors]
    assert exact_response.json()["strategy"]["strategy_id"] == "SYNTHETIC_ALIAS_B"
    assert exact_response.json()["selection"]["strategy_id"] == "SYNTHETIC_ALIAS_B"
    assert exact_response.json()["source_observation_count"] == 1
    assert database.read_bytes() == before
    assert not list(tmp_path.glob("historical.db-*"))
    assert not list(tmp_path.glob("historical.db-journal"))


def test_absent_exact_import_is_404_without_latest_fallback(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist_valid_source(database)

    response = _client(database).get(LIST_PATH, params=_params("f" * 64))

    assert response.status_code == 404
    assert response.json()["error_code"] == "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"
    assert run_import.import_identity_sha256 != "f" * 64


def test_corrupt_persisted_state_maps_to_sanitized_503(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist_valid_source(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE historical_ticket SET ticket_sha256 = ? WHERE id = 1",
            ("f" * 64,),
        )
        connection.commit()

    response = _client(database).get(
        LIST_PATH,
        params=_params(run_import.import_identity_sha256),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE",
        "message": "Historical prefix success windows are unavailable.",
    }
