"""Compute and write the lock hash for STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1.

Mirrors the established pattern (`hash_preregistration_t539_arm_b.py`,
`hash_preregistration_p638_arm_b.py`, `hash_preregistration_b649_constructor_frontier.py`):
build a strict, LCJ-1-domain `locked_parameters` mapping, hash its canonical
bytes, and write the sidecar `-preregistration-hash.json`. This is the one
lock artifact `run_low_overlap_geometry_mechanism_v1.py` re-verifies before
touching any native winning space.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration-hash.json"
)

MATRIX_RESULTS = "docs/research/matrix-native-results/"

LOCKED_PARAMETERS: dict[str, Any] = {
    "study_id": "STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1",
    "task_id": "STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_LOCK_EXECUTE_R1",
    "owner_authorization": (
        "AUTHORIZE_STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_LOCK_EXECUTE_R1"
    ),
    "hypothesis_family_id": "DIVERSIFICATION",
    "source_type": "STRATEGY_MATRIX_NATIVE_MECHANISM",
    "evidence_type": "EXACT_COMBINATORIAL",
    "design_commit": "1fb81414747864d31f91c6567ff81fe1ed50eb02",
    "canonical_input_commit": "52b8353c932589c3f3ea8ff61fe7982c667cbbb0",
    "canonical_input_tree": "69e81767f701ea4f29f86bb0af34262191950c70",
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "delta_direction": "arm_b_minus_sidon",
    "portfolio_mode": "nested_prefix",
    "duplicate_tickets_invariant": 0,
    "monte_carlo": False,
    "historical_draws_used": False,
    "p638_zone2": "out_of_scope",
    "arm_c": "out_of_scope",
    "secondary_events": "not_run_by_default",
    "metric_semantics": {
        "relative_lift_vs_random": "(q_b-q_r)/q_r",
        "relative_coverage_delta_vs_sidon": "(q_b-q_s)/q_s",
        "gain_over_random_ratio_to_sidon": "(q_b-q_r)/(q_s-q_r)_when_denominator_positive",
        "sealed_rel_gain_over_sidon_maps_to": "gain_over_random_ratio_to_sidon",
    },
    "lotteries": {
        "big_lotto": {
            "lottery_type": "BIG_LOTTO",
            "pool_size": 49,
            "draw_size": 6,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 12, 20],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_B649_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1",
            "sealed_sidon_source_matrix_id": "DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1",
            "sealed_arm_b_source_matrix_id": "DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1",
            "sealed_sidon_result_path": MATRIX_RESULTS
            + "diversification-constructor-frontier-b649-v1-result.json",
            "sealed_arm_b_result_path": MATRIX_RESULTS
            + "diversification-constructor-frontier-b649-v1-result.json",
            "sealed_sidon_result_blob_sha1": "169df1649ff0b8247ef5c779e8104079ae574cf4",
            "sealed_arm_b_result_blob_sha1": "169df1649ff0b8247ef5c779e8104079ae574cf4",
            "sealed_report_blob_sha1": "60289b021f7859f0b92ccf42f38add16b9a31158",
            "sealed_preregistration_hash_sha256": (
                "02b3bc90256b94864eb35e1caf940bec79f83f0315671281a49b3c0cb05b9e71"
            ),
            "sealed_q_sidon_path": "q.a.3",
            "sealed_q_arm_b_path": "q.b.3",
        },
        "daily_539": {
            "lottery_type": "DAILY_539",
            "pool_size": 39,
            "draw_size": 5,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 12],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_T539_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1",
            "sealed_sidon_source_matrix_id": "DIVERSIFICATION_COVERAGE_T539_V1",
            "sealed_arm_b_source_matrix_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1",
            "sealed_sidon_result_path": (
                MATRIX_RESULTS + "diversification-coverage-t539-v1-result.json"
            ),
            "sealed_arm_b_result_path": MATRIX_RESULTS
            + "greedy-min-overlap-constructor-t539-v1-result.json",
            "sealed_sidon_result_blob_sha1": "013f4fbc1de6d62966b4c09e6f4bca5f5ae8a032",
            "sealed_arm_b_result_blob_sha1": "346544f3a644a3083ef9863bd7f35a345a50f531",
            "sealed_sidon_report_blob_sha1": "30e92c82033c67cabc92f2ac17131c328106d739",
            "sealed_arm_b_report_blob_sha1": "c542920fc8bc900dcdb8e148cde772d22b80a731",
            "sealed_sidon_preregistration_hash_sha256": (
                "dd926b0ea045cb57be4e1cd10bc16e3d524e3b6acae5b34a805ed01f437e334e"
            ),
            "sealed_arm_b_preregistration_hash_sha256": (
                "cb786aac3fc04ea2f1c302b37120831a2296869e94e7d397260d5745420ff8bd"
            ),
            "sealed_q_sidon_path": "q_sidon.3",
            "sealed_q_arm_b_path": "q.b.3",
        },
        "power_lotto_zone1": {
            "lottery_type": "POWER_LOTTO",
            "zone": "ZONE1",
            "pool_size": 38,
            "draw_size": 6,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 17, 30],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_P638_ZONE1_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
            "sealed_sidon_source_matrix_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1",
            "sealed_arm_b_source_matrix_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
            "sealed_sidon_result_path": MATRIX_RESULTS
            + "diversification-coverage-p638-zone1-v1-result.json",
            "sealed_arm_b_result_path": MATRIX_RESULTS
            + "greedy-min-overlap-constructor-p638-zone1-v1-result.json",
            "sealed_sidon_result_blob_sha1": "f75ce278096d120ab368a058dba0f6262e9e8041",
            "sealed_arm_b_result_blob_sha1": "7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5",
            "sealed_sidon_report_blob_sha1": "ca7754640ecd41f70351330382106e28bcd4fa53",
            "sealed_arm_b_report_blob_sha1": "958a1a71b7169df352dd6a71ec196d63df7a90aa",
            "sealed_sidon_preregistration_hash_sha256": (
                "53e18558d07821460772a49f8358da3f2290b888dbde21c4497a0525c73cc992"
            ),
            "sealed_arm_b_preregistration_hash_sha256": (
                "e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b"
            ),
            "sealed_q_sidon_path": "q_sidon.3",
            "sealed_q_arm_b_path": "q.b.3",
        },
    },
}


def main() -> None:
    hash_hex = canonical_json.sha256_hex(canonical_json.canonical_bytes(LOCKED_PARAMETERS))
    record = {
        "hash_method": "LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256",
        "study_id": LOCKED_PARAMETERS["study_id"],
        "locked_parameters": LOCKED_PARAMETERS,
        "preregistration_hash_sha256": hash_hex,
    }
    serialized = json.dumps(record, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"preregistration_hash_sha256={hash_hex}")


if __name__ == "__main__":
    main()
