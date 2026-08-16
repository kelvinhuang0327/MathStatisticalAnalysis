"""Compute and write the lock hash for STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1.

Mirrors the established pattern
(`hash_preregistration_low_overlap_geometry_mechanism_v1.py`,
`hash_preregistration_t539_arm_b.py`, `hash_preregistration_p638_arm_b.py`):
build a strict, LCJ-1-domain `locked_parameters` mapping, hash its canonical
bytes, and write the sidecar `-preregistration-hash.json`. This is the one
lock artifact `run_higher_order_residual_mechanism_v1.py` re-verifies before
touching any native constructor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "higher-order-residual-mechanism-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "study_id": "STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1",
    "task_id": "STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_LOCK_EXECUTE_R1",
    "owner_authorization": (
        "AUTHORIZE_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_LOCK_EXECUTE_R1"
    ),
    "hypothesis_family_id": "DIVERSIFICATION",
    "source_type": "STRATEGY_MATRIX_NATIVE_MECHANISM",
    "evidence_type": "EXACT_COMBINATORIAL",
    "design_commit": "21cc748bdeb3a81688b62a077665e61a9d079bb9",
    "canonical_input_commit": "81104798a9f265de400c1a8bc476e109b14e1a4a",
    "canonical_input_tree": "a82dc823bab4d396ac63a8856d507b43d393047d",
    "exposure_ladder": [1, 3, 5, 10, 15, 20],
    "primary_event_minimum_matches": 3,
    "delta_direction": "arm_b_minus_sidon",
    "portfolio_mode": "nested_prefix",
    "duplicate_tickets_invariant": 0,
    "monte_carlo": False,
    "historical_draws_used": False,
    "native_winning_space_enumeration": False,
    "p638_zone2": "out_of_scope",
    "arm_c": "out_of_scope",
    "j4_geometry": "out_of_scope",
    "secondary_events": "not_run_by_default",
    "invalid_shape_behavior": "stop_no_silent_skip",
    "primary_geometry_order": 3,
    "sealed_phase5": {
        "study_id": "STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1",
        "result_path": (
            "docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json"
        ),
        "result_blob_sha1": "dc17f0b39c9baf81f8c85162d5db554e7ca2797a",
        "report_path": (
            "docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-report.md"
        ),
        "report_blob_sha1": "0243589b14068ea6a3f32d8af37e4db9b7569065",
        "preregistration_path": (
            "docs/research/matrix-native-results/"
            "low-overlap-geometry-mechanism-v1-preregistration.md"
        ),
        "preregistration_blob_sha1": "17b1ae14523bcd63f48d226a3134a2c5531ee654",
        "preregistration_hash_path": (
            "docs/research/matrix-native-results/"
            "low-overlap-geometry-mechanism-v1-preregistration-hash.json"
        ),
        "preregistration_hash_blob_sha1": "c26e61a62dbebcfa44881d5a23f044a0ed52e04f",
        "preregistration_hash_sha256": (
            "8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be"
        ),
        "module_path": "src/lottolab/research/low_overlap_geometry_mechanism.py",
        "module_blob_sha1": "20b6e0d70b17ef4e34c4d3d6f89196685c5bd22c",
        "s3_multiplicity_json_path": (
            'per_lottery.{lottery}.per_k.{k}.arms.{arm}.collision_moments."3"'
        ),
        "max_pairwise_overlap_json_path": (
            "per_lottery.{lottery}.per_k.{k}.arms.{arm}.geometry.max_pairwise_overlap"
        ),
        "portfolio_sha256_json_path": "per_lottery.{lottery}.portfolio_sha256.{arm}",
        "t3_t4_t5_h_json_path": (
            "per_lottery.{lottery}.per_k.{k}.comparison.higher_order_signed_terms"
        ),
        "delta_covered_json_path": "per_lottery.{lottery}.per_k.{k}.comparison.delta_covered",
        "mechanism_descriptor_json_path": (
            "per_lottery.{lottery}.per_k.{k}.comparison.mechanism_descriptor"
        ),
    },
    "higher_order_module_path": "src/lottolab/research/higher_order_residual_mechanism.py",
    "higher_order_module_blob_sha1": "2bc6eb7857ba373b723ac9e4d6c4dc89080e464c",
    "lotteries": {
        "big_lotto": {
            "lottery_type": "BIG_LOTTO",
            "pool_size": 49,
            "draw_size": 6,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 12, 20],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_B649_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1",
            "sidon_module_path": "src/lottolab/research/cyclic_sidon_shift.py",
            "sidon_module_blob_sha1": "d07efb5c71a0b25bb00ba3823e208c57aabb306e",
            "arm_b_module_path": "src/lottolab/research/greedy_min_overlap_constructor.py",
            "arm_b_module_blob_sha1": "5511f67d981f7f8a1c33183c966d76ee50249d7d",
        },
        "daily_539": {
            "lottery_type": "DAILY_539",
            "pool_size": 39,
            "draw_size": 5,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 12],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_T539_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1",
            "sidon_module_path": "src/lottolab/research/cyclic_sidon_shift_t539.py",
            "sidon_module_blob_sha1": "f6b95bed2e0d51ed81781efd096d4f87d88606a1",
            "arm_b_module_path": "src/lottolab/research/greedy_min_overlap_constructor_t539.py",
            "arm_b_module_blob_sha1": "372542aa0c164d3548a6aaa91dd56b28821d0eaa",
        },
        "power_lotto_zone1": {
            "lottery_type": "POWER_LOTTO",
            "zone": "ZONE1",
            "pool_size": 38,
            "draw_size": 6,
            "sidon_base_set_0_indexed": [0, 1, 3, 7, 17, 30],
            "sidon_constructor_id": "CYCLIC_SIDON_SHIFT_P638_ZONE1_V1",
            "arm_b_constructor_id": "GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1",
            "sidon_module_path": "src/lottolab/research/cyclic_sidon_shift_p638.py",
            "sidon_module_blob_sha1": "736d0c7e8efc79f68e989921be3e5e0742617e97",
            "arm_b_module_path": (
                "src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py"
            ),
            "arm_b_module_blob_sha1": "622898a9f0a9f4c72af456a21af83c0fc63c7d45",
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
