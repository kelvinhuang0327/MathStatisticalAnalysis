"""Lock the Phase-7 B649 next-generation constructor parameters.

Must run before any native candidate portfolio generation or M3+ coverage
inspection. The run tool re-hashes `LOCKED_PARAMETERS` and refuses to
execute if this file has been edited after lock.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-v1-preregistration-hash.json"
)

MATRIX_RESULTS = "docs/research/matrix-native-results/"
FRONTIER_RESULT = MATRIX_RESULTS + "diversification-constructor-frontier-b649-v1-result.json"

LOCKED_PARAMETERS: dict[str, Any] = {
    "study_id": "STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1",
    "task_id": "STRATEGY_MATRIX_PHASE7_B649_NEXT_GEN_CONSTRUCTOR_LOCK_EXECUTE_R1",
    "owner_authorization": "AUTHORIZE_MATRIX_PHASE7_B649_NEXT_GEN_CONSTRUCTOR_LOCK_EXECUTE_R1",
    "hypothesis_family_id": "DIVERSIFICATION",
    "source_type": "STRATEGY_MATRIX_NATIVE",
    "evidence_type": "EXACT_COMBINATORIAL",
    "lock_scope": "THIS_EXACT_CONSTRUCTOR_VARIANT_ONLY",
    "design_source_commit": "b7e9f31d069227d25323c51d912a1a38a5bf07dc",
    "canonical_input_commit": "3b3f953bf9857b85094e9f26c6ef5301ba3561e5",
    "canonical_input_tree": "6774dcade3c662d0ab3b757710e9e0aafcc3900b",
    "lottery_type": "BIG_LOTTO",
    "pool_size": 49,
    "draw_size": 6,
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "secondary_events": "not_run",
    "portfolio_mode": "nested_prefix",
    "constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "constructor_rule": "unused_legal_ticket_minimizing_max_then_sum_then_lex_ticket",
    "constructor_key": ["max_pairwise_overlap", "sum_pairwise_overlap", "ticket"],
    "tie_breaking": ["max_pairwise_overlap", "sum_pairwise_overlap", "lexicographic_ticket"],
    "weights": "none",
    "randomness": "none",
    "historical_draws_used": False,
    "monte_carlo": False,
    "post_result_tuning": "forbidden",
    "parameter_rescue": "forbidden",
    "arm_c_rerun": "forbidden",
    "t539_execution": "not_run",
    "p638_execution": "not_run",
    "duplicate_tickets_invariant": 0,
    "global_optimum_status": "UNKNOWN",
    "arm_a_constructor_id": "CYCLIC_SIDON_SHIFT_B649_V1",
    "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1",
    "arm_e_constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "arm_d_constructor_id": "RANDOM_EXPECTED_COVERAGE",
    "arm_c_role": "SEALED_B649_FRONTIER_REFERENCE_ONLY",
    "sidon_base_set_0_indexed": [0, 1, 3, 7, 12, 20],
    "evaluator_id": "ONE_PASS_EXACT_PREFIX_BITMASK_M3_PLUS",
    "random_baseline_id": "exact_random_portfolio_coverage",
    "material_gap_capture_threshold": "1/4",
    "material_gap_capture_k": 20,
    "frontier_capture_ratio_e": "(q_e-q_d)/(q_c-q_d)_when_q_c_gt_q_d",
    "b_to_c_gap_capture": "(q_e-q_b)/(q_c-q_b)_when_q_c_gt_q_b",
    "sealed_frontier_result_path": FRONTIER_RESULT,
    "sealed_frontier_result_blob_sha1": "169df1649ff0b8247ef5c779e8104079ae574cf4",
    "sealed_frontier_preregistration_hash_sha256": (
        "02b3bc90256b94864eb35e1caf940bec79f83f0315671281a49b3c0cb05b9e71"
    ),
    "sealed_q_a_path": "q.a.3",
    "sealed_q_b_path": "q.b.3",
    "sealed_q_c_path": "q.c.3",
    "sealed_q_d_path": "q.d.3",
    "sealed_q_a": [
        "4654/249711",
        "27487/499422",
        "18299/202664",
        "2428175/13983816",
        "5351/21252",
        "108833/332948",
    ],
    "sealed_q_b": [
        "4654/249711",
        "32528/582659",
        "54130/582659",
        "211705/1165318",
        "86785/332948",
        "142111/423752",
    ],
    "sealed_q_c": [
        "4654/249711",
        "32528/582659",
        "54130/582659",
        "636901/3495954",
        "3709795/13983816",
        "4788733/13983816",
    ],
    "sealed_q_d": [
        "4654/249711",
        "159788892251374/2911762307093563",
        "1419959489150088733927686730/15816289414131626798664925023",
        (
            "3245609755099340710811707686284489657738894441607314745205"
            "/18925227210815123131416370444785812104697344617405087907644"
        ),
        (
            "271586308598091491944473961161920217701361795742045773468872681632141016123471965"
            "/1104556455747825549799619007981605395356311895723711279867280216503407663299199788"
        ),
        (
            "136464931196442477556786924908590695592336254501634564575023749354655653145167291853998053419693416916091773745"
            "/435181005946643158001043454324458968052260403234855038192511642491193996017476596387224730277641783401254902388"
        ),
    ],
    "design_file_blobs": [
        {
            "path": (
                "docs/research/strategy-matrix-phase7-constructor-frontier-"
                "next-generation-design-r1.md"
            ),
            "blob": "3bd544d084ccab5e095bd9e29e10e5e23b894be8",
        },
        {
            "path": (
                "docs/research/constructor-frontier-next-generation-v1-preregistration-draft.md"
            ),
            "blob": "86f824a45709497972a614cc0f58be7b701711e1",
        },
        {
            "path": (
                "docs/research/constructor-frontier-next-generation-v1-execution-plan-schema.md"
            ),
            "blob": "d2a37077055dc87afa342a1c555a0327e369393c",
        },
        {
            "path": "src/lottolab/research/greedy_minmax_then_sum_overlap_constructor.py",
            "blob": "b141a3c881252135b581123761db820108e2f046",
        },
        {
            "path": "tests/unit/test_greedy_minmax_then_sum_overlap_constructor.py",
            "blob": "acb71b9571550f8a3366710c121179fc11034816",
        },
    ],
    "b649_advance_gate": [
        "q_e_gt_q_d_for_every_k_gt_1",
        "q_e_ge_q_b_for_every_k_gt_1",
        "q_e_gt_q_b_at_k_10_15_20",
        "b_to_c_gap_capture_20_ge_1_over_4",
        "duplicate_count_eq_0",
    ],
}


def main() -> None:
    digest = canonical_json.sha256_hex(canonical_json.canonical_bytes(LOCKED_PARAMETERS))
    record = {
        "hash_method": "LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256",
        "locked_parameters": LOCKED_PARAMETERS,
        "preregistration_hash_sha256": digest,
        "study_id": LOCKED_PARAMETERS["study_id"],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(record, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"preregistration_hash_sha256={digest}")


if __name__ == "__main__":
    main()
