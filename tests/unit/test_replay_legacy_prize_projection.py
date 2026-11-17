# pyright: reportPrivateUsage=false

from copy import deepcopy

import pytest

from lottolab.infrastructure.persistence.replay_backfill_store import JsonObject
from lottolab.interfaces.api.replay_backfill import _historical_prize_tier, _prediction_item


@pytest.mark.parametrize(
    ("lottery", "draw", "main", "special", "tier", "expected"),
    [
        ("BIG_LOTTO", "103000080", 2, True, "SEVENTH", None),
        ("BIG_LOTTO", "103000081", 2, True, "SEVENTH", "SEVENTH"),
        ("BIG_LOTTO", "97000052", 3, True, "SIXTH", "SIXTH"),
        ("DAILY_539", "97000052", 2, True, "SEVENTH", "SEVENTH"),
        ("BIG_LOTTO", "unknown", 2, True, "SEVENTH", "SEVENTH"),
        ("BIG_LOTTO", "97000052", True, True, "SEVENTH", "SEVENTH"),
    ],
)
def test_historical_tier_boundary(
    lottery: str, draw: str, main: int, special: bool, tier: str, expected: str | None
) -> None:
    assert (
        _historical_prize_tier(
            {"lottery_type": lottery, "target_draw_id": draw},
            {"zone1_hits": main, "zone2_hit": special, "prize_tier": tier},
        )
        == expected
    )


@pytest.mark.parametrize(("draw", "expected"), [("103000080", False), ("103000081", True)])
def test_portfolio_projection_uses_drawing_period_without_changing_source(
    draw: str, expected: bool
) -> None:
    identity: JsonObject = {
        "cell_identity": "cell",
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "legacy-test",
        "strategy_version": "v0.1",
        "target_draw_id": draw,
        "target_draw_date": "2014-01-01",
        "run_id": "test-run",
    }
    payload: JsonObject = {
        **{key: value for key, value in identity.items() if key != "run_id"},
        "execution_status": "COMPLETE",
        "predicted_tickets": [
            {"ticket_position": 1, "main_numbers": [1, 2, 3, 4, 5, 6], "special_number": None},
        ],
        "hit_details": [{"zone1_hits": 2, "zone2_hit": True, "prize_tier": "SEVENTH"}],
        "winning_numbers": {"main_numbers": [1, 2, 11, 12, 13, 14], "special_number": 3},
        "training": {},
    }
    original = deepcopy(payload)
    item = _prediction_item(payload, identity, None)
    assert item["identity_status"] == "VERIFIED"
    assert item["portfolio_any_prize"] is expected
    assert item["predicted_tickets"][0]["prize_tier"] == ("SEVENTH" if expected else None)
    assert payload == original
