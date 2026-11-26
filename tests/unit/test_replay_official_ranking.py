import json
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
    assert p is not None
    assert p == Fraction(sum(comb(5, h) * comb(34, 5 - h) for h in range(2, 6)), comb(39, 5))
    assert iid_period_probability("DAILY_539", 3) == 1 - (1 - p) ** 3
    assert single_ticket_probability("BIG_LOTTO") == Fraction(
        sum(
            comb(6, h) * comb(42, 6 - h - s)
            for h in range(7)
            for s in range(2)
            if 0 <= 6 - h - s <= 42 and (h >= 4 or (h == 3 and s == 1) or (h == 2 and s == 1))
        ),
        comb(49, 6),
    )
    assert (
        single_ticket_probability("BIG_LOTTO")
        == Fraction(203224, 13983816)
        == Fraction(3629, 249711)
    )
    assert iid_period_probability("BIG_LOTTO", 2) == Fraction(1799232797, 62355583521)
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
    assert 0 <= result["successes"] <= result["evaluated"]
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


def test_big_lotto_general_prize_is_excluded():
    assert score_period("BIG_LOTTO", ((1, 2, 3, 8, 9, 10),), (1, 2, 3, 4, 5, 6), 7) is False


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
    assert (row["successes"], row["evaluated"], row["rank"], row["registered"], row["rate"]) == (
        0,
        1,
        1,
        False,
        0.0,
    )
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

    def cell(strategy: str, execution: str, draw: int, count: int) -> dict[str, object]:
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


def test_numeric_draw_tiebreak_at_recent_window_boundary():
    tied = [RankingPeriod(i, "2024-01-01", "EVALUATED", i == "31", 1) for i in ("9", "10", "31")]
    later = [
        RankingPeriod(f"later-{i}", f"2024-02-{i:02}", "EVALUATED", False, 1) for i in range(1, 50)
    ]
    result = summarize_periods("BIG_LOTTO", list(reversed(tied + later)), "RECENT_50")
    assert [i for i in result["target_ids"] if i in ("9", "10", "31")] == ["31"]
    assert (result["successes"], result["evaluated"]) == (1, 50)


def test_draw_order_dates_leading_zero_and_non_ascii_or_nonnumeric():
    ids = ["x", "10", "09", "9", "31", "\uff19", "A"]
    periods = [RankingPeriod(i, "2024-01-01", "EVALUATED", False, 1) for i in ids]
    periods += [RankingPeriod("0", "2024-01-02", "EVALUATED", False, 1)]
    result = summarize_periods("BIG_LOTTO", periods, "FULL")
    assert result["target_ids"] == ["09", "9", "10", "31", "A", "x", "\uff19", "0"]


def _ranking_cell(
    strategy_id: str,
    ticket_main: tuple[int, ...] | None,
) -> dict[str, object]:
    tickets = [] if ticket_main is None else [(1, json.dumps(ticket_main), "[]")]
    return {
        "run_id": "r",
        "target_draw_id": "1",
        "target_draw_date": "2026-01-01",
        "strategy_id": strategy_id,
        "strategy_version": "v1",
        "execution_version": "e1",
        "dataset_identity": "d1",
        "execution_status": "COMPLETE",
        "ticket_count": 1,
        "ticket_evidence_valid": ticket_main is not None,
        "tickets": tickets,
    }


def test_aggregate_ranking_orders_float_collision_by_exact_rate(monkeypatch):
    from lottolab.application import replay_official_ranking as ranking

    evaluated = 18_014_398_509_481_984
    synthetic_summaries = iter(
        (
            ("a-low", 9_007_199_254_740_992),
            ("z-high", 9_007_199_254_740_993),
        )
    )

    def synthetic_summary(_lottery_type, _periods, _window):
        _strategy_id, successes = next(synthetic_summaries)
        rate = Fraction(successes, evaluated)
        return {
            "target_ids": ["1"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "successes": successes,
            "evaluated": evaluated,
            "missing": 0,
            "unknown": 0,
            "rate": rate,
            "baseline": Fraction(1, 4),
            "delta": rate - Fraction(1, 4),
        }

    monkeypatch.setattr(ranking, "summarize_periods", synthetic_summary)
    rows = ranking.aggregate_ranking(
        "BIG_LOTTO",
        "FULL",
        [],
        [_ranking_cell("a-low", None), _ranking_cell("z-high", None)],
        {},
    )

    low = next(row for row in rows if row["strategy_id"] == "a-low")
    high = next(row for row in rows if row["strategy_id"] == "z-high")
    assert Fraction(low["successes"], low["evaluated"]) == Fraction(1, 2)
    assert Fraction(high["successes"], high["evaluated"]) > Fraction(1, 2)
    assert low["rate"] == high["rate"] == 0.5
    assert (high["rank"], low["rank"]) == (1, 2)
    assert json.loads(json.dumps(rows))[0]["rate"] == 0.5


def test_aggregate_ranking_uses_exact_rate_then_strategy_id_for_real_cohort():
    from lottolab.application.replay_official_ranking import aggregate_ranking

    targets = [
        {
            "run_id": "r",
            "target_draw_id": "1",
            "target_draw_date": "2026-01-01",
            "main": "[1,2,3,4,5,6]",
            "special": "[7]",
        }
    ]
    rows = aggregate_ranking(
        "BIG_LOTTO",
        "FULL",
        targets,
        [
            _ranking_cell("a-low", (1, 2, 8, 9, 10, 11)),
            _ranking_cell("z-high", (1, 2, 7, 8, 9, 10)),
            _ranking_cell("m-high", (1, 2, 7, 8, 9, 10)),
        ],
        {},
    )

    ranked = sorted(rows, key=lambda row: row["rank"])
    assert [(row["strategy_id"], row["rank"]) for row in ranked] == [
        ("m-high", 1),
        ("z-high", 2),
        ("a-low", 3),
    ]
    assert [(row["successes"], row["evaluated"], row["rate"]) for row in ranked] == [
        (1, 1, 1.0),
        (1, 1, 1.0),
        (0, 1, 0.0),
    ]
    assert json.loads(json.dumps(rows))
