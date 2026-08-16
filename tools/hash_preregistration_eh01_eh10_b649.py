"""Compute and record the locked preregistration hash for

EH01_MATRIX_PROFILE_MOTIF_DISCORD_B649_V1 and
EH10_PERMUTATION_ENTROPY_ORDINAL_B649_V1
(B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1).

Run once, at lock time, before any EH01/EH10 statistic is computed on real
B649 draw values. `LOCKED_PARAMETERS` is the single source of truth
`run_eh01_eh10_b649_v1.py` imports its constants from -- never redefined a
second time, so what gets hashed and what gets run cannot drift apart.

LCJ-1 forbids binary floats, so every threshold is recorded as an exact
integer numerator/denominator pair (mirrors
`regime-changepoint-cusum-b649-v1` hash script's own convention). The exact
mathematical definitions these scalars parametrize are frozen in
`B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` (pinned by
`proposal_sha256` below) and in
`docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-preregistration.md`;
this file locks only the scalar/categorical parameters that select one exact
design out of that document's parameter space.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json

OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "eh01-eh10-b649-ordinal-temporal-v1-preregistration-hash.json"
)

LOCKED_PARAMETERS: dict[str, Any] = {
    "task_id": "B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1",
    "eh01_variant_id": "EH01_MATRIX_PROFILE_MOTIF_DISCORD_B649_V1",
    "eh10_variant_id": "EH10_PERMUTATION_ENTROPY_ORDINAL_B649_V1",
    "hypothesis_family_id": "HIGHER_ORDER_TEMPORAL_STRUCTURE",
    "lottery_type": "BIG_LOTTO",
    "proposal_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md"
    ),
    "proposal_sha256": "76629e97f0f7a44848075da6e615f9c946e2b80dedb23bc3d77a6e67104fd094",
    "owner_authorization_token": (
        "AUTHORIZE_B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1"
    ),
    # -- shared input representation (proposal section 2) --
    "input_scalar": "sum_of_six_main_numbers",
    "input_include_special": False,
    "input_order": "draw_date_ascending_then_numeric_draw_id_ascending",
    "input_calendar_gap_policy": "no_interpolation",
    # -- dataset identity (proposal prelock issue #2, now resolved) --
    "dataset_source_path": (
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
        "BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite"
    ),
    "dataset_table": "research_draw_bindings",
    "dataset_lottery_type": "BIG_LOTTO",
    "dataset_draw_data_version": "canonical-full-history-2382-draws-v1",
    "dataset_eligible_history_rule": (
        "EXCLUDE_ROWS_WHERE_DRAW_NUMBER_EQUALS_YYYYMMDD_DRAW_DATE"
    ),
    "dataset_row_count": 2138,
    "dataset_excluded_contaminant_count": 150,
    "dataset_date_range_start": "2007-03-09",
    "dataset_date_range_end": "2026-07-31",
    "dataset_logical_sha256": (
        "a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918"
    ),
    # -- implementation route (proposal prelock issues #3-4, now resolved) --
    "eh01_implementation_module": "lottolab.research.b649_eh01_matrix_profile",
    "eh10_implementation_module": "lottolab.research.b649_eh10_permutation_entropy",
    "shared_implementation_module": "lottolab.research.b649_eh01_eh10_shared",
    "dependencies_added": "none_pure_stdlib_only",
    # -- EH01 locked design (proposal section 3) --
    "eh01_representation": "chronological_main_number_sum_one_scalar_per_draw",
    "eh01_lengths": [26, 52, 104],
    "eh01_distance": "subsequence_z_normalized_euclidean_ddof0_unscaled",
    "eh01_candidate_side": "strict_left",
    "eh01_overlap": "prohibited",
    "eh01_minimum_prior_candidate_starts_equals_length": True,
    "eh01_constant_subsequence_policy": "omit_as_query_and_candidate",
    "eh01_motif_statistic": "negative_global_profile_minimum",
    "eh01_discord_statistic": "global_profile_maximum",
    "eh01_tie_break": "earliest_query_then_earliest_neighbor",
    "eh01_comparator_decision": "removed_unidentifiable_no_proxy",
    "eh01_claim_downgrade": "structural_temporal_precondition_only",
    "eh01_primary_family_size": 6,
    "eh01_robustness_family_size": 6,
    "eh01_era_min_length_draws": 312,
    # -- EH10 locked design (proposal section 4) --
    "eh10_orders": [3, 4, 5],
    "eh10_delay": 1,
    "eh10_rolling_window": 124,
    "eh10_rolling_step": 1,
    "eh10_tie_policy": "sha256_secondary_key_v1",
    "eh10_entropy_log": "natural",
    "eh10_entropy_normalizer": "ln_factorial_order",
    "eh10_statistic": "one_minus_minimum_rolling_normalized_entropy",
    "eh10_tie_break": "earliest_window_start",
    "eh10_primary_family_size": 3,
    "eh10_robustness_family_size": 3,
    "eh10_era_min_length_draws": 248,
    # -- null / surrogate policy (proposal section 5) --
    "null_primary_policy": "GLOBAL",
    "null_robustness_policy": "ERA4",
    "null_permutations_per_policy": 999,
    "null_master_seed": 6490110,
    "null_generator": "sha256_hash_sort",
    "null_tail": "one_sided_larger_or_equal",
    "null_raw_p_numerator_offset": 1,
    "null_raw_p_denominator": 1000,
    # -- era geometry (proposal section 5.2, 8) --
    "era_count": 4,
    "era_assignment_formula": "era_t_equals_min_4_floor_4_times_t_minus_1_over_n_plus_1",
    # -- multiplicity (proposal section 6) --
    "multiplicity_method": "holm_step_down",
    "multiplicity_cross_hypothesis_family": "none",
    # -- classification thresholds, exact fractions (proposal section 7) --
    "signal_primary_adjusted_p_max_numerator": 5,
    "signal_primary_adjusted_p_max_denominator": 100,
    "signal_era4_adjusted_p_max_numerator": 5,
    "signal_era4_adjusted_p_max_denominator": 100,
    "weak_signal_primary_adjusted_p_max_numerator": 10,
    "weak_signal_primary_adjusted_p_max_denominator": 100,
    # -- scope boundary --
    "predictive_advantage": "NOT_TESTED",
    "allocation_benefit": "NOT_TESTED",
    "prize_value_advantage": "NOT_TESTED",
    "economic_optimality": "NOT_TESTED",
    "combined_eh01_eh10_effect": "PROHIBITED",
    "cross_lottery_replication_this_task": "NOT_RUN",
    "production_promotion": "NO",
    "cohort_creation": "NO",
    "prospective_activation": "NO",
    "db_mutation": "NONE_READ_ONLY_QUERY_ONLY",
}


def main() -> None:
    digest = canonical_json.sha256_hex(canonical_json.canonical_bytes(LOCKED_PARAMETERS))
    record = {
        "task_id": LOCKED_PARAMETERS["task_id"],
        "eh01_variant_id": LOCKED_PARAMETERS["eh01_variant_id"],
        "eh10_variant_id": LOCKED_PARAMETERS["eh10_variant_id"],
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
