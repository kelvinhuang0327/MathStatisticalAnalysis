"""Append the sealed DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 cell to the ledger.

Unlike `build_research_ledger.py` (which rebuilds the whole ledger from
every source at once), this appends exactly one new cell to the existing
`cells` array and leaves every other cell -- including the B649 and T539
DIVERSIFICATION cells -- byte-for-byte unchanged. An `hypothesis_variant_id`
is never edited in place after its outcome was inspected (see the schema
doc's Lifecycle section); this script only ever adds a new row.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

TODAY = date(2026, 8, 14).isoformat()
LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
RESULT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json"
)
NEW_CELL_ID = "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1"


def _build_cell() -> dict[str, Any]:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    d3_at_max_k = result["delta"]["3"]["20"]
    return {
        "cell_id": NEW_CELL_ID,
        "hypothesis_family_id": "DIVERSIFICATION",
        "hypothesis_variant_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1",
        "mechanism_class": "STRUCTURAL",
        "mechanism_family": "DIVERSIFICATION",
        "lottery_type": "POWER_LOTTO",
        "zone": "zone1",
        "generation": 1,
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "evidence_type": "EXACT_COMBINATORIAL",
        "uncertainty": "NONE -- exact enumeration / exact closed form",
        "record_state": "SEALED",
        "preregistration_grade": "R1_PREREGISTERED",
        "evidence_grade": "LOCAL_VERIFIED",
        "descriptive_classification": result["descriptive_classification"],
        "decision_state": "ADVANCE_TO_NEXT_LEVEL",
        "global_mechanism_status": "RETAIN_AND_REPLICATE",
        "exhausted": False,
        "predictive_advantage": "NOT_TESTED",
        "prize_value_advantage": "NOT_TESTED",
        "economic_optimality": "NOT_TESTED",
        "primary_endpoint_value": d3_at_max_k["float"],
        "primary_endpoint_definition": (
            "D_3(20) = Q_sidon_M3+(20) - Q_random_expected_M3+(20), exact combinatorics, "
            f"exact value {d3_at_max_k['exact']}. Native replication of "
            "DIVERSIFICATION_COVERAGE_B649_V1 and DIVERSIFICATION_COVERAGE_T539_V1 into "
            "POWER_LOTTO Zone-1's 6/38 structure (Zone-2 1-of-8 out of scope; see "
            "zone2 NOT_TESTED note below). Constructor required a completed backtracking "
            "search, not plain greedy: 38 is the first even pool size this mechanism was "
            "run against, and 19=38/2 is self-inverse, which plain greedy cannot satisfy "
            "(see preregistration Sec 3). Q_sidon(M6) == Q_random(M6) exactly for every k "
            "(D_6(k)=0), the same degenerate exact-match case as T539's M5: with draw_size=6, "
            "M6 means the draw equals a ticket outright, which no fixed-vs-random geometry "
            "distinction can affect."
        ),
        "null_replay_percentile": None,
        "artifact_paths": [
            f"docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-{suffix}"
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
            "DIVERSIFICATION_FULL_TICKET_P638_V2 (Zone-1 low-overlap geometry combined with "
            "Zone-2 1-of-8 allocation/cycling geometry) tests whether the mechanism survives "
            "once full-ticket structure is introduced -- a separate design, not authorized here",
            "extending the exposure ladder beyond k=20 to see whether the growing marginal "
            "advantage (already the largest of the three sealed native cells at k=20) "
            "continues or eventually turns over",
        ],
        "next_priority": "MEDIUM",
        "source_note": (
            "Computed and independently verified in this session (Strategy Matrix Phase 3) "
            "via complete C(38,6) = 2,760,681-draw enumeration, exact fractions.Fraction "
            "arithmetic, no simulation. Native replication cell: independently derived and "
            "independently verified Sidon-type base set in Z_38 (see "
            "diversification-coverage-p638-zone1-v1-preregistration.md Sec 3 for the "
            "even-modulus obstruction and its resolution), not copied from B649's or T539's "
            "base set. Makes no predictive-advantage or prize-value claim. decision_state is "
            "ADVANCE_TO_NEXT_LEVEL rather than REPLICATION_REQUIRED because this repository "
            "has exactly three lottery types (BIG_LOTTO, DAILY_539, POWER_LOTTO) and this "
            "single-zone diversification mechanism has now been natively replicated, "
            "positively, in all three -- CROSS_LOTTERY_REPLICATION_STATUS: "
            "SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES. This does not imply a universal "
            "predictive mechanism, a forecasting edge, economic optimality, or "
            "profitability -- the evidence type remains EXACT_COMBINATORIAL portfolio-"
            "geometry coverage, not forecasting. The B649 and T539 sibling cells' own "
            "decision_state fields are left unchanged (REPLICATION_REQUIRED, as sealed at "
            "the time), per the ledger's no-retroactive-edit rule."
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
