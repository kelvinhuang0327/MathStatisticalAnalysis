"""Compose frozen C rankings, D portfolio evaluation and K multiplicity control.

Only saved replay artifacts are read. No strategy execution, database access,
production catalog mutation, or invented draw/ticket outcomes occurs here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k235_cutoff_rank_refresh_r1 import (
    COMPLETE_STATUS,
    FATAL_STATUSES,
    INELIGIBLE_STATUS,
    load_rank_history,
    refresh_from_files,
)
from lottolab.research.b649_k235_selection_bias_calibration_r1 import calibrate_historical_windows
from lottolab.research.b649_k235_window_lift_report_r1 import (
    WINDOWS,
    ZERO_OVERLAP_RANDOM_BASELINES,
    HistoricalDrawOutcome,
    PredictionStatus,
    StrategyTargetReplay,
    TargetStatus,
    compare_k235_strategies,
    evaluate_native_k235_history,
)

SCHEMA_VERSION = "B649_K235_HISTORICAL_REPORT_BRIDGE_R1"


class HistoricalBridgeInputError(ValueError):
    """Saved evidence is missing, inconsistent, or uses incompatible semantics."""


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _validate_saved_ranking(
    ranking: Mapping[str, Any],
    saved_path: Path | None,
    evidence_kind: str,
) -> dict[str, Any] | None:
    if saved_path is None:
        if evidence_kind == "OBSERVED":
            raise HistoricalBridgeInputError("OBSERVED requires the saved C ranking artifact")
        return None
    saved, identity = load_rank_history(saved_path)
    for key in ("cutoff", "strategy_pool", "strategies", "rankings", "baseline_validation"):
        if _json_value(saved.get(key)) != _json_value(ranking.get(key)):
            raise HistoricalBridgeInputError(f"saved C ranking mismatch: {key}")
    for key in ("rank_history", "per_draw_outcomes"):
        if _json_value(saved["source_identity"][key]) != _json_value(
            ranking["source_identity"][key]
        ):
            raise HistoricalBridgeInputError(f"saved C source identity mismatch: {key}")
    if evidence_kind == "OBSERVED" and ranking["baseline_validation"]["status"] != "MATCH":
        raise HistoricalBridgeInputError("historical ranking baseline did not match")
    return identity


def _read_native_evidence(
    paths: Sequence[Path],
    ranking: Mapping[str, Any],
    cutoff: int,
) -> tuple[
    list[HistoricalDrawOutcome],
    list[StrategyTargetReplay],
    dict[tuple[str, str], tuple[bool, int, bool]],
]:
    native = {row["strategy_id"]: row["native_ticket_count"] for row in ranking["strategies"]}
    outcomes: dict[str, HistoricalDrawOutcome] = {}
    predictions: list[StrategyTargetReplay] = []
    scores: dict[tuple[str, str], tuple[bool, int, bool]] = {}
    identities = ranking["source_identity"]["per_draw_outcomes"]
    for path, identity in zip(paths, identities, strict=True):
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for raw_line in source:
                digest.update(raw_line)
                if not raw_line.strip():
                    continue
                row = json.loads(raw_line)
                strategy_id = row.get("strategy_id")
                if strategy_id not in native:
                    continue
                draw_id = row["target_draw_number"]
                if int(draw_id) > cutoff:
                    continue
                try:
                    outcome = HistoricalDrawOutcome(
                        draw_id,
                        date.fromisoformat(row["target_draw_date"]),
                        tuple(row["actual_main_numbers"]),
                        row["actual_special_number"],
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise HistoricalBridgeInputError(
                        f"missing/invalid actual draw: {draw_id}"
                    ) from exc
                previous = outcomes.setdefault(draw_id, outcome)
                if previous != outcome:
                    raise HistoricalBridgeInputError(f"conflicting actual draw: {draw_id}")
                replay_status = row["replay_status"]
                if row["native_ticket_count"] != native[strategy_id] or (
                    replay_status == COMPLETE_STATUS
                    and row.get("actual_native_ticket_count") != native[strategy_id]
                ):
                    replay_status = "NATIVE_TICKET_COUNT_VIOLATION"
                tickets = None
                if replay_status == COMPLETE_STATUS:
                    raw_tickets = row.get("native_portfolio")
                    if (
                        not isinstance(raw_tickets, list)
                        or len(cast(list[Any], raw_tickets)) != native[strategy_id]
                    ):
                        raise HistoricalBridgeInputError(
                            f"missing exact native portfolio: {draw_id}"
                        )
                    tickets = tuple(tuple(ticket) for ticket in cast(list[list[int]], raw_tickets))
                    status = PredictionStatus.OK
                    matches = [
                        len(set(ticket) & set(outcome.winning_main_numbers)) for ticket in tickets
                    ]
                    scores[strategy_id, draw_id] = (
                        row["official_any_prize"],
                        sum(matches),
                        max(matches) >= 3,
                    )
                elif replay_status in FATAL_STATUSES:
                    status = PredictionStatus.FAILED
                elif replay_status == INELIGIBLE_STATUS:
                    status = PredictionStatus.NOT_EVALUABLE
                else:
                    raise HistoricalBridgeInputError(f"unknown replay status: {replay_status}")
                predictions.append(
                    StrategyTargetReplay(
                        strategy_id,
                        draw_id,
                        tickets,
                        status,
                        None if status is PredictionStatus.OK else replay_status,
                    )
                )
        if digest.hexdigest() != identity["sha256"]:
            raise HistoricalBridgeInputError("source changed between ranking and native evaluation")
    ordered = [outcomes[key] for key in sorted(outcomes, key=int)]
    if len(ordered) != ranking["cutoff"]["included_target_draw_count"]:
        raise HistoricalBridgeInputError("actual outcomes missing for ranking target universe")
    return ordered, predictions, scores


def build_historical_report(
    *,
    rank_history_path: Path,
    replay_paths: Sequence[Path],
    cutoff_draw: str,
    evidence_kind: str,
    saved_ranking_path: Path | None = None,
) -> dict[str, Any]:
    """Create one JSON-ready report; OBSERVED requires a matching saved C artifact."""
    if evidence_kind not in {"OBSERVED", "SYNTHETIC"}:
        raise HistoricalBridgeInputError("evidence_kind must be OBSERVED or SYNTHETIC")
    ranking = refresh_from_files(
        rank_history_path=rank_history_path,
        replay_paths=replay_paths,
        cutoff_draw=cutoff_draw,
    )
    saved_identity = _validate_saved_ranking(ranking, saved_ranking_path, evidence_kind)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_kind": evidence_kind,
        "status": "MISSING" if ranking["status"] == "MISSING" else "COMPLETE",
        "cutoff": ranking["cutoff"],
        "metric_semantics": {
            "primary_endpoint": "OFFICIAL_ANY_PRIZE",
            "definition": "Any native ticket wins an official prize, including 2 main + special.",
            "cost_basis": "EXACT_NATIVE_K; NO_PREFIX_TRUNCATION; COMPARE_ONLY_WITHIN_K",
            "supplementary_endpoints": [
                "M3_PLUS",
                "AVERAGE_MAIN_MATCHES",
                "EXPECTED_MAX_MAIN_MATCHES",
            ],
            "cross_endpoint_ranking": "FORBIDDEN",
        },
        "ranking": ranking,
        "saved_ranking_identity": saved_identity,
        "source_identity": ranking["source_identity"],
        "window_metrics": [],
        "statistical_results": None,
        "later_cutoffs": [
            {
                "cutoff": str(target),
                "status": "MISSING",
                "evaluated": False,
                "reason": "Outside this cutoff comparison; no completed result inferred.",
            }
            for target in (115000097, 115000098, 115000099)
            if target > int(cutoff_draw)
        ],
    }
    if ranking["status"] == "MISSING":
        return report
    outcomes, predictions, scores = _read_native_evidence(replay_paths, ranking, int(cutoff_draw))
    native = {row["strategy_id"]: row["native_ticket_count"] for row in ranking["strategies"]}
    c_rows = {row["strategy_id"]: row for row in ranking["strategies"]}
    evaluated = evaluate_native_k235_history(outcomes, predictions, native)
    all_metrics = [metric for strategy in evaluated.strategy_reports for metric in strategy.windows]
    checked = 0
    for strategy in evaluated.strategy_reports:
        for target in strategy.target_results:
            saved_score = scores.get((strategy.strategy_id, target.draw_id))
            if saved_score is not None:
                if (
                    target.status is not TargetStatus.EVALUABLE
                    or target.official_any_prize != saved_score[0]
                ):
                    raise HistoricalBridgeInputError(
                        f"C/D official prize conflict: {strategy.strategy_id}/{target.draw_id}"
                    )
                checked += 1
        for metric in strategy.windows:
            window = metric.window.removeprefix("RECENT_")
            c_metric = c_rows[strategy.strategy_id]["windows"][window]
            checks = (
                (metric.denominator, c_metric["effective_denominator"]),
                (metric.official_any_prize_success_count, c_metric["success_count"]),
                (metric.missing_period_count, c_metric["missing_cell_count"]),
                (metric.failed_period_count, c_metric["execution_failure_count"]),
                (metric.not_evaluable_period_count, c_metric["ineligible_draw_count"]),
                (metric.target_period_count, c_metric["source_draw_count"]),
            )
            if any(left != right for left, right in checks):
                raise HistoricalBridgeInputError(
                    f"C/D denominator or status mismatch: {strategy.strategy_id}/{window}"
                )
            targets = strategy.target_results[-metric.target_period_count :]
            valid = [
                scores[strategy.strategy_id, t.draw_id]
                for t in targets
                if t.status is TargetStatus.EVALUABLE
            ]
            n = metric.denominator
            kind = evidence_kind if n else "MISSING"
            row = metric.to_dict()
            row.update(
                {
                    "window": window,
                    "endpoint": "OFFICIAL_ANY_PRIZE",
                    "evidence_kind": kind,
                    "ranking_status": c_rows[strategy.strategy_id]["ranking_status"],
                    "source_counts": c_metric,
                    "state_counts": {
                        "OBSERVED": n if evidence_kind == "OBSERVED" else 0,
                        "SYNTHETIC": n if evidence_kind == "SYNTHETIC" else 0,
                        "MISSING": metric.target_period_count - n,
                    },
                    "supplementary": {
                        "M3_PLUS": {
                            "evidence_kind": kind,
                            "success_count": sum(value[2] for value in valid),
                            "effective_denominator": n,
                            "rate": sum(value[2] for value in valid) / n if n else None,
                        },
                        "AVERAGE_MAIN_MATCHES": {
                            "evidence_kind": kind,
                            "main_match_sum": sum(value[1] for value in valid),
                            "effective_target_denominator": n,
                            "effective_ticket_denominator": n * strategy.k,
                            "mean_per_ticket": sum(value[1] for value in valid) / (n * strategy.k)
                            if n
                            else None,
                        },
                        "EXPECTED_MAX_MAIN_MATCHES": {
                            "evidence_kind": "MISSING",
                            "value": None,
                            "reason": "No C/D/K expectation model supplied for this endpoint.",
                        },
                    },
                }
            )
            report["window_metrics"].append(row)
    pairs = [
        compare_k235_strategies(evaluated, left, right, k=k, window=window)
        for k in (2, 3, 5)
        for left, right in combinations(
            sorted(sid for sid, count in native.items() if count == k), 2
        )
        for window, _size in WINDOWS
    ]
    calibration = calibrate_historical_windows(all_metrics, pairs)
    report["statistical_results"] = calibration
    report["random_baselines"] = {
        "zero_overlap_reference": {
            str(k): {
                "numerator": p.numerator,
                "denominator": p.denominator,
                "probability": float(p),
            }
            for k, p in ZERO_OVERLAP_RANDOM_BASELINES.items()
        },
        "applied_policy": (
            "D_EXACT_ACTUAL_PORTFOLIO_PER_TARGET; AVERAGE_ONLY_OVER_EFFECTIVE_TARGETS"
        ),
        "overlap_reference_substitution": False,
    }
    report["validation"] = {
        "C_ranking_preserved": True,
        "C_D_windows_match": True,
        "official_outcome_crosscheck_count": checked,
        "strategy_count": len(native),
        "native_strategy_report_count": len(evaluated.strategy_reports),
        "rankable_strategy_count": ranking["strategy_pool"]["rankable_strategy_count"],
        "target_count": len(outcomes),
        "future_outcomes_used": False,
        "production_predictor_or_database_written": False,
    }
    return _json_value(report)
