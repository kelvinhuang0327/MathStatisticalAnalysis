"""Write the single attempt-ledger record for the P638 Zone-1 diversification experiment.

Mirrors `write_attempt_ledger_entry_t539.py` exactly. `result_hash_sha256`
uses plain JSON canonicalization (sorted keys, SHA-256), not LCJ-1: this
result blob legitimately contains floats (reported alongside exact
fraction strings), which LCJ-1 forbids by design for the strict,
integer-only `locked_parameters` document.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-attempt-ledger.json"
)


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_hash = hashlib.sha256(canonical).hexdigest()

    entry: dict[str, Any] = {
        "attempt_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__ATTEMPT_1",
        "sequence": 1,
        "task_id": "STRATEGY_MATRIX_PHASE3_P638_DIVERSIFICATION_LOCK_EXECUTE_R1",
        "hypothesis_family_id": result["hypothesis_family_id"],
        "matrix_variant_id": result["matrix_variant_id"],
        "lottery_type": result["lottery_type"],
        "design_version": "V1",
        "record_state": "SEALED",
        "preregistration_hash_sha256": result["preregistration_hash_sha256"],
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
