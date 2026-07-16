"""HTTP contracts for CSV preview/commit and local history APIs."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.application.draw_data import RepositoryUnavailableError
from lottolab.infrastructure.imports.csv_draws import (
    MAX_CSV_BYTES,
    PARSER_VERSION,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.app import create_app

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def csv_row(
    draw_number: str,
    *,
    draw_date: str = "2026-07-16",
    main_numbers: str = "1|3|9|17|24|49",
    special_number: str = "7",
    source: str = "synthetic-reference",
) -> str:
    return (
        f"BIG_LOTTO,{draw_number},{draw_date},{main_numbers},{special_number},{source}"
    )


def csv_document(*rows: str) -> str:
    return "\n".join((HEADER, *rows, ""))


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "api-task-data")}
    )


def client_for(paths: LocalDataPaths) -> TestClient:
    return TestClient(create_app(data_paths_provider=lambda: paths))


def preview_body(content: str, *, filename: str = "synthetic.csv") -> dict[str, object]:
    return {"filename": filename, "csv_text": content}


def commit_body(content: str, *, filename: str = "synthetic.csv") -> dict[str, object]:
    return {
        "filename": filename,
        "csv_text": content,
        "expected_sha256": digest(content),
        "parser_version": PARSER_VERSION,
        "conflict_policy": "REJECT",
    }


def test_valid_preview_is_bounded_structured_and_db_free(tmp_path: Path) -> None:
    calls = 0

    def forbidden_paths() -> LocalDataPaths:
        nonlocal calls
        calls += 1
        raise AssertionError("preview must not resolve data paths")

    client = TestClient(create_app(data_paths_provider=forbidden_paths))
    content = csv_document(
        "BIG_LOTTO,0001,2026-07-16,9|1|3|49|24|17,7,=1+1"
    )
    display_only = str(tmp_path / "must-not-be-opened.csv")

    response = client.post(
        "/api/v1/draw-imports/preview",
        json=preview_body(content, filename=display_only),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == display_only
    assert payload["is_valid"] is True
    assert payload["content_sha256"] == digest(content)
    assert payload["parser_version"] == PARSER_VERSION
    assert payload["supported_lottery_types"] == ["BIG_LOTTO"]
    assert payload["total_rows"] == payload["valid_rows"] == 1
    assert payload["duplicate_rows"] == payload["conflict_rows_inside_input"] == 0
    assert payload["validation_error_count"] == 0
    assert payload["normalized_preview"][0]["main_numbers"] == [1, 3, 9, 17, 24, 49]
    assert payload["normalized_preview"][0]["source_reference"] == "=1+1"
    assert calls == 0
    assert not Path(display_only).exists()


@pytest.mark.parametrize(
    ("content", "error_code"),
    [
        (csv_document("UNKNOWN,1,2026-07-16,1|2|3|4|5|6,7,x"), "UNSUPPORTED_LOTTERY_TYPE"),
        (csv_document("BIG_LOTTO,1,not-a-date,1|2|3|4|5|6,7,x"), "INVALID_DRAW_DATE"),
    ],
)
def test_invalid_preview_returns_structured_422(
    tmp_path: Path, content: str, error_code: str
) -> None:
    paths = task_paths(tmp_path)
    response = client_for(paths).post(
        "/api/v1/draw-imports/preview", json=preview_body(content)
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "CSV_VALIDATION_FAILED"
    preview = payload["preview"]
    assert preview["is_valid"] is False
    assert preview["validation_errors"][0]["code"] == error_code
    assert not paths.data_directory.exists()


def test_oversized_preview_rejects_without_database(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    content = "x" * (MAX_CSV_BYTES + 1)
    response = client_for(paths).post(
        "/api/v1/draw-imports/preview", json=preview_body(content)
    )

    assert response.status_code == 422
    preview = response.json()["preview"]
    assert preview["validation_errors"][0]["code"] == "FILE_TOO_LARGE"
    assert preview["content_sha256"] == digest(content)
    assert not paths.data_directory.exists()


def test_preview_bounds_records_and_errors(tmp_path: Path) -> None:
    client = client_for(task_paths(tmp_path))
    valid_content = csv_document(
        *(csv_row(str(index)) for index in range(1, 52))
    )
    valid = client.post(
        "/api/v1/draw-imports/preview", json=preview_body(valid_content)
    ).json()
    assert len(valid["normalized_preview"]) == 50
    assert valid["preview_truncated"] is True

    invalid_content = csv_document(
        *(
            csv_row(str(index), draw_date="invalid")
            for index in range(1, 102)
        )
    )
    response = client.post(
        "/api/v1/draw-imports/preview", json=preview_body(invalid_content)
    )
    assert response.status_code == 422
    invalid = response.json()["preview"]
    assert invalid["validation_error_count"] == 101
    assert len(invalid["validation_errors"]) == 100
    assert invalid["errors_truncated"] is True


def test_digest_and_parser_mismatch_stop_before_path_resolution() -> None:
    def forbidden_paths() -> LocalDataPaths:
        raise AssertionError("validation failure must not resolve data paths")

    client = TestClient(create_app(data_paths_provider=forbidden_paths))
    content = csv_document(csv_row("1"))
    mismatched = commit_body(content)
    mismatched["expected_sha256"] = "0" * 64
    digest_response = client.post("/api/v1/draw-imports/commit", json=mismatched)
    assert digest_response.status_code == 409
    assert digest_response.json()["error_code"] == "DIGEST_MISMATCH"

    stale = commit_body(content)
    stale["parser_version"] = "stale-parser"
    version_response = client.post("/api/v1/draw-imports/commit", json=stale)
    assert version_response.status_code == 422
    assert version_response.json()["error_code"] == "PARSER_VERSION_MISMATCH"


@pytest.mark.parametrize("kind", ["duplicate", "conflict"])
def test_contested_input_document_never_reaches_persistence(kind: str) -> None:
    def forbidden_paths() -> LocalDataPaths:
        raise AssertionError("invalid parser output must not reach persistence")

    first = csv_row("1")
    second = (
        csv_row("1")
        if kind == "duplicate"
        else csv_row("1", main_numbers="1|3|9|17|24|48")
    )
    content = csv_document(first, second)
    response = TestClient(create_app(data_paths_provider=forbidden_paths)).post(
        "/api/v1/draw-imports/commit", json=commit_body(content)
    )

    assert response.status_code == 422
    preview = response.json()["preview"]
    expected = "DUPLICATE_INPUT_ROW" if kind == "duplicate" else "CONFLICTING_INPUT_ROW"
    assert expected in {error["code"] for error in preview["validation_errors"]}


def test_commit_success_idempotency_history_and_run_apis(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)
    content = csv_document(
        csv_row("0001", draw_date="2026-07-15"),
        csv_row("0002", draw_date="2026-07-16", source="source-two"),
    )

    first = client.post("/api/v1/draw-imports/commit", json=commit_body(content))
    second = client.post("/api/v1/draw-imports/commit", json=commit_body(content))

    assert first.status_code == second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["inserted_count"] == 2
    assert first_payload["skipped_count"] == 0
    assert second_payload["inserted_count"] == 0
    assert second_payload["skipped_count"] == 2

    history = client.get(
        "/api/v1/draws",
        params={
            "lottery_type": "BIG_LOTTO",
            "draw_number": "000",
            "date_from": "2026-07-15",
            "date_to": "2026-07-16",
            "page": 1,
            "page_size": 1,
        },
    )
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["total_count"] == 2
    assert history_payload["total_pages"] == 2
    assert history_payload["records"][0]["draw_number"] == "0002"
    assert history_payload["records"][0]["source_reference"] == "source-two"
    assert history_payload["sort"] == [
        "draw_date:desc",
        "draw_number:string_desc",
        "id:desc",
    ]

    draw = client.get("/api/v1/draws/BIG_LOTTO/0001")
    assert draw.status_code == 200
    assert draw.json()["main_numbers"] == [1, 3, 9, 17, 24, 49]

    runs = client.get(
        "/api/v1/ingestion-runs",
        params={"status": "SUCCESS", "lottery_type": "BIG_LOTTO", "page_size": 10},
    )
    assert runs.status_code == 200
    assert runs.json()["total_count"] == 2
    run_id = second_payload["run_id"]
    detail = client.get(f"/api/v1/ingestion-runs/{run_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["run"]["source_sha256"] == digest(content)
    assert detail_payload["run"]["total_count"] == detail_payload["item_count"] == 2
    assert {item["disposition"] for item in detail_payload["items"]} == {
        "SKIPPED_DUPLICATE"
    }
    assert content not in detail.text


def test_existing_conflict_is_409_and_preserves_entire_batch(tmp_path: Path) -> None:
    client = client_for(task_paths(tmp_path))
    initial = csv_document(csv_row("10"))
    assert client.post("/api/v1/draw-imports/commit", json=commit_body(initial)).status_code == 200
    before = client.get("/api/v1/draws/BIG_LOTTO/10").json()

    conflict = csv_document(
        csv_row("11", draw_date="2026-07-17"),
        csv_row("10", main_numbers="1|3|9|17|24|48"),
    )
    response = client.post("/api/v1/draw-imports/commit", json=commit_body(conflict))

    assert response.status_code == 409
    payload = response.json()
    assert payload["error_code"] == "EXISTING_DRAW_CONFLICT"
    assert payload["result"]["inserted_count"] == 0
    assert payload["result"]["conflict_count"] == 1
    assert payload["result"]["failed_count"] == 1
    assert client.get("/api/v1/draws/BIG_LOTTO/11").status_code == 404
    assert client.get("/api/v1/draws/BIG_LOTTO/10").json() == before

    detail = client.get(f"/api/v1/ingestion-runs/{payload['result']['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["run"]["status"] == "FAILED"


def test_empty_history_and_unknown_ids_do_not_create_database(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)

    draws = client.get("/api/v1/draws")
    runs = client.get("/api/v1/ingestion-runs")
    missing_draw = client.get("/api/v1/draws/BIG_LOTTO/999")
    missing_run = client.get("/api/v1/ingestion-runs/unknown")

    assert draws.status_code == runs.status_code == 200
    assert draws.json()["records"] == []
    assert runs.json()["records"] == []
    assert missing_draw.status_code == missing_run.status_code == 404
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_pagination_date_range_and_request_errors_are_sanitized(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)
    raw_marker = "RAW_CSV_MUST_NOT_BE_ECHOED"

    invalid_page = client.get("/api/v1/draws", params={"page_size": 101})
    invalid_range = client.get(
        "/api/v1/draws",
        params={"date_from": "2026-07-17", "date_to": "2026-07-16"},
    )
    invalid_body = client.post(
        "/api/v1/draw-imports/commit",
        json={
            **commit_body(raw_marker),
            "expected_sha256": "invalid",
        },
    )

    assert invalid_page.status_code == invalid_range.status_code == invalid_body.status_code == 422
    assert invalid_page.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert invalid_range.json()["error_code"] == "INVALID_DATE_RANGE"
    assert raw_marker not in invalid_body.text
    assert str(paths.database) not in invalid_body.text


def test_repository_error_response_exposes_no_exception_or_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)

    def unavailable(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RepositoryUnavailableError(f"sqlite failed at {paths.database}")

    monkeypatch.setattr(SQLiteDrawDataRepository, "apply_valid_import", unavailable)
    content = csv_document(csv_row("1"))
    response = client_for(paths).post(
        "/api/v1/draw-imports/commit", json=commit_body(content)
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPOSITORY_UNAVAILABLE",
        "message": "Local draw data is unavailable.",
    }
    assert str(paths.database) not in response.text
    assert "sqlite" not in response.text.casefold()
