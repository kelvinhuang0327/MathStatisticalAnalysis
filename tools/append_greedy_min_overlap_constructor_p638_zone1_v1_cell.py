"""Append the sealed GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 cell to the ledger.

Unlike `build_research_ledger.py` (which rebuilds the whole ledger from
every source at once), this appends exactly one new cell to the existing
`cells` array and leaves every other cell -- including
`DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO` and
`GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1__DAILY_539` -- byte-for-byte
unchanged. An `hypothesis_variant_id` is never edited in place after its
outcome was inspected (see the schema doc's Lifecycle section); this script
only ever adds a new row. Mirrors
`append_greedy_min_overlap_constructor_t539_v1_cell.py` and
`append_diversification_coverage_p638_zone1_v1_cell.py`.

This cell is the P638 Zone-1-native replication of
`DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO` and
`GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1__DAILY_539` (Strategy Matrix Phase
5, Generation 2): the design (9b60007) confirmed no B649/T539-specific
constant is required, so this is a native parameter-substitution instance
of the same mechanism, not a new algorithm -- `generation: 2` here matches
both siblings, not the Generation-1 Sidon-coverage cells.

Unlike the T539 cell (sealed while P638 native replication was still
outstanding), this cell closes the three-native-lottery replication chain
for the non-Sidon low-overlap constructor mechanism -- POWER_LOTTO is the
last of this repository's three native lottery structures (BIG_LOTTO,
DAILY_539, POWER_LOTTO). `decision_state` is therefore
`ADVANCE_TO_NEXT_LEVEL`, not `REPLICATION_REQUIRED`, mirroring the exact
precedent `DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1`
already set for the Sidon-coverage mechanism's own closure. The B649 and
T539 sibling cells' own `decision_state` fields (`REPLICATION_REQUIRED`, as
sealed at the time) are left unchanged, per the ledger's no-retroactive-edit
rule -- same as that precedent cell's own source_note already disclosed
doing for its siblings.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

TODAY = date(2026, 8, 15).isoformat()
LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
RESULT_PATH = Path(
    "docs/research/matrix-native-results/greedy-min-overlap-constructor-p638-zone1-v1-result.json"
)
NEW_CELL_ID = "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1__POWER_LOTTO_zone1"


def _build_cell() -> dict[str, Any]:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    delta_sidon_20 = result["delta_sidon"]["3"]["20"]
    delta_random_b_20 = result["delta_random_b"]["3"]["20"]
    return {
        "cell_id": NEW_CELL_ID,
        "hypothesis_family_id": "DIVERSIFICATION",
        "hypothesis_variant_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
        "mechanism_class": "STRUCTURAL",
        "mechanism_family": "DIVERSIFICATION",
        "lottery_type": "POWER_LOTTO",
        "zone": "zone1",
        "generation": 2,
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "evidence_type": "EXACT_COMBINATORIAL",
        "uncertainty": "NONE -- exact enumeration / exact closed form",
        "record_state": "SEALED",
        "preregistration_grade": "R1_PREREGISTERED",
        "evidence_grade": "LOCAL_VERIFIED",
        "descriptive_classification": "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE",
        "decision_state": "ADVANCE_TO_NEXT_LEVEL",
        "global_mechanism_status": "RETAIN_AND_REPLICATE",
        "exhausted": False,
        "predictive_advantage": "NOT_TESTED",
        "prize_value_advantage": "NOT_TESTED",
        "economic_optimality": "NOT_TESTED",
        "primary_endpoint_value": delta_sidon_20["float"],
        "primary_endpoint_definition": (
            "DELTA_SIDON(20) = Q_greedy_M3+(20) - Q_sidon_M3+(20), exact combinatorics via "
            f"complete C(38,6)=2,760,681 enumeration, exact value {delta_sidon_20['exact']}. "
            "Q2 requires DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}: TRUE -> "
            "P638_ARM_B_EXCEEDS_SIDON_GAIN -- arm B (greedy, non-Sidon) exceeds P638 "
            "Zone-1's own sealed Sidon-shift gain over random at every tested k>1, "
            "matching B649's and T539's own arm-B findings in direction "
            "(CONSISTENT_WITH_B649_AND_T539). DELTA_RANDOM_B(20) (arm B vs. random, Q1) = "
            f"{delta_random_b_20['exact']} ({delta_random_b_20['float']:+.8f}), also > 0 "
            "at every k>1 -> P638_ARM_B_OUTPERFORMS_RANDOM. "
            "NON_SIDON_LOW_OVERLAP_CROSS_LOTTERY_STATUS: "
            "SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES -- POWER_LOTTO Zone-1 is the last of "
            "this repository's three native lottery structures for this arm-B translation "
            "chain."
        ),
        "null_replay_percentile": None,
        "artifact_paths": [
            f"docs/research/matrix-native-results/greedy-min-overlap-constructor-p638-zone1-v1-{suffix}"
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
            "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1) is run at P638 Zone-1 scale to "
            "test whether an even larger gap over Sidon exists here too",
            "DIVERSIFICATION_FULL_TICKET_P638_V2 (Zone-1 low-overlap geometry combined "
            "with Zone-2 1-of-8 allocation/cycling geometry) tests whether this mechanism "
            "survives once full-ticket structure is introduced -- a separate design, not "
            "authorized here",
            "extending the exposure ladder beyond k=20 to see whether the non-monotonic "
            "DELTA_SIDON(k) shape (peaking at k=5, declining but still positive through "
            "k=20) continues to hold or eventually turns non-positive",
        ],
        "next_priority": "MEDIUM",
        "source_note": (
            "Computed and independently verified in this session (Strategy Matrix Phase 5, "
            "Generation 2, design commit 9b60007 + this task's single lock+execute+"
            "canonicalize commit) via complete C(38,6)=2,760,681 enumeration, exact "
            "fractions.Fraction arithmetic, no simulation, no historical draws. Native "
            "POWER_LOTTO Zone-1 parameter-substitution translation of "
            "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1/T539_V1 (see "
            "DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO and "
            "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1__DAILY_539) -- the design doc (9b60007) "
            "confirmed no B649/T539-specific constant is required, so this is a thin "
            "parameter-substitution wrapper, not a new algorithm. Arm A (Sidon) was "
            "recomputed fresh and cross-checked for exact identity against the already-"
            "sealed DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 cell "
            "(arm_a_identity_check_vs_sealed_coverage_cell: true in the sealed result). "
            "Makes no predictive-advantage or prize-value claim. This closes the "
            "three-native-lottery replication chain for this arm-B mechanism -- "
            "decision_state is ADVANCE_TO_NEXT_LEVEL rather than REPLICATION_REQUIRED for "
            "the same reason DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1's "
            "own decision_state was: this repository has exactly three lottery types and "
            "this mechanism has now been natively replicated, positively, in all three. "
            "The B649 and T539 sibling cells' own decision_state fields are left unchanged "
            "(REPLICATION_REQUIRED, as sealed at the time), per the ledger's "
            "no-retroactive-edit rule -- same precedent that Sidon-coverage closure cell "
            "already set."
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
