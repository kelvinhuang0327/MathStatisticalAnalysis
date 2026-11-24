from fractions import Fraction
from math import comb

import pytest

from lottolab.application.replay_official_ranking import (
    RankingPeriod,
    iid_period_probability,
    score_period,
    single_ticket_probability,
    summarize_periods,
)


def test_big_lotto_seventh_prize_and_no_prize():
    draw = (1, 2, 3, 4, 5, 6)
    assert score_period("BIG_LOTTO", ((1, 2, 7, 8, 9, 10),), draw, 7) is True
    assert score_period("BIG_LOTTO", ((1, 2, 8, 9, 10, 11),), draw, 7) is False
    assert score_period("BIG_LOTTO", ((1, 2, 7, 8, 9, 10),), draw) is None
    assert score_period("BIG_LOTTO", ((1, 2, 7, 8, 9, 10), (1, 1, 2, 3, 4, 5)), draw, 7) is None


def test_daily_539_lowest_prize_and_invalid_evidence():
    draw = (1, 2, 3, 4, 5)
    assert score_period("DAILY_539", ((1, 2, 6, 7, 8),), draw) is True
    assert score_period("DAILY_539", ((1, 6, 7, 8, 9),), draw) is False
    assert score_period("DAILY_539", ((1, 1, 6, 7, 8),), draw) is None


def test_exact_probability_and_replacement():
    p = single_ticket_probability("DAILY_539")
    assert p == Fraction(sum(comb(5, h) * comb(34, 5 - h) for h in range(2, 6)), comb(39, 5))
    assert iid_period_probability("DAILY_539", 3) == 1 - (1 - p) ** 3
    assert single_ticket_probability("BIG_LOTTO") == Fraction(
        sum(
            comb(6, h) * comb(42, 6 - h - s)
            for h in range(7)
            for s in range(2)
            if 0 <= 6 - h - s <= 42 and (h >= 3 or (h == 2 and s == 1))
        ),
        comb(49, 6),
    )
    assert single_ticket_probability("POWER_LOTTO") is None
    assert iid_period_probability("POWER_LOTTO", 1) is None
    assert score_period("POWER_LOTTO", (), (), None) is None
    with pytest.raises(ValueError):
        iid_period_probability("DAILY_539", 0)
    with pytest.raises(ValueError):
        iid_period_probability("DAILY_539", True)


def test_window_summary_preserves_missing_unknown_and_dates():
    periods = [
        RankingPeriod(f"{i:03}", f"2026-01-{i:03}", "EVALUATED", i % 2 == 0, 2)
        for i in range(1, 52)
    ]
    periods[1] = RankingPeriod("002", "2026-01-002", "UNKNOWN")
    periods[2] = RankingPeriod("003", "2026-01-003", "MISSING")
    result = summarize_periods("DAILY_539", list(reversed(periods)), "RECENT_50")
    assert result["target_ids"][0] == "002"
    assert (result["evaluated"], result["unknown"], result["missing"]) == (48, 1, 1)
    assert result["successes"] == 24
    assert result["rate"] == Fraction(1, 2)
    assert result["baseline"] == iid_period_probability("DAILY_539", 2)
    assert result["delta"] == result["rate"] - result["baseline"]


def test_summary_rejects_mixed_tickets_duplicates_and_unknown_scoring():
    first = RankingPeriod("1", "2026-01-01", "EVALUATED", True, 1)
    with pytest.raises(ValueError, match="ticket counts"):
        summarize_periods(
            "BIG_LOTTO", [first, RankingPeriod("2", "2026-01-02", "EVALUATED", False, 2)], "FULL"
        )
    with pytest.raises(ValueError, match="duplicate"):
        summarize_periods("BIG_LOTTO", [first, first], "FULL")
    with pytest.raises(ValueError, match="unscorable"):
        summarize_periods("POWER_LOTTO", [first], "FULL")
    unknown = summarize_periods(
        "POWER_LOTTO", [RankingPeriod("1", "2026-01-01", "UNKNOWN")], "FULL"
    )
    assert (unknown["unknown"], unknown["rate"], unknown["baseline"], unknown["delta"]) == (
        1,
        None,
        None,
        None,
    )


def test_big_lotto_general_prize_is_included():
    assert score_period("BIG_LOTTO", ((1, 2, 3, 8, 9, 10),), (1, 2, 3, 4, 5, 6), 7) is True


def test_aggregate_requires_complete_saved_evidence_and_keeps_power_unknown():
    import json

    from lottolab.application.replay_official_ranking import aggregate_ranking

    target = {
        "run_id": "r",
        "target_draw_id": "1",
        "target_draw_date": "2026-01-01",
        "main": "[1,2,3,4,5,6]",
        "special": "[7]",
    }
    payload = {
        "expected_native_ticket_count": 1,
        "predicted_tickets": [
            {"ticket_position": 1, "main_numbers": [1, 2, 3, 8, 9, 10], "special_number": None}
        ],
        "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
    }
    cell = {
        "run_id": "r",
        "target_draw_id": "1",
        "target_draw_date": "2026-01-01",
        "strategy_id": "s",
        "strategy_version": "v",
        "execution_version": "e",
        "dataset_identity": "d",
        "execution_status": "COMPLETE",
        "expected_ticket_count": 1,
        "ticket_evidence_valid": True,
        "payload_json": json.dumps(payload),
        "tickets": [(1, "[1,2,3,8,9,10]", "[]")],
    }
    row = aggregate_ranking("BIG_LOTTO", "FULL", [target], [cell], {})[0]
    assert (row["successes"], row["evaluated"], row["rank"], row["registered"]) == (1, 1, 1, False)
    row = aggregate_ranking("BIG_LOTTO", "FULL", [target], [{**cell, "tickets": []}], {})[0]
    assert (row["unknown"], row["rate"], row["rank"]) == (1, None, None)
    row = aggregate_ranking("POWER_LOTTO", "FULL", [target], [cell], {})[0]
    assert (row["unknown"], row["rate"], row["baseline"], row["delta"], row["rank"]) == (
        1,
        None,
        None,
        None,
        None,
    )


def test_aggregate_separates_other_ticket_counts_and_execution_cohorts():
    import json

    from lottolab.application.replay_official_ranking import aggregate_ranking

    targets = [
        {
            "run_id": "r",
            "target_draw_id": str(i),
            "target_draw_date": f"2026-01-0{i}",
            "main": "[1,2,3,4,5,6]",
            "special": "[7]",
        }
        for i in (1, 2, 3)
    ]

    def cell(strategy, execution, draw, count):
        tickets = [
            {"ticket_position": i, "main_numbers": [1, 2, 3, 8, 9, 10], "special_number": None}
            for i in range(1, count + 1)
        ]
        payload = {
            "expected_native_ticket_count": count,
            "predicted_tickets": tickets,
            "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
        }
        return {
            "run_id": "r",
            "target_draw_id": str(draw),
            "target_draw_date": f"2026-01-0{draw}",
            "strategy_id": strategy,
            "strategy_version": "v",
            "execution_version": execution,
            "dataset_identity": "d",
            "execution_status": "COMPLETE",
            "expected_ticket_count": count,
            "ticket_evidence_valid": True,
            "payload_json": json.dumps(payload),
            "tickets": [(i, "[1,2,3,8,9,10]", "[]") for i in range(1, count + 1)],
        }

    mixed = aggregate_ranking(
        "BIG_LOTTO", "FULL", targets, [cell("s", "e", 1, 1), cell("s", "e", 2, 2)], {}
    )
    one = next(row for row in mixed if row["ticket_count"] == 1)
    two = next(row for row in mixed if row["ticket_count"] == 2)
    assert (one["target_ids"], one["evaluated"], one["missing"]) == (["1", "2", "3"], 1, 2)
    assert (two["target_ids"], two["evaluated"], two["missing"]) == (["1", "2", "3"], 1, 2)
    ranked = aggregate_ranking(
        "BIG_LOTTO",
        "FULL",
        targets[:1],
        [cell("s1", "e1", 1, 1), cell("s2", "e1", 1, 1), cell("s3", "e2", 1, 1)],
        {},
    )
    assert {row["strategy_id"]: row["rank"] for row in ranked} == {"s1": 1, "s2": 2, "s3": 1}
