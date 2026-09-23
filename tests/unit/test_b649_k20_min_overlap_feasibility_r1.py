"""Feasibility estimate for the K=20 minimum-overlap family. Not an enumeration."""

from __future__ import annotations

import json
from fractions import Fraction

import pytest

from lottolab.research.b649_k20_min_overlap_feasibility_r1 import (
    BASELINE_FRACTION,
    RECORD_PATH,
    baseline_fingerprint,
    class_set_sha256,
    color_preserving_canonical_id,
    comparison_label,
    configuration_stubs,
    hard_div_k20,
    k20_overlap_proof,
    rejection_reason,
    score_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

ALLOWED_DECISIONS = {
    "K20_EXHAUSTIVE_FEASIBLE",
    "K20_REQUIRES_SHARDING",
    "K20_REQUIRES_CANONICAL_BRANCH_AND_BOUND",
    "K20_FULL_ENUMERATION_NOT_CURRENTLY_FEASIBLE",
}


def test_k20_minimum_overlap_profile_is_proved() -> None:
    proof = k20_overlap_proof()
    assert proof["minimum_mass"] == 93
    assert proof["histogram"] == {"2": 27, "3": 22}
    assert proof["profile_unique"] is True
    assert int(proof["outside_frequency_min_mass"]["0"]) > 93
    assert int(proof["outside_frequency_min_mass"]["4"]) > 93


def test_legality_reasons_for_duplicate_and_repeated_numbers() -> None:
    repeated = [tuple(range(6)) for _ in range(20)]
    repeated[0] = (0, 0, 1, 2, 3, 4)
    assert rejection_reason(repeated) == "repeated_number"
    duplicate = [tuple(range(6)) for _ in range(20)]
    duplicate[1] = duplicate[0]
    assert rejection_reason(duplicate) == "duplicate_ticket"
    assert rejection_reason("incidence_profile") == "incidence_profile"


def test_color_preserving_digest_is_stable_on_one_legal_draw() -> None:
    import random

    generator = random.Random(11)
    found = None
    for _ in range(20000):
        outcome = configuration_stubs(generator)
        if rejection_reason(outcome) is None:
            found = outcome
            break
    assert isinstance(found, list)
    first = color_preserving_canonical_id(found)
    second = color_preserving_canonical_id(found)
    assert first == second
    assert class_set_sha256([first]) == class_set_sha256([second])


def test_record_scores_match_the_canonical_evaluator() -> None:
    if not RECORD_PATH.exists():
        pytest.skip("pilot record is written by the bounded run")
    record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    assert record["feasibility_decision"] in ALLOWED_DECISIONS
    assert record["global_optimum_status"] == "UNKNOWN"
    assert record["discovery_saturation"] == "NOT_REACHED"
    assert record["next_task_started"] is False
    assert record["exhaustive_claim"] is False
    assert record["class_set_sha256_run_1"] == record["class_set_sha256_run_2"]
    assert record["pilot_raw_count"] <= 100_000
    assert record["pilot_canonical_unique_count"] <= 10_000
    assert record["pilot_exact_score_count"] <= 100
    assert record["baseline_in_min_overlap_family"] is True
    assert record["hard_div_canonical_id"]
    scored = record["scored"]
    assert len(scored) == record["pilot_exact_score_count"]
    for row in scored:
        portfolio = tuple(tuple(ticket) for ticket in row["tickets"])
        got = evaluate_portfolio(portfolio).official_any_prize
        assert got == Fraction(row["official_any_prize"])
        assert score_portfolio(portfolio).official_any_prize == got
        label = comparison_label(got.numerator, got.denominator)
        assert label == row["comparison_label"]
        if label == "STRICT_IMPROVEMENT":
            assert got > Fraction(*BASELINE_FRACTION)
            assert record["sampled_decision"] == "STRICT_IMPROVEMENT_FOUND"
    hard = hard_div_k20()
    assert evaluate_portfolio(hard).official_any_prize == Fraction(*BASELINE_FRACTION)
    fingerprint = baseline_fingerprint(hard)
    assert fingerprint["in_family"] is True
    assert fingerprint["canonical_id"] == record["hard_div_canonical_id"]
    ids = [row["canonical_id"] for row in scored[:8]]
    assert class_set_sha256(ids) == class_set_sha256(list(ids))
