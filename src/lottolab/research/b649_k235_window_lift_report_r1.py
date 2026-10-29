"""Compare BIG_LOTTO K=2/3/5 native portfolios on common historical targets.

The evaluator is pure: callers supply chronological realized draws and native
ticket outputs. It never opens a database, replays a strategy, ranks results,
or infers future performance. A period wins once when any ticket resolves to
an official prize under :mod:`lottolab.domain.lottery_rules`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, permutations
from math import comb, fsum, sqrt

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.research.exact_statistics import (
    binomial_two_sided_exact_p_value,
    binomial_upper_tail,
)

K_VALUES = (2, 3, 5)
WINDOWS: tuple[tuple[str, int | None], ...] = (
    ("FULL", None),
    ("RECENT_50", 50),
    ("RECENT_300", 300),
    ("RECENT_750", 750),
    ("RECENT_1500", 1500),
)

# Exact fractions for portfolios whose six-number tickets are pairwise
# number-disjoint. They match the committed official-prize evaluator's
# 6.1724283504%, 9.2317509739%, and 15.2966131173% references.
ZERO_OVERLAP_RANDOM_BASELINES: dict[int, Fraction] = {
    2: Fraction(220_923, 3_579_191),
    3: Fraction(330_422, 3_579_191),
    5: Fraction(547_495, 3_579_191),
}

RESEARCH_CAVEAT = (
    "Historical rates, intervals, and p-values describe the supplied history. "
    "A small p-value does not prove a future advantage; no ranking or "
    "multiple-comparison adjustment is applied."
)
_WILSON_Z_95 = 1.959963984540054
_WILSON_Z_97_5 = 2.241402727604947
_POISSON_BINOMIAL_TOLERANCE = 1e-14

type Ticket = tuple[int, ...]


class K235WindowLiftError(ValueError):
    """The supplied draw or replay inputs violate the evaluation contract."""


class PredictionStatus(StrEnum):
    OK = "OK"
    FAILED = "FAILED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class TargetStatus(StrEnum):
    EVALUABLE = "EVALUABLE"
    MISSING = "MISSING"
    FAILED = "FAILED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True, slots=True)
class HistoricalDrawOutcome:
    """One realized BIG_LOTTO draw; input sequences must be chronological."""

    draw_id: str
    draw_date: date
    winning_main_numbers: tuple[int, ...]
    winning_special_number: int

    def __post_init__(self) -> None:
        _require_text(self.draw_id, "draw_id")
        if type(self.draw_date) is not date:
            raise K235WindowLiftError("draw_date must be a date, not a datetime")
        numbers = _normalize_numbers(
            self.winning_main_numbers,
            label=f"winning_main_numbers for {self.draw_id}",
        )
        object.__setattr__(self, "winning_main_numbers", numbers)
        special = self.winning_special_number
        if type(special) is not int:
            raise K235WindowLiftError("winning_special_number must be an exact integer")
        rule = BIG_LOTTO_RULE_CONTRACT
        if not rule.special_number_min <= special <= rule.special_number_max:
            raise K235WindowLiftError("winning_special_number is outside the BIG_LOTTO range")
        if special in numbers:
            raise K235WindowLiftError(
                "winning_special_number must not overlap winning main numbers"
            )


@dataclass(frozen=True, slots=True)
class StrategyTargetReplay:
    """One strategy's native ticket output or typed replay status for a target."""

    strategy_id: str
    draw_id: str
    native_tickets: Sequence[Sequence[int]] | None
    status: PredictionStatus = PredictionStatus.OK
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.strategy_id, "strategy_id")
        _require_text(self.draw_id, "draw_id")
        status = self.status
        if type(status) is str:
            try:
                status = PredictionStatus(status)
            except ValueError as exc:
                raise K235WindowLiftError(
                    f"unsupported prediction status: {self.status!r}"
                ) from exc
            object.__setattr__(self, "status", status)
        elif type(status) is not PredictionStatus:
            raise K235WindowLiftError("status must be a PredictionStatus")
        if self.failure_reason is not None and (
            type(self.failure_reason) is not str or not self.failure_reason.strip()
        ):
            raise K235WindowLiftError("failure_reason must be non-empty text or None")


@dataclass(frozen=True, slots=True)
class K235TargetResult:
    draw_id: str
    draw_index: int
    status: TargetStatus
    official_any_prize: bool | None
    random_probability: Fraction | None
    random_probability_method: str | None
    has_number_overlap: bool | None
    native_ticket_count: int | None
    distinct_ticket_count: int | None
    reason_code: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "draw_id": self.draw_id,
            "draw_index": self.draw_index,
            "status": self.status.value,
            "official_any_prize": self.official_any_prize,
            "random_probability": _fraction_payload(self.random_probability),
            "random_probability_method": self.random_probability_method,
            "has_number_overlap": self.has_number_overlap,
            "native_ticket_count": self.native_ticket_count,
            "distinct_ticket_count": self.distinct_ticket_count,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class StatisticalResult:
    method: str
    expected_random_successes: float
    upper_tail_p_value: float
    two_sided_p_value: float
    two_sided_definition: str
    numeric_representation: str = "FLOAT64"

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "expected_random_successes": self.expected_random_successes,
            "upper_tail_p_value": self.upper_tail_p_value,
            "two_sided_p_value": self.two_sided_p_value,
            "two_sided_definition": self.two_sided_definition,
            "numeric_representation": self.numeric_representation,
        }


@dataclass(frozen=True, slots=True)
class K235WindowMetric:
    strategy_id: str
    k: int
    window: str
    requested_target_periods: int | None
    target_period_count: int
    first_draw_id: str | None
    last_draw_id: str | None
    official_any_prize_success_count: int
    denominator: int
    historical_win_rate: Fraction | None
    random_baseline_probability: Fraction | None
    relative_random_gain: Fraction | None
    relative_random_gain_percentage_points: float | None
    win_rate_ci_95: tuple[float, float] | None
    win_rate_ci_method: str
    random_gain_ci_95_percentage_points: tuple[float, float] | None
    random_gain_ci_method: str
    statistical_result: StatisticalResult | None
    missing_period_count: int
    failed_period_count: int
    not_evaluable_period_count: int
    overlap_period_count: int
    random_probability_method_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "k": self.k,
            "window": self.window,
            "requested_target_periods": self.requested_target_periods,
            "target_period_count": self.target_period_count,
            "first_draw_id": self.first_draw_id,
            "last_draw_id": self.last_draw_id,
            "official_any_prize_success_count": self.official_any_prize_success_count,
            "denominator": self.denominator,
            "historical_win_rate": _fraction_payload(self.historical_win_rate),
            "random_baseline_probability": _fraction_payload(self.random_baseline_probability),
            "relative_random_gain": _fraction_payload(self.relative_random_gain),
            "relative_random_gain_percentage_points": self.relative_random_gain_percentage_points,
            "win_rate_ci_95": list(self.win_rate_ci_95) if self.win_rate_ci_95 else None,
            "win_rate_ci_method": self.win_rate_ci_method,
            "random_gain_ci_95_percentage_points": (
                list(self.random_gain_ci_95_percentage_points)
                if self.random_gain_ci_95_percentage_points
                else None
            ),
            "random_gain_ci_method": self.random_gain_ci_method,
            "statistical_result": (
                self.statistical_result.to_dict() if self.statistical_result else None
            ),
            "missing_period_count": self.missing_period_count,
            "failed_period_count": self.failed_period_count,
            "not_evaluable_period_count": self.not_evaluable_period_count,
            "overlap_period_count": self.overlap_period_count,
            "random_probability_method_counts": dict(self.random_probability_method_counts),
        }


@dataclass(frozen=True, slots=True)
class K235StrategyReport:
    strategy_id: str
    k: int
    target_results: tuple[K235TargetResult, ...]
    windows: tuple[K235WindowMetric, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "k": self.k,
            "windows": [metric.to_dict() for metric in self.windows],
            "target_results": [result.to_dict() for result in self.target_results],
        }


@dataclass(frozen=True, slots=True)
class PairedWindowComparison:
    strategy_a_id: str
    strategy_b_id: str
    k: int
    window: str
    target_period_count: int
    common_evaluable_period_count: int
    strategy_a_success_count: int
    strategy_b_success_count: int
    both_success_count: int
    neither_success_count: int
    strategy_a_only_success_count: int
    strategy_b_only_success_count: int
    paired_success_rate_difference: Fraction | None
    paired_difference_percentage_points: float | None
    paired_difference_ci_95_percentage_points: tuple[float, float] | None
    paired_difference_ci_method: str | None
    mcnemar_exact_two_sided_p_value: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_a_id": self.strategy_a_id,
            "strategy_b_id": self.strategy_b_id,
            "k": self.k,
            "window": self.window,
            "target_period_count": self.target_period_count,
            "common_evaluable_period_count": self.common_evaluable_period_count,
            "strategy_a_success_count": self.strategy_a_success_count,
            "strategy_b_success_count": self.strategy_b_success_count,
            "both_success_count": self.both_success_count,
            "neither_success_count": self.neither_success_count,
            "strategy_a_only_success_count": self.strategy_a_only_success_count,
            "strategy_b_only_success_count": self.strategy_b_only_success_count,
            "paired_success_rate_difference": _fraction_payload(
                self.paired_success_rate_difference
            ),
            "paired_difference_percentage_points": self.paired_difference_percentage_points,
            "paired_difference_ci_95_percentage_points": (
                list(self.paired_difference_ci_95_percentage_points)
                if self.paired_difference_ci_95_percentage_points
                else None
            ),
            "paired_difference_ci_method": self.paired_difference_ci_method,
            "mcnemar_exact_two_sided_p_value": self.mcnemar_exact_two_sided_p_value,
        }


@dataclass(frozen=True, slots=True)
class K235WindowLiftReport:
    history_draw_count: int
    strategy_reports: tuple[K235StrategyReport, ...]
    incumbent_strategy_id: str | None
    incumbent_comparisons: tuple[PairedWindowComparison, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "B649_K235_WINDOW_LIFT_REPORT_R1",
            "event_definition": "OFFICIAL_ANY_PRIZE via resolve_big_lotto_prize_tier",
            "history_draw_count": self.history_draw_count,
            "windows": [{"name": name, "requested_target_periods": size} for name, size in WINDOWS],
            "k_values": list(K_VALUES),
            "zero_overlap_random_baselines": {
                str(k): _fraction_payload(probability)
                for k, probability in ZERO_OVERLAP_RANDOM_BASELINES.items()
            },
            "incumbent_strategy_id": self.incumbent_strategy_id,
            "strategies": [report.to_dict() for report in self.strategy_reports],
            "incumbent_comparisons": [
                comparison.to_dict() for comparison in self.incumbent_comparisons
            ],
            "statistical_caveat": RESEARCH_CAVEAT,
        }


def evaluate_k235_history(
    outcomes: Sequence[HistoricalDrawOutcome],
    predictions: Sequence[StrategyTargetReplay],
    *,
    incumbent_strategy_id: str | None = None,
) -> K235WindowLiftReport:
    """Evaluate each strategy's ordered native prefixes on the supplied targets.

    Window selection uses the last N target draws in input chronology. Missing,
    failed, and non-evaluable periods remain visible but never enter a rate's
    denominator. For each evaluable target, the random reference conditions on
    the exact K-ticket geometry, including overlap within the portfolio.
    """

    draw_ids = _validate_outcomes(outcomes)
    if not predictions:
        raise K235WindowLiftError("predictions must contain at least one strategy row")
    by_strategy_draw: dict[tuple[str, str], StrategyTargetReplay] = {}
    strategy_ids: list[str] = []
    for replay in predictions:
        if replay.draw_id not in draw_ids:
            raise K235WindowLiftError(
                f"prediction for {replay.strategy_id} references unknown draw {replay.draw_id}"
            )
        key = (replay.strategy_id, replay.draw_id)
        if key in by_strategy_draw:
            raise K235WindowLiftError(
                f"duplicate prediction for {replay.strategy_id} on draw {replay.draw_id}"
            )
        by_strategy_draw[key] = replay
        if replay.strategy_id not in strategy_ids:
            strategy_ids.append(replay.strategy_id)

    if incumbent_strategy_id is not None:
        _require_text(incumbent_strategy_id, "incumbent_strategy_id")
        if incumbent_strategy_id not in strategy_ids:
            raise K235WindowLiftError("incumbent_strategy_id has no prediction rows")

    strategy_reports: list[K235StrategyReport] = []
    for strategy_id in strategy_ids:
        for k in K_VALUES:
            target_results = tuple(
                _evaluate_target(
                    strategy_id,
                    index,
                    outcome,
                    by_strategy_draw.get((strategy_id, outcome.draw_id)),
                    k,
                )
                for index, outcome in enumerate(outcomes)
            )
            strategy_reports.append(
                K235StrategyReport(
                    strategy_id=strategy_id,
                    k=k,
                    target_results=target_results,
                    windows=_evaluate_windows(strategy_id, k, target_results),
                )
            )

    report = K235WindowLiftReport(
        history_draw_count=len(outcomes),
        strategy_reports=tuple(strategy_reports),
        incumbent_strategy_id=incumbent_strategy_id,
        incumbent_comparisons=(),
    )
    comparisons: list[PairedWindowComparison] = []
    if incumbent_strategy_id is not None:
        for strategy_id in strategy_ids:
            if strategy_id == incumbent_strategy_id:
                continue
            for k in K_VALUES:
                for window, _size in WINDOWS:
                    comparisons.append(
                        compare_k235_strategies(
                            report,
                            strategy_id,
                            incumbent_strategy_id,
                            k=k,
                            window=window,
                        )
                    )
    return K235WindowLiftReport(
        history_draw_count=report.history_draw_count,
        strategy_reports=report.strategy_reports,
        incumbent_strategy_id=incumbent_strategy_id,
        incumbent_comparisons=tuple(comparisons),
    )


def compare_k235_strategies(
    report: K235WindowLiftReport,
    strategy_a_id: str,
    strategy_b_id: str,
    *,
    k: int,
    window: str,
) -> PairedWindowComparison:
    """Compare two strategies only on the same evaluable target draw IDs."""

    if k not in K_VALUES:
        raise K235WindowLiftError(f"k must be one of {K_VALUES}")
    window_size = _window_size(window)
    if strategy_a_id == strategy_b_id:
        raise K235WindowLiftError("paired comparison requires two different strategies")
    left = _find_strategy_report(report, strategy_a_id, k)
    right = _find_strategy_report(report, strategy_b_id, k)
    if len(left.target_results) != len(right.target_results):
        raise K235WindowLiftError("strategy reports do not share the same history targets")
    start = max(0, report.history_draw_count - window_size) if window_size else 0
    target_count = report.history_draw_count - start
    left_by_id = {result.draw_id: result for result in left.target_results[start:]}
    right_by_id = {result.draw_id: result for result in right.target_results[start:]}
    common = [
        (left_by_id[draw_id], right_by_id[draw_id])
        for draw_id in left_by_id.keys() & right_by_id.keys()
        if left_by_id[draw_id].status is TargetStatus.EVALUABLE
        and right_by_id[draw_id].status is TargetStatus.EVALUABLE
    ]
    left_only = sum(
        int(left_result.official_any_prize is True and right_result.official_any_prize is False)
        for left_result, right_result in common
    )
    right_only = sum(
        int(right_result.official_any_prize is True and left_result.official_any_prize is False)
        for left_result, right_result in common
    )
    both = sum(
        int(left_result.official_any_prize is True and right_result.official_any_prize is True)
        for left_result, right_result in common
    )
    neither = len(common) - left_only - right_only - both
    denominator = len(common)
    difference = Fraction(left_only - right_only, denominator) if denominator else None
    ci = _paired_difference_interval(left_only, right_only, denominator)
    discordant = left_only + right_only
    mcnemar = binomial_two_sided_exact_p_value(discordant, left_only, 0.5) if denominator else None
    if mcnemar is not None and mcnemar >= 1.0 - 1e-14:
        mcnemar = 1.0
    return PairedWindowComparison(
        strategy_a_id=strategy_a_id,
        strategy_b_id=strategy_b_id,
        k=k,
        window=window,
        target_period_count=target_count,
        common_evaluable_period_count=denominator,
        strategy_a_success_count=left_only + both,
        strategy_b_success_count=right_only + both,
        both_success_count=both,
        neither_success_count=neither,
        strategy_a_only_success_count=left_only,
        strategy_b_only_success_count=right_only,
        paired_success_rate_difference=difference,
        paired_difference_percentage_points=(
            float(difference) * 100 if difference is not None else None
        ),
        paired_difference_ci_95_percentage_points=(
            (ci[0] * 100, ci[1] * 100) if ci is not None else None
        ),
        paired_difference_ci_method=("BONFERRONI_WILSON_95_PERCENT" if ci is not None else None),
        mcnemar_exact_two_sided_p_value=mcnemar,
    )


def evaluate_native_k235_history(
    outcomes: Sequence[HistoricalDrawOutcome],
    predictions: Sequence[StrategyTargetReplay],
    native_ticket_counts: Mapping[str, int],
) -> K235WindowLiftReport:
    """Evaluate only each frozen strategy's native K, without taking prefixes.

    The original prefix evaluator remains available. This adapter preserves
    the C strategy pool, including identities with no evaluable predictions.
    """
    draw_ids = _validate_outcomes(outcomes)
    if not native_ticket_counts or any(
        type(k) is not int or k not in K_VALUES for k in native_ticket_counts.values()
    ):
        raise K235WindowLiftError("native_ticket_counts must specify K2/K3/K5 identities")
    indexed: dict[tuple[str, str], StrategyTargetReplay] = {}
    for replay in predictions:
        if replay.strategy_id not in native_ticket_counts or replay.draw_id not in draw_ids:
            raise K235WindowLiftError("prediction references an unknown native identity or target")
        key = replay.strategy_id, replay.draw_id
        if key in indexed:
            raise K235WindowLiftError("duplicate native prediction")
        if replay.status is PredictionStatus.OK and (
            replay.native_tickets is None
            or len(replay.native_tickets) != native_ticket_counts[replay.strategy_id]
        ):
            raise K235WindowLiftError("COMPLETE native portfolio must contain exactly K tickets")
        indexed[key] = replay
    reports: list[K235StrategyReport] = []
    for strategy_id, k in sorted(native_ticket_counts.items()):
        results = tuple(
            _evaluate_target(
                strategy_id, index, outcome, indexed.get((strategy_id, outcome.draw_id)), k
            )
            for index, outcome in enumerate(outcomes)
        )
        reports.append(
            K235StrategyReport(strategy_id, k, results, _evaluate_windows(strategy_id, k, results))
        )
    return K235WindowLiftReport(len(outcomes), tuple(reports), None, ())


def exact_portfolio_random_probability(tickets: Sequence[Sequence[int]]) -> Fraction:
    """Exact fair-draw chance that this native ticket group wins any prize.

    Pairwise number-disjoint K2/K3/K5 groups use the task's exact zero-overlap
    reference. Any group with a number overlap is evaluated from its full
    incidence geometry and never borrows that reference.
    """

    normalized = tuple(_normalize_ticket(ticket, label="ticket") for ticket in tickets)
    if not normalized:
        raise K235WindowLiftError("tickets must contain at least one ticket")
    if len(normalized) not in K_VALUES:
        raise K235WindowLiftError(f"ticket group size must be one of {K_VALUES}")
    has_overlap = _has_number_overlap(normalized)
    if not has_overlap and len(normalized) in ZERO_OVERLAP_RANDOM_BASELINES:
        return ZERO_OVERLAP_RANDOM_BASELINES[len(normalized)]
    profile = _canonical_incidence_profile(normalized)
    return _probability_from_incidence_profile(len(normalized), profile)


def _evaluate_target(
    strategy_id: str,
    draw_index: int,
    outcome: HistoricalDrawOutcome,
    replay: StrategyTargetReplay | None,
    k: int,
) -> K235TargetResult:
    if replay is None:
        return _not_evaluable_result(
            outcome.draw_id, draw_index, TargetStatus.MISSING, "MISSING_PREDICTION"
        )
    if replay.status is PredictionStatus.FAILED:
        return _not_evaluable_result(
            outcome.draw_id,
            draw_index,
            TargetStatus.FAILED,
            replay.failure_reason or "REPLAY_FAILED",
        )
    if replay.status is PredictionStatus.NOT_EVALUABLE:
        return _not_evaluable_result(
            outcome.draw_id,
            draw_index,
            TargetStatus.NOT_EVALUABLE,
            replay.failure_reason or "REPLAY_NOT_EVALUABLE",
        )
    native_tickets = replay.native_tickets
    if native_tickets is None:
        return _not_evaluable_result(
            outcome.draw_id, draw_index, TargetStatus.NOT_EVALUABLE, "MISSING_NATIVE_TICKETS"
        )
    try:
        if len(native_tickets) < k:
            return _not_evaluable_result(
                outcome.draw_id,
                draw_index,
                TargetStatus.NOT_EVALUABLE,
                "NATIVE_TICKET_COUNT_BELOW_K",
            )
        tickets = tuple(
            _normalize_ticket(ticket, label=f"{strategy_id} ticket {position}")
            for position, ticket in enumerate(native_tickets[:k], start=1)
        )
    except (TypeError, ValueError, K235WindowLiftError) as exc:
        return _not_evaluable_result(
            outcome.draw_id,
            draw_index,
            TargetStatus.NOT_EVALUABLE,
            f"INVALID_NATIVE_TICKET:{exc}",
        )

    success = False
    for ticket in tickets:
        score = score_big_lotto_ticket(
            predicted_main_numbers=ticket,
            winning_main_numbers=outcome.winning_main_numbers,
            winning_special_number=outcome.winning_special_number,
        )
        tier = resolve_big_lotto_prize_tier(score.main_hits, score.special_hit)
        if tier is not NoPrizeResult.NO_PRIZE:
            success = True
            break

    overlap = _has_number_overlap(tickets)
    probability = exact_portfolio_random_probability(tickets)
    method = "EXACT_OVERLAPPING_PORTFOLIO" if overlap else "ZERO_OVERLAP_REFERENCE"
    return K235TargetResult(
        draw_id=outcome.draw_id,
        draw_index=draw_index,
        status=TargetStatus.EVALUABLE,
        official_any_prize=success,
        random_probability=probability,
        random_probability_method=method,
        has_number_overlap=overlap,
        native_ticket_count=len(native_tickets),
        distinct_ticket_count=len(set(tickets)),
        reason_code=None,
    )


def _not_evaluable_result(
    draw_id: str,
    draw_index: int,
    status: TargetStatus,
    reason_code: str,
) -> K235TargetResult:
    return K235TargetResult(
        draw_id=draw_id,
        draw_index=draw_index,
        status=status,
        official_any_prize=None,
        random_probability=None,
        random_probability_method=None,
        has_number_overlap=None,
        native_ticket_count=None,
        distinct_ticket_count=None,
        reason_code=reason_code,
    )


def _evaluate_windows(
    strategy_id: str,
    k: int,
    results: tuple[K235TargetResult, ...],
) -> tuple[K235WindowMetric, ...]:
    selected_by_window: dict[str, tuple[K235TargetResult, ...]] = {}
    suffix_lengths: set[int] = set()
    for window, size in WINDOWS:
        start = max(0, len(results) - size) if size is not None else 0
        selected = results[start:]
        selected_by_window[window] = selected
        suffix_lengths.add(sum(result.status is TargetStatus.EVALUABLE for result in selected))

    all_probabilities = tuple(
        result.random_probability
        for result in results
        if result.status is TargetStatus.EVALUABLE and result.random_probability is not None
    )
    has_heterogeneous_null = bool(all_probabilities) and any(
        probability != all_probabilities[0] for probability in all_probabilities[1:]
    )
    distributions = (
        _poisson_binomial_suffix_distributions(all_probabilities, suffix_lengths)
        if has_heterogeneous_null
        else {}
    )
    metrics: list[K235WindowMetric] = []
    for window, size in WINDOWS:
        selected = selected_by_window[window]
        eligible = tuple(result for result in selected if result.status is TargetStatus.EVALUABLE)
        denominator = len(eligible)
        successes = sum(result.official_any_prize is True for result in eligible)
        probability_sum = sum(
            (
                result.random_probability
                for result in eligible
                if result.random_probability is not None
            ),
            Fraction(0),
        )
        baseline = probability_sum / denominator if denominator else None
        rate = Fraction(successes, denominator) if denominator else None
        rate_ci = _wilson_interval(successes, denominator)
        gain_fraction = rate - baseline if rate is not None and baseline is not None else None
        gain = float(gain_fraction) * 100 if gain_fraction is not None else None
        gain_ci = (
            ((rate_ci[0] - float(baseline)) * 100, (rate_ci[1] - float(baseline)) * 100)
            if rate_ci is not None and baseline is not None
            else None
        )
        p_values = tuple(
            result.random_probability
            for result in eligible
            if result.random_probability is not None
        )
        distribution = distributions.get(denominator)
        statistical = _statistical_result(p_values, successes, distribution)
        statuses = Counter(result.status for result in selected)
        methods = Counter(
            result.random_probability_method
            for result in eligible
            if result.random_probability_method is not None
        )
        metrics.append(
            K235WindowMetric(
                strategy_id=strategy_id,
                k=k,
                window=window,
                requested_target_periods=size,
                target_period_count=len(selected),
                first_draw_id=selected[0].draw_id if selected else None,
                last_draw_id=selected[-1].draw_id if selected else None,
                official_any_prize_success_count=successes,
                denominator=denominator,
                historical_win_rate=rate,
                random_baseline_probability=baseline,
                relative_random_gain=gain_fraction,
                relative_random_gain_percentage_points=gain,
                win_rate_ci_95=rate_ci,
                win_rate_ci_method="WILSON_SCORE_95_PERCENT",
                random_gain_ci_95_percentage_points=gain_ci,
                random_gain_ci_method=("WILSON_RATE_INTERVAL_MINUS_EXACT_MEAN_RANDOM_BASELINE"),
                statistical_result=statistical,
                missing_period_count=statuses[TargetStatus.MISSING],
                failed_period_count=statuses[TargetStatus.FAILED],
                not_evaluable_period_count=statuses[TargetStatus.NOT_EVALUABLE],
                overlap_period_count=sum(result.has_number_overlap is True for result in eligible),
                random_probability_method_counts=tuple(
                    sorted((method, count) for method, count in methods.items())
                ),
            )
        )
    return tuple(metrics)


def _statistical_result(
    probabilities: tuple[Fraction, ...],
    observed_successes: int,
    distribution: tuple[float, ...] | None,
) -> StatisticalResult | None:
    if not probabilities:
        return None
    expected = fsum(float(probability) for probability in probabilities)
    if all(probability == probabilities[0] for probability in probabilities):
        probability = float(probabilities[0])
        return StatisticalResult(
            method="EXACT_BINOMIAL_TAILS_FLOAT64",
            expected_random_successes=expected,
            upper_tail_p_value=binomial_upper_tail(
                len(probabilities), observed_successes, probability
            ),
            two_sided_p_value=binomial_two_sided_exact_p_value(
                len(probabilities), observed_successes, probability
            ),
            two_sided_definition="EXACT_BINOMIAL_PROBABILITY_ORDERING",
        )
    if distribution is None:
        return None
    observed_mass = distribution[observed_successes]
    upper_tail = fsum(distribution[observed_successes:])
    cutoff = observed_mass + _POISSON_BINOMIAL_TOLERANCE * max(1.0, observed_mass)
    two_sided = fsum(mass for mass in distribution if mass <= cutoff)
    return StatisticalResult(
        method="POISSON_BINOMIAL_DP_FLOAT64",
        expected_random_successes=expected,
        upper_tail_p_value=min(1.0, max(0.0, upper_tail)),
        two_sided_p_value=min(1.0, max(0.0, two_sided)),
        two_sided_definition="POISSON_BINOMIAL_PROBABILITY_ORDERING",
    )


def _poisson_binomial_suffix_distributions(
    probabilities: tuple[Fraction, ...], wanted_lengths: set[int]
) -> dict[int, tuple[float, ...]]:
    lengths = {length for length in wanted_lengths if 0 < length <= len(probabilities)}
    if not lengths:
        return {}
    distributions: dict[int, tuple[float, ...]] = {}
    masses = [1.0]
    for size, probability in enumerate(reversed(probabilities), start=1):
        p = float(probability)
        next_masses = [0.0] * (size + 1)
        for successes, mass in enumerate(masses):
            next_masses[successes] += mass * (1.0 - p)
            next_masses[successes + 1] += mass * p
        masses = next_masses
        if size in lengths:
            total = fsum(masses)
            distributions[size] = tuple(mass / total for mass in masses)
        if size == max(lengths):
            break
    return distributions


def _paired_difference_interval(
    left_only: int, right_only: int, denominator: int
) -> tuple[float, float] | None:
    if denominator == 0:
        return None
    left_interval = _wilson_interval(left_only, denominator, z=_WILSON_Z_97_5)
    right_interval = _wilson_interval(right_only, denominator, z=_WILSON_Z_97_5)
    assert left_interval is not None and right_interval is not None
    return (
        max(-1.0, left_interval[0] - right_interval[1]),
        min(1.0, left_interval[1] - right_interval[0]),
    )


def _wilson_interval(
    successes: int, denominator: int, *, z: float = _WILSON_Z_95
) -> tuple[float, float] | None:
    if denominator == 0:
        return None
    p = successes / denominator
    z2 = z * z
    divisor = 1.0 + z2 / denominator
    center = (p + z2 / (2.0 * denominator)) / divisor
    radius = z * sqrt(p * (1.0 - p) / denominator + z2 / (4.0 * denominator**2)) / divisor
    return max(0.0, center - radius), min(1.0, center + radius)


@lru_cache(maxsize=8192)
def _probability_from_incidence_profile(ticket_count: int, profile: tuple[int, ...]) -> Fraction:
    if ticket_count <= 0 or len(profile) != (1 << ticket_count) - 1:
        raise K235WindowLiftError("ticket incidence profile is malformed")
    tickets: list[list[int]] = [[] for _ in range(ticket_count)]
    next_number = BIG_LOTTO_RULE_CONTRACT.main_number_min
    for incidence_mask, multiplicity in enumerate(profile, start=1):
        for _ in range(multiplicity):
            if next_number > BIG_LOTTO_RULE_CONTRACT.main_number_max:
                raise K235WindowLiftError("ticket incidence profile exceeds the number pool")
            for position in range(ticket_count):
                if incidence_mask & (1 << position):
                    tickets[position].append(next_number)
            next_number += 1
    normalized = tuple(tuple(ticket) for ticket in tickets)
    # Same intersection enumeration and integer weights as the scalar path.
    # NumPy is an optional research accelerator, not a core dependency.
    try:
        return _batched_portfolio_probability(normalized)
    except ImportError:
        return _enumerate_portfolio_probability(normalized)


def _batched_portfolio_probability(tickets: tuple[Ticket, ...]) -> Fraction:
    import numpy as np

    from lottolab.research.b649_official_any_prize_exact import all_main_draw_masks

    rule = BIG_LOTTO_RULE_CONTRACT
    if rule.main_special_overlap_allowed:
        raise K235WindowLiftError("exact special model requires non-overlapping zones")
    numbers = sorted({number for ticket in tickets for number in ticket})
    positions = {number: index for index, number in enumerate(numbers)}
    masks = [np.uint64(sum(1 << positions[number] for number in ticket)) for ticket in tickets]
    pool_size = rule.main_number_max - rule.main_number_min + 1
    draw_size = rule.main_number_count
    specials = pool_size - draw_size
    outside = pool_size - len(numbers)
    main_prizes = np.array(
        [
            resolve_big_lotto_prize_tier(hits, False) is not NoPrizeResult.NO_PRIZE
            for hits in range(draw_size + 1)
        ]
    )
    special_prizes = np.array(
        [
            hits < draw_size
            and resolve_big_lotto_prize_tier(hits, True) is not NoPrizeResult.NO_PRIZE
            for hits in range(draw_size + 1)
        ]
    )
    winning = 0
    for selected_count in range(min(draw_size, len(numbers)) + 1):
        outside_selected = draw_size - selected_count
        if outside_selected > outside:
            continue
        draws = (
            all_main_draw_masks(len(numbers), selected_count)
            if selected_count
            else np.array([0], dtype=np.uint64)
        )
        won = np.zeros(draws.size, dtype=np.bool_)
        rescue = np.zeros(draws.size, dtype=np.uint64)
        for mask in masks:
            hits = np.bitwise_count(draws & mask)
            won |= main_prizes[hits]
            rescue |= np.where(special_prizes[hits], mask, np.uint64(0))
        rescue &= ~draws
        count = int(np.count_nonzero(won)) * specials
        count += int(np.bitwise_count(rescue[~won]).sum(dtype=np.int64))
        winning += comb(outside, outside_selected) * count
    return Fraction(winning, comb(pool_size, draw_size) * specials)


@lru_cache(maxsize=8192)
def _enumerate_portfolio_probability(tickets: tuple[Ticket, ...]) -> Fraction:
    """Enumerate only draws' intersection with the at-most-30 ticket numbers."""

    rule = BIG_LOTTO_RULE_CONTRACT
    if rule.main_special_overlap_allowed:
        raise K235WindowLiftError("BIG_LOTTO exact special model requires non-overlapping zones")
    pool_size = rule.main_number_max - rule.main_number_min + 1
    draw_size = rule.main_number_count
    special_count = rule.special_number_max - rule.special_number_min + 1 - draw_size
    if special_count <= 0:
        raise K235WindowLiftError("BIG_LOTTO special-number outcome space is empty")
    union_numbers = tuple(sorted({number for ticket in tickets for number in ticket}))
    outside_count = pool_size - len(union_numbers)
    number_masks = tuple(
        sum(1 << (number - rule.main_number_min) for number in ticket) for ticket in tickets
    )
    total_winning_outcomes = 0
    for selected_count in range(min(draw_size, len(union_numbers)) + 1):
        outside_selected = draw_size - selected_count
        if outside_selected > outside_count:
            continue
        multiplicity = comb(outside_count, outside_selected)
        for selected in combinations(union_numbers, selected_count):
            selected_mask = sum(1 << (number - rule.main_number_min) for number in selected)
            eligible_special_mask = 0
            any_main_only_prize = False
            for ticket_mask in number_masks:
                main_hits = (ticket_mask & selected_mask).bit_count()
                if resolve_big_lotto_prize_tier(main_hits, False) is not NoPrizeResult.NO_PRIZE:
                    any_main_only_prize = True
                    break
                if main_hits < draw_size and (
                    resolve_big_lotto_prize_tier(main_hits, True) is not NoPrizeResult.NO_PRIZE
                ):
                    eligible_special_mask |= ticket_mask
            winning_specials = (
                special_count
                if any_main_only_prize
                else (eligible_special_mask & ~selected_mask).bit_count()
            )
            total_winning_outcomes += multiplicity * winning_specials
    denominator = comb(pool_size, draw_size) * special_count
    return Fraction(total_winning_outcomes, denominator)


def _canonical_incidence_profile(tickets: tuple[Ticket, ...]) -> tuple[int, ...]:
    ticket_count = len(tickets)
    membership: dict[int, int] = {}
    for position, ticket in enumerate(tickets):
        for number in ticket:
            membership[number] = membership.get(number, 0) | (1 << position)
    counts = [0] * (1 << ticket_count)
    for incidence_mask in membership.values():
        counts[incidence_mask] += 1

    return _canonical_profile_counts(ticket_count, tuple(counts))


@lru_cache(maxsize=8192)
def _canonical_profile_counts(ticket_count: int, counts: tuple[int, ...]) -> tuple[int, ...]:

    best: tuple[int, ...] | None = None
    for permutation in permutations(range(ticket_count)):
        transformed = [0] * (1 << ticket_count)
        for old_mask in range(1, 1 << ticket_count):
            new_mask = sum(
                1 << permutation[old_position]
                for old_position in range(ticket_count)
                if old_mask & (1 << old_position)
            )
            transformed[new_mask] = counts[old_mask]
        candidate = tuple(transformed[1:])
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best


def _has_number_overlap(tickets: tuple[Ticket, ...]) -> bool:
    return sum(len(ticket) for ticket in tickets) != len(
        {number for ticket in tickets for number in ticket}
    )


def _find_strategy_report(
    report: K235WindowLiftReport, strategy_id: str, k: int
) -> K235StrategyReport:
    for strategy_report in report.strategy_reports:
        if strategy_report.strategy_id == strategy_id and strategy_report.k == k:
            return strategy_report
    raise K235WindowLiftError(f"report has no strategy {strategy_id!r} at K={k}")


def _window_size(window: str) -> int | None:
    for name, size in WINDOWS:
        if name == window:
            return size
    raise K235WindowLiftError(f"unsupported window: {window!r}")


def _validate_outcomes(outcomes: Sequence[HistoricalDrawOutcome]) -> set[str]:
    if not outcomes:
        raise K235WindowLiftError("outcomes must contain at least one draw")
    seen: set[str] = set()
    previous_date: date | None = None
    for outcome in outcomes:
        if type(outcome) is not HistoricalDrawOutcome:
            raise K235WindowLiftError("outcomes must contain HistoricalDrawOutcome values")
        if outcome.draw_id in seen:
            raise K235WindowLiftError(f"duplicate outcome draw_id: {outcome.draw_id}")
        if previous_date is not None and outcome.draw_date < previous_date:
            raise K235WindowLiftError(
                "outcomes must be supplied in ascending historical date order"
            )
        seen.add(outcome.draw_id)
        previous_date = outcome.draw_date
    return seen


def _normalize_ticket(ticket: Sequence[int], *, label: str) -> Ticket:
    return _normalize_numbers(ticket, label=label)


def _normalize_numbers(numbers: Sequence[int], *, label: str) -> Ticket:
    try:
        values = tuple(numbers)
    except TypeError as exc:
        raise K235WindowLiftError(f"{label} must be a sequence of integers") from exc
    rule = BIG_LOTTO_RULE_CONTRACT
    if len(values) != rule.main_number_count:
        raise K235WindowLiftError(f"{label} must contain exactly {rule.main_number_count} numbers")
    if any(type(number) is not int for number in values):
        raise K235WindowLiftError(f"{label} must contain exact built-in integers")
    if len(set(values)) != len(values):
        raise K235WindowLiftError(f"{label} must not contain duplicates")
    if any(not rule.main_number_min <= number <= rule.main_number_max for number in values):
        raise K235WindowLiftError(f"{label} contains an out-of-range number")
    return tuple(sorted(values))


def _fraction_payload(value: Fraction | None) -> dict[str, int | str] | None:
    if value is None:
        return None
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_12": f"{float(value):.12f}",
        "percent_10": f"{float(value) * 100:.10f}",
    }


def _require_text(value: str, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise K235WindowLiftError(f"{label} must be a non-empty canonical string")


__all__ = [
    "K_VALUES",
    "RESEARCH_CAVEAT",
    "WINDOWS",
    "ZERO_OVERLAP_RANDOM_BASELINES",
    "HistoricalDrawOutcome",
    "K235StrategyReport",
    "K235TargetResult",
    "K235WindowLiftError",
    "K235WindowLiftReport",
    "K235WindowMetric",
    "PairedWindowComparison",
    "PredictionStatus",
    "StrategyTargetReplay",
    "TargetStatus",
    "compare_k235_strategies",
    "evaluate_k235_history",
    "evaluate_native_k235_history",
    "exact_portfolio_random_probability",
]
