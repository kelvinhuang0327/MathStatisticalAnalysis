"""Focused checks for the branch-6 paired OFFICIAL_ANY_PRIZE evaluator.

Fixtures in this file are synthetic. They are not a historical success experiment.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.domain.lottery_rules import (
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.research.b649_branch6_forward_paired_any_prize_r1 import (
    COST_COMPARISON_POLICY,
    CUTOFF_NOT_BEFORE_RESULT,
    DAMAGED_SHA256,
    DUPLICATE_DRAW,
    EXTERNAL_PREDRAW_ATTESTATION,
    GENERATED_AT_ONLY,
    GENERATED_AT_ONLY_REJECTION,
    ILLEGAL_OFFICIAL_DRAW,
    ILLEGAL_TICKET,
    IN_SAMPLE,
    LATE_CUTOFF,
    MISSING_FREEZE_EVIDENCE,
    MISSING_LEGAL_INFORMATION_CUTOFF,
    MISSING_OFFICIAL_RESULT,
    NOT_COMPARABLE,
    NOT_ESTABLISHED,
    OUT_OF_SAMPLE,
    REAL_OBSERVED,
    REAL_PREDRAW_ARTIFACT,
    SHA256_MISMATCH,
    SIGNIFICANCE_NOT_CLAIMED,
    SUPPORTED_TICKET_COUNTS,
    SYNTHETIC_EXCLUDED_FROM_REAL,
    SYNTHETIC_FIXTURE,
    UNSUPPORTED_TICKET_COUNT,
    WRONG_BUDGET_BASELINE,
    WRONG_COUNT_BASELINE,
    EvaluationReport,
    canonical_frozen_artifact_bytes,
    deterministic_tie_order,
    evaluate_paired_any_prize,
    frozen_artifact_sha256,
    observed_official_any_prize,
    render_evaluation_report,
    synthetic_launch_inputs,
)
from lottolab.research.b649_official_any_prize_exact import (
    independent_random_official_any_prize,
)

MAINS = (1, 2, 3, 4, 5, 6)
SPECIAL = 7
SEVENTH = (1, 2, 7, 8, 9, 10)
TWO_MAIN_MISS = (1, 2, 8, 9, 10, 11)
CUTOFF = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
CAPTURED_AT = datetime(2026, 1, 1, 11, 30, tzinfo=UTC)
AVAILABLE_AT = datetime(2026, 1, 1, 20, 0, tzinfo=UTC)
MODULE_PATH = Path("src/lottolab/research/b649_branch6_forward_paired_any_prize_r1.py")


def _miss_tickets(count: int) -> list[list[int]]:
    pool = list(range(20, 50))
    return [pool[index : index + 6] for index in range(count)]


def _winning_portfolio(count: int) -> list[list[int]]:
    return [list(SEVENTH), *_miss_tickets(count - 1)]


def _losing_portfolio(count: int) -> list[list[int]]:
    return [list(TWO_MAIN_MISS), *_miss_tickets(count - 1)]


def _evidence(draw_id: str) -> dict[str, object]:
    return {
        "evidence_kind": EXTERNAL_PREDRAW_ATTESTATION,
        "artifact_sha256": "",
        "captured_at": CAPTURED_AT,
        "capture_locator": f"external-capture:{draw_id}",
    }


def _snapshot(
    *,
    draw_id: str,
    ticket_count: int,
    candidate: list[list[int]],
    baseline: list[list[int]],
    baseline_count: int | None = None,
    sample_scope: str = OUT_OF_SAMPLE,
    provenance: str = SYNTHETIC_FIXTURE,
    cutoff: datetime = CUTOFF,
) -> dict[str, object]:
    return {
        "draw_id": draw_id,
        "ticket_count": ticket_count,
        "ranking_algorithm_id": "fixture-ranking",
        "ranking_version": "fixture-0",
        "candidate_portfolio": candidate,
        "same_count_baseline": {
            "ticket_count": ticket_count if baseline_count is None else baseline_count,
            "portfolio": baseline,
        },
        "prediction_cutoff": cutoff,
        "prediction_generated_at": GENERATED_AT,
        "frozen_artifact_sha256": "",
        "pre_draw_capture_evidence": _evidence(draw_id),
        "sample_scope": sample_scope,
        "provenance": provenance,
    }


def _official(
    draw_id: str,
    *,
    mains: tuple[int, ...] = MAINS,
    special: int = SPECIAL,
    legal_cutoff: datetime | None = CUTOFF,
    available_at: datetime = AVAILABLE_AT,
) -> dict[str, object]:
    result: dict[str, object] = {
        "official_draw_id": draw_id,
        "official_draw_source_identity": f"synthetic-source:{draw_id}",
        "official_result_available_at": available_at,
        "winning_main_numbers": mains,
        "winning_special_number": special,
    }
    if legal_cutoff is not None:
        result["legal_pre_draw_information_cutoff"] = legal_cutoff
    return result


def _typed_evidence(snapshot: dict[str, object]) -> dict[str, object]:
    evidence = snapshot["pre_draw_capture_evidence"]
    if not isinstance(evidence, dict):
        raise AssertionError("pre_draw_capture_evidence must be a dict")
    return cast(dict[str, object], evidence)


def _stamp(snapshot: dict[str, object]) -> dict[str, object]:
    digest = frozen_artifact_sha256(snapshot)
    snapshot["frozen_artifact_sha256"] = digest
    _typed_evidence(snapshot)["artifact_sha256"] = digest
    return snapshot


def _pair(
    draw_id: str,
    ticket_count: int,
    *,
    candidate_wins: bool,
    baseline_wins: bool = False,
    sample_scope: str = OUT_OF_SAMPLE,
    provenance: str = SYNTHETIC_FIXTURE,
    cutoff: datetime = CUTOFF,
) -> tuple[dict[str, object], dict[str, object]]:
    candidate = (
        _winning_portfolio(ticket_count)
        if candidate_wins
        else _losing_portfolio(ticket_count)
    )
    baseline = (
        _winning_portfolio(ticket_count) if baseline_wins else _miss_tickets(ticket_count)
    )
    snapshot = _stamp(
        _snapshot(
            draw_id=draw_id,
            ticket_count=ticket_count,
            candidate=candidate,
            baseline=baseline,
            sample_scope=sample_scope,
            provenance=provenance,
            cutoff=cutoff,
        )
    )
    return snapshot, _official(draw_id)


def _codes(report: EvaluationReport, draw_id: str) -> set[str]:
    found: set[str] = set()
    for rejection in report.leakage_disposition.rejections:
        if rejection.draw_id == draw_id:
            found.update(rejection.codes)
    return found


def _evaluate(
    snapshots: list[dict[str, object]],
    officials: list[dict[str, object]],
    *,
    report_label: str,
) -> EvaluationReport:
    return evaluate_paired_any_prize(snapshots, officials, report_label=report_label)


def _ticket_wins(ticket: tuple[int, ...], mains: tuple[int, ...], special: int) -> bool:
    score = score_big_lotto_ticket(
        predicted_main_numbers=ticket,
        winning_main_numbers=mains,
        winning_special_number=special,
    )
    tier = resolve_big_lotto_prize_tier(score.main_hits, score.special_hit)
    return isinstance(tier, BigLottoPrizeTier)


def test_supported_ticket_counts_use_one_evaluation_path() -> None:
    snapshots: list[dict[str, object]] = []
    officials: list[dict[str, object]] = []
    for ticket_count in SUPPORTED_TICKET_COUNTS:
        snapshot, official = _pair(f"COUNT-{ticket_count}", ticket_count, candidate_wins=True)
        snapshots.append(snapshot)
        officials.append(official)

    report = _evaluate(snapshots, officials, report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == len(SUPPORTED_TICKET_COUNTS)
    stakes = [bucket.stake for bucket in report.out_of_sample_buckets]
    assert stakes == list(SUPPORTED_TICKET_COUNTS)
    assert report.in_sample_buckets == ()
    for bucket in report.out_of_sample_buckets:
        assert bucket.ticket_count == bucket.stake
        assert bucket.ticket_count in SUPPORTED_TICKET_COUNTS
        assert bucket.records[0].candidate_observed_official_any_prize is True


def test_seventh_prize_wins_and_two_main_miss_does_not() -> None:
    seventh_score = score_big_lotto_ticket(
        predicted_main_numbers=SEVENTH,
        winning_main_numbers=MAINS,
        winning_special_number=SPECIAL,
    )
    seventh_tier = resolve_big_lotto_prize_tier(
        seventh_score.main_hits,
        seventh_score.special_hit,
    )
    miss_score = score_big_lotto_ticket(
        predicted_main_numbers=TWO_MAIN_MISS,
        winning_main_numbers=MAINS,
        winning_special_number=SPECIAL,
    )
    miss_tier = resolve_big_lotto_prize_tier(miss_score.main_hits, miss_score.special_hit)
    assert isinstance(seventh_tier, BigLottoPrizeTier)
    assert seventh_tier.tier_id is BigLottoPrizeTierId.SEVENTH
    assert miss_tier is NoPrizeResult.NO_PRIZE

    winning, winning_draw = _pair("SEVENTH", 2, candidate_wins=True)
    losing, losing_draw = _pair("MISS", 2, candidate_wins=False)
    report = _evaluate(
        [winning, losing],
        [winning_draw, losing_draw],
        report_label=SYNTHETIC_FIXTURE,
    )
    by_draw = {
        record.draw_id: record
        for bucket in report.out_of_sample_buckets
        for record in bucket.records
    }

    assert by_draw["SEVENTH"].candidate_observed_official_any_prize is True
    assert by_draw["MISS"].candidate_observed_official_any_prize is False
    assert observed_official_any_prize(_winning_portfolio(2), MAINS, SPECIAL) is True
    assert observed_official_any_prize(_losing_portfolio(2), MAINS, SPECIAL) is False
    assert _ticket_wins(SEVENTH, MAINS, SPECIAL) is True
    assert _ticket_wins(TWO_MAIN_MISS, MAINS, SPECIAL) is False


def test_illegal_ticket_is_rejected() -> None:
    snapshot = _snapshot(
        draw_id="ILLEGAL",
        ticket_count=2,
        candidate=[[6, 5, 4, 3, 2, 1], [20, 21, 22, 23, 24, 25]],
        baseline=_miss_tickets(2),
    )
    _stamp(snapshot)
    report = _evaluate([snapshot], [_official("ILLEGAL")], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert ILLEGAL_TICKET in _codes(report, "ILLEGAL")


def test_theoretical_coverage_is_not_the_observed_indicator() -> None:
    snapshot, official = _pair("THEORY", 2, candidate_wins=False)
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)
    record = report.out_of_sample_buckets[0].records[0]
    coverage = independent_random_official_any_prize(2)

    assert report.observed_field_name != report.theoretical_field_name
    assert record.candidate_observed_official_any_prize is False
    assert isinstance(record.candidate_observed_official_any_prize, bool)
    assert record.theoretical_uniform_any_prize_coverage == (
        f"{coverage.numerator}/{coverage.denominator}"
    )
    assert record.theoretical_uniform_any_prize_coverage != "false"
    assert coverage != Fraction(0, 1)


def test_missing_freeze_evidence_is_excluded_even_with_generated_at() -> None:
    snapshot, official = _pair("NO-EVIDENCE", 2, candidate_wins=True)
    snapshot["pre_draw_capture_evidence"] = None
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert snapshot["prediction_generated_at"] == GENERATED_AT
    assert report.valid_paired_draw_count == 0
    assert MISSING_FREEZE_EVIDENCE in _codes(report, "NO-EVIDENCE")
    assert report.same_count_observed_lift == NOT_ESTABLISHED


def test_generated_at_only_evidence_is_excluded() -> None:
    snapshot, official = _pair("GENERATED", 2, candidate_wins=True)
    evidence = _typed_evidence(snapshot)
    evidence["evidence_kind"] = GENERATED_AT_ONLY
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert GENERATED_AT_ONLY_REJECTION in _codes(report, "GENERATED")


def test_mismatched_sha_is_excluded() -> None:
    snapshot, official = _pair("SHA", 2, candidate_wins=True)
    snapshot["frozen_artifact_sha256"] = "0" * 64
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert SHA256_MISMATCH in _codes(report, "SHA")


def test_damaged_sha_is_excluded() -> None:
    snapshot, official = _pair("DAMAGED", 2, candidate_wins=True)
    snapshot["frozen_artifact_sha256"] = "ZZ"
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert DAMAGED_SHA256 in _codes(report, "DAMAGED")


def test_late_cutoff_is_excluded() -> None:
    snapshot, official = _pair(
        "LATE",
        2,
        candidate_wins=True,
        cutoff=CUTOFF + timedelta(minutes=1),
    )
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert LATE_CUTOFF in _codes(report, "LATE")


def test_cutoff_not_strictly_before_result_is_excluded() -> None:
    snapshot, official = _pair(
        "CLOCK",
        2,
        candidate_wins=True,
        cutoff=AVAILABLE_AT,
    )
    official["legal_pre_draw_information_cutoff"] = AVAILABLE_AT
    _stamp(snapshot)
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert CUTOFF_NOT_BEFORE_RESULT in _codes(report, "CLOCK")


def test_missing_legal_information_cutoff_is_excluded() -> None:
    snapshot, official = _pair("NO-LEGAL", 2, candidate_wins=True)
    del official["legal_pre_draw_information_cutoff"]
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert MISSING_LEGAL_INFORMATION_CUTOFF in _codes(report, "NO-LEGAL")


def test_different_count_baseline_is_excluded() -> None:
    snapshot = _stamp(
        _snapshot(
            draw_id="COUNT",
            ticket_count=5,
            candidate=_losing_portfolio(5),
            baseline=_miss_tickets(2),
            baseline_count=2,
        )
    )
    report = _evaluate([snapshot], [_official("COUNT")], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert WRONG_COUNT_BASELINE in _codes(report, "COUNT")


def test_wrong_budget_baseline_is_excluded() -> None:
    snapshot = _stamp(
        _snapshot(
            draw_id="BUDGET",
            ticket_count=5,
            candidate=_losing_portfolio(5),
            baseline=_miss_tickets(4),
            baseline_count=5,
        )
    )
    report = _evaluate([snapshot], [_official("BUDGET")], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert WRONG_BUDGET_BASELINE in _codes(report, "BUDGET")
    assert WRONG_COUNT_BASELINE not in _codes(report, "BUDGET")


def test_duplicate_draw_is_excluded_without_using_the_result() -> None:
    first, official = _pair("DUP", 2, candidate_wins=True)
    second, _ignored = _pair("DUP", 2, candidate_wins=False)
    report = _evaluate([first, second], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert _codes(report, "DUP") == {DUPLICATE_DRAW}
    assert report.leakage_disposition.rejected_count == 2


def test_missing_official_result_is_excluded() -> None:
    snapshot, _official_row = _pair("ABSENT", 2, candidate_wins=True)
    report = _evaluate([snapshot], [], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert MISSING_OFFICIAL_RESULT in _codes(report, "ABSENT")


def test_illegal_official_draw_is_excluded() -> None:
    snapshot, official = _pair("OVERLAP", 2, candidate_wins=False)
    official["winning_special_number"] = 1
    report = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert ILLEGAL_OFFICIAL_DRAW in _codes(report, "OVERLAP")


def test_official_numbers_do_not_reselect_the_frozen_portfolio() -> None:
    snapshot, losing_draw = _pair("FROZEN", 2, candidate_wins=False)
    smuggled = _winning_portfolio(2)
    snapshot["selected_after_draw"] = smuggled
    frozen_ticket = tuple(_losing_portfolio(2)[0])
    winning_draw = _official("FROZEN", mains=frozen_ticket, special=49)
    losing_report = _evaluate([snapshot], [losing_draw], report_label=SYNTHETIC_FIXTURE)
    winning_report = _evaluate(
        [deepcopy(snapshot)],
        [winning_draw],
        report_label=SYNTHETIC_FIXTURE,
    )
    losing_record = losing_report.out_of_sample_buckets[0].records[0]
    winning_record = winning_report.out_of_sample_buckets[0].records[0]
    frozen = deterministic_tie_order(_losing_portfolio(2))

    assert losing_record.candidate_portfolio == frozen
    assert winning_record.candidate_portfolio == frozen
    assert losing_record.candidate_portfolio == winning_record.candidate_portfolio
    assert losing_record.candidate_observed_official_any_prize is False
    assert winning_record.candidate_observed_official_any_prize is True
    assert tuple(tuple(ticket) for ticket in smuggled) != frozen
    assert losing_report.leakage_disposition.official_numbers_used_for_selection is False


def test_tied_inputs_are_deterministic() -> None:
    forward_portfolio = _winning_portfolio(3)
    backward_portfolio = list(reversed(forward_portfolio))
    forward = _stamp(
        _snapshot(
            draw_id="TIE",
            ticket_count=3,
            candidate=forward_portfolio,
            baseline=_miss_tickets(3),
        )
    )
    backward = _stamp(
        _snapshot(
            draw_id="TIE",
            ticket_count=3,
            candidate=backward_portfolio,
            baseline=list(reversed(_miss_tickets(3))),
        )
    )
    official = _official("TIE")

    assert frozen_artifact_sha256(forward) == frozen_artifact_sha256(backward)
    assert canonical_frozen_artifact_bytes(forward) == canonical_frozen_artifact_bytes(backward)
    assert deterministic_tie_order(forward_portfolio) == deterministic_tie_order(backward_portfolio)
    first = _evaluate([forward], [official], report_label=SYNTHETIC_FIXTURE)
    second = _evaluate([backward], [official], report_label=SYNTHETIC_FIXTURE)
    repeated = _evaluate([forward], [official], report_label=SYNTHETIC_FIXTURE)

    assert first == second == repeated
    assert render_evaluation_report(first) == render_evaluation_report(second)


def test_in_sample_and_out_of_sample_stay_in_separate_buckets() -> None:
    inside, inside_draw = _pair("IN", 2, candidate_wins=True, sample_scope=IN_SAMPLE)
    outside, outside_draw = _pair("OUT", 2, candidate_wins=False, sample_scope=OUT_OF_SAMPLE)
    report = _evaluate(
        [inside, outside],
        [inside_draw, outside_draw],
        report_label=SYNTHETIC_FIXTURE,
    )

    assert len(report.in_sample_buckets) == 1
    assert len(report.out_of_sample_buckets) == 1
    assert report.in_sample_buckets[0].draw_ids == ("IN",)
    assert report.out_of_sample_buckets[0].draw_ids == ("OUT",)
    assert report.in_sample_buckets[0].same_count_observed_lift == "1/1"
    assert report.out_of_sample_buckets[0].same_count_observed_lift == "0/1"
    assert report.same_count_observed_lift == (
        "IN_SAMPLE:stake=2:ticket_count=2:1/1;OUT_OF_SAMPLE:stake=2:ticket_count=2:0/1"
    )


def test_paired_lift_uses_shared_draw_differences() -> None:
    first, first_draw = _pair("A", 2, candidate_wins=True, baseline_wins=False)
    second, second_draw = _pair("B", 2, candidate_wins=False, baseline_wins=True)
    report = _evaluate([second, first], [second_draw, first_draw], report_label=SYNTHETIC_FIXTURE)
    bucket = report.out_of_sample_buckets[0]

    assert bucket.draw_ids == ("A", "B")
    assert [record.paired_indicator_difference for record in bucket.records] == [1, -1]
    assert bucket.same_count_observed_lift == "0/1"
    assert {record.draw_id for record in bucket.records} == {"A", "B"}
    for record in bucket.records:
        assert record.stake == record.ticket_count


def test_cross_count_names_the_stake_and_does_not_rank_20_above_2() -> None:
    small, small_draw = _pair("SMALL", 2, candidate_wins=False)
    large, large_draw = _pair("LARGE", 20, candidate_wins=True)
    report = _evaluate([small, large], [small_draw, large_draw], report_label=SYNTHETIC_FIXTURE)
    rendered = render_evaluation_report(report)

    assert "stake=2" in rendered
    assert "stake=20" in rendered
    assert "larger_stake_is_not_ranking_skill=true" in rendered
    assert "cross_count_comparison_is_not_ranking_skill=true" in rendered
    assert "not evidence of a stronger ranking" in rendered
    assert "is a stronger ranking" not in rendered
    assert "stronger ranking than" not in rendered
    assert report.cost_comparison_policy == COST_COMPARISON_POLICY
    assert report.predictive_gain == NOT_ESTABLISHED
    assert report.significance_claim == SIGNIFICANCE_NOT_CLAIMED


def test_empty_real_input_is_not_established() -> None:
    report = evaluate_paired_any_prize((), (), report_label=REAL_OBSERVED)
    rendered = render_evaluation_report(report)

    assert report.report_label == REAL_OBSERVED
    assert report.valid_paired_draw_count == 0
    assert report.same_count_observed_lift == NOT_ESTABLISHED
    assert report.predictive_gain == NOT_ESTABLISHED
    assert report.future_predictive_gain == NOT_ESTABLISHED
    assert report.ranking_comparability == NOT_COMPARABLE
    assert report.sample_uncertainty == NOT_ESTABLISHED
    assert report.leakage_disposition.admitted_real_pair_count == 0
    assert report.leakage_disposition.admitted_synthetic_pair_count == 0
    assert report.leakage_disposition.generated_at_alone_is_proof is False
    assert report.significance_claim == SIGNIFICANCE_NOT_CLAIMED
    assert "statistically significant" not in rendered.lower()
    assert "candidate_observed_official_any_prize=true" not in rendered


def test_synthetic_win_is_labeled_and_absent_from_the_real_report() -> None:
    snapshot, official = synthetic_launch_inputs()
    synthetic = _evaluate([snapshot], [official], report_label=SYNTHETIC_FIXTURE)
    real = _evaluate([snapshot], [official], report_label=REAL_OBSERVED)
    synthetic_text = render_evaluation_report(synthetic)
    real_text = render_evaluation_report(real)
    record = synthetic.out_of_sample_buckets[0].records[0]

    assert snapshot["provenance"] == SYNTHETIC_FIXTURE
    assert synthetic.report_label == SYNTHETIC_FIXTURE
    assert synthetic.valid_paired_draw_count == 1
    assert record.candidate_observed_official_any_prize is True
    assert record.report_label == SYNTHETIC_FIXTURE
    assert "report_label=SYNTHETIC_FIXTURE" in synthetic_text
    assert real.valid_paired_draw_count == 0
    assert real.same_count_observed_lift == NOT_ESTABLISHED
    assert real.predictive_gain == NOT_ESTABLISHED
    assert SYNTHETIC_EXCLUDED_FROM_REAL in _codes(real, "SYNTHETIC-FIXTURE-DRAW-1")
    assert "candidate_observed_official_any_prize=true" not in real_text
    assert "report_label=SYNTHETIC_FIXTURE" not in real_text
    assert "statistically significant" not in synthetic_text.lower()
    assert synthetic.significance_claim == SIGNIFICANCE_NOT_CLAIMED
    assert synthetic.future_predictive_gain == NOT_ESTABLISHED


def test_real_provenance_fixture_can_be_admitted_without_becoming_history() -> None:
    snapshot, official = _pair(
        "GATE-ONLY",
        2,
        candidate_wins=True,
        provenance=REAL_PREDRAW_ARTIFACT,
    )
    report = _evaluate([snapshot], [official], report_label=REAL_OBSERVED)

    assert report.valid_paired_draw_count == 1
    assert report.leakage_disposition.admitted_real_pair_count == 1
    assert report.out_of_sample_buckets[0].records[0].draw_id == "GATE-ONLY"
    assert report.future_predictive_gain == NOT_ESTABLISHED
    assert report.significance_claim == SIGNIFICANCE_NOT_CLAIMED


def test_same_draw_at_two_stakes_stays_two_same_count_pairs() -> None:
    small, small_draw = _pair("SHARED", 2, candidate_wins=False)
    large, _large_draw = _pair("SHARED", 10, candidate_wins=True)
    report = _evaluate([small, large], [small_draw], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 2
    assert [bucket.stake for bucket in report.out_of_sample_buckets] == [2, 10]
    assert all(bucket.draw_ids == ("SHARED",) for bucket in report.out_of_sample_buckets)


def test_generated_at_is_not_part_of_the_frozen_digest() -> None:
    original = _snapshot(
        draw_id="DIGEST",
        ticket_count=2,
        candidate=_losing_portfolio(2),
        baseline=_miss_tickets(2),
    )
    shifted = deepcopy(original)
    shifted["prediction_generated_at"] = GENERATED_AT + timedelta(days=3)
    shifted["selected_after_draw"] = _winning_portfolio(2)

    assert canonical_frozen_artifact_bytes(original) == canonical_frozen_artifact_bytes(shifted)


def test_unsupported_ticket_count_is_rejected() -> None:
    snapshot = _stamp(
        _snapshot(
            draw_id="FOUR",
            ticket_count=4,
            candidate=_miss_tickets(4),
            baseline=_miss_tickets(4),
        )
    )
    report = _evaluate([snapshot], [_official("FOUR")], report_label=SYNTHETIC_FIXTURE)

    assert report.valid_paired_draw_count == 0
    assert UNSUPPORTED_TICKET_COUNT in _codes(report, "FOUR")


def test_module_does_not_import_a_ranking_or_prediction_pipeline() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)

    assert "lottolab.domain.lottery_rules" in modules
    assert "lottolab.research.b649_official_any_prize_exact" in modules
    assert all("strategies" not in name for name in modules)
    assert all("sqlite" not in name for name in modules)
    assert all(name != "random" for name in modules)
    assert "score_big_lotto_ticket" in source
    assert "resolve_big_lotto_prize_tier" in source
    assert "evaluate_portfolio" not in source


def test_launch_inputs_are_a_mapping_pair() -> None:
    snapshot, official = synthetic_launch_inputs()
    assert isinstance(snapshot, Mapping)
    assert isinstance(official, Mapping)
    report = evaluate_paired_any_prize((), (), report_label=REAL_OBSERVED)
    assert report.valid_paired_draw_count == 0
