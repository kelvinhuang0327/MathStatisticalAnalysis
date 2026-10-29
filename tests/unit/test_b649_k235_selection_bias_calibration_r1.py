from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import TypedDict, cast

import pytest

from lottolab.research.b649_k235_selection_bias_calibration_r1 import (
    ReplaySuccess,
    analyze_payload,
    calibrate_selection_bias,
    main,
    null_result_document,
    replay_successes_from_rows,
    write_json_document,
)


class ReplayRow(TypedDict):
    target_draw_number: str
    strategy_id: str
    native_ticket_count: int
    ticket_position: int
    replay_status: str
    is_winner: bool


class CalibrationPayload(TypedDict):
    rows: list[ReplayRow]
    target_partitions: dict[str, str]
    fair_success_probability_by_k: dict[str, dict[str, int]]
    independent_holdout_target_ids: list[str]
    permutation_seed: int
    permutation_resamples: int


class Probability(TypedDict):
    numerator: int


class CandidateResult(TypedDict):
    strategy_id: str
    K: int
    N: int
    successful_count: int
    fair_success_probability: Probability
    one_sided_exact_binomial_p_value: float
    bonferroni_adjusted_p_value: float
    holm_adjusted_p_value: float
    evidence_status: str
    statistical_result: str


class PairwiseComparison(TypedDict):
    K: int
    N: int
    paired_wins_a: int
    paired_wins_b: int
    discordant_count: int
    exact_two_sided_mcnemar_p_value: float


class PartitionSummary(TypedDict):
    status: str
    N: int
    candidate_count: int
    candidate_results: list[CandidateResult]
    pairwise_comparisons: list[PairwiseComparison]


class HistoricalSummary(PartitionSummary):
    independence_status: str
    independent_holdout_claim_is_verified: bool
    previously_reused_target_overlap_count: int


class SelectedCandidateResult(TypedDict):
    selected_strategy_id: str | None
    N: int
    successful_count: int | None
    selection_origin: str


class SelectedHoldoutCheck(TypedDict):
    results: list[SelectedCandidateResult]


class PermutationResult(TypedDict):
    status: str
    method: str
    seed: int
    resamples: int
    empirical_p_value_plus_one: float


class AnalysisResult(TypedDict):
    candidate_count: int
    selected_strategy_by_k_from_exploration: dict[str, str]
    exploration: PartitionSummary
    unselected_historical: HistoricalSummary
    selected_candidate_holdout_check: SelectedHoldoutCheck
    exploration_null_permutation: PermutationResult
    prior_r1_judge_status: str
    prior_r1_result_relabelled_verified: bool


class NullExploration(TypedDict):
    status: str
    candidate_count: int
    N: int
    successful_count: int | None


class NullHistorical(TypedDict):
    status: str
    candidate_count: int
    N: int
    successful_count: int | None
    independence_status: str
    independent_holdout_claim_is_verified: bool


class NullResult(TypedDict):
    analysis_status: str
    candidate_count: int
    N: int
    successful_count: int | None
    exploration: NullExploration
    unselected_historical: NullHistorical


def _analyze(payload: CalibrationPayload) -> AnalysisResult:
    return cast(AnalysisResult, analyze_payload(payload))


def _calibrate(
    records: Sequence[ReplaySuccess],
    *,
    fair_success_probability_by_k: Mapping[int | str, Fraction | Mapping[str, object]],
    permutation_resamples: int,
    permutation_seed: int = 0,
    previously_reused_target_ids: tuple[str, ...] = (),
) -> AnalysisResult:
    return cast(
        AnalysisResult,
        calibrate_selection_bias(
            records,
            fair_success_probability_by_k=fair_success_probability_by_k,
            permutation_seed=permutation_seed,
            permutation_resamples=permutation_resamples,
            previously_reused_target_ids=previously_reused_target_ids,
        ),
    )


def _records() -> tuple[ReplaySuccess, ...]:
    outcomes = {
        "e1": {"A": True, "B": True},
        "e2": {"A": True, "B": False},
        "e3": {"A": True, "B": False},
        "e4": {"A": False, "B": True},
        "h1": {"A": True, "B": False},
        "h2": {"A": False, "B": True},
        "h3": {"A": True, "B": False},
    }
    return tuple(
        ReplaySuccess(
            target_id=target_id,
            strategy_id=strategy_id,
            k=2,
            success=success,
            partition=("EXPLORATION" if target_id.startswith("e") else "UNSELECTED_HISTORICAL"),
            independent_holdout_asserted=target_id.startswith("h"),
        )
        for target_id, strategies in outcomes.items()
        for strategy_id, success in strategies.items()
    )


def _candidate(rows: list[ReplayRow], strategy_id: str, targets: dict[str, bool]) -> None:
    for target_id, success in targets.items():
        for ticket_position in (1, 2):
            rows.append(
                {
                    "target_draw_number": target_id,
                    "strategy_id": strategy_id,
                    "native_ticket_count": 2,
                    "ticket_position": ticket_position,
                    "replay_status": "COMPLETE",
                    "is_winner": success and ticket_position == 1,
                }
            )


def _base_payload() -> CalibrationPayload:
    rows: list[ReplayRow] = []
    _candidate(
        rows,
        "A",
        {"e1": True, "e2": True, "e3": True, "e4": True, "h1": True, "h2": False},
    )
    _candidate(
        rows,
        "B",
        {"e1": False, "e2": True, "e3": False, "e4": False, "h1": False, "h2": True},
    )
    return {
        "rows": rows,
        "target_partitions": {
            "e1": "EXPLORATION",
            "e2": "EXPLORATION",
            "e3": "EXPLORATION",
            "e4": "EXPLORATION",
            "h1": "UNSELECTED_HISTORICAL",
            "h2": "UNSELECTED_HISTORICAL",
        },
        "fair_success_probability_by_k": {"2": {"numerator": 1, "denominator": 4}},
        "independent_holdout_target_ids": ["h1", "h2"],
        "permutation_seed": 719,
        "permutation_resamples": 31,
    }


def test_replay_rows_aggregate_at_least_one_winning_ticket_for_each_target() -> None:
    payload = _base_payload()
    records = replay_successes_from_rows(
        payload["rows"],
        target_partitions=payload["target_partitions"],
        independent_holdout_target_ids=payload["independent_holdout_target_ids"],
    )

    assert len(records) == 12
    assert {(row.target_id, row.strategy_id, row.success) for row in records} == {
        ("e1", "A", True),
        ("e2", "A", True),
        ("e3", "A", True),
        ("e4", "A", True),
        ("h1", "A", True),
        ("h2", "A", False),
        ("e1", "B", False),
        ("e2", "B", True),
        ("e3", "B", False),
        ("e4", "B", False),
        ("h1", "B", False),
        ("h2", "B", True),
    }


def test_missing_ticket_or_incomplete_replay_is_rejected_instead_of_shrinking_n() -> None:
    payload = _base_payload()
    rows = payload["rows"][:-1]
    with pytest.raises(ValueError, match="incomplete ticket positions"):
        replay_successes_from_rows(
            rows,
            target_partitions=payload["target_partitions"],
            independent_holdout_target_ids=payload["independent_holdout_target_ids"],
        )

    rows = list(payload["rows"])
    first_row = rows[0]
    rows[0] = {
        "target_draw_number": first_row["target_draw_number"],
        "strategy_id": first_row["strategy_id"],
        "native_ticket_count": first_row["native_ticket_count"],
        "ticket_position": first_row["ticket_position"],
        "replay_status": "PARTIAL",
        "is_winner": first_row["is_winner"],
    }
    with pytest.raises(ValueError, match="not COMPLETE"):
        replay_successes_from_rows(
            rows,
            target_partitions=payload["target_partitions"],
            independent_holdout_target_ids=payload["independent_holdout_target_ids"],
        )


def test_same_k_candidates_must_have_identical_target_periods() -> None:
    records = _records()
    with pytest.raises(ValueError, match="identical target periods"):
        calibrate_selection_bias(
            records[:-1],
            fair_success_probability_by_k={2: Fraction(1, 4)},
            permutation_resamples=5,
        )


def test_exploration_selects_winner_and_reports_candidate_n_successes_and_corrections() -> None:
    result = _analyze(_base_payload())

    assert result["candidate_count"] == 2
    assert result["selected_strategy_by_k_from_exploration"] == {"2": "A"}
    exploration = result["exploration"]
    assert exploration["N"] == 4
    assert exploration["candidate_count"] == 2
    candidate_a = next(row for row in exploration["candidate_results"] if row["strategy_id"] == "A")
    assert candidate_a["K"] == 2
    assert candidate_a["N"] == 4
    assert candidate_a["successful_count"] == 4
    assert candidate_a["fair_success_probability"]["numerator"] == 1
    assert candidate_a["one_sided_exact_binomial_p_value"] == pytest.approx(1 / 256)
    assert (
        candidate_a["bonferroni_adjusted_p_value"]
        >= candidate_a["one_sided_exact_binomial_p_value"]
    )
    assert candidate_a["holm_adjusted_p_value"] >= candidate_a["one_sided_exact_binomial_p_value"]
    assert candidate_a["evidence_status"] == "EXPLORATORY_SIGNAL_ONLY"

    selected_check = result["selected_candidate_holdout_check"]["results"][0]
    assert selected_check["selected_strategy_id"] == "A"
    assert selected_check["N"] == 2
    assert selected_check["successful_count"] == 1
    assert selected_check["selection_origin"] == "EXPLORATION_ONLY"


def test_pairwise_results_are_paired_and_only_compare_within_same_k() -> None:
    result = _analyze(_base_payload())
    comparisons = result["exploration"]["pairwise_comparisons"]

    assert len(comparisons) == 1
    pair = comparisons[0]
    assert pair["K"] == 2
    assert pair["N"] == 4
    assert pair["paired_wins_a"] == 3
    assert pair["paired_wins_b"] == 0
    assert pair["discordant_count"] == 3
    assert 0.0 <= pair["exact_two_sided_mcnemar_p_value"] <= 1.0


def test_seeded_candidate_label_permutation_is_reproducible_after_json_round_trip() -> None:
    first = _analyze(_base_payload())
    second = _analyze(_base_payload())

    # Project JSON comparison rules normalize mappings and sequence types first.
    first_json = json.loads(json.dumps(first, sort_keys=True))
    second_json = json.loads(json.dumps(second, sort_keys=True))
    assert first_json == second_json
    permutation = first["exploration_null_permutation"]
    assert permutation["status"] == "COMPLETE"
    assert permutation["method"] == "WITHIN_TARGET_SAME_K_CANDIDATE_LABEL_PERMUTATION"
    assert permutation["seed"] == 719
    assert permutation["resamples"] == 31
    assert 0.0 < permutation["empirical_p_value_plus_one"] <= 1.0


def test_unselected_historical_results_keep_provenance_uncertainty() -> None:
    result = _analyze(_base_payload())
    historical = result["unselected_historical"]

    assert historical["independence_status"] == "USER_ASSERTED_NOT_VERIFIED"
    assert historical["independent_holdout_claim_is_verified"] is False
    assert historical["N"] == 2
    assert historical["candidate_count"] == 2
    assert all(row["evidence_status"] == "UNCERTAIN" for row in historical["candidate_results"])
    assert result["prior_r1_judge_status"] == "BLOCKED_UNVERIFIABLE"
    assert result["prior_r1_result_relabelled_verified"] is False


def test_repeated_436_target_partition_cannot_be_labelled_independent() -> None:
    records = [
        ReplaySuccess("e0", "A", 2, True, "EXPLORATION"),
        ReplaySuccess("e0", "B", 2, False, "EXPLORATION"),
    ]
    for index in range(436):
        target_id = f"h{index:03d}"
        records.extend(
            (
                ReplaySuccess(target_id, "A", 2, True, "UNSELECTED_HISTORICAL", True),
                ReplaySuccess(target_id, "B", 2, False, "UNSELECTED_HISTORICAL", True),
            )
        )

    result = _calibrate(
        records,
        fair_success_probability_by_k={2: Fraction(1, 10)},
        permutation_seed=2,
        permutation_resamples=7,
    )
    historical = result["unselected_historical"]

    assert historical["N"] == 436
    assert historical["independence_status"] == "REUSED_436_NOT_INDEPENDENT"
    assert historical["independent_holdout_claim_is_verified"] is False
    candidate_a = next(row for row in historical["candidate_results"] if row["strategy_id"] == "A")
    assert candidate_a["successful_count"] == 436
    assert candidate_a["statistical_result"] == "FAMILYWISE_SIGNAL"
    assert candidate_a["evidence_status"] == "UNCERTAIN"


def test_overlap_with_known_reused_targets_blocks_independence_status() -> None:
    result = _calibrate(
        _records(),
        fair_success_probability_by_k={2: Fraction(1, 4)},
        permutation_resamples=5,
        previously_reused_target_ids=("h1",),
    )

    assert (
        result["unselected_historical"]["independence_status"] == "REUSED_TARGETS_NOT_INDEPENDENT"
    )
    assert result["unselected_historical"]["previously_reused_target_overlap_count"] == 1


def test_null_result_does_not_turn_missing_evidence_into_zero_success() -> None:
    result = cast(NullResult, null_result_document("No replay rows were supplied."))

    assert result["analysis_status"] == "NULL_NO_PER_PERIOD_EVIDENCE"
    assert result["candidate_count"] == 0
    assert result["N"] == 0
    assert result["successful_count"] is None
    assert result["exploration"]["status"] == "NULL"
    assert result["unselected_historical"]["independence_status"] == "NOT_ESTABLISHED"


def test_mismatched_candidate_set_between_partitions_is_rejected() -> None:
    records = [
        ReplaySuccess("e1", "A", 2, True, "EXPLORATION"),
        ReplaySuccess("e1", "B", 2, False, "EXPLORATION"),
        ReplaySuccess("h1", "A", 2, True, "UNSELECTED_HISTORICAL"),
    ]

    with pytest.raises(ValueError, match="present in both analysis partitions"):
        calibrate_selection_bias(
            records,
            fair_success_probability_by_k={2: Fraction(1, 4)},
            permutation_resamples=5,
        )


def test_json_result_writer_emits_sorted_reproducible_document(tmp_path: Path) -> None:
    path = write_json_document(null_result_document("missing"), tmp_path / "nested" / "result.json")

    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw)["analysis_status"] == "NULL_NO_PER_PERIOD_EVIDENCE"


def test_executable_entrypoint_reads_replay_envelope_and_writes_result(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(_base_payload()), encoding="utf-8")

    assert main([str(input_path), "--output", str(output_path)]) == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["analysis_status"] == "COMPLETE"
    assert result["candidate_count"] == 2
