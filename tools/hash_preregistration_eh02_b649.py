"""Compute and record the locked preregistration hash for

EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_B649_V1
(EXPERIMENT_H02_V1_LOCK_EXECUTE_R1).

Run once, at lock time, before any EH02 statistic is computed on real
B649/T539/P638 draw values. `LOCKED_PARAMETERS` is the single source of
truth `run_eh02_b649_v1.py` imports its constants from -- never redefined a
second time, so what gets hashed and what gets run cannot drift apart.

LCJ-1 forbids binary floats, so every threshold is recorded as an exact
integer numerator/denominator pair (mirrors
`hash_preregistration_eh01_eh10_b649.py`'s own convention). The exact
mathematical definitions these scalars parametrize are frozen in the two
off-repo authority artifacts pinned by `authority_a_sha256` /
`authority_b_sha256` below (mirrored, byte-identical, into
`docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-preregistration.md`);
this file locks only the scalar/categorical parameters that select one
exact design out of that design space. Neutral dataset aliases (per the
Owner packet's handoff convention): Dataset A = target (B649/BIG_LOTTO),
Dataset B = source 1 (T539/DAILY_539), Dataset C = source 2 (P638
Zone-1/POWER_LOTTO_ZONE1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "eh02-b649-cross-lottery-transfer-entropy-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "task_id": "EXPERIMENT_H02_V1_LOCK_EXECUTE_R1",
    "variant_id": "EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_B649_V1",
    "hypothesis_family_id": "TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH",
    "lottery_type": "BIG_LOTTO",
    "authority_a_role": "EH02_PARAMETER_LOCK_PROPOSAL",
    "authority_a_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md"
    ),
    "authority_a_sha256": "69e03026ce40962cfed8a8295336918edc6f6db8d3d6f0f3f5a487a1bfc9262b",
    "authority_b_role": "EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION",
    "authority_b_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/"
        "B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md"
    ),
    "authority_b_sha256": "76aef07bedb10d51ab0446170c116bf9b5ffee8fc3b5c36ad8e13c14f46daae7",
    "owner_authorization_token": "AUTHORIZE_EXPERIMENT_H02_V1_LOCK_EXECUTE_R1",
    "authority_scope_note": (
        "both_authority_files_are_off_repo_untracked_by_git_pinned_by_content_"
        "sha256_instead_of_commit_per_explicit_owner_direction"
    ),
    # -- shared input representation (authority_a Sec. 2, 12) --
    "input_scalar": "sum_of_main_numbers",
    "input_include_special_or_zone2": False,
    "input_order": "draw_date_ascending_then_numeric_draw_id_ascending",
    "dataset_a_main_count": 6,
    "dataset_b_main_count": 5,
    "dataset_c_main_count": 6,
    # -- cross-lottery causal alignment (authority_a Sec. 2.3) --
    "alignment_rule": "last_strictly_prior_by_draw_date",
    "same_day_policy": "excluded",
    "timestamp_granularity": "date_only",
    # -- edges (authority_a Sec. 4) --
    "edge_1_id": "T539_TO_B649",
    "edge_1_source_lag_draws": 1,
    "edge_1_target_self_order": 1,
    "edge_2_id": "P638Z1_TO_B649",
    "edge_2_source_lag_draws": 1,
    "edge_2_target_self_order": 1,
    "reverse_edge_1_id": "B649_TO_T539_REVERSE",
    "reverse_edge_2_id": "B649_TO_P638Z1_REVERSE",
    # -- discretization (authority_a Sec. 3.1-3.3; exact index formula is this
    # task's own operationalization of "empirical tertiles", pinned before any
    # real data is read -- see b649_eh02_transfer_entropy module docstring) --
    "bins": 3,
    "alternate_bins": 2,
    "bin_edge_policy": "causal_expanding_window_per_series",
    "discretization_granularity": (
        "one_pass_per_physical_series_reused_across_forward_and_reverse_roles"
    ),
    "tertile_cutpoint_index_formula": (
        "floor_k_times_m_over_bin_count_for_k_in_1_to_bin_count_minus_1_over_tie_broken_"
        "ascending_prior_sample"
    ),
    "early_position_bin_fallback": (
        "middle_bin_when_fewer_than_2_prior_observations_always_inside_burn_in"
    ),
    "tie_policy": "sha256_secondary_key_v1_per_series_role",
    "burn_in_observations": 200,
    # -- estimator (authority_a Sec. 3.4-3.5) --
    "estimator": "discrete_plugin_conditional_transfer_entropy",
    "estimator_reference": "schreiber_2000",
    "log": "natural",
    "bias_correction": "none_surrogate_implicit",
    "comparator": "unconditioned_lagged_mutual_information",
    # -- null / surrogate policy (authority_a Sec. 5) --
    "null_primary_policy": "GLOBAL",
    "null_robustness_policy": "ERA4",
    "permutations_per_policy": 999,
    "master_seed": 6490110,
    "generator": "sha256_hash_sort_edge_and_hypothesis_salted",
    "permutation_key_index_basis": "one_indexed_global_eligible_index_position",
    "era4_key_basis": "global_position_not_per_era_local_renumbering",
    "raw_p_numerator_offset": 1,
    "raw_p_denominator": 1000,
    "null_tail": "one_sided_larger_or_equal",
    # -- era geometry (authority_a Sec. 5.2, 11) --
    "era_count": 4,
    "era_assignment_formula": "era_i_equals_min_4_floor_4_times_i_minus_1_over_n_plus_1",
    "geometry_floor_eligible_total_minimum": 800,
    "geometry_floor_eligible_per_era_minimum": 30,
    # -- timing control (authority_a Sec. 6) --
    "timing_control_stale_days": 28,
    "timing_control_gate": "observed_te_greater_than_stale_te",
    # -- directionality control (authority_a Sec. 7) --
    "directionality_control_estimator": "same_discrete_plugin_transfer_entropy_role_swapped",
    "directionality_reverse_p_min_numerator": 10,
    "directionality_reverse_p_min_denominator": 100,
    "directionality_control_gate": (
        "forward_raw_p_less_than_reverse_raw_p_and_reverse_raw_p_greater_than_"
        "directionality_reverse_p_min"
    ),
    # -- multiplicity (authority_a Sec. 9) --
    "multiplicity_method": "holm_step_down",
    "primary_family_size": 2,
    "robustness_family_size": 2,
    "cross_edge_family": "none",
    "timing_and_directionality_are_holm_members": False,
    # -- classification thresholds, exact fractions (authority_a Sec. 10) --
    "signal_global_holm_max_numerator": 5,
    "signal_global_holm_max_denominator": 100,
    "signal_era4_holm_max_numerator": 5,
    "signal_era4_holm_max_denominator": 100,
    "weak_signal_global_holm_max_numerator": 10,
    "weak_signal_global_holm_max_denominator": 100,
    # -- dataset identity (resolves authority_a prelock issues 2-3, per
    # authority_b Sec. 1, 2, 3, 5.1) --
    "dataset_a_identity": "BIG_LOTTO",
    "dataset_a_source_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
        "BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite"
    ),
    "dataset_a_table": "research_draw_bindings",
    "dataset_a_filter": "big_lotto_canonical_full_history_2382_draws_v1_exclude_date_like",
    "dataset_a_row_count": 2138,
    "dataset_a_date_range_start": "2007-03-09",
    "dataset_a_date_range_end": "2026-07-31",
    "dataset_a_logical_sha256": (
        "a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918"
    ),
    "dataset_b_identity": "DAILY_539",
    "dataset_b_source_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
        "T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3"
    ),
    "dataset_b_table": "source_draws",
    "dataset_b_filter": "lottery_type_daily_539",
    "dataset_b_row_count": 5930,
    "dataset_b_date_range_start": "2007-01-01",
    "dataset_b_date_range_end": "2026-08-01",
    "dataset_b_logical_sha256": (
        "794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42"
    ),
    "dataset_c_identity": "POWER_LOTTO_ZONE1",
    "dataset_c_source_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
        "P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3"
    ),
    "dataset_c_table": "draws",
    "dataset_c_filter": "zone1_only_zone2_out_of_scope",
    "dataset_c_row_count": 1933,
    "dataset_c_date_range_start": "2008-01-24",
    "dataset_c_date_range_end": "2026-07-30",
    "dataset_c_logical_sha256": (
        "49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0"
    ),
    # -- expected eligibility, independently reproduced by the runner before
    # any statistic is computed (authority_b Sec. 4) --
    "edge_1_expected_eligible_post_burn_in": 1937,
    "edge_1_expected_era4_partition_sizes": [485, 484, 484, 484],
    "edge_2_expected_eligible_post_burn_in": 1846,
    "edge_2_expected_era4_partition_sizes": [462, 461, 462, 461],
    # -- implementation route (resolves authority_a prelock issues 4-6) --
    "implementation_module": "lottolab.research.b649_eh02_transfer_entropy",
    "dataset_module": "lottolab.research.b649_eh02_dataset",
    "runner_path": "tools/run_eh02_b649_v1.py",
    "dependencies_added": "none_pure_stdlib_only",
    "synthetic_fixture_check": "PASS_REQUIRED_BEFORE_REAL_DATA_READ",
    # -- scope boundary (authority_a Sec. 15, 17) --
    "predictive_advantage": "NOT_TESTED",
    "allocation_benefit": "NOT_TESTED",
    "prize_value_advantage": "NOT_TESTED",
    "universal_cross_lottery_causality": "NOT_TESTED",
    "arbitrary_lag_generalization": "NOT_TESTED",
    "combined_edge_effect": "PROHIBITED",
    "production_promotion": "NO",
    "cohort_creation": "NO",
    "prospective_activation": "NO",
    "parameter_rescue_run": "NO",
    "db_mutation": "NONE_READ_ONLY_QUERY_ONLY",
}


def main() -> None:
    digest = canonical_json.sha256_hex(canonical_json.canonical_bytes(LOCKED_PARAMETERS))
    record = {
        "task_id": LOCKED_PARAMETERS["task_id"],
        "variant_id": LOCKED_PARAMETERS["variant_id"],
        "locked_parameters": LOCKED_PARAMETERS,
        "preregistration_hash_sha256": digest,
        "hash_method": "LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(record, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"preregistration_hash_sha256={digest}")


if __name__ == "__main__":
    main()
