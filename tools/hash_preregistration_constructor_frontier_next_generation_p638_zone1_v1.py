"""Lock the Phase-7 P638 Zone-1 next-generation constructor replication.

Must run before any native P638 Zone-1 candidate portfolio coverage
inspection. The run tool re-hashes `LOCKED_PARAMETERS` and refuses to
execute if this file has been edited after lock. B649 and T539 are
referenced as sealed authority only and are not rerun. Arm-C is not
manufactured. Zone-2 is out of scope.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-p638-zone1-v1-preregistration-hash.json"
)

MATRIX_RESULTS = "docs/research/matrix-native-results/"
B649_RESULT = MATRIX_RESULTS + "constructor-frontier-next-generation-v1-result.json"
T539_RESULT = MATRIX_RESULTS + "constructor-frontier-next-generation-t539-v1-result.json"
SIDON_RESULT = MATRIX_RESULTS + "diversification-coverage-p638-zone1-v1-result.json"
ARM_B_RESULT = MATRIX_RESULTS + "greedy-min-overlap-constructor-p638-zone1-v1-result.json"

LOCKED_PARAMETERS: dict[str, Any] = {
    "arm_a_constructor_id": "CYCLIC_SIDON_SHIFT_P638_ZONE1_V1",
    "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
    "arm_c_rerun": "forbidden",
    "arm_c_role": "not_applicable_no_p638_frontier",
    "arm_d_constructor_id": "RANDOM_EXPECTED_COVERAGE",
    "arm_e_constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "b649_phase7_advance": "PASS",
    "b649_phase7_constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "b649_phase7_cross_lottery_replication_eligible": True,
    "b649_phase7_preregistration_hash_sha256": (
        "ea014c2204e1fa77041329fc60d172502589bbc02c7922c63e78120e582080c1"
    ),
    "b649_phase7_result_blob_sha1": "70148c6c59baea1087126bf95a009eb4d291149c",
    "b649_phase7_result_path": B649_RESULT,
    "b649_rerun": "forbidden",
    "canonical_input_commit": "8d5e83219834266c4a60927297ba21a61a2379f4",
    "canonical_input_tree": "3eef6b026100ce8550442a10c92750bce1852b04",
    "constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "constructor_key": [
        "max_pairwise_overlap",
        "sum_pairwise_overlap",
        "ticket",
    ],
    "constructor_rule": "unused_legal_ticket_minimizing_max_then_sum_then_lex_ticket",
    "design_file_blobs": [
        {
            "blob": "b141a3c881252135b581123761db820108e2f046",
            "path": "src/lottolab/research/greedy_minmax_then_sum_overlap_constructor.py",
        },
        {
            "blob": "736d0c7e8efc79f68e989921be3e5e0742617e97",
            "path": "src/lottolab/research/cyclic_sidon_shift_p638.py",
        },
        {
            "blob": "5511f67d981f7f8a1c33183c966d76ee50249d7d",
            "path": "src/lottolab/research/greedy_min_overlap_constructor.py",
        },
        {
            "blob": "622898a9f0a9f4c72af456a21af83c0fc63c7d45",
            "path": "src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py",
        },
    ],
    "draw_size": 6,
    "duplicate_tickets_invariant": 0,
    "evaluator_id": "ONE_PASS_EXACT_PREFIX_BITMASK_ZONE1_M3_PLUS",
    "evidence_type": "EXACT_COMBINATORIAL",
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "fail_classification": "DO_NOT_ADVANCE_THIS_EXACT_P638_REPLICATION",
    "geometry_metrics": [
        "max_pairwise_overlap",
        "mean_pairwise_overlap",
        "pair_intersection_histogram",
        "overlap_one_pair_count",
        "s2_redundancy_proxy",
        "unique_number_coverage",
        "reuse_dispersion",
        "duplicate_count",
        "sum_pairwise_overlap",
    ],
    "global_optimum_status": "UNKNOWN",
    "historical_draws_used": False,
    "hypothesis_family_id": "DIVERSIFICATION",
    "lock_scope": "THIS_EXACT_P638_ZONE1_REPLICATION_ONLY",
    "lottery_type": "POWER_LOTTO",
    "monte_carlo": False,
    "owner_authorization": "AUTHORIZE_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1",
    "p638_replication_gate": [
        "q_e_gt_q_d_for_every_k_gt_1",
        "q_e_ge_q_b_for_every_k_gt_1",
        "q_e_gt_q_b_at_k_10_15_20",
        "duplicate_count_eq_0",
        "geometry_lex_max_sum_not_increased_where_coverage_superiority_claimed",
    ],
    "p638_zone": "zone1",
    "p638_zone2": "out_of_scope",
    "parameter_rescue": "forbidden",
    "pass_classification": "P638_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
    "pool_size": 38,
    "portfolio_mode": "nested_prefix",
    "post_result_tuning": "forbidden",
    "primary_event": "ZONE1_M3_PLUS",
    "primary_event_minimum_matches": 3,
    "random_baseline_id": "exact_random_portfolio_coverage",
    "randomness": "none",
    "sealed_arm_b_preregistration_hash_sha256": (
        "e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b"
    ),
    "sealed_arm_b_result_blob_sha1": "7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5",
    "sealed_arm_b_result_path": ARM_B_RESULT,
    "sealed_q_a": [
        "35611/920227",
        "44509/394383",
        "504676/2760681",
        "950281/2760681",
        "445590/920227",
        "1369/2261",
    ],
    "sealed_q_a_path": "q.a.3",
    "sealed_q_b": [
        "35611/920227",
        "106433/920227",
        "530165/2760681",
        "324750/920227",
        "64365/131461",
        "1686068/2760681",
    ],
    "sealed_q_b_path": "q.b.3",
    "sealed_q_d": [
        "35611/920227",
        "1075700708906341/9633754456494355",
        "7689288966780371765498391/42936912681087072686828603",
        (
            "12055457617054652709605677589559750389447883460801"
            "/36969021318790152117334906498422957884935295458270"
        ),
        (
            "2810171242532411178262502967881988185426574514447954450164460031493081669148"
            "/6289809660854272027754500622017671140253487926128804664208537474143850220895"
        ),
        (
            "10270202302633615863312327738837263272327303835576854236234331415440224472009028462792403800706875633"
            "/18814913719018706731244049116896221395094413679195712746293706387357748656881255158086112913373655910"
        ),
    ],
    "sealed_q_d_path": "q.c.3",
    "sealed_sidon_preregistration_hash_sha256": (
        "53e18558d07821460772a49f8358da3f2290b888dbde21c4497a0525c73cc992"
    ),
    "sealed_sidon_result_blob_sha1": "f75ce278096d120ab368a058dba0f6262e9e8041",
    "sealed_sidon_result_path": SIDON_RESULT,
    "secondary_events": "not_run",
    "sidon_base_set_0_indexed": [0, 1, 3, 7, 17, 30],
    "source_type": "STRATEGY_MATRIX_NATIVE",
    "study_id": "STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1",
    "t539_phase7_constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
    "t539_phase7_p638_replication_eligible": True,
    "t539_phase7_preregistration_hash_sha256": (
        "3ecd753f664e7a2d558df8a2a9e43f9ab93105b0713e1a58d0e8d67abebee59d"
    ),
    "t539_phase7_result_blob_sha1": "ac6a1ae936566d78880d61f4db8d7c4168c8606c",
    "t539_phase7_result_path": T539_RESULT,
    "t539_phase7_status": "T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
    "t539_rerun": "forbidden",
    "task_id": "STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1",
    "tie_breaking": [
        "max_pairwise_overlap",
        "sum_pairwise_overlap",
        "lexicographic_ticket",
    ],
    "weights": "none",
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
