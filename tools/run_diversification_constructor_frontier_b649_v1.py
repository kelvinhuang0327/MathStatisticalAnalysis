"""Execute the locked DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 experiment.

Reads locked parameters from
`docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (mirrors
`run_diversification_coverage_p638_zone1_v1.py`'s pattern). Computes, at
real B649 scale (`pool_size=49, draw_size=6`), for the very first time:

- arm A (`CYCLIC_SIDON_SHIFT_B649_V1`, immutable, unmodified) and arm D
  (`exact_random_portfolio_coverage`, immutable, unmodified) fresh at all
  four thresholds `m in {3,4,5,6}` -- the sealed
  `DIVERSIFICATION_COVERAGE_B649_V1` cell never locked `m=6`, so this is a
  new computation from the same immutable inputs, not a reuse of that
  cell's own JSON;
- arm B (`GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1`) and arm C
  (`RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1`, via the fast-evaluator-backed
  `bounded_coverage_optimizer_fast.restart_greedy_swap_search_fast`) at real
  B649 scale for the first time ever -- the Phase-5 design task (971b97b)
  explicitly deferred both to this lock-and-execute task.

Arms A and B are strict nested-prefix constructions: each is built once at
`max(K)` and every smaller `k`'s portfolio is an exact prefix (structurally
guaranteed, not just observed -- monotonicity in `k` is asserted for both).
Arm C is `INDEPENDENT_PER_K` (971b97b Sec 6.1): one independent bounded
search per ladder rung, no carried portfolio, so its `Q_C(k)` is not
asserted monotonic in `k` -- only observed and reported.

`MONTE_CARLO: NONE`. `REAL_DRAW_HISTORY: NOT_USED`. Every coverage value is
an exact `fractions.Fraction`.
"""

from __future__ import annotations

import itertools
import json
import math
import resource
import statistics
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research.bounded_coverage_optimizer_fast import restart_greedy_swap_search_fast
from lottolab.research.cyclic_sidon_shift import SIDON_BASE_SET_0_INDEXED, sidon_shift_portfolio
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    fast_exact_portfolio_coverage,
)
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "diversification-constructor-frontier-b649-v1-preregistration-hash.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-result.json"
)

Ticket = tuple[int, ...]

_CLASSIFICATION_BY_SIGNS: dict[frozenset[int], str] = {
    frozenset({1}): "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE",
    frozenset({0}): "MATCHES_RANDOM_EXPECTED_COVERAGE",
    frozenset({-1}): "UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE",
}

FRONTIER_NEARNESS_MARGIN = Fraction(9, 10)


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError(
            "preregistration hash mismatch -- the locked parameters file was "
            "modified after locking; refusing to execute against tampered parameters"
        )
    return locked


def _verify_evaluation_ceiling(locked: dict[str, Any]) -> int:
    ladder: list[int] = locked["exposure_ladder"]
    restart_count = locked["optimizer_restart_count"]
    candidate_sample_size = locked["optimizer_candidate_sample_size"]
    max_swap_passes = locked["optimizer_max_swap_passes"]
    per_k_ceiling = {
        k: restart_count
        * (k * candidate_sample_size + max_swap_passes * k * (candidate_sample_size + 1))
        for k in ladder
    }
    total = sum(per_k_ceiling.values())
    locked_total = locked["optimizer_max_candidate_evaluations_total_ladder"]
    if total != locked_total:
        raise ValueError(
            f"evaluation ceiling formula produced {total}, locked value says {locked_total} "
            "-- refusing to execute against an inconsistent budget lock"
        )
    return total


def geometry_metrics(pool_size: int, portfolio: tuple[Ticket, ...]) -> dict[str, Any]:
    k = len(portfolio)
    duplicate_tickets = k - len(set(portfolio))
    if duplicate_tickets != 0:
        raise ValueError(f"duplicate_tickets invariant violated: {duplicate_tickets} != 0")

    pair_overlaps = [
        len(set(a) & set(b)) for a, b in itertools.combinations(portfolio, 2)
    ]
    overlap_profile: dict[str, int] = {}
    for overlap in pair_overlaps:
        overlap_profile[str(overlap)] = overlap_profile.get(str(overlap), 0) + 1

    number_use_counts = {str(n): 0 for n in range(1, pool_size + 1)}
    for ticket in portfolio:
        for number in ticket:
            number_use_counts[str(number)] += 1
    unique_number_coverage = sum(1 for count in number_use_counts.values() if count >= 1)

    mean_pairwise_overlap = (
        (sum(pair_overlaps) / len(pair_overlaps)) if pair_overlaps else 0.0
    )
    return {
        "max_pairwise_overlap": max(pair_overlaps, default=0),
        "mean_pairwise_overlap": mean_pairwise_overlap,
        "overlap_profile": overlap_profile,
        "number_use_counts": number_use_counts,
        "unique_number_coverage": unique_number_coverage,
        "reuse_dispersion": statistics.pstdev(number_use_counts.values()),
        "duplicate_tickets": duplicate_tickets,
    }


def _fraction_entry(value: Fraction) -> dict[str, Any]:
    return {"exact": f"{value.numerator}/{value.denominator}", "float": float(value)}


def _q_by_k(
    pool_size: int,
    draw_size: int,
    thresholds: list[int],
    ladder: list[int],
    portfolio_by_k: dict[int, tuple[Ticket, ...]],
) -> dict[int, dict[int, Fraction]]:
    q: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for k in ladder:
        portfolio = portfolio_by_k[k]
        for m in thresholds:
            q[m][k] = fast_exact_portfolio_coverage(pool_size, draw_size, m, portfolio)
        clear_cache()
    return q


def run(locked: dict[str, Any]) -> dict[str, Any]:
    pool_size: int = locked["pool_size"]
    draw_size: int = locked["draw_size"]
    ladder: list[int] = locked["exposure_ladder"]
    max_k = max(ladder)
    primary_m: int = locked["primary_event_minimum_matches"]
    secondary_m: list[int] = locked["secondary_event_minimum_matches"]
    thresholds = [primary_m, *secondary_m]

    if list(SIDON_BASE_SET_0_INDEXED) != locked["sidon_base_set_0_indexed"]:
        raise ValueError("arm A base set drifted from the locked sidon_base_set_0_indexed")

    total_evaluation_ceiling = _verify_evaluation_ceiling(locked)

    runtime: dict[str, Any] = {}
    t_start = time.perf_counter()

    # Arm A: SIDON_REFERENCE (immutable, nested prefix)
    t0 = time.perf_counter()
    sidon_full = sidon_shift_portfolio(max_k)
    portfolio_a = {k: sidon_full[:k] for k in ladder}
    runtime["arm_a_seconds"] = time.perf_counter() - t0

    # Arm B: NON_SIDON_LOW_OVERLAP, real B649 scale for the first time (nested prefix)
    t0 = time.perf_counter()
    greedy_full = greedy_min_overlap_portfolio(pool_size, draw_size, max_k)
    portfolio_b = {k: greedy_full[:k] for k in ladder}
    runtime["arm_b_seconds"] = time.perf_counter() - t0

    # Arm C: BOUNDED_COVERAGE_OPTIMIZER, INDEPENDENT_PER_K, real B649 scale for the first time
    portfolio_c: dict[int, tuple[Ticket, ...]] = {}
    arm_c_search: dict[int, dict[str, Any]] = {}
    runtime["arm_c_seconds_by_k"] = {}
    total_evaluations_used = 0
    for k in ladder:
        t0 = time.perf_counter()
        result = restart_greedy_swap_search_fast(
            pool_size,
            draw_size,
            primary_m,
            k,
            seed=locked["optimizer_seed"],
            restart_count=locked["optimizer_restart_count"],
            candidate_sample_size=locked["optimizer_candidate_sample_size"],
            max_swap_passes=locked["optimizer_max_swap_passes"],
        )
        dt = time.perf_counter() - t0
        runtime["arm_c_seconds_by_k"][str(k)] = dt
        portfolio_c[k] = result.portfolio
        total_evaluations_used += result.evaluations_used
        arm_c_search[k] = {
            "evaluations_used": result.evaluations_used,
            "best_restart_index": result.best_restart_index,
            "converged_by_restart": [outcome.converged for outcome in result.restart_outcomes],
            "swap_passes_run_by_restart": [
                outcome.swap_passes_run for outcome in result.restart_outcomes
            ],
        }

    if total_evaluations_used > total_evaluation_ceiling:
        raise ValueError(
            f"optimizer budget enforcement failed: used {total_evaluations_used} > "
            f"ceiling {total_evaluation_ceiling}"
        )

    # Arm D: RANDOM_EXPECTED_BASELINE (immutable, closed form, no portfolio/geometry)
    t0 = time.perf_counter()
    q_d: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for m in thresholds:
        for k in ladder:
            q_d[m][k] = exact_random_portfolio_coverage(pool_size, draw_size, m, k)
    runtime["arm_d_seconds"] = time.perf_counter() - t0

    # Coverage at all thresholds for A, B, C
    q_a = _q_by_k(pool_size, draw_size, thresholds, ladder, portfolio_a)
    q_b = _q_by_k(pool_size, draw_size, thresholds, ladder, portfolio_b)
    q_c = _q_by_k(pool_size, draw_size, thresholds, ladder, portfolio_c)

    runtime["total_seconds"] = time.perf_counter() - t_start
    peak_memory_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Structural sanity checks (asserted, not just observed)
    for m in thresholds:
        if q_a[m][1] != q_d[m][1]:
            raise ValueError(f"sanity check failed: arm A vs D at k=1, m={m} are not equal")
        if q_b[m][1] != q_d[m][1]:
            raise ValueError(f"sanity check failed: arm B vs D at k=1, m={m} are not equal")
        if q_c[m][1] != q_d[m][1]:
            raise ValueError(f"sanity check failed: arm C vs D at k=1, m={m} are not equal")
    for m in thresholds:
        for previous_k, current_k in itertools.pairwise(ladder):
            if q_a[m][current_k] < q_a[m][previous_k]:
                raise ValueError(f"arm A coverage not monotonic in k at m={m}")
            if q_b[m][current_k] < q_b[m][previous_k]:
                raise ValueError(f"arm B coverage not monotonic in k at m={m}")

    arm_c_monotonic = all(
        q_c[primary_m][current_k] >= q_c[primary_m][previous_k]
        for previous_k, current_k in itertools.pairwise(ladder)
    )

    # Deltas (all thresholds) for arms A, B, C vs random and vs Sidon
    delta_random: dict[str, dict[int, dict[int, Fraction]]] = {}
    relative_lift_vs_random: dict[str, dict[int, dict[int, float | None]]] = {}
    for label, q_arm in (("a", q_a), ("b", q_b), ("c", q_c)):
        delta_random[label] = {
            m: {k: q_arm[m][k] - q_d[m][k] for k in ladder} for m in thresholds
        }
        relative_lift_vs_random[label] = {
            m: {
                k: (
                    (float(delta_random[label][m][k]) / float(q_d[m][k]))
                    if q_d[m][k] != 0
                    else None
                )
                for k in ladder
            }
            for m in thresholds
        }
    delta_sidon: dict[str, dict[int, dict[int, Fraction]]] = {
        label: {m: {k: q_arm[m][k] - q_a[m][k] for k in ladder} for m in thresholds}
        for label, q_arm in (("b", q_b), ("c", q_c))
    }

    # Deterministic classification (primary event, k > 1, reused verbatim)
    classification: dict[str, str] = {}
    for label in ("a", "b", "c"):
        primary_deltas_excl_k1 = [delta_random[label][primary_m][k] for k in ladder if k != 1]
        signs = {(1 if d > 0 else (-1 if d < 0 else 0)) for d in primary_deltas_excl_k1}
        classification[label] = _CLASSIFICATION_BY_SIGNS.get(frozenset(signs), "MIXED_BY_EXPOSURE")

    # Frontier estimands (primary event only, per 971b97b Sec 5/10-11)
    best_found_q: dict[int, Fraction] = {}
    best_found_constructor: dict[int, str] = {}
    sidon_frontier_gap: dict[int, Fraction] = {}
    frontier_capture_ratio: dict[int, Any] = {}
    for k in ladder:
        candidates = {"a": q_a[primary_m][k], "b": q_b[primary_m][k], "c": q_c[primary_m][k]}
        winner = max(candidates, key=lambda label: candidates[label])
        best_found_q[k] = candidates[winner]
        best_found_constructor[k] = winner
        sidon_frontier_gap[k] = best_found_q[k] - q_a[primary_m][k]
        if k == 1:
            frontier_capture_ratio[k] = "NOT_APPLICABLE_K1"
            continue
        sidon_delta_random = q_a[primary_m][k] - q_d[primary_m][k]
        best_found_delta_random = best_found_q[k] - q_d[primary_m][k]
        if best_found_delta_random <= 0:
            frontier_capture_ratio[k] = "NOT_APPLICABLE"
        else:
            frontier_capture_ratio[k] = sidon_delta_random / best_found_delta_random

    ladder_gt1 = [k for k in ladder if k != 1]
    sidon_delta_random_gt1 = {k: q_a[primary_m][k] - q_d[primary_m][k] for k in ladder_gt1}
    any_sidon_delta_negative = any(delta < 0 for delta in sidon_delta_random_gt1.values())
    defined_ratios = {
        k: frontier_capture_ratio[k]
        for k in ladder_gt1
        if isinstance(frontier_capture_ratio[k], Fraction)
    }
    all_k_have_defined_ratio = len(defined_ratios) == len(ladder_gt1)
    near_frontier = (
        not any_sidon_delta_negative
        and all_k_have_defined_ratio
        and all(ratio >= FRONTIER_NEARNESS_MARGIN for ratio in defined_ratios.values())
    )
    all_gaps_le_zero = all(sidon_frontier_gap[k] <= 0 for k in ladder_gt1)
    if near_frontier:
        sidon_frontier_classification = "NEAR_BEST_FOUND_FRONTIER"
    elif all_gaps_le_zero:
        sidon_frontier_classification = "SIDON_AT_OR_ABOVE_BEST_FOUND"
    else:
        sidon_frontier_classification = "SIDON_BELOW_FRONTIER_MARGIN"

    # Required Question 1 ("does arm B reproduce most of Sidon's gain?",
    # 971b97b Sec 12 item 1): answered from arm B's own DELTA_SIDON(k),
    # reusing the one already-frozen FRONTIER_NEARNESS_MARGIN rather than a
    # new ad hoc threshold -- not a post-hoc metric, a direct application of
    # the design doc's own prescribed reading of an already-frozen estimand.
    arm_b_sidon_capture_ratio: dict[int, Any] = {}
    for k in ladder:
        if k == 1:
            arm_b_sidon_capture_ratio[k] = "NOT_APPLICABLE_K1"
            continue
        sidon_delta_random_k = q_a[primary_m][k] - q_d[primary_m][k]
        arm_b_delta_random_k = q_b[primary_m][k] - q_d[primary_m][k]
        if sidon_delta_random_k <= 0:
            arm_b_sidon_capture_ratio[k] = "NOT_APPLICABLE_SIDON_DID_NOT_BEAT_RANDOM"
        else:
            arm_b_sidon_capture_ratio[k] = arm_b_delta_random_k / sidon_delta_random_k

    defined_b_ratios = {
        k: r for k, r in arm_b_sidon_capture_ratio.items() if isinstance(r, Fraction)
    }
    all_b_ratio_ge_margin = len(defined_b_ratios) == len(ladder_gt1) and all(
        ratio >= FRONTIER_NEARNESS_MARGIN for ratio in defined_b_ratios.values()
    )
    all_b_delta_sidon_non_negative = all(
        (q_b[primary_m][k] - q_a[primary_m][k]) >= 0 for k in ladder_gt1
    )
    all_b_delta_sidon_negative = all(
        (q_b[primary_m][k] - q_a[primary_m][k]) < 0 for k in ladder_gt1
    )
    if all_b_delta_sidon_non_negative or all_b_ratio_ge_margin:
        low_overlap_mechanism_result = "REPRODUCES_MOST_OF_SIDON_GAIN"
    elif all_b_delta_sidon_negative:
        low_overlap_mechanism_result = "DOES_NOT_REPRODUCE_SIDON_GAIN"
    else:
        low_overlap_mechanism_result = "PARTIALLY_REPRODUCES_SIDON_GAIN"

    # Replication eligibility (971b97b Sec 11), arm-level, applied to B and C independently
    replication_eligibility: dict[str, dict[str, Any]] = {}
    for label in ("b", "c"):
        condition_a = classification[label] == "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE"
        condition_b = any(delta_sidon[label][primary_m][k] > 0 for k in ladder)
        # Both modules are parametrized by (pool_size, draw_size); no B649-tuned constant.
        condition_c = True
        eligible = condition_a and condition_b and condition_c
        status = (
            "ELIGIBLE_FOR_T539_P638_REPLICATION" if eligible else "NOT_ELIGIBLE_FOR_REPLICATION"
        )
        replication_eligibility[label] = {
            "eligible": eligible,
            "status": status,
            "condition_a_outperforms_random_full_ladder": condition_a,
            "condition_b_beats_sidon_at_some_k": condition_b,
            "condition_c_generically_parametrized": condition_c,
        }

    # Geometry (arms A, B, C, every k)
    geometry: dict[str, dict[int, dict[str, Any]]] = {
        "a": {k: geometry_metrics(pool_size, portfolio_a[k]) for k in ladder},
        "b": {k: geometry_metrics(pool_size, portfolio_b[k]) for k in ladder},
        "c": {k: geometry_metrics(pool_size, portfolio_c[k]) for k in ladder},
    }

    def _q_out(q: dict[int, dict[int, Fraction]]) -> dict[str, dict[str, Any]]:
        return {str(m): {str(k): _fraction_entry(q[m][k]) for k in ladder} for m in thresholds}

    def _delta_out(delta: dict[int, dict[int, Fraction]]) -> dict[str, dict[str, Any]]:
        return {str(m): {str(k): _fraction_entry(delta[m][k]) for k in ladder} for m in thresholds}

    def _geometry_out(geo_by_k: dict[int, dict[str, Any]]) -> dict[str, Any]:
        return {str(k): geo_by_k[k] for k in ladder}

    return {
        "matrix_variant_id": locked["matrix_variant_id"],
        "hypothesis_family_id": locked["hypothesis_family_id"],
        "lottery_type": locked["lottery_type"],
        "preregistration_hash_sha256": canonical_json.sha256_hex(
            canonical_json.canonical_bytes(locked)
        ),
        "total_draws_enumerated": math.comb(pool_size, draw_size),
        "primary_event_minimum_matches": primary_m,
        "secondary_event_minimum_matches": secondary_m,
        "exposure_ladder": ladder,
        "sidon_mode": locked["sidon_mode"],
        "optimizer_mode": locked["optimizer_mode"],
        "sanity_check_delta_at_k1_is_exactly_zero": True,
        "arm_c_primary_coverage_monotonic_in_k": arm_c_monotonic,
        "q": {"a": _q_out(q_a), "b": _q_out(q_b), "c": _q_out(q_c), "d": _q_out(q_d)},
        "delta_random": {label: _delta_out(delta_random[label]) for label in ("a", "b", "c")},
        "delta_sidon": {label: _delta_out(delta_sidon[label]) for label in ("b", "c")},
        "relative_lift_vs_random_primary_event_float": {
            label: {str(k): relative_lift_vs_random[label][primary_m][k] for k in ladder}
            for label in ("a", "b", "c")
        },
        "best_found_q_primary_event": {
            str(k): _fraction_entry(best_found_q[k]) for k in ladder
        },
        "best_found_constructor_primary_event": {str(k): best_found_constructor[k] for k in ladder},
        "sidon_frontier_gap_primary_event": {
            str(k): _fraction_entry(sidon_frontier_gap[k]) for k in ladder
        },
        "frontier_capture_ratio_primary_event": {
            str(k): (
                _fraction_entry(frontier_capture_ratio[k])
                if isinstance(frontier_capture_ratio[k], Fraction)
                else frontier_capture_ratio[k]
            )
            for k in ladder
        },
        "descriptive_classification": classification,
        "sidon_frontier_classification": sidon_frontier_classification,
        "near_frontier": near_frontier,
        "low_overlap_mechanism_result": low_overlap_mechanism_result,
        "arm_b_sidon_capture_ratio_primary_event": {
            str(k): (
                _fraction_entry(arm_b_sidon_capture_ratio[k])
                if isinstance(arm_b_sidon_capture_ratio[k], Fraction)
                else arm_b_sidon_capture_ratio[k]
            )
            for k in ladder
        },
        "replication_eligibility": replication_eligibility,
        "global_optimum_status": "UNKNOWN",
        "geometry": {
            "a": _geometry_out(geometry["a"]),
            "b": _geometry_out(geometry["b"]),
            "c": _geometry_out(geometry["c"]),
        },
        "optimizer": {
            "seed": locked["optimizer_seed"],
            "restart_count": locked["optimizer_restart_count"],
            "candidate_sample_size": locked["optimizer_candidate_sample_size"],
            "max_swap_passes": locked["optimizer_max_swap_passes"],
            "evaluation_ceiling_total_ladder": total_evaluation_ceiling,
            "evaluations_used_total_ladder": total_evaluations_used,
            "search_by_k": {str(k): arm_c_search[k] for k in ladder},
        },
        "runtime_seconds": runtime,
        "peak_memory_bytes": peak_memory_bytes,
        "scope": {
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "t539": "NOT_RUN",
            "p638": "NOT_RUN",
            "production_promotion": "NO",
            "cohort_creation": "NO",
            "prospective_activation": "NO",
        },
    }


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"descriptive_classification: {result['descriptive_classification']}")
    print(f"sidon_frontier_classification: {result['sidon_frontier_classification']}")
    print(f"near_frontier: {result['near_frontier']}")
    print(f"replication_eligibility: {result['replication_eligibility']}")
    print(f"total runtime: {result['runtime_seconds']['total_seconds']:.1f}s")
    print(f"peak memory: {result['peak_memory_bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
