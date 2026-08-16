"""Write the attempt-ledger record for the EH01/EH10 B649 experiment.

Mirrors `write_attempt_ledger_entry_greedy_min_overlap_constructor_p638_zone1.py`
exactly, extended to two sealed rows (one per hypothesis) sharing the same
task/preregistration since both were locked and executed together.
`result_hash_sha256` uses plain JSON canonicalization (sorted keys,
SHA-256), not LCJ-1: this result blob legitimately contains floats, which
LCJ-1 forbids by design for the strict, integer-only `locked_parameters`
document.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULT_PATH = Path(
    "docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-attempt-ledger.json"
)
TASK_ID = "B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1"


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_hash = hashlib.sha256(canonical).hexdigest()
    sealed_at = datetime.now(UTC).isoformat()

    attempts: list[dict[str, Any]] = [
        {
            "attempt_id": f"{result['eh01_variant_id']}__ATTEMPT_1",
            "sequence": 1,
            "task_id": TASK_ID,
            "hypothesis_family_id": "HIGHER_ORDER_TEMPORAL_STRUCTURE",
            "matrix_variant_id": result["eh01_variant_id"],
            "lottery_type": "BIG_LOTTO",
            "design_version": "V1",
            "record_state": "SEALED",
            "descriptive_classification": result["eh01"]["classification"],
            "preregistration_hash_sha256": result["preregistration_hash_sha256"],
            "result_hash_sha256": result_hash,
            "invalidated_reason": None,
            "supersedes_attempt_id": None,
            "sealed_at": sealed_at,
        },
        {
            "attempt_id": f"{result['eh10_variant_id']}__ATTEMPT_1",
            "sequence": 1,
            "task_id": TASK_ID,
            "hypothesis_family_id": "HIGHER_ORDER_TEMPORAL_STRUCTURE",
            "matrix_variant_id": result["eh10_variant_id"],
            "lottery_type": "BIG_LOTTO",
            "design_version": "V1",
            "record_state": "SEALED",
            "descriptive_classification": result["eh10"]["classification"],
            "preregistration_hash_sha256": result["preregistration_hash_sha256"],
            "result_hash_sha256": result_hash,
            "invalidated_reason": None,
            "supersedes_attempt_id": None,
            "sealed_at": sealed_at,
        },
    ]
    serialized = json.dumps({"attempts": attempts}, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"result_hash_sha256={result_hash}")


if __name__ == "__main__":
    main()
