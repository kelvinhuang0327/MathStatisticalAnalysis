"""Contract tests for the host app's pinned K5 draw-event API."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.interfaces.api import research_backtest_events as events_api
from lottolab.interfaces.api.app import create_app

API_PATH = events_api.API_PATH
ANCHOR_DRAW = "103000101"


@pytest.fixture(scope="module")
def client() -> Any:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def source_index() -> events_api.EventIndex:
    return events_api.load_event_index()


def _normalize(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _identity_params(policy: tuple[Any, ...], **extra: Any) -> dict[str, Any]:
    return {
        "strategy_id": policy[0],
        "strategy_version": policy[1],
        "policy_version": policy[2],
        "algorithm_version": policy[3],
        "run_identity": policy[4],
        "K": 5,
        **extra,
    }


def test_create_app_registers_and_serves_source_anchored_draw_events(
    client: Any, source_index: events_api.EventIndex
) -> None:
    assert API_PATH in create_app().openapi()["paths"]
    for policy in events_api.POLICY_IDENTITIES:
        response = client.get(
            API_PATH,
            params=_identity_params(policy, target_draw=ANCHOR_DRAW),
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["count"] == payload["returned"] == 1
        assert payload["source_manifest"]["event_count"] == 10536
        assert payload["source_manifest"]["identity_count"] == 5268
        record = payload["draw_events"][0]
        source = next(
            item
            for item in source_index.records
            if item.prediction["strategy_id"] == policy[0]
            and item.prediction["strategy_version"] == policy[1]
            and item.prediction["policy_version"] == policy[2]
            and item.prediction["algorithm_version"] == policy[3]
            and item.prediction["run_identity"] == policy[4]
            and item.prediction["target_draw"] == ANCHOR_DRAW
        )
        assert record["lottery"] == "BIG_LOTTO"
        assert record["K"] == 5
        assert record["history_cutoff"] == source.prediction["history_cutoff"]
        assert record["ordered_tickets"] == _normalize(source.prediction["ordered_tickets"])
        assert record["official_result"]["winning_result"] == _normalize(
            source.official_result["winning_result"]
        )
        assert record["official_any_prize"] is source.official_result["candidate_any_prize"]
        assert record["ticket_prize_tiers"] == _normalize(
            source.official_result["ticket_prize_tiers"]
        )
        assert record["prediction_any_prize"] is source.prediction.get("candidate_any_prize")
        assert record["source_variant"] == source.prediction.get("source_variant")
        assert record["data_version"] == source_index.data_version
        assert (
            record["source_identity"]["prediction"]["producer"]["sha256"]
            == source.prediction["producer_source_identity"]["sha256"]
        )
        assert (
            record["source_identity"]["official_result"]["result_artifact_sha256"]
            == (source.official_result["result_artifact_sha256"])
        )
        assert "/Users/" not in json.dumps(record)
        assert "/.task-data/" not in json.dumps(record)
        assert "/Users/" not in json.dumps(payload["source_manifest"])
        assert "original_predraw_evidence" in payload["source_manifest"]
        assert payload["source_manifest"]["producer_causality"] == "NOT_ESTABLISHED"
        if policy[0] == "GREEDY_DISJOINT_K":
            assert record["prediction_any_prize"] is None
            assert record["official_any_prize"] is False


def test_four_policies_keep_1317_rows_ordered_paginated_and_parity_counts(
    client: Any,
) -> None:
    for policy in events_api.POLICY_IDENTITIES:
        params = _identity_params(policy, limit=250, offset=0)
        first = client.get(API_PATH, params=params)
        repeated = client.get(API_PATH, params=params)
        assert first.status_code == repeated.status_code == 200
        assert first.content == repeated.content
        first_payload = first.json()
        assert first_payload["count"] == 1317
        rows = list(first_payload["draw_events"])
        for offset in range(250, 1317, 250):
            page = client.get(API_PATH, params={**params, "offset": offset})
            assert page.status_code == 200, page.text
            assert page.json()["count"] == 1317
            rows.extend(page.json()["draw_events"])
        assert len(rows) == 1317
        assert len({row["target_draw"] for row in rows}) == 1317
        assert [row["target_draw"] for row in rows] == sorted(row["target_draw"] for row in rows)
        assert all(
            row["strategy_id"] == policy[0]
            and row["strategy_version"] == policy[1]
            and row["policy_version"] == policy[2]
            and row["algorithm_version"] == policy[3]
            and row["run_identity"] == policy[4]
            for row in rows
        )
        assert sum(row["official_any_prize"] is True for row in rows) == policy[6]
        assert all(row["K"] == 5 and row["lottery"] == "BIG_LOTTO" for row in rows)
        assert all(row["data_version"] == first_payload["data_version"] for row in rows)

        if policy[0] == "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01":
            assert (
                sum(row["fallback"]["native_fallback_class"] == "GREEDY_FALLBACK" for row in rows)
                == 1
            )
        if policy[0] == "SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE":
            assert all(
                row["source_variant"] == "counterfactual_23_roster_clean_history_r2" for row in rows
            )
            assert (
                sum(
                    row["fallback"]["native_fallback_class"] == "WARMUP_GREEDY_FALLBACK"
                    for row in rows
                )
                == 100
            )


def test_query_errors_unknown_identity_and_data_version_are_explicit(client: Any) -> None:
    base_policy = events_api.POLICY_IDENTITIES[0]
    assert client.get(API_PATH, params={"strategy_id": base_policy[0]}).status_code == 400
    assert client.get(API_PATH, params={"K": 4, "strategy_id": base_policy[0]}).status_code == 400
    assert (
        client.get(
            API_PATH, params={"K": 5, "strategy_id": base_policy[0], "limit": "lots"}
        ).status_code
        == 400
    )
    assert (
        client.get(
            API_PATH, params={"K": 5, "strategy_id": base_policy[0], "source_path": "/tmp/x"}
        ).status_code
        == 400
    )

    unknown = client.get(API_PATH, params={"K": 5, "strategy_id": "NO_SUCH_STRATEGY"})
    assert unknown.status_code == 200
    assert unknown.json()["count"] == 0
    assert unknown.json()["draw_events"] == []

    wrong_version = client.get(
        API_PATH,
        params={"K": 5, "strategy_id": base_policy[0], "data_version": "old-version"},
    )
    assert wrong_version.status_code == 409
    assert wrong_version.json()["error"] == "source_version_mismatch"


def test_ambiguous_strategy_version_is_rejected_over_http(
    source_index: events_api.EventIndex,
) -> None:
    source = source_index.records[0]
    changed_prediction = _normalize(source.prediction)
    changed_prediction["strategy_version"] = "another-version"
    ambiguous_record = replace(source, prediction=changed_prediction)
    ambiguous_index = replace(source_index, records=(source, ambiguous_record))
    app = FastAPI()
    app.include_router(events_api.create_research_backtest_events_router(ambiguous_index))
    with TestClient(app) as test_client:
        response = test_client.get(
            API_PATH,
            params={"K": 5, "strategy_id": source.prediction["strategy_id"]},
        )
    assert response.status_code == 409
    assert response.json()["error"] == "ambiguous_identity"
    assert "strategy_version" in response.json()["message"]


def test_pairing_rejects_orphans_duplicates_and_conflicting_metadata(
    source_index: events_api.EventIndex,
) -> None:
    source = source_index.records[0]
    prediction = _normalize(source.prediction)
    official = _normalize(source.official_result)

    raw_events: dict[tuple[Any, ...], dict[str, Any]] = {}
    events_api._insert_event(raw_events, prediction, source.source_id)
    with pytest.raises(events_api.EventSourceError, match="duplicate"):
        events_api._insert_event(raw_events, prediction, source.source_id)
    with pytest.raises(events_api.EventSourceError, match="orphan"):
        events_api._pair_event_records(raw_events, expected_identities=1)

    conflicted_official = {**official, "source_variant": "wrong-counterfactual"}
    with pytest.raises(events_api.EventSourceError, match="metadata conflict"):
        events_api._pair_event_records(
            {
                source.identity: {
                    "PREDICTION": prediction,
                    "OFFICIAL_RESULT": conflicted_official,
                }
            },
            expected_identities=1,
        )


def test_changed_pinned_source_fails_closed_without_returning_another_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    specs = list(events_api._source_specs())
    changed_path = tmp_path / specs[0].file_name
    changed_path.write_bytes(specs[0].path.read_bytes() + b" ")
    specs[0] = replace(specs[0], path=changed_path)
    bad_specs = tuple(specs)
    with pytest.raises(events_api.EventSourceError, match="integrity"):
        events_api.load_event_index(bad_specs)

    monkeypatch.setattr(events_api, "_source_specs", lambda: bad_specs)
    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.get(
            API_PATH,
            params={"K": 5, "strategy_id": events_api.POLICY_IDENTITIES[0][0]},
        )
    assert response.status_code == 503
    assert response.json()["error"] == "source_unavailable"
    assert "/Users/" not in response.text
    assert str(changed_path) not in response.text
