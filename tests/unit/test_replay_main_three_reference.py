from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any

from lottolab.application.replay_main_three_reference import (
    MAIN_THREE_EVENT,
    main_three_baseline,
    main_three_reference,
)
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.application.replay_uniform_reference import uniform_eight_reference
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import ReplayExecutionCapability
from lottolab.infrastructure.persistence.replay_backfill_store import identity


def saved_cell() -> tuple[dict[str, Any], dict[str, Any]]:
    tickets = [[1, 2, 7, 8, 9, 10], [11, 12, 13, 14, 15, 16], [17, 18, 19, 20, 21, 22]]
    payload: dict[str, Any] = {
        "cell_identity": "cell-1",
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "cluster",
        "strategy_version": "v0.2",
        "dataset_identity": "research-data",
        "execution_version": "saved-v1",
        "target_draw_id": "100000001",
        "target_draw_date": "2020-01-01",
        "execution_status": "COMPLETE",
        "expected_native_ticket_count": 3,
        "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
        "predicted_tickets": [
            {"ticket_position": i, "main_numbers": numbers, "special_number": None}
            for i, numbers in enumerate(tickets, 1)
        ],
        "hit_details": [
            {"ticket_position": 1, "zone1_hits": 2, "zone2_hit": True},
            {"ticket_position": 2, "zone1_hits": 0, "zone2_hit": False},
            {"ticket_position": 3, "zone1_hits": 0, "zone2_hit": False},
        ],
        "research_success_event": MAIN_THREE_EVENT,
        "research_success": False,
        "research_scorer_version": "fixed-scorer-v1",
    }
    return seal(payload)


def seal(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload.pop("result_identity", None)
    payload["result_identity"] = identity(payload)
    stored = {
        key: payload[key]
        for key in (
            "cell_identity",
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "dataset_identity",
            "execution_version",
            "result_identity",
            "target_draw_id",
            "target_draw_date",
        )
    }
    stored["run_id"] = "run-1"
    return payload, stored


def checked_main_three(payload: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    result = main_three_reference(payload, stored)
    assert result is not None
    return result


def checked_uniform_eight(payload: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    result = uniform_eight_reference(payload, stored)
    assert result is not None
    return result


def test_research_event_is_distinct_from_eight_tier_and_has_exact_baseline() -> None:
    payload, stored = saved_cell()
    assert checked_uniform_eight(payload, stored)["any_prize"] is True
    assert main_three_reference(payload, stored) == {
        "metric_id": MAIN_THREE_EVENT,
        "status": "SCORABLE",
        "success": False,
        "scorer_version": "fixed-scorer-v1",
    }
    assert main_three_baseline(payload) == Fraction(32528, 582659)


def test_research_event_requires_explicit_declaration_and_consistent_saved_evidence() -> None:
    payload, stored = saved_cell()
    missing = deepcopy(payload)
    missing.pop("research_success_event")
    assert main_three_reference(missing, stored) is None
    wrong_success = deepcopy(payload)
    wrong_success["research_success"] = True
    wrong_success, wrong_stored = seal(wrong_success)
    assert checked_main_three(wrong_success, wrong_stored)["status"] == "UNKNOWN"
    wrong_hits = deepcopy(payload)
    wrong_hits["hit_details"][0]["zone1_hits"] = 3
    wrong_hits, wrong_stored = seal(wrong_hits)
    assert checked_main_three(wrong_hits, wrong_stored)["status"] == "UNKNOWN"
    wrong_identity = {**stored, "dataset_identity": "another-source"}
    assert checked_main_three(payload, wrong_identity)["status"] == "UNKNOWN"
    wrong_digest = deepcopy(payload)
    wrong_digest["research_success"] = True
    assert checked_main_three(wrong_digest, stored)["status"] == "UNKNOWN"


def test_main_three_does_not_depend_on_special_number_or_prize_evidence() -> None:
    payload, _ = saved_cell()
    payload["winning_numbers"].pop("special_number")
    for hit in payload["hit_details"]:
        hit.pop("zone2_hit")
    payload, stored = seal(payload)
    assert checked_uniform_eight(payload, stored)["status"] == "UNKNOWN"
    assert checked_main_three(payload, stored)["status"] == "SCORABLE"
    assert checked_main_three(payload, stored)["success"] is False


def test_failure_and_duplicate_positions_remain_unknown_not_losses() -> None:
    payload, _ = saved_cell()
    payload["execution_status"] = "FAILED"
    payload["research_success"] = None
    payload["predicted_tickets"] = []
    payload["hit_details"] = []
    payload, stored = seal(payload)
    assert checked_main_three(payload, stored)["status"] == "UNKNOWN"
    payload, _ = saved_cell()
    payload["predicted_tickets"][1]["ticket_position"] = 1
    payload, stored = seal(payload)
    assert checked_main_three(payload, stored)["status"] == "UNKNOWN"


def test_cluster_research_version_is_visible_without_claiming_executable() -> None:
    items = load_replay_strategy_inventory().items
    same_id = [
        item
        for item in items
        if item.lottery_type is LotteryType.BIG_LOTTO
        and item.strategy_id == "legacy_biglotto__test_cluster_cover__5b43959e7c55"
    ]
    research = [item for item in same_id if item.strategy_version == "v0.2-research-frequency100"]
    assert len(research) == 1
    assert research[0].execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert research[0].backfill_native_binding is not True
    assert any(item.strategy_version == "v0.1" for item in same_id)
