"""Append the sealed DIVERSIFICATION_COVERAGE_T539_V1 cell to the ledger.

Unlike `build_research_ledger.py` (which rebuilds the whole ledger from
every source at once), this appends exactly one new cell to the existing
`cells` array and leaves every other cell -- including
`DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO` -- byte-for-byte unchanged.
An `hypothesis_variant_id` is never edited in place after its outcome was
inspected (see the schema doc's Lifecycle section); this script only
ever adds a new row.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

TODAY = date(2026, 8, 14).isoformat()
LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
RESULT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-t539-v1-result.json"
)
NEW_CELL_ID = "DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539"


def _build_cell() -> dict[str, Any]:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    d3_at_max_k = result["delta"]["3"]["20"]
    return {
        "cell_id": NEW_CELL_ID,
        "hypothesis_family_id": "DIVERSIFICATION",
        "hypothesis_variant_id": "DIVERSIFICATION_COVERAGE_T539_V1",
        "mechanism_class": "STRUCTURAL",
        "mechanism_family": "DIVERSIFICATION",
        "lottery_type": "DAILY_539",
        "zone": None,
        "generation": 1,
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "evidence_type": "EXACT_COMBINATORIAL",
        "uncertainty": "NONE -- exact enumeration / exact closed form",
        "record_state": "SEALED",
        "preregistration_grade": "R1_PREREGISTERED",
        "evidence_grade": "LOCAL_VERIFIED",
        "descriptive_classification": result["descriptive_classification"],
        "decision_state": "REPLICATION_REQUIRED",
        "global_mechanism_status": "RETAIN_AND_REPLICATE",
        "exhausted": False,
        "predictive_advantage": "NOT_TESTED",
        "prize_value_advantage": "NOT_TESTED",
        "economic_optimality": "NOT_TESTED",
        "primary_endpoint_value": d3_at_max_k["float"],
        "primary_endpoint_definition": (
            "D_3(20) = Q_sidon_M3+(20) - Q_random_expected_M3+(20), exact combinatorics, "
            f"exact value {d3_at_max_k['exact']}. Native replication of "
            "DIVERSIFICATION_COVERAGE_B649_V1 into DAILY_539's 5/39 structure; classification "
            "terminology locked correctly from the start, no ledger-layer relabeling needed "
            "(contrast DIVERSIFICATION_COVERAGE_B649_V1's primary_endpoint_definition)."
        ),
        "null_replay_percentile": None,
        "artifact_paths": [
            f"docs/research/matrix-native-results/diversification-coverage-t539-v1-{suffix}"
            for suffix in (
                "preregistration.md",
                "preregistration-hash.json",
                "result.json",
                "attempt-ledger.json",
                "report.md",
            )
        ],
        "related_legacy_evidence": [],
        "retest_eligible": True,
        "retest_triggers": [
            "P638 native replication (dual-zone 6/38 + 1/8 structure) tests whether the "
            "geometric advantage generalizes beyond single-zone pick-m-of-n structures",
            "extending the exposure ladder beyond k=20 to see whether the growing marginal "
            "advantage continues or eventually turns over",
        ],
        "next_priority": "MEDIUM",
        "source_note": (
            "Computed and independently verified in this session (Strategy Matrix Phase 2) "
            "via complete C(39,5) enumeration, exact fractions.Fraction arithmetic, no "
            "simulation. Native replication cell: independently derived and independently "
            "verified Sidon base set in Z_39, not copied from B649's base set (see "
            "diversification-coverage-t539-v1-preregistration.md Sec 3 for the wording "
            "correction on that point). Makes no predictive-advantage or prize-value claim."
        ),
        "last_reviewed_at": TODAY,
    }


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    existing_ids = {cell["cell_id"] for cell in ledger["cells"]}
    if NEW_CELL_ID in existing_ids:
        raise ValueError(f"{NEW_CELL_ID} is already present in the ledger -- refusing to duplicate")

    ledger["cells"].append(_build_cell())
    ledger["generated_at"] = TODAY

    serialized = json.dumps(ledger, indent=2, sort_keys=True).rstrip("\n") + "\n"
    LEDGER_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {LEDGER_PATH}: {len(ledger['cells'])} cells (added {NEW_CELL_ID})")


if __name__ == "__main__":
    main()
