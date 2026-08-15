"""Execute the locked GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 experiment.

Reads locked parameters from
`docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (same
fail-closed pattern every prior lock-and-execute script in this Matrix
uses). Computes, at real T539 scale (`pool_size=39, draw_size=5`, for the
first time ever):

- arm A (`CYCLIC_SIDON_SHIFT_T539_V1`, immutable, unmodified) and arm B
  (`GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1`, first real-scale invocation)
  via the same single-pass earliest-index enumeration method
  `run_diversification_coverage_t539_v1.py` already used -- no
  B649-specific fast evaluator, per the design doc's own feasibility
  finding (`strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md`
  S6) that arm B's construction cost, not its coverage evaluation, is
  what dominates;
- arm C (`RANDOM_EXPECTED_COVERAGE`, closed form, immutable, unmodified).

Arms A and B are strict nested-prefix constructions: each is built once at
`max(K)` and every smaller `k`'s portfolio is an exact prefix (structurally
guaranteed, not just observed -- monotonicity in `k` is asserted for both).
Arm A's coverage is additionally cross-checked for exact identity against
the already-sealed `DIVERSIFICATION_COVERAGE_T539_V1` cell's own
`q_sidon` values -- an identity check, not a rerun that could produce a
different number, since arm A's constructor and the evaluation method are
both unchanged.

`MONTE_CARLO: NONE`. `REAL_DRAW_HISTORY: NOT_USED`. Every coverage value is
an exact `fractions.Fraction`. B649's own bounded-optimizer arm has no
counterpart here -- three arms only, per the Owner packet.
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
from lottolab.research.cyclic_sidon_shift_t539 import (
    SIDON_BASE_SET_0_INDEXED,
    sidon_shift_portfolio,
)
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage
from lottolab.research.greedy_min_overlap_constructor_t539 import (
    greedy_min_overlap_portfolio_t539,
)

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "greedy-min-overlap-constructor-t539-v1-preregistration-hash.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-result.json"
)
SEALED_COVERAGE_RESULT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-t539-v1-result.json"
)

Ticket = tuple[int, ...]


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


def _ticket_bitmask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def geometry_metrics(pool_size: int, portfolio: tuple[Ticket, ...]) -> dict[str, Any]:
    k = len(portfolio)
    duplicate_tickets = k - len(set(portfolio))
    if duplicate_tickets != 0:
        raise ValueError(f"duplicate_tickets invariant violated: {duplicate_tickets} != 0")

    pair_overlaps = [len(set(a) & set(b)) for a, b in itertools.combinations(portfolio, 2)]
    overlap_profile: dict[str, int] = {}
    for overlap in pair_overlaps:
        overlap_profile[str(overlap)] = overlap_profile.get(str(overlap), 0) + 1

    number_use_counts = {str(n): 0 for n in range(1, pool_size + 1)}
    for ticket in portfolio:
        for number in ticket:
            number_use_counts[str(number)] += 1
    unique_number_coverage = sum(1 for count in number_use_counts.values() if count >= 1)
    mean_pairwise_overlap = (sum(pair_overlaps) / len(pair_overlaps)) if pair_overlaps else 0.0

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


def _earliest_index_counts(
    ticket_masks: list[int],
    thresholds: list[int],
    max_k: int,
    pool_size: int,
    draw_size: int,
) -> dict[int, list[int]]:
    counts: dict[int, list[int]] = {m: [0] * (max_k + 1) for m in thresholds}
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_mask = _ticket_bitmask(draw)
        remaining = set(thresholds)
        earliest = dict.fromkeys(thresholds, max_k)
        for index, mask in enumerate(ticket_masks):
            if not remaining:
                break
            hits = (draw_mask & mask).bit_count()
            satisfied_now = [m for m in remaining if hits >= m]
            for m in satisfied_now:
                earliest[m] = index
                remaining.discard(m)
        for m in thresholds:
            counts[m][earliest[m]] += 1
    return counts


def _prefix_q(
    earliest_index_counts: dict[int, list[int]],
    thresholds: list[int],
    ladder: list[int],
    max_k: int,
    total_draws: int,
) -> dict[int, dict[int, Fraction]]:
    q: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for m in thresholds:
        cumulative = 0
        prefix_counts: dict[int, int] = {}
        for i in range(max_k):
            cumulative += earliest_index_counts[m][i]
            prefix_counts[i + 1] = cumulative
        for k in ladder:
            q[m][k] = Fraction(prefix_counts[k], total_draws)
    return q


def _classify_by_signs(
    deltas: list[Fraction], all_positive: str, all_nonpositive: str, mixed: str
) -> str:
    signs = {(1 if d > 0 else (-1 if d < 0 else 0)) for d in deltas}
    if signs == {1}:
        return all_positive
    if 1 not in signs:
        return all_nonpositive
    return mixed


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

    runtime: dict[str, Any] = {}
    t_start = time.perf_counter()

    # Arm A: SIDON_REFERENCE (immutable, nested prefix)
    t0 = time.perf_counter()
    sidon_full = sidon_shift_portfolio(max_k)
    runtime["arm_a_seconds"] = time.perf_counter() - t0
    if len(set(sidon_full)) != len(sidon_full):
        raise ValueError("arm A duplicate_tickets invariant violated at max_k")

    # Arm B: NON_SIDON_LOW_OVERLAP, real T539 scale for the first time (nested prefix)
    t0 = time.perf_counter()
    greedy_full = greedy_min_overlap_portfolio_t539(max_k)
    runtime["arm_b_seconds"] = time.perf_counter() - t0
    if len(set(greedy_full)) != len(greedy_full):
        raise ValueError("arm B duplicate_tickets invariant violated at max_k")

    portfolio_b = {k: greedy_full[:k] for k in ladder}

    sidon_masks = [_ticket_bitmask(t) for t in sidon_full]
    greedy_masks = [_ticket_bitmask(t) for t in greedy_full]
    total_draws = math.comb(pool_size, draw_size)

    t0 = time.perf_counter()
    earliest_a = _earliest_index_counts(sidon_masks, thresholds, max_k, pool_size, draw_size)
    earliest_b = _earliest_index_counts(greedy_masks, thresholds, max_k, pool_size, draw_size)
    runtime["enumeration_seconds"] = time.perf_counter() - t0

    q_a = _prefix_q(earliest_a, thresholds, ladder, max_k, total_draws)
    q_b = _prefix_q(earliest_b, thresholds, ladder, max_k, total_draws)

    q_c: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for m in thresholds:
        for k in ladder:
            q_c[m][k] = exact_random_portfolio_coverage(pool_size, draw_size, m, k)

    runtime["total_seconds"] = time.perf_counter() - t_start
    peak_memory_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Identity cross-check: arm A recomputed fresh here must exactly match the
    # already-sealed DIVERSIFICATION_COVERAGE_T539_V1 cell's own q_sidon values.
    sealed = json.loads(SEALED_COVERAGE_RESULT_PATH.read_text(encoding="utf-8"))
    for m in thresholds:
        for k in ladder:
            sealed_exact = sealed["q_sidon"][str(m)][str(k)]["exact"]
            num, den = sealed_exact.split("/")
            if q_a[m][k] != Fraction(int(num), int(den)):
                raise ValueError(
                    f"arm A coverage drifted from the sealed coverage cell at m={m}, k={k}"
                )
    arm_a_identity_check_vs_sealed_coverage_cell = True

    # Structural sanity checks (asserted, not just observed)
    for m in thresholds:
        if q_a[m][1] != q_c[m][1]:
            raise ValueError(f"sanity check failed: arm A vs C at k=1, m={m} are not equal")
        if q_b[m][1] != q_c[m][1]:
            raise ValueError(f"sanity check failed: arm B vs C at k=1, m={m} are not equal")
    for m in thresholds:
        for previous_k, current_k in itertools.pairwise(ladder):
            if q_a[m][current_k] < q_a[m][previous_k]:
                raise ValueError(f"arm A coverage not monotonic in k at m={m}")
            if q_b[m][current_k] < q_b[m][previous_k]:
                raise ValueError(f"arm B coverage not monotonic in k at m={m}")

    delta_random_b = {m: {k: q_b[m][k] - q_c[m][k] for k in ladder} for m in thresholds}
    delta_random_sidon = {m: {k: q_a[m][k] - q_c[m][k] for k in ladder} for m in thresholds}
    delta_sidon = {m: {k: q_b[m][k] - q_a[m][k] for k in ladder} for m in thresholds}

    # Required sanity checks (preregistration S5): both exactly 0 at k=1.
    if delta_random_b[primary_m][1] != 0:
        raise ValueError("required sanity check failed: DELTA_RANDOM_B(1) != 0")
    if delta_sidon[primary_m][1] != 0:
        raise ValueError("required sanity check failed: DELTA_SIDON(1) != 0")
    if delta_random_sidon[primary_m][1] != 0:
        raise ValueError("required sanity check failed: DELTA_RANDOM_SIDON(1) != 0")

    ladder_gt1 = [k for k in ladder if k != 1]

    q1_classification = _classify_by_signs(
        [delta_random_b[primary_m][k] for k in ladder_gt1],
        "T539_ARM_B_OUTPERFORMS_RANDOM",
        "T539_ARM_B_DOES_NOT_OUTPERFORM_RANDOM",
        "T539_ARM_B_MIXED_BY_EXPOSURE",
    )
    q2_classification = _classify_by_signs(
        [delta_sidon[primary_m][k] for k in ladder_gt1],
        "T539_ARM_B_EXCEEDS_SIDON_GAIN",
        "T539_ARM_B_DOES_NOT_EXCEED_SIDON_GAIN",
        "T539_ARM_B_MIXED_VS_SIDON",
    )
    q3_classification = (
        "CONSISTENT_WITH_B649"
        if q2_classification == "T539_ARM_B_EXCEEDS_SIDON_GAIN"
        else "DIRECTION_INCONSISTENT_WITH_B649"
    )

    t539_replication_supported = (
        q1_classification == "T539_ARM_B_OUTPERFORMS_RANDOM"
        and q2_classification == "T539_ARM_B_EXCEEDS_SIDON_GAIN"
        and q3_classification == "CONSISTENT_WITH_B649"
    )
    t539_replication_status = (
        "T539_REPLICATION_SUPPORTED" if t539_replication_supported else "NOT_SUPPORTED"
    )
    p638_native_replication_candidate = "YES" if t539_replication_supported else "NO"

    geometry_b = {k: geometry_metrics(pool_size, portfolio_b[k]) for k in ladder}

    def _q_out(q: dict[int, dict[int, Fraction]]) -> dict[str, dict[str, Any]]:
        return {str(m): {str(k): _fraction_entry(q[m][k]) for k in ladder} for m in thresholds}

    def _delta_out(delta: dict[int, dict[int, Fraction]]) -> dict[str, dict[str, Any]]:
        return {str(m): {str(k): _fraction_entry(delta[m][k]) for k in ladder} for m in thresholds}

    return {
        "matrix_variant_id": locked["matrix_variant_id"],
        "hypothesis_family_id": locked["hypothesis_family_id"],
        "lottery_type": locked["lottery_type"],
        "preregistration_hash_sha256": canonical_json.sha256_hex(
            canonical_json.canonical_bytes(locked)
        ),
        "total_draws_enumerated": total_draws,
        "primary_event_minimum_matches": primary_m,
        "secondary_event_minimum_matches": secondary_m,
        "exposure_ladder": ladder,
        "sanity_check_delta_random_b_at_k1_is_exactly_zero": True,
        "sanity_check_delta_sidon_at_k1_is_exactly_zero": True,
        "sanity_check_delta_random_sidon_at_k1_is_exactly_zero": True,
        "arm_a_identity_check_vs_sealed_coverage_cell": (
            arm_a_identity_check_vs_sealed_coverage_cell
        ),
        "q": {"a": _q_out(q_a), "b": _q_out(q_b), "c": _q_out(q_c)},
        "delta_random_b": _delta_out(delta_random_b),
        "delta_random_sidon": _delta_out(delta_random_sidon),
        "delta_sidon": _delta_out(delta_sidon),
        "q1_classification": q1_classification,
        "q2_classification": q2_classification,
        "q3_classification": q3_classification,
        "t539_replication_status": t539_replication_status,
        "p638_native_replication_candidate": p638_native_replication_candidate,
        "geometry": {"b": {str(k): geometry_b[k] for k in ladder}},
        "runtime_seconds": runtime,
        "peak_memory_bytes": peak_memory_bytes,
        "scope": {
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "p638": "NOT_RUN",
            "b649": "NOT_RERUN",
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
    print(f"q1_classification: {result['q1_classification']}")
    print(f"q2_classification: {result['q2_classification']}")
    print(f"q3_classification: {result['q3_classification']}")
    print(f"t539_replication_status: {result['t539_replication_status']}")
    print(f"p638_native_replication_candidate: {result['p638_native_replication_candidate']}")
    print(f"total runtime: {result['runtime_seconds']['total_seconds']:.1f}s")
    print(f"peak memory: {result['peak_memory_bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
