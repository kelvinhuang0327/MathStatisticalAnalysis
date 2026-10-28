"""Walk-forward experiment for strictly-prior B649 regime reweighting.

The module keeps a small, predeclared set of short/middle/long window weights.
For each forecast, CUSUM and all ticket scores use only the supplied historical
prefix. A rule is fitted on an earlier training segment and then frozen for
the following evaluation segment. The fixed-weight control reuses the existing
constraint-filter score function; all controls are projected to the same
disjoint K2/K3/K5 ticket budget before scoring.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from lottolab.research.b649_k235_output_quality import evaluate_candidate_quality
from lottolab.research.conditional_state_features import LAST_SEEN_GAP_CAP
from lottolab.research.regime_changepoint_cusum import max_abs_cusum
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_constraint_filter import _constraint_weights

K_VALUES = (2, 3, 5)
WINDOWS = (50, 300, 750)
EVALUATION_WINDOWS = (50, 300, 750, 1500)
MINIMUM_HISTORY = 50
MINIMUM_TRAINING_TARGETS = 50
CUSUM_WINDOW = 300
CUSUM_THRESHOLDS = (1.5, 2.0, 2.5)
RANDOM_REPLICATES = 64
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_BLOCK_LENGTH = 10


@dataclass(frozen=True, slots=True)
class HistoricalDraw:
    """One official BIG_LOTTO draw used as a target or prior observation."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.draw_number) is not str or not self.draw_number:
            raise ValueError("draw_number must be a non-empty string")
        try:
            int(self.draw_number)
        except ValueError as exc:
            raise ValueError("draw_number must be numeric") from exc
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")
        if type(self.main_numbers) is not tuple or len(self.main_numbers) != 6:
            raise ValueError("main_numbers must contain exactly six numbers")
        if any(type(number) is not int or not 1 <= number <= 49 for number in self.main_numbers):
            raise ValueError("main_numbers must be exact integers in 1..49")
        if len(set(self.main_numbers)) != 6:
            raise ValueError("main_numbers must be unique")

    @property
    def sort_key(self) -> tuple[date, int]:
        return self.draw_date, int(self.draw_number)


@dataclass(frozen=True, slots=True)
class WindowWeightPreset:
    """A fixed mixture over the short, middle, and long signal windows."""

    preset_id: str
    short: float
    middle: float
    long: float

    @property
    def weights(self) -> tuple[float, float, float]:
        return self.short, self.middle, self.long


WEIGHT_PRESETS = (
    WindowWeightPreset("SHORT_HEAVY", 0.65, 0.25, 0.10),
    WindowWeightPreset("BALANCED", 0.25, 0.50, 0.25),
    WindowWeightPreset("LONG_HEAVY", 0.10, 0.25, 0.65),
)
_PRESET_BY_ID = {preset.preset_id: preset for preset in WEIGHT_PRESETS}


@dataclass(frozen=True, slots=True)
class RegimeRule:
    """A frozen two-state rule selected only from the training segment."""

    threshold: float
    stable_weight_id: str
    changed_weight_id: str

    @property
    def rule_id(self) -> str:
        return (
            f"CUSUM_GE_{self.threshold:.1f}_"
            f"STABLE_{self.stable_weight_id}_CHANGED_{self.changed_weight_id}"
        )


@dataclass(frozen=True, slots=True)
class RuleFit:
    rule: RegimeRule
    training_mean_unique_hits: float
    training_target_count: int


@dataclass(frozen=True, slots=True)
class ForecastContext:
    """A target-free prediction context made from one strictly-prior prefix."""

    feature_cutoff_draw_number: str
    history_draw_count: int
    history_fingerprint: str
    cusum_statistic: float
    weighted_tickets_by_k: Mapping[int, Mapping[str, tuple[tuple[int, ...], ...]]]
    fixed_weight_tickets_by_k: Mapping[int, tuple[tuple[int, ...], ...]]


def validate_draw_history(draws: Sequence[HistoricalDraw]) -> None:
    if not draws:
        raise ValueError("draw history must be non-empty")
    seen: set[str] = set()
    previous_key: tuple[date, int] | None = None
    for draw in draws:
        if not isinstance(draw, HistoricalDraw):
            raise ValueError("draw history must contain HistoricalDraw values")
        if draw.draw_number in seen:
            raise ValueError("draw history identities must be unique")
        if previous_key is not None and draw.sort_key <= previous_key:
            raise ValueError("draw history must be strictly chronological")
        seen.add(draw.draw_number)
        previous_key = draw.sort_key


def history_fingerprint(history: Sequence[HistoricalDraw]) -> str:
    """Hash a JSON-compatible round-trip of the exact historical prefix."""

    payload: object = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
        }
        for draw in history
    ]
    normalized = json.loads(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _gap_score(gap_from_latest: int) -> float:
    gap = min(gap_from_latest, LAST_SEEN_GAP_CAP)
    if gap < 8:
        return gap / 8.0 * 0.5
    if gap <= 15:
        return 1.0
    return max(0.3, 0.9 ** ((gap - 15) / 5.0))


def _window_components(history: Sequence[HistoricalDraw], horizon: int) -> dict[int, float]:
    selected = history[-horizon:]
    if not selected:
        raise ValueError("window components require prior draws")
    counts = {number: 0 for number in range(1, 50)}
    last_seen_from_latest: dict[int, int | None] = {number: None for number in range(1, 50)}
    for age, draw in enumerate(reversed(selected)):
        for number in draw.main_numbers:
            counts[number] += 1
            if last_seen_from_latest[number] is None:
                last_seen_from_latest[number] = age
    maximum_frequency = max(counts.values()) or 1
    return {
        number: 0.5 * (counts[number] / maximum_frequency)
        + 0.5
        * _gap_score(
            LAST_SEEN_GAP_CAP
            if last_seen_from_latest[number] is None
            else last_seen_from_latest[number]
        )
        for number in range(1, 50)
    }


def _weighted_scores(history: Sequence[HistoricalDraw]) -> dict[str, dict[int, float]]:
    components = tuple(_window_components(history, window) for window in WINDOWS)
    return {
        preset.preset_id: {
            number: math.fsum(
                weight * component[number]
                for weight, component in zip(preset.weights, components, strict=True)
            )
            for number in range(1, 50)
        }
        for preset in WEIGHT_PRESETS
    }


def _portfolio_from_scores(
    scores: Mapping[int, float], ticket_count: int
) -> tuple[tuple[int, ...], ...]:
    if ticket_count not in K_VALUES:
        raise ValueError("ticket_count must be one of K2, K3, or K5")
    ordered = sorted(scores, key=lambda number: (-scores[number], number))
    selected = ordered[: 6 * ticket_count]
    if len(selected) != 6 * ticket_count:
        raise ValueError("not enough numbers to emit the requested ticket portfolio")
    tickets = tuple(
        tuple(sorted(selected[offset : offset + 6])) for offset in range(0, len(selected), 6)
    )
    quality = evaluate_candidate_quality(tickets, ticket_count)
    if not quality.is_valid:
        raise RuntimeError(f"candidate emitted an illegal K{ticket_count} portfolio")
    return tickets


def predict_weighted_tickets(
    history: Sequence[HistoricalDraw], ticket_count: int, preset_id: str
) -> tuple[tuple[int, ...], ...]:
    """Emit deterministic disjoint tickets from one named window-weight preset."""

    if not history:
        raise ValueError("history must contain at least one strictly-prior draw")
    if preset_id not in _PRESET_BY_ID:
        raise ValueError(f"unknown weight preset: {preset_id}")
    return _portfolio_from_scores(_weighted_scores(history)[preset_id], ticket_count)


def predict_fixed_weight_tickets(
    history: Sequence[HistoricalDraw], ticket_count: int
) -> tuple[tuple[int, ...], ...]:
    """Apply the existing fixed 50/50 frequency-gap weights at K2/K3/K5 cost."""

    if not history:
        raise ValueError("history must contain at least one strictly-prior draw")
    recent_first = tuple(
        CausalDrawRow(
            draw=draw.draw_number,
            date=draw.draw_date.isoformat(),
            numbers=draw.main_numbers,
        )
        for draw in reversed(history)
    )
    weights = _constraint_weights(recent_first)
    return _portfolio_from_scores(weights, ticket_count)


def _cusum_statistic(history: Sequence[HistoricalDraw]) -> float:
    if len(history) < 3:
        return 0.0
    selected = history[-CUSUM_WINDOW:]
    null_mean = 6.0 / 49.0
    scale = math.sqrt(len(selected) * null_mean * (1.0 - null_mean))
    maximum = 0.0
    for number in range(1, 50):
        values = tuple(1.0 if number in draw.main_numbers else 0.0 for draw in selected)
        result = max_abs_cusum(
            values,
            null_mean,
            trim_fraction_numerator=10,
            trim_fraction_denominator=100,
        )
        maximum = max(maximum, result.statistic / scale)
    return maximum


def forecast_from_history(history: Sequence[HistoricalDraw]) -> ForecastContext:
    """Create signals and tickets without receiving or reading a target draw."""

    validate_draw_history(history)
    score_sets = _weighted_scores(history)
    weighted: dict[int, dict[str, tuple[tuple[int, ...], ...]]] = {
        ticket_count: {
            preset_id: _portfolio_from_scores(scores, ticket_count)
            for preset_id, scores in score_sets.items()
        }
        for ticket_count in K_VALUES
    }
    fixed = {
        ticket_count: predict_fixed_weight_tickets(history, ticket_count)
        for ticket_count in K_VALUES
    }
    return ForecastContext(
        feature_cutoff_draw_number=history[-1].draw_number,
        history_draw_count=len(history),
        history_fingerprint=history_fingerprint(history),
        cusum_statistic=_cusum_statistic(history),
        weighted_tickets_by_k=weighted,
        fixed_weight_tickets_by_k=fixed,
    )


def _regime(rule: RegimeRule, statistic: float) -> tuple[str, str]:
    if statistic >= rule.threshold:
        return "CHANGED", rule.changed_weight_id
    return "STABLE", rule.stable_weight_id


def _candidate_rules() -> tuple[RegimeRule, ...]:
    return tuple(
        RegimeRule(threshold, stable_id, changed_id)
        for threshold in CUSUM_THRESHOLDS
        for stable_id in _PRESET_BY_ID
        for changed_id in _PRESET_BY_ID
    )


def _total_hits(tickets: Sequence[Sequence[int]], actual: Sequence[int]) -> int:
    actual_set = set(actual)
    return sum(len(set(ticket) & actual_set) for ticket in tickets)


def fit_switch_rule(
    draws: Sequence[HistoricalDraw],
    contexts: Mapping[int, ForecastContext],
    training_target_indices: Sequence[int],
    ticket_count: int,
) -> RuleFit:
    """Choose one finite switch rule using labels from the earlier train slice."""

    if ticket_count not in K_VALUES:
        raise ValueError("ticket_count must be one of K2, K3, or K5")
    if len(training_target_indices) < MINIMUM_TRAINING_TARGETS:
        raise ValueError("training segment must contain at least 50 targets")
    if any(index < MINIMUM_HISTORY or index >= len(draws) for index in training_target_indices):
        raise ValueError("training target indices are outside the prepared history")

    best: RuleFit | None = None
    for rule in _candidate_rules():
        hit_values: list[int] = []
        for index in training_target_indices:
            context = contexts[index]
            _, weight_id = _regime(rule, context.cusum_statistic)
            tickets = context.weighted_tickets_by_k[ticket_count][weight_id]
            hit_values.append(_total_hits(tickets, draws[index].main_numbers))
        score = math.fsum(hit_values) / len(hit_values)
        candidate = RuleFit(rule, score, len(hit_values))
        if best is None or candidate.training_mean_unique_hits > best.training_mean_unique_hits:
            best = candidate
    if best is None:
        raise RuntimeError("no finite switch rule was evaluated")
    return best


def random_tickets(
    history: Sequence[HistoricalDraw], ticket_count: int, replicate: int = 0
) -> tuple[tuple[int, ...], ...]:
    """Emit a reproducible random disjoint portfolio seeded by the prior prefix."""

    if not history:
        raise ValueError("history must contain at least one strictly-prior draw")
    return _random_tickets_from_fingerprint(history_fingerprint(history), ticket_count, replicate)


def _random_tickets_from_fingerprint(
    fingerprint: str, ticket_count: int, replicate: int
) -> tuple[tuple[int, ...], ...]:
    if ticket_count not in K_VALUES:
        raise ValueError("ticket_count must be one of K2, K3, or K5")
    if type(replicate) is not int or replicate < 0:
        raise ValueError("replicate must be a non-negative integer")
    seed_material = f"{fingerprint}|K={ticket_count}|R={replicate}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16)
    chosen = random.Random(seed).sample(range(1, 50), 6 * ticket_count)
    tickets = tuple(
        tuple(sorted(chosen[offset : offset + 6])) for offset in range(0, len(chosen), 6)
    )
    quality = evaluate_candidate_quality(tickets, ticket_count)
    if not quality.is_valid:
        raise RuntimeError(f"random baseline emitted an illegal K{ticket_count} portfolio")
    return tickets


def _block_bootstrap_interval(
    differences: Sequence[float], seed_material: str
) -> tuple[float, float]:
    if not differences:
        raise ValueError("bootstrap requires at least one difference")
    values = tuple(differences)
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    sample_count = len(values)
    blocks_per_sample = math.ceil(sample_count / BOOTSTRAP_BLOCK_LENGTH)
    means: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample: list[float] = []
        for _block in range(blocks_per_sample):
            start = rng.randrange(sample_count)
            sample.extend(
                values[(start + offset) % sample_count] for offset in range(BOOTSTRAP_BLOCK_LENGTH)
            )
        means.append(math.fsum(sample[:sample_count]) / sample_count)
    means.sort()
    low_index = max(0, math.floor(0.005 * (BOOTSTRAP_REPLICATES - 1)))
    high_index = min(
        BOOTSTRAP_REPLICATES - 1,
        math.ceil(0.995 * (BOOTSTRAP_REPLICATES - 1)),
    )
    return means[low_index], means[high_index]


def _mean(values: Sequence[float | int]) -> float:
    return math.fsum(values) / len(values) if values else 0.0


def _percentile_count(values: Sequence[int], minimum: int) -> float:
    return sum(value >= minimum for value in values) / len(values) if values else 0.0


def run_walk_forward_backtest(
    draws: Sequence[HistoricalDraw],
    *,
    evaluation_windows: Sequence[int] = EVALUATION_WINDOWS,
    random_replicates: int = RANDOM_REPLICATES,
) -> dict[str, object]:
    """Fit before each tail window, then score dynamic/fixed/random at equal K."""

    validate_draw_history(draws)
    if type(random_replicates) is not int or random_replicates <= 0:
        raise ValueError("random_replicates must be positive")
    contexts = {
        index: forecast_from_history(draws[:index]) for index in range(MINIMUM_HISTORY, len(draws))
    }
    rows: list[dict[str, object]] = []
    target_records: list[dict[str, object]] = []
    unavailable_windows: list[dict[str, object]] = []
    usable_windows: list[int] = []
    random_cache: dict[tuple[int, int], tuple[float, tuple[tuple[int, ...], ...]]] = {}
    maximum_usable_window = max(evaluation_windows, default=0)
    random_start = max(MINIMUM_HISTORY, len(draws) - maximum_usable_window)

    for index in range(random_start, len(draws)):
        context = contexts[index]
        target = draws[index]
        for ticket_count in K_VALUES:
            hits: list[int] = []
            first_portfolio: tuple[tuple[int, ...], ...] | None = None
            for replicate in range(random_replicates):
                portfolio = _random_tickets_from_fingerprint(
                    context.history_fingerprint, ticket_count, replicate
                )
                if first_portfolio is None:
                    first_portfolio = portfolio
                hits.append(_total_hits(portfolio, target.main_numbers))
            random_cache[index, ticket_count] = (
                _mean(hits),
                first_portfolio or (),
            )

    for window_size in evaluation_windows:
        if type(window_size) is not int or window_size <= 0:
            raise ValueError("evaluation windows must be positive integers")
        if len(draws) < window_size:
            unavailable_windows.append(
                {"window_size": window_size, "reason": "INSUFFICIENT_EVALUATION_DRAWS"}
            )
            continue
        evaluation_start = len(draws) - window_size
        training_indices = tuple(range(MINIMUM_HISTORY, evaluation_start))
        if len(training_indices) < MINIMUM_TRAINING_TARGETS:
            unavailable_windows.append(
                {"window_size": window_size, "reason": "INSUFFICIENT_PRIOR_TRAINING_TARGETS"}
            )
            continue
        usable_windows.append(window_size)

        for ticket_count in K_VALUES:
            fit = fit_switch_rule(draws, contexts, training_indices, ticket_count)
            evaluated: list[dict[str, object]] = []
            previous_state: str | None = None
            previous_weight: str | None = None
            regime_switch_count = 0
            weight_switch_count = 0
            state_counts = {"STABLE": 0, "CHANGED": 0}
            weight_counts = {preset.preset_id: 0 for preset in WEIGHT_PRESETS}

            for index in range(evaluation_start, len(draws)):
                context = contexts[index]
                target = draws[index]
                state, weight_id = _regime(fit.rule, context.cusum_statistic)
                if previous_state is not None and state != previous_state:
                    regime_switch_count += 1
                if previous_weight is not None and weight_id != previous_weight:
                    weight_switch_count += 1
                previous_state = state
                previous_weight = weight_id
                state_counts[state] += 1
                weight_counts[weight_id] += 1

                dynamic_tickets = context.weighted_tickets_by_k[ticket_count][weight_id]
                fixed_tickets = context.fixed_weight_tickets_by_k[ticket_count]
                random_mean, random_sample = random_cache[index, ticket_count]
                dynamic_hits = _total_hits(dynamic_tickets, target.main_numbers)
                fixed_hits = _total_hits(fixed_tickets, target.main_numbers)
                random_sample_hits = _total_hits(random_sample, target.main_numbers)
                dynamic_ticket_hits = [
                    len(set(ticket) & set(target.main_numbers)) for ticket in dynamic_tickets
                ]
                fixed_ticket_hits = [
                    len(set(ticket) & set(target.main_numbers)) for ticket in fixed_tickets
                ]
                random_ticket_hits = [
                    len(set(ticket) & set(target.main_numbers)) for ticket in random_sample
                ]
                record = {
                    "window_size": window_size,
                    "k": ticket_count,
                    "target_draw_number": target.draw_number,
                    "feature_cutoff_draw_number": context.feature_cutoff_draw_number,
                    "history_fingerprint": context.history_fingerprint,
                    "cusum_statistic": context.cusum_statistic,
                    "cusum_threshold": fit.rule.threshold,
                    "selected_regime": state,
                    "selected_weight_preset": weight_id,
                    "selection_rule_id": fit.rule.rule_id,
                    "training_last_target_draw_number": draws[evaluation_start - 1].draw_number,
                    "training_target_count": fit.training_target_count,
                    "actual_main_numbers": list(target.main_numbers),
                    "dynamic_tickets": [list(ticket) for ticket in dynamic_tickets],
                    "fixed_weight_tickets": [list(ticket) for ticket in fixed_tickets],
                    "random_sample_tickets": [list(ticket) for ticket in random_sample],
                    "random_replicate_count": random_replicates,
                    "dynamic_unique_hits": dynamic_hits,
                    "fixed_weight_unique_hits": fixed_hits,
                    "random_sample_unique_hits": random_sample_hits,
                    "random_mean_unique_hits": random_mean,
                    "dynamic_best_ticket_hits": max(dynamic_ticket_hits),
                    "fixed_weight_best_ticket_hits": max(fixed_ticket_hits),
                    "random_sample_best_ticket_hits": max(random_ticket_hits),
                    "dynamic_three_plus_tickets": sum(hit >= 3 for hit in dynamic_ticket_hits),
                    "fixed_weight_three_plus_tickets": sum(hit >= 3 for hit in fixed_ticket_hits),
                    "random_sample_three_plus_tickets": sum(hit >= 3 for hit in random_ticket_hits),
                }
                evaluated.append(record)
                target_records.append(record)

            dynamic_hits_values = [int(item["dynamic_unique_hits"]) for item in evaluated]
            fixed_hits_values = [int(item["fixed_weight_unique_hits"]) for item in evaluated]
            random_mean_values = [float(item["random_mean_unique_hits"]) for item in evaluated]
            dynamic_fixed_diffs = [
                dynamic - fixed
                for dynamic, fixed in zip(dynamic_hits_values, fixed_hits_values, strict=True)
            ]
            dynamic_random_diffs = [
                dynamic - random
                for dynamic, random in zip(dynamic_hits_values, random_mean_values, strict=True)
            ]
            fixed_interval = _block_bootstrap_interval(
                dynamic_fixed_diffs,
                f"{window_size}|{ticket_count}|DYNAMIC_MINUS_FIXED",
            )
            random_interval = _block_bootstrap_interval(
                dynamic_random_diffs,
                f"{window_size}|{ticket_count}|DYNAMIC_MINUS_RANDOM",
            )
            credible = fixed_interval[0] > 0.0 and random_interval[0] > 0.0
            rows.append(
                {
                    "window_size": window_size,
                    "k": ticket_count,
                    "training_first_target_draw_number": draws[training_indices[0]].draw_number,
                    "training_last_target_draw_number": draws[training_indices[-1]].draw_number,
                    "training_target_count": len(training_indices),
                    "evaluation_first_target_draw_number": draws[evaluation_start].draw_number,
                    "evaluation_last_target_draw_number": draws[-1].draw_number,
                    "evaluation_target_count": window_size,
                    "selection_rule_id": fit.rule.rule_id,
                    "cusum_threshold": fit.rule.threshold,
                    "stable_weight_preset": fit.rule.stable_weight_id,
                    "changed_weight_preset": fit.rule.changed_weight_id,
                    "training_mean_unique_hits": fit.training_mean_unique_hits,
                    "regime_switch_count": regime_switch_count,
                    "weight_switch_count": weight_switch_count,
                    "stable_target_count": state_counts["STABLE"],
                    "changed_target_count": state_counts["CHANGED"],
                    "weight_preset_target_counts": weight_counts,
                    "dynamic_mean_unique_hits": _mean(dynamic_hits_values),
                    "fixed_weight_mean_unique_hits": _mean(fixed_hits_values),
                    "random_mean_unique_hits": _mean(random_mean_values),
                    "dynamic_delta_vs_fixed": _mean(dynamic_fixed_diffs),
                    "dynamic_delta_vs_random": _mean(dynamic_random_diffs),
                    "dynamic_fixed_99pct_block_ci": list(fixed_interval),
                    "dynamic_random_99pct_block_ci": list(random_interval),
                    "dynamic_best_ticket_3plus_rate": _percentile_count(
                        [int(item["dynamic_best_ticket_hits"]) for item in evaluated], 3
                    ),
                    "fixed_weight_best_ticket_3plus_rate": _percentile_count(
                        [int(item["fixed_weight_best_ticket_hits"]) for item in evaluated], 3
                    ),
                    "random_sample_best_ticket_3plus_rate": _percentile_count(
                        [int(item["random_sample_best_ticket_hits"]) for item in evaluated], 3
                    ),
                    "status": "CREDIBLE_GAIN" if credible else "NO_GAIN",
                }
            )

    if not usable_windows:
        overall_status = "NO_GAIN"
    else:
        longest_window = max(usable_windows)
        longest_rows = [row for row in rows if row["window_size"] == longest_window]
        all_k_pass = len(longest_rows) == len(K_VALUES) and all(
            cast_ci(row, "dynamic_fixed_99pct_block_ci") > 0.0
            and cast_ci(row, "dynamic_random_99pct_block_ci") > 0.0
            for row in longest_rows
        )
        all_window_points_nonnegative = all(
            float(row["dynamic_delta_vs_fixed"]) >= 0.0
            and float(row["dynamic_delta_vs_random"]) >= 0.0
            for row in rows
        )
        overall_status = (
            "CREDIBLE_GAIN" if all_k_pass and all_window_points_nonnegative else "NO_GAIN"
        )

    return {
        "status": overall_status,
        "draw_count": len(draws),
        "first_draw_number": draws[0].draw_number,
        "last_draw_number": draws[-1].draw_number,
        "minimum_history": MINIMUM_HISTORY,
        "minimum_training_targets": MINIMUM_TRAINING_TARGETS,
        "signal_windows": list(WINDOWS),
        "cusum_window": CUSUM_WINDOW,
        "cusum_threshold_candidates": list(CUSUM_THRESHOLDS),
        "weight_presets": [
            {
                "preset_id": preset.preset_id,
                "short": preset.short,
                "middle": preset.middle,
                "long": preset.long,
            }
            for preset in WEIGHT_PRESETS
        ],
        "fixed_weight_control": "EXISTING_CONSTRAINT_FILTER_50_50_FREQUENCY_GAP_TOP_6K",
        "random_replicates_per_target": random_replicates,
        "random_seed_scheme": "SHA256(strictly-prior-history-fingerprint|K|replicate)",
        "bootstrap": {
            "method": "CIRCULAR_PAIRED_BLOCK_BOOTSTRAP",
            "replicates": BOOTSTRAP_REPLICATES,
            "block_length": BOOTSTRAP_BLOCK_LENGTH,
            "interval": "99%",
        },
        "evaluation_windows": usable_windows,
        "unavailable_windows": unavailable_windows,
        "rows": rows,
        "target_records": target_records,
        "conclusion": overall_status,
    }


def cast_ci(row: Mapping[str, object], key: str) -> float:
    interval = row[key]
    if not isinstance(interval, list) or not interval:
        raise ValueError(f"{key} must be a non-empty list")
    return float(interval[0])


__all__ = [
    "BOOTSTRAP_BLOCK_LENGTH",
    "BOOTSTRAP_REPLICATES",
    "CUSUM_THRESHOLDS",
    "EVALUATION_WINDOWS",
    "K_VALUES",
    "MINIMUM_HISTORY",
    "MINIMUM_TRAINING_TARGETS",
    "WEIGHT_PRESETS",
    "WINDOWS",
    "ForecastContext",
    "HistoricalDraw",
    "RegimeRule",
    "RuleFit",
    "fit_switch_rule",
    "forecast_from_history",
    "history_fingerprint",
    "predict_fixed_weight_tickets",
    "predict_weighted_tickets",
    "random_tickets",
    "run_walk_forward_backtest",
    "validate_draw_history",
]
