"""Selection-bias calibration for same-K historical replay candidates.

The input rows follow the historical replay CLI records-jsonl shape: one row
per target, strategy, and ticket. Complete ticket rows are aggregated to one
binary target outcome (at least one winning ticket among K). The caller must
provide the exact fair-null probability for that same K and outcome; this
module does not infer prize rules or manufacture missing replay evidence.

An input JSON document has this shape::

    {
      "rows": [{"target_draw_number": "...", "strategy_id": "...",
                "native_ticket_count": 2, "ticket_position": 1,
                "replay_status": "COMPLETE", "is_winner": false}, ...],
      "target_partitions": {"...": "EXPLORATION",
                            "...": "UNSELECTED_HISTORICAL"},
      "fair_success_probability_by_k": {
        "2": {"numerator": 1, "denominator": 100}
      },
      "independent_holdout_target_ids": [],
      "previously_reused_target_ids": [],
      "permutation_seed": 123,
      "permutation_resamples": 9999
    }

The candidate-label permutation conditions on the observed number of
successful candidates for each target and K. It tests whether the observed
maximum is unusual if same-K candidate identities are exchangeable; it is not
a permutation of lottery draws or a substitute for the specified fair-null
probability. Exact binomial tests assume independent target outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k235_window_lift_report_r1 import (
    K235WindowMetric,
    PairedWindowComparison,
)
from lottolab.research.exact_statistics import (
    binomial_two_sided_exact_p_value,
    binomial_upper_tail,
    holm_bonferroni_adjusted,
)

_SCHEMA_VERSION = "b649-k235-selection-bias-calibration-r1"
_EXPLORATION = "EXPLORATION"
_UNSELECTED_HISTORICAL = "UNSELECTED_HISTORICAL"
_PARTITIONS = frozenset({_EXPLORATION, _UNSELECTED_HISTORICAL})
_PRIOR_R1_JUDGE_STATUS = "BLOCKED_UNVERIFIABLE"
_REUSED_436_TARGET_COUNT = 436
_DEFAULT_ALPHA = 0.05
_DEFAULT_SEED = 0
_DEFAULT_RESAMPLES = 9999


@dataclass(frozen=True, slots=True)
class ReplaySuccess:
    """One target-level strategy outcome after aggregating K ticket rows."""

    target_id: str
    strategy_id: str
    k: int
    success: bool
    partition: str
    independent_holdout_asserted: bool = False

    def __post_init__(self) -> None:
        if type(self.target_id) is not str or not self.target_id.strip():
            raise ValueError("target_id must be a non-empty string")
        if type(self.strategy_id) is not str or not self.strategy_id.strip():
            raise ValueError("strategy_id must be a non-empty string")
        if type(self.k) is not int or self.k <= 0:
            raise ValueError("k must be a positive exact integer")
        if type(self.success) is not bool:
            raise ValueError("success must be a boolean")
        if type(self.partition) is not str or self.partition not in _PARTITIONS:
            raise ValueError(f"partition must be one of {sorted(_PARTITIONS)}")
        if type(self.independent_holdout_asserted) is not bool:
            raise ValueError("independent_holdout_asserted must be a boolean")
        if self.partition == _EXPLORATION and self.independent_holdout_asserted:
            raise ValueError("exploration targets cannot be asserted as holdout")


def replay_successes_from_rows(
    replay_rows: Sequence[Mapping[str, object]],
    *,
    target_partitions: Mapping[str, str],
    independent_holdout_target_ids: Iterable[str] = (),
) -> tuple[ReplaySuccess, ...]:
    """Aggregate complete records-jsonl ticket rows into target successes.

    A target/strategy group must contain every ticket position from 1 through
    native_ticket_count. Any incomplete, unavailable, or non-boolean outcome
    fails closed so an incomplete replay cannot silently shrink N.
    """

    if not replay_rows:
        raise ValueError("replay rows contain no per-target evidence")
    if not isinstance(cast(object, target_partitions), Mapping):
        raise ValueError("target_partitions must be a mapping")

    if isinstance(independent_holdout_target_ids, (str, bytes)):
        raise ValueError("independent holdout target ids must be an iterable of ids")
    independent_ids = frozenset(independent_holdout_target_ids)
    if any(type(item) is not str or not item for item in independent_ids):
        raise ValueError("independent holdout target ids must be non-empty strings")

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(replay_rows):
        if not isinstance(cast(object, row), Mapping):
            raise ValueError(f"replay row {index} must be an object")
        target_id = _required_string(row, "target_draw_number", index)
        strategy_id = _required_string(row, "strategy_id", index)
        k = _required_int(row, "native_ticket_count", index, minimum=1)
        position = _required_int(row, "ticket_position", index, minimum=1)
        status = row.get("replay_status")
        if status != "COMPLETE":
            raise ValueError(f"replay row {index} is not COMPLETE; missing evidence is not scored")
        success = row.get("is_winner")
        if type(success) is not bool:
            raise ValueError(f"replay row {index} is missing a boolean is_winner")

        key = target_id, strategy_id
        group = groups.get(key)
        if group is None:
            if target_id not in target_partitions:
                raise ValueError(f"target partition is missing for {target_id}")
            partition = target_partitions[target_id]
            if partition not in _PARTITIONS:
                raise ValueError(f"invalid partition for target {target_id}: {partition!r}")
            group = cast(
                dict[str, Any],
                {"k": k, "positions": set(), "successes": [], "partition": partition},
            )
            groups[key] = group
        elif group["k"] != k:
            raise ValueError(f"native_ticket_count changes within {target_id}:{strategy_id}")

        if position > k:
            raise ValueError(f"ticket_position exceeds K for {target_id}:{strategy_id}")
        if position in group["positions"]:
            raise ValueError(f"duplicate ticket position for {target_id}:{strategy_id}")
        group["positions"].add(position)
        group["successes"].append(success)

    observed_target_ids = {target for target, _ in groups}
    if set(target_partitions) != observed_target_ids:
        unknown = sorted(set(target_partitions) - observed_target_ids)
        if unknown:
            raise ValueError(f"target partitions have no replay rows: {unknown[:3]}")
    if not independent_ids <= observed_target_ids:
        raise ValueError("independent holdout target ids must appear in replay rows")
    for target_id in independent_ids:
        partition = target_partitions[target_id]
        if partition != _UNSELECTED_HISTORICAL:
            raise ValueError("only unselected historical targets can be holdout asserted")

    output: list[ReplaySuccess] = []
    for (target_id, strategy_id), group in sorted(groups.items()):
        expected_positions = set(range(1, group["k"] + 1))
        if group["positions"] != expected_positions:
            raise ValueError(
                f"incomplete ticket positions for {target_id}:{strategy_id}; "
                "all K rows are required"
            )
        partition = str(group["partition"])
        output.append(
            ReplaySuccess(
                target_id=target_id,
                strategy_id=strategy_id,
                k=int(group["k"]),
                success=any(group["successes"]),
                partition=partition,
                independent_holdout_asserted=target_id in independent_ids,
            )
        )
    return tuple(output)


def calibrate_selection_bias(
    records: Sequence[ReplaySuccess],
    *,
    fair_success_probability_by_k: Mapping[int | str, Fraction | Mapping[str, object]],
    alpha: float = _DEFAULT_ALPHA,
    permutation_seed: int = _DEFAULT_SEED,
    permutation_resamples: int = _DEFAULT_RESAMPLES,
    previously_reused_target_ids: Iterable[str] = (),
) -> dict[str, object]:
    """Compare complete same-K replay results to fair chance and each other."""

    if not records:
        raise ValueError("records contain no per-period replay evidence")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    if type(permutation_seed) is not int or permutation_seed < 0:
        raise ValueError("permutation_seed must be a non-negative exact integer")
    if type(permutation_resamples) is not int or permutation_resamples <= 0:
        raise ValueError("permutation_resamples must be a positive exact integer")

    p0_by_k = _normalize_probabilities(fair_success_probability_by_k)
    reused_ids = frozenset(previously_reused_target_ids)
    if any(type(item) is not str or not item for item in reused_ids):
        raise ValueError("previously reused target ids must be non-empty strings")
    grouped, target_partitions, target_independence = _index_records(records)
    observed_ks = {k for k, _partition in grouped}
    if set(p0_by_k) != observed_ks:
        missing = sorted(observed_ks - set(p0_by_k))
        extra = sorted(set(p0_by_k) - observed_ks)
        raise ValueError(
            f"fair probabilities must match observed K values; missing={missing}, extra={extra}"
        )

    selected_by_k = _select_from_exploration(grouped)
    exploration = _summarize_partition(
        _EXPLORATION, grouped, p0_by_k, alpha=alpha, independence_status="NOT_APPLICABLE"
    )
    historical_target_ids = {
        target_id
        for target_id, partition in target_partitions.items()
        if partition == _UNSELECTED_HISTORICAL
    }
    independence_status, reused_overlap_count = _historical_independence_status(
        historical_target_ids,
        target_independence,
        reused_ids,
    )
    historical = _summarize_partition(
        _UNSELECTED_HISTORICAL,
        grouped,
        p0_by_k,
        alpha=alpha,
        independence_status=independence_status,
    )
    historical["independence_status"] = independence_status
    historical["previously_reused_target_overlap_count"] = reused_overlap_count
    historical["independent_holdout_claim_is_verified"] = False

    selected_holdout = _selected_holdout_summary(
        grouped, p0_by_k, selected_by_k, historical, alpha=alpha
    )
    permutation = _selection_permutation(
        grouped,
        p0_by_k,
        alpha=alpha,
        seed=permutation_seed,
        resamples=permutation_resamples,
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis_status": "COMPLETE",
        "success_definition": "AT_LEAST_ONE_WINNING_TICKET_AMONG_K_PER_TARGET",
        "prior_r1_judge_status": _PRIOR_R1_JUDGE_STATUS,
        "prior_r1_result_relabelled_verified": False,
        "alpha": alpha,
        "candidate_count": exploration["candidate_count"],
        "K_values": sorted(observed_ks),
        "target_period_count": len(target_partitions),
        "selected_strategy_by_k_from_exploration": {
            str(k): strategy_id for k, strategy_id in sorted(selected_by_k.items())
        },
        "exploration": exploration,
        "unselected_historical": historical,
        "selected_candidate_holdout_check": selected_holdout,
        "exploration_null_permutation": permutation,
        "pairwise_method": "EXACT_TWO_SIDED_MCNEMAR_WITH_HOLM_CORRECTION",
        "research_limitations": _limitations(),
    }


def analyze_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Load the existing replay JSON rows plus explicit split/null metadata."""

    if not isinstance(cast(object, payload), Mapping):
        raise ValueError("input document must be a JSON object")
    rows = payload.get("rows")
    partitions = payload.get("target_partitions")
    probabilities = payload.get("fair_success_probability_by_k")
    if not isinstance(rows, list):
        raise ValueError("input rows must be a JSON array of replay records-jsonl rows")
    if not isinstance(partitions, Mapping):
        raise ValueError("target_partitions must be a JSON object")
    if not isinstance(probabilities, Mapping):
        raise ValueError("fair_success_probability_by_k must be a JSON object")
    normalized_partitions: dict[str, str] = {}
    for key, value in cast(Mapping[object, object], partitions).items():
        if type(key) is not str or type(value) is not str:
            raise ValueError("target_partitions keys and values must be strings")
        normalized_partitions[key] = value
    independent_ids = _string_array(
        payload.get("independent_holdout_target_ids", []), "independent_holdout_target_ids"
    )
    reused_ids = _string_array(
        payload.get("previously_reused_target_ids", []), "previously_reused_target_ids"
    )
    records = replay_successes_from_rows(
        cast(list[Mapping[str, object]], rows),
        target_partitions=normalized_partitions,
        independent_holdout_target_ids=independent_ids,
    )
    return calibrate_selection_bias(
        records,
        fair_success_probability_by_k=cast(
            Mapping[int | str, Fraction | Mapping[str, object]], probabilities
        ),
        alpha=_number(payload.get("alpha", _DEFAULT_ALPHA), "alpha"),
        permutation_seed=_exact_int(
            payload.get("permutation_seed", _DEFAULT_SEED), "permutation_seed", minimum=0
        ),
        permutation_resamples=_exact_int(
            payload.get("permutation_resamples", _DEFAULT_RESAMPLES),
            "permutation_resamples",
            minimum=1,
        ),
        previously_reused_target_ids=reused_ids,
    )


def calibrate_historical_windows(
    metrics: Sequence[K235WindowMetric],
    pairs: Sequence[PairedWindowComparison],
    *,
    alpha: float = _DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Correct D's portfolio-specific tests without substituting a same-K p0.

    Constant-probability rows reuse K's exact binomial test. Heterogeneous
    rows retain D's Poisson-binomial calculation. Every supplied strategy and
    window belongs to the family, including unavailable hypotheses (p=1 for
    correction only). This is reused exploratory history, never a holdout.
    """
    if not metrics or not 0 < alpha < 1:
        raise ValueError("non-empty metrics and alpha in (0, 1) are required")
    keys = [(row.strategy_id, row.k, row.window) for row in metrics]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate strategy/K/window hypothesis")
    raw_values: list[float | None] = []
    for row in metrics:
        statistical = row.statistical_result
        if statistical is None:
            raw_values.append(None)
            continue
        raw_p = statistical.upper_tail_p_value
        if statistical.method == "EXACT_BINOMIAL_TAILS_FLOAT64":
            assert row.random_baseline_probability is not None
            raw_p = binomial_upper_tail(
                row.denominator,
                row.official_any_prize_success_count,
                float(row.random_baseline_probability),
            )
            if not math.isclose(raw_p, statistical.upper_tail_p_value, abs_tol=1e-12):
                raise ValueError("D/K constant-probability test mismatch")
        if not math.isfinite(raw_p) or not 0 <= raw_p <= 1:
            raise ValueError("invalid portfolio p-value")
        raw_values.append(raw_p)
    adjusted = holm_bonferroni_adjusted([p if p is not None else 1.0 for p in raw_values])
    results: list[dict[str, Any]] = []
    for row, raw_p, corrected in zip(metrics, raw_values, adjusted, strict=True):
        gain = row.relative_random_gain
        evidence = (
            "MISSING"
            if raw_p is None
            else "NO_GAIN"
            if gain is None or gain <= 0
            else "EXPLORATORY_SIGNAL_ONLY"
            if corrected <= alpha
            else "UNCERTAIN"
        )
        results.append(
            {
                "strategy_id": row.strategy_id,
                "K": row.k,
                "window": row.window,
                "N": row.denominator,
                "successful_count": row.official_any_prize_success_count,
                "method": row.statistical_result.method if row.statistical_result else None,
                "one_sided_p_value": raw_p,
                "holm_adjusted_p_value": corrected if raw_p is not None else None,
                "bonferroni_adjusted_p_value": min(1.0, raw_p * len(metrics))
                if raw_p is not None
                else None,
                "evidence_status": evidence,
            }
        )
    pair_p = [row.mcnemar_exact_two_sided_p_value for row in pairs]
    pair_adjusted = holm_bonferroni_adjusted([p if p is not None else 1.0 for p in pair_p])
    paired_results = [
        {
            **row.to_dict(),
            "status": "COMPLETE" if p is not None else "MISSING_NO_COMMON_TARGETS",
            "holm_adjusted_p_value": corrected if p is not None else None,
            "bonferroni_adjusted_p_value": min(1.0, p * len(pairs)) if p is not None else None,
        }
        for row, p, corrected in zip(pairs, pair_p, pair_adjusted, strict=True)
    ]
    return {
        "selection_origin": "C_EXISTING_FULL_HISTORY_RANKING",
        "independence_status": "REUSED_SELECTION_HISTORY_NOT_INDEPENDENT",
        "independent_holdout_claim_is_verified": False,
        "alpha": alpha,
        "candidate_count": len({(row.strategy_id, row.k) for row in metrics}),
        "hypothesis_family": "ALL_STRATEGY_K_WINDOW_OFFICIAL_ANY_PRIZE_UPPER_TAILS",
        "hypothesis_count": len(metrics),
        "untestable_hypothesis_policy": "P_ONE_FOR_CORRECTION_ONLY; REPORTED_VALUES_REMAIN_NULL",
        "candidate_results": results,
        "paired_family": "ALL_SAME_K_PAIRS_AND_WINDOWS; TWO_SIDED_MCNEMAR",
        "paired_hypothesis_count": len(pairs),
        "paired_results": paired_results,
        "candidate_label_permutation": {
            "status": "NOT_RUN_EXCHANGEABILITY_NOT_ESTABLISHED",
            "reason": "Actual ticket geometries and evaluable target sets differ within K.",
            "seed": None,
            "resamples": None,
            "empirical_p_value": None,
        },
        "research_limitations": [
            "All windows reuse historical selection data; no independent test set.",
            "Correction covers this frozen pool and these five windows, not unrecorded searches.",
            "Binomial/Poisson-binomial tails assume independent outcomes with specified p values.",
            "For adaptive portfolios, conditioning on the realized geometry sequence may violate "
            "that assumption; heterogeneous tails are a descriptive model, not a gain certificate.",
            "Wilson intervals are marginal descriptive intervals, not simultaneous intervals.",
            "Pairwise differences use only common targets, with a separate pair/window family.",
        ],
    }


def null_result_document(reason: str) -> dict[str, object]:
    """Describe the absence of per-period data without implying zero success."""

    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis_status": "NULL_NO_PER_PERIOD_EVIDENCE",
        "reason": reason,
        "prior_r1_judge_status": _PRIOR_R1_JUDGE_STATUS,
        "prior_r1_result_relabelled_verified": False,
        "candidate_count": 0,
        "K": None,
        "N": 0,
        "successful_count": None,
        "fair_success_probability": None,
        "exploration": {"status": "NULL", "candidate_count": 0, "N": 0, "successful_count": None},
        "unselected_historical": {
            "status": "NULL",
            "candidate_count": 0,
            "N": 0,
            "successful_count": None,
            "independence_status": "NOT_ESTABLISHED",
            "independent_holdout_claim_is_verified": False,
        },
        "exploration_null_permutation": {
            "status": "NULL",
            "seed": None,
            "resamples": None,
            "empirical_p_value": None,
        },
        "research_limitations": _limitations(),
    }


def write_json_document(document: Mapping[str, object], path: Path) -> Path:
    """Write one deterministic JSON artifact with sorted keys and a newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="JSON envelope with replay rows and null/split metadata"
    )
    parser.add_argument("--output", type=Path, help="write result JSON here; stdout if omitted")
    arguments = parser.parse_args(argv)
    payload = json.loads(arguments.input.read_text(encoding="utf-8"))
    result = analyze_payload(payload)
    serialized = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    if arguments.output is None:
        sys.stdout.write(serialized)
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")
    return 0


def _required_string(row: Mapping[str, object], field: str, index: int) -> str:
    value = row.get(field)
    if type(value) is not str or not value.strip():
        raise ValueError(f"replay row {index} requires non-empty {field}")
    return value


def _required_int(row: Mapping[str, object], field: str, index: int, *, minimum: int) -> int:
    return _exact_int(row.get(field), f"replay row {index} {field}", minimum=minimum)


def _exact_int(value: object, label: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an exact integer >= {minimum}")
    return value


def _number(value: object, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be numeric")
    result = float(cast(int | float, value))
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _string_array(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array of non-empty strings")
    items = cast(list[object], value)
    if any(type(item) is not str or not item for item in items):
        raise ValueError(f"{label} must be an array of non-empty strings")
    if len(set(items)) != len(items):
        raise ValueError(f"{label} must not contain duplicates")
    return tuple(cast(list[str], items))


def _normalize_probabilities(
    values: Mapping[int | str, Fraction | Mapping[str, object]],
) -> dict[int, Fraction]:
    if not isinstance(cast(object, values), Mapping) or not values:
        raise ValueError("fair_success_probability_by_k must be a non-empty mapping")
    output: dict[int, Fraction] = {}
    for raw_k, raw_probability in values.items():
        try:
            k = int(raw_k)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid K probability key: {raw_k!r}") from exc
        if type(raw_k) is bool or str(k) != str(raw_k) or k <= 0:
            raise ValueError(f"invalid K probability key: {raw_k!r}")
        if isinstance(raw_probability, Fraction):
            probability = raw_probability
        elif isinstance(cast(object, raw_probability), Mapping):
            numerator = _exact_int(raw_probability.get("numerator"), f"K={k} numerator", minimum=0)
            denominator = _exact_int(
                raw_probability.get("denominator"), f"K={k} denominator", minimum=1
            )
            probability = Fraction(numerator, denominator)
        else:
            raise ValueError(f"K={k} fair probability must be an exact rational")
        if not 0 < probability < 1:
            raise ValueError(f"K={k} fair probability must lie strictly between 0 and 1")
        if k in output:
            raise ValueError(f"duplicate fair probability for K={k}")
        output[k] = probability
    return output


def _index_records(
    records: Sequence[ReplaySuccess],
) -> tuple[
    dict[tuple[int, str], dict[str, dict[str, bool]]],
    dict[str, str],
    dict[str, bool],
]:
    grouped: dict[tuple[int, str], dict[str, dict[str, bool]]] = defaultdict(dict)
    target_partitions: dict[str, str] = {}
    target_independence: dict[str, bool] = {}
    seen: set[tuple[str, str, int]] = set()
    for row in records:
        if not isinstance(cast(object, row), ReplaySuccess):
            raise ValueError("records must contain ReplaySuccess values")
        prior_partition = target_partitions.setdefault(row.target_id, row.partition)
        if prior_partition != row.partition:
            raise ValueError(f"target {row.target_id} appears in both analysis partitions")
        prior_independence = target_independence.setdefault(
            row.target_id, row.independent_holdout_asserted
        )
        if prior_independence != row.independent_holdout_asserted:
            raise ValueError(f"holdout assertion differs across candidates for {row.target_id}")
        row_key = row.target_id, row.strategy_id, row.k
        if row_key in seen:
            raise ValueError(f"duplicate target/strategy/K result: {row_key}")
        seen.add(row_key)
        candidates = grouped[(row.k, row.partition)]
        outcomes = candidates.setdefault(row.strategy_id, {})
        if row.target_id in outcomes:
            raise ValueError(f"duplicate target result for {row.strategy_id}:{row.target_id}")
        outcomes[row.target_id] = row.success

    for (k, partition), candidates in grouped.items():
        candidate_ids = sorted(candidates)
        if len(candidate_ids) < 1:
            continue
        expected_targets = set(candidates[candidate_ids[0]])
        for candidate_id in candidate_ids[1:]:
            target_ids = set(candidates[candidate_id])
            if target_ids != expected_targets:
                raise ValueError(f"K={k} {partition} candidates must have identical target periods")
    for k in {group_key[0] for group_key in grouped}:
        exploration_ids = set(grouped.get((k, _EXPLORATION), {}))
        historical_ids = set(grouped.get((k, _UNSELECTED_HISTORICAL), {}))
        if exploration_ids and historical_ids and exploration_ids != historical_ids:
            raise ValueError(f"K={k} candidates must be present in both analysis partitions")
    return dict(grouped), target_partitions, target_independence


def _select_from_exploration(
    grouped: Mapping[tuple[int, str], Mapping[str, Mapping[str, bool]]],
) -> dict[int, str | None]:
    selected: dict[int, str | None] = {}
    k_values = sorted({k for k, _partition in grouped})
    for k in k_values:
        candidates = grouped.get((k, _EXPLORATION), {})
        if not candidates:
            selected[k] = None
            continue
        ranked = sorted(
            (
                sum(outcomes.values()),
                candidate_id,
            )
            for candidate_id, outcomes in candidates.items()
        )
        highest = max(success_count for success_count, _candidate in ranked)
        selected[k] = min(
            candidate for success_count, candidate in ranked if success_count == highest
        )
    return selected


def _summarize_partition(
    partition: str,
    grouped: Mapping[tuple[int, str], Mapping[str, Mapping[str, bool]]],
    p0_by_k: Mapping[int, Fraction],
    *,
    alpha: float,
    independence_status: str,
) -> dict[str, object]:
    candidates: list[dict[str, Any]] = []
    for (k, candidate_partition), strategy_map in sorted(grouped.items()):
        if candidate_partition != partition:
            continue
        for strategy_id, outcomes in sorted(strategy_map.items()):
            target_ids = sorted(outcomes)
            n = len(target_ids)
            successes = sum(outcomes.values())
            probability = p0_by_k[k]
            raw_p = binomial_upper_tail(n, successes, float(probability))
            candidates.append(
                {
                    "strategy_id": strategy_id,
                    "K": k,
                    "candidate_count_within_K": len(strategy_map),
                    "candidate_count": 0,
                    "N": n,
                    "successful_count": successes,
                    "observed_rate": successes / n,
                    "fair_success_probability": _fraction_document(probability),
                    "expected_success_count_under_null": n * float(probability),
                    "rate_difference_vs_fair_null": successes / n - float(probability),
                    "one_sided_exact_binomial_p_value": raw_p,
                }
            )

    candidate_count = len(candidates)
    raw_p_values = [float(item["one_sided_exact_binomial_p_value"]) for item in candidates]
    adjusted = holm_bonferroni_adjusted(raw_p_values)
    for index, item in enumerate(candidates):
        raw_p = raw_p_values[index]
        adjusted_p = adjusted[index]
        item["candidate_count"] = candidate_count
        item["bonferroni_adjusted_p_value"] = min(1.0, raw_p * candidate_count)
        item["holm_adjusted_p_value"] = adjusted_p
        item["null_hypothesis_rejected_after_holm"] = adjusted_p <= alpha
        item["statistical_result"] = _statistical_result(
            int(item["N"]),
            int(item["successful_count"]),
            float(item["fair_success_probability"]["value"]),  # type: ignore[index]
            adjusted_p,
            alpha,
        )
        item["evidence_status"] = _evidence_status(
            str(item["statistical_result"]), partition, independence_status
        )

    target_ids = sorted(
        {
            target_id
            for (_k, candidate_partition), strategy_map in grouped.items()
            if candidate_partition == partition
            for outcomes in strategy_map.values()
            for target_id in outcomes
        }
    )
    pairs = _pairwise_comparisons(grouped, partition, alpha=alpha)
    return {
        "status": "COMPLETE" if target_ids else "NULL",
        "partition": partition,
        "target_period_count": len(target_ids),
        "candidate_count": candidate_count,
        "N": len(target_ids),
        "successful_count": None,
        "candidate_results": candidates,
        "pairwise_comparison_count": len(pairs),
        "pairwise_comparisons": pairs,
    }


def _pairwise_comparisons(
    grouped: Mapping[tuple[int, str], Mapping[str, Mapping[str, bool]]],
    partition: str,
    *,
    alpha: float,
) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for (k, candidate_partition), strategy_map in sorted(grouped.items()):
        if candidate_partition != partition:
            continue
        strategy_ids = sorted(strategy_map)
        for left_index, left_id in enumerate(strategy_ids):
            left = strategy_map[left_id]
            for right_id in strategy_ids[left_index + 1 :]:
                right = strategy_map[right_id]
                target_ids = sorted(left)
                wins = sum(left[target] and not right[target] for target in target_ids)
                losses = sum(right[target] and not left[target] for target in target_ids)
                ties = len(target_ids) - wins - losses
                discordant = wins + losses
                pending.append(
                    {
                        "K": k,
                        "strategy_a": left_id,
                        "strategy_b": right_id,
                        "N": len(target_ids),
                        "successful_count_a": sum(left.values()),
                        "successful_count_b": sum(right.values()),
                        "paired_wins_a": wins,
                        "paired_wins_b": losses,
                        "paired_ties": ties,
                        "discordant_count": discordant,
                        "rate_difference_a_minus_b": (sum(left.values()) - sum(right.values()))
                        / len(target_ids),
                        "exact_two_sided_mcnemar_p_value": _mcnemar_p_value(discordant, wins),
                    }
                )

    adjusted = holm_bonferroni_adjusted(
        [float(item["exact_two_sided_mcnemar_p_value"]) for item in pending]
    )
    for index, item in enumerate(pending):
        adjusted_p = adjusted[index]
        difference = float(item["rate_difference_a_minus_b"])
        item["holm_adjusted_p_value"] = adjusted_p
        item["statistical_result"] = (
            "NO_GAIN"
            if difference <= 0
            else "PAIRED_FAMILYWISE_SIGNAL"
            if adjusted_p <= alpha
            else "UNCERTAIN"
        )
        if difference <= 0:
            item["evidence_status"] = "NO_GAIN"
        elif adjusted_p <= alpha and partition == _EXPLORATION:
            item["evidence_status"] = "EXPLORATORY_SIGNAL_ONLY"
        else:
            item["evidence_status"] = "UNCERTAIN"
    return pending


@cache
def _mcnemar_p_value(discordant: int, wins: int) -> float:
    if discordant == 0:
        return 1.0
    return binomial_two_sided_exact_p_value(discordant, wins, 0.5)


def _selected_holdout_summary(
    grouped: Mapping[tuple[int, str], Mapping[str, Mapping[str, bool]]],
    p0_by_k: Mapping[int, Fraction],
    selected_by_k: Mapping[int, str | None],
    historical: Mapping[str, Any],
    *,
    alpha: float,
) -> dict[str, object]:
    independence_status = str(historical["independence_status"])
    adjusted_by_candidate = {
        (int(item["K"]), str(item["strategy_id"])): item for item in historical["candidate_results"]
    }
    rows: list[dict[str, object]] = []
    for k, strategy_id in sorted(selected_by_k.items()):
        candidates = grouped.get((k, _UNSELECTED_HISTORICAL), {})
        if strategy_id is None or strategy_id not in candidates:
            rows.append(
                {
                    "K": k,
                    "selected_strategy_id": strategy_id,
                    "status": "NULL",
                    "N": 0,
                    "successful_count": None,
                }
            )
            continue
        outcomes = candidates[strategy_id]
        n = len(outcomes)
        successes = sum(outcomes.values())
        p0 = p0_by_k[k]
        raw_p = binomial_upper_tail(n, successes, float(p0))
        adjusted_result = adjusted_by_candidate[(k, strategy_id)]
        adjusted_p = float(adjusted_result["holm_adjusted_p_value"])
        rows.append(
            {
                "K": k,
                "selected_strategy_id": strategy_id,
                "status": "COMPLETE",
                "N": n,
                "successful_count": successes,
                "observed_rate": successes / n,
                "fair_success_probability": _fraction_document(p0),
                "one_sided_exact_binomial_p_value": raw_p,
                "holm_adjusted_p_value": adjusted_p,
                "selection_origin": "EXPLORATION_ONLY",
                "independence_status": independence_status,
                "independent_holdout_claim_is_verified": False,
                "evidence_status": _evidence_status(
                    _statistical_result(n, successes, float(p0), adjusted_p, alpha),
                    _UNSELECTED_HISTORICAL,
                    independence_status,
                ),
            }
        )
    return {
        "status": "COMPLETE" if any(row["status"] == "COMPLETE" for row in rows) else "NULL",
        "selection_rule": "MAXIMUM_EXPLORATION_SUCCESS_RATE; LEXICOGRAPHIC_STRATEGY_ID_TIEBREAK",
        "results": rows,
    }


def _selection_permutation(
    grouped: Mapping[tuple[int, str], Mapping[str, Mapping[str, bool]]],
    p0_by_k: Mapping[int, Fraction],
    *,
    alpha: float,
    seed: int,
    resamples: int,
) -> dict[str, object]:
    groups = [
        (k, candidates)
        for (k, partition), candidates in sorted(grouped.items())
        if partition == _EXPLORATION and candidates
    ]
    candidate_count = sum(len(candidates) for _k, candidates in groups)
    if candidate_count == 0:
        return {
            "status": "NULL",
            "method": "WITHIN_TARGET_SAME_K_CANDIDATE_LABEL_PERMUTATION",
            "seed": seed,
            "resamples": resamples,
            "candidate_count": 0,
            "observed_max_standardized_excess": None,
            "exceedance_count": None,
            "empirical_p_value": None,
        }

    observed_max = max(
        _standardized_excess(len(outcomes), sum(outcomes.values()), float(p0_by_k[k]))
        for k, candidates in groups
        for outcomes in candidates.values()
    )
    prepared_groups: list[tuple[int, int, float, tuple[int, ...]]] = []
    for k, candidates in groups:
        strategy_ids = sorted(candidates)
        target_ids = sorted(next(iter(candidates.values())))
        row_success_counts = tuple(
            sum(candidates[strategy_id][target_id] for strategy_id in strategy_ids)
            for target_id in target_ids
        )
        prepared_groups.append(
            (len(strategy_ids), len(target_ids), float(p0_by_k[k]), row_success_counts)
        )
    rng = random.Random(seed)
    exceedances = 0
    for _replicate in range(resamples):
        replicate_max = -math.inf
        for candidate_total, n, p0, row_success_counts in prepared_groups:
            candidate_counts = [0] * candidate_total
            for success_count in row_success_counts:
                if success_count == candidate_total:
                    candidate_counts = [count + 1 for count in candidate_counts]
                elif success_count:
                    for index in rng.sample(range(candidate_total), success_count):
                        candidate_counts[index] += 1
            replicate_max = max(
                replicate_max,
                max(_standardized_excess(n, count, p0) for count in candidate_counts),
            )
        if replicate_max >= observed_max - 1e-12:
            exceedances += 1

    empirical_p = (exceedances + 1) / (resamples + 1)
    return {
        "status": "COMPLETE",
        "method": "WITHIN_TARGET_SAME_K_CANDIDATE_LABEL_PERMUTATION",
        "null_hypothesis": "CANDIDATE_IDENTITIES_ARE_EXCHANGEABLE_WITHIN_EACH_TARGET_AND_K",
        "statistic": "MAXIMUM_STANDARDIZED_EXCESS_OVER_SPECIFIED_FAIR_SUCCESS_PROBABILITY",
        "seed": seed,
        "resamples": resamples,
        "candidate_count": candidate_count,
        "observed_max_standardized_excess": observed_max,
        "exceedance_count": exceedances,
        "empirical_p_value_plus_one": empirical_p,
        "null_hypothesis_rejected_at_alpha": empirical_p <= alpha,
        "random_generator": "Python random.Random; sorted input order; local generator",
    }


def _standardized_excess(n: int, successes: int, p0: float) -> float:
    standard_deviation = math.sqrt(n * p0 * (1.0 - p0))
    return (successes - n * p0) / standard_deviation


def _historical_independence_status(
    target_ids: set[str],
    target_independence: Mapping[str, bool],
    reused_target_ids: frozenset[str],
) -> tuple[str, int]:
    if not target_ids:
        return "NOT_ESTABLISHED", 0
    overlap = target_ids & reused_target_ids
    if len(target_ids) == _REUSED_436_TARGET_COUNT:
        return "REUSED_436_NOT_INDEPENDENT", len(overlap)
    if overlap:
        return "REUSED_TARGETS_NOT_INDEPENDENT", len(overlap)
    if all(target_independence.get(target_id, False) for target_id in target_ids):
        return "USER_ASSERTED_NOT_VERIFIED", 0
    return "NOT_ESTABLISHED", 0


def _statistical_result(n: int, successes: int, p0: float, adjusted_p: float, alpha: float) -> str:
    if n == 0:
        return "NULL"
    if successes / n <= p0:
        return "NO_GAIN"
    if adjusted_p <= alpha:
        return "FAMILYWISE_SIGNAL"
    return "UNCERTAIN"


def _evidence_status(statistical_result: str, partition: str, independence_status: str) -> str:
    if statistical_result == "NULL":
        return "NULL"
    if statistical_result == "NO_GAIN":
        return "NO_GAIN"
    if statistical_result == "UNCERTAIN":
        return "UNCERTAIN"
    if partition == _EXPLORATION:
        return "EXPLORATORY_SIGNAL_ONLY"
    if independence_status != "USER_ASSERTED_NOT_VERIFIED":
        return "UNCERTAIN"
    return "HISTORICAL_SIGNAL_PROVENANCE_UNVERIFIED"


def _fraction_document(probability: Fraction) -> dict[str, int | float]:
    return {
        "numerator": probability.numerator,
        "denominator": probability.denominator,
        "value": float(probability),
    }


def _limitations() -> list[str]:
    return [
        (
            "The exact fair probability must match K and the any-winning-ticket event; "
            "prize rules are not derived here."
        ),
        "Exact binomial p-values assume independent target outcomes under the fair null.",
        (
            "Holm covers every strategy-K candidate in a partition; "
            "Bonferroni values are also emitted."
        ),
        (
            "Permutation conditions on per-target success totals and assumes exchangeable "
            "candidate labels within K; it does not shuffle draw outcomes."
        ),
        (
            "Pairwise results use exact two-sided McNemar tests on same-target outcomes, "
            "with Holm correction across the pair family."
        ),
        (
            "Unselected history is descriptive unless provenance establishes exclusion; "
            "a 436-target partition is never labelled independent."
        ),
        (
            "The prior R1 Judge remains BLOCKED_UNVERIFIABLE; this analysis does not "
            "reclassify it as verified."
        ),
    ]


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ReplaySuccess",
    "analyze_payload",
    "calibrate_historical_windows",
    "calibrate_selection_bias",
    "main",
    "null_result_document",
    "replay_successes_from_rows",
    "write_json_document",
]
