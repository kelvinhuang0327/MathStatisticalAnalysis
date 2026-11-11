"""Research qualification must not rewrite the native positional record."""

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.replay_backfill_store import (
    SQLiteBackfillStore,
    _research_portfolio_context,
    identity,
)
from lottolab.interfaces.api.replay_backfill import (
    _prediction_item,
    create_replay_backfill_router,
)

A = [1, 2, 3, 4, 5, 6]
B = [7, 8, 9, 10, 11, 12]
C = [13, 14, 15, 16, 17, 18]
D = [19, 20, 21, 22, 23, 24]
E = [25, 26, 27, 28, 29, 30]


def _fixture(
    tmp_path: Path,
    combinations: list[list[int]],
    *,
    source_hash: str = "fixture-hash",
    training_present: bool = True,
) -> tuple[TestClient, dict, SQLiteBackfillStore]:
    target = {
        "draw_number": "123",
        "draw_date": "2026-01-02",
        "main_numbers": A,
        "special_numbers": [],
        "source_identity": "dataset",
    }
    manifest = {
        "run_id": "test-run",
        "lottery_type": "BIG_LOTTO",
        "dataset_identity": "dataset",
        "source_locator": "fixture://sealed",
        "source_hash": source_hash,
        "expected_cells": 1,
        "strategies": [
            {
                "strategy_id": "strategy",
                "strategy_version": "v1",
                "strategy_name": "Example",
                "native_ticket_count": 5,
            }
        ],
        "targets": [target],
    }
    result = {
        "cell_identity": "cell",
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "strategy",
        "strategy_version": "v1",
        "execution_version": "test",
        "dataset_identity": "dataset",
        "target_draw_id": "123",
        "target_draw_date": "2026-01-02",
        "execution_status": "COMPLETE",
        "expected_native_ticket_count": 5,
        "predicted_tickets": [
            {"ticket_position": i, "main_numbers": numbers}
            for i, numbers in enumerate(combinations, 1)
        ],
        "hit_details": [],
        "winning_numbers": {"main_numbers": A},
        "training": {"training_status": "UNKNOWN"},
    }
    if not training_present:
        del result["training"]
    result["result_identity"] = identity(result)
    store = SQLiteBackfillStore(tmp_path / "candidate.sqlite")
    store.prepare(manifest)
    store.save("test-run", result)
    app = FastAPI()
    app.include_router(create_replay_backfill_router(store))
    return TestClient(app), result, store


def _item(client: TestClient) -> dict:
    response = client.get(
        "/api/v1/replay-backfill/predictions",
        params={"lottery_type": "BIG_LOTTO", "run_id": "test-run"},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


def test_duplicate_positions_are_flagged_without_changing_native_record(tmp_path: Path) -> None:
    client, original, store = _fixture(tmp_path, [A, B, A, B, C])
    item = _item(client)
    assert item["prediction_status"] == "COMPLETE"
    assert [ticket["main_numbers"] for ticket in item["predicted_tickets"]] == [A, B, A, B, C]
    assert item["research_portfolio_qualification"] == {
        "status": "FAIL",
        "reason_code": "DUPLICATE_MAIN_NUMBER_COMBINATION",
        "duplicate_groups": [
            {"main_numbers": A, "positions": [1, 3]},
            {"main_numbers": B, "positions": [2, 4]},
        ],
        "import_qualification": "NOT_QUALIFIED",
    }
    assert store.lookup("cell") == original


def test_distinct_combinations_do_not_establish_import_qualification(tmp_path: Path) -> None:
    client, original, store = _fixture(tmp_path, [A, B, C, D, E])
    assessment = _item(client)["research_portfolio_qualification"]
    assert assessment == {
        "status": "PASS",
        "reason_code": None,
        "duplicate_groups": [],
        "import_qualification": "UNKNOWN",
    }
    assert store.lookup("cell") == original


def test_existing_metric_display_is_unchanged_for_complete_tickets(tmp_path: Path) -> None:
    _, original, _ = _fixture(tmp_path, [A, B, A, B, C])
    original["hit_details"] = [{"zone1_hits": 3, "zone2_hit": False, "prize_tier": "SIXTH"}]
    result = _prediction_item(original)
    assert result["portfolio_any_prize"] is True
    assert result["best_main_hits"] == 3
    assert result["predicted_tickets"][0]["main_hit_count"] == 3
    assert result["predicted_tickets"][0]["prize_tier"] == "SIXTH"


def test_reordered_numbers_count_as_same_combination(tmp_path: Path) -> None:
    client, _, _ = _fixture(tmp_path, [A, B, list(reversed(A)), D, E])
    assessment = _item(client)["research_portfolio_qualification"]
    assert assessment["status"] == "FAIL"
    assert assessment["duplicate_groups"] == [{"main_numbers": A, "positions": [1, 3]}]


def test_missing_ticket_and_source_binding_do_not_qualify(tmp_path: Path) -> None:
    client, original, _ = _fixture(tmp_path, [A, B, C, D])
    assessment = _item(client)["research_portfolio_qualification"]
    assert assessment["status"] == "UNKNOWN"
    assert assessment["import_qualification"] == "UNKNOWN"
    assert original["execution_status"] == "COMPLETE"


def test_direct_consumer_keeps_missing_source_unknown(tmp_path: Path) -> None:
    client, _, _ = _fixture(tmp_path, [A, B, C, D, E], source_hash="")
    assessment = _item(client)["research_portfolio_qualification"]
    assert assessment["status"] == "UNKNOWN"
    assert assessment["reason_code"] == "SOURCE_OR_STRATEGY_EVIDENCE_INCOMPLETE"
    assert assessment["import_qualification"] == "UNKNOWN"


def test_missing_training_evidence_remains_unknown(tmp_path: Path) -> None:
    client, original, store = _fixture(tmp_path, [A, B, C, D, E], training_present=False)
    assert _item(client)["training"]["training_status"] == "UNKNOWN"
    assert store.lookup("cell") == original
    with store._connect() as connection:
        assert connection.execute(
            "SELECT training_status FROM replay_backfill_training"
        ).fetchone() == ("UNKNOWN",)
        assert connection.execute(
            "SELECT training_status FROM replay_backfill_strategy_inventory"
        ).fetchone() == ("UNKNOWN",)


def test_incomplete_fields_are_unknown_without_mutating_input() -> None:
    from lottolab.application.replay_portfolio_qualification import assess_research_portfolio

    tickets = [{"ticket_position": 1, "main_numbers": A}, {"main_numbers": B}]
    before = deepcopy(tickets)
    result = assess_research_portfolio(tickets, 2, source_bound=True, execution_status="COMPLETE")
    assert result["status"] == "UNKNOWN"
    assert result["import_qualification"] == "UNKNOWN"
    assert tickets == before
    tickets[1] = {"ticket_position": 2}
    assert (
        assess_research_portfolio(tickets, 2, source_bound=True, execution_status="COMPLETE")[
            "status"
        ]
        == "UNKNOWN"
    )
    tickets[1] = {"ticket_position": 2, "main_numbers": B}
    assert (
        assess_research_portfolio(tickets, 2, source_bound=False, execution_status="COMPLETE")[
            "status"
        ]
        == "UNKNOWN"
    )
    tickets[1]["special_number"] = 50
    assert (
        assess_research_portfolio(tickets, 2, source_bound=True, execution_status="COMPLETE")[
            "status"
        ]
        == "UNKNOWN"
    )


@pytest.mark.parametrize("count", [2, 3, 5])
def test_uniqueness_contract_covers_each_supported_native_count(count: int) -> None:
    from lottolab.application.replay_portfolio_qualification import assess_research_portfolio

    numbers = [A, B, C, D, E][:count]
    tickets = [{"ticket_position": i, "main_numbers": value} for i, value in enumerate(numbers, 1)]
    assert (
        assess_research_portfolio(tickets, count, source_bound=True, execution_status="COMPLETE")[
            "status"
        ]
        == "PASS"
    )
    tickets[-1]["main_numbers"] = list(reversed(A))
    assert (
        assess_research_portfolio(tickets, count, source_bound=True, execution_status="COMPLETE")[
            "status"
        ]
        == "FAIL"
    )


def test_strategy_count_and_record_digest_must_bind_to_the_manifest(tmp_path: Path) -> None:
    _, original, store = _fixture(tmp_path, [A, B, C, D, E])
    manifest = store.run_manifest("test-run")
    stored = {
        key: original[key]
        for key in (
            "target_draw_date",
            "target_draw_id",
            "strategy_id",
            "strategy_version",
            "cell_identity",
            "dataset_identity",
            "execution_version",
            "result_identity",
        )
    }
    assert _research_portfolio_context(
        manifest, original, "test-run", "BIG_LOTTO", stored_identity=stored
    )["source_bound"]
    changed = deepcopy(original)
    changed["predicted_tickets"][0]["main_numbers"] = B
    assert not _research_portfolio_context(
        manifest, changed, "test-run", "BIG_LOTTO", stored_identity=stored
    )["source_bound"]
    changed = deepcopy(manifest)
    changed["strategies"][0]["native_ticket_count"] = 3
    assert not _research_portfolio_context(
        changed, original, "test-run", "BIG_LOTTO", stored_identity=stored
    )["source_bound"]
    changed = deepcopy(original)
    changed["predicted_tickets"][0]["strategy_id"] = "foreign-strategy"
    changed["result_identity"] = identity(
        {k: v for k, v in changed.items() if k != "result_identity"}
    )
    stored["result_identity"] = changed["result_identity"]
    assert not _research_portfolio_context(
        manifest, changed, "test-run", "BIG_LOTTO", stored_identity=stored
    )["source_bound"]


def test_prediction_consumer_exposes_missing_fields_as_unknown(tmp_path: Path) -> None:
    _, _, store = _fixture(tmp_path, [A, B, C, D, E])
    row = store.prediction_page(
        lottery_type="BIG_LOTTO",
        run_id="test-run",
        strategy_id=None,
        from_date=None,
        to_date=None,
        period=None,
        limit=5,
    )["rows"][0]
    for missing in ("main_numbers", "ticket_position"):
        payload = deepcopy(row["payload"])
        del payload["predicted_tickets"][0][missing]
        result = _prediction_item(payload, row["portfolio_context"])
        assert result["research_portfolio_qualification"]["status"] == "UNKNOWN"
        assert result["research_portfolio_qualification"]["import_qualification"] == "UNKNOWN"
        assert result["predicted_tickets"][0][missing] is None
        assert result["portfolio_any_prize"] is None
        assert result["best_main_hits"] is None
