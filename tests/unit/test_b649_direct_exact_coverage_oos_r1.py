from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools/evaluate_b649_direct_exact_coverage_oos_r1.py"
SPEC = importlib.util.spec_from_file_location("b649_direct_exact_coverage_oos_r1", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def _paired_row(
    candidate: bool, sealed: bool, *, candidate_hash: str = "candidate", sealed_hash: str = "sealed"
) -> dict[str, object]:
    return {
        "candidate_win": candidate,
        "sealed_v6_win": sealed,
        "candidate_portfolio_sha256_k10": candidate_hash,
        "sealed_v6_portfolio_sha256_k10": sealed_hash,
    }


def test_exact_mcnemar_uses_two_sided_conditional_binomial_tail() -> None:
    assert replay.exact_mcnemar_two_sided(5, 0) == Fraction(1, 16)
    assert replay.exact_mcnemar_two_sided(6, 0) == Fraction(1, 32)
    assert replay.exact_mcnemar_two_sided(3, 3) == Fraction(1, 1)
    assert replay.exact_mcnemar_two_sided(0, 0) == Fraction(1, 1)


def test_pair_summary_accounts_for_all_four_paired_outcomes() -> None:
    rows = [
        _paired_row(True, False),
        _paired_row(False, True),
        _paired_row(True, True),
        _paired_row(False, False),
    ]
    summary = replay.summarize_pairs(rows, 10)

    assert summary["eligible_paired_draws"] == 4
    assert summary["candidate_wins"] == 2
    assert summary["sealed_v6_wins"] == 2
    assert summary["candidate_only"] == 1
    assert summary["sealed_only"] == 1
    assert summary["both_win"] == 1
    assert summary["both_lose"] == 1
    assert summary["discordant_count"] == 2
    assert summary["absolute_delta_fraction"] == "0/1"
    assert summary["relative_lift_fraction"] == "0/1"
    assert summary["paired_statistical_evidence"]["exact_p_value_fraction"] == "1/1"
    assert summary["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_no_decision_leverage_requires_identical_portfolios() -> None:
    rows = [_paired_row(True, True, candidate_hash="same", sealed_hash="same")]
    assert replay.summarize_pairs(rows, 10)["verdict"] == "NO_DECISION_LEVERAGE"


def test_prediction_input_must_be_strictly_predraw_and_outcome_free() -> None:
    expected = {
        "stream-a": {
            "strategy_version": "v1",
            "native_ticket_count": 1,
            "strategy_config": {},
            "producer_fingerprint": "producer",
            "pinned_implementation": "commit",
        }
    }
    record = {
        "schema_version": replay.PREDICTION_SCHEMA,
        "task_id": "B649_OPERATIONAL_PREDICTION_LOOP_R1",
        "lottery_type": "BIG_LOTTO",
        "draw_number": "115000081",
        "draw_date": "2026-08-21",
        "scheduled_at": "2026-08-21T20:30:00+08:00",
        "prediction_created_at": "2026-08-21T15:00:00+08:00",
        "strategy_id": "stream-a",
        "strategy_version": "v1",
        "strategy_config": {},
        "producer_fingerprint": "producer",
        "pinned_implementation": "commit",
        "native_ticket_count": 1,
        "availability": "AVAILABLE",
        "prediction_temporal_class": "PRE_DRAW",
        "history_cutoff": {"draw_number": "115000080", "draw_date": "2026-08-18"},
        "history_draw_count": 2000,
        "history_sha256": "a" * 64,
        "tickets": [{"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}],
    }

    assert (
        replay._validate_prediction_record(record, target="115000081", expected_streams=expected)[0]
        == "stream-a"
    )

    post_draw = dict(record, prediction_created_at=record["scheduled_at"])
    with pytest.raises(replay.ReplayInputError, match="not created before draw"):
        replay._validate_prediction_record(post_draw, target="115000081", expected_streams=expected)

    outcome_bearing = dict(record, winning_main_numbers=[1, 2, 3, 4, 5, 6])
    with pytest.raises(replay.ReplayInputError, match="outcome-bearing"):
        replay._validate_prediction_record(
            outcome_bearing, target="115000081", expected_streams=expected
        )
