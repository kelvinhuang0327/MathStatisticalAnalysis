"""Compute and record the locked preregistration hash for

GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1
(STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1). Run
once, at lock time, before any real P638 Zone-1-scale constructor call or
winning-space enumeration against arm B. `LOCKED_PARAMETERS` is the single
source of truth `run_greedy_min_overlap_constructor_p638_zone1_v1.py`
imports its constants from -- never redefined a second time, so what gets
hashed and what gets run cannot drift apart. Mirrors
`hash_preregistration_t539_arm_b.py` (arm-B lock shape) and
`hash_preregistration_p638.py` (this lottery's own `zone` key), combined:
this experiment has no optimizer arm (B649 arm C, the bounded search, is
out-of-scope per the Owner packet), so no seed/restart/candidate/swap-pass
budget or fast-evaluator identity is locked here -- coverage is computed via
the same single-pass earliest-index enumeration method
`run_diversification_coverage_t539_v1.py` / the sealed P638 Zone-1 Sidon
cell already use, not a new evaluator.

The geometry metric definitions and classification/replication rules are
already frozen by
`docs/research/strategy-matrix-phase5-p638-non-sidon-low-overlap-native-design-r1.md`
(commit 9b60007, design-only) and are not re-hashed here, matching the
precedent set by the sealed T539 arm-B lock: this file locks only the
execution-time parameters that could vary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "greedy-min-overlap-constructor-p638-zone1-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "matrix_variant_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
    "hypothesis_family_id": "DIVERSIFICATION",
    "lottery_type": "POWER_LOTTO",
    "zone": "zone1",
    "pool_size": 38,
    "draw_size": 6,
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "secondary_event_minimum_matches": [4, 5, 6],
    "sidon_base_set_0_indexed": [0, 1, 3, 7, 17, 30],
    "portfolio_mode": "NESTED_PREFIX",
    "arm_a_constructor_id": "CYCLIC_SIDON_SHIFT_P638_ZONE1_V1",
    "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
    "arm_c_constructor_id": "RANDOM_EXPECTED_COVERAGE",
    "arm_a_mutation": "none",
    "arm_b_mutation": "none",
    "arm_c_mutation": "none",
    "duplicate_tickets_invariant": 0,
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
