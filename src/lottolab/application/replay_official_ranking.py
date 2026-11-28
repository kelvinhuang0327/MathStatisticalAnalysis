"""Rule-bound primitives for the formal replay ranking.

These functions do not access a database. A caller must establish that the
persisted ticket set and draw are complete before scoring a period.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import groupby
from math import comb
from typing import Any, cast

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    DAILY_539_RULE_CONTRACT,
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.domain.prize_evaluation import DAILY_FIVE39_PRIZE_RULE_CONTRACT

JsonObject = dict[str, Any]


@lru_cache(maxsize=3)
def single_ticket_probability(lottery_type: str) -> Fraction | None:
    """Count winning legal tickets exactly; Power Lotto's source is unverified."""
    if lottery_type == "BIG_LOTTO":
        rule = BIG_LOTTO_RULE_CONTRACT
        total = rule.main_number_max - rule.main_number_min + 1
        size = rule.main_number_count
        prize_rule = rule.prize_rule
        assert prize_rule is not None
        wins = sum(
            comb(size, tier.main_hits)
            * comb(total - size - 1, size - tier.main_hits - int(tier.special_hit))
            for tier in prize_rule.tiers
            if tier.tier_id != BigLottoPrizeTierId.GENERAL
            and 0 <= size - tier.main_hits - int(tier.special_hit) <= total - size - 1
        )
        return Fraction(wins, comb(total, size))
    if lottery_type == "DAILY_539":
        rule = DAILY_539_RULE_CONTRACT
        prize_rule = DAILY_FIVE39_PRIZE_RULE_CONTRACT
        prize_rule.validate()
        total = rule.main_number_max - rule.main_number_min + 1
        size = rule.main_number_count
        wins = sum(
            comb(size, tier.match_count) * comb(total - size, size - tier.match_count)
            for tier in prize_rule.tiers
        )
        return Fraction(wins, comb(total, size))
    if lottery_type == "POWER_LOTTO":
        return None
    raise ValueError("unsupported lottery type")


@lru_cache(maxsize=128, typed=True)
def iid_period_probability(lottery_type: str, ticket_count: int) -> Fraction | None:
    """Probability of the ranking event with independent tickets with replacement."""
    if type(ticket_count) is not int or ticket_count < 1:
        raise ValueError("ticket_count must be a positive integer")
    probability = single_ticket_probability(lottery_type)
    return None if probability is None else 1 - (1 - probability) ** ticket_count


def score_period(
    lottery_type: str,
    tickets: tuple[tuple[int, ...], ...],
    winning_main: tuple[int, ...],
    winning_special: int | None = None,
) -> bool | None:
    """Score complete evidence; invalid or unverified evidence remains unknown."""
    if lottery_type == "POWER_LOTTO":
        return None
    if lottery_type not in ("BIG_LOTTO", "DAILY_539"):
        raise ValueError("unsupported lottery type")
    if not tickets:
        return None
    if lottery_type == "BIG_LOTTO":
        if winning_special is None:
            return None
        try:
            scores = [
                score_big_lotto_ticket(
                    predicted_main_numbers=ticket,
                    winning_main_numbers=winning_main,
                    winning_special_number=winning_special,
                )
                for ticket in tickets
            ]
        except (TypeError, ValueError):
            return None
        tiers = (
            resolve_big_lotto_prize_tier(score.main_hits, score.special_hit) for score in scores
        )
        return any(
            isinstance(tier, BigLottoPrizeTier) and tier.tier_id != BigLottoPrizeTierId.GENERAL
            for tier in tiers
        )
    rule = DAILY_539_RULE_CONTRACT

    def valid(numbers: tuple[int, ...]) -> bool:
        return (
            type(numbers) is tuple
            and len(numbers) == rule.main_number_count
            and all(
                type(n) is int and rule.main_number_min <= n <= rule.main_number_max
                for n in numbers
            )
            and len(set(numbers)) == len(numbers)
        )

    if not valid(winning_main) or not all(valid(ticket) for ticket in tickets):
        return None
    prize_rule = DAILY_FIVE39_PRIZE_RULE_CONTRACT
    return any(
        prize_rule.resolve(match_count=len(set(ticket) & set(winning_main))) is not None
        for ticket in tickets
    )


def ranking_target_sort_key(draw_date: str, draw_id: str) -> tuple[str, int, int, str]:
    """Order dates first, then ASCII decimal IDs numerically and other IDs lexically."""
    numeric = bool(draw_id) and draw_id.isascii() and draw_id.isdecimal()
    return (draw_date, 0 if numeric else 1, int(draw_id) if numeric else 0, draw_id)


@dataclass(frozen=True)
class RankingPeriod:
    """One target within an already isolated strategy and ticket-count cohort."""

    target_draw_id: str
    target_draw_date: str
    status: str  # EVALUATED, UNKNOWN, MISSING, FAILED or NOT_ELIGIBLE
    success: bool | None = None
    ticket_count: int | None = None
    status_reason: str | None = None


def summarize_periods(lottery_type: str, periods: list[RankingPeriod], window: str) -> JsonObject:
    """Summarize one cohort; the caller must supply its complete target universe.

    Missing targets cannot be inferred from a list of existing cells. Explicit
    MISSING periods preserve that distinction from incomplete evidence.
    """
    sizes = {"FULL": None, "RECENT_750": 750, "RECENT_300": 300, "RECENT_50": 50}
    if window not in sizes:
        raise ValueError("unsupported window")
    if len({p.target_draw_id for p in periods}) != len(periods):
        raise ValueError("duplicate target")
    for period in periods:
        if period.status not in ("EVALUATED", "UNKNOWN", "MISSING", "FAILED", "NOT_ELIGIBLE"):
            raise ValueError("invalid period status")
        if period.status == "EVALUATED":
            if type(period.success) is not bool or type(period.ticket_count) is not int:
                raise ValueError("evaluated period requires success and ticket count")
            if period.ticket_count < 1 or single_ticket_probability(lottery_type) is None:
                raise ValueError("unscorable evaluated period")
        elif period.success is not None:
            raise ValueError("unknown or missing period cannot have a success value")
    ordered = sorted(
        periods, key=lambda p: ranking_target_sort_key(p.target_draw_date, p.target_draw_id)
    )
    size = sizes[window]
    selected = ordered if size is None else ordered[-size:]
    evaluated = [p for p in selected if p.status == "EVALUATED"]
    counts = {p.ticket_count for p in evaluated}
    if len(counts) > 1:
        raise ValueError("ticket counts must not be mixed in a cohort")
    successes = sum(p.success is True for p in evaluated)
    baseline: Fraction | None = None
    window_complete = bool(selected) and len(evaluated) == len(selected)
    if window_complete:
        probabilities: list[Fraction] = []
        for period in evaluated:
            assert period.ticket_count is not None
            probability = iid_period_probability(lottery_type, period.ticket_count)
            assert probability is not None
            probabilities.append(probability)
        baseline = sum(probabilities, Fraction()) / len(evaluated)
    rate = Fraction(successes, len(selected)) if window_complete else None
    return {
        "target_ids": [p.target_draw_id for p in selected],
        "start_date": selected[0].target_draw_date if selected else None,
        "end_date": selected[-1].target_draw_date if selected else None,
        "successes": successes,
        "evaluated": len(evaluated),
        "missing": sum(p.status == "MISSING" for p in selected),
        "unknown": sum(p.status == "UNKNOWN" for p in selected),
        "failed_count": sum(p.status == "FAILED" for p in selected),
        "not_eligible_count": sum(p.status == "NOT_ELIGIBLE" for p in selected),
        "status_reasons": sorted(
            {p.status_reason for p in selected if p.status_reason is not None}
        ),
        "rate": rate,
        "baseline": baseline,
        "delta": None if rate is None or baseline is None else rate - baseline,
    }


def _aggregate_ranking_materialized(
    lottery_type: str,
    window: str,
    targets: list[JsonObject],
    cells: Iterable[JsonObject],
    names: dict[tuple[str, str], str],
    run_diagnostics: list[JsonObject] | None = None,
) -> list[JsonObject]:
    """Build run-isolated cohorts from persisted evidence, without modifying it."""
    target_by_run: dict[str, dict[str, JsonObject]] = {}
    for target in targets:
        target_by_run.setdefault(target["run_id"], {})[target["target_draw_id"]] = target
    groups: dict[tuple[Any, ...], dict[str, RankingPeriod]] = {}
    discovered: set[tuple[Any, ...]] = set()
    matrix_status: dict[tuple[Any, ...], tuple[bool, str | None]] = {}
    conflicting_draws: set[tuple[str, str]] = set()
    for cell in cells:
        if cell.get("run_diagnostic") == "INVALID_MANIFEST_NO_STRATEGY_IDENTITY":
            if run_diagnostics is not None:
                run_diagnostics.append(
                    {
                        "kind": "INVALID_MANIFEST_NO_STRATEGY_IDENTITY",
                        "run_id": cell["run_id"],
                        "matrix_reason": cell["manifest_matrix_reason"],
                        "successes": 0,
                        "evaluated": 0,
                        "denominator": 0,
                        "rate": None,
                        "baseline": None,
                        "delta": None,
                        "rank": None,
                    }
                )
            continue
        run = cell["run_id"]
        draw_id = cell["target_draw_id"]
        base_key = (
            cell["strategy_id"],
            cell["strategy_version"],
            cell["execution_version"],
            cell["dataset_identity"],
            run,
            cell.get("scope_status", "MANIFEST"),
        )
        discovered.add(base_key)
        if cell.get("manifest_expected") is True:
            matrix_status[base_key] = (
                cell.get("manifest_matrix_valid") is True,
                cell.get("manifest_matrix_reason"),
            )
            continue
        if cell.get("ranking_window_included", True) is False:
            continue
        target = (
            target_by_run.get(run, {}).get(draw_id)
            if base_key[-1] in ("MANIFEST", "WINDOW_UNDETERMINED")
            else None
        )
        if target is not None and target["target_draw_date"] != cell["target_draw_date"]:
            conflicting_draws.add((run, draw_id))
        if (
            target is not None
            and not target.get("target_unverified")
            and cell.get("payload_winning_present")
        ):
            try:
                winning = cell["payload_winning_numbers"]
                if winning is not None:
                    if not isinstance(winning, dict):
                        raise ValueError("invalid winning evidence")
                    winning = cast(JsonObject, winning)
                    if "main_numbers" in winning:
                        payload_main = winning["main_numbers"]
                        target_main = json.loads(target["main"])
                        payload_main_list: list[Any] = (
                            cast(list[Any], payload_main) if isinstance(payload_main, list) else []
                        )
                        if (
                            not isinstance(payload_main, list)
                            or any(type(n) is not int for n in payload_main_list)
                            or sorted(payload_main_list) != sorted(target_main)
                        ):
                            conflicting_draws.add((run, draw_id))
                    if "special_number" in winning:
                        payload_special = winning["special_number"]
                        target_special = json.loads(target["special"])
                        if (payload_special is not None and type(payload_special) is not int) or (
                            [] if payload_special is None else [payload_special]
                        ) != target_special:
                            conflicting_draws.add((run, draw_id))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                conflicting_draws.add((run, draw_id))
        saved = cell["tickets"]
        persisted_count = cell.get("ticket_count")
        count = (persisted_count if type(persisted_count) is int else len(saved)) or None
        outcome = None
        try:
            if (
                lottery_type != "POWER_LOTTO"
                and base_key[-1] != "WINDOW_UNDETERMINED"
                and count is not None
                and len(saved) == count
                and cell["execution_status"] == "COMPLETE"
                and cell.get("ticket_evidence_valid", False)
                and target is not None
                and target["target_draw_date"] == cell["target_draw_date"]
            ):
                saved_tickets = [
                    (position, tuple(json.loads(main)), tuple(json.loads(special)))
                    for position, main, special in saved
                ]
                winning_main = tuple(json.loads(target["main"]))
                winning_special = tuple(json.loads(target["special"]))
                if (
                    [t[0] for t in saved_tickets] == list(range(1, count + 1))
                    and all(not t[2] for t in saved_tickets)
                    and (lottery_type != "BIG_LOTTO" or len(winning_special) == 1)
                    and (lottery_type != "DAILY_539" or not winning_special)
                ):
                    outcome = score_period(
                        lottery_type,
                        tuple(t[1] for t in saved_tickets),
                        winning_main,
                        winning_special[0] if winning_special else None,
                    )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        execution_status = cell.get("execution_status")
        if execution_status == "FAILED":
            period_status = "FAILED"
            period_reason = "FAILED"
        elif execution_status == "NOT_ELIGIBLE":
            period_status = "NOT_ELIGIBLE"
            period_reason = "NOT_ELIGIBLE"
        elif (
            execution_status == "MISSING"
            and target is not None
            and not target.get("target_unverified")
        ):
            period_status = "MISSING"
            period_reason = None
        else:
            period_status = "UNKNOWN" if outcome is None else "EVALUATED"
            period_reason = None if outcome is not None else str(execution_status or "UNKNOWN")
        key = (*base_key, count)
        group = groups.setdefault(key, {})
        if draw_id in group:
            conflicting_draws.add((run, draw_id))
            group[draw_id] = RankingPeriod(
                draw_id,
                cell["target_draw_date"],
                "UNKNOWN",
                status_reason="DUPLICATE_EXPECTED_KEY",
            )
        else:
            group[draw_id] = RankingPeriod(
                draw_id,
                cell["target_draw_date"],
                period_status,
                outcome if period_status == "EVALUATED" else None,
                count,
                period_reason,
            )
    # A disagreement in any linked cell invalidates that draw across all
    # strategies, regardless of iteration order.
    for key, periods in groups.items():
        run, scope = key[4], key[5]
        if scope in ("MANIFEST", "WINDOW_UNDETERMINED"):
            for draw_id, period in list(periods.items()):
                if (run, draw_id) in conflicting_draws:
                    periods[draw_id] = RankingPeriod(
                        draw_id,
                        period.target_draw_date,
                        "UNKNOWN",
                        ticket_count=period.ticket_count,
                    )
    grouped_base_keys = {key[:-1] for key in groups}
    for base_key in discovered - grouped_base_keys:
        groups[(*base_key, None)] = {}
    rows: list[JsonObject] = []
    for (strategy, version, execution, dataset, run, scope, count), periods in groups.items():
        base_key = (strategy, version, execution, dataset, run, scope)
        scoped_targets = (
            target_by_run.get(run, {}) if scope in ("MANIFEST", "WINDOW_UNDETERMINED") else {}
        )
        for draw_id, target in scoped_targets.items():
            if draw_id not in periods:
                periods[draw_id] = RankingPeriod(
                    draw_id,
                    target["target_draw_date"],
                    "UNKNOWN"
                    if (
                        scope == "WINDOW_UNDETERMINED"
                        or target.get("target_unverified")
                        or (run, draw_id) in conflicting_draws
                    )
                    else "MISSING",
                )
        summary = summarize_periods(
            lottery_type,
            list(periods.values()),
            "FULL" if scope == "WINDOW_UNDETERMINED" else window,
        )
        missing_target_evidence = (
            sum(
                bool(target_by_run.get(run, {}).get(draw_id, {}).get("target_unverified"))
                for draw_id in summary["target_ids"]
            )
            if scope in ("MANIFEST", "WINDOW_UNDETERMINED")
            else 0
        )
        conflicting_target_evidence = (
            sum((run, draw_id) in conflicting_draws for draw_id in summary["target_ids"])
            if scope in ("MANIFEST", "WINDOW_UNDETERMINED")
            else 0
        )
        rate, baseline, delta = (summary.pop(k) for k in ("rate", "baseline", "delta"))
        status_reasons = summary.pop("status_reasons", [])
        failed_count = summary.pop("failed_count", 0)
        not_eligible_count = summary.pop("not_eligible_count", 0)
        matrix_valid, matrix_reason = matrix_status.get(base_key, (True, None))
        if not matrix_valid or scope != "MANIFEST":
            rate = baseline = delta = None
        name = names.get((strategy, version)) or names.get((strategy, ""))
        reasons: list[str] = []
        if not matrix_valid:
            reasons.append(f"run matrix invalid: {matrix_reason or 'unknown reason'}")
        if scope != "MANIFEST":
            reasons.append("非 run manifest 預期格 (僅供診斷)")
        if failed_count:
            reasons.append(f"FAILED cells: {failed_count}")
        if not_eligible_count:
            reasons.append(f"NOT_ELIGIBLE cells: {not_eligible_count}")
        ordinary_unknown = summary["unknown"]
        if ordinary_unknown:
            reasons.append(
                "目標清單或日期不足, 窗口無法判定"
                if scope == "WINDOW_UNDETERMINED"
                else (
                    "不在 run 評估清單或未連結 run"
                    if scope != "MANIFEST"
                    else (
                        "現行獎規來源未核實"
                        if lottery_type == "POWER_LOTTO"
                        else "票券、開獎或注數證據不完整"
                    )
                )
            )
        reasons.extend(status_reasons)
        rows.append(
            {
                "strategy_id": strategy,
                "strategy_name": name or strategy,
                "registered": name is not None,
                "strategy_version": version,
                "execution_version": execution,
                "dataset_identity": dataset,
                "run_id": run,
                "scope_status": scope,
                "missing_target_evidence": missing_target_evidence,
                "conflicting_target_evidence": conflicting_target_evidence,
                "ticket_count": count,
                **summary,
                "failed_count": failed_count,
                "not_eligible_count": not_eligible_count,
                "rate": None if rate is None else float(rate),
                "baseline": None if baseline is None else float(baseline),
                "delta": None if delta is None else float(delta),
                "unknown_reason": "; ".join(reasons) if reasons else None,
                "rank": None,
            }
        )
    cohorts: dict[tuple[Any, ...], list[JsonObject]] = {}
    for row in rows:
        if (
            row["scope_status"] == "MANIFEST"
            and row["rate"] is not None
            and not row["unknown"]
            and not row["missing"]
            and row["ticket_count"] is not None
        ):
            cohorts.setdefault(
                (
                    row["ticket_count"],
                    row["dataset_identity"],
                    row["execution_version"],
                    row["run_id"],
                    tuple(row["target_ids"]),
                ),
                [],
            ).append(row)
    for cohort in cohorts.values():
        cohort.sort(
            key=lambda row: (
                -Fraction(row["successes"], row["evaluated"]),
                row["strategy_id"],
            )
        )
        for rank, row in enumerate(cohort, 1):
            row["rank"] = rank
    return rows


def aggregate_ranking(
    lottery_type: str,
    window: str,
    targets: list[JsonObject],
    cells: Iterable[JsonObject],
    names: dict[tuple[str, str], str],
    *,
    run_diagnostics: list[JsonObject] | None = None,
) -> list[JsonObject]:
    """Aggregate contiguous run groups, releasing per-period state per run."""
    target_groups: dict[str, list[JsonObject]] = {}
    for target in targets:
        target_groups.setdefault(target["run_id"], []).append(target)
    rows: list[JsonObject] = []
    completed: set[str] = set()
    for run_id, group in groupby(cells, key=lambda cell: cell["run_id"]):
        if run_id in completed:
            raise ValueError("ranking input must have contiguous run groups")
        completed.add(run_id)
        rows.extend(
            _aggregate_ranking_materialized(
                lottery_type,
                window,
                target_groups.get(run_id, []),
                group,
                names,
                run_diagnostics,
            )
        )
    return rows
