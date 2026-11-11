"""Contract tests for the receipt-pinned A/D strategy identity crosswalk API."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from lottolab.interfaces.api import research_crosswalk
from lottolab.interfaces.api.app import create_app


class JsonTestClient(Protocol):
    def __enter__(self) -> JsonTestClient: ...

    def __exit__(self, *args: object) -> None: ...

    def get(self, url: str, **kwargs: object) -> httpx.Response: ...

API_PATH = "/api/v1/research/backtests/identity-crosswalk"
SOURCE_FILES = (
    "current_ad_crosswalk.csv",
    "unmatched_ad_identities.csv",
    "result.json",
    "crosswalk_summary.json",
)


def _copy_source_root(destination: Path) -> Path:
    destination.mkdir(parents=True)
    for filename in SOURCE_FILES:
        shutil.copyfile(research_crosswalk.DEFAULT_SOURCE_ROOT / filename, destination / filename)
    return destination


@pytest.fixture
def client() -> Iterator[JsonTestClient]:
    with cast(JsonTestClient, TestClient(create_app())) as test_client:
        yield test_client


def _get(client: JsonTestClient, **params: Any) -> dict[str, Any]:
    response = client.get(API_PATH, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_route_is_registered_and_existing_research_routes_remain_available(
    client: JsonTestClient,
) -> None:
    paths = set(create_app().openapi()["paths"])
    assert API_PATH in paths
    assert {
        "/api/v1/research/backtests/strategies",
        "/api/v1/research/backtests/rankings",
        "/api/v1/research/backtests/scores",
    } <= paths

    for path in (
        "/api/v1/research/backtests/strategies",
        "/api/v1/b649-multi-ticket-records/summary",
    ):
        response = client.get(path)
        assert response.status_code == 200, response.text


def test_actual_http_counts_keep_scored_status_only_and_unknown_sets_separate(
    client: JsonTestClient,
) -> None:
    first = _get(client, limit=500, offset=0)
    second = _get(client, limit=500, offset=500)
    repeated = client.get(API_PATH, params={"limit": 500, "offset": 0})
    assert repeated.status_code == 200
    assert repeated.content == client.get(API_PATH, params={"limit": 500, "offset": 0}).content
    assert first["source"]["sha256"] == research_crosswalk.PINNED_CSV_SHA256
    assert first["source"]["version"] == research_crosswalk.SOURCE_VERSION
    assert first["counts"] == {
        "source_rows": 559,
        "legacy_d58_rows": 58,
        "row_match_statuses": {
            "EXACT_MATCH": 64,
            "PARTIAL_IDENTITY": 358,
            "UNKNOWN": 31,
            "UNMATCHED": 106,
        },
        "identity_scopes": {
            "SCORED_IDENTITY": 202,
            "STATUS_ONLY_IDENTITY": 326,
            "UNKNOWN_STATUS_IDENTITY": 31,
        },
        "scored_identity_match_statuses": {
            "EXACT_MATCH": 64,
            "PARTIAL_IDENTITY": 108,
            "UNMATCHED": 30,
        },
    }
    rows = first["identities"] + second["identities"]
    assert len(rows) == first["total"] == 559
    assert second["total"] == 559
    assert len({row["identity_key"] for row in rows}) == 559
    assert Counter(row["identity_scope"] for row in rows) == {
        "SCORED_IDENTITY": 202,
        "STATUS_ONLY_IDENTITY": 326,
        "UNKNOWN_STATUS_IDENTITY": 31,
    }
    assert Counter(
        row["match_status"] for row in rows if row["identity_scope"] == "SCORED_IDENTITY"
    ) == {"EXACT_MATCH": 64, "PARTIAL_IDENTITY": 108, "UNMATCHED": 30}
    assert "/Users/" not in str(rows)
    assert "/.task-data/" not in str(rows)
    legacy = first["legacy_d58"]
    assert legacy["total"] == legacy["returned"] == 58
    assert len({row["identity_key"] for row in legacy["identities"]}) == 58
    assert len(
        {(row["strategy_id"], row["strategy_version"]) for row in legacy["identities"]}
    ) == 58
    assert all(row["match_status"] == "LEGACY_UNMATCHED_RETAINED" for row in legacy["identities"])
    assert all(
        row["source_identity"]["crosswalk"]["collection"] == "legacy_d58_snapshot"
        for row in legacy["identities"]
    )
    assert "/Users/" not in str(legacy["identities"])


def test_exact_and_partial_versions_are_filtered_without_automatic_promotion(
    client: JsonTestClient,
) -> None:
    identity = {
        "strategy_id": "legacy_biglotto__advanced_methods_benchmark__87ee0d15033c",
        "strategy_version": "legacy-source-49a25effa62f-87ee0d15033c",
    }
    exact = _get(client, **identity, match_status="EXACT_MATCH", limit=500)["identities"]
    partial = _get(client, **identity, match_status="PARTIAL_IDENTITY", limit=500)["identities"]
    assert exact
    assert all(row["variant_type"] == "NATIVE" for row in exact)
    assert all(row["policy_version"] is None and row["algorithm_version"] is None for row in exact)
    assert partial
    assert all(row["match_status"] == "PARTIAL_IDENTITY" for row in partial)
    assert any(row["policy_version"] or row["algorithm_version"] for row in partial)

    unknown_version = _get(
        client, **{**identity, "strategy_version": "no-such-version"}
    )
    assert unknown_version["total"] == 0
    assert unknown_version["identities"] == []

    legacy = _get(
        client,
        strategy_id="EH01",
        strategy_version="eh01-causal-motif-single-ticket-r1",
        match_status="LEGACY_UNMATCHED_RETAINED",
        limit=20,
    )["legacy_d58"]
    assert legacy["total"] == 1
    assert legacy["identities"][0]["match_status"] == "LEGACY_UNMATCHED_RETAINED"


def test_h24_seeds_and_eh27_original_clean_identities_remain_separate(
    client: JsonTestClient,
) -> None:
    for seed in (1, 2, 3):
        payload = _get(
            client,
            strategy_id=f"H24_TRANSFORMER_SEED{seed}",
            strategy_version="h24-blocked-causal-transformer-residual-meta-v1",
            limit=20,
        )
        variants = {row["variant_type"] for row in payload["identities"]}
        scopes = {row["identity_scope"] for row in payload["identities"]}
        assert payload["total"] == 2
        assert f"H24_VERSION_REVIEW_SEED{seed}" in variants
        assert "STATUS_ONLY_IDENTITY" in scopes
        assert "SCORED_IDENTITY" in scopes

    original = _get(client, strategy_id="EH27", limit=20)["identities"]
    clean = _get(
        client,
        strategy_id="SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE",
        strategy_version="EH27_R1_FIXED_30_V1",
        limit=20,
    )["identities"]
    assert original
    assert all(row["strategy_id"] == "EH27" for row in original)
    assert any(row["variant_type"] == "EH27_COUNTERFACTUAL_CLEAN" for row in clean)


def test_window_contracts_keep_d_history_and_app_full_denominators_separate(
    client: JsonTestClient,
) -> None:
    payload = _get(
        client,
        strategy_id="legacy_biglotto__advanced_methods_benchmark__87ee0d15033c",
        strategy_version="legacy-source-49a25effa62f-87ee0d15033c",
        match_status="EXACT_MATCH",
        limit=20,
    )
    row = payload["identities"][0]
    assert row["D_window_contract"]["history_denominators"] == {
        "LONG": 1317,
        "MID": 520,
        "SHORT": 104,
    }
    d_windows = row["D_window_contract"]["K_windows"]
    assert {item["K"] for item in d_windows} >= {"2", "3", "5"}
    assert {item["window"] for item in d_windows} >= {"LONG", "MID", "SHORT"}
    app_windows = row["App_window_contract"]["K_windows"]
    assert {item["K"] for item in app_windows} >= {"2", "3", "5"}
    assert {item["window"] for item in app_windows} >= {
        "FULL",
        "RECENT_50",
        "RECENT_300",
        "RECENT_750",
    }
    app_full = {
        item["K"]: int(item["required_targets"][0])
        for item in row["App_window_contract"]["FULL_denominators"]
    }
    assert app_full == {"10": 2166, "2": 2149, "20": 2149, "3": 2149, "5": 2166}
    assert 1317 not in app_full.values()


def test_pagination_filters_and_source_group_are_stable(client: JsonTestClient) -> None:
    page_one = client.get(API_PATH, params={"limit": 100, "offset": 0})
    page_one_repeat = client.get(API_PATH, params={"limit": 100, "offset": 0})
    assert page_one.status_code == page_one_repeat.status_code == 200
    assert page_one.content == page_one_repeat.content
    rows = list(page_one.json()["identities"])
    total = page_one.json()["total"]
    for offset in range(100, total, 100):
        page = _get(client, limit=100, offset=offset)
        rows.extend(page["identities"])
    assert len(rows) == total == 559
    assert len({row["identity_key"] for row in rows}) == total

    legacy_rows: list[dict[str, Any]] = []
    for offset in range(0, 58, 17):
        page = _get(
            client,
            match_status="LEGACY_UNMATCHED_RETAINED",
            limit=17,
            offset=offset,
        )["legacy_d58"]
        assert page["total"] == 58
        legacy_rows.extend(page["identities"])
    assert len(legacy_rows) == 58
    assert len({row["identity_key"] for row in legacy_rows}) == 58

    group = "EH"
    grouped = _get(client, source_group=group, limit=500)
    assert grouped["total"] > 0
    assert all(group in row["source_groups"] for row in grouped["identities"])
    assert grouped["query"]["source_group"] == group

    unknown_strategy = _get(client, strategy_id="NO_SUCH_STRATEGY")
    assert unknown_strategy["total"] == 0
    assert unknown_strategy["identities"] == []


def test_same_strategy_keeps_distinct_source_versions(client: JsonTestClient) -> None:
    rows: list[dict[str, Any]] = []
    first = _get(client, limit=500, offset=0)
    rows.extend(first["identities"])
    for offset in range(500, first["total"], 500):
        rows.extend(_get(client, limit=500, offset=offset)["identities"])

    versions_by_strategy: dict[str, set[str]] = {}
    for row in rows:
        strategy_id = row.get("strategy_id")
        strategy_version = row.get("strategy_version")
        if strategy_id and strategy_version:
            versions_by_strategy.setdefault(strategy_id, set()).add(strategy_version)
    multi_version_ids = sorted(
        strategy_id for strategy_id, versions in versions_by_strategy.items() if len(versions) > 1
    )
    assert multi_version_ids

    strategy_id = multi_version_ids[0]
    expected_versions = versions_by_strategy[strategy_id]
    response_rows: list[dict[str, Any]] = []
    first_version_page = _get(client, strategy_id=strategy_id, limit=500, offset=0)
    response_rows.extend(first_version_page["identities"])
    for offset in range(500, first_version_page["total"], 500):
        response_rows.extend(
            _get(client, strategy_id=strategy_id, limit=500, offset=offset)["identities"]
        )
    assert {row["strategy_version"] for row in response_rows} == expected_versions
    assert len({row["identity_key"] for row in response_rows}) == len(response_rows)


def test_configured_source_root_is_captured_and_reads_only_alternate_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_root_env = research_crosswalk.SOURCE_ROOT_ENV
    monkeypatch.delenv(source_root_env, raising=False)
    default_app = create_app()
    with cast(JsonTestClient, TestClient(default_app)) as default_client:
        default_pages = [
            default_client.get(API_PATH, params={"limit": 500, "offset": offset})
            for offset in (0, 500)
        ]
    assert all(response.status_code == 200 for response in default_pages)
    assert default_pages[0].json()["total"] == 559
    assert default_pages[0].json()["legacy_d58"]["total"] == 58

    alternate_root = _copy_source_root(tmp_path / "relocated-crosswalk")
    monkeypatch.setenv(source_root_env, str(alternate_root))
    alternate_app = create_app()
    monkeypatch.setenv(source_root_env, str(tmp_path / "must-not-be-read"))

    original_reader = research_crosswalk._read_pinned_bytes  # pyright: ignore[reportPrivateUsage]
    read_paths: list[Path] = []

    def recording_reader(path: Path, expected_sha256: str, label: str) -> bytes:
        read_paths.append(path.resolve())
        return original_reader(path, expected_sha256, label)

    monkeypatch.setattr(research_crosswalk, "_read_pinned_bytes", recording_reader)
    with cast(JsonTestClient, TestClient(alternate_app)) as alternate_client:
        alternate_pages = [
            alternate_client.get(
                API_PATH,
                params={"limit": 500, "offset": offset},
                headers=(
                    {"X-Number2-AD-Crosswalk-Source-Root": "/etc/passwd"} if offset == 0 else None
                ),
            )
            for offset in (0, 500)
        ]

    assert all(response.status_code == 200 for response in alternate_pages)
    assert [response.content for response in alternate_pages] == [
        response.content for response in default_pages
    ]
    assert len(read_paths) == 8
    assert set(read_paths) == {alternate_root.resolve() / name for name in SOURCE_FILES}
    assert all(str(alternate_root.resolve()) in str(path) for path in read_paths)
    assert all("/Users/" not in response.text for response in alternate_pages)


@pytest.mark.parametrize("configured_value", ("", "   ", "relative/crosswalk"))
def test_blank_or_relative_source_configuration_fails_closed(
    configured_value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, configured_value)
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert not configured_value or configured_value not in response.text
    assert "/Users/" not in response.text


def test_missing_configured_source_root_fails_without_default_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_root = tmp_path / "missing-crosswalk"
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, str(missing_root))
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert str(missing_root) not in response.text
    assert "/Users/" not in response.text


def test_missing_file_in_configured_source_root_fails_without_default_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    alternate_root = _copy_source_root(tmp_path / "incomplete-crosswalk")
    missing_file = alternate_root / "crosswalk_summary.json"
    missing_file.unlink()
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, str(alternate_root))
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert str(alternate_root) not in response.text
    assert "/Users/" not in response.text


@pytest.mark.parametrize("filename", SOURCE_FILES)
def test_alternate_source_sha_mismatch_fails_without_default_fallback(
    filename: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    alternate_root = _copy_source_root(tmp_path / "tampered-crosswalk")
    source = alternate_root / filename
    source.write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, str(alternate_root))
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert str(alternate_root) not in response.text
    assert "/Users/" not in response.text


def test_alternate_source_rejects_receipt_version_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    alternate_root = _copy_source_root(tmp_path / "wrong-version-crosswalk")
    result_path = alternate_root / "result.json"
    receipt = json.loads(result_path.read_text(encoding="utf-8"))
    receipt["task_id"] = "UNAPPROVED_CROSSWALK_VERSION"
    result_bytes = json.dumps(receipt, ensure_ascii=False).encode("utf-8")
    result_path.write_bytes(result_bytes)
    monkeypatch.setattr(
        research_crosswalk,
        "PINNED_RESULT_SHA256",
        hashlib.sha256(result_bytes).hexdigest(),
    )
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, str(alternate_root))
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert "unexpected identity" in response.json()["message"]
    assert str(alternate_root) not in response.text


def test_alternate_source_rejects_symlink_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    alternate_root = _copy_source_root(tmp_path / "symlink-crosswalk")
    outside_source = tmp_path / "outside.csv"
    outside_source.write_bytes((alternate_root / "unmatched_ad_identities.csv").read_bytes())
    (alternate_root / "unmatched_ad_identities.csv").unlink()
    (alternate_root / "unmatched_ad_identities.csv").symlink_to(outside_source)
    monkeypatch.setenv(research_crosswalk.SOURCE_ROOT_ENV, str(alternate_root))
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(API_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert str(alternate_root) not in response.text
    assert str(outside_source) not in response.text


def test_invalid_and_arbitrary_path_parameters_are_rejected(client: JsonTestClient) -> None:
    for params in (
        {"match_status": "MATCHED"},
        {"source_group": "NO_SUCH_GROUP"},
        {"limit": 0},
        {"offset": -1},
        {"file": "/etc/passwd"},
        [("strategy_id", "EH12"), ("strategy_id", "EH12")],
    ):
        response = client.get(API_PATH, params=params)
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"


def test_response_uses_logical_source_locators_without_local_paths(client: JsonTestClient) -> None:
    payload = _get(client, limit=100)
    serialized = client.get(API_PATH, params={"limit": 100}).text
    assert "/Users/" not in serialized
    row = payload["identities"][0]
    source_identity = row["source_identity"]
    assert source_identity["crosswalk"] == {
        "collection": "current_crosswalk",
        "locator": f"current_ad_crosswalk.csv#identity_key={row['identity_key']}",
        "version": research_crosswalk.SOURCE_VERSION,
        "sha256": research_crosswalk.PINNED_CSV_SHA256,
    }
    assert all("/" not in locator for locator in source_identity["d"]["locators"])
    assert "D_window_contract" in row
    assert "App_window_contract" in row
    assert "exact_gap" in row


def test_missing_or_changed_pinned_sources_return_503_without_path_disclosure(
    client: JsonTestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_receipt = tmp_path / "missing-result.json"
    monkeypatch.setattr(research_crosswalk, "CROSSWALK_RESULT_PATH", missing_receipt)
    missing = client.get(API_PATH)
    assert missing.status_code == 503
    assert missing.json()["error"] == "source_unavailable"
    assert "/Users/" not in missing.text

    monkeypatch.setattr(
        research_crosswalk,
        "CROSSWALK_RESULT_PATH",
        research_crosswalk.DEFAULT_SOURCE_ROOT / "result.json",
    )
    for attribute, source_path in (
        ("CROSSWALK_RESULT_PATH", research_crosswalk.DEFAULT_SOURCE_ROOT / "result.json"),
        ("CROSSWALK_CSV_PATH", research_crosswalk.DEFAULT_SOURCE_ROOT / "current_ad_crosswalk.csv"),
        (
            "CROSSWALK_UNMATCHED_CSV_PATH",
            research_crosswalk.DEFAULT_SOURCE_ROOT / "unmatched_ad_identities.csv",
        ),
        (
            "CROSSWALK_SUMMARY_PATH",
            research_crosswalk.DEFAULT_SOURCE_ROOT / "crosswalk_summary.json",
        ),
    ):
        changed_source = tmp_path / f"changed-{source_path.name}"
        changed_source.write_bytes(source_path.read_bytes() + b"\n")
        monkeypatch.setattr(research_crosswalk, attribute, changed_source)
        changed = client.get(API_PATH)
        assert changed.status_code == 503
        assert changed.json()["error"] == "source_unavailable"
        assert "sha-256" in changed.json()["message"].lower()
        assert str(tmp_path) not in changed.text
        monkeypatch.setattr(research_crosswalk, attribute, source_path)
