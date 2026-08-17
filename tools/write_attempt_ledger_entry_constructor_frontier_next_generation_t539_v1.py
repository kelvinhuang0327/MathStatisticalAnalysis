"""Write the single attempt-ledger record after the locked T539 result exists."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-t539-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-t539-v1-attempt-ledger.json"
)
PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-t539-v1-preregistration-hash.json"
)


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    prereg_record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_hash = hashlib.sha256(canonical).hexdigest()
    entry: dict[str, Any] = {
        "attempt_id": (
            "STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1__ATTEMPT_1"
        ),
        "design_version": "V1",
        "hypothesis_family_id": "DIVERSIFICATION",
        "invalidated_reason": None,
        "lock_existed_before_native_q_e": True,
        "preregistration_hash_sha256": prereg_record["preregistration_hash_sha256"],
        "record_state": "SEALED",
        "result_hash_sha256": result_hash,
        "sealed_at": datetime.now(UTC).isoformat(),
        "sequence": 1,
        "study_id": result["study_id"],
        "supersedes_attempt_id": None,
        "task_id": "STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1",
    }
    serialized = json.dumps({"attempts": [entry]}, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"result_hash_sha256={result_hash}")


if __name__ == "__main__":
    main()
