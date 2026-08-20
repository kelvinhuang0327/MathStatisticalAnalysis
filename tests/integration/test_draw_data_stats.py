"""Temporary-DB integration tests for the canonical draw statistics read model."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.application.draw_data import RepositoryUnavailableError
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.imports.csv_draws import PARSER_VERSION
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.app import create_app

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "stats-draw-data")}
    )


def csv_row(
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: str,
    *,
    source: str = "synthetic-stats",
) -> str:
    if lottery_type is LotteryType.BIG_LOTTO:
        main_numbers = "1|3|9|17|24|49"
        special_number = "7"
    elif lottery_type is LotteryType.DAILY_539:
        main_numbers = "1|3|9|17|24"
        special_number = ""
    else:
        main_numbers = "1|3|9|17|24|38"
        special_number = "8"
    return (
        f"{lottery_type.value},{draw_number},{draw_date},"
        f"{main_numbers},{special_number},{source}"
    )


def csv_document(*rows: str) -> str:
    return "\n".join((HEADER, *rows, ""))


def commit_body(content: str) -> dict[str, object]:
    return {
        "filename": "synthetic-stats.csv",
        "csv_text": content,
        "expected_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "parser_version": PARSER_VERSION,
        "conflict_policy": "REJECT",
    }


def client_for(paths: LocalDataPaths) -> TestClient:
    return TestClient(create_app(data_paths_provider=lambda: paths))


def stats_by_lottery(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["items"]
    assert isinstance(items, list)
    return {str(item["lottery_type"]): item for item in items}


def test_empty_stats_are_complete_and_do_not_create_storage(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    response = client_for(paths).get("/api/v1/draws/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_draw_count"] == 0
    assert [item["lottery_type"] for item in payload["items"]] == [
        lottery_type.value for lottery_type in LotteryType
    ]
    assert all(
        item["draw_count"] == 0
        and item["earliest_draw_date"] is None
        and item["latest_draw_date"] is None
        and item["latest_draw_number"] is None
        for item in payload["items"]
    )
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_stats_aggregate_multiple_lotteries_and_retain_missing_lottery(
    tmp_path: Path,
) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)
    big_lotto = csv_document(
        csv_row(LotteryType.BIG_LOTTO, "0100", "2026-07-15"),
        csv_row(LotteryType.BIG_LOTTO, "0101", "2026-07-17"),
    )
    daily_539 = csv_document(
        csv_row(LotteryType.DAILY_539, "0200", "2026-07-11"),
        csv_row(LotteryType.DAILY_539, "0201", "2026-07-12"),
    )

    assert (
        client.post("/api/v1/draw-imports/commit", json=commit_body(big_lotto)).status_code
        == 200
    )
    assert (
        client.post("/api/v1/draw-imports/commit", json=commit_body(daily_539)).status_code
        == 200
    )

    response = client.get("/api/v1/draws/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_draw_count"] == 4
    assert [item["lottery_type"] for item in payload["items"]] == [
        lottery_type.value for lottery_type in LotteryType
    ]
    stats = stats_by_lottery(payload)
    assert stats[LotteryType.BIG_LOTTO.value] == {
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "draw_count": 2,
        "earliest_draw_date": "2026-07-15",
        "latest_draw_date": "2026-07-17",
        "latest_draw_number": "0101",
    }
    assert stats[LotteryType.DAILY_539.value] == {
        "lottery_type": LotteryType.DAILY_539.value,
        "draw_count": 2,
        "earliest_draw_date": "2026-07-11",
        "latest_draw_date": "2026-07-12",
        "latest_draw_number": "0201",
    }
    assert stats[LotteryType.POWER_LOTTO.value] == {
        "lottery_type": LotteryType.POWER_LOTTO.value,
        "draw_count": 0,
        "earliest_draw_date": None,
        "latest_draw_date": None,
        "latest_draw_number": None,
    }


def test_stats_latest_number_uses_draw_order_not_insert_order(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)
    content = csv_document(
        csv_row(LotteryType.BIG_LOTTO, "0101", "2026-07-17"),
        csv_row(LotteryType.BIG_LOTTO, "0100", "2026-07-17"),
    )
    assert client.post("/api/v1/draw-imports/commit", json=commit_body(content)).status_code == 200

    response = client.get("/api/v1/draws/stats")

    assert response.status_code == 200
    stats = stats_by_lottery(response.json())
    assert stats[LotteryType.BIG_LOTTO.value]["latest_draw_number"] == "0101"


def test_stats_request_is_read_only(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    client = client_for(paths)
    content = csv_document(csv_row(LotteryType.BIG_LOTTO, "0100", "2026-07-17"))
    assert client.post("/api/v1/draw-imports/commit", json=commit_body(content)).status_code == 200
    database_before = paths.database.read_bytes()
    sidecars_before = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    history_before = client.get("/api/v1/draws").json()["total_count"]

    response = client.get("/api/v1/draws/stats")

    assert response.status_code == 200
    assert client.get("/api/v1/draws").json()["total_count"] == history_before == 1
    assert paths.database.read_bytes() == database_before
    assert {path.name for path in tmp_path.rglob("*") if path.is_file()} == sidecars_before


def test_stats_repository_error_is_sanitized(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    paths = task_paths(tmp_path)

    def unavailable(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RepositoryUnavailableError(f"sqlite failed at {paths.database}")

    monkeypatch.setattr(SQLiteDrawDataRepository, "get_stats", unavailable)
    response = client_for(paths).get("/api/v1/draws/stats")

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPOSITORY_UNAVAILABLE",
        "message": "Local draw data is unavailable.",
    }
    assert str(paths.database) not in response.text
    assert "sqlite" not in response.text.casefold()
