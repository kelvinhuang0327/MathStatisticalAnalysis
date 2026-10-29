"""Incrementally extend K2/K3/K5 observed history through draw 115000099.

This module consumes the saved 115000096 report and only the three saved
115000097-115000099 outcome cells per strategy. Earlier strategy outcomes are
never replayed. Recent windows are shifted by removing their three oldest
targets and adding the three new targets.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, TypeAlias, Union, cast

from lottolab.research import b649_k235_window_lift_report_r1 as _window_lift_report

JSONValue: TypeAlias = Union[  # noqa: UP007, UP040
    str,
    int,
    float,
    bool,
    None,
    list["JSONValue"],
    dict[str, "JSONValue"],
]
JSONObject: TypeAlias = dict[str, JSONValue]  # noqa: UP040

_WILSON_HELPER_NAME = "_wilson_interval"
_wilson_interval = cast(
    Callable[[int, int], tuple[float, float] | None],
    getattr(_window_lift_report, _WILSON_HELPER_NAME),
)
exact_portfolio_random_probability = _window_lift_report.exact_portfolio_random_probability

TASK_ID = "NUMBER2_1028_R_K235_INCREMENTAL_RANK_099_R1"
CANONICAL_SOURCE = "cb32f260490de1635ee0c6a4e4ee275b6a10d238"
PRIOR_CUTOFF = "115000096"
TARGET_DRAWS = ("115000097", "115000098", "115000099")
WINDOWS: tuple[tuple[str, int | None], ...] = (
    ("50", 50),
    ("300", 300),
    ("750", 750),
    ("1500", 1500),
    ("FULL", None),
)
K_VALUES = (2, 3, 5)
EXPECTED_STATUSES = {"COMPLETE": 123, "FAILED": 3, "MISSING": 3}


class IncrementalRankInputError(ValueError):
    """A fixed source or cell violates the incremental ranking contract."""


@dataclass(frozen=True, slots=True)
class _CellEvidence:
    status: str
    success: bool | None = None
    probability: Fraction | None = None
    overlap: bool | None = None
    reason: str | None = None
    ticket_count_violation: bool = False


def _json_copy(value: object) -> JSONValue:
    """Round-trip JSON before comparing data with JSON-compatible values."""
    return cast(JSONValue, json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False)))


def _same_json(left: Any, right: Any) -> bool:
    return _json_copy(left) == _json_copy(right)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IncrementalRankInputError(message)


def _expect_json_mapping(value: object, message: str) -> Mapping[str, JSONValue]:
    if not isinstance(value, Mapping):
        raise IncrementalRankInputError(message)
    # JSON object keys are strings; the runtime Mapping check cannot retain that key type.
    return cast(Mapping[str, JSONValue], value)


def _expect_int(value: object, message: str) -> int:
    if type(value) is not int:
        raise IncrementalRankInputError(message)
    return value


def _fraction_from_payload(value: object, *, label: str) -> Fraction | None:
    if value is None:
        return None
    fraction = _expect_json_mapping(value, f"{label} must be a fraction object or null")
    numerator = _expect_int(fraction.get("numerator"), f"{label}.numerator must be an integer")
    denominator = _expect_int(
        fraction.get("denominator"), f"{label}.denominator must be a positive integer"
    )
    _require(denominator > 0, f"{label}.denominator must be a positive integer")
    return Fraction(numerator, denominator)


def _fraction_payload(value: Fraction | None) -> JSONObject | None:
    if value is None:
        return None
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_12": f"{float(value):.12f}",
        "percent_10": f"{float(value) * 100:.10f}",
    }


def _source_rate_payload(successes: int, denominator: int) -> JSONObject | None:
    if denominator == 0:
        return None
    return {
        "numerator": successes,
        "denominator": denominator,
        "fraction": f"{successes}/{denominator}",
        "decimal": successes / denominator,
    }


def _has_overlap(tickets: Sequence[Sequence[int]]) -> bool:
    seen: set[int] = set()
    for ticket in tickets:
        values = set(ticket)
        if seen.intersection(values):
            return True
        seen.update(values)
    return False


def _new_cell(row: Mapping[str, JSONValue], expected_k: int) -> _CellEvidence:
    status = row.get("result_status")
    if status == "FAILED":
        return _CellEvidence(
            "FAILED",
            reason=str(row.get("failure_reason") or row.get("failure_type") or "FAILED"),
        )
    if status == "MISSING":
        return _CellEvidence(
            "MISSING",
            reason=str(row.get("missing_reason") or row.get("failure_reason") or "MISSING"),
        )
    if status != "COMPLETE":
        raise IncrementalRankInputError(f"unsupported new cell status: {status!r}")
    official_any_prize = row.get("official_any_prize")
    if type(official_any_prize) is not bool:
        raise IncrementalRankInputError("COMPLETE cell must carry an official_any_prize boolean")
    _require(
        row.get("replay_status") == "COMPLETE" and row.get("replay_attempted") is True,
        "COMPLETE cell must be a completed replay",
    )
    _require(row.get("target_outcome_excluded") is True, "target outcome leaked into replay")
    native_ticket_count = row.get("native_ticket_count")
    if type(native_ticket_count) is not int or native_ticket_count != expected_k:
        raise IncrementalRankInputError(
            "new cell native ticket count does not match its fixed strategy identity"
        )
    raw_tickets = row.get("tickets")
    if not isinstance(raw_tickets, list) or len(raw_tickets) != expected_k:
        raise IncrementalRankInputError("COMPLETE cell must include exactly K native tickets")
    tickets: list[list[int]] = []
    for raw_ticket in raw_tickets:
        ticket = _expect_json_mapping(raw_ticket, "ticket must be an object")
        main_numbers = ticket.get("main_numbers")
        if not isinstance(main_numbers, list):
            raise IncrementalRankInputError("ticket main_numbers must be a list")
        ticket_numbers: list[int] = []
        for number in main_numbers:
            if type(number) is not int:
                raise IncrementalRankInputError("ticket main_numbers must contain exact integers")
            ticket_numbers.append(number)
        tickets.append(ticket_numbers)
    evaluations = row.get("ticket_evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != expected_k:
        raise IncrementalRankInputError(
            "COMPLETE cell must include one official evaluation per native ticket"
        )
    evaluated: list[bool] = []
    for raw_evaluation in evaluations:
        evaluation = _expect_json_mapping(raw_evaluation, "ticket evaluation must be an object")
        value = evaluation.get("is_winner")
        if type(value) is not bool:
            raise IncrementalRankInputError(
                "ticket evaluations must contain official is_winner booleans"
            )
        evaluated.append(value)
    _require(
        any(evaluated) is official_any_prize,
        "official_any_prize conflicts with the saved official ticket evaluations",
    )
    overlap = _has_overlap(tickets)
    return _CellEvidence(
        status="COMPLETE",
        success=official_any_prize,
        probability=exact_portfolio_random_probability(tickets),
        overlap=overlap,
    )


def _prior_cell(row: Mapping[str, JSONValue], expected_k: int) -> _CellEvidence:
    status = row.get("replay_status")
    if status == "COMPLETE":
        official_any_prize = row.get("official_any_prize")
        if type(official_any_prize) is not bool:
            raise IncrementalRankInputError(
                "prior COMPLETE evidence must carry an official_any_prize boolean"
            )
        native_ticket_count = row.get("native_ticket_count")
        if type(native_ticket_count) is not int or native_ticket_count != expected_k:
            raise IncrementalRankInputError(
                "prior COMPLETE evidence has a native ticket count mismatch"
            )
        portfolio = row.get("native_portfolio")
        if not isinstance(portfolio, list) or len(portfolio) != expected_k:
            raise IncrementalRankInputError(
                "prior COMPLETE evidence must carry exactly K native tickets"
            )
        typed_portfolio: list[list[int]] = []
        for ticket in portfolio:
            if not isinstance(ticket, list):
                raise IncrementalRankInputError(
                    "prior native portfolio must be a list of ticket number lists"
                )
            typed_ticket: list[int] = []
            for number in ticket:
                if type(number) is not int:
                    raise IncrementalRankInputError(
                        "prior native portfolio tickets must contain exact integers"
                    )
                typed_ticket.append(number)
            typed_portfolio.append(typed_ticket)
        overlap = _has_overlap(typed_portfolio)
        return _CellEvidence(
            status="COMPLETE",
            success=official_any_prize,
            probability=exact_portfolio_random_probability(typed_portfolio),
            overlap=overlap,
        )
    if status == "EXECUTION_FAILURE" or status == "NATIVE_TICKET_COUNT_VIOLATION":
        return _CellEvidence(
            "FAILED",
            reason=str(row.get("reason") or status),
            ticket_count_violation=status == "NATIVE_TICKET_COUNT_VIOLATION",
        )
    if isinstance(status, str) and status.startswith("WINDOW_INELIGIBLE"):
        return _CellEvidence("NOT_EVALUABLE", reason=str(row.get("reason") or status))
    if status in {"MISSING", "MISSING_PREDICTION"}:
        return _CellEvidence("MISSING", reason=str(row.get("reason") or status))
    raise IncrementalRankInputError(f"unsupported prior replay status: {status!r}")


def _verify_base_metric(
    metric: Mapping[str, JSONValue],
    *,
    expected_draws: Sequence[str],
    strategy_id: str,
) -> tuple[Fraction, Counter[str]]:
    denominator = _expect_int(metric.get("denominator"), "invalid prior denominator")
    successes = _expect_int(
        metric.get("official_any_prize_success_count"), "invalid prior official success count"
    )
    target_count = metric.get("target_period_count")
    _require(
        0 <= successes <= denominator,
        "invalid prior official success count",
    )
    _require(
        target_count == len(expected_draws),
        f"prior target count mismatch for {strategy_id}/{metric.get('window')}",
    )
    _require(
        metric.get("first_draw_id") == expected_draws[0],
        f"prior first target mismatch for {strategy_id}/{metric.get('window')}",
    )
    _require(
        metric.get("last_draw_id") == expected_draws[-1],
        f"prior last target mismatch for {strategy_id}/{metric.get('window')}",
    )

    source = _expect_json_mapping(
        metric.get("source_counts"), "prior metric source_counts must be an object"
    )
    _require(
        source.get("effective_denominator") == denominator,
        "prior denominator differs from the C source counts",
    )
    _require(
        source.get("success_count") == successes,
        "prior success count differs from the C source counts",
    )
    _require(
        source.get("source_draw_count") == target_count,
        "prior target period count differs from the C source counts",
    )
    _require(
        source.get("failure_count") == denominator - successes,
        "prior observed failure count differs from the C source counts",
    )

    failed = _expect_int(metric.get("failed_period_count"), "invalid prior failed period count")
    missing = _expect_int(metric.get("missing_period_count"), "invalid prior missing period count")
    not_evaluable = _expect_int(
        metric.get("not_evaluable_period_count"), "invalid prior not-evaluable period count"
    )
    _require(failed >= 0, "invalid prior failed period count")
    _require(missing >= 0, "invalid prior missing period count")
    _require(not_evaluable >= 0, "invalid prior not-evaluable period count")
    unknown = _expect_int(
        source.get("unknown_status_count", 0), "invalid prior unknown status count"
    )
    _require(unknown >= 0, "invalid prior unknown status count")
    _require(
        denominator + failed + missing + not_evaluable + unknown == target_count,
        f"prior states do not cover all targets for {strategy_id}/{metric.get('window')}",
    )
    _require(
        source.get("execution_failure_count") == failed,
        "prior failure count differs from the C source counts",
    )
    _require(
        source.get("missing_cell_count") == missing,
        "prior missing count differs from the C source counts",
    )
    _require(
        source.get("ineligible_draw_count") == not_evaluable,
        "prior non-evaluable count differs from the C source counts",
    )

    rate = _fraction_from_payload(metric.get("historical_win_rate"), label="historical_win_rate")
    if denominator:
        _require(rate == Fraction(successes, denominator), "prior success rate is inconsistent")
        baseline = _fraction_from_payload(
            metric.get("random_baseline_probability"), label="random_baseline_probability"
        )
        if baseline is None:
            raise IncrementalRankInputError("prior baseline is missing for observed outcomes")
        baseline_sum = baseline * denominator
    else:
        _require(rate is None, "zero-denominator prior metric must not have a success rate")
        _require(
            metric.get("random_baseline_probability") is None,
            "zero-denominator prior metric must not have a random baseline",
        )
        baseline_sum = Fraction(0)

    methods = _expect_json_mapping(
        metric.get("random_probability_method_counts"),
        "prior random method counts must be an object",
    )
    method_counts: Counter[str] = Counter(
        {
            key: _expect_int(value, "prior random method count must be an integer")
            for key, value in methods.items()
        }
    )
    _require(
        all(value >= 0 for value in method_counts.values()),
        "prior random method count cannot be negative",
    )
    _require(
        sum(method_counts.values()) == denominator,
        "prior random method counts do not equal the effective denominator",
    )
    overlap_period_count = _expect_int(
        metric.get("overlap_period_count", 0), "invalid prior overlap count"
    )
    _require(
        overlap_period_count <= denominator, "prior overlap count exceeds the effective denominator"
    )
    return baseline_sum, method_counts


def _advance_window_metric(
    metric: Mapping[str, JSONValue],
    *,
    expected_prior_draws: Sequence[str],
    removed: Sequence[_CellEvidence],
    added: Sequence[_CellEvidence],
    first_draw_id: str,
    last_draw_id: str,
    target_period_count: int,
    requested_target_periods: int | None,
    strategy_id: str,
    display_name: str,
    k: int,
    prior_ranking_status: str,
    current_ranking_class: str,
) -> JSONObject:
    baseline_sum, methods = _verify_base_metric(
        metric,
        expected_draws=expected_prior_draws,
        strategy_id=strategy_id,
    )
    denominator = _expect_int(metric.get("denominator"), "invalid prior denominator")
    successes = _expect_int(
        metric.get("official_any_prize_success_count"), "invalid prior official success count"
    )
    failed = _expect_int(metric.get("failed_period_count"), "invalid prior failed period count")
    missing = _expect_int(metric.get("missing_period_count"), "invalid prior missing period count")
    not_evaluable = _expect_int(
        metric.get("not_evaluable_period_count"), "invalid prior not-evaluable period count"
    )
    source = _expect_json_mapping(
        metric.get("source_counts"), "prior metric source_counts must be an object"
    )
    unknown = _expect_int(
        source.get("unknown_status_count", 0), "invalid prior unknown status count"
    )
    violations = _expect_int(
        source.get("ticket_count_violation_count", 0), "invalid prior ticket count violation count"
    )
    overlap_count = _expect_int(
        metric.get("overlap_period_count", 0), "invalid prior overlap count"
    )

    def apply(cell: _CellEvidence, direction: int) -> None:
        nonlocal denominator, successes, failed, missing, not_evaluable
        nonlocal unknown, violations, overlap_count, baseline_sum, methods
        if cell.status == "COMPLETE":
            if cell.success is None:
                raise IncrementalRankInputError("complete cell lacks success state")
            if cell.probability is None:
                raise IncrementalRankInputError("complete cell lacks random baseline")
            if cell.overlap is None:
                raise IncrementalRankInputError("complete cell lacks overlap state")
            denominator += direction
            successes += direction * int(cell.success)
            baseline_sum += direction * cell.probability
            overlap_count += direction * int(cell.overlap)
            method = "EXACT_OVERLAPPING_PORTFOLIO" if cell.overlap else "ZERO_OVERLAP_REFERENCE"
            methods[method] += direction
        elif cell.status == "FAILED":
            failed += direction
            violations += direction * int(cell.ticket_count_violation)
        elif cell.status == "MISSING":
            missing += direction
        elif cell.status == "NOT_EVALUABLE":
            not_evaluable += direction
        elif cell.status == "UNKNOWN":
            unknown += direction
        else:
            raise IncrementalRankInputError(f"unsupported cell state: {cell.status!r}")

    for cell in removed:
        apply(cell, -1)
    for cell in added:
        apply(cell, 1)

    _require(
        denominator >= 0 and 0 <= successes <= denominator,
        f"updated success counts are invalid for {strategy_id}",
    )
    _require(
        denominator + failed + missing + not_evaluable + unknown == target_period_count,
        f"updated states do not cover all targets for {strategy_id}/{metric.get('window')}",
    )
    _require(
        all(value >= 0 for value in methods.values()),
        "updated random method count cannot be negative",
    )
    _require(
        sum(methods.values()) == denominator,
        "updated random method counts do not equal the effective denominator",
    )
    _require(
        overlap_count >= 0 and overlap_count <= denominator, "updated overlap count is invalid"
    )
    _require(baseline_sum >= 0, "updated random probability sum is negative")

    rate = Fraction(successes, denominator) if denominator else None
    baseline = baseline_sum / denominator if denominator else None
    gain = rate - baseline if rate is not None and baseline is not None else None
    rate_interval = _wilson_interval(successes, denominator)
    gain_interval = (
        (
            (rate_interval[0] - float(baseline)) * 100,
            (rate_interval[1] - float(baseline)) * 100,
        )
        if rate_interval is not None and baseline is not None
        else None
    )
    if denominator == 0:
        availability = "MISSING"
    elif failed or missing or unknown:
        availability = "PARTIAL"
    elif requested_target_periods is not None and target_period_count < requested_target_periods:
        availability = "INSUFFICIENT_HISTORY"
    else:
        availability = "AVAILABLE"

    source_counts = dict(source)
    source_counts.update(
        {
            "effective_denominator": denominator,
            "success_count": successes,
            "failure_count": denominator - successes,
            "success_rate": _source_rate_payload(successes, denominator),
            "missing_cell_count": missing,
            "ineligible_draw_count": not_evaluable,
            "execution_failure_count": failed,
            "ticket_count_violation_count": violations,
            "unknown_status_count": unknown,
            "source_draw_count": target_period_count,
            "first_target_draw": first_draw_id,
            "last_target_draw": last_draw_id,
            "requested_draw_count": requested_target_periods,
            "status": availability,
            "strategy_id": strategy_id,
        }
    )
    return {
        "strategy_id": strategy_id,
        "display_name": display_name,
        "k": k,
        "window": metric["window"],
        "endpoint": "OFFICIAL_ANY_PRIZE",
        "evidence_kind": "OBSERVED" if denominator else "MISSING",
        "ranking_status_096": prior_ranking_status,
        "ranking_class_099": current_ranking_class,
        "requested_target_periods": requested_target_periods,
        "target_period_count": target_period_count,
        "first_draw_id": first_draw_id,
        "last_draw_id": last_draw_id,
        "official_any_prize_success_count": successes,
        "denominator": denominator,
        "historical_win_rate": _fraction_payload(rate),
        "random_baseline_probability": _fraction_payload(baseline),
        "relative_random_gain": _fraction_payload(gain),
        "relative_random_gain_percentage_points": float(gain) * 100 if gain is not None else None,
        "win_rate_ci_95": list(rate_interval) if rate_interval is not None else None,
        "win_rate_ci_method": "WILSON_SCORE_95_PERCENT",
        "random_gain_ci_95_percentage_points": list(gain_interval)
        if gain_interval is not None
        else None,
        "random_gain_ci_method": "WILSON_RATE_INTERVAL_MINUS_EXACT_MEAN_RANDOM_BASELINE",
        "failed_period_count": failed,
        "missing_period_count": missing,
        "not_evaluable_period_count": not_evaluable,
        "overlap_period_count": overlap_count,
        "random_probability_method_counts": {
            method: count for method, count in sorted(methods.items()) if count
        },
        "state_counts": {
            "OBSERVED": denominator,
            "SYNTHETIC": 0,
            "MISSING": target_period_count - denominator,
        },
        "source_counts": source_counts,
        "status": availability,
    }


def _ranking_key(row: Mapping[str, Any], window: str = "FULL") -> tuple[Any, ...]:
    metric = row["windows"][window]
    denominator = metric.get("denominator", metric.get("effective_denominator"))
    _require(
        type(denominator) is int and denominator > 0,
        f"rankable candidate {row['strategy_id']} has no effective denominator",
    )
    successes = metric.get("official_any_prize_success_count", metric.get("success_count"))
    return (-Fraction(successes, denominator), -denominator, row["strategy_id"])


def _history_ranks(c_ranking: Mapping[str, Any]) -> dict[str, int]:
    strategies = {row["strategy_id"]: row for row in c_ranking["strategies"]}
    result: dict[str, int] = {}
    for k in K_VALUES:
        eligible = [
            row
            for row in strategies.values()
            if row["native_ticket_count"] == k and row["ranking_status"] == "RANKABLE"
        ]
        ordered = sorted(eligible, key=lambda row: _ranking_key(row, "FULL"))
        top_ids = [row["strategy_id"] for row in c_ranking["rankings"][f"K{k}"]["top3"]]
        _require(
            top_ids == [row["strategy_id"] for row in ordered[:3]],
            f"C ranking top three do not match its saved FULL tie rule for K{k}",
        )
        result.update({row["strategy_id"]: rank for rank, row in enumerate(ordered, 1)})
    return result


def _validate_and_index_inputs(
    o_result: Mapping[str, Any],
    o_report: Mapping[str, Any],
    c_ranking: Mapping[str, Any],
    n_result: Mapping[str, Any],
    n_gap_rows: Sequence[Mapping[str, Any]],
    n_coverage: Mapping[str, Any],
    input_paths: Mapping[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], Mapping[str, Any]]]:
    _require(o_result.get("task_lifecycle_state") == "COMPLETED", "O result is not complete")
    _require(
        o_result.get("candidate_head") == "91de7cc34b8c8710f3971a5d2a6a3afe21834efe",
        "O candidate head differs from the fixed packet",
    )
    _require(
        o_result.get("canonical_base") == CANONICAL_SOURCE,
        "O canonical source differs from the fixed packet",
    )
    _require(o_report.get("status") == "COMPLETE", "O historical report is not complete")
    _require(
        o_report.get("cutoff", {}).get("actual_cutoff_applied") == PRIOR_CUTOFF,
        "O report cutoff is not 115000096",
    )
    _require(
        c_ranking.get("cutoff", {}).get("actual_cutoff_applied") == PRIOR_CUTOFF,
        "C ranking cutoff is not 115000096",
    )
    _require(
        o_report.get("metric_semantics", {}).get("primary_endpoint") == "OFFICIAL_ANY_PRIZE",
        "O primary endpoint is not OFFICIAL_ANY_PRIZE",
    )
    _require(
        c_ranking.get("ranking_contract", {}).get("future_outcomes_used") is False,
        "C ranking does not establish a no-future-outcomes boundary",
    )
    _require(
        _same_json(o_report.get("ranking"), c_ranking),
        "O embedded ranking differs from the fixed C ranking",
    )
    _require(
        _same_json(o_report.get("source_identity"), c_ranking.get("source_identity")),
        "O and C historical source identities differ",
    )

    candidate = "91de7cc34b8c8710f3971a5d2a6a3afe21834efe"
    _require(candidate == o_result.get("candidate_head"), "candidate identity mismatch")
    _require(n_result.get("task_lifecycle_state") == "COMPLETED", "N result is not complete")
    _require(n_result.get("strategy_identity_count") == 43, "N strategy identity count is not 43")
    _require(
        n_result.get("data_source_identity", {}).get("canonical_source_authority")
        == CANONICAL_SOURCE,
        "N canonical source differs from the fixed packet",
    )
    _require(
        n_result.get("data_source_identity", {}).get("ranking_096", {}).get("path")
        == input_paths["c_ranking"],
        "N ranking_096 locator differs from fixed C",
    )
    _require(
        n_result.get("data_source_identity", {}).get("ranking_096", {}).get("sha256")
        == o_report.get("saved_ranking_identity", {}).get("sha256"),
        "N ranking_096 digest differs from O/C",
    )

    c_strategies = {row["strategy_id"]: dict(row) for row in c_ranking.get("strategies", [])}
    o_strategies = {
        row["strategy_id"]: dict(row) for row in o_report.get("ranking", {}).get("strategies", [])
    }
    coverage_strategies = {
        row["strategy_id"]: dict(row) for row in n_coverage.get("strategies", [])
    }
    _require(len(c_strategies) == 43, "C ranking does not contain 43 strategies")
    _require(
        set(c_strategies) == set(o_strategies) == set(coverage_strategies),
        "strategy identities differ across fixed sources",
    )
    _require(
        n_coverage.get("strategy_identity_count") == 43, "N coverage does not contain 43 strategies"
    )
    _require(n_coverage.get("cell_total") == 129, "N coverage cell total is not 129")
    _require(
        n_result.get("targets_processed", {}).get("cell_total") == 129,
        "N result cell total is not 129",
    )
    _require(
        n_result.get("targets_processed", {}).get("requested") == list(TARGET_DRAWS),
        "N requested targets differ from the fixed packet",
    )

    for strategy_id, row in c_strategies.items():
        c_ticket_count = row.get("native_ticket_count")
        n_ticket_count = coverage_strategies[strategy_id].get("native_ticket_count")
        _require(
            c_ticket_count == n_ticket_count,
            f"native ticket count differs for {strategy_id}",
        )
        _require(
            row.get("ranking_status") == o_strategies[strategy_id].get("ranking_status"),
            f"O/C ranking status differs for {strategy_id}",
        )

    target_outcomes = _expect_json_mapping(
        n_result.get("data_source_identity", {}).get("draw_database", {}).get("target_draws", {}),
        "N target outcome identities must be an object",
    )
    _require(
        set(target_outcomes) == set(TARGET_DRAWS),
        "N recorded target outcome identities differ from the fixed packet",
    )
    expected_cutoffs: dict[str, str] = dict(
        zip(TARGET_DRAWS, (PRIOR_CUTOFF, *TARGET_DRAWS[:-1]), strict=True)
    )
    new_cells: dict[tuple[str, str], Mapping[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    per_target_counts: dict[str, Counter[str]] = {target: Counter() for target in TARGET_DRAWS}
    per_strategy_complete: Counter[str] = Counter()
    per_strategy_successes: Counter[str] = Counter()
    per_target_complete: Counter[str] = Counter()
    per_target_successes: Counter[str] = Counter()

    for raw_row in n_gap_rows:
        row = _expect_json_mapping(_json_copy(raw_row), "N gap row must be an object")
        strategy_id_value = row.get("strategy_id")
        if not isinstance(strategy_id_value, str):
            raise IncrementalRankInputError("N gap strategy identity must be a string")
        strategy_id = strategy_id_value
        target_value = row.get("target_draw_number")
        if not isinstance(target_value, str):
            raise IncrementalRankInputError("N target draw number must be a string")
        target = target_value
        _require(strategy_id in c_strategies, f"unknown N strategy identity: {strategy_id!r}")
        _require(target in TARGET_DRAWS, f"unexpected N target: {target!r}")
        key = (strategy_id, target)
        _require(key not in new_cells, f"duplicate N cell: {key}")
        expected_k = _expect_int(
            coverage_strategies[strategy_id].get("native_ticket_count"),
            f"invalid N native ticket identity for {strategy_id}",
        )
        _require(expected_k in K_VALUES, f"invalid N native ticket identity for {strategy_id}")
        _require(
            row.get("causal_cutoff_verified") is True, f"N causal cutoff was not verified for {key}"
        )
        _require(
            row.get("causal_cutoff_draw_number") == expected_cutoffs[target],
            f"N causal cutoff is incorrect for {key}",
        )
        _require(
            row.get("target_outcome_excluded") is True,
            f"N target outcome was not excluded for {key}",
        )
        target_result = _expect_json_mapping(
            row.get("target_draw_result"), f"N target result is missing for {key}"
        )
        _require(
            target_result.get("draw_number") == target,
            f"N target result identity differs for {key}",
        )
        saved_target = _expect_json_mapping(
            target_outcomes[target], f"saved N target outcome is missing for {target}"
        )
        for field in ("draw_date", "main_numbers", "special_number"):
            if field in target_result:
                _require(
                    _same_json(target_result[field], saved_target[field]),
                    f"N target result {field} differs for {key}",
                )
        cell = _new_cell(row, expected_k)
        new_cells[key] = row
        status_counts[cell.status] += 1
        per_target_counts[target][cell.status] += 1
        if cell.status == "COMPLETE":
            per_strategy_complete[strategy_id] += 1
            per_target_complete[target] += 1
            per_strategy_successes[strategy_id] += int(bool(cell.success))
            per_target_successes[target] += int(bool(cell.success))
        if strategy_id == "b649_new_horizon_minimax_disagreement_r1":
            _require(
                row.get("strategy_version") == "v0.1", "Horizon new cells must remain bound to v0.1"
            )
            strategy_source = _expect_json_mapping(
                row.get("strategy_source", {}), "N strategy source identity must be an object"
            )
            _require(
                strategy_source.get("strategy_source_commit")
                == n_result.get("data_source_identity", {})
                .get("horizon_v01", {})
                .get("source_commit"),
                "Horizon v0.1 source commit differs from N identity",
            )

    _require(len(new_cells) == 129, "N gap does not contain 129 unique cells")
    _require(
        status_counts == Counter(EXPECTED_STATUSES),
        f"N gap status counts differ: {dict(status_counts)}",
    )
    _require(
        _same_json(dict(status_counts), n_coverage.get("cell_counts_by_status")),
        "N gap status counts differ from N coverage",
    )
    _require(
        _same_json(
            {target: dict(counts) for target, counts in per_target_counts.items()},
            n_coverage.get("cell_counts_by_target"),
        ),
        "N per-target status counts differ from coverage",
    )
    expected_strategy_denominators = {
        strategy_id: per_strategy_complete.get(strategy_id, 0) for strategy_id in c_strategies
    }
    expected_strategy_successes = {
        strategy_id: per_strategy_successes.get(strategy_id, 0)
        if per_strategy_complete.get(strategy_id, 0)
        else None
        for strategy_id in c_strategies
    }
    _require(
        _same_json(
            expected_strategy_denominators,
            n_coverage.get("effective_denominators_by_strategy"),
        ),
        "N per-strategy effective denominators differ from coverage",
    )
    _require(
        _same_json(
            expected_strategy_successes,
            n_coverage.get("official_any_prize_successes_by_strategy"),
        ),
        "N per-strategy official successes differ from coverage",
    )
    expected_target_denominators = {
        target: per_target_complete.get(target, 0) for target in TARGET_DRAWS
    }
    expected_target_successes = {
        target: per_target_successes.get(target, 0) for target in TARGET_DRAWS
    }
    _require(
        _same_json(
            expected_target_denominators, n_coverage.get("effective_denominators_by_target")
        ),
        "N per-target effective denominators differ from coverage",
    )
    _require(
        _same_json(
            expected_target_successes, n_coverage.get("official_any_prize_successes_by_target")
        ),
        "N per-target official successes differ from coverage",
    )

    horizon_id = "b649_new_horizon_minimax_disagreement_r1"
    horizon_rows = [new_cells[(horizon_id, target)] for target in TARGET_DRAWS]
    _require(
        all(row["result_status"] == "MISSING" for row in horizon_rows),
        "Horizon v0.1 097-099 cells must remain MISSING",
    )
    result_horizon_parity = n_result.get("horizon_v01_native_ticket_parity", {})
    coverage_horizon_parity = n_coverage.get("horizon_v01_native_ticket_parity", {})
    _require(
        _same_json(result_horizon_parity, coverage_horizon_parity),
        "N result and coverage Horizon v0.1 parity evidence differs",
    )
    _require(
        result_horizon_parity.get("status") == "MISMATCH",
        "N Horizon v0.1 parity must preserve its recorded mismatch status",
    )
    _require(len(n_gap_rows) == 129, "N gap row count is not 129")
    return c_strategies, new_cells


def _inspect_prior_sources(
    locators: Sequence[Mapping[str, Any]],
    *,
    strategy_ids: set[str],
    expected_draw_count: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    draw_ids: set[str] = set()
    draw_counts: Counter[str] = Counter()
    seen_cells: set[tuple[str, str]] = set()
    source_artifacts: list[dict[str, Any]] = []
    for locator in locators:
        path = Path(str(locator.get("path", "")))
        _require(path.is_file(), f"named prior evidence locator is missing: {path}")
        digest = hashlib.sha256()
        record_count = 0
        with path.open("rb") as source:
            for line in source:
                digest.update(line)
                if not line.strip():
                    continue
                row = json.loads(line)
                draw = row.get("target_draw_number")
                strategy = row.get("strategy_id")
                _require(
                    isinstance(draw, str) and draw.isdigit(),
                    f"invalid target draw in named prior source {path}",
                )
                _require(
                    strategy in strategy_ids,
                    f"unknown strategy in named prior source {path}: {strategy!r}",
                )
                key = (strategy, draw)
                _require(key not in seen_cells, f"duplicate named prior cell: {key}")
                seen_cells.add(key)
                draw_ids.add(draw)
                draw_counts[draw] += 1
                record_count += 1
        _require(
            record_count == locator.get("record_count"),
            f"prior record count differs from named locator: {path}",
        )
        _require(
            digest.hexdigest() == locator.get("sha256"),
            f"prior evidence digest differs from named locator: {path}",
        )
        source_artifacts.append(
            {
                "path": str(path),
                "byte_count": path.stat().st_size,
                "record_count": record_count,
                "sha256": digest.hexdigest(),
            }
        )

    ordered_draws = sorted(draw_ids, key=int)
    _require(
        len(ordered_draws) == expected_draw_count,
        "named prior evidence target count differs from O cutoff",
    )
    _require(
        ordered_draws[-1] == PRIOR_CUTOFF,
        "named prior evidence latest target differs from O cutoff",
    )
    _require(
        all(count == len(strategy_ids) for count in draw_counts.values()),
        "named prior sources do not contain one row per strategy and target",
    )
    _require(
        len(seen_cells) == sum(draw_counts.values()),
        "named prior evidence contains duplicate strategy/target cells",
    )
    return ordered_draws, source_artifacts


def _load_prior_outgoing_rows(
    locators: Sequence[Mapping[str, Any]],
    *,
    strategy_ids: set[str],
    required_target_ids: set[str],
    source_artifacts: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    selected: dict[tuple[str, str], Mapping[str, Any]] = {}
    rechecked_artifacts: list[dict[str, Any]] = []
    for locator in locators:
        path = Path(str(locator["path"]))
        digest = hashlib.sha256()
        record_count = 0
        with path.open("rb") as source:
            for line in source:
                digest.update(line)
                if not line.strip():
                    continue
                record_count += 1
                row = json.loads(line)
                draw = row["target_draw_number"]
                strategy_id = row["strategy_id"]
                _require(
                    strategy_id in strategy_ids,
                    f"unknown strategy in named prior source: {strategy_id!r}",
                )
                if draw not in required_target_ids:
                    continue
                key = (strategy_id, draw)
                _require(key not in selected, f"duplicate named prior cell: {key}")
                selected[key] = row
        _require(
            record_count == locator.get("record_count"),
            f"prior record count changed while reading outgoing rows: {path}",
        )
        _require(
            digest.hexdigest() == locator.get("sha256"),
            f"prior evidence changed while reading outgoing rows: {path}",
        )
        rechecked_artifacts.append(
            {
                "path": str(path),
                "byte_count": path.stat().st_size,
                "record_count": record_count,
                "sha256": digest.hexdigest(),
            }
        )
    expected_cells = len(strategy_ids) * len(required_target_ids)
    _require(
        len(selected) == expected_cells,
        "named prior evidence lacks one or more outgoing strategy cells",
    )
    _require(
        _same_json(source_artifacts, rechecked_artifacts),
        "named prior evidence identities changed during extraction",
    )
    return selected


def _verify_fixed_artifact(expected: object, actual: Mapping[str, JSONValue], label: str) -> None:
    if not isinstance(expected, Mapping):
        return
    expected_mapping = cast(Mapping[str, JSONValue], expected)
    if expected_mapping.get("path"):
        _require(
            expected_mapping["path"] == actual["path"],
            f"{label} path differs from its recorded identity",
        )
    if expected_mapping.get("byte_count") is not None:
        _require(
            expected_mapping["byte_count"] == actual["byte_count"],
            f"{label} byte count differs from its recorded identity",
        )
    if expected_mapping.get("sha256"):
        _require(
            expected_mapping["sha256"] == actual["sha256"],
            f"{label} digest differs from its recorded identity",
        )


def _read_json(path: Path) -> JSONObject:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    _require(isinstance(value, dict), f"JSON input must be an object: {path}")
    return cast(JSONObject, value)


def _read_jsonl(path: Path) -> list[JSONObject]:
    rows: list[JSONObject] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            _require(isinstance(value, dict), f"JSONL row {line_number} must be an object")
            rows.append(cast(JSONObject, value))
    return rows


def _file_identity(path: Path) -> JSONObject:
    _require(path.is_file(), f"fixed input is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "byte_count": path.stat().st_size, "sha256": digest.hexdigest()}


def build_incremental_artifacts(
    *,
    o_result: Mapping[str, Any],
    o_report: Mapping[str, Any],
    c_ranking: Mapping[str, Any],
    n_result: Mapping[str, Any],
    n_gap_rows: Sequence[Mapping[str, Any]],
    n_coverage: Mapping[str, Any],
    input_paths: Mapping[str, str],
    input_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build current complete ranks and a separate table for partial history."""
    c_strategies, new_rows = _validate_and_index_inputs(
        o_result, o_report, c_ranking, n_result, n_gap_rows, n_coverage, input_paths
    )
    history_ranks = _history_ranks(c_ranking)
    old_metrics = {
        (row["strategy_id"], row["k"], row["window"]): dict(row)
        for row in o_report.get("window_metrics", [])
    }
    _require(
        len(old_metrics) == 43 * len(WINDOWS),
        "O historical report must contain exactly 43 by 5 window metrics",
    )

    old_draw_count = o_report.get("cutoff", {}).get("included_target_draw_count")
    locators = o_report.get("source_identity", {}).get("per_draw_outcomes")
    if not isinstance(locators, list) or not locators:
        raise IncrementalRankInputError(
            "O report does not name its prior per-draw evidence locators"
        )
    prior_locators = [
        _expect_json_mapping(locator, "O prior evidence locator must be an object")
        for locator in cast(list[JSONValue], locators)
    ]
    outgoing_ids: set[str] = set()
    all_new_ids = list(TARGET_DRAWS)
    # Inspect only the raw sources explicitly named by O. The second bounded
    # pass below extracts the twelve outgoing target periods for recent windows.
    ordered_draws, prior_source_artifacts = _inspect_prior_sources(
        prior_locators,
        strategy_ids=set(c_strategies),
        expected_draw_count=int(old_draw_count),
    )
    for _label, size in WINDOWS:
        if size is None:
            continue
        old_targets = ordered_draws[-size:]
        outgoing_ids.update(old_targets[:3])
    _require(len(outgoing_ids) == 12, "recent windows do not identify twelve outgoing targets")

    prior_rows = _load_prior_outgoing_rows(
        prior_locators,
        strategy_ids=set(c_strategies),
        required_target_ids=outgoing_ids,
        source_artifacts=prior_source_artifacts,
    )
    prior_draws = ordered_draws
    _require(prior_draws[-1] == PRIOR_CUTOFF, "prior evidence cutoff changed")
    updated_draws = prior_draws + all_new_ids
    _require(
        all(int(left) < int(right) for left, right in pairwise(updated_draws)),
        "new target periods do not extend prior history in order",
    )

    _require(
        len(o_report.get("window_metrics", [])) == len(old_metrics),
        "O window metrics contain duplicate strategy/window rows",
    )
    latest_metrics: dict[str, dict[str, Any]] = {}
    for strategy_id, c_row in c_strategies.items():
        k = c_row["native_ticket_count"]
        new_statuses = [new_rows[(strategy_id, draw)]["result_status"] for draw in TARGET_DRAWS]
        current_class = (
            "HISTORICALLY_UNRANKABLE"
            if c_row["ranking_status"] != "RANKABLE"
            else "COMPLETE"
            if all(status == "COMPLETE" for status in new_statuses)
            else "PARTIAL"
        )
        per_window: dict[str, Any] = {}
        for label, size in WINDOWS:
            old_targets = prior_draws if size is None else prior_draws[-size:]
            new_targets = updated_draws if size is None else updated_draws[-size:]
            old_target_set = set(old_targets)
            new_target_set = set(new_targets)
            removed_ids = [draw for draw in old_targets if draw not in new_target_set]
            added_ids = [draw for draw in new_targets if draw not in old_target_set]
            metric = old_metrics[(strategy_id, k, label)]
            _require(
                metric.get("target_period_count") == len(old_targets),
                f"O target count differs for {strategy_id}/{label}",
            )
            _require(
                metric.get("first_draw_id") == old_targets[0]
                and metric.get("last_draw_id") == old_targets[-1],
                f"O target range differs for {strategy_id}/{label}",
            )
            removed = [_prior_cell(prior_rows[(strategy_id, draw)], k) for draw in removed_ids]
            added = [_new_cell(new_rows[(strategy_id, draw)], k) for draw in added_ids]
            per_window[label] = _advance_window_metric(
                metric,
                expected_prior_draws=old_targets,
                removed=removed,
                added=added,
                first_draw_id=new_targets[0],
                last_draw_id=new_targets[-1],
                target_period_count=len(new_targets),
                requested_target_periods=size,
                strategy_id=strategy_id,
                display_name=c_row["display_name"],
                k=k,
                prior_ranking_status=c_row["ranking_status"],
                current_ranking_class=current_class,
            )
        latest_metrics[strategy_id] = {
            "strategy_id": strategy_id,
            "display_name": c_row["display_name"],
            "native_ticket_count": k,
            "ranking_status_096": c_row["ranking_status"],
            "ranking_class_099": current_class,
            "prior_full_rank_096": history_ranks.get(strategy_id),
            "new_gap_status_counts": dict(
                Counter(new_rows[(strategy_id, draw)]["result_status"] for draw in TARGET_DRAWS)
            ),
            "strategy_version": new_rows[(strategy_id, TARGET_DRAWS[0])].get("strategy_version"),
            "windows": per_window,
        }

    current_rankings: dict[str, list[dict[str, Any]]] = {}
    historical_rankings: dict[str, list[dict[str, Any]]] = {}
    for k in K_VALUES:
        old_eligible = [
            latest_metrics[sid]
            for sid, c_row in c_strategies.items()
            if c_row["native_ticket_count"] == k and c_row["ranking_status"] == "RANKABLE"
        ]
        historical_rankings[f"K{k}"] = sorted(old_eligible, key=_ranking_key)
        complete = [row for row in old_eligible if row["ranking_class_099"] == "COMPLETE"]
        current_rankings[f"K{k}"] = sorted(complete, key=_ranking_key)

    ranking_entries: dict[str, Any] = {}
    for k in K_VALUES:
        key = f"K{k}"
        complete_rows = current_rankings[key]
        partial_rows = [
            row for row in historical_rankings[key] if row["ranking_class_099"] == "PARTIAL"
        ]
        historical_unrankable_ids = sorted(
            sid
            for sid, row in c_strategies.items()
            if row["native_ticket_count"] == k and row["ranking_status"] != "RANKABLE"
        )
        full_ranking = [
            {
                "rank": rank,
                "strategy_id": row["strategy_id"],
                "display_name": row["display_name"],
                "prior_full_rank_096": row["prior_full_rank_096"],
                "success_count": row["windows"]["FULL"]["official_any_prize_success_count"],
                "effective_denominator": row["windows"]["FULL"]["denominator"],
                "success_rate": row["windows"]["FULL"]["historical_win_rate"],
            }
            for rank, row in enumerate(complete_rows, 1)
        ]
        top3 = [
            {
                "rank": rank,
                "strategy_id": row["strategy_id"],
                "display_name": row["display_name"],
                "native_ticket_count": k,
                "prior_full_rank_096": row["prior_full_rank_096"],
                "full": row["windows"]["FULL"],
            }
            for rank, row in enumerate(complete_rows[:3], 1)
        ]
        ranking_entries[key] = {
            "status": "COMPLETE" if len(top3) == 3 else "PARTIAL",
            "ranking_basis": (
                "FULL success rate descending; denominator descending; strategy_id ascending"
            ),
            "strategy_pool_count": sum(
                row["native_ticket_count"] == k for row in c_strategies.values()
            ),
            "historically_rankable_count_096": len(historical_rankings[key]),
            "complete_through_099_count": len(complete_rows),
            "partial_valid_candidate_ids": [row["strategy_id"] for row in partial_rows],
            "historically_unrankable_candidate_ids": historical_unrankable_ids,
            "ranked_strategy_count": len(complete_rows),
            "missing_strategy_ids": sorted(
                [row["strategy_id"] for row in partial_rows] + historical_unrankable_ids
            ),
            "top3": top3,
            "full_ranking": full_ranking,
        }

    partial_valid = [
        row for row in latest_metrics.values() if row["ranking_class_099"] == "PARTIAL"
    ]
    historical_unrankable = [
        {
            "strategy_id": row["strategy_id"],
            "display_name": row["display_name"],
            "native_ticket_count": row["native_ticket_count"],
            "missing_reason_096": c_strategies[row["strategy_id"]].get("missing_reason"),
            "new_gap_status_counts": row["new_gap_status_counts"],
        }
        for row in latest_metrics.values()
        if row["ranking_class_099"] == "HISTORICALLY_UNRANKABLE"
    ]
    failed_missing_cells: list[JSONObject] = []
    for (strategy_id, target), row in sorted(
        new_rows.items(), key=lambda item: (int(item[0][1]), item[0][0])
    ):
        if row["result_status"] == "COMPLETE":
            continue
        failed_missing_cells.append(
            {
                "strategy_id": strategy_id,
                "display_name": c_strategies[strategy_id]["display_name"],
                "native_ticket_count": c_strategies[strategy_id]["native_ticket_count"],
                "target_draw_number": target,
                "status": row["result_status"],
                "strategy_version": row.get("strategy_version"),
                "reason": row.get("failure_reason") or row.get("missing_reason"),
            }
        )

    per_k_completeness: dict[str, JSONObject] = {}
    for k in K_VALUES:
        key = f"K{k}"
        per_k_completeness[key] = {
            "strategy_pool_count": ranking_entries[key]["strategy_pool_count"],
            "historically_rankable_count_096": ranking_entries[key][
                "historically_rankable_count_096"
            ],
            "complete_through_099_count": ranking_entries[key]["complete_through_099_count"],
            "partial_valid_candidate_count": len(
                ranking_entries[key]["partial_valid_candidate_ids"]
            ),
            "historically_unrankable_count": len(
                ranking_entries[key]["historically_unrankable_candidate_ids"]
            ),
        }

    input_artifact_list: list[JSONValue] = [_json_copy(item) for item in input_artifacts]
    gap_cell_counts: Counter[str] = Counter()
    for row in n_gap_rows:
        gap_status = row["result_status"]
        if not isinstance(gap_status, str):
            raise IncrementalRankInputError("N gap result status must be a string")
        gap_cell_counts[gap_status] += 1
    ranking_artifact: dict[str, object] = {
        "schema_version": "B649_K235_INCREMENTAL_RANK_099_R1",
        "task_id": TASK_ID,
        "status": "PARTIAL" if partial_valid or historical_unrankable else "COMPLETE",
        "cutoff": {
            "prior_cutoff": PRIOR_CUTOFF,
            "actual_cutoff_applied": TARGET_DRAWS[-1],
            "inclusive_outcome_cutoff": True,
            "future_outcomes_used": False,
            "prior_target_draw_count": len(prior_draws),
            "included_target_draw_count": len(updated_draws),
            "new_target_draws": list(TARGET_DRAWS),
        },
        "source_identity": {
            "canonical_source_authority": CANONICAL_SOURCE,
            "o_candidate_head": o_result["candidate_head"],
            "c_ranking_identity": _json_copy(o_report["saved_ranking_identity"]),
            "prior_per_draw_outcomes": prior_source_artifacts,
            "horizon_v01_source_commit": n_result["data_source_identity"]["horizon_v01"][
                "source_commit"
            ],
        },
        "ranking_contract": _json_copy(c_ranking["ranking_contract"]),
        "metric_semantics": _json_copy(o_report["metric_semantics"]),
        "strategy_count": 43,
        "ranking_completeness": {
            "historically_rankable_count_096": sum(
                row["ranking_status"] == "RANKABLE" for row in c_strategies.values()
            ),
            "complete_through_099_count": sum(
                row["ranking_class_099"] == "COMPLETE" for row in latest_metrics.values()
            ),
            "partial_valid_candidate_count": len(partial_valid),
            "historically_unrankable_count": len(historical_unrankable),
            "failed_or_missing_new_cell_count": len(failed_missing_cells),
            "per_k": per_k_completeness,
        },
        "new_gap_cell_counts": dict(sorted(gap_cell_counts.items())),
        "rankings": ranking_entries,
        "partial_valid_candidates": [
            {
                "strategy_id": row["strategy_id"],
                "display_name": row["display_name"],
                "native_ticket_count": row["native_ticket_count"],
                "prior_full_rank_096": row["prior_full_rank_096"],
                "strategy_version": row["strategy_version"],
                "new_gap_status_counts": row["new_gap_status_counts"],
                "full_through_096": c_strategies[row["strategy_id"]]["windows"]["FULL"],
                "partial_full_through_099": row["windows"]["FULL"],
            }
            for row in partial_valid
        ],
        "historically_unrankable_candidates": historical_unrankable,
        "failed_or_missing_new_cells": failed_missing_cells,
        "input_artifacts": input_artifact_list,
        "notes": [
            "Only named O/C ranking aggregates and N 097-099 cells were combined; "
            "earlier strategies were not replayed.",
            "Partial candidates are excluded from the complete 099 ranking and "
            "retained with their valid 096 history.",
            "FAILED and MISSING cells are excluded from success numerators and "
            "effective denominators.",
        ],
    }

    comparison_rows = sorted(
        latest_metrics.values(),
        key=lambda row: (row["native_ticket_count"], row["strategy_id"]),
    )
    windows_artifact: dict[str, object] = {
        "schema_version": "B649_K235_WINDOW_COMPARISON_099_R1",
        "task_id": TASK_ID,
        "status": ranking_artifact["status"],
        "cutoff": {
            "prior_cutoff": PRIOR_CUTOFF,
            "actual_cutoff_applied": TARGET_DRAWS[-1],
            "target_period_count": len(updated_draws),
            "new_target_draws": list(TARGET_DRAWS),
        },
        "metric_contract": {
            "primary_endpoint": "OFFICIAL_ANY_PRIZE",
            "success_definition": o_report["metric_semantics"]["definition"],
            "success_denominator": (
                "COMPLETE official outcome cells only; FAILED and MISSING are excluded, "
                "never treated as zero wins."
            ),
            "random_probability": (
                "D exact actual portfolio per target; average only over effective targets; "
                "overlapping portfolios use exact overlap geometry."
            ),
            "difference": (
                "historical OFFICIAL_ANY_PRIZE rate minus mean exact random probability; "
                "reported in percentage points."
            ),
            "ranking_window": (
                "FULL; ties use success rate descending, effective denominator descending, "
                "then strategy_id ascending."
            ),
        },
        "window_ranges": {
            label: {
                "requested_target_periods": size,
                "first_target_draw": updated_draws[-size] if size is not None else updated_draws[0],
                "last_target_draw": updated_draws[-1],
                "target_period_count": size if size is not None else len(updated_draws),
            }
            for label, size in WINDOWS
        },
        "strategy_count": 43,
        "strategy_windows": [
            {
                "strategy_id": row["strategy_id"],
                "display_name": row["display_name"],
                "native_ticket_count": row["native_ticket_count"],
                "ranking_status_096": row["ranking_status_096"],
                "ranking_class_099": row["ranking_class_099"],
                "prior_full_rank_096": row["prior_full_rank_096"],
                "new_gap_status_counts": row["new_gap_status_counts"],
                "strategy_version": row["strategy_version"],
                "windows": row["windows"],
            }
            for row in comparison_rows
        ],
        "inferential_statistics": {
            "status": "NOT_RECOMPUTED",
            "reason": (
                "This incremental artifact reports the requested rates, exact mean random "
                "baselines, differences, and Wilson intervals. It makes no updated p-value "
                "or multiple-comparison claim."
            ),
        },
        "input_artifacts": input_artifact_list,
    }
    return cast(JSONObject, ranking_artifact), cast(JSONObject, windows_artifact)


def build_from_fixed_paths() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load only the six task inputs and the raw locators named in O."""
    root = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
    workspace = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data")
    paths = {
        "o_result": workspace / "NUMBER2_1028_O_K235_ANALYTICS_COMPOSITION_R1/result.json",
        "o_report": workspace
        / "NUMBER2_1028_O_K235_ANALYTICS_COMPOSITION_R1/historical_comparison_115000096.json",
        "c_ranking": root
        / ".task-data/NUMBER2_1028_C_K235_CUTOFF_RANK_REFRESH_R1/ranking_115000096.json",
        "n_result": workspace / "NUMBER2_1028_N_K235_097_099_GAP_ONLY_R1/result.json",
        "n_gap": workspace / "NUMBER2_1028_N_K235_097_099_GAP_ONLY_R1/gap_097_099.jsonl",
        "n_coverage": workspace / "NUMBER2_1028_N_K235_097_099_GAP_ONLY_R1/coverage_097_099.json",
    }
    artifacts = [_file_identity(path) for path in paths.values()]
    artifact_by_path = {str(item["path"]): item for item in artifacts}
    o_result = _read_json(paths["o_result"])
    o_report = _read_json(paths["o_report"])
    c_ranking = _read_json(paths["c_ranking"])
    n_result = _read_json(paths["n_result"])
    n_coverage = _read_json(paths["n_coverage"])
    n_gap_rows = _read_jsonl(paths["n_gap"])

    _verify_fixed_artifact(
        o_result.get("report_artifact"),
        artifact_by_path[str(paths["o_report"])],
        "O report",
    )
    saved_c = o_report.get("saved_ranking_identity")
    _verify_fixed_artifact(saved_c, artifact_by_path[str(paths["c_ranking"])], "C ranking")
    n_outputs = _expect_json_mapping(
        n_result.get("output_integrity", {}), "N output integrity must be an object"
    )
    _verify_fixed_artifact(
        n_outputs.get("gap_jsonl"), artifact_by_path[str(paths["n_gap"])], "N gap"
    )
    _verify_fixed_artifact(
        n_outputs.get("coverage_json"),
        artifact_by_path[str(paths["n_coverage"])],
        "N coverage",
    )
    n_data_source_identity = _expect_json_mapping(
        n_result.get("data_source_identity"), "N data source identity must be an object"
    )
    n_ranking = _expect_json_mapping(
        n_data_source_identity.get("ranking_096"), "N ranking_096 identity must be an object"
    )
    _verify_fixed_artifact(n_ranking, artifact_by_path[str(paths["c_ranking"])], "N ranking_096")

    path_map = {key: str(value) for key, value in paths.items()}
    ranking, windows = build_incremental_artifacts(
        o_result=o_result,
        o_report=o_report,
        c_ranking=c_ranking,
        n_result=n_result,
        n_gap_rows=n_gap_rows,
        n_coverage=n_coverage,
        input_paths=path_map,
        input_artifacts=artifacts,
    )
    return ranking, windows


__all__ = [
    "IncrementalRankInputError",
    "build_from_fixed_paths",
    "build_incremental_artifacts",
]
