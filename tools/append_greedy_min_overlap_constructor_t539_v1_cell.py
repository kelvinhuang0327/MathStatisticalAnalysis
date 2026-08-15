"""Append the sealed GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 cell to the ledger.

Unlike `build_research_ledger.py` (which rebuilds the whole ledger from
every source at once), this appends exactly one new cell to the existing
`cells` array and leaves every other cell -- including
`DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO` and
`DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539` -- byte-for-byte unchanged.
An `hypothesis_variant_id` is never edited in place after its outcome was
inspected (see the schema doc's Lifecycle section); this script only ever
adds a new row. Mirrors `append_diversification_coverage_t539_v1_cell.py`
and `append_diversification_coverage_p638_zone1_v1_cell.py`.

This cell is the T539-native replication of
`DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO` (Strategy Matrix
Phase 5, Generation 2): the design (94aa504) confirmed no B649-specific
constant is required, so this is a native parameter-substitution instance
of the same mechanism, not a new algorithm -- `generation: 2` here matches
that B649 sibling, not the Generation-1 Sidon-coverage cells.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

TODAY = date(2026, 8, 15).isoformat()
LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
RESULT_PATH = Path(
    "docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-result.json"
)
NEW_CELL_ID = "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1__DAILY_539"


def _build_cell() -> dict[str, Any]:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    delta_sidon_20 = result["delta_sidon"]["3"]["20"]
    delta_random_b_20 = result["delta_random_b"]["3"]["20"]
    return {
        "cell_id": NEW_CELL_ID,
        "hypothesis_family_id": "DIVERSIFICATION",
        "hypothesis_variant_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1",
        "mechanism_class": "STRUCTURAL",
        "mechanism_family": "DIVERSIFICATION",
        "lottery_type": "DAILY_539",
        "zone": None,
        "generation": 2,
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "evidence_type": "EXACT_COMBINATORIAL",
        "uncertainty": "NONE -- exact enumeration / exact closed form",
        "record_state": "SEALED",
        "preregistration_grade": "R1_PREREGISTERED",
        "evidence_grade": "LOCAL_VERIFIED",
        "descriptive_classification": "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE",
        "decision_state": "REPLICATION_REQUIRED",
        "global_mechanism_status": "RETAIN_AND_REPLICATE",
        "exhausted": False,
        "predictive_advantage": "NOT_TESTED",
        "prize_value_advantage": "NOT_TESTED",
        "economic_optimality": "NOT_TESTED",
        "primary_endpoint_value": delta_sidon_20["float"],
        "primary_endpoint_definition": (
            "DELTA_SIDON(20) = Q_greedy_M3+(20) - Q_sidon_M3+(20), exact combinatorics via "
            f"complete C(39,5)=575,757 enumeration, exact value {delta_sidon_20['exact']}. "
            "Q2 requires DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}: TRUE -> "
            "T539_ARM_B_EXCEEDS_SIDON_GAIN -- arm B (greedy, non-Sidon) not only reproduces "
            "but exceeds T539's own sealed Sidon-shift gain over random at every tested k>1, "
            "matching B649's own constructor-frontier finding in direction "
            "(CONSISTENT_WITH_B649). DELTA_RANDOM_B(20) (arm B vs. random, Q1) = "
            f"{delta_random_b_20['exact']} ({delta_random_b_20['float']:+.8f}), also > 0 at "
            "every k>1 -> T539_ARM_B_OUTPERFORMS_RANDOM."
        ),
        "null_replay_percentile": None,
        "artifact_paths": [
            f"docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-{suffix}"
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
            "a richer optimizer arm (e.g. a bounded seeded search analogous to B649's "
            "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1) is run at T539 scale to test "
            "whether an even larger gap over Sidon exists",
            "P638 native replication of GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1/B649_V1 tests "
            "whether this mechanism's advantage over Sidon-shift generalizes to the third "
            "native lottery structure",
        ],
        "next_priority": "MEDIUM",
        "source_note": (
            "Computed and independently verified in this session (Strategy Matrix Phase 5, "
            "Generation 2, commits 94aa504 design + fd3ebd7 execute) via complete "
            "C(39,5)=575,757 enumeration, exact fractions.Fraction arithmetic, no simulation, "
            "no historical draws. Native T539 parameter-substitution translation of "
            "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (see "
            "DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO) -- the design doc "
            "(94aa504) confirmed no B649-specific constant is required, so this is a thin "
            "parameter-substitution wrapper, not a new algorithm. Arm A (Sidon) was "
            "recomputed fresh and cross-checked for exact identity against the already-sealed "
            "DIVERSIFICATION_COVERAGE_T539_V1 cell "
            "(arm_a_identity_check_vs_sealed_coverage_cell: true in the sealed result). "
            "Makes no predictive-advantage or prize-value claim. P638 not run by this task; "
            "P638_NATIVE_REPLICATION_CANDIDATE: YES per the sealed result."
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
