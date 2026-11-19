"""Focused contract and SQLite v6 runtime tests for the Native B649 current forecast API."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# Starlette TestClient is partially untyped under the httpx compatibility shim.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.unit.test_research_live_forecast import native as native

from lottolab.infrastructure.persistence.research_repository import SQLiteResearchRepository
from lottolab.infrastructure.persistence.research_schema import ResearchDataPaths
from lottolab.interfaces.api.app import create_app

PATH = "/api/b649/native-forecast/current"
TABLES = ("research_live_forecast_versions", "research_live_forecast_current_pointer")


def _snapshot(database: Path) -> dict[str, tuple[int, str]]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, isolation_level=None)
    try:
        connection.execute("BEGIN")
        result: dict[str, tuple[int, str]] = {}
        for table in TABLES:
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            row_digest = hashlib.sha256()
            for row in rows:
                values = [value.hex() if isinstance(value, bytes) else value for value in row]
                row_digest.update(
                    json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
                )
                row_digest.update(b"\n")
            result[table] = (len(rows), row_digest.hexdigest())
        connection.execute("COMMIT")
        return result
    finally:
        connection.close()


def _reader_result(database: Path, scope: tuple[str, str, str, str, str]) -> Any:
    paths = ResearchDataPaths(database.parent, database)
    result = SQLiteResearchRepository(paths, initialize=False).read_current_native(scope)
    assert result is not None
    return result


def _client(database_directory: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(database_directory))
    monkeypatch.delenv("LOTTOLAB_REPLAY_BACKFILL_DB", raising=False)
    return TestClient(create_app())


def test_http_current_valid_missing_invalid_repeatable_and_read_only(
    native: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, generate, captured = native
    generated = generate("adopted-native-current-http-v1")
    forecast = captured["adopted-native-current-http-v1"]
    database = service.repository.paths.database
    scope = forecast.scope
    expected = _reader_result(database, scope)
    before = _snapshot(database)

    client = _client(database.parent, monkeypatch)
    params = {"target_draw_number": scope[1], "target_draw_date": scope[2]}
    first = client.get(PATH, params=params)
    second = client.get(PATH, params=params)
    override = client.get(
        PATH,
        params={
            **params,
            "forecast_stream_id": "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS",
            "forecast_stream_version": "1.0.0",
        },
    )

    assert first.status_code == second.status_code == override.status_code == 200
    assert first.json() == second.json() == override.json()
    body = first.json()
    assert body["scope"] == {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": scope[1],
        "target_draw_date": scope[2],
        "forecast_stream_id": "B649_NEXT_UNDRAWN_FORECAST",
        "forecast_stream_version": "B649_FULL_OFFICIAL_ANY_PRIZE_R1",
    }
    assert body["request_identity"] == {
        "request_id": expected.request_id,
        "request_sha256": expected.request_sha256,
        "version": expected.version,
        "run_id": expected.run_id,
        "payload_sha256": expected.payload_sha256,
        "generation_started_at": expected.forecast.original["generation_started_at"],
        "generation_finished_at": expected.forecast.original["generation_finished_at"],
        "committed_at": expected.committed_at,
    }
    assert (
        body["payload"] == json.loads(expected.payload_bytes) == json.loads(forecast.payload_bytes)
    )
    assert (
        body["request_identity"]["generation_started_at"]
        == expected.forecast.original["generation_started_at"]
    )
    assert (
        body["request_identity"]["generation_finished_at"]
        == expected.forecast.original["generation_finished_at"]
    )
    assert "issued_at" not in body and "is_undrawn" not in body

    missing = client.get(
        PATH, params={"target_draw_number": "115000088", "target_draw_date": "2026-09-12"}
    )
    assert missing.status_code == 404
    assert missing.json() == {
        "error_code": "B649_NATIVE_CURRENT_NOT_FOUND",
        "message": "The requested Native current forecast was not found.",
    }

    invalid_requests = (
        {"target_draw_number": "11500008x", "target_draw_date": scope[2]},
        {"target_draw_number": scope[1], "target_draw_date": "2026-02-30"},
        {"target_draw_number": scope[1]},
        {"target_draw_number": "11500008", "target_draw_date": scope[2]},
    )
    for invalid in invalid_requests:
        assert client.get(PATH, params=invalid).status_code == 422
    assert _snapshot(database) == before
    assert generated.run_id == expected.run_id


@pytest.mark.parametrize("corruption", ("payload", "envelope", "pointer_stream"))
def test_integrity_or_wrong_stream_is_sanitized_non_success(
    corruption: str,
    native: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, generate, captured = native
    generated = generate(f"adopted-native-current-http-{corruption}")
    forecast = captured[f"adopted-native-current-http-{corruption}"]
    database = service.repository.paths.database
    scope = forecast.scope

    directory = tmp_path / "corrupt_fixtures" / corruption
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    copied = directory / database.name
    shutil.copy2(database, copied)
    os.chmod(copied, stat.S_IRUSR | stat.S_IWUSR)

    connection = sqlite3.connect(copied)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        triggers = connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type='trigger' AND tbl_name IN (?, ?)",
            TABLES,
        ).fetchall()
        for name, _statement in triggers:
            escaped = str(name).replace('"', '""')
            connection.execute(f'DROP TRIGGER "{escaped}"')
        if corruption == "payload":
            connection.execute(
                "UPDATE research_live_forecast_versions SET payload_bytes=? WHERE run_id=?",
                (b"{}", generated.run_id),
            )
        elif corruption == "envelope":
            connection.execute(
                "UPDATE research_live_forecast_versions "
                "SET provenance_envelope_json=? WHERE run_id=?",
                ("{}", generated.run_id),
            )
        else:
            connection.execute(
                "UPDATE research_live_forecast_current_pointer "
                "SET forecast_stream_id=?, forecast_stream_version=? "
                "WHERE lottery_type=? AND target_draw_number=? AND target_draw_date=?",
                (
                    "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS",
                    "1.0.0",
                    scope[0],
                    scope[1],
                    scope[2],
                ),
            )
        for _name, statement in triggers:
            assert statement is not None
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()

    response = _client(directory, monkeypatch).get(
        PATH, params={"target_draw_number": scope[1], "target_draw_date": scope[2]}
    )
    assert response.status_code in {404, 409, 503} and response.status_code != 200
    assert str(directory) not in response.text
    lowered = response.text.casefold()
    assert "sqlite" not in lowered and "select " not in lowered and "traceback" not in lowered
    if corruption in {"payload", "envelope"}:
        assert response.status_code == 409
        assert response.json() == {
            "error_code": "B649_NATIVE_CURRENT_INTEGRITY_CONFLICT",
            "message": "The Native current forecast failed integrity validation.",
        }
    else:
        assert response.status_code in {404, 503}
