"""Contract tests for D's checksum-pinned read-only routes in the host app."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from shutil import copyfile
from typing import Any, Protocol, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from lottolab.interfaces.api import research_backtests
from lottolab.interfaces.api.app import create_app


class JsonTestClient(Protocol):
    def __enter__(self) -> JsonTestClient: ...

    def __exit__(self, *args: object) -> None: ...

    def get(self, url: str, **kwargs: object) -> httpx.Response: ...

MANIFEST_PATH = research_backtests.DEFAULT_MANIFEST_PATH
STRATEGIES_PATH = "/api/v1/research/backtests/strategies"
RANKINGS_PATH = "/api/v1/research/backtests/rankings"
SCORES_PATH = "/api/v1/research/backtests/scores"


def _pinned_csv_hashes() -> dict[str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        name: hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        for name, item in sorted(manifest["source_files"].items())
    }


@pytest.fixture(scope="module", autouse=True)
def d_source_files_remain_read_only() -> Iterator[None]:
    before = _pinned_csv_hashes()
    yield
    assert _pinned_csv_hashes() == before


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[JsonTestClient]:
    monkeypatch.delenv(research_backtests.MANIFEST_PATH_ENV, raising=False)
    with TestClient(create_app()) as test_client:
        yield cast(JsonTestClient, test_client)


def _scores_for(client: JsonTestClient, **params: Any) -> dict[str, Any]:
    response = client.get(SCORES_PATH, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _copy_manifest_with_relative_csvs(root: Path) -> tuple[Path, dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    csv_root = root / "csv"
    csv_root.mkdir(parents=True)
    for item in manifest["source_files"].values():
        source = Path(item["path"])
        destination = csv_root / source.name
        copyfile(source, destination)
        item["path"] = destination.relative_to(root).as_posix()
    manifest_path = root / "read_model_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path, manifest


def _response_without_local_source_locations(response: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(response))
    normalized["source_manifest"].pop("path")
    normalized["source_manifest"].pop("sha256")
    for source in normalized["source_files"].values():
        source.pop("path")
    return normalized


def test_d_routes_are_registered_and_existing_b649_summary_contract_remains(
    client: JsonTestClient,
) -> None:
    paths = set(create_app().openapi()["paths"])
    assert {STRATEGIES_PATH, RANKINGS_PATH, SCORES_PATH} <= paths

    response = client.get("/api/v1/b649-multi-ticket-records/summary")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["progress"]["total_strategy_count"] == 221
    assert payload["prefix_counts"] == [5, 10, 15, 20]
    assert payload["windows"] == ["FULL", "RECENT_750", "RECENT_300", "RECENT_50"]
    assert "catalog_sha256" in payload
    assert "projection_sha256" in payload


def test_strategies_expose_all_receipted_states_without_changing_manual_fields(
    client: JsonTestClient,
) -> None:
    first = client.get(STRATEGIES_PATH)
    second = client.get(STRATEGIES_PATH)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content

    payload = first.json()
    assert payload["counts"] == {
        "status_rows": 3286,
        "retained_records": 1064,
        "source_coverage_identities": 184,
    }
    assert len(payload["strategies"]) == 3286
    assert len(payload["retention_evidence"]) == 1064
    assert payload["source_reference"]["h24_master_status"] == "CANONICAL_NOT_SELECTED"
    assert all(
        row[field] is None
        for row in payload["strategies"]
        for field in ("manual_rank", "owner_decision", "owner_notes")
    )

    serialized = json.dumps(payload, ensure_ascii=False)
    for status in ("DO_NOT_ADVANCE", "BLOCKED", "NONCAUSAL", "NOT_COMPARABLE", "UNRESOLVED"):
        assert status in serialized
    assert payload["source_task"]["task_id"] == "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1"


def test_formal_and_descriptive_rankings_are_separate_and_paginate_stably(
    client: JsonTestClient,
) -> None:
    formal = client.get(RANKINGS_PATH, params={"K": 5, "window": "LONG", "type": "formal"})
    descriptive = client.get(
        RANKINGS_PATH,
        params={"K": 5, "window": "LONG", "type": "descriptive", "limit": 2},
    )
    assert formal.status_code == descriptive.status_code == 200
    formal_payload = formal.json()
    descriptive_payload = descriptive.json()
    assert formal_payload["count"] == 143
    assert all(row["rank_basis"] == "formal_rank" for row in formal_payload["rankings"])
    assert descriptive_payload["count"] == 3
    assert descriptive_payload["returned"] == 2
    assert all(row["formal_rank"] is None for row in descriptive_payload["rankings"])
    assert all(row["rank_basis"] == "descriptive_rank" for row in descriptive_payload["rankings"])
    all_h24_seeds = client.get(
        RANKINGS_PATH,
        params={"K": 5, "window": "LONG", "type": "descriptive", "limit": 10},
    ).json()["rankings"]
    assert {row["strategy_id"] for row in all_h24_seeds} == {
        "H24_TRANSFORMER_SEED1",
        "H24_TRANSFORMER_SEED2",
        "H24_TRANSFORMER_SEED3",
    }

    page_one = client.get(
        RANKINGS_PATH,
        params={"K": 5, "window": "LONG", "type": "formal", "offset": 0, "limit": 17},
    ).json()["rankings"]
    page_two = client.get(
        RANKINGS_PATH,
        params={"K": 5, "window": "LONG", "type": "formal", "offset": 17, "limit": 17},
    ).json()["rankings"]
    identities_one = {row["identity_key"] for row in page_one}
    identities_two = {row["identity_key"] for row in page_two}
    assert len(page_one) == len(page_two) == 17
    assert identities_one.isdisjoint(identities_two)


def test_score_filters_keep_strategy_versions_and_k_windows_independent(
    client: JsonTestClient,
) -> None:
    for k in (2, 3, 5):
        response = client.get(SCORES_PATH, params={"K": k, "window": "LONG"})
        assert response.status_code == 200
        assert response.json()["count"] > 0
        assert all(row["K"] == k and row["window"] == "LONG" for row in response.json()["scores"])

    version_a = _scores_for(
        client, strategy_id="EH12", strategy_version="EH12_WASSERSTEIN_WINDOW_SHIFT_R1"
    )
    version_b = _scores_for(
        client,
        strategy_id="EH12",
        strategy_version="eh12-causal-w1-prior100-split50-threshold0025-native-gate-v1",
    )
    assert version_a["count"] > 0
    assert version_b["count"] > 0
    assert {row["strategy_version"] for row in version_a["scores"]} == {
        "EH12_WASSERSTEIN_WINDOW_SHIFT_R1"
    }
    assert {row["strategy_version"] for row in version_b["scores"]} == {
        "eh12-causal-w1-prior100-split50-threshold0025-native-gate-v1"
    }

    coldpool = _scores_for(
        client,
        strategy_id="legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5",
        strategy_version="legacy-source-49a25effa62f-2a80423e3cf5",
        K=5,
    )
    assert {row["window"]: row["historical_success_count"] for row in coldpool["scores"]} == {
        "LONG": 251,
        "MID": 98,
        "SHORT": 23,
    }

    l3 = _scores_for(
        client,
        strategy_id="legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        strategy_version="legacy-source-49a25effa62f-d5b3de348d01",
        policy_version="l3-enhanced-dual-bet-single-invalid-greedy-fallback-v1",
        K=5,
    )
    assert {row["window"]: row["historical_success_count"] for row in l3["scores"]} == {
        "LONG": 209,
        "MID": 73,
        "SHORT": 20,
    }

    status_rows = client.get(STRATEGIES_PATH).json()["strategies"]
    eh27_original = [
        row
        for row in status_rows
        if row["strategy_id"] == "EH27"
        and row["source_task_id"] == "NUMBER2_D_B649_FRONTIER_EH27_SUBSET_SCAN_COMPLETE_R1"
    ]
    eh27_clean = [
        row
        for row in status_rows
        if row["strategy_id"] == "SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE"
        and row["source_task_id"] == "NUMBER2_D_EH27_CLEAN_HORIZON_RECOVERY_20261102_R1"
        and row["variant_type"] == "EH27_COUNTERFACTUAL_CLEAN"
    ]
    assert eh27_original
    assert eh27_clean

    absent = _scores_for(client, strategy_id="NO_SUCH_D_STRATEGY")
    assert absent["count"] == 0
    assert absent["scores"] == []


def test_scores_paginate_and_preserve_null_and_zero_values(client: JsonTestClient) -> None:
    first = client.get(SCORES_PATH, params={"offset": 0, "limit": 500})
    second = client.get(SCORES_PATH, params={"offset": 500, "limit": 500})
    assert first.status_code == second.status_code == 200
    assert first.json()["count"] == second.json()["count"] == 1806
    assert first.json()["returned"] == second.json()["returned"] == 500
    assert {row["identity_key"] for row in first.json()["scores"]}.isdisjoint(
        row["identity_key"] for row in second.json()["scores"]
    )

    all_rows: list[dict[str, Any]] = []
    for offset in range(0, 1806, 500):
        page = client.get(SCORES_PATH, params={"offset": offset, "limit": 500})
        assert page.status_code == 200
        all_rows.extend(page.json()["scores"])
    assert len(all_rows) == 1806
    assert any(row["historical_success_count"] is None for row in all_rows)
    assert any(row["W"] == 0 for row in all_rows)
    assert any(row["L"] == 0 for row in all_rows)


def test_stale_source_version_and_invalid_parameters_have_fixed_errors(
    client: JsonTestClient,
) -> None:
    current = client.get(STRATEGIES_PATH).json()["data_version"]
    stale = client.get(STRATEGIES_PATH, params={"data_version": "0" * 64})
    assert stale.status_code == 409
    assert stale.json()["error"] == "source_version_mismatch"
    assert stale.json()["data_version"] == current
    for path, params in (
        (RANKINGS_PATH, {"K": 5, "window": "LONG", "type": "formal", "data_version": "0" * 64}),
        (SCORES_PATH, {"strategy_id": "EH12", "data_version": "0" * 64}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 409
        assert response.json()["error"] == "source_version_mismatch"

    for params in (
        {"K": 10, "window": "LONG", "type": "formal"},
        {"K": 5, "window": "FULL", "type": "formal"},
        {"K": 5, "window": "LONG", "type": "unknown"},
        {"K": 5, "window": "LONG", "type": "formal", "limit": 0},
        {"K": 5, "window": "LONG", "type": "formal", "unexpected": "x"},
    ):
        response = client.get(RANKINGS_PATH, params=params)
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    duplicate = client.get(f"{RANKINGS_PATH}?K=5&K=3&window=LONG&type=formal")
    assert duplicate.status_code == 400
    assert duplicate.json()["error"] == "invalid_request"

    invalid_scores = client.get(SCORES_PATH, params={"algorithm_version": ""})
    assert invalid_scores.status_code == 400


def test_configured_relative_manifest_reproduces_all_three_get_results(
    client: JsonTestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The app fixture captured the default path at construction; a later
    # environment change must not switch its data source mid-process.
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, "/etc/passwd")
    default_strategies = client.get(STRATEGIES_PATH)
    default_formal = client.get(
        RANKINGS_PATH, params={"K": 5, "window": "LONG", "type": "formal"}
    )
    default_descriptive = client.get(
        RANKINGS_PATH, params={"K": 5, "window": "LONG", "type": "descriptive"}
    )
    default_score_pages = [
        client.get(SCORES_PATH, params={"offset": offset, "limit": 500})
        for offset in range(0, 1806, 500)
    ]
    assert all(
        response.status_code == 200
        for response in (
            default_strategies,
            default_formal,
            default_descriptive,
            *default_score_pages,
        )
    )

    alternate_manifest, _ = _copy_manifest_with_relative_csvs(tmp_path / "relocated")
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(alternate_manifest))
    alternate_app = create_app()
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(MANIFEST_PATH))
    with cast(JsonTestClient, TestClient(alternate_app)) as alternate_client:
        alternate_strategies = alternate_client.get(STRATEGIES_PATH)
        alternate_formal = alternate_client.get(
            RANKINGS_PATH, params={"K": 5, "window": "LONG", "type": "formal"}
        )
        alternate_descriptive = alternate_client.get(
            RANKINGS_PATH, params={"K": 5, "window": "LONG", "type": "descriptive"}
        )
        alternate_score_pages = [
            alternate_client.get(
                SCORES_PATH,
                params={"offset": offset, "limit": 500},
                headers={"X-Manifest-Path": "/etc/passwd"} if offset == 0 else None,
            )
            for offset in range(0, 1806, 500)
        ]
        request_path_override = alternate_client.get(
            SCORES_PATH, params={"manifest_path": "/etc/passwd"}
        )

    assert all(
        response.status_code == 200
        for response in (
            alternate_strategies,
            alternate_formal,
            alternate_descriptive,
            *alternate_score_pages,
        )
    )
    assert request_path_override.status_code == 400
    assert request_path_override.json()["error"] == "invalid_request"

    default_payloads = [
        default_strategies.json(),
        default_formal.json(),
        default_descriptive.json(),
        *(response.json() for response in default_score_pages),
    ]
    alternate_payloads = [
        alternate_strategies.json(),
        alternate_formal.json(),
        alternate_descriptive.json(),
        *(response.json() for response in alternate_score_pages),
    ]
    assert [payload["data_version"] for payload in default_payloads] == [
        payload["data_version"] for payload in alternate_payloads
    ]
    assert [payload["data_version"] for payload in alternate_payloads] == [
        "5834c3e65569990d07927e0857adaaada450dcef376fec648ce181048f12de97"
    ] * len(alternate_payloads)
    assert alternate_strategies.json()["strategies"] == default_strategies.json()["strategies"]
    assert alternate_strategies.json()["retention_evidence"] == default_strategies.json()[
        "retention_evidence"
    ]
    assert alternate_formal.json()["rankings"] == default_formal.json()["rankings"]
    assert alternate_descriptive.json()["rankings"] == default_descriptive.json()["rankings"]
    default_scores = [row for response in default_score_pages for row in response.json()["scores"]]
    alternate_scores = [
        row for response in alternate_score_pages for row in response.json()["scores"]
    ]
    assert len(default_scores) == len(alternate_scores) == 1806
    assert alternate_scores == default_scores
    default_responses = [
        default_strategies,
        default_formal,
        default_descriptive,
        *default_score_pages,
    ]
    alternate_responses = [
        alternate_strategies,
        alternate_formal,
        alternate_descriptive,
        *alternate_score_pages,
    ]
    assert [
        _response_without_local_source_locations(response.json())
        for response in alternate_responses
    ] == [
        _response_without_local_source_locations(response.json())
        for response in default_responses
    ]
    assert alternate_strategies.json()["source_manifest"]["path"] == str(
        alternate_manifest.resolve()
    )
    assert (
        alternate_strategies.json()["source_files"]["scores"]["path"]
        == "csv/owner_all_horizon_scores.csv"
    )


@pytest.mark.parametrize(
    ("mutation", "message_fragment"),
    [
        ("wrong_schema", "schema"),
        ("wrong_identity", "identity"),
        ("absolute_source", "external"),
        ("path_escape", "external"),
        ("symlink_escape", "escapes"),
    ],
)
def test_alternate_manifest_rejects_untrusted_schema_identity_and_paths(
    mutation: str,
    message_fragment: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path, manifest = _copy_manifest_with_relative_csvs(tmp_path / mutation)
    if mutation == "wrong_schema":
        manifest["schema_version"] = "999"
    elif mutation == "wrong_identity":
        manifest["source_task_id"] = "UNAPPROVED_SOURCE"
    elif mutation == "absolute_source":
        manifest["source_files"]["scores"]["path"] = "/etc/passwd"
    elif mutation == "symlink_escape":
        (manifest_path.parent / "escape.csv").symlink_to("/etc/passwd")
        manifest["source_files"]["scores"]["path"] = "escape.csv"
    else:
        manifest["source_files"]["scores"]["path"] = "../outside.csv"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(manifest_path))

    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(SCORES_PATH)

    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert message_fragment in response.json()["message"].lower()


def test_missing_manifest_and_changed_source_sha_return_explicit_service_errors(
    client: JsonTestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_manifest = tmp_path / "missing-manifest.json"
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(missing_manifest))
    with cast(JsonTestClient, TestClient(create_app())) as missing_manifest_client:
        missing = missing_manifest_client.get(SCORES_PATH)
    assert missing.status_code == 503
    assert missing.json()["error"] == "source_unavailable"
    assert "manifest" in missing.json()["message"].lower()

    missing_csv_manifest, missing_csv_model = _copy_manifest_with_relative_csvs(
        tmp_path / "missing-csv"
    )
    missing_csv = missing_csv_manifest.parent / missing_csv_model["source_files"]["scores"]["path"]
    missing_csv.unlink()
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(missing_csv_manifest))
    with cast(JsonTestClient, TestClient(create_app())) as missing_csv_client:
        missing_source = missing_csv_client.get(SCORES_PATH)
    assert missing_source.status_code == 503
    assert missing_source.json()["error"] == "source_unavailable"
    assert "resolve manifest source" in missing_source.json()["message"].lower()

    changed_manifest, changed_payload = _copy_manifest_with_relative_csvs(
        tmp_path / "changed-source"
    )
    scores_path = changed_manifest.parent / changed_payload["source_files"]["scores"]["path"]
    altered_bytes = bytearray(scores_path.read_bytes())
    altered_bytes[0] ^= 1
    scores_path.write_bytes(altered_bytes)
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, str(changed_manifest))
    with cast(JsonTestClient, TestClient(create_app())) as changed_client:
        changed = changed_client.get(SCORES_PATH)
    assert changed.status_code == 503
    assert changed.json()["error"] == "source_unavailable"
    assert "sha mismatch" in changed.json()["message"].lower()


def test_blank_manifest_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(research_backtests.MANIFEST_PATH_ENV, "  ")
    with cast(JsonTestClient, TestClient(create_app())) as configured_client:
        response = configured_client.get(SCORES_PATH)
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert research_backtests.MANIFEST_PATH_ENV in response.json()["message"]
