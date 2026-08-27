"""Execute Strategy Matrix Phase 9: Reference E Exact 1-Exchange Discovery on B649.

Exhaustively evaluates every legal 1-number-exchange neighbor of sealed Method E
(``GREEDY_MINMAX_THEN_SUM_OVERLAP_V1``) at exposure rungs k=10, 15, 20 for B649
(pool_size=49, draw_size=6, primary_event=M3_PLUS).

Verifies sealed Method E identity before evaluating any native neighbor.
Outputs exact combinatorial results to
`docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json`.
"""

from __future__ import annotations

import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    evaluate_one_exchange_neighborhood,
)

PREREGISTRATION_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-preregistration.md"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json"
)

LOCKED_PREREGISTRATION_SHA256 = (
    "68b25e8e2c7ee82d2f6c035003a3d21f67c649b00c465345e5d85423b377eb8d"
)
SEALED_METHOD_E_20_SHA256 = (
    "ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff"
)
SEALED_Q_E: dict[int, Fraction] = {
    10: Fraction(212295, 1165318),
    15: Fraction(927161, 3495954),
    20: Fraction(17379, 50666),
}

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]


def rational(value: Fraction) -> dict[str, Any]:
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def portfolio_sha256(portfolio: Portfolio) -> str:
    payload = json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_preregistration_lock() -> str:
    if not PREREGISTRATION_PATH.exists():
        raise FileNotFoundError(f"preregistration file missing: {PREREGISTRATION_PATH}")
    content = PREREGISTRATION_PATH.read_bytes()
    computed_hash = hashlib.sha256(content).hexdigest()
    if computed_hash != LOCKED_PREREGISTRATION_SHA256:
        raise ValueError(
            f"preregistration sha256 mismatch: expected {LOCKED_PREREGISTRATION_SHA256}, "
            f"got {computed_hash}"
        )
    return computed_hash


def execute_phase9_discovery() -> dict[str, Any]:
    prereg_sha256 = verify_preregistration_lock()

    pool_size = 49
    draw_size = 6
    minimum_matches = 3
    ladder = [10, 15, 20]
    max_k = max(ladder)

    t_start = time.perf_counter()
    print("Regenerating Method E (GREEDY_MINMAX_THEN_SUM_OVERLAP_V1)...")
    t0 = time.perf_counter()
    method_e_20 = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, max_k)
    method_e_gen_time = time.perf_counter() - t0
    print(f"Method E regenerated in {method_e_gen_time:.2f}s")

    # Verify Method E portfolio identity against Phase-7 sealed authority
    computed_e_sha256 = portfolio_sha256(method_e_20)
    if computed_e_sha256 != SEALED_METHOD_E_20_SHA256:
        raise ValueError(
            f"SEALED_REFERENCE_E_IDENTITY_MISMATCH: expected {SEALED_METHOD_E_20_SHA256}, "
            f"got {computed_e_sha256}"
        )
    print(f"Method E 20-ticket sha256 verified: {computed_e_sha256}")

    per_k_results: dict[str, Any] = {}
    neighbor_counts: dict[str, int] = {}
    delta_vs_e: dict[str, dict[str, Any]] = {}
    q_best: dict[str, dict[str, Any]] = {}
    q_ref: dict[str, dict[str, Any]] = {}
    classifications: dict[str, str] = {}
    best_portfolios_sha256: dict[str, str] = {}
    timing_per_k: dict[str, float] = {}

    for k in ladder:
        print(f"\n--- Evaluating B649 k={k} 1-exchange neighborhood ---")
        t_k = time.perf_counter()
        ref_k = method_e_20[:k]
        ref_sha256 = portfolio_sha256(ref_k)

        res = evaluate_one_exchange_neighborhood(
            pool_size=pool_size,
            draw_size=draw_size,
            minimum_matches=minimum_matches,
            portfolio=ref_k,
        )
        elapsed_k = time.perf_counter() - t_k
        timing_per_k[str(k)] = elapsed_k

        # Verify reference coverage against sealed Phase-7 Q_E
        if res["q_reference"] != SEALED_Q_E[k]:
            raise ValueError(
                f"Q_E({k}) mismatch against sealed authority: expected {SEALED_Q_E[k]}, "
                f"got {res['q_reference']}"
            )

        best_sha256 = portfolio_sha256(res["best_neighbor"])
        k_str = str(k)

        neighbor_counts[k_str] = res["unique_neighbor_count"]
        q_ref[k_str] = rational(res["q_reference"])
        q_best[k_str] = rational(res["q_best_neighbor"])
        delta_vs_e[k_str] = rational(res["delta_vs_reference"])
        classifications[k_str] = res["classification"]
        best_portfolios_sha256[k_str] = best_sha256

        per_k_results[k_str] = {
            "k": k,
            "reference_portfolio_sha256": ref_sha256,
            "q_reference_e": rational(res["q_reference"]),
            "unique_neighbor_count": res["unique_neighbor_count"],
            "best_neighbor_portfolio": [list(t) for t in res["best_neighbor"]],
            "best_neighbor_portfolio_sha256": best_sha256,
            "q_best_neighbor": rational(res["q_best_neighbor"]),
            "delta_vs_reference_e": rational(res["delta_vs_reference"]),
            "classification": res["classification"],
            "evaluation_time_seconds": elapsed_k,
        }

        print(f"k={k}: {res['unique_neighbor_count']} unique neighbors evaluated")
        print(f"  Q_E({k}) = {res['q_reference']} ({float(res['q_reference']):.8f})")
        print(f"  Q_best({k}) = {res['q_best_neighbor']} ({float(res['q_best_neighbor']):.8f})")
        print(f"  Delta = {res['delta_vs_reference']} ({float(res['delta_vs_reference']):.8f})")
        print(f"  Classification: {res['classification']}")
        print(f"  Best neighbor sha256: {best_sha256}")

    total_time = time.perf_counter() - t_start
    peak_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Advance gate: PASS iff at least one tested k has delta_vs_reference_e > 0
    advance_pass = any(
        res["classification"] == "ONE_EXCHANGE_IMPROVEMENT_FOUND"
        for res in per_k_results.values()
    )
    advance_gate_status = "PASS" if advance_pass else "FAIL"

    result_payload: dict[str, Any] = {
        "study_id": "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1",
        "task_id": "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1",
        "owner_authorization": (
            "AUTHORIZE_STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1"
        ),
        "reference_constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
        "candidate_id": "REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1",
        "lottery_type": "BIG_LOTTO",
        "pool_size": pool_size,
        "draw_size": draw_size,
        "primary_event": "M3_PLUS",
        "primary_event_minimum_matches": minimum_matches,
        "exposure_ladder": ladder,
        "canonical_base": {
            "commit": "79948c6ba3b7195b85e11c690c50b70bf185b1d2",
            "tree": "5e5c0c94550c0444ddb1e7ebd994c4223c48ca5a",
        },
        "preregistration": {
            "path": str(PREREGISTRATION_PATH),
            "sha256": prereg_sha256,
        },
        "reference_e_regeneration": {
            "portfolio_20_sha256": computed_e_sha256,
            "matches_sealed_phase7_authority": True,
            "generation_time_seconds": method_e_gen_time,
        },
        "gate": {
            "phase9_advance_gate": advance_gate_status,
            "any_k_delta_gt_0": advance_pass,
            "global_optimum_status": "UNKNOWN",
        },
        "per_k": per_k_results,
        "summary": {
            "classifications": classifications,
            "unique_neighbor_counts": neighbor_counts,
            "q_reference_e": q_ref,
            "q_best_neighbor": q_best,
            "delta_vs_reference_e": delta_vs_e,
            "best_neighbor_portfolio_sha256": best_portfolios_sha256,
        },
        "runtime": {
            "method_e_generation_seconds": method_e_gen_time,
            "neighborhood_evaluation_seconds": timing_per_k,
            "total_elapsed_seconds": total_time,
            "peak_memory_bytes": peak_memory,
        },
        "invariants": {
            "historical_draws_used": False,
            "rng": "NONE",
            "monte_carlo": "NONE",
            "db_access": False,
            "global_optimum_status": "UNKNOWN",
            "runtime_promotion": "NOT_AUTHORIZED",
            "t539_execution": "NOT_RUN",
            "p638_execution": "NOT_RUN",
            "second_exchange_performed": False,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result_payload, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"\nWrote results to {OUTPUT_PATH}")
    print(f"PHASE9_ADVANCE_GATE: {advance_gate_status}")
    print("GLOBAL_OPTIMUM_STATUS: UNKNOWN")

    return result_payload


def main() -> None:
    execute_phase9_discovery()


if __name__ == "__main__":
    main()
