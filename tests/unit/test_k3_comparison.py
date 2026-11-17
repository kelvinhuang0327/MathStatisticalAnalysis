"""Source-bound K3 comparison must never silently pair an unrelated result."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from copy import deepcopy
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.interfaces.api.replay_backfill import (
    _build_k3_comparison,
    create_replay_backfill_router,
)

NEW = "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116"
OLD = "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5"


def record(strategy: str, cell: str, *, winner: bool = False) -> dict[str, Any]:
    identity = {
        "cell_identity": cell,
        "lottery_type": "BIG_LOTTO",
        "strategy_id": strategy,
        "strategy_version": "v0.1" if strategy == OLD else "v1.0.0",
        "target_draw_id": "115000105",
        "target_draw_date": "2026-11-13",
    }
    tickets = [{"ticket_position": i, "main_numbers": [1, 2, 3, 4, 5, i + 5]} for i in (1, 2, 3)]
    hits = [
        {
            "ticket_position": i,
            "zone1_hits": 2,
            "zone2_hit": False,
            "prize_tier": "SEVENTH" if winner and i == 1 else None,
        }
        for i in (1, 2, 3)
    ]
    source: dict[str, Any] = {
        "source_locator": "saved-evidence:105",
        "original_source_identity": {"record": "105"},
    }
    payload: dict[str, Any] = {
        **identity,
        "execution_status": "COMPLETE",
        "predicted_tickets": tickets,
        "hit_details": hits,
        "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
        "strategy_source": source,
        "training": {"training_status": "NOT_TRAINABLE"},
    }
    if strategy == NEW:
        source.update(
            original_strategy_id=OLD, original_strategy_version="v0.1", source_segment="TEST"
        )
        payload.update(
            fair_old_q={"numerator": 1, "denominator": 10},
            fair_new_q={"numerator": 2, "denominator": 10},
        )
    return {"identity": identity, "payload": payload, "run_ids": ["real-old-run"]}


class FakeStore:
    def __init__(self, new: list[dict[str, Any]], old: list[dict[str, Any]]) -> None:
        self.new = new
        self.old = old

    def k3_comparison_payloads(
        self, run_id: str, new: str, old: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assert run_id and new == NEW and old == OLD
        return self.new, self.old


def compare(new: list[dict[str, Any]], old: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_k3_comparison(cast(SQLiteBackfillStore, FakeStore(new, old)), "optimizer")


def test_pair_by_original_cell_and_preserve_real_run() -> None:
    new, old = record(NEW, "new-cell", winner=True), record(OLD, "old-cell")
    new["payload"]["strategy_source"]["original_source_identity"] = {"cell_identity": "old-cell"}
    result = compare([new], [old])
    assert (result["paired_count"], result["old_wins"], result["new_wins"]) == (1, 0, 1)
    assert result["fair_delta"] == pytest.approx(0.1)
    assert result["observed_minus_fair"] == pytest.approx(0.9)
    assert result["rows"][0]["old"]["run_id"] == "real-old-run"


def test_fallback_requires_unique_original_source_and_reports_ambiguous() -> None:
    new, old = record(NEW, "new-cell", winner=True), record(OLD, "old-cell")
    result = compare([new], [old])
    assert result["paired_count"] == 1
    assert result["rows"][0]["match_status"] == "SOURCE_EVIDENCE"
    duplicate = deepcopy(old)
    duplicate["identity"]["cell_identity"] = "another-cell"
    result = compare([new], [old, duplicate])
    assert result["paired_count"] == 0
    assert result["unmatched_count"] == 1
    assert result["rows"][0]["old"] is None


def test_wrong_original_outcome_is_not_counted_and_duplicate_target_rejected() -> None:
    new, old = record(NEW, "new-cell"), record(OLD, "old-cell")
    new["payload"]["strategy_source"]["original_source_identity"] = {"cell_identity": "old-cell"}
    old["payload"]["winning_numbers"]["special_number"] = 8
    result = compare([new], [old])
    assert result["rows"][0]["match_status"] == "SOURCE_MISMATCH"
    assert result["paired_count"] == 0
    with pytest.raises(ValueError, match="duplicate candidate"):
        compare([new, deepcopy(new)], [old])


def test_original_identity_conflict_is_not_counted() -> None:
    new, old = record(NEW, "new-cell"), record(OLD, "old-cell")
    new["payload"]["strategy_source"]["original_source_identity"] = {
        "cell_identity": "old-cell", "dataset_identity": "expected"
    }
    old["identity"]["dataset_identity"] = "different"
    result = compare([new], [old])
    assert result["rows"][0]["match_status"] == "SOURCE_MISMATCH"
    assert result["paired_count"] == 0


def test_http_response_is_typed_and_unknown_strategy_is_rejected() -> None:
    new, old = record(NEW, "new-cell", winner=True), record(OLD, "old-cell")
    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(cast(SQLiteBackfillStore, FakeStore([new], [old])))
    )
    client = TestClient(app)
    response = client.get("/api/v1/replay-backfill/k3-comparison", params={"strategy": "optimizer"})
    assert response.status_code == 200
    assert response.json()["paired_count"] == 1
    assert (
        client.get(
            "/api/v1/replay-backfill/k3-comparison", params={"strategy": "unknown"}
        ).status_code
        == 422
    )
