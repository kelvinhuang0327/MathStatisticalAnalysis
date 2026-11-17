# pyright: reportPrivateUsage=false
from copy import deepcopy
from math import comb
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.replay_uniform_reference import uniform_eight_reference
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.interfaces.api.replay_backfill import _prediction_item, create_replay_backfill_router


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


def _example(k: int = 3) -> tuple[dict[str, Any], dict[str, Any]]:
    identity: dict[str, Any] = {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "candidate",
        "strategy_version": "v1",
        "target_draw_id": "103000080",
        "target_draw_date": "2014-09-23",
        "cell_identity": "cell",
        "run_id": "run",
    }
    tickets: list[dict[str, Any]] = [
        {"ticket_position": 1, "main_numbers": [1, 2, 3, 4, 5, 6], "special_number": None}
    ]
    hits: list[dict[str, Any]] = [
        {"ticket_position": 1, "zone1_hits": 2, "zone2_hit": True, "prize_tier": "SEVENTH"}
    ]
    for n in range(2, k + 1):
        tickets.append(
            {"ticket_position": n, "main_numbers": [20, 21, 22, 23, 24, 25], "special_number": None}
        )
        hits.append({"ticket_position": n, "zone1_hits": 0, "zone2_hit": False, "prize_tier": None})
    payload: dict[str, Any] = {key: value for key, value in identity.items() if key != "run_id"}
    payload.update(
        {
            "execution_status": "COMPLETE",
            "expected_native_ticket_count": k,
            "predicted_tickets": tickets,
            "hit_details": hits,
            "winning_numbers": {"main_numbers": [1, 2, 11, 12, 13, 14], "special_number": 3},
            "source_history_provenance_status": "UNKNOWN",
            "training": {},
        }
    )
    return payload, identity


@pytest.mark.parametrize("k", [3, 6, 20])
def test_reference_uses_same_event_for_k_and_preserves_official_projection(k: int) -> None:
    payload, identity = _example(k)
    before = deepcopy(payload)
    view = _prediction_item(payload, identity, None)
    assert view["portfolio_any_prize"] is False
    assert view["uniform_eight_reference"] == {
        "status": "SCORABLE",
        "ticket_count": k,
        "any_prize": True,
    }
    assert payload == before


@pytest.mark.parametrize("defect", ["special", "ticket", "hit", "identity"])
def test_incomplete_or_inconsistent_evidence_is_unknown(defect: str) -> None:
    payload, identity = _example()
    if defect == "special":
        payload["winning_numbers"]["special_number"] = None
    elif defect == "ticket":
        payload["predicted_tickets"].pop()
    elif defect == "hit":
        payload["hit_details"][0]["zone1_hits"] = 0
    else:
        identity["target_draw_id"] = "different"
    assert uniform_eight_reference(payload, identity) == {
        "status": "UNKNOWN",
        "ticket_count": 3,
        "any_prize": None,
    }


def test_summary_paginates_and_excludes_unknown_without_losing_provenance() -> None:
    template, base = _example()
    rows: list[dict[str, Any]] = []
    for n in range(251):
        payload, identity = deepcopy(template), deepcopy(base)
        identity.update({"target_draw_id": str(100000000 + n), "cell_identity": f"cell-{n}"})
        payload.update(
            {
                "target_draw_id": identity["target_draw_id"],
                "cell_identity": identity["cell_identity"],
            }
        )
        if n == 250:
            payload["winning_numbers"]["special_number"] = None
        rows.append(
            {
                "payload": payload,
                "identity": identity,
                "key": [
                    identity["target_draw_date"],
                    100000000 + n,
                    "candidate",
                    "v1",
                    f"cell-{n}",
                ],
            }
        )

    class Store:
        def prediction_page(self, **kwargs: Any) -> dict[str, Any]:
            after = kwargs["after"]
            start = 0 if after is None else int(after[1]) - 100000000 + 1
            return {"run_id": "run", "total_count": 251, "rows": rows[start : start + 251]}

    app = FastAPI()
    app.include_router(create_replay_backfill_router(Store()))  # type: ignore[arg-type]
    response = cast(JsonTestClient, TestClient(app)).get(
        "/api/v1/replay-backfill/uniform-eight-reference",
        params={"strategy_id": "candidate", "run_id": "run"},
    )
    assert response.status_code == 200
    assert response.json()["groups"] == [
        {
            "strategy_version": "v1",
            "ticket_count": 3,
            "scorable_draws": 250,
            "unknown_draws": 1,
            "successes": 250,
            "success_rate_percent": 100.0,
            "unknown_provenance_draws": 251,
            "baseline_kind": "UNKNOWN",
            "baseline_success_rate_percent": None,
            "difference_from_baseline_pp": None,
        }
    ]


def test_reference_run_does_not_replace_default_historical_run(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(tmp_path / "replay.sqlite3")
    base = {"lottery_type": "BIG_LOTTO", "expected_cells": 1, "dataset_identity": "source"}
    store.prepare({**base, "run_id": "historical"})
    store.prepare({**base, "run_id": "reference", "reference_projection": {"version": 1}})
    with store.write_transaction() as connection:
        connection.execute(
            "UPDATE replay_backfill_runs SET created_at='2020-01-01' WHERE run_id='historical'"
        )
        connection.execute(
            "UPDATE replay_backfill_runs SET created_at='2026-01-01' WHERE run_id='reference'"
        )
    assert store.latest_run_id("BIG_LOTTO") == "historical"
    assert store.strategy_history_snapshot("BIG_LOTTO")["run_id"] == "historical"
    assert store.strategy_history_snapshot("BIG_LOTTO", run_id="reference")["run_id"] == "reference"


def test_persisted_reference_conflict_fails_closed() -> None:
    payload, identity = _example()

    class Store:
        def prediction_page(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "run_id": "run",
                "total_count": 1,
                "rows": [{"payload": payload, "identity": identity}],
            }

        def run_manifest(self, run_id: str) -> dict[str, Any]:
            return {
                "reference_projection": {
                    "metric_id": "REFERENCE_FIXED_EIGHT_TIER_ANY_PRIZE",
                    "outcomes_by_cell": {"cell": False},
                }
            }

    app = FastAPI()
    app.include_router(create_replay_backfill_router(Store()))  # type: ignore[arg-type]
    response = cast(JsonTestClient, TestClient(app)).get(
        "/api/v1/replay-backfill/uniform-eight-reference",
        params={"strategy_id": "candidate", "run_id": "run"},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "REFERENCE_EVIDENCE_MISMATCH"


def test_disjoint_k3_baseline_is_an_explicit_theoretical_comparison() -> None:
    payload, identity = _example()
    payload["predicted_tickets"][2]["main_numbers"] = [30, 31, 32, 33, 34, 35]

    class Store:
        def prediction_page(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "run_id": "run",
                "total_count": 1,
                "rows": [
                    {
                        "payload": payload,
                        "identity": identity,
                    }
                ],
            }

    app = FastAPI()
    app.include_router(create_replay_backfill_router(Store()))  # type: ignore[arg-type]
    result = cast(JsonTestClient, TestClient(app)).get(
        "/api/v1/replay-backfill/uniform-eight-reference",
        params={"strategy_id": "candidate", "run_id": "run"},
    )
    assert result.status_code == 200
    group = result.json()["groups"][0]
    total = comb(49, 6) * 43
    losses = 0
    for a in range(3):
        for b in range(3):
            for c in range(3):
                rest = 6 - a - b - c
                if 0 <= rest <= 31:
                    losses += (
                        comb(6, a)
                        * comb(6, b)
                        * comb(6, c)
                        * comb(31, rest)
                        * (43 - 4 * sum(n == 2 for n in (a, b, c)))
                    )
    baseline = 100 * (total - losses) / total
    assert group["baseline_kind"] == "UNIFORM_RANDOM_DISJOINT_K3"
    assert group["baseline_success_rate_percent"] == pytest.approx(baseline)
    assert group["difference_from_baseline_pp"] == pytest.approx(100 - baseline)
