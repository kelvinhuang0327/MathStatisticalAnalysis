from __future__ import annotations

from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.replay_backfill_store import (
    JsonObject,
    SQLiteBackfillStore,
)
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router

_RUN_ID = "projection-fixture-run"
_STRATEGY_ID = "projection-fixture-strategy"
_STRATEGY_VERSION = "v0.1"


def _case(
    tiers: list[str | None],
    *,
    target_draw_id: str = "102000010",
    lottery_type: str = "BIG_LOTTO",
    ticket_positions: list[int | None] | None = None,
    hit_values: list[tuple[int | None, bool, str | None]] | None = None,
    provenance: str = "UNVERIFIED",
) -> tuple[JsonObject, JsonObject]:
    positions = ticket_positions or list(range(1, len(tiers) + 1))
    hits = hit_values or [(0, False, tier) for tier in tiers]
    identity: JsonObject = {
        "lottery_type": lottery_type,
        "run_id": _RUN_ID,
        "target_draw_id": target_draw_id,
        "target_draw_date": "2015-01-01",
        "strategy_id": _STRATEGY_ID,
        "strategy_version": _STRATEGY_VERSION,
        "cell_identity": f"fixture-cell-{target_draw_id}",
    }
    payload: JsonObject = {
        **identity,
        "execution_status": "COMPLETED",
        "predicted_tickets": [
            {
                "ticket_position": position,
                "main_numbers": [1, 2, 3, 4, 5, 6],
                "special_number": 7,
            }
            for position in positions
        ],
        "hit_details": [
            {
                "ticket_position": position,
                "zone1_hits": zone1_hits,
                "zone2_hit": zone2_hit,
                "prize_tier": tier,
            }
            for position, (zone1_hits, zone2_hit, tier) in zip(positions, hits, strict=True)
        ],
        "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
        "source_history_provenance_status": provenance,
        "strategy_source": {},
    }
    return payload, identity


class PredictionPageStore:
    def __init__(self, rows: list[JsonObject]) -> None:
        self._rows = rows

    def prediction_page(self, **_: object) -> JsonObject:
        return {"run_id": _RUN_ID, "total_count": len(self._rows), "rows": self._rows}


def _request_items(cases: list[tuple[JsonObject, JsonObject]]) -> tuple[int, JsonObject]:
    rows = [
        {
            "payload": payload,
            "identity": identity,
            "cutoff_source": None,
            "portfolio_context": None,
        }
        for payload, identity in cases
    ]
    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(cast(SQLiteBackfillStore, PredictionPageStore(rows)))
    )

    with cast(httpx.Client, TestClient(app)) as client:
        response: httpx.Response = client.get(
            "/api/v1/replay-backfill/predictions",
            params={"lottery_type": "BIG_LOTTO", "run_id": _RUN_ID, "period": "ALL"},
        )

    return response.status_code, cast(JsonObject, response.json())


def _item(
    tiers: list[str | None],
    *,
    target_draw_id: str = "102000010",
    lottery_type: str = "BIG_LOTTO",
    ticket_positions: list[int | None] | None = None,
    hit_values: list[tuple[int | None, bool, str | None]] | None = None,
    provenance: str = "UNVERIFIED",
) -> JsonObject:
    payload, identity = _case(
        tiers,
        target_draw_id=target_draw_id,
        lottery_type=lottery_type,
        ticket_positions=ticket_positions,
        hit_values=hit_values,
        provenance=provenance,
    )
    status_code, body = _request_items([(payload, identity)])

    assert status_code == 200
    assert body["total_count"] == 1
    return cast(list[JsonObject], body["items"])[0]


def test_all_no_prize_tickets_are_not_a_win() -> None:
    item = _item(["NO_PRIZE"] * 5)

    assert item["portfolio_any_prize"] is False
    assert [ticket["prize_tier"] for ticket in item["predicted_tickets"]] == [None] * 5


def test_all_null_tickets_are_not_a_win() -> None:
    assert _item([None] * 5)["portfolio_any_prize"] is False


def test_no_prize_mixed_with_legal_award_is_a_win() -> None:
    item = _item(["NO_PRIZE", "FIFTH"])

    assert item["portfolio_any_prize"] is True
    assert [ticket["prize_tier"] for ticket in item["predicted_tickets"]] == [None, "FIFTH"]


def test_old_rule_two_plus_special_seventh_is_removed_at_boundary() -> None:
    item = _item(
        ["SEVENTH"],
        target_draw_id="103000080",
        hit_values=[(2, True, "SEVENTH")],
    )

    assert item["predicted_tickets"][0]["prize_tier"] is None
    assert item["portfolio_any_prize"] is False


def test_new_rule_two_plus_special_seventh_is_retained_at_boundary() -> None:
    item = _item(
        ["SEVENTH"],
        target_draw_id="103000081",
        hit_values=[(2, True, "SEVENTH")],
    )

    assert item["predicted_tickets"][0]["prize_tier"] == "SEVENTH"
    assert item["portfolio_any_prize"] is True


def test_legal_three_plus_award_is_retained() -> None:
    item = _item(["FIRST"], hit_values=[(3, False, "FIRST")])

    assert item["predicted_tickets"][0]["prize_tier"] == "FIRST"
    assert item["portfolio_any_prize"] is True


def test_incomplete_hit_evidence_remains_unscorable() -> None:
    item = _item([None], hit_values=[(None, False, None)])

    assert item["evaluation_status"] == "NOT_EVALUATED"
    assert item["portfolio_any_prize"] is None


def test_missing_ticket_position_remains_untrusted_and_unscored() -> None:
    item = _item(["NO_PRIZE"], ticket_positions=[None])

    assert item["identity_status"] == "UNTRUSTED"
    assert item["portfolio_any_prize"] is None


def test_duplicate_ticket_positions_remain_untrusted_and_unscored() -> None:
    item = _item(["NO_PRIZE", "FIRST"], ticket_positions=[1, 1])

    assert item["identity_status"] == "UNTRUSTED"
    assert item["portfolio_any_prize"] is None


def test_identity_mismatch_remains_untrusted_and_unscored() -> None:
    payload, identity = _case(["NO_PRIZE"])
    payload["run_id"] = "another-run"

    status_code, body = _request_items([(payload, identity)])
    item = cast(list[JsonObject], body["items"])[0]

    assert status_code == 200
    assert item["identity_status"] == "UNTRUSTED"
    assert item["portfolio_any_prize"] is None


def test_unverified_provenance_is_not_upgraded() -> None:
    item = _item(["NO_PRIZE"], provenance="UNVERIFIED")

    assert item["source_history_provenance_status"] == "UNVERIFIED"
    assert item["identity_status"] == "VERIFIED"


def test_other_lottery_no_prize_projection_is_unchanged() -> None:
    item = _item(["NO_PRIZE"], lottery_type="POWER_LOTTO")

    assert item["predicted_tickets"][0]["prize_tier"] == "NO_PRIZE"
    assert item["portfolio_any_prize"] is True


def test_predictions_http_projects_no_prize_and_counts_multi_award_cell_once() -> None:
    no_prize = _case(["NO_PRIZE", "NO_PRIZE"], target_draw_id="102000010")
    two_awards = _case(["FIRST", "SECOND"], target_draw_id="102000011")

    status_code, body = _request_items([no_prize, two_awards])
    items = cast(list[JsonObject], body["items"])

    assert status_code == 200
    assert body["total_count"] == 2
    assert len(items) == 2
    assert [item["portfolio_any_prize"] for item in items] == [False, True]
    assert [ticket["prize_tier"] for ticket in items[0]["predicted_tickets"]] == [None, None]
    assert [ticket["prize_tier"] for ticket in items[1]["predicted_tickets"]] == [
        "FIRST",
        "SECOND",
    ]
