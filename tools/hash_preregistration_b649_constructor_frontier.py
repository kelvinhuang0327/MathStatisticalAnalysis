"""Compute and record the locked preregistration hash for

DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1
(STRATEGY_MATRIX_PHASE5_B649_CONSTRUCTOR_FRONTIER_LOCK_EXECUTE_R1). Run once,
at lock time, before any real B649-scale constructor or optimizer call.
`LOCKED_PARAMETERS` is the single source of truth
`run_diversification_constructor_frontier_b649_v1.py` imports its constants
from -- never redefined a second time, so what gets hashed and what gets run
cannot drift apart. Mirrors `hash_preregistration_p638.py` /
`hash_preregistration_t539.py`'s pattern, extended with this experiment's
frozen arms and optimizer budget (Owner authorization
`AUTHORIZE_STRATEGY_MATRIX_PHASE5_B649_CONSTRUCTOR_FRONTIER_LOCK_EXECUTE_R1`).

The classification rule, frontier-nearness margin (0.90), and
replication-eligibility rule are frozen already by
`docs/research/strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
(commit 971b97b, immutable) and are not re-hashed here, matching the
precedent set by the sealed B649/T539/P638-Zone1 diversification-coverage
locks: this file locks only the execution-time parameters that could vary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "diversification-constructor-frontier-b649-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "matrix_variant_id": "DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1",
    "hypothesis_family_id": "DIVERSIFICATION",
    "lottery_type": "BIG_LOTTO",
    "pool_size": 49,
    "draw_size": 6,
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "secondary_event_minimum_matches": [4, 5, 6],
    "sidon_base_set_0_indexed": [0, 1, 3, 7, 12, 20],
    "sidon_mode": "NESTED_PREFIX",
    "optimizer_mode": "INDEPENDENT_PER_K",
    "arm_a_constructor_id": "CYCLIC_SIDON_SHIFT_B649_V1",
    "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1",
    "arm_c_constructor_id": "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1",
    "arm_d_constructor_id": "RANDOM_EXPECTED_COVERAGE",
    "arm_a_mutation": "none",
    "arm_d_mutation": "none",
    "optimizer_objective_minimum_matches": 3,
    "optimizer_seed": 20260815,
    "optimizer_restart_count": 5,
    "optimizer_candidate_sample_size": 60,
    "optimizer_max_swap_passes": 3,
    "optimizer_max_candidate_evaluations_total_ladder": 65610,
    "optimizer_budget_class": "MODERATE",
    "evaluator_id": "EXACT_COVERAGE_FAST_EVALUATOR_C7E3B4A",
    "evaluator_no_approximation": True,
    "evaluator_no_monte_carlo": True,
    "cache_clear_between_swap_slots": True,
    "cache_clear_between_restarts": True,
    "cache_clear_between_construction_steps": True,
    "cache_policy_result_dependent": False,
    "duplicate_tickets_invariant": 0,
    "global_optimum_status": "UNKNOWN",
}


def main() -> None:
    digest = canonical_json.sha256_hex(canonical_json.canonical_bytes(LOCKED_PARAMETERS))
    record = {
        "matrix_variant_id": LOCKED_PARAMETERS["matrix_variant_id"],
        "locked_parameters": LOCKED_PARAMETERS,
        "preregistration_hash_sha256": digest,
        "hash_method": "LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(record, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"preregistration_hash_sha256={digest}")


if __name__ == "__main__":
    main()
