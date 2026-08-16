"""Write the single attempt-ledger record for HIGHER_ORDER_RESIDUAL_MECHANISM_V1.

Mirrors `write_attempt_ledger_entry_low_overlap_geometry_mechanism_v1.py`
exactly. `result_hash_sha256` uses plain JSON canonicalization (sorted keys,
SHA-256), not LCJ-1: this result blob legitimately contains floats (runtime
seconds), which LCJ-1 forbids by design for the strict, integer-only
`locked_parameters` document.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MATRIX_RESULTS = "docs/research/matrix-native-results/"
RESULT_PATH = Path(_MATRIX_RESULTS + "higher-order-residual-mechanism-v1-result.json")
OUTPUT_PATH = Path(_MATRIX_RESULTS + "higher-order-residual-mechanism-v1-attempt-ledger.json")
PREREGISTRATION_HASH_PATH = Path(
    _MATRIX_RESULTS + "higher-order-residual-mechanism-v1-preregistration-hash.json"
)


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    prereg_record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_hash = hashlib.sha256(canonical).hexdigest()

    entry: dict[str, Any] = {
        "attempt_id": "STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1__ATTEMPT_1",
        "sequence": 1,
        "task_id": "STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_LOCK_EXECUTE_R1",
        "hypothesis_family_id": "DIVERSIFICATION",
        "study_id": result["study_id"],
        "design_version": "V1",
        "record_state": "SEALED",
        "preregistration_hash_sha256": prereg_record["preregistration_hash_sha256"],
        "result_hash_sha256": result_hash,
        "invalidated_reason": None,
        "supersedes_attempt_id": None,
        "sealed_at": datetime.now(UTC).isoformat(),
    }
    serialized = json.dumps({"attempts": [entry]}, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"result_hash_sha256={result_hash}")


if __name__ == "__main__":
    main()
