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

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    DAILY_539_RULE_CONTRACT,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.domain.prize_evaluation import DAILY_FIVE39_PRIZE_RULE_CONTRACT


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
            if 0 <= size - tier.main_hits - int(tier.special_hit) <= total - size - 1
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
    """Probability of any prize with independent uniform tickets with replacement."""
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
        return any(
            resolve_big_lotto_prize_tier(score.main_hits, score.special_hit)
            != NoPrizeResult.NO_PRIZE
            for score in scores
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


@dataclass(frozen=True)
class RankingPeriod:
    """One target within an already isolated strategy and ticket-count cohort."""

    target_draw_id: str
    target_draw_date: str
    status: str  # EVALUATED, UNKNOWN or MISSING
    success: bool | None = None
    ticket_count: int | None = None


def summarize_periods(
    lottery_type: str, periods: list[RankingPeriod], window: str
) -> dict[str, object]:
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
        if period.status not in ("EVALUATED", "UNKNOWN", "MISSING"):
            raise ValueError("invalid period status")
        if period.status == "EVALUATED":
            if type(period.success) is not bool or type(period.ticket_count) is not int:
                raise ValueError("evaluated period requires success and ticket count")
            if period.ticket_count < 1 or single_ticket_probability(lottery_type) is None:
                raise ValueError("unscorable evaluated period")
        elif period.success is not None:
            raise ValueError("unknown or missing period cannot have a success value")
    ordered = sorted(periods, key=lambda p: (p.target_draw_date, p.target_draw_id))
    size = sizes[window]
    selected = ordered if size is None else ordered[-size:]
    evaluated = [p for p in selected if p.status == "EVALUATED"]
    counts = {p.ticket_count for p in evaluated}
    if len(counts) > 1:
        raise ValueError("ticket counts must not be mixed in a cohort")
    successes = sum(p.success is True for p in evaluated)
    baseline = (
        sum((iid_period_probability(lottery_type, p.ticket_count) for p in evaluated), Fraction())
        / len(evaluated)
        if evaluated
        else None
    )
    rate = Fraction(successes, len(evaluated)) if evaluated else None
    return {
        "target_ids": [p.target_draw_id for p in selected],
        "start_date": selected[0].target_draw_date if selected else None,
        "end_date": selected[-1].target_draw_date if selected else None,
        "successes": successes,
        "evaluated": len(evaluated),
        "missing": sum(p.status == "MISSING" for p in selected),
        "unknown": sum(p.status == "UNKNOWN" for p in selected),
        "rate": rate,
        "baseline": baseline,
        "delta": None if rate is None or baseline is None else rate - baseline,
    }


def _aggregate_ranking_materialized(
    lottery_type: str,
    window: str,
    targets: list[dict],
    cells: Iterable[dict],
    names: dict[tuple[str, str], str],
) -> list[dict]:
    """Build run-isolated cohorts from persisted evidence, without modifying it."""
    target_by_run: dict[str, dict[str, dict]] = {}
    for target in targets:
        target_by_run.setdefault(target["run_id"], {})[target["target_draw_id"]] = target
    groups: dict[tuple, dict[str, RankingPeriod]] = {}
    discovered: set[tuple] = set()
    conflicting_draws: set[tuple[str, str]] = set()
    for cell in cells:
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
                    if "main_numbers" in winning:
                        payload_main = winning["main_numbers"]
                        target_main = json.loads(target["main"])
                        if (
                            not isinstance(payload_main, list)
                            or any(type(n) is not int for n in payload_main)
                            or sorted(payload_main) != sorted(target_main)
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
        key = (*base_key, count)
        groups.setdefault(key, {})[draw_id] = RankingPeriod(
            draw_id,
            cell["target_draw_date"],
            "UNKNOWN" if outcome is None else "EVALUATED",
            outcome,
            count,
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
    rows = []
    for (strategy, version, execution, dataset, run, scope, count), periods in groups.items():
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
        name = names.get((strategy, version)) or names.get((strategy, ""))
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
                "rate": None if rate is None else float(rate),
                "baseline": None if baseline is None else float(baseline),
                "delta": None if delta is None else float(delta),
                "unknown_reason": (
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
                if summary["unknown"]
                else None,
                "rank": None,
            }
        )
    cohorts: dict[tuple, list[dict]] = {}
    for row in rows:
        if (
            row["rate"] is not None
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
        cohort.sort(key=lambda row: (-row["rate"], row["strategy_id"]))
        for rank, row in enumerate(cohort, 1):
            row["rank"] = rank
    return rows


def aggregate_ranking(
    lottery_type: str,
    window: str,
    targets: list[dict],
    cells: Iterable[dict],
    names: dict[tuple[str, str], str],
) -> list[dict]:
    """Aggregate contiguous run groups, releasing per-period state per run."""
    target_groups: dict[str, list[dict]] = {}
    for target in targets:
        target_groups.setdefault(target["run_id"], []).append(target)
    rows: list[dict] = []
    completed: set[str] = set()
    for run_id, group in groupby(cells, key=lambda cell: cell["run_id"]):
        if run_id in completed:
            raise ValueError("ranking input must have contiguous run groups")
        completed.add(run_id)
        rows.extend(
            _aggregate_ranking_materialized(
                lottery_type, window, target_groups.get(run_id, []), group, names
            )
        )
    return rows
