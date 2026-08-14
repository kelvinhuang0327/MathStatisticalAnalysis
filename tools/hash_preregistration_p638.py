"""Compute and record the locked preregistration hash for

DIVERSIFICATION_COVERAGE_P638_ZONE1_V1. Run once, at lock time, before any
winning-space enumeration is performed. `LOCKED_PARAMETERS` is the single
source of truth the execution script imports its constants from -- never
redefined a second time, so there is no way for what gets hashed and what
gets run to drift apart. Mirrors `hash_preregistration_t539.py` exactly,
parameters substituted for POWER_LOTTO Zone-1's native 6/38 structure.
Zone-2 (1-of-8) is out of scope entirely; it is not represented here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "matrix_variant_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1",
    "hypothesis_family_id": "DIVERSIFICATION",
    "lottery_type": "POWER_LOTTO",
    "zone": "zone1",
    "pool_size": 38,
    "draw_size": 6,
    "sidon_base_set_0_indexed": [0, 1, 3, 7, 17, 30],
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "secondary_event_minimum_matches": [4, 5, 6],
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
