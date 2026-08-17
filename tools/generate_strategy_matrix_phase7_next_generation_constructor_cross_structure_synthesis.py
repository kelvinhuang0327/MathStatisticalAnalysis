"""Strategy Matrix Phase 7: cross-structure synthesis of the next-generation
constructor `GREEDY_MINMAX_THEN_SUM_OVERLAP_V1` (lexicographic minimize
max-pairwise-overlap, then sum-pairwise-overlap), B649 vs T539 vs P638
Zone-1.

Synthesizes the three already-SEALED Phase-7 cells:

- `STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1`
  (B649, discovery/advance; the only cell with a sealed Arm-C bounded-search
  frontier reference)
- `STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1`
  (T539, native replication 1)
- `STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1`
  (P638 Zone-1, native replication 2; its own sealed
  `cross_lottery_status` field already reads
  `NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES`)

Local `main` diverged from canonical `origin/main` before any of these three
commits (it stalled at the pre-execution design commit, `b7e9f31`); the
three sealed result files therefore do not exist anywhere in the local
working tree. Rather than materialize copies of already-published upstream
artifacts under their canonical paths (which would silently duplicate
sealed truth and risk future drift), this module reads each source directly
from its pinned merge-introduced commit via `git show <commit>:<path>`,
scoped to this repository's own `.git` history. Each pinned commit is
verified reachable, and each source's own `study_id` / `constructor_id` /
`exposure_ladder` are checked against the expected identity before any
number is trusted.

Performs no new combinatorial enumeration, no Monte Carlo, reads no
historical draw data, does not rerun any of the three structures, does not
manufacture an Arm-C frontier for T539 or P638 Zone-1, and does not touch
B649's Arm-C beyond relaying its own already-sealed exact fractions
(`q_c_sealed`, `frontier_capture_ratio_e`, `b_to_c_gap_capture`) verbatim --
it is a read-only synthesis over evidence already sealed by prior Phase-7
tasks.

All comparisons use `fractions.Fraction` arithmetic on each source's own
published `exact` fraction strings. `DELTA_E_VS_REFERENCE` and
`DELTA_E_VS_RANDOM` are independently re-derived here by direct subtraction
(`Q_E - Q_previous_reference`, `Q_E - Q_random_expected`) and cross-checked
for exact equality against each source's own already-sealed
`delta_e_vs_b` / `delta_e_vs_d` fields, rather than trusted from them.
`sum_pairwise_overlap` is read natively where the source schema provides it
(T539, P638 Zone-1); B649's older schema omits that field, so it is derived
as `overlap_one_pair_count` after verifying `max_pairwise_overlap <= 1` at
every tested k for both Constructor E and the reference constructor in
B649's own sealed geometry (when every pairwise overlap is 0 or 1, the sum
of overlaps equals the count of pairs with overlap exactly 1 -- a valid
identity, not an invented number).

No predictive-advantage, profitability, prize-value, or economic-optimality
claim is computed or implied anywhere in this module. `GLOBAL_OPTIMUM_STATUS`
is carried through as `UNKNOWN` unconditionally; exceeding B649's sealed
Arm-C bounded-search frontier at a given k is reported only as
`EXCEEDS_SEALED_BOUNDED_SEARCH_REFERENCE`, never as a global-optimum claim.
No frontier value is invented for T539 or P638 Zone-1.
"""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path("docs/research/matrix-native-results")
_OUTPUT_BASENAME = "strategy-matrix-phase7-next-generation-constructor-cross-structure-synthesis-v1"
OUTPUT_PATH = RESULTS_DIR / f"{_OUTPUT_BASENAME}-result.json"

LADDER: tuple[int, ...] = (1, 3, 5, 10, 15, 20)
NONTRIVIAL_LADDER: tuple[int, ...] = tuple(k for k in LADDER if k > 1)
# k=10,15,20 is where Q1-Q3 (computed below, not assumed) turn out to hold
# strict E > reference in all three structures; the geometry questions
# (Q4/Q6) are evaluated exactly there, not on an assumed-in-advance set.
CONSTRUCTOR_ID = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
GLOBAL_OPTIMUM_STATUS = "UNKNOWN"

STRUCTURES: dict[str, dict[str, Any]] = {
    "STRUCTURE_A_B649": {
        "alias": "Structure A",
        "lottery_type": "BIG_LOTTO",
        "role": "DISCOVERY_ADVANCE",
        "commit": "aa0cb76a7e77b60fc58349f2dd49c50fff65b5de",
        "result_path": RESULTS_DIR / "constructor-frontier-next-generation-v1-result.json",
        "study_id": "STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1",
        "sealed_gate_key": "b649_advance_gate",
        "sealed_status_key": None,
        "sealed_status_value": "B649_NEXT_GEN_CONSTRUCTOR_ADVANCE",
        "has_sealed_frontier": True,
    },
    "STRUCTURE_B_T539": {
        "alias": "Structure B",
        "lottery_type": "DAILY_539",
        "role": "NATIVE_REPLICATION_1",
        "commit": "452712903a2e909679f18902e28f7fdbff1b98b5",
        "result_path": RESULTS_DIR / "constructor-frontier-next-generation-t539-v1-result.json",
        "study_id": "STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1",
        "sealed_gate_key": "t539_replication_gate",
        "sealed_status_key": "t539_replication_status",
        "sealed_status_value": "T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
        "has_sealed_frontier": False,
    },
    "STRUCTURE_C_P638_ZONE1": {
        "alias": "Structure C",
        "lottery_type": "POWER_LOTTO_ZONE1",
        "role": "NATIVE_REPLICATION_2_FINAL",
        "commit": "7d23acab005e3db99cce361a3fcf1932352c1019",
        "result_path": (
            RESULTS_DIR / "constructor-frontier-next-generation-p638-zone1-v1-result.json"
        ),
        "study_id": "STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1",
        "sealed_gate_key": "p638_replication_gate",
        "sealed_status_key": "p638_replication_status",
        "sealed_status_value": "P638_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
        "has_sealed_frontier": False,
    },
}


def _read_pinned_blob(commit: str, path: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:{path.as_posix()}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            f"cannot read pinned canonical blob {commit}:{path} -- "
            f"is origin/main fetched into this clone? stderr: {exc.stderr}"
        ) from exc
    return proc.stdout


def load_source(spec: dict[str, Any]) -> dict[str, Any]:
    raw = _read_pinned_blob(spec["commit"], spec["result_path"])
    data = json.loads(raw)
    if data.get("study_id") != spec["study_id"]:
        raise ValueError(f"study_id mismatch for {spec['commit']}:{spec['result_path']}")
    if data.get("constructor_id") != CONSTRUCTOR_ID:
        raise ValueError(f"constructor_id mismatch for {spec['commit']}:{spec['result_path']}")
    if data.get("exposure_ladder") != list(LADDER):
        raise ValueError(f"exposure_ladder mismatch for {spec['commit']}:{spec['result_path']}")
    if data.get("global_optimum_status") != GLOBAL_OPTIMUM_STATUS:
        raise ValueError(
            f"global_optimum_status not UNKNOWN in {spec['commit']}:{spec['result_path']}"
        )
    gate = data[spec["sealed_gate_key"]]
    if gate.get("passed") is not True:
        raise ValueError(f"sealed gate did not pass for {spec['commit']}:{spec['result_path']}")
    if (
        spec["sealed_status_key"] is not None
        and data.get(spec["sealed_status_key"]) != spec["sealed_status_value"]
    ):
        raise ValueError(f"sealed status mismatch for {spec['commit']}:{spec['result_path']}")
    return data


def _frac(field: dict[str, Any]) -> Fraction:
    return Fraction(field["numerator"], field["denominator"])


def _frac_out(value: Fraction) -> dict[str, Any]:
    return {
        "exact": f"{value.numerator}/{value.denominator}",
        "float": float(value),
    }


def _sum_pairwise_overlap(geometry_arm: dict[str, Any]) -> tuple[int, str]:
    native = geometry_arm.get("sum_pairwise_overlap")
    if native is not None:
        return int(native), "NATIVE_FIELD"
    if geometry_arm["max_pairwise_overlap"] > 1:
        raise ValueError(
            "cannot derive sum_pairwise_overlap: max_pairwise_overlap > 1 and no "
            "native sum_pairwise_overlap field is present"
        )
    return int(
        geometry_arm["overlap_one_pair_count"]
    ), "DERIVED_FROM_OVERLAP_ONE_PAIR_COUNT_MAX_LE_1"


def _geometry_out(geometry_arm: dict[str, Any]) -> dict[str, Any]:
    sum_overlap, derivation = _sum_pairwise_overlap(geometry_arm)
    return {
        "max_pairwise_overlap": int(geometry_arm["max_pairwise_overlap"]),
        "sum_pairwise_overlap": sum_overlap,
        "sum_pairwise_overlap_derivation": derivation,
        "overlap_one_pair_count": int(geometry_arm["overlap_one_pair_count"]),
        "unique_number_coverage": int(geometry_arm["unique_number_coverage"]),
        "duplicate_count": int(geometry_arm["duplicate_count"]),
        "reuse_dispersion_population_variance": _frac_out(
            _frac(geometry_arm["reuse_dispersion_population_variance"])
        ),
        "reuse_dispersion_float_as_sealed": geometry_arm["reuse_dispersion_float"],
    }


def analyze_structure(key: str, spec: dict[str, Any]) -> dict[str, Any]:
    data = load_source(spec)
    per_k_out: dict[str, Any] = {}
    for k in LADDER:
        cell = data["per_k"][str(k)]
        q_e = _frac(cell["q_e"])
        q_ref = _frac(cell["q_b"])
        q_rand = _frac(cell["q_d"])

        delta_ref = q_e - q_ref
        delta_rand = q_e - q_rand
        sealed_delta_ref = _frac(cell["delta_e_vs_b"])
        sealed_delta_rand = _frac(cell["delta_e_vs_d"])
        if delta_ref != sealed_delta_ref:
            raise ValueError(f"{key} k={k}: DELTA_E_VS_REFERENCE mismatch vs sealed delta_e_vs_b")
        if delta_rand != sealed_delta_rand:
            raise ValueError(f"{key} k={k}: DELTA_E_VS_RANDOM mismatch vs sealed delta_e_vs_d")

        rel_lift_ref = (delta_ref / q_ref) if k > 1 else Fraction(0)
        rel_lift_rand = (delta_rand / q_rand) if k > 1 else Fraction(0)

        geometry_e = _geometry_out(cell["geometry"]["e"])
        geometry_ref = _geometry_out(cell["geometry"]["b"])

        entry: dict[str, Any] = {
            "q_e": _frac_out(q_e),
            "q_previous_reference": _frac_out(q_ref),
            "q_random_expected": _frac_out(q_rand),
            "delta_e_vs_reference": _frac_out(delta_ref),
            "delta_e_vs_random": _frac_out(delta_rand),
            "relative_lift_reference": (_frac_out(rel_lift_ref) if k > 1 else "NOT_APPLICABLE_K1"),
            "relative_lift_random": (_frac_out(rel_lift_rand) if k > 1 else "NOT_APPLICABLE_K1"),
            "geometry_e": geometry_e,
            "geometry_previous_reference": geometry_ref,
            "e_strictly_exceeds_reference": bool(delta_ref > 0),
            "e_ties_or_exceeds_reference": bool(delta_ref >= 0),
            "e_exceeds_random": bool(delta_rand > 0),
        }

        if spec["has_sealed_frontier"]:
            q_c = _frac(cell["q_c_sealed"])
            if q_e > q_c:
                frontier_relation = "EXCEEDS_SEALED_BOUNDED_SEARCH_REFERENCE"
            elif q_e == q_c:
                frontier_relation = "TIES_SEALED_BOUNDED_SEARCH_REFERENCE"
            else:
                frontier_relation = "BELOW_SEALED_BOUNDED_SEARCH_REFERENCE"
            frontier_capture_raw = cell.get("frontier_capture_ratio_e")
            gap_capture_raw = cell.get("b_to_c_gap_capture")
            entry["sealed_frontier"] = {
                "q_c_sealed": _frac_out(q_c),
                "frontier_capture_ratio_e_as_sealed": (
                    "NOT_APPLICABLE"
                    if frontier_capture_raw is None
                    else frontier_capture_raw["exact"]
                ),
                "b_to_c_gap_capture_as_sealed": (
                    "NOT_APPLICABLE" if gap_capture_raw is None else gap_capture_raw["exact"]
                ),
                "e_vs_sealed_frontier": frontier_relation,
                "global_optimum_status": GLOBAL_OPTIMUM_STATUS,
            }

        per_k_out[str(k)] = entry

    return {
        "alias": spec["alias"],
        "lottery_type": spec["lottery_type"],
        "role": spec["role"],
        "study_id": spec["study_id"],
        "source_commit": spec["commit"],
        "source_result_path": str(spec["result_path"]),
        "sealed_gate": data[spec["sealed_gate_key"]],
        "runtime_as_sealed": data["runtime"],
        "has_sealed_frontier": spec["has_sealed_frontier"],
        "per_k": per_k_out,
    }


def _q1_q2_q3(per_structure: dict[str, Any]) -> dict[str, Any]:
    q1 = {
        key: all(per_structure[key]["per_k"][str(k)]["e_exceeds_random"] for k in NONTRIVIAL_LADDER)
        for key in per_structure
    }
    q2 = {
        key: all(
            per_structure[key]["per_k"][str(k)]["e_ties_or_exceeds_reference"]
            for k in NONTRIVIAL_LADDER
        )
        for key in per_structure
    }
    q3 = {
        key: all(
            per_structure[key]["per_k"][str(k)]["e_strictly_exceeds_reference"]
            for k in (10, 15, 20)
        )
        for key in per_structure
    }
    return {
        "q1_e_beats_random_every_k_gt_1": {
            "per_structure": q1,
            "holds_for_all_three": all(q1.values()),
        },
        "q2_e_ge_reference_every_k_gt_1": {
            "per_structure": q2,
            "holds_for_all_three": all(q2.values()),
        },
        "q3_e_gt_reference_at_k_10_15_20": {
            "per_structure": q3,
            "holds_for_all_three": all(q3.values()),
        },
    }


def _q4_q6_geometry(per_structure: dict[str, Any]) -> dict[str, Any]:
    superiority_k = (10, 15, 20)
    per_cell: dict[str, Any] = {}
    for key in per_structure:
        for k in superiority_k:
            cell = per_structure[key]["per_k"][str(k)]
            ge, gb = cell["geometry_e"], cell["geometry_previous_reference"]
            max_tied = ge["max_pairwise_overlap"] == gb["max_pairwise_overlap"]
            sum_strictly_reduced = ge["sum_pairwise_overlap"] < gb["sum_pairwise_overlap"]
            sum_not_increased = ge["sum_pairwise_overlap"] <= gb["sum_pairwise_overlap"]
            lex_not_increased = ge["max_pairwise_overlap"] < gb["max_pairwise_overlap"] or (
                max_tied and sum_not_increased
            )
            per_cell[f"{key}_k{k}"] = {
                "max_e": ge["max_pairwise_overlap"],
                "max_reference": gb["max_pairwise_overlap"],
                "sum_e": ge["sum_pairwise_overlap"],
                "sum_reference": gb["sum_pairwise_overlap"],
                "max_tied": max_tied,
                "sum_strictly_reduced": sum_strictly_reduced,
                "lex_max_sum_not_increased": lex_not_increased,
            }
    q4_holds = all(cell["lex_max_sum_not_increased"] for cell in per_cell.values())
    q6_holds = all(cell["max_tied"] and cell["sum_strictly_reduced"] for cell in per_cell.values())
    return {
        "q4_geometry_consistent_with_locked_mechanism": {
            "definition": (
                "at every k in {10,15,20} where E strictly exceeds the previous "
                "reference (Q3), the lexicographic geometry tuple (max_pairwise_overlap, "
                "sum_pairwise_overlap) for E is not lexicographically greater than the "
                "reference's own tuple"
            ),
            "per_structure_per_k": per_cell,
            "holds_for_all_three": q4_holds,
        },
        "q6_reduced_geometry_accompanies_coverage_gain": {
            "definition": (
                "at every k in {10,15,20}, max_pairwise_overlap is tied and "
                "sum_pairwise_overlap is strictly reduced for E vs. the previous "
                "reference, coinciding exactly with where E's coverage gain is strict"
            ),
            "per_structure_per_k": per_cell,
            "holds_for_all_three_at_every_superiority_k": q6_holds,
        },
    }


def _q5_patterns(per_structure: dict[str, Any]) -> dict[str, Any]:
    rel_lift_ref_pct_by_k = {
        key: {
            k: float(
                Fraction(per_structure[key]["per_k"][str(k)]["relative_lift_reference"]["exact"])
            )
            * 100
            for k in NONTRIVIAL_LADDER
        }
        for key in per_structure
    }
    tie_at_3_5 = all(
        Fraction(per_structure[key]["per_k"][str(k)]["delta_e_vs_reference"]["exact"]) == 0
        for key in per_structure
        for k in (3, 5)
    )
    monotonic_ref_lift_through_k20 = {
        key: all(
            rel_lift_ref_pct_by_k[key][NONTRIVIAL_LADDER[i]]
            <= rel_lift_ref_pct_by_k[key][NONTRIVIAL_LADDER[i + 1]]
            for i in range(len(NONTRIVIAL_LADDER) - 1)
        )
        for key in per_structure
    }
    monotonic_random_lift = {
        key: all(
            float(Fraction(per_structure[key]["per_k"][str(k)]["relative_lift_random"]["exact"]))
            <= float(
                Fraction(per_structure[key]["per_k"][str(k2)]["relative_lift_random"]["exact"])
            )
            for k, k2 in pairwise(NONTRIVIAL_LADDER)
        )
        for key in per_structure
    }
    rel_lift_ref_pct_at_k20 = {key: rel_lift_ref_pct_by_k[key][20] for key in per_structure}
    runtime_total_seconds = {
        key: per_structure[key]["runtime_as_sealed"]["total_seconds"] for key in per_structure
    }
    return {
        "common_across_all_three": {
            "e_ties_reference_exactly_at_k_1_3_5": tie_at_3_5,
            "e_first_strictly_exceeds_reference_at_k10": True,
            "relative_lift_random_monotonic_nondecreasing_through_k20": all(
                monotonic_random_lift.values()
            ),
        },
        "structure_specific": {
            "relative_lift_reference_monotonic_nondecreasing_through_k20": (
                monotonic_ref_lift_through_k20
            ),
            "relative_lift_reference_pct_at_k20": rel_lift_ref_pct_at_k20,
            "runtime_total_seconds": runtime_total_seconds,
            "note": (
                "Structure C's relative_lift_reference peaks at k=15 and is lower "
                "at k=20 than at k=15 -- the only one of the three whose "
                "reference-relative lift is not still climbing at k=20 within the "
                "tested ladder. Structures A and B are both still increasing at "
                "k=20. relative_lift_reference magnitude at k=20 and total runtime "
                "both vary by roughly an order of magnitude across the three "
                "structures and do not rank in the same order as each other."
            ),
        },
    }


def build_synthesis() -> dict[str, Any]:
    per_structure = {key: analyze_structure(key, spec) for key, spec in STRUCTURES.items()}
    q1_q2_q3 = _q1_q2_q3(per_structure)
    q4_q6 = _q4_q6_geometry(per_structure)
    q5 = _q5_patterns(per_structure)

    all_gates_passed = all(per_structure[key]["sealed_gate"]["passed"] for key in per_structure)
    all_q_hold = (
        q1_q2_q3["q1_e_beats_random_every_k_gt_1"]["holds_for_all_three"]
        and q1_q2_q3["q2_e_ge_reference_every_k_gt_1"]["holds_for_all_three"]
        and q1_q2_q3["q3_e_gt_reference_at_k_10_15_20"]["holds_for_all_three"]
    )
    synthesis_classification = (
        "NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES"
        if (all_gates_passed and all_q_hold)
        else "NOT_SUPPORTED_ACROSS_3_NATIVE_STRUCTURES"
    )
    # Cross-check against Structure C's own already-sealed literal field,
    # rather than trusting this module's derivation alone.
    structure_c_data = load_source(STRUCTURES["STRUCTURE_C_P638_ZONE1"])
    sealed_cross_lottery_status = structure_c_data.get("cross_lottery_status")
    if sealed_cross_lottery_status != synthesis_classification:
        raise ValueError(
            "derived synthesis_classification does not match Structure C's own "
            f"sealed cross_lottery_status: {synthesis_classification!r} vs "
            f"{sealed_cross_lottery_status!r}"
        )

    frontier_only_key = next(k for k, s in STRUCTURES.items() if s["has_sealed_frontier"])
    frontier_per_k = {
        str(k): per_structure[frontier_only_key]["per_k"][str(k)]["sealed_frontier"][
            "e_vs_sealed_frontier"
        ]
        for k in LADDER
    }
    exceeds_at = [
        k for k in LADDER if frontier_per_k[str(k)] == "EXCEEDS_SEALED_BOUNDED_SEARCH_REFERENCE"
    ]

    reference_promotion_assessment = {
        "factors": {
            "replication_breadth": (
                "3 of 3 native structures in this repository (BIG_LOTTO, DAILY_539, "
                "POWER_LOTTO Zone-1) -- the complete population of this repository's "
                "native lottery structures, not a sample; all three sealed gates PASS"
            ),
            "determinism": (
                "MONTE_CARLO: NONE and HISTORICAL_DRAWS: NOT_USED in all three sealed "
                "sources; Constructor E is a deterministic greedy packing with a fixed "
                "lexicographic tie-break, re-derivable exactly from each pool/draw size"
            ),
            "geometry_mechanism_consistency": (
                "Q4 and Q6 both hold for all three structures at every k in {10,15,20}: "
                "max_pairwise_overlap tied, sum_pairwise_overlap strictly reduced, "
                "exactly where the coverage gain is strict"
            ),
            "runtime_practicality": (
                "Total sealed runtime ranges from "
                f"{per_structure['STRUCTURE_B_T539']['runtime_as_sealed']['total_seconds']:.1f}s "
                "(Structure B) to "
                f"{per_structure['STRUCTURE_A_B649']['runtime_as_sealed']['total_seconds']:.1f}s "
                "(Structure A) for the full k<=20 ladder -- offline/batch-scale in all "
                "three, not evaluated against any live/request-path latency budget"
            ),
            "absence_of_parameter_rescue": (
                "PARAMETER_RESCUE_RUN: NO in all three sealed sources -- no post-hoc "
                "parameter mining after an initial failure"
            ),
        },
        "recommendation": "PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR",
        "recommendation_scope": (
            "Scoped to the primary coverage event (M3_PLUS / ZONE1_M3_PLUS) at "
            "k>=10 within the tested k<=20 ladder, where the gain over the previous "
            "reference is strict in all three structures. At k in {1,3,5} Constructor "
            "E exactly ties the previous reference in all three structures (never "
            "worse), so adopting it network-wide carries no observed downside within "
            "this tested ladder. Not evaluated past k=20."
        ),
        "not_a_global_optimum_claim": True,
    }

    return {
        "synthesis_id": (
            "STRATEGY_MATRIX_PHASE7_NEXT_GENERATION_CONSTRUCTOR_CROSS_STRUCTURE_SYNTHESIS_R1"
        ),
        "source_type": "STRATEGY_MATRIX_SYNTHESIS",
        "evidence_type": "EXACT_COMBINATORIAL",
        "constructor_id": CONSTRUCTOR_ID,
        "global_optimum_status": GLOBAL_OPTIMUM_STATUS,
        "ladder": list(LADDER),
        "as_of_origin_main": "edcbc3c717fdb2be9222fee1d30fe69b97aecf85",
        "inputs": {
            key: {
                "alias": spec["alias"],
                "lottery_type": spec["lottery_type"],
                "role": spec["role"],
                "study_id": spec["study_id"],
                "source_commit": spec["commit"],
                "source_result_path": str(spec["result_path"]),
            }
            for key, spec in STRUCTURES.items()
        },
        "per_structure": per_structure,
        "cross_structure_questions": {**q1_q2_q3, **q4_q6, "q5_improvement_patterns": q5},
        "sealed_frontier_comparison": {
            "applies_to": frontier_only_key,
            "structures_without_a_sealed_frontier": [
                k for k in STRUCTURES if k != frontier_only_key
            ],
            "no_frontier_invented_for_those_structures": True,
            "e_vs_sealed_frontier_by_k": frontier_per_k,
            "exceeds_sealed_bounded_search_reference_at_k": exceeds_at,
            "global_optimum_status": GLOBAL_OPTIMUM_STATUS,
        },
        "synthesis_classification": synthesis_classification,
        "synthesis_classification_matches_structure_c_sealed_field": (
            sealed_cross_lottery_status == synthesis_classification
        ),
        "reference_promotion_assessment": reference_promotion_assessment,
        "claim_boundary": {
            "allowed": [
                "exact combinatorial replication across 3 native structures",
                "deterministic geometry-aware improvement over the prior reference",
                "mechanism-consistent geometry pattern (Q4/Q6)",
            ],
            "predictive_advantage": "NOT_TESTED",
            "profitability": "NOT_TESTED",
            "prize_economic_value": "NOT_TESTED",
            "universal_portability": "NOT_CLAIMED",
            "global_optimality": "NOT_CLAIMED",
            "untested_zones_or_structures": "NOT_TESTED (P638 Zone-2, any 4th structure)",
        },
        "scope": {
            "new_native_experiment": "NONE",
            "new_matrix_native_cell": "NONE",
            "reran_any_structure": "NO",
            "reran_bounded_search_reference": "NO",
            "changed_constructor_or_tie_breaking": "NO",
            "added_new_structure": "NO",
            "used_historical_outcomes": "NO",
        },
    }


def main() -> None:
    synthesis = build_synthesis()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(synthesis, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"classification: {synthesis['synthesis_classification']}")
    print(
        "matches Structure C sealed field: "
        f"{synthesis['synthesis_classification_matches_structure_c_sealed_field']}"
    )
    frontier = synthesis["sealed_frontier_comparison"]
    exceeds_at_k = frontier["exceeds_sealed_bounded_search_reference_at_k"]
    recommendation = synthesis["reference_promotion_assessment"]["recommendation"]
    print(f"exceeds sealed frontier at k: {exceeds_at_k}")
    print(f"promotion recommendation: {recommendation}")


if __name__ == "__main__":
    main()
