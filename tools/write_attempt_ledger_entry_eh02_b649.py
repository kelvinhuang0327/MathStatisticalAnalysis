"""Write the attempt-ledger record for the EH02 B649 cross-lottery TE experiment.

Mirrors `write_attempt_ledger_entry_eh01_eh10_b649.py` exactly, extended to
two sealed rows (one per edge) sharing the same task/preregistration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULT_PATH = Path(
    "docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "eh02-b649-cross-lottery-transfer-entropy-v1-attempt-ledger.json"
)
TASK_ID = "EXPERIMENT_H02_V1_LOCK_EXECUTE_R1"


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_hash = hashlib.sha256(canonical).hexdigest()
    sealed_at = datetime.now(UTC).isoformat()

    attempts: list[dict[str, Any]] = [
        {
            "attempt_id": f"{result['variant_id']}__EDGE_1_T539_TO_B649__ATTEMPT_1",
            "sequence": 1,
            "task_id": TASK_ID,
            "hypothesis_family_id": "TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH",
            "matrix_variant_id": result["variant_id"],
            "edge_id": "T539_TO_B649",
            "lottery_type": "BIG_LOTTO",
            "design_version": "V1",
            "record_state": "SEALED",
            "descriptive_classification": result["edge_1_t539_to_b649"]["classification"],
            "preregistration_hash_sha256": result["preregistration_hash_sha256"],
            "result_hash_sha256": result_hash,
            "invalidated_reason": None,
            "supersedes_attempt_id": None,
            "sealed_at": sealed_at,
        },
        {
            "attempt_id": f"{result['variant_id']}__EDGE_2_P638Z1_TO_B649__ATTEMPT_1",
            "sequence": 1,
            "task_id": TASK_ID,
            "hypothesis_family_id": "TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH",
            "matrix_variant_id": result["variant_id"],
            "edge_id": "P638Z1_TO_B649",
            "lottery_type": "BIG_LOTTO",
            "design_version": "V1",
            "record_state": "SEALED",
            "descriptive_classification": result["edge_2_p638z1_to_b649"]["classification"],
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
