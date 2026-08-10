"""Authority-backed acceptance tests for the T539/P638 base-data query APIs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import create_local_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = REPOSITORY_ROOT.parent / ".runs" / "MathStatisticalAnalysis"
AUTHORITY_ROOT = RUN_ROOT / "BIGLOTTO68_CROSSLOTTERY_EXHAUSTIVE_CLOSURE_R2"
T539_DB = AUTHORITY_ROOT / "t539_biglotto68_cross_lottery_r2.sqlite3"
P638_DB = AUTHORITY_ROOT / "p638_current_ranking_r2.sqlite3"
P638_REPLAY_DB = AUTHORITY_ROOT / "p638_current_replay_r2.sqlite3"
T539_RUN_ID = "BIGLOTTO68_TO_T539_CROSS_LOTTERY_CLOSURE_R2"
P638_RUN_ID = "p638-wave1-f892e6fa25a394c7"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _get(client: Any, path: str, **params: object) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    payload = cast(dict[str, Any], response.json())
    assert isinstance(payload, dict)
    return payload


@pytest.mark.skipif(
    not all(path.exists() for path in (T539_DB, P638_DB, P638_REPLAY_DB)),
    reason="preserved T539/P638 authority databases are not present",
)
def test_real_authority_base_data_is_complete_read_only_and_lottery_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_hashes = {path: _sha256(path) for path in (T539_DB, P638_DB, P638_REPLAY_DB)}
    monkeypatch.setenv("LOTTOLAB_T539_HISTORICAL_DB", str(T539_DB))
    monkeypatch.setenv("LOTTOLAB_P638_CURRENT_RANKING_DB", str(P638_DB))
    monkeypatch.setenv("LOTTOLAB_P638_CURRENT_REPLAY_DB", str(P638_REPLAY_DB))
    client: Any = TestClient(create_local_app())

    t_base = "/api/v1/t539-historical"
    t_run = _get(client, f"{t_base}/runs", limit=1)["items"][0]
    assert t_run["run_id"] == T539_RUN_ID
    assert t_run["strategy_count"] == 62
    assert t_run["draw_count"] == 5930
    t_strategies = _get(client, f"{t_base}/runs/{T539_RUN_ID}/strategies", limit=200)
    assert t_strategies["total_count"] == 62
    t_draw_pages = [
        _get(client, f"{t_base}/runs/{T539_RUN_ID}/draws", limit=1, offset=offset)
        for offset in (0, 2964, 5929)
    ]
    assert all(page["total_count"] == 5930 for page in t_draw_pages)
    assert len({page["items"][0]["draw_id"] for page in t_draw_pages}) == 3

    t_complete = _get(
        client,
        f"{t_base}/runs/{T539_RUN_ID}/replay",
        status="COMPLETE_CAUSAL_REPLAY",
        limit=1,
    )
    assert t_complete["total_count"] == 365502
    t_single_strategy = next(
        item for item in t_strategies["items"] if item["native_ticket_count"] == 1
    )
    t_multi_strategy = next(
        item for item in t_strategies["items"] if item["native_ticket_count"] > 1
    )
    t_single = _get(
        client,
        f"{t_base}/runs/{T539_RUN_ID}/replay",
        strategy_id=t_single_strategy["strategy_id"],
        status="COMPLETE_CAUSAL_REPLAY",
        limit=1,
    )["items"][0]
    t_multi = _get(
        client,
        f"{t_base}/runs/{T539_RUN_ID}/replay",
        strategy_id=t_multi_strategy["strategy_id"],
        status="COMPLETE_CAUSAL_REPLAY",
        limit=1,
    )["items"][0]
    for record in (t_single, t_multi):
        assert record["status"] == "COMPLETE_CAUSAL_REPLAY"
        assert len(record["tickets"]) == record["native_ticket_count"]
        detail = _get(
            client,
            f"{t_base}/runs/{T539_RUN_ID}/strategies/{record['strategy_id']}/"
            f"{record['strategy_version']}/targets/{record['target_draw_id']}",
        )
        assert [ticket["ticket_position"] for ticket in detail["tickets"]] == list(
            range(1, record["native_ticket_count"] + 1)
        )

    with _readonly(T539_DB) as connection:
        pre_identity = connection.execute(
            "SELECT strategy_id, strategy_version, first_eligible_target_draw_id "
            "FROM strategy_coverage WHERE first_eligible_target_draw_id IS NOT NULL "
            "ORDER BY strategy_id, strategy_version LIMIT 1"
        ).fetchone()
        assert pre_identity is not None
        pre_draw = connection.execute(
            "SELECT draw_id FROM source_draws WHERE draw_order < "
            "(SELECT draw_order FROM source_draws WHERE draw_id = ?) "
            "ORDER BY draw_order LIMIT 1",
            (pre_identity[2],),
        ).fetchone()
        assert pre_draw is not None
        persisted_ticket = connection.execute(
            "SELECT pt.main_numbers_json, ps.actual_main_numbers_json, "
            "ps.hit_numbers_json, ps.hits FROM prediction_tickets AS pt "
            "JOIN prediction_scores AS ps ON ps.run_id = pt.run_id "
            "AND ps.strategy_id = pt.strategy_id AND ps.strategy_version = pt.strategy_version "
            "AND ps.target_draw_id = pt.target_draw_id "
            "AND ps.ticket_position = pt.ticket_position "
            "WHERE pt.run_id = ? AND pt.strategy_id = ? AND pt.strategy_version = ? "
            "AND pt.target_draw_id = ? AND pt.ticket_position = 1",
            (
                T539_RUN_ID,
                t_single["strategy_id"],
                t_single["strategy_version"],
                t_single["target_draw_id"],
            ),
        ).fetchone()
        assert persisted_ticket is not None
    pre = _get(
        client,
        f"{t_base}/runs/{T539_RUN_ID}/strategies/{pre_identity[0]}/"
        f"{pre_identity[1]}/targets/{pre_draw[0]}",
    )
    assert pre["status"] == "PRE_ELIGIBILITY"
    assert pre["tickets"] == []
    assert pre["reason_type"] == "INSUFFICIENT_CAUSAL_HISTORY"
    api_ticket = t_single["tickets"][0]
    assert api_ticket["predicted_numbers"] == json.loads(persisted_ticket[0])
    assert api_ticket["actual_numbers"] == json.loads(persisted_ticket[1])
    assert api_ticket["hit_numbers"] == json.loads(persisted_ticket[2])
    assert api_ticket["hits"] == persisted_ticket[3]

    p_base = "/api/v1/p638-historical"
    p_run = _get(client, f"{p_base}/runs", limit=1)["items"][0]
    assert p_run["run_id"] == P638_RUN_ID
    assert p_run["strategy_count"] == 70
    assert p_run["draw_count"] == 1933
    p_strategies = _get(client, f"{p_base}/runs/{P638_RUN_ID}/strategies", limit=200)
    assert p_strategies["total_count"] == 70
    p_draw_pages = [
        _get(client, f"{p_base}/runs/{P638_RUN_ID}/draws", limit=1, offset=offset)
        for offset in (0, 966, 1932)
    ]
    assert all(page["total_count"] == 1933 for page in p_draw_pages)
    assert len({page["items"][0]["draw_number"] for page in p_draw_pages}) == 3
    p_complete = _get(
        client,
        f"{p_base}/runs/{P638_RUN_ID}/replay",
        status="COMPLETE_CAUSAL_REPLAY",
        limit=1,
    )
    assert p_complete["total_count"] == 130948
    p_record = p_complete["items"][0]
    assert len(p_record["tickets"]) == p_record["expected_ticket_count"]
    p_detail = _get(
        client,
        f"{p_base}/runs/{P638_RUN_ID}/strategies/{p_record['strategy_id']}/"
        f"{p_record['strategy_version']}/targets/{p_record['target_draw_number']}",
    )
    assert [ticket["ticket_position"] for ticket in p_detail["tickets"]] == list(
        range(1, p_record["expected_ticket_count"] + 1)
    )
    p_ticket = p_record["tickets"][0]
    assert p_ticket["predicted_zone2_number"] in range(1, 9)
    assert p_ticket["actual_zone2_number"] in range(1, 9)
    assert p_ticket["second_zone_ssot_version"] == "p638-powerlotto-second-zone-v1"
    with _readonly(P638_DB) as connection:
        persisted_p_ticket = connection.execute(
            "SELECT predicted_zone1_numbers_json, predicted_zone2_number, "
            "actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit, "
            "is_winner, prize_tier, prize_tier_order FROM p638_current_ticket "
            "WHERE id = ?",
            (p_ticket["ticket_id"],),
        ).fetchone()
        assert persisted_p_ticket is not None
    assert p_ticket["predicted_zone1_numbers"] == json.loads(persisted_p_ticket[0])
    assert p_ticket["predicted_zone2_number"] == persisted_p_ticket[1]
    assert p_ticket["actual_zone1_numbers"] == json.loads(persisted_p_ticket[2])
    assert p_ticket["actual_zone2_number"] == persisted_p_ticket[3]
    assert p_ticket["zone1_hit_count"] == persisted_p_ticket[4]
    assert p_ticket["zone2_hit"] == bool(persisted_p_ticket[5])
    assert p_ticket["is_winner"] == bool(persisted_p_ticket[6])
    assert p_ticket["prize_tier"] == persisted_p_ticket[7]
    assert p_ticket["prize_tier_order"] == persisted_p_ticket[8]

    with _readonly(P638_DB) as connection:
        closure_identity = connection.execute(
            "SELECT strategy_id, strategy_version, target_draw_number "
            "FROM p638_current_target WHERE status = 'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE' "
            "ORDER BY target_draw_number, strategy_id LIMIT 1"
        ).fetchone()
        assert closure_identity is not None
    closure = _get(
        client,
        f"{p_base}/runs/{P638_RUN_ID}/strategies/{closure_identity[0]}/"
        f"{closure_identity[1]}/targets/{closure_identity[2]}",
    )
    assert closure["status"] == "SOURCE_NATIVE_TYPED_CLOSURE"
    assert closure["reason_type"] == "SOURCE_NATIVE_PORTFOLIO_CLOSURE"
    assert closure["tickets"] == []
    assert _get(
        client,
        f"{p_base}/runs/{P638_RUN_ID}/replay",
        status="PRE_ELIGIBILITY",
        limit=1,
    )["total_count"] == 3640
    assert _get(
        client,
        f"{p_base}/runs/{P638_RUN_ID}/replay",
        status="SOURCE_NATIVE_TYPED_CLOSURE",
        limit=1,
    )["total_count"] == 722

    assert _get(client, f"{t_base}/runs/{T539_RUN_ID}/draws", limit=2, offset=2)["items"]
    assert _get(client, f"{p_base}/runs/{P638_RUN_ID}/strategies", limit=2, offset=2)["items"]
    for base, run_id, error_code in (
        (t_base, T539_RUN_ID, "T539_RUN_NOT_FOUND"),
        (p_base, P638_RUN_ID, "P638_RUN_NOT_FOUND"),
    ):
        missing: Any = client.get(f"{base}/runs/unknown/strategies")
        assert missing.status_code == 404
        assert missing.json()["error_code"] == error_code
        assert client.get(f"{base}/runs/{run_id}/draws/unknown").status_code == 404
    assert client.post(f"{t_base}/runs/{T539_RUN_ID}/draws").status_code == 405

    after_hashes = {path: _sha256(path) for path in before_hashes}
    assert after_hashes == before_hashes


def test_base_data_query_api_reports_unconfigured_without_opening_storage() -> None:
    client: Any = TestClient(create_app())
    assert client.get("/api/v1/t539-historical/runs").status_code == 503
    assert client.get("/api/v1/p638-historical/runs").status_code == 503
