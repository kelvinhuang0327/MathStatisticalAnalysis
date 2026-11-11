"""HTTP checks for the read-only sealed-084 research replay projection."""

# These tests verify archive integrity by deliberately inspecting and mutating
# the module-private source registry and sealed manifest constants.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pytest
from fastapi.testclient import TestClient

import lottolab.interfaces.api.b649_sealed084_replays as sealed084_api
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import (
    B649_SEALED084_REPLAY_SOURCE_ROOT_ENV,
    create_local_app,
)


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...

SOURCE_ROOT = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102")
ARCHIVE_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
    "B649_SEALED084_REPLAY_ARCHIVE_V1"
)
API_PATH = "/api/v1/b649/sealed-084-replays"
STATUS_PATH = f"{API_PATH}/status"
TASKS = (
    "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1",
)
STRATEGY_TICKET_COUNTS = {
    "research_causal_renewal_hazard_k2": 2,
    "research_causal_renewal_hazard_k3": 3,
    "research_causal_renewal_hazard_k5": 5,
    "research_conditional_transfer_entropy_k2": 2,
    "research_conditional_transfer_entropy_k3": 3,
    "research_conditional_transfer_entropy_k5": 5,
    "b649_new_horizon_minimax_disagreement_r1": 2,
}


def _local_client(monkeypatch: pytest.MonkeyPatch, source_root: Path | None) -> JsonTestClient:
    monkeypatch.delenv(B649_SEALED084_REPLAY_SOURCE_ROOT_ENV, raising=False)
    if source_root is not None:
        monkeypatch.setenv(B649_SEALED084_REPLAY_SOURCE_ROOT_ENV, str(source_root))
    return cast(JsonTestClient, TestClient(create_local_app()))


def _csv_rows() -> dict[tuple[str, str, int, str], dict[str, str]]:
    expected: dict[tuple[str, str, int, str], dict[str, str]] = {}
    for task_id in TASKS:
        source_dir = SOURCE_ROOT / task_id
        receipt: dict[str, Any] = json.loads(
            (source_dir / "result.json").read_text(encoding="utf-8")
        )
        generator: dict[str, Any] = receipt.get("generator_identity") or {}
        with (source_dir / "four_window_results.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            for csv_row in csv.DictReader(stream):
                strategy_id: str = csv_row.get("strategy_id") or generator["strategy_id"]
                version: str = (
                    csv_row.get("strategy_version")
                    or csv_row.get("version")
                    or generator["version"]
                )
                ticket_count: int = int(
                    csv_row.get("ticket_count") or generator["native_k"]
                )
                key: tuple[str, str, int, str] = (
                    strategy_id,
                    version,
                    ticket_count,
                    csv_row["window"],
                )
                expected[key] = csv_row
    return expected


def _copy_archive(destination: Path) -> Path:
    archive_root = destination / "archive"
    shutil.copytree(ARCHIVE_ROOT, archive_root)
    return archive_root


def _archive_skeleton(
    destination: Path,
    materialized_paths: tuple[str, ...] = (),
    missing_paths: tuple[str, ...] = (),
) -> Path:
    archive_root = destination / "archive"
    archive_root.mkdir()
    manifest_bytes = (ARCHIVE_ROOT / "archive_manifest.json").read_bytes()
    (archive_root / "archive_manifest.json").write_bytes(manifest_bytes)
    manifest = json.loads(manifest_bytes)
    for row in manifest["archived_files"]:
        relative_path = row["archive_relative_path"]
        target = archive_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative_path in missing_paths:
            continue
        if relative_path in materialized_paths:
            shutil.copy2(ARCHIVE_ROOT / relative_path, target)
        else:
            with target.open("wb") as stream:
                stream.truncate(row["byte_size"])
    return archive_root


def _reseal_archive_fixture(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    task_id: str,
    artifact_name: str,
) -> None:
    manifest_path = archive_root / sealed084_api._ARCHIVE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = next(row for row in manifest["source_tasks"] if row["task_id"] == task_id)
    archive_path = f"{source['archive_subdirectory']}/{artifact_name}"
    artifact_path = archive_root / archive_path
    artifact_bytes = artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    row = next(
        item
        for item in manifest["archived_files"]
        if item["source_task_id"] == task_id and item["relative_source_path"] == artifact_name
    )
    row["sha256"] = artifact_sha256
    row["byte_size"] = len(artifact_bytes)
    for parity in manifest["source_sha_parity"]:
        if parity["source_group"] == source["source_group"] and parity["name"] == artifact_name:
            parity["expected_sha256"] = artifact_sha256
            parity["actual_sha256"] = artifact_sha256
            parity["expected_byte_size"] = len(artifact_bytes)
            parity["actual_byte_size"] = len(artifact_bytes)
            parity["match"] = True
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        sealed084_api,
        "_ARCHIVE_MANIFEST_SHA256",
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    )
    updated_sources = [
        replace(
            spec,
            expected_hashes={**spec.expected_hashes, artifact_name: artifact_sha256},
        )
        if spec.task_id == task_id
        else spec
        for spec in sealed084_api._SOURCES
    ]
    monkeypatch.setattr(sealed084_api, "_SOURCES", tuple(updated_sources))


def _assert_archive_fixture_integrity(archive_root: Path) -> None:
    manifest_path = archive_root / sealed084_api._ARCHIVE_MANIFEST_NAME
    manifest_bytes = manifest_path.read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == sealed084_api._ARCHIVE_MANIFEST_SHA256
    source_directories = sealed084_api._load_archive_source_directories(archive_root)
    assert source_directories is not None

    manifest = json.loads(manifest_bytes)
    for row in manifest["archived_files"]:
        artifact_bytes = (archive_root / row["archive_relative_path"]).read_bytes()
        assert len(artifact_bytes) == row["byte_size"]
        assert hashlib.sha256(artifact_bytes).hexdigest() == row["sha256"]

    for spec in sealed084_api._SOURCES:
        source_dir = source_directories[spec.task_id]
        artifact_bytes = {
            name: (source_dir / name).read_bytes() for name in sealed084_api._ARTIFACT_NAMES
        }
        artifact_hashes = {
            name: hashlib.sha256(data).hexdigest() for name, data in artifact_bytes.items()
        }
        assert artifact_hashes == spec.expected_hashes

        result: dict[str, Any] = json.loads(artifact_bytes["result.json"])
        assert result["task_id"] == spec.task_id
        assert result["task_lifecycle_state"] == "COMPLETED"
        assert result["source_tier"] == sealed084_api.SOURCE_TIER
        cutoff_values = {
            str(result.get(key))
            for key in ("source_cutoff", "source_snapshot_cutoff", "cutoff_issue")
            if result.get(key) is not None
        }
        assert sealed084_api.SOURCE_CUTOFF in cutoff_values

        declarations = cast(dict[str, Any], result.get("artifacts", {}))
        for name in sealed084_api._ARTIFACT_NAMES[1:]:
            declaration = cast(dict[str, Any], declarations.get(name, {}))
            assert declaration.get("sha256") == artifact_hashes[name]
            assert declaration.get("bytes") == len(artifact_bytes[name])


def test_local_app_reads_all_28_cells_with_exact_csv_metrics_and_source_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _local_client(monkeypatch, SOURCE_ROOT).get(API_PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["source_cutoff"] == "115000084"
    assert payload["source_tier"] == "SEALED_ATTESTED_DRAW_ROWS"
    assert payload["strategy_count"] == 7
    assert payload["returned_window_rows"] == 28
    assert len(payload["results"]) == 28

    expected = _csv_rows()
    actual_by_key = {
        (
            row["strategy_id"],
            row["strategy_version"],
            row["ticket_count"],
            row["window"],
        ): row
        for row in payload["results"]
    }
    assert len(actual_by_key) == 28
    assert set(actual_by_key) == set(expected)
    for key, csv_row in expected.items():
        api_row = actual_by_key[key]
        assert api_row["game"] == csv_row.get("game", "BIG_LOTTO")
        assert api_row["successful_issues"] == int(
            csv_row.get("successful_issues") or csv_row["success_count"]
        )
        assert api_row["evaluated_issues"] == int(
            csv_row.get("evaluated_issues") or csv_row["eligible_count"]
        )
        assert api_row["success_rate"] == float(csv_row["success_rate"])
        assert api_row["source_cutoff"] == "115000084"
        assert api_row["source_tier"] == "SEALED_ATTESTED_DRAW_ROWS"
        assert api_row["source_task_id"] in TASKS
        assert api_row["source_artifact_identity"].startswith("sha256:")
        assert api_row["historical_replay_status"] == "SEALED_084_RESEARCH_REPLAY"
        assert api_row["owner_rank"] is None

    horizon_full = actual_by_key[("b649_new_horizon_minimax_disagreement_r1", "v0.1", 2, "FULL")]
    renewal_full = actual_by_key[("research_causal_renewal_hazard_k2", "v1.0", 2, "FULL")]
    assert horizon_full["evaluated_issues"] == 1966
    assert renewal_full["evaluated_issues"] == 1416
    assert horizon_full["comparability_status"] == ("NOT_DIRECTLY_COMPARABLE_ELIGIBLE_ISSUE_SET")
    assert renewal_full["comparability_status"] == "COMPARABLE_WITHIN_MATCHED_WINDOW"

    status = _local_client(monkeypatch, SOURCE_ROOT).get(STATUS_PATH)
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["returned_window_rows"] == 28
    assert len(status_payload["sources"]) == 3
    horizon_source = next(
        source
        for source in status_payload["sources"]
        if source["source_task_id"].endswith("HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1")
    )
    assert "085\u2013096" in horizon_source["source_gaps"]
    assert "097\u2013099" in horizon_source["source_gaps"]
    assert horizon_source["original_draw_data_v3_status"].startswith("NOT_DIRECTLY_VERIFIED")
    renewal_source = next(
        source for source in status_payload["sources"] if source["source_task_id"] == TASKS[0]
    )
    assert renewal_source["original_draw_data_v3_status"] == "UNVERIFIED"
    assert renewal_source["draw_source_status"].startswith("PASS:")


def test_local_app_reads_the_independent_archive_without_task_data_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = _copy_archive(tmp_path)
    client = _local_client(monkeypatch, archive_root)

    response = client.get(API_PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["source_cutoff"] == "115000084"
    assert payload["source_tier"] == "SEALED_ATTESTED_DRAW_ROWS"
    assert payload["strategy_count"] == 7
    assert payload["returned_window_rows"] == 28
    assert len(payload["results"]) == 28

    manifest = json.loads((archive_root / "archive_manifest.json").read_text(encoding="utf-8"))
    expected = {
        json.dumps(
            [row["strategy_id"], row["strategy_version"], row["ticket_count"], row["window"]],
            separators=(",", ":"),
        ): (row["success_count"], row["evaluated_issues"], row["success_rate"])
        for row in manifest["restored_window_statistics"]
    }
    actual = {
        json.dumps(
            [row["strategy_id"], row["strategy_version"], row["ticket_count"], row["window"]],
            separators=(",", ":"),
        ): (row["successful_issues"], row["evaluated_issues"], row["success_rate"])
        for row in payload["results"]
    }
    assert len(expected) == len(actual) == 28
    assert json.loads(json.dumps(actual, sort_keys=True)) == json.loads(
        json.dumps(expected, sort_keys=True)
    )
    assert {row["strategy_id"] for row in payload["results"]} == set(STRATEGY_TICKET_COUNTS)
    assert all(row["source_cutoff"] == "115000084" for row in payload["results"])
    assert all(row["source_tier"] == "SEALED_ATTESTED_DRAW_ROWS" for row in payload["results"])

    expected_tasks = {row["task_id"] for row in manifest["source_tasks"]}
    status = client.get(STATUS_PATH)
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["returned_window_rows"] == 28
    assert {row["source_task_id"] for row in status_payload["sources"]} == expected_tasks

    expected_authority = {
        row["task_id"]: row["draw_data_v3_authority"] for row in manifest["source_authority_limits"]
    }
    assert {
        row["source_task_id"]: row["original_draw_data_v3_status"]
        for row in status_payload["sources"]
    } == expected_authority

    recreated = _local_client(monkeypatch, archive_root).get(API_PATH)
    assert recreated.status_code == 200
    assert json.loads(json.dumps(recreated.json(), sort_keys=True)) == json.loads(
        json.dumps(payload, sort_keys=True)
    )


def test_archive_without_manifest_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    (archive_root / "restore_check.json").write_text("{}", encoding="utf-8")
    client = _local_client(monkeypatch, archive_root)

    for path in (API_PATH, STATUS_PATH):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["status"] == "SOURCE_UNAVAILABLE"
        assert response.json()["error_code"] == "SOURCE_ARCHIVE_MANIFEST_MISSING"


def test_archive_manifest_hash_mismatch_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    manifest_bytes = (ARCHIVE_ROOT / "archive_manifest.json").read_bytes()
    (archive_root / "archive_manifest.json").write_bytes(manifest_bytes + b" ")

    response = _local_client(monkeypatch, archive_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == "SOURCE_ARCHIVE_MANIFEST_HASH_MISMATCH"


def test_archive_file_hash_mismatch_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = _archive_skeleton(tmp_path, materialized_paths=("Renewal/result.json",))
    result_path = archive_root / "Renewal" / "result.json"
    result_bytes = bytearray(result_path.read_bytes())
    result_bytes[0] ^= 1
    result_path.write_bytes(result_bytes)

    response = _local_client(monkeypatch, archive_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == "SOURCE_HASH_MISMATCH"


def test_missing_manifest_listed_archive_file_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = _archive_skeleton(tmp_path, missing_paths=("Renewal/result.json",))

    response = _local_client(monkeypatch, archive_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == "SOURCE_FILE_MISSING"


def test_archive_version_conflict_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = _archive_skeleton(
        tmp_path,
        materialized_paths=(
            "Horizon/result.json",
            "Horizon/four_window_results.csv",
            "Horizon/per_issue_results.jsonl",
            "Horizon/draw_issue_manifest.json",
        ),
    )
    source_task_id = TASKS[2]
    result_path = archive_root / "Horizon" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["generator_identity"]["version"] = "v9.9"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    _reseal_archive_fixture(archive_root, monkeypatch, source_task_id, "result.json")
    monkeypatch.setattr(
        sealed084_api,
        "_SOURCES",
        tuple(
            sorted(
                sealed084_api._SOURCES,
                key=lambda spec: spec.task_id != source_task_id,
            )
        ),
    )

    response = _local_client(monkeypatch, archive_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == "SOURCE_IDENTITY_CONFLICT"


def test_archive_empty_denominator_is_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = _copy_archive(tmp_path)
    source_task_id = TASKS[0]
    csv_path = archive_root / "Renewal" / "four_window_results.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    denominator_field = "evaluated_issues" if "evaluated_issues" in fieldnames else "eligible_count"
    rows[0][denominator_field] = "0"
    rows[0]["success_rate"] = "0"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    result_path = archive_root / "Renewal" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    artifact_name = "four_window_results.csv"
    artifact_bytes = (archive_root / "Renewal" / artifact_name).read_bytes()
    declaration = result.get("artifacts", {}).get(artifact_name)
    if isinstance(declaration, dict):
        declaration["sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
        declaration["bytes"] = len(artifact_bytes)
    result_path.write_text(json.dumps(result), encoding="utf-8")
    for artifact_name in (
        "four_window_results.csv",
        "result.json",
    ):
        _reseal_archive_fixture(archive_root, monkeypatch, source_task_id, artifact_name)
    _assert_archive_fixture_integrity(archive_root)

    response = _local_client(monkeypatch, archive_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == "EMPTY_DENOMINATOR"


def test_each_strategy_can_be_queried_including_low_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _local_client(monkeypatch, SOURCE_ROOT)
    for strategy_id, ticket_count in STRATEGY_TICKET_COUNTS.items():
        version = "v0.1" if strategy_id == "b649_new_horizon_minimax_disagreement_r1" else "v1.0"
        response = client.get(
            API_PATH,
            params={
                "strategy_id": strategy_id,
                "strategy_version": version,
                "ticket_count": ticket_count,
                "window": "RECENT_50",
            },
        )

        assert response.status_code == 200
        assert response.json()["returned_window_rows"] == 1
        assert response.json()["results"][0]["strategy_id"] == strategy_id


def test_recreated_local_app_returns_identical_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _local_client(monkeypatch, SOURCE_ROOT).get(API_PATH).json()
    second = _local_client(monkeypatch, SOURCE_ROOT).get(API_PATH).json()

    assert json.loads(json.dumps(first, sort_keys=True)) == json.loads(
        json.dumps(second, sort_keys=True)
    )


@pytest.mark.parametrize(
    ("configured_root", "expected_code"),
    [
        (None, "SOURCE_ROOT_NOT_CONFIGURED"),
        (Path("/missing/sealed-084-source"), "SOURCE_ROOT_MISSING"),
    ],
)
def test_unconfigured_or_missing_source_is_not_an_empty_success(
    monkeypatch: pytest.MonkeyPatch,
    configured_root: Path | None,
    expected_code: str,
) -> None:
    response = _local_client(monkeypatch, configured_root).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == expected_code
    assert "results" not in response.json()


def test_hash_mismatch_is_reported_as_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / TASKS[0]
    source_dir.mkdir()
    original = SOURCE_ROOT / TASKS[0]
    shutil.copy2(original / "result.json", source_dir / "result.json")
    csv_path = source_dir / "four_window_results.csv"
    csv_path.write_bytes((original / "four_window_results.csv").read_bytes() + b"\n")

    response = _local_client(monkeypatch, tmp_path).get(API_PATH)

    assert response.status_code == 503
    assert response.json()["error_code"] == "SOURCE_HASH_MISMATCH"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("version", "SOURCE_IDENTITY_CONFLICT"),
        ("empty_denominator", "EMPTY_DENOMINATOR"),
        ("missing_window", "SOURCE_WINDOW_MISSING_OR_DUPLICATE"),
    ],
)
def test_invalid_identity_metrics_and_windows_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_code: str,
) -> None:
    spec = next(spec for spec in sealed084_api._SOURCES if spec.task_id == TASKS[2])
    source_dir = tmp_path / spec.task_id
    source_dir.mkdir()
    original_dir = SOURCE_ROOT / spec.task_id
    for name in sealed084_api._ARTIFACT_NAMES:
        shutil.copy2(original_dir / name, source_dir / name)

    csv_path = source_dir / "four_window_results.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    expected_hashes = dict(spec.expected_hashes)
    if mutation == "version":
        result_path = source_dir / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["generator_identity"]["version"] = "v9.9"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        expected_hashes["result.json"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    elif mutation == "empty_denominator":
        rows[0]["eligible_count"] = "0"
        rows[0]["success_rate"] = "0"
    else:
        rows = [row for row in rows if row["window"] != "RECENT_50"]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    expected_hashes["four_window_results.csv"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        sealed084_api, "_SOURCES", (replace(spec, expected_hashes=expected_hashes),)
    )
    client = cast(
        JsonTestClient,
        TestClient(create_app(b649_sealed084_replay_source_root=tmp_path)),
    )

    response = client.get(API_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == "SOURCE_UNAVAILABLE"
    assert response.json()["error_code"] == expected_code


def test_unknown_filter_does_not_return_an_empty_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _local_client(monkeypatch, SOURCE_ROOT).get(
        API_PATH, params={"strategy_id": "unknown_strategy"}
    )

    assert response.status_code == 404
    assert response.json() == {
        "status": "NO_MATCHING_RESULTS",
        "error_code": "RESULT_NOT_FOUND",
    }


def test_ticket_count_mapping_covers_exactly_seven_strategy_identities() -> None:
    assert len(STRATEGY_TICKET_COUNTS) == 7
