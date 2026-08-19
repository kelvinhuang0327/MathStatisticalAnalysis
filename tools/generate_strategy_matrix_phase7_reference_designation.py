"""Strategy Matrix Phase 7: reference designation for the next-generation
constructor `GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`.

This is a RESEARCH REFERENCE designation only. It does not change any
runtime, product, or default behavior; it is not a prediction method, a
runtime strategy, a profitability claim, or a global-optimum claim.

Reads exactly one canonical source: the already-SEALED Phase-7
cross-structure synthesis
(`STRATEGY_MATRIX_PHASE7_NEXT_GENERATION_CONSTRUCTOR_CROSS_STRUCTURE_SYNTHESIS_R1`),
pinned to the commit that introduced it (`SOURCE_COMMIT` below;
`git log --follow` on the source path shows it is that file's only
commit -- the later shallow-clone-safety fix touched only the generator
and test scripts that produced it, not the sealed data). Read via
`git show <commit>:<path>`, matching the pinning discipline of the
synthesis this designation is built on rather than trusting the working
tree.

Performs no new combinatorial enumeration, no portfolio regeneration, no
change to Constructor E, no parameter tuning, creates no new
matrix-native-result cell, does not alter any prior sealed artifact, and
reads no outcome/history data. Every field below is either read verbatim
from the source (`constructor_id`, `inputs.*.lottery_type`,
`reference_promotion_assessment.recommendation_scope`, ...) or is a direct
restatement of the designation-scope policy fixed by the task authority
that commissioned this module -- nothing here extrapolates past the
sealed ladder, sealed structures, or sealed recommendation.

Designation scope: Constructor E becomes the default *research* comparator
for future in-scope Matrix constructor studies only where ALL hold: the
primary tested coverage event, k >= 10, a domain compatible with the
sealed evidence, and Constructor E applied unchanged. At k in {1,3,5}
Constructor E only ties the previous reference in all three structures --
a tie alone does not trigger replacement. Untested k (>20), untested
structures/zones (P638 Zone-2, any 4th structure), and untested
objectives (predictive advantage, profitability, prize economic value)
are explicitly `NOT_ESTABLISHED_BY_THIS_DESIGNATION`.

`GLOBAL_OPTIMUM_STATUS` is carried through as `UNKNOWN` unconditionally,
and `RUNTIME_PROMOTION` is fixed at `NOT_AUTHORIZED`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path("docs/research/matrix-native-results")

SOURCE_COMMIT = "e7e886ff0537487f1ea2cbac848ea93382a22f43"
SOURCE_PATH = RESULTS_DIR / (
    "strategy-matrix-phase7-next-generation-constructor-cross-structure-synthesis-v1-result.json"
)
SOURCE_SYNTHESIS_ID = (
    "STRATEGY_MATRIX_PHASE7_NEXT_GENERATION_CONSTRUCTOR_CROSS_STRUCTURE_SYNTHESIS_R1"
)

_OUTPUT_BASENAME = "strategy-matrix-phase7-reference-designation-v1"
OUTPUT_PATH = RESULTS_DIR / f"{_OUTPUT_BASENAME}.json"

REQUIRED_CLASSIFICATION = "NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES"
REQUIRED_RECOMMENDATION = "PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR"
REQUIRED_GLOBAL_OPTIMUM_STATUS = "UNKNOWN"
EXPECTED_CONSTRUCTOR_ID = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
EXPECTED_LADDER = [1, 3, 5, 10, 15, 20]
IN_SCOPE_K = [k for k in EXPECTED_LADDER if k >= 10]
TIE_ONLY_K = [k for k in EXPECTED_LADDER if k < 10]

DESIGNATION_ID = "STRATEGY_MATRIX_PHASE7_REFERENCE_DESIGNATION_R1"
REFERENCE_DESIGNATION_STATUS = "METHOD_E_IS_NEXT_RESEARCH_REFERENCE_IN_SCOPE"
RUNTIME_PROMOTION = "NOT_AUTHORIZED"
NOT_ESTABLISHED = "NOT_ESTABLISHED_BY_THIS_DESIGNATION"


def _read_pinned_blob(commit: str, path: Path) -> str:
    show_cmd = ["git", "show", f"{commit}:{path.as_posix()}"]
    proc = subprocess.run(show_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        # Shallow checkouts (e.g. actions/checkout@v4's default fetch-depth: 1)
        # don't have older merged-in commits locally even though they're
        # reachable on the remote. Fetch just that commit, then retry once.
        subprocess.run(
            ["git", "fetch", "--depth=1", "origin", commit],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        proc = subprocess.run(show_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:  # pragma: no cover - environment guard
        raise RuntimeError(
            "STOP_REFERENCE_DESIGNATION_AUTHORITY_UNRESOLVED: cannot read pinned "
            f"canonical blob {commit}:{path} -- tried fetching {commit} from origin "
            f"and it still failed. stderr: {proc.stderr}"
        )
    return proc.stdout


def _require(condition: bool, what: str) -> None:
    if not condition:
        raise ValueError(f"STOP_REFERENCE_DESIGNATION_AUTHORITY_UNRESOLVED: {what}")


def load_source() -> dict[str, Any]:
    raw = _read_pinned_blob(SOURCE_COMMIT, SOURCE_PATH)
    data = json.loads(raw)

    _require(data.get("synthesis_id") == SOURCE_SYNTHESIS_ID, "synthesis_id mismatch")
    _require(
        data.get("synthesis_classification") == REQUIRED_CLASSIFICATION,
        f"synthesis_classification is not {REQUIRED_CLASSIFICATION!r}",
    )
    _require(
        data.get("reference_promotion_assessment", {}).get("recommendation")
        == REQUIRED_RECOMMENDATION,
        f"reference_promotion_assessment.recommendation is not {REQUIRED_RECOMMENDATION!r}",
    )
    _require(
        data.get("global_optimum_status") == REQUIRED_GLOBAL_OPTIMUM_STATUS,
        "global_optimum_status is not UNKNOWN",
    )
    _require(
        data.get("constructor_id") == EXPECTED_CONSTRUCTOR_ID,
        f"constructor_id is not {EXPECTED_CONSTRUCTOR_ID!r}",
    )
    _require(
        data.get("ladder") == EXPECTED_LADDER, "ladder does not match the expected exposure ladder"
    )
    _require(
        data.get("reference_promotion_assessment", {}).get("not_a_global_optimum_claim") is True,
        "source does not flag not_a_global_optimum_claim",
    )

    q2 = data["cross_structure_questions"]["q2_e_ge_reference_every_k_gt_1"]
    _require(
        q2.get("holds_for_all_three") is True,
        "Q2 (E ties-or-exceeds reference for every k>1) does not hold for all three structures",
    )
    q3 = data["cross_structure_questions"]["q3_e_gt_reference_at_k_10_15_20"]
    _require(
        q3.get("holds_for_all_three") is True,
        "Q3 (E strictly exceeds reference at k=10,15,20) does not hold for all three structures",
    )
    tie_at_1_3_5 = data["cross_structure_questions"]["q5_improvement_patterns"][
        "common_across_all_three"
    ]["e_ties_reference_exactly_at_k_1_3_5"]
    _require(
        tie_at_1_3_5 is True,
        "source does not confirm E ties (never worse) the reference at k in {1,3,5} "
        "across all three structures",
    )

    return data


def build_designation() -> dict[str, Any]:
    source = load_source()
    inputs = source["inputs"]
    structures = sorted(inputs)
    domains = sorted({spec["lottery_type"] for spec in inputs.values()})
    recommendation_scope = source["reference_promotion_assessment"]["recommendation_scope"]

    return {
        "designation_id": DESIGNATION_ID,
        "source_type": "STRATEGY_MATRIX_REFERENCE_DESIGNATION",
        "source_synthesis": {
            "synthesis_id": source["synthesis_id"],
            "source_result_path": str(SOURCE_PATH),
            "source_commit": SOURCE_COMMIT,
            "verified": {
                "synthesis_classification": source["synthesis_classification"],
                "reference_promotion_recommendation": (
                    source["reference_promotion_assessment"]["recommendation"]
                ),
                "global_optimum_status": source["global_optimum_status"],
            },
        },
        "constructor_id": source["constructor_id"],
        "reference_designation_status": REFERENCE_DESIGNATION_STATUS,
        "effective_scope": {
            "conditions_all_must_hold": {
                "primary_tested_coverage_event": (
                    f"as stated in the source's own recommendation_scope: {recommendation_scope!r}"
                ),
                "k_gte_10": f"within the tested ladder, k in {IN_SCOPE_K}",
                "domain_compatible_with_sealed_evidence": (
                    f"one of the {len(domains)} sealed native structures: {domains}"
                ),
                "method_e_applicable_unchanged": (
                    f"{source['constructor_id']} applied exactly as sealed, no parameter changes"
                ),
            },
            "recommendation_scope_as_sealed": recommendation_scope,
            "k_ladder_in_scope": IN_SCOPE_K,
            "structures_in_scope": structures,
            "domains_in_scope": domains,
        },
        "excluded_scope": {
            "k_1_3_5": {
                "status": "TIE_ONLY_DOES_NOT_TRIGGER_REPLACEMENT",
                "k": TIE_ONLY_K,
                "reason": (
                    "Constructor E exactly ties the previous reference (never worse) at "
                    "k in {1,3,5} in all three sealed structures per the source synthesis "
                    "(q2_e_ge_reference_every_k_gt_1, q5 common_across_all_three). A tie "
                    "alone does not replace Reference R for these k."
                ),
                "reference_status": NOT_ESTABLISHED,
            },
            "k_beyond_20": NOT_ESTABLISHED,
            "p638_zone2": NOT_ESTABLISHED,
            "any_4th_structure": NOT_ESTABLISHED,
            "untested_objectives": {
                "predictive_advantage": NOT_ESTABLISHED,
                "profitability": NOT_ESTABLISHED,
                "prize_economic_value": NOT_ESTABLISHED,
            },
            "incompatible_domains": NOT_ESTABLISHED,
            "extrapolation_policy": "DO_NOT_EXTRAPOLATE",
        },
        "prior_reference_treatment": {
            "status": "HISTORICAL_SEALED_COMPARATOR",
            "replaced_by_this_designation": False,
            "note": (
                "The prior reference constructor remains the historical/sealed comparator "
                "for every already-sealed result that used it. This designation does not "
                "alter, invalidate, or retroactively re-grade any prior sealed artifact."
            ),
        },
        "semantics": {
            "means": [
                "default scientific comparator for future in-scope Matrix constructor studies",
                "prior reference remains historical/sealed comparator",
                "future candidates should compare against Constructor E in-scope",
            ],
            "does_not_mean": [
                "production default",
                "prediction method",
                "runtime strategy",
                "profitability claim",
                "universal portability",
                "global optimum",
            ],
        },
        "claim_boundary": {
            "production_default": "NOT_CLAIMED",
            "prediction_method": "NOT_CLAIMED",
            "runtime_strategy": "NOT_CLAIMED",
            "profitability_claim": "NOT_CLAIMED",
            "universal_portability": "NOT_CLAIMED",
            "global_optimum": "NOT_CLAIMED",
        },
        "global_optimum_status": REQUIRED_GLOBAL_OPTIMUM_STATUS,
        "runtime_promotion": RUNTIME_PROMOTION,
        "no_new_science": {
            "reran_a_b_c": "NO",
            "regenerated_portfolios": "NO",
            "changed_method_e": "NO",
            "tuned_parameters": "NO",
            "new_matrix_native_result_cell": "NO",
            "altered_prior_sealed_artifacts": "NO",
            "inspected_outcome_or_history_data": "NO",
        },
        "next_task": "MATRIX_PHASE7_REFERENCE_DESIGNATION_CANONICALIZE_PUBLISH_R1",
    }


def main() -> None:
    designation = build_designation()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(designation, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"reference_designation_status: {designation['reference_designation_status']}")
    print(f"runtime_promotion: {designation['runtime_promotion']}")
    print(f"global_optimum_status: {designation['global_optimum_status']}")


if __name__ == "__main__":
    main()
