"""Execute the locked B649 next-generation constructor study.

Re-verifies the LCJ-1 lock hash before generating any native candidate
portfolio or inspecting `Q_E`. Arm-C is loaded only as sealed exact
coverages. T539 and P638 are not constructed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import resource
import subprocess
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research.cyclic_sidon_shift import SIDON_BASE_SET_0_INDEXED, sidon_shift_portfolio
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)
from lottolab.research.low_overlap_geometry_mechanism import (
    portfolio_geometry,
    s2_from_ticket_pair_intersection_histogram,
)

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-v1-preregistration-hash.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/constructor-frontier-next-generation-v1-result.json"
)

Ticket = tuple[int, ...]


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError("preregistration hash mismatch -- refusing to execute")
    return locked


def _git_blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _worktree_blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "hash-object", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_lock_inputs(locked: dict[str, Any]) -> None:
    if list(SIDON_BASE_SET_0_INDEXED) != locked["sidon_base_set_0_indexed"]:
        raise ValueError("Sidon base set drifted from the lock")
    frontier_path = locked["sealed_frontier_result_path"]
    if _git_blob(frontier_path) != locked["sealed_frontier_result_blob_sha1"]:
        raise ValueError("sealed Arm-C frontier artifact drifted from the lock")
    for entry in locked["design_file_blobs"]:
        if _worktree_blob(entry["path"]) != entry["blob"]:
            raise ValueError(f"design file drifted from lock: {entry['path']}")


def parse_fraction(text: str) -> Fraction:
    return Fraction(text)


def rational(value: Fraction) -> dict[str, Any]:
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def optional_ratio(numerator: Fraction, denominator: Fraction) -> Fraction | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def ticket_bitmask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def portfolio_sha256(portfolio: tuple[Ticket, ...]) -> str:
    payload = json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_portfolio(
    portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int, ticket_count: int
) -> None:
    if len(portfolio) != ticket_count:
        raise ValueError(f"expected {ticket_count} tickets, got {len(portfolio)}")
    seen: set[Ticket] = set()
    for ticket in portfolio:
        if len(ticket) != draw_size or len(set(ticket)) != draw_size:
            raise ValueError("illegal ticket shape")
        if tuple(sorted(ticket)) != ticket:
            raise ValueError("tickets must be ascending")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError("ticket number out of range")
        if ticket in seen:
            raise ValueError("duplicate ticket")
        seen.add(ticket)


def multiplicity_prefix_counts(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    ladder: tuple[int, ...],
    portfolios: dict[str, tuple[Ticket, ...]],
) -> dict[str, dict[int, list[int]]]:
    max_k = max(ladder)
    ladder_set = set(ladder)
    masks = {
        arm: tuple(ticket_bitmask(ticket) for ticket in portfolio)
        for arm, portfolio in portfolios.items()
    }
    counts: dict[str, dict[int, list[int]]] = {
        arm: {k: [0] * (k + 1) for k in ladder} for arm in portfolios
    }
    for winner in itertools.combinations(range(1, pool_size + 1), draw_size):
        winner_mask = ticket_bitmask(winner)
        for arm, arm_masks in masks.items():
            hits = 0
            for index in range(1, max_k + 1):
                if (winner_mask & arm_masks[index - 1]).bit_count() >= minimum_matches:
                    hits += 1
                if index in ladder_set:
                    counts[arm][index][hits] += 1
    return counts


def covered_from_counts(counts: list[int]) -> int:
    return sum(counts[1:])


def geometry_payload(
    portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int, minimum_matches: int
) -> dict[str, Any]:
    geometry = portfolio_geometry(portfolio, pool_size, draw_size)
    histogram = {
        int(size): int(count) for size, count in geometry.ticket_pair_intersection_histogram
    }
    overlap_one = histogram.get(1, 0)
    s2 = s2_from_ticket_pair_intersection_histogram(
        pool_size, draw_size, minimum_matches, histogram
    )
    return {
        "duplicate_count": geometry.duplicate_count,
        "max_pairwise_overlap": geometry.max_pairwise_overlap,
        "mean_pairwise_overlap": rational(geometry.mean_pairwise_overlap),
        "overlap_one_pair_count": overlap_one,
        "pair_intersection_histogram": {
            str(size): count for size, count in sorted(histogram.items())
        },
        "per_number_reuse_vector": list(geometry.per_number_reuse_vector),
        "reuse_dispersion_float": geometry.reuse_dispersion,
        "reuse_dispersion_population_variance": rational(
            geometry.reuse_dispersion_population_variance
        ),
        "s2_geometry": s2,
        "unique_number_coverage": geometry.unique_number_coverage,
    }


def evaluate_b649_advance_gate(
    ladder: list[int],
    q_e: dict[int, Fraction],
    q_b: dict[int, Fraction],
    q_d: dict[int, Fraction],
    q_c: dict[int, Fraction],
    duplicate_counts: dict[int, int],
) -> dict[str, Any]:
    gt1 = [k for k in ladder if k > 1]
    clauses = {
        "q_e_gt_q_d_for_every_k_gt_1": all(q_e[k] > q_d[k] for k in gt1),
        "q_e_ge_q_b_for_every_k_gt_1": all(q_e[k] >= q_b[k] for k in gt1),
        "q_e_gt_q_b_at_k_10_15_20": all(q_e[k] > q_b[k] for k in (10, 15, 20)),
        "duplicate_count_eq_0": all(duplicate_counts[k] == 0 for k in ladder),
    }
    gap_20 = optional_ratio(q_e[20] - q_b[20], q_c[20] - q_b[20])
    clauses["b_to_c_gap_capture_20_ge_1_over_4"] = gap_20 is not None and gap_20 >= Fraction(1, 4)
    passed = all(clauses.values())
    return {
        "clauses": clauses,
        "passed": passed,
        "classification": (
            "B649_NEXT_GEN_CONSTRUCTOR_ADVANCE" if passed else "DO_NOT_ADVANCE_THIS_EXACT_VARIANT"
        ),
        "cross_lottery_replication_eligible": passed,
    }


def load_sealed_q(locked: dict[str, Any], arm_key: str) -> dict[int, Fraction]:
    ladder: list[int] = locked["exposure_ladder"]
    values: list[str] = locked[arm_key]
    if len(values) != len(ladder):
        raise ValueError(f"{arm_key} length does not match the locked ladder")
    return {k: parse_fraction(text) for k, text in zip(ladder, values, strict=True)}


def verify_sealed_frontier_file(locked: dict[str, Any]) -> None:
    payload = json.loads(Path(locked["sealed_frontier_result_path"]).read_text(encoding="utf-8"))
    locked_hash = locked["sealed_frontier_preregistration_hash_sha256"]
    if payload["preregistration_hash_sha256"] != locked_hash:
        raise ValueError("sealed frontier preregistration hash drifted")
    for arm, key in (
        ("a", "sealed_q_a"),
        ("b", "sealed_q_b"),
        ("c", "sealed_q_c"),
        ("d", "sealed_q_d"),
    ):
        locked_map = load_sealed_q(locked, key)
        for k, expected in locked_map.items():
            actual = parse_fraction(payload["q"][arm]["3"][str(k)]["exact"])
            if actual != expected:
                raise ValueError(f"sealed {arm} Q({k}) drifted from the lock")


def run(locked: dict[str, Any]) -> dict[str, Any]:
    verify_lock_inputs(locked)
    verify_sealed_frontier_file(locked)

    pool_size = int(locked["pool_size"])
    draw_size = int(locked["draw_size"])
    minimum_matches = int(locked["primary_event_minimum_matches"])
    ladder = [int(k) for k in locked["exposure_ladder"]]
    max_k = max(ladder)

    sealed_a = load_sealed_q(locked, "sealed_q_a")
    sealed_b = load_sealed_q(locked, "sealed_q_b")
    sealed_c = load_sealed_q(locked, "sealed_q_c")
    sealed_d = load_sealed_q(locked, "sealed_q_d")

    runtime: dict[str, Any] = {}
    t_start = time.perf_counter()

    t0 = time.perf_counter()
    sidon_full = sidon_shift_portfolio(max_k)
    runtime["arm_a_seconds"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    arm_b_full = greedy_min_overlap_portfolio(pool_size, draw_size, max_k)
    runtime["arm_b_seconds"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    arm_e_full = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, max_k)
    runtime["arm_e_seconds"] = time.perf_counter() - t0

    validate_portfolio(sidon_full, pool_size, draw_size, max_k)
    validate_portfolio(arm_b_full, pool_size, draw_size, max_k)
    validate_portfolio(arm_e_full, pool_size, draw_size, max_k)

    disjoint_capacity = pool_size // draw_size
    if arm_e_full[:disjoint_capacity] != arm_b_full[:disjoint_capacity]:
        raise ValueError("candidate/Arm-B disjoint-prefix identity failed")

    portfolios = {"a": sidon_full, "b": arm_b_full, "e": arm_e_full}
    t0 = time.perf_counter()
    counts = multiplicity_prefix_counts(
        pool_size, draw_size, minimum_matches, tuple(ladder), portfolios
    )
    runtime["winning_space_seconds"] = time.perf_counter() - t0
    runtime["total_seconds"] = time.perf_counter() - t_start
    runtime["peak_memory_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    total_draws = math.comb(pool_size, draw_size)
    q_measured: dict[str, dict[int, Fraction]] = {}
    for arm in ("a", "b", "e"):
        q_measured[arm] = {}
        for k in ladder:
            if sum(counts[arm][k]) != total_draws:
                raise ValueError(f"N_c for arm {arm} k={k} does not sum to C(n,d)")
            q_measured[arm][k] = Fraction(covered_from_counts(counts[arm][k]), total_draws)

    q_d = {
        k: exact_random_portfolio_coverage(pool_size, draw_size, minimum_matches, k) for k in ladder
    }
    for k in ladder:
        if q_measured["a"][k] != sealed_a[k]:
            raise ValueError(f"measured Q_A({k}) does not match sealed Sidon")
        if q_measured["b"][k] != sealed_b[k]:
            raise ValueError(f"measured Q_B({k}) does not match sealed Arm-B")
        if q_d[k] != sealed_d[k]:
            raise ValueError(f"measured Q_D({k}) does not match sealed random expected")

    if q_measured["e"][1] != q_measured["b"][1]:
        raise ValueError("k=1 identity failed: Q_E(1) != Q_B(1)")

    per_k: dict[str, Any] = {}
    duplicate_counts: dict[int, int] = {}
    for k in ladder:
        prefix_a = sidon_full[:k]
        prefix_b = arm_b_full[:k]
        prefix_e = arm_e_full[:k]
        if prefix_a != sidon_full[:k] or prefix_b != arm_b_full[:k] or prefix_e != arm_e_full[:k]:
            raise ValueError("prefix reconstruction failed")
        geom_e = geometry_payload(prefix_e, pool_size, draw_size, minimum_matches)
        geom_b = geometry_payload(prefix_b, pool_size, draw_size, minimum_matches)
        geom_a = geometry_payload(prefix_a, pool_size, draw_size, minimum_matches)
        duplicate_counts[k] = int(geom_e["duplicate_count"])
        q_e = q_measured["e"][k]
        q_b = q_measured["b"][k]
        q_a = q_measured["a"][k]
        q_c = sealed_c[k]
        capture = optional_ratio(q_e - q_d[k], q_c - q_d[k])
        gap = optional_ratio(q_e - q_b, q_c - q_b)
        per_k[str(k)] = {
            "b_to_c_gap_capture": None if gap is None else rational(gap),
            "delta_e_vs_b": rational(q_e - q_b),
            "delta_e_vs_d": rational(q_e - q_d[k]),
            "frontier_capture_ratio_e": None if capture is None else rational(capture),
            "geometry": {"a": geom_a, "b": geom_b, "e": geom_e},
            "q_a": rational(q_a),
            "q_b": rational(q_b),
            "q_c_sealed": rational(q_c),
            "q_d": rational(q_d[k]),
            "q_e": rational(q_e),
            "redundancy_e": int(
                sum(index * count for index, count in enumerate(counts["e"][k]))
                - covered_from_counts(counts["e"][k])
            ),
        }

    gate = evaluate_b649_advance_gate(
        ladder, q_measured["e"], q_measured["b"], q_d, sealed_c, duplicate_counts
    )

    return {
        "arm_c_rerun": "NO",
        "b649_advance_gate": gate,
        "canonical_input": {
            "commit": locked["canonical_input_commit"],
            "design_source_commit": locked["design_source_commit"],
            "locked_preregistration_path": str(PREREGISTRATION_HASH_PATH),
            "locked_preregistration_sha256": canonical_json.sha256_hex(
                canonical_json.canonical_bytes(locked)
            ),
            "sealed_frontier_result_blob": locked["sealed_frontier_result_blob_sha1"],
            "tree": locked["canonical_input_tree"],
        },
        "constructor_id": locked["constructor_id"],
        "cross_lottery_replication_eligible": gate["cross_lottery_replication_eligible"],
        "evidence_type": "EXACT_COMBINATORIAL",
        "execution_classification": gate["classification"],
        "exposure_ladder": ladder,
        "global_optimum_status": "UNKNOWN",
        "lottery_type": "BIG_LOTTO",
        "monte_carlo": False,
        "p638_execution": "NOT_RUN",
        "parameter_rescue_run": "NO",
        "per_k": per_k,
        "portfolio_sha256": {
            "a": portfolio_sha256(sidon_full),
            "b": portfolio_sha256(arm_b_full),
            "e": portfolio_sha256(arm_e_full),
        },
        "primary_event_minimum_matches": minimum_matches,
        "runtime": runtime,
        "scope": {
            "arm_c_rerun": "NOT_RUN",
            "historical_draws_read": False,
            "monte_carlo": False,
            "p638_zone2": "NOT_RUN",
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "secondary_events": "NOT_RUN",
            "t539": "NOT_RUN",
        },
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "study_id": locked["study_id"],
        "t539_execution": "NOT_RUN",
    }


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"execution_classification={result['execution_classification']}")
    print(f"cross_lottery_replication_eligible={result['cross_lottery_replication_eligible']}")


if __name__ == "__main__":
    main()
