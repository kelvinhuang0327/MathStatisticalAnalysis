"""Configured local composition from one task-owned SQLite database to both APIs."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from tests.fixtures.historical.local_workspace_builder import (
    persist_local_workspace_source,
)

from lottolab.interfaces.api.local_app import (
    HISTORICAL_RESULTS_DB_ENV,
    create_local_app,
)

RUNS_PATH = "/api/v1/historical-results/runs"
WINDOWS_PATH = "/api/v1/historical-prefix-success-windows"


@contextmanager
def _read_only(database: Path) -> Generator[sqlite3.Connection]:
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


def _database_inventory(database: Path) -> tuple[bytes, tuple[tuple[str, int], ...], set[str]]:
    with _read_only(database) as connection:
        tables = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
            if not str(row[0]).startswith("sqlite_")
        )
        counts = tuple(
            (table, int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]))
            for table in tables
        )
    sidecars = {path.name for path in database.parent.glob(f"{database.name}-*")}
    return database.read_bytes(), counts, sidecars


def _params(import_identity_sha256: str) -> dict[str, object]:
    return {
        "import_identity_sha256": import_identity_sha256,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }


def test_one_exact_configured_database_feeds_runs_list_windows_and_exact_strategy_read_only(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database = tmp_path / "historical.db"
    run_import, commit = persist_local_workspace_source(database)
    before = _database_inventory(database)
    monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, str(database))
    client = TestClient(create_local_app())

    runs = client.get(RUNS_PATH)
    assert runs.status_code == 200
    (run,) = runs.json()["items"]
    assert run["run_id"] == commit.run_id
    assert run["import_identity_sha256"] == run_import.import_identity_sha256
    assert run["dataset_identity"] == run_import.dataset.dataset_identity
    assert run["source_repository"] == run_import.source.source_repository
    assert run["source_commit_oid"] == run_import.source.source_commit_oid

    windows = client.get(WINDOWS_PATH, params=_params(run["import_identity_sha256"]))
    assert windows.status_code == 200
    payload = windows.json()
    assert payload["metadata"]["run_id"] == commit.run_id
    assert payload["metadata"]["import_identity_sha256"] == run_import.import_identity_sha256
    assert payload["total_count"] == len(run_import.strategy_descriptors)
    assert [item["strategy"]["strategy_id"] for item in payload["items"]] == [
        descriptor.strategy_id for descriptor in run_import.strategy_descriptors
    ]
    assert any(item["strategy"]["alias_of_strategy_id"] for item in payload["items"])
    assert any(item["strategy"]["replicate"] > 1 for item in payload["items"])
    assert any(item["source_observation_count"] == 0 for item in payload["items"])

    selected = payload["items"][1]["strategy"]
    exact = client.get(
        (
            f"{WINDOWS_PATH}/strategies/{selected['strategy_id']}/"
            f"{selected['strategy_version']}/{selected['replicate']}"
        ),
        params=_params(run["import_identity_sha256"]),
    )
    assert exact.status_code == 200
    assert exact.json()["strategy"] == selected
    assert exact.json()["prefix_count"] == 1
    assert exact.json()["criterion"]["criterion"] == "M3_PLUS"

    cohorts = client.get(
        (
            f"{WINDOWS_PATH}/strategies/{selected['strategy_id']}/"
            f"{selected['strategy_version']}/{selected['replicate']}/feature-cohorts"
        ),
        params=_params(run["import_identity_sha256"]),
    )
    assert cohorts.status_code == 200
    cohort_payload = cohorts.json()
    assert cohort_payload["strategy"] == selected
    assert cohort_payload["baseline"]["observation_count"] == (
        exact.json()["source_observation_count"]
    )
    assert cohort_payload["cohort_count"] == len(cohort_payload["cohorts"]) == 64
    assert sum(
        item["observation_count"] for item in cohort_payload["cohorts"]
    ) == cohort_payload["baseline"]["observation_count"]

    diagnostics = client.get(
        (
            f"{WINDOWS_PATH}/strategies/{selected['strategy_id']}/"
            f"{selected['strategy_version']}/{selected['replicate']}/"
            "feature-cohorts/diagnostics"
        ),
        params=_params(run["import_identity_sha256"]),
    )
    assert diagnostics.status_code == 200
    diagnostics_payload = diagnostics.json()
    assert diagnostics_payload["strategy"] == selected
    assert (
        diagnostics_payload["family_size"]
        == len(diagnostics_payload["diagnostics"])
        == 64
    )
    assert all(
        item["cohort_counts"]["observation_count"]
        + item["outside_counts"]["observation_count"]
        == diagnostics_payload["baseline"]["observation_count"]
        for item in diagnostics_payload["diagnostics"]
    )

    after = _database_inventory(database)
    assert after == before
    assert after[2] == set()


def test_corrupt_configured_database_is_sanitized_for_both_route_families(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database = tmp_path / "historical.db"
    database.write_bytes(b"not sqlite")
    monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, str(database))
    client = TestClient(create_local_app())

    runs = client.get(RUNS_PATH)
    windows = client.get(WINDOWS_PATH, params=_params("a" * 64))

    assert runs.status_code == 503
    assert windows.status_code == 503
    assert str(database) not in runs.text
    assert str(database) not in windows.text
