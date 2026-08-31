"""Validate canonical Runner R2 documents and emit their embedded artifact.

The assembler consumes exactly four unwrapped documents produced by the
``NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R2`` Runner: Plan, Run A,
Run B, and Acceptance. Runner field names and self-hash keys are used
directly. There is no compatibility schema, translation step, or second
accepted-evidence representation.

After validation, the canonical artifact is
``run_a.deterministic_payload.artifact``. Run B must contain byte-identical
deterministic payload and artifact content. Synthetic documents are accepted
only when the caller explicitly selects the synthetic-test execution path;
the default path requires real ``PASS`` evidence.

This module never imports or runs a strategy, opens the replay database, or
writes packaged V1 evidence.
"""

from __future__ import annotations

import argparse
import copy
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.evidence.canonical_json import (
    canonical_bytes,
    canonical_file_bytes,
    loads_canonical,
    self_key_removed_sha256,
    sha256_hex,
    validate_value_domain,
)

PROTOCOL_VERSION = "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R2"
OLD_PROTOCOL_VERSIONS = frozenset(
    {
        "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R1",
        "NEXT_DRAW_REPLAY_STRATEGY_ISOLATED_MANIFEST_SEED_V1",
    }
)
PLAN_MANIFEST_SCHEMA_VERSION = "NEXT_DRAW_54_REPLAY_PLAN_MANIFEST_V2"
RUN_MANIFEST_SCHEMA_VERSION = "NEXT_DRAW_54_REPLAY_RUN_MANIFEST_V2"
ACCEPTANCE_MANIFEST_SCHEMA_VERSION = "NEXT_DRAW_54_REPLAY_ACCEPTANCE_MANIFEST_V2"
CANONICALIZATION_VERSION = "LCJ-1"

REPOSITORY_HEAD = "ba2f88f2622c278b358b2513bac3369196399439"
REPOSITORY_TREE = "9fed7b2e1f258fd7c80efbfa74d75d2000b16d04"
CATALOG_GIT_BLOB = "0c44bededa43ae9cad5cde7fc412424ffcde7560"
CATALOG_SHA256 = "8e3a7a60b9c5b25bbf0c71bfa3a158bdd7ee40e11ab7dd6ef43d5bef9c83a448"
UV_LOCK_SHA256 = "1566430ccbfeca9dc0613c58a743c7684a0648b466ede6d3fc7763c4a5a7ead8"

EXPECTED_STRATEGY_COUNT = 54
EXPECTED_RECORD_COUNT = 55
EXPECTED_REPLAY_DEPTH = 800
EXPECTED_EVALUATED_CELL_COUNT = EXPECTED_STRATEGY_COUNT * EXPECTED_REPLAY_DEPTH
EXPECTED_ZONE_ORDINAL = 19
ZONE_STRATEGY_ID = "legacy_biglotto__zone_momentum_predict__9e89f2b41add"
ZONE_STATUS = "DRIVER_ERROR"
EXPECTED_HIT_TIER_ID = "M3_PLUS"
EXPECTED_EVALUATOR_SEMANTIC_VERSION = "base_method_evaluation/1.0.0"
EXPECTED_RANDOM_REFERENCE = Fraction(4654, 249711)
EXPECTED_WINDOW_ORDER = (
    "WINDOW_50",
    "WINDOW_300",
    "WINDOW_750",
    "FULL_HISTORY",
)
EXPECTED_WINDOW_ELIGIBLE_COUNTS = (50, 300, 750, EXPECTED_REPLAY_DEPTH)

EXPECTED_STRATEGY_IDS = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet2",
    "biglotto_zone_split_3bet_bet3",
    "biglotto_deviation_2bet",
    "biglotto_deviation_2bet_bet2",
    "biglotto_p0_2bet_bet1",
    "biglotto_p0_2bet_bet2",
    "legacy_biglotto__graph_predictor__cd70713a5709",
    "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
    "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
    "legacy_biglotto__optimized_ensemble__e05e0fde22d7",
    "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
    "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
    "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
    "legacy_biglotto__pure_cold_predict__9e89f2b41add",
    "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
    "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
    "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
    "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs",
    "biglotto_wave2_neighbor_ad_cooccurrence_conditional",
    "biglotto_wave2_neighbor_ad_cooccurrence_top_pairs",
    "biglotto_wave2_neighbor_ad_cooccurrence_transition_pairs",
    "biglotto_wave2_neighbor_ad_cooccurrence_triplet",
    "biglotto_wave2_neighbor_ad_graph_bridge_bet",
    "biglotto_wave2_neighbor_ad_graph_centrality_bet",
    "biglotto_wave2_neighbor_ad_graph_pagerank_bet",
    "biglotto_wave2_sum_range_ad_structural_sum_regression",
    "biglotto_wave2_social_ad_negative_consensus_remove",
    "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c",
    "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef",
    "legacy_biglotto__frontend_bayesian_strategy__baa3045817fb",
    "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1",
    "legacy_biglotto__frontend_deviation_strategy__3c895052122e",
    "legacy_biglotto__frontend_hot_cold_mix_strategy__92e0540fac02",
    "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0",
    "legacy_biglotto__frontend_sum_range_strategy__4941213e6c46",
    "legacy_biglotto__frontend_zone_balance_strategy__6a016aa83b3e",
    "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96",
    "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e",
    "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a",
    "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b",
    "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7",
    "legacy_biglotto__frontend_unified_ensemble_combined__8f1183a9d8a7",
    "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7",
    "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba",
    "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
)
EXPECTED_STRATEGY_ORDER_SHA256 = (
    "1efeba5519693c58f1b407f859d5b37f54647efcd4a34b424b9eed71ff7c9493"
)
EXPECTED_STRATEGY_UNIVERSE_SHA256 = (
    "02cf7c5403e4714416824ae1a71ef7478a4a975ff973b7f237f9992b6f9dd0a9"
)
EXPECTED_RNG_CLASSIFICATION_SHA256 = (
    "cda9f5ff34784da35ef762425d1e5e6b3539a20e6bdd5fcad82bbb10f92c86d7"
)

SYNTHETIC_DATA_KIND = "SYNTHETIC_TEST_ONLY"
REAL_DATA_KIND = "SEALED_READ_ONLY_DB"
SYNTHETIC_FINAL_STATUS = "SYNTHETIC_TEST_ONLY"
REAL_FINAL_STATUS = "PASS"
SYNTHETIC_COMPUTATION_STATUS = "SYNTHETIC_TEST_ONLY"
REAL_COMPUTATION_STATUS = "FRESH_UNREVIEWED"
ARTIFACT_SCHEMA_VERSION = "1.0.0"

PRIVATE_RNG_STRATEGY_IDS = (
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet2",
    "biglotto_zone_split_3bet_bet3",
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
)
GLOBAL_RNG_STRATEGY_IDS = frozenset(
    {
        "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96",
        "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e",
        "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a",
        "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b",
        "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7",
        "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7",
        "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9",
        "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
        "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba",
        "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
    }
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
_DECIMAL_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")


def _keys(names: str) -> frozenset[str]:
    return frozenset(names.split())


PLAN_KEYS = _keys(
    "manifest_schema_version canonicalization_version protocol_version plan_manifest_sha256 "
    "common_manifest common_manifest_sha256 authority dataset targets strategies rng "
    "runtime_fingerprint runtime_fingerprint_sha256 execution evaluation"
)
RUN_KEYS = _keys(
    "manifest_schema_version canonicalization_version protocol_version run_manifest_sha256 "
    "plan_manifest_sha256 common_manifest_sha256 campaign_label operational_envelope "
    "deterministic_payload deterministic_payload_sha256"
)
ACCEPTANCE_KEYS = _keys(
    "manifest_schema_version canonicalization_version protocol_version "
    "acceptance_manifest_sha256 plan_manifest_sha256 common_manifest_sha256 "
    "run_a_manifest_file_sha256 run_b_manifest_file_sha256 "
    "run_a_deterministic_payload_sha256 run_b_deterministic_payload_sha256 "
    "comparison_contract comparison_results old_84_reuse_attestation final_status"
)
COMMON_KEYS = _keys(
    "canonicalization_version protocol_version repository_head repository_tree "
    "source_draw_db_sha256 dataset_snapshot_sha256 target_count target_order_sha256 "
    "strategy_count strategy_order_sha256 strategy_universe_sha256 "
    "rng_classification_sha256 runtime_fingerprint_sha256 process_model seed_timing "
    "global_random_policy cache_policy strategy_parallelization max_concurrency "
    "failure_restart_boundary metric_contract window_order excluded_strategy_id old_84_reuse"
)
AUTHORITY_KEYS = _keys(
    "repository_head repository_tree catalog_git_blob catalog_sha256 uv_lock_sha256 "
    "load_bearing_blobs source_inventory_sha256"
)
DATASET_KEYS = _keys(
    "dataset_id dataset_version snapshot dataset_snapshot_sha256 source_db "
    "rule_contract rule_contract_sha256"
)
SNAPSHOT_KEYS = _keys("snapshot_schema_version kind lottery_type draws")
DRAW_KEYS = _keys("source_row_id draw_date draw_number main_numbers special_number")
SOURCE_DB_KEYS = _keys("sha256 size_bytes read_only sqlite_mode")
TARGET_KEYS = _keys("order count vector target_order_sha256")
TARGET_IDENTITY_KEYS = _keys("draw_date draw_number")
STRATEGIES_KEYS = _keys(
    "count records names excluded strategy_order_sha256 strategy_universe_sha256 "
    "rng_classification rng_classification_sha256"
)
STRATEGY_IDENTITY_KEYS = _keys(
    "strategy_id strategy_version adapter_path min_history native_ticket_count response_shape"
)
STRATEGY_NAME_KEYS = _keys("strategy_id strategy_name")
RNG_CLASSIFICATION_KEYS = _keys("strategy_id strategy_version rng_class")
EXCLUDED_KEYS = _keys("strategy_id strategy_name filtered_catalog_ordinal status windows")
RNG_KEYS = _keys(
    "seed_policy seed_timing global_random_policy private_rng_policy "
    "private_rng_exceptions seeds"
)
RNG_SEED_KEYS = _keys(
    "strategy_id strategy_version adapter_path seed_digest seed_integer"
)
RUNTIME_KEYS = _keys(
    "schema_version python platform numeric distributions installer environment "
    "source_inventory_sha256 runner_files"
)
RUNNER_FILE_KEYS = _keys("path sha256")
OPERATIONAL_KEYS = _keys(
    "run_id output_root source_root source_db_path host_label started_at_utc "
    "ended_at_utc elapsed_ns attempts"
)
ATTEMPT_KEYS = _keys(
    "attempt_id strategy_id ordinal pid started_at_utc ended_at_utc elapsed_ns "
    "exit_status status failure_kind previous_attempt_id result_sha256 "
    "partial_output_sha256 bootstrap_before_sha256 bootstrap_after_sha256"
)
DETERMINISTIC_PAYLOAD_KEYS = _keys(
    "runtime_fingerprint authority strategy_results matrix_order matrix_cell_count matrix "
    "matrix_sha256 evaluation_records evaluation_sha256 excluded_strategy artifact "
    "artifact_content_sha256 artifact_file_sha256 old_84_reuse final_status"
)
EVALUATION_RECORD_KEYS = _keys("strategy_id windows")
EVALUATION_WINDOW_KEYS = _keys(
    "window success_count eligible_draw_count observed_value"
)
ARTIFACT_KEYS = _keys(
    "artifact_schema_version evaluator_version window_order computation_status lottery_type "
    "source_draw_db_sha256 source_draw_count last_causal_draw_id replay_depth hit_tier_id "
    "records artifact_sha256"
)
ARTIFACT_RECORD_KEYS = _keys(
    "strategy_id strategy_name native_ticket_count status hit_tier_id windows"
)
ARTIFACT_WINDOW_KEYS = _keys(
    "window_kind window_status eligible_draw_count observed_value random_reference "
    "delta_vs_random"
)
COMPARISON_RESULTS_KEYS = _keys(
    "equal run_a_accepted_cell_count run_b_accepted_cell_count total_empirical_cell_count "
    "evaluated_strategy_count source_db_unchanged artifact_bytes_equal"
)

EXPECTED_RULE_CONTRACT: dict[str, object] = {
    "lottery_type": "BIG_LOTTO",
    "main_number_count": 6,
    "main_number_min": 1,
    "main_number_max": 49,
    "main_numbers_unique": True,
    "special_number_count": 1,
    "special_number_min": 1,
    "special_number_max": 49,
    "main_special_overlap": False,
}
EXPECTED_EXECUTION: dict[str, object] = {
    "process_model": "ONE_PROCESS_PER_STRATEGY",
    "launch_method": "POSIX_SPAWN_EXEC",
    "strategies_per_child": 1,
    "targets_per_child": EXPECTED_REPLAY_DEPTH,
    "replay_calls_per_child": 1,
    "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
    "global_random_policy": (
        "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
    ),
    "cache_policy": "NO_REPLAY_RESULT_CACHE",
    "cache_configured": False,
    "strategy_parallelization": "SERIAL_ONLY",
    "max_concurrency": 1,
    "failure_restart_boundary": "ENTIRE_STRATEGY_PROCESS",
    "checkpoint_resume": False,
    "cell_retry": False,
    "nested_parallelism": False,
    "maximum_history_draws": "NONE",
    "minimum_history_draws": "DESCRIPTOR_MIN_HISTORY",
    "preflight_all_cells": True,
    "old_84_reuse": False,
}
EXPECTED_EVALUATION: dict[str, object] = {
    "metric_contract": EXPECTED_HIT_TIER_ID,
    "evaluator_version": EXPECTED_EVALUATOR_SEMANTIC_VERSION,
    "window_order": list(EXPECTED_WINDOW_ORDER),
    "random_reference": {
        "numerator": str(EXPECTED_RANDOM_REFERENCE.numerator),
        "denominator": str(EXPECTED_RANDOM_REFERENCE.denominator),
    },
}
EXPECTED_COMPARISON_RESULTS: dict[str, object] = {
    "equal": True,
    "run_a_accepted_cell_count": EXPECTED_EVALUATED_CELL_COUNT,
    "run_b_accepted_cell_count": EXPECTED_EVALUATED_CELL_COUNT,
    "total_empirical_cell_count": EXPECTED_EVALUATED_CELL_COUNT * 2,
    "evaluated_strategy_count": EXPECTED_STRATEGY_COUNT,
    "source_db_unchanged": True,
    "artifact_bytes_equal": True,
}


class EvidenceAssemblyError(ValueError):
    """A direct canonical Runner document or embedded artifact is invalid."""


@dataclass(frozen=True, slots=True)
class _ValidatedPlan:
    payload: dict[str, Any]
    synthetic: bool
    strategy_names: tuple[str, ...]
    source_draw_count: int
    last_causal_draw_id: str


@dataclass(frozen=True, slots=True)
class _ValidatedRun:
    payload: dict[str, Any]
    deterministic_payload: dict[str, Any]
    artifact: dict[str, Any]
    run_id: str
    output_root: str
    attempt_ids: frozenset[str]


def _as_dict(value: object, *, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise EvidenceAssemblyError(f"{path}: expected object")
    return cast(dict[str, Any], value)


def _as_list(value: object, *, path: str) -> list[Any]:
    if type(value) is not list:
        raise EvidenceAssemblyError(f"{path}: expected array")
    return cast(list[Any], value)


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], *, path: str
) -> None:
    actual = set(value)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        raise EvidenceAssemblyError(
            f"{path}: canonical Runner keys mismatch; missing={missing}, extra={extra}"
        )


def _require_string(value: object, *, path: str, empty: bool = False) -> str:
    if type(value) is not str:
        raise EvidenceAssemblyError(f"{path}: expected NUL-free string")
    if (not empty and not value) or "\x00" in value:
        raise EvidenceAssemblyError(f"{path}: expected NUL-free string")
    return value


def _require_int(value: object, *, path: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 9_007_199_254_740_991:
        raise EvidenceAssemblyError(f"{path}: expected integer >= {minimum}")
    return value


def _require_hash(value: object, *, path: str) -> str:
    candidate = _require_string(value, path=path)
    if _HASH_RE.fullmatch(candidate) is None:
        raise EvidenceAssemblyError(f"{path}: expected lowercase SHA-256")
    return candidate


def _digest(value: object) -> str:
    return sha256_hex(canonical_bytes(value))


def _file_digest(value: object) -> str:
    return sha256_hex(canonical_file_bytes(value))


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _require_equal(actual: object, expected: object, *, path: str) -> None:
    if not _canonical_equal(actual, expected):
        raise EvidenceAssemblyError(f"{path}: mismatch")


def _validate_protocol(value: object, *, path: str) -> None:
    token = _require_string(value, path=path)
    if token != PROTOCOL_VERSION:
        if token in OLD_PROTOCOL_VERSIONS:
            raise EvidenceAssemblyError(f"{path}: superseded protocol is forbidden")
        raise EvidenceAssemblyError(f"{path}: only canonical R2 is accepted")


def _validate_self_hash(payload: dict[str, Any], key: str, *, path: str) -> None:
    declared = _require_hash(payload.get(key), path=f"{path}.{key}")
    if declared != self_key_removed_sha256(payload, key):
        raise EvidenceAssemblyError(f"{path}.{key}: self hash mismatch")


def _validate_fraction(
    value: object,
    *,
    path: str,
    expected: Fraction | None = None,
) -> Fraction:
    pair = _as_dict(value, path=path)
    _require_exact_keys(pair, _keys("numerator denominator"), path=path)
    numerator = _require_string(pair["numerator"], path=f"{path}.numerator", empty=True)
    denominator = _require_string(pair["denominator"], path=f"{path}.denominator")
    if _DECIMAL_RE.fullmatch(numerator) is None or _DECIMAL_RE.fullmatch(denominator) is None:
        raise EvidenceAssemblyError(f"{path}: fraction components must be canonical decimals")
    denominator_int = int(denominator)
    if denominator_int <= 0:
        raise EvidenceAssemblyError(f"{path}: denominator must be positive")
    result = Fraction(int(numerator), denominator_int)
    if numerator != str(result.numerator) or denominator != str(result.denominator):
        raise EvidenceAssemblyError(f"{path}: fraction must be reduced")
    if expected is not None and result != expected:
        raise EvidenceAssemblyError(f"{path}: frozen fraction mismatch")
    return result


def _rng_class(strategy_id: str) -> str:
    if strategy_id in PRIVATE_RNG_STRATEGY_IDS:
        return "ADAPTER_LOCAL_DETERMINISTIC_RNG"
    if strategy_id in GLOBAL_RNG_STRATEGY_IDS:
        return "PROCESS_GLOBAL_PYTHON_RANDOM"
    return "NO_RNG"


def _validate_inventory(value: object, *, path: str, git: bool = False) -> None:
    rows = _as_list(value, path=path)
    if not rows:
        raise EvidenceAssemblyError(f"{path}: inventory must not be empty")
    paths: list[str] = []
    expected_keys = _keys("path sha256 git_blob mode" if git else "path sha256")
    for index, raw in enumerate(rows):
        row_path = f"{path}[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, expected_keys, path=row_path)
        relative = _require_string(row["path"], path=f"{row_path}.path")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise EvidenceAssemblyError(f"{row_path}.path: must be contained and relative")
        paths.append(relative)
        _require_hash(row["sha256"], path=f"{row_path}.sha256")
        if git:
            blob = _require_string(row["git_blob"], path=f"{row_path}.git_blob")
            if _GIT_BLOB_RE.fullmatch(blob) is None:
                raise EvidenceAssemblyError(f"{row_path}.git_blob: expected Git blob SHA-1")
            if row["mode"] not in ("100644", "100755"):
                raise EvidenceAssemblyError(f"{row_path}.mode: regular file mode required")
    if paths != sorted(set(paths)):
        raise EvidenceAssemblyError(f"{path}: paths must be unique and sorted")


def _validate_authority(value: object, *, path: str) -> dict[str, Any]:
    authority = _as_dict(value, path=path)
    _require_exact_keys(authority, AUTHORITY_KEYS, path=path)
    expected = {
        "repository_head": REPOSITORY_HEAD,
        "repository_tree": REPOSITORY_TREE,
        "catalog_git_blob": CATALOG_GIT_BLOB,
        "catalog_sha256": CATALOG_SHA256,
        "uv_lock_sha256": UV_LOCK_SHA256,
    }
    for key, expected_value in expected.items():
        if authority[key] != expected_value:
            raise EvidenceAssemblyError(f"{path}.{key}: frozen Runner authority mismatch")
    inventory = authority["load_bearing_blobs"]
    _validate_inventory(inventory, path=f"{path}.load_bearing_blobs", git=True)
    if authority["source_inventory_sha256"] != _digest(inventory):
        raise EvidenceAssemblyError(f"{path}.source_inventory_sha256: hash mismatch")
    return authority


def _draw_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return cast(str, row["draw_date"]), int(cast(str, row["draw_number"]))


def _frozen_targets(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    # This is intentionally TEXT order, matching the pinned Runner's page-1 query.
    newest = sorted(
        rows,
        key=lambda row: (
            cast(str, row["draw_date"]),
            cast(str, row["draw_number"]),
            cast(int, row["source_row_id"]),
        ),
        reverse=True,
    )[:EXPECTED_REPLAY_DEPTH]
    return [
        {
            "draw_date": cast(str, row["draw_date"]),
            "draw_number": cast(str, row["draw_number"]),
        }
        for row in reversed(newest)
    ]


def _validate_dataset(
    value: object, *, path: str
) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
    dataset = _as_dict(value, path=path)
    _require_exact_keys(dataset, DATASET_KEYS, path=path)
    if dataset["dataset_id"] != "NEXT_DRAW_BIG_LOTTO_R2":
        raise EvidenceAssemblyError(f"{path}.dataset_id: mismatch")
    snapshot = _as_dict(dataset["snapshot"], path=f"{path}.snapshot")
    _require_exact_keys(snapshot, SNAPSHOT_KEYS, path=f"{path}.snapshot")
    if snapshot["snapshot_schema_version"] != "NEXT_DRAW_54_SOURCE_SNAPSHOT_V2":
        raise EvidenceAssemblyError(f"{path}.snapshot: schema mismatch")
    kind = snapshot["kind"]
    if kind not in (REAL_DATA_KIND, SYNTHETIC_DATA_KIND):
        raise EvidenceAssemblyError(f"{path}.snapshot.kind: invalid execution kind")
    if snapshot["lottery_type"] != "BIG_LOTTO":
        raise EvidenceAssemblyError(f"{path}.snapshot.lottery_type: mismatch")
    draws = _as_list(snapshot["draws"], path=f"{path}.snapshot.draws")
    if len(draws) < EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError(f"{path}.snapshot.draws: at least 800 draws required")
    row_ids: set[int] = set()
    draw_numbers: set[str] = set()
    numeric_draw_numbers: set[int] = set()
    validated_draws: list[dict[str, Any]] = []
    for index, raw in enumerate(draws):
        row_path = f"{path}.snapshot.draws[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, DRAW_KEYS, path=row_path)
        row_id = _require_int(row["source_row_id"], path=f"{row_path}.source_row_id", minimum=1)
        draw_number = _require_string(row["draw_number"], path=f"{row_path}.draw_number")
        if not draw_number.isascii() or not draw_number.isdecimal() or int(draw_number) <= 0:
            raise EvidenceAssemblyError(f"{row_path}.draw_number: positive decimal required")
        numeric_draw_number = int(draw_number)
        if (
            row_id in row_ids
            or draw_number in draw_numbers
            or numeric_draw_number in numeric_draw_numbers
        ):
            raise EvidenceAssemblyError(f"{row_path}: duplicate source or draw identity")
        row_ids.add(row_id)
        draw_numbers.add(draw_number)
        numeric_draw_numbers.add(numeric_draw_number)
        draw_date = _require_string(row["draw_date"], path=f"{row_path}.draw_date")
        try:
            if date.fromisoformat(draw_date).isoformat() != draw_date:
                raise ValueError
        except ValueError as exc:
            raise EvidenceAssemblyError(f"{row_path}.draw_date: ISO date required") from exc
        main_numbers = _as_list(row["main_numbers"], path=f"{row_path}.main_numbers")
        if (
            len(main_numbers) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in main_numbers)
            or len(set(main_numbers)) != 6
        ):
            raise EvidenceAssemblyError(f"{row_path}.main_numbers: illegal ticket")
        special = _require_int(
            row["special_number"], path=f"{row_path}.special_number", minimum=1
        )
        if special > 49 or special in main_numbers:
            raise EvidenceAssemblyError(f"{row_path}.special_number: illegal special number")
        validated_draws.append(row)
    if validated_draws != sorted(validated_draws, key=_draw_key):
        raise EvidenceAssemblyError(
            f"{path}.snapshot.draws: causal rows must be oldest first"
        )
    if dataset["dataset_version"] != _digest(snapshot):
        raise EvidenceAssemblyError(f"{path}.dataset_version: hash mismatch")
    if dataset["dataset_snapshot_sha256"] != _digest(snapshot):
        raise EvidenceAssemblyError(f"{path}.dataset_snapshot_sha256: hash mismatch")
    source_db = _as_dict(dataset["source_db"], path=f"{path}.source_db")
    _require_exact_keys(source_db, SOURCE_DB_KEYS, path=f"{path}.source_db")
    _require_hash(source_db["sha256"], path=f"{path}.source_db.sha256")
    _require_int(source_db["size_bytes"], path=f"{path}.source_db.size_bytes", minimum=1)
    if source_db["read_only"] is not True or source_db["sqlite_mode"] != "ro_immutable_no_wal":
        raise EvidenceAssemblyError(f"{path}.source_db: sealed read-only contract required")
    _require_equal(dataset["rule_contract"], EXPECTED_RULE_CONTRACT, path=f"{path}.rule_contract")
    if dataset["rule_contract_sha256"] != _digest(EXPECTED_RULE_CONTRACT):
        raise EvidenceAssemblyError(f"{path}.rule_contract_sha256: hash mismatch")
    return dataset, kind == SYNTHETIC_DATA_KIND, validated_draws


def _validate_strategies(value: object, *, path: str) -> tuple[str, ...]:
    strategies = _as_dict(value, path=path)
    _require_exact_keys(strategies, STRATEGIES_KEYS, path=path)
    if strategies["count"] != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}.count: exactly 54 strategies required")
    records = _as_list(strategies["records"], path=f"{path}.records")
    if len(records) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}.records: exactly 54 strategies required")
    identities: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        row_path = f"{path}.records[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, STRATEGY_IDENTITY_KEYS, path=row_path)
        for key in ("strategy_id", "strategy_version", "adapter_path"):
            _require_string(row[key], path=f"{row_path}.{key}")
        _require_int(row["min_history"], path=f"{row_path}.min_history", minimum=1)
        if row["native_ticket_count"] != 1 or row["response_shape"] != "SINGLE_TICKET":
            raise EvidenceAssemblyError(f"{row_path}: native single-ticket required")
        identities.append(row)
    ids = tuple(row["strategy_id"] for row in identities)
    if ids != EXPECTED_STRATEGY_IDS:
        raise EvidenceAssemblyError(f"{path}.records: frozen strategy order mismatch")
    if _digest(list(ids)) != EXPECTED_STRATEGY_ORDER_SHA256:
        raise EvidenceAssemblyError(f"{path}: strategy-order authority mismatch")
    if _digest(identities) != EXPECTED_STRATEGY_UNIVERSE_SHA256:
        raise EvidenceAssemblyError(f"{path}.records: frozen strategy universe mismatch")
    if strategies["strategy_order_sha256"] != EXPECTED_STRATEGY_ORDER_SHA256:
        raise EvidenceAssemblyError(f"{path}.strategy_order_sha256: mismatch")
    if strategies["strategy_universe_sha256"] != EXPECTED_STRATEGY_UNIVERSE_SHA256:
        raise EvidenceAssemblyError(f"{path}.strategy_universe_sha256: mismatch")

    names = _as_list(strategies["names"], path=f"{path}.names")
    if len(names) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}.names: exactly 54 names required")
    strategy_names: list[str] = []
    for index, (raw, identity) in enumerate(zip(names, identities, strict=True)):
        row_path = f"{path}.names[{index}]"
        name = _as_dict(raw, path=row_path)
        _require_exact_keys(name, STRATEGY_NAME_KEYS, path=row_path)
        if name["strategy_id"] != identity["strategy_id"]:
            raise EvidenceAssemblyError(f"{row_path}.strategy_id: order mismatch")
        strategy_names.append(
            _require_string(name["strategy_name"], path=f"{row_path}.strategy_name")
        )

    classifications = _as_list(
        strategies["rng_classification"], path=f"{path}.rng_classification"
    )
    expected_classifications = [
        {
            "strategy_id": row["strategy_id"],
            "strategy_version": row["strategy_version"],
            "rng_class": _rng_class(row["strategy_id"]),
        }
        for row in identities
    ]
    for index, raw in enumerate(classifications):
        row_path = f"{path}.rng_classification[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, RNG_CLASSIFICATION_KEYS, path=row_path)
    _require_equal(classifications, expected_classifications, path=f"{path}.rng_classification")
    if strategies["rng_classification_sha256"] != EXPECTED_RNG_CLASSIFICATION_SHA256:
        raise EvidenceAssemblyError(f"{path}.rng_classification_sha256: mismatch")
    if _digest(classifications) != EXPECTED_RNG_CLASSIFICATION_SHA256:
        raise EvidenceAssemblyError(f"{path}.rng_classification: frozen hash mismatch")

    excluded = _as_dict(strategies["excluded"], path=f"{path}.excluded")
    _require_exact_keys(excluded, EXCLUDED_KEYS, path=f"{path}.excluded")
    if (
        excluded["strategy_id"] != ZONE_STRATEGY_ID
        or excluded["filtered_catalog_ordinal"] != EXPECTED_ZONE_ORDINAL
        or excluded["status"] != ZONE_STATUS
        or excluded["windows"] != []
    ):
        raise EvidenceAssemblyError(f"{path}.excluded: frozen zone record mismatch")
    _require_string(excluded["strategy_name"], path=f"{path}.excluded.strategy_name")
    return tuple(strategy_names)


def _validate_rng(value: object, plan: dict[str, Any], *, path: str) -> None:
    rng = _as_dict(value, path=path)
    _require_exact_keys(rng, RNG_KEYS, path=path)
    expected_scalars = {
        "seed_policy": "MANIFEST_BOUND_PER_STRATEGY_SHA256",
        "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
        "global_random_policy": (
            "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
        ),
        "private_rng_policy": "PRIVATE_RNG_SOURCE_SEMANTICS_PRESERVED_EXACTLY",
    }
    for key, expected in expected_scalars.items():
        if rng[key] != expected:
            raise EvidenceAssemblyError(f"{path}.{key}: Runner contract mismatch")
    exceptions = _as_list(
        rng["private_rng_exceptions"], path=f"{path}.private_rng_exceptions"
    )
    exception_ids: list[str] = []
    for index, raw in enumerate(exceptions):
        row_path = f"{path}.private_rng_exceptions[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, _keys("strategy_id policy"), path=row_path)
        exception_ids.append(
            _require_string(row["strategy_id"], path=f"{row_path}.strategy_id")
        )
        _require_string(row["policy"], path=f"{row_path}.policy")
    if tuple(exception_ids) != PRIVATE_RNG_STRATEGY_IDS:
        raise EvidenceAssemblyError(f"{path}.private_rng_exceptions: mismatch")
    seeds = _as_list(rng["seeds"], path=f"{path}.seeds")
    identities = cast(list[dict[str, Any]], plan["strategies"]["records"])
    if len(seeds) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}.seeds: exactly 54 seeds required")
    common_hash = cast(str, plan["common_manifest_sha256"])
    for index, (raw, identity) in enumerate(zip(seeds, identities, strict=True)):
        row_path = f"{path}.seeds[{index}]"
        seed = _as_dict(raw, path=row_path)
        _require_exact_keys(seed, RNG_SEED_KEYS, path=row_path)
        for key in ("strategy_id", "strategy_version", "adapter_path"):
            if seed[key] != identity[key]:
                raise EvidenceAssemblyError(f"{row_path}.{key}: identity mismatch")
        parts = [
            PROTOCOL_VERSION,
            common_hash,
            *[
                cast(str, identity[key])
                for key in ("strategy_id", "strategy_version", "adapter_path")
            ],
        ]
        expected_digest = sha256_hex(b"\x00".join(part.encode("utf-8") for part in parts))
        if seed["seed_digest"] != expected_digest or seed["seed_integer"] != str(
            int(expected_digest, 16)
        ):
            raise EvidenceAssemblyError(f"{row_path}: manifest-bound seed mismatch")


def _validate_runtime(
    value: object, authority: dict[str, Any], *, path: str
) -> dict[str, Any]:
    runtime = _as_dict(value, path=path)
    _require_exact_keys(runtime, RUNTIME_KEYS, path=path)
    if runtime["schema_version"] != "NEXT_DRAW_54_REPLAY_RUNTIME_V2":
        raise EvidenceAssemblyError(f"{path}.schema_version: mismatch")
    if runtime["source_inventory_sha256"] != authority["source_inventory_sha256"]:
        raise EvidenceAssemblyError(f"{path}.source_inventory_sha256: authority mismatch")
    runner_files = _as_list(runtime["runner_files"], path=f"{path}.runner_files")
    expected_paths = [
        "tools/next_draw_54_replay_r2.py",
        "tools/next_draw_54_replay_r2_lib.py",
        "tools/next_draw_54_replay_r2_runtime.py",
    ]
    if len(runner_files) != 3:
        raise EvidenceAssemblyError(f"{path}.runner_files: exact inventory required")
    for index, raw in enumerate(runner_files):
        row_path = f"{path}.runner_files[{index}]"
        row = _as_dict(raw, path=row_path)
        _require_exact_keys(row, RUNNER_FILE_KEYS, path=row_path)
        _require_hash(row["sha256"], path=f"{row_path}.sha256")
    if [row["path"] for row in runner_files] != expected_paths:
        raise EvidenceAssemblyError(f"{path}.runner_files: path inventory mismatch")
    return runtime


def _validate_plan(value: Mapping[str, Any]) -> _ValidatedPlan:
    payload = copy.deepcopy(dict(value))
    validate_value_domain(payload)
    _require_exact_keys(payload, PLAN_KEYS, path="plan")
    if payload["manifest_schema_version"] != PLAN_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError("plan.manifest_schema_version: mismatch")
    if payload["canonicalization_version"] != CANONICALIZATION_VERSION:
        raise EvidenceAssemblyError("plan.canonicalization_version: LCJ-1 required")
    _validate_protocol(payload["protocol_version"], path="plan.protocol_version")
    _validate_self_hash(payload, "plan_manifest_sha256", path="plan")

    authority = _validate_authority(payload["authority"], path="plan.authority")
    dataset, synthetic, draw_rows = _validate_dataset(
        payload["dataset"], path="plan.dataset"
    )
    strategy_names = _validate_strategies(
        payload["strategies"], path="plan.strategies"
    )
    runtime = _validate_runtime(
        payload["runtime_fingerprint"], authority, path="plan.runtime_fingerprint"
    )
    if payload["runtime_fingerprint_sha256"] != _digest(runtime):
        raise EvidenceAssemblyError("plan.runtime_fingerprint_sha256: hash mismatch")

    targets = _as_dict(payload["targets"], path="plan.targets")
    _require_exact_keys(targets, TARGET_KEYS, path="plan.targets")
    if targets["order"] != "BOUND_800_VECTOR_OLDEST_FIRST" or targets["count"] != 800:
        raise EvidenceAssemblyError("plan.targets: frozen 800-target order required")
    vector = _as_list(targets["vector"], path="plan.targets.vector")
    if len(vector) != EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError("plan.targets.vector: exactly 800 targets required")
    target_ids: list[tuple[str, str]] = []
    for index, raw in enumerate(vector):
        row_path = f"plan.targets.vector[{index}]"
        target = _as_dict(raw, path=row_path)
        _require_exact_keys(target, TARGET_IDENTITY_KEYS, path=row_path)
        target_ids.append(
            (
                _require_string(target["draw_date"], path=f"{row_path}.draw_date"),
                _require_string(target["draw_number"], path=f"{row_path}.draw_number"),
            )
        )
    if len(set(target_ids)) != EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError("plan.targets.vector: duplicate target")
    expected_vector = _frozen_targets(draw_rows)
    if not _canonical_equal(vector, expected_vector):
        raise EvidenceAssemblyError(
            "plan.targets.vector: exact dataset-derived frozen 800-target vector required"
        )
    if targets["target_order_sha256"] != _digest(vector):
        raise EvidenceAssemblyError("plan.targets.target_order_sha256: hash mismatch")
    strategy_records = cast(list[dict[str, Any]], payload["strategies"]["records"])
    largest_minimum = max(cast(int, row["min_history"]) for row in strategy_records)
    if not all(
        sum(_draw_key(row) < _draw_key(target) for row in draw_rows)
        >= largest_minimum
        for target in vector
    ):
        raise EvidenceAssemblyError(
            "plan.targets.vector: all 43,200 cells must be eligible before execution"
        )

    _require_equal(payload["execution"], EXPECTED_EXECUTION, path="plan.execution")
    _require_equal(payload["evaluation"], EXPECTED_EVALUATION, path="plan.evaluation")

    common = _as_dict(payload["common_manifest"], path="plan.common_manifest")
    _require_exact_keys(common, COMMON_KEYS, path="plan.common_manifest")
    expected_common = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "repository_head": REPOSITORY_HEAD,
        "repository_tree": REPOSITORY_TREE,
        "source_draw_db_sha256": dataset["source_db"]["sha256"],
        "dataset_snapshot_sha256": dataset["dataset_snapshot_sha256"],
        "target_count": EXPECTED_REPLAY_DEPTH,
        "target_order_sha256": targets["target_order_sha256"],
        "strategy_count": EXPECTED_STRATEGY_COUNT,
        "strategy_order_sha256": EXPECTED_STRATEGY_ORDER_SHA256,
        "strategy_universe_sha256": EXPECTED_STRATEGY_UNIVERSE_SHA256,
        "rng_classification_sha256": EXPECTED_RNG_CLASSIFICATION_SHA256,
        "runtime_fingerprint_sha256": payload["runtime_fingerprint_sha256"],
        "process_model": "ONE_PROCESS_PER_STRATEGY",
        "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
        "global_random_policy": (
            "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
        ),
        "cache_policy": "NO_REPLAY_RESULT_CACHE",
        "strategy_parallelization": "SERIAL_ONLY",
        "max_concurrency": 1,
        "failure_restart_boundary": "ENTIRE_STRATEGY_PROCESS",
        "metric_contract": EXPECTED_HIT_TIER_ID,
        "window_order": list(EXPECTED_WINDOW_ORDER),
        "excluded_strategy_id": ZONE_STRATEGY_ID,
        "old_84_reuse": False,
    }
    _require_equal(common, expected_common, path="plan.common_manifest")
    if payload["common_manifest_sha256"] != _digest(common):
        raise EvidenceAssemblyError("plan.common_manifest_sha256: hash mismatch")
    _validate_rng(payload["rng"], payload, path="plan.rng")

    return _ValidatedPlan(
        payload=payload,
        synthetic=synthetic,
        strategy_names=strategy_names,
        source_draw_count=len(draw_rows),
        last_causal_draw_id=cast(str, vector[-1]["draw_number"]),
    )


def _validate_evaluation_records(
    value: object, *, path: str
) -> tuple[dict[str, Any], ...]:
    records = _as_list(value, path=path)
    if len(records) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}: exactly 54 evaluation records required")
    validated: list[dict[str, Any]] = []
    for record_index, (raw, strategy_id) in enumerate(
        zip(records, EXPECTED_STRATEGY_IDS, strict=True)
    ):
        row_path = f"{path}[{record_index}]"
        record = _as_dict(raw, path=row_path)
        _require_exact_keys(record, EVALUATION_RECORD_KEYS, path=row_path)
        if record["strategy_id"] != strategy_id:
            raise EvidenceAssemblyError(f"{row_path}.strategy_id: frozen order mismatch")
        windows = _as_list(record["windows"], path=f"{row_path}.windows")
        if len(windows) != len(EXPECTED_WINDOW_ORDER):
            raise EvidenceAssemblyError(f"{row_path}.windows: four windows required")
        for window_index, raw_window in enumerate(windows):
            window_path = f"{row_path}.windows[{window_index}]"
            window = _as_dict(raw_window, path=window_path)
            _require_exact_keys(window, EVALUATION_WINDOW_KEYS, path=window_path)
            eligible = EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index]
            if window["window"] != EXPECTED_WINDOW_ORDER[window_index]:
                raise EvidenceAssemblyError(f"{window_path}.window: order mismatch")
            if window["eligible_draw_count"] != eligible:
                raise EvidenceAssemblyError(f"{window_path}.eligible_draw_count: mismatch")
            success = _require_int(
                window["success_count"], path=f"{window_path}.success_count"
            )
            if success > eligible:
                raise EvidenceAssemblyError(f"{window_path}.success_count: too large")
            _validate_fraction(
                window["observed_value"],
                path=f"{window_path}.observed_value",
                expected=Fraction(success, eligible),
            )
        validated.append(record)
    return tuple(validated)


def _validate_artifact(
    value: object,
    *,
    synthetic: bool,
    plan: _ValidatedPlan | None = None,
    evaluations: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    artifact = copy.deepcopy(_as_dict(value, path="artifact"))
    validate_value_domain(artifact)
    _require_exact_keys(artifact, ARTIFACT_KEYS, path="artifact")
    _validate_self_hash(artifact, "artifact_sha256", path="artifact")
    if artifact["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise EvidenceAssemblyError("artifact.artifact_schema_version: mismatch")
    if artifact["evaluator_version"] != EXPECTED_EVALUATOR_SEMANTIC_VERSION:
        raise EvidenceAssemblyError("artifact.evaluator_version: mismatch")
    if artifact["window_order"] != list(EXPECTED_WINDOW_ORDER):
        raise EvidenceAssemblyError("artifact.window_order: mismatch")
    expected_status = (
        SYNTHETIC_COMPUTATION_STATUS if synthetic else REAL_COMPUTATION_STATUS
    )
    if artifact["computation_status"] != expected_status:
        raise EvidenceAssemblyError("artifact.computation_status: path mismatch")
    if artifact["lottery_type"] != "BIG_LOTTO":
        raise EvidenceAssemblyError("artifact.lottery_type: mismatch")
    _require_hash(
        artifact["source_draw_db_sha256"], path="artifact.source_draw_db_sha256"
    )
    _require_int(
        artifact["source_draw_count"], path="artifact.source_draw_count", minimum=1
    )
    _require_string(
        artifact["last_causal_draw_id"], path="artifact.last_causal_draw_id"
    )
    if artifact["replay_depth"] != EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError("artifact.replay_depth: exactly 800 required")
    if artifact["hit_tier_id"] != EXPECTED_HIT_TIER_ID:
        raise EvidenceAssemblyError("artifact.hit_tier_id: M3_PLUS required")
    if plan is not None:
        if (
            artifact["source_draw_db_sha256"]
            != plan.payload["dataset"]["source_db"]["sha256"]
        ):
            raise EvidenceAssemblyError("artifact.source_draw_db_sha256: plan mismatch")
        if artifact["source_draw_count"] != plan.source_draw_count:
            raise EvidenceAssemblyError("artifact.source_draw_count: plan mismatch")
        if artifact["last_causal_draw_id"] != plan.last_causal_draw_id:
            raise EvidenceAssemblyError("artifact.last_causal_draw_id: target mismatch")

    records = _as_list(artifact["records"], path="artifact.records")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise EvidenceAssemblyError("artifact.records: exact 55-record census required")
    expected_ids: list[str] = list(EXPECTED_STRATEGY_IDS)
    expected_ids.insert(EXPECTED_ZONE_ORDINAL - 1, ZONE_STRATEGY_ID)
    reachable_index = 0
    evaluated_count = 0
    zone_count = 0
    for index, (raw, strategy_id) in enumerate(zip(records, expected_ids, strict=True)):
        row_path = f"artifact.records[{index}]"
        record = _as_dict(raw, path=row_path)
        _require_exact_keys(record, ARTIFACT_RECORD_KEYS, path=row_path)
        if record["strategy_id"] != strategy_id:
            raise EvidenceAssemblyError(f"{row_path}.strategy_id: order mismatch")
        _require_string(record["strategy_name"], path=f"{row_path}.strategy_name")
        if (
            record["native_ticket_count"] != 1
            or record["hit_tier_id"] != EXPECTED_HIT_TIER_ID
        ):
            raise EvidenceAssemblyError(f"{row_path}: native M3_PLUS record required")
        windows = _as_list(record["windows"], path=f"{row_path}.windows")
        if index == EXPECTED_ZONE_ORDINAL - 1:
            zone_count += 1
            if record["status"] != ZONE_STATUS or windows:
                raise EvidenceAssemblyError(f"{row_path}: DRIVER_ERROR zone required")
            if (
                plan is not None
                and record["strategy_name"]
                != plan.payload["strategies"]["excluded"]["strategy_name"]
            ):
                raise EvidenceAssemblyError(f"{row_path}.strategy_name: plan mismatch")
            continue
        if record["status"] != "EVALUATED" or len(windows) != 4:
            raise EvidenceAssemblyError(f"{row_path}: complete EVALUATED record required")
        if (
            plan is not None
            and record["strategy_name"] != plan.strategy_names[reachable_index]
        ):
            raise EvidenceAssemblyError(f"{row_path}.strategy_name: plan mismatch")
        evaluation = evaluations[reachable_index] if evaluations is not None else None
        evaluated_count += 1
        for window_index, raw_window in enumerate(windows):
            window_path = f"{row_path}.windows[{window_index}]"
            window = _as_dict(raw_window, path=window_path)
            _require_exact_keys(window, ARTIFACT_WINDOW_KEYS, path=window_path)
            eligible = EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index]
            if (
                window["window_kind"] != EXPECTED_WINDOW_ORDER[window_index]
                or window["window_status"] != "COMPLETE"
                or window["eligible_draw_count"] != eligible
            ):
                raise EvidenceAssemblyError(f"{window_path}: window contract mismatch")
            observed = _validate_fraction(
                window["observed_value"], path=f"{window_path}.observed_value"
            )
            reference = _validate_fraction(
                window["random_reference"],
                path=f"{window_path}.random_reference",
                expected=EXPECTED_RANDOM_REFERENCE,
            )
            delta = _validate_fraction(
                window["delta_vs_random"], path=f"{window_path}.delta_vs_random"
            )
            if delta != observed - reference:
                raise EvidenceAssemblyError(f"{window_path}.delta_vs_random: mismatch")
            if not 0 <= observed <= 1 or eligible % observed.denominator != 0:
                raise EvidenceAssemblyError(f"{window_path}.observed_value: invalid ratio")
            if evaluation is not None:
                source_window = evaluation["windows"][window_index]
                if observed != Fraction(source_window["success_count"], eligible):
                    raise EvidenceAssemblyError(f"{window_path}: evaluation mismatch")
        reachable_index += 1
    if evaluated_count != 54 or zone_count != 1:
        raise EvidenceAssemblyError("artifact.records: frozen census mismatch")
    return artifact


def _validate_operational(
    value: object, *, path: str
) -> tuple[str, str, frozenset[str]]:
    operational = _as_dict(value, path=path)
    _require_exact_keys(operational, OPERATIONAL_KEYS, path=path)
    run_id = _require_string(operational["run_id"], path=f"{path}.run_id")
    output_root = _require_string(
        operational["output_root"], path=f"{path}.output_root"
    )
    for key in (
        "source_root",
        "source_db_path",
        "host_label",
        "started_at_utc",
        "ended_at_utc",
    ):
        _require_string(operational[key], path=f"{path}.{key}")
    _require_int(operational["elapsed_ns"], path=f"{path}.elapsed_ns")
    attempts = _as_list(operational["attempts"], path=f"{path}.attempts")
    attempt_ids: set[str] = set()
    successful_ids: list[str] = []
    for index, raw in enumerate(attempts):
        row_path = f"{path}.attempts[{index}]"
        attempt = _as_dict(raw, path=row_path)
        _require_exact_keys(attempt, ATTEMPT_KEYS, path=row_path)
        attempt_id = _require_string(
            attempt["attempt_id"], path=f"{row_path}.attempt_id"
        )
        if attempt_id in attempt_ids:
            raise EvidenceAssemblyError(f"{row_path}.attempt_id: duplicate")
        attempt_ids.add(attempt_id)
        strategy_id = _require_string(
            attempt["strategy_id"], path=f"{row_path}.strategy_id"
        )
        if strategy_id not in EXPECTED_STRATEGY_IDS:
            raise EvidenceAssemblyError(f"{row_path}.strategy_id: outside universe")
        if attempt["status"] == "SUCCEEDED":
            successful_ids.append(strategy_id)
    if tuple(successful_ids) != EXPECTED_STRATEGY_IDS:
        raise EvidenceAssemblyError(f"{path}.attempts: serial 54-success lineage required")
    return run_id, output_root, frozenset(attempt_ids)


def _validate_run(
    value: Mapping[str, Any], plan: _ValidatedPlan, *, label: str
) -> _ValidatedRun:
    payload = copy.deepcopy(dict(value))
    validate_value_domain(payload)
    _require_exact_keys(payload, RUN_KEYS, path=label)
    if payload["manifest_schema_version"] != RUN_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError(f"{label}.manifest_schema_version: mismatch")
    if payload["canonicalization_version"] != CANONICALIZATION_VERSION:
        raise EvidenceAssemblyError(f"{label}.canonicalization_version: LCJ-1 required")
    _validate_protocol(payload["protocol_version"], path=f"{label}.protocol_version")
    _validate_self_hash(payload, "run_manifest_sha256", path=label)
    if payload["plan_manifest_sha256"] != plan.payload["plan_manifest_sha256"]:
        raise EvidenceAssemblyError(f"{label}.plan_manifest_sha256: plan mismatch")
    if payload["common_manifest_sha256"] != plan.payload["common_manifest_sha256"]:
        raise EvidenceAssemblyError(f"{label}.common_manifest_sha256: common mismatch")
    _require_string(payload["campaign_label"], path=f"{label}.campaign_label")
    run_id, output_root, attempt_ids = _validate_operational(
        payload["operational_envelope"], path=f"{label}.operational_envelope"
    )

    deterministic = _as_dict(
        payload["deterministic_payload"], path=f"{label}.deterministic_payload"
    )
    _require_exact_keys(
        deterministic,
        DETERMINISTIC_PAYLOAD_KEYS,
        path=f"{label}.deterministic_payload",
    )
    if payload["deterministic_payload_sha256"] != _digest(deterministic):
        raise EvidenceAssemblyError(f"{label}.deterministic_payload_sha256: mismatch")
    _require_equal(
        deterministic["runtime_fingerprint"],
        plan.payload["runtime_fingerprint"],
        path=f"{label}.deterministic_payload.runtime_fingerprint",
    )
    _require_equal(
        deterministic["authority"],
        plan.payload["authority"],
        path=f"{label}.deterministic_payload.authority",
    )
    strategy_results = _as_list(
        deterministic["strategy_results"],
        path=f"{label}.deterministic_payload.strategy_results",
    )
    if len(strategy_results) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{label}: exactly 54 strategy results required")
    result_ids: list[str] = []
    for index, raw in enumerate(strategy_results):
        result_path = f"{label}.deterministic_payload.strategy_results[{index}]"
        result = _as_dict(raw, path=result_path)
        identity = _as_dict(
            result.get("strategy_identity"), path=f"{result_path}.strategy_identity"
        )
        result_ids.append(
            _require_string(
                identity.get("strategy_id"),
                path=f"{result_path}.strategy_identity.strategy_id",
            )
        )
    if tuple(result_ids) != EXPECTED_STRATEGY_IDS:
        raise EvidenceAssemblyError(f"{label}: strategy result order mismatch")
    if deterministic["matrix_order"] != "TARGET_MAJOR_STRATEGY_MINOR":
        raise EvidenceAssemblyError(f"{label}.deterministic_payload.matrix_order: mismatch")
    if deterministic["matrix_cell_count"] != EXPECTED_EVALUATED_CELL_COUNT:
        raise EvidenceAssemblyError(f"{label}.deterministic_payload.matrix_cell_count: mismatch")
    matrix = _as_list(
        deterministic["matrix"], path=f"{label}.deterministic_payload.matrix"
    )
    if len(matrix) != EXPECTED_EVALUATED_CELL_COUNT:
        raise EvidenceAssemblyError(f"{label}.deterministic_payload.matrix: cell count")
    if deterministic["matrix_sha256"] != _digest(matrix):
        raise EvidenceAssemblyError(f"{label}.deterministic_payload.matrix_sha256: mismatch")
    evaluations = _validate_evaluation_records(
        deterministic["evaluation_records"],
        path=f"{label}.deterministic_payload.evaluation_records",
    )
    if deterministic["evaluation_sha256"] != _digest(list(evaluations)):
        raise EvidenceAssemblyError(
            f"{label}.deterministic_payload.evaluation_sha256: mismatch"
        )
    _require_equal(
        deterministic["excluded_strategy"],
        plan.payload["strategies"]["excluded"],
        path=f"{label}.deterministic_payload.excluded_strategy",
    )
    artifact = _validate_artifact(
        deterministic["artifact"],
        synthetic=plan.synthetic,
        plan=plan,
        evaluations=evaluations,
    )
    if deterministic["artifact_content_sha256"] != artifact["artifact_sha256"]:
        raise EvidenceAssemblyError(f"{label}.artifact_content_sha256: mismatch")
    if deterministic["artifact_file_sha256"] != _file_digest(artifact):
        raise EvidenceAssemblyError(f"{label}.artifact_file_sha256: mismatch")
    if deterministic["old_84_reuse"] is not False:
        raise EvidenceAssemblyError(f"{label}.old_84_reuse: must be false")
    expected_final = SYNTHETIC_FINAL_STATUS if plan.synthetic else REAL_FINAL_STATUS
    if deterministic["final_status"] != expected_final:
        raise EvidenceAssemblyError(f"{label}.final_status: path mismatch")
    return _ValidatedRun(
        payload=payload,
        deterministic_payload=deterministic,
        artifact=artifact,
        run_id=run_id,
        output_root=output_root,
        attempt_ids=attempt_ids,
    )


def _validate_acceptance(
    value: Mapping[str, Any],
    plan: _ValidatedPlan,
    run_a: _ValidatedRun,
    run_b: _ValidatedRun,
    *,
    synthetic_test: bool,
) -> None:
    acceptance = copy.deepcopy(dict(value))
    validate_value_domain(acceptance)
    _require_exact_keys(acceptance, ACCEPTANCE_KEYS, path="acceptance")
    if acceptance["manifest_schema_version"] != ACCEPTANCE_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError("acceptance.manifest_schema_version: mismatch")
    if acceptance["canonicalization_version"] != CANONICALIZATION_VERSION:
        raise EvidenceAssemblyError("acceptance.canonicalization_version: LCJ-1 required")
    _validate_protocol(acceptance["protocol_version"], path="acceptance.protocol_version")
    _validate_self_hash(acceptance, "acceptance_manifest_sha256", path="acceptance")
    if acceptance["plan_manifest_sha256"] != plan.payload["plan_manifest_sha256"]:
        raise EvidenceAssemblyError("acceptance.plan_manifest_sha256: mismatch")
    if acceptance["common_manifest_sha256"] != plan.payload["common_manifest_sha256"]:
        raise EvidenceAssemblyError("acceptance.common_manifest_sha256: mismatch")
    if acceptance["run_a_manifest_file_sha256"] != _file_digest(run_a.payload):
        raise EvidenceAssemblyError("acceptance.run_a_manifest_file_sha256: mismatch")
    if acceptance["run_b_manifest_file_sha256"] != _file_digest(run_b.payload):
        raise EvidenceAssemblyError("acceptance.run_b_manifest_file_sha256: mismatch")
    if (
        acceptance["run_a_deterministic_payload_sha256"]
        != run_a.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("acceptance.run_a_deterministic_payload_sha256: mismatch")
    if (
        acceptance["run_b_deterministic_payload_sha256"]
        != run_b.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("acceptance.run_b_deterministic_payload_sha256: mismatch")
    if (
        acceptance["comparison_contract"]
        != "EXACT_LF_FREE_LCJ1_DETERMINISTIC_PAYLOAD_BYTES"
    ):
        raise EvidenceAssemblyError("acceptance.comparison_contract: mismatch")
    comparison = _as_dict(
        acceptance["comparison_results"], path="acceptance.comparison_results"
    )
    _require_exact_keys(
        comparison, COMPARISON_RESULTS_KEYS, path="acceptance.comparison_results"
    )
    _require_equal(
        comparison, EXPECTED_COMPARISON_RESULTS, path="acceptance.comparison_results"
    )
    if acceptance["old_84_reuse_attestation"] is not False:
        raise EvidenceAssemblyError("acceptance.old_84_reuse_attestation: must be false")
    expected_final = SYNTHETIC_FINAL_STATUS if plan.synthetic else REAL_FINAL_STATUS
    if acceptance["final_status"] != expected_final:
        raise EvidenceAssemblyError("acceptance.final_status: plan/run mismatch")
    if synthetic_test:
        if not plan.synthetic or acceptance["final_status"] != SYNTHETIC_FINAL_STATUS:
            raise EvidenceAssemblyError(
                "synthetic-test path requires SYNTHETIC_TEST_ONLY evidence"
            )
    elif plan.synthetic or acceptance["final_status"] != REAL_FINAL_STATUS:
        raise EvidenceAssemblyError(
            "SYNTHETIC_TEST_ONLY is forbidden on the real-evidence assembly path"
        )


def assemble_artifact(
    plan: Mapping[str, Any],
    run_a: Mapping[str, Any],
    run_b: Mapping[str, Any],
    acceptance: Mapping[str, Any],
    *,
    synthetic_test: bool = False,
) -> dict[str, Any]:
    """Validate four direct Runner documents and return Run A's exact artifact."""

    validated_plan = _validate_plan(plan)
    validated_run_a = _validate_run(run_a, validated_plan, label="run_a")
    validated_run_b = _validate_run(run_b, validated_plan, label="run_b")
    if (
        validated_run_a.payload["run_manifest_sha256"]
        == validated_run_b.payload["run_manifest_sha256"]
    ):
        raise EvidenceAssemblyError("run_a/run_b: two distinct run identities are required")
    if _file_digest(validated_run_a.payload) == _file_digest(validated_run_b.payload):
        raise EvidenceAssemblyError("run_a/run_b: canonical Run file hashes must differ")
    if validated_run_a.payload["campaign_label"] == validated_run_b.payload["campaign_label"]:
        raise EvidenceAssemblyError("run_a/run_b: distinct campaign labels are required")
    if validated_run_a.run_id == validated_run_b.run_id:
        raise EvidenceAssemblyError("run_a/run_b: distinct operational run IDs are required")
    if validated_run_a.output_root == validated_run_b.output_root:
        raise EvidenceAssemblyError("run_a/run_b: separate output roots are required")
    if not validated_run_a.attempt_ids.isdisjoint(validated_run_b.attempt_ids):
        raise EvidenceAssemblyError("run_a/run_b: attempt identities must be disjoint")
    if not _canonical_equal(
        validated_run_a.deterministic_payload,
        validated_run_b.deterministic_payload,
    ):
        raise EvidenceAssemblyError("run_a/run_b: deterministic payload bytes differ")
    if (
        validated_run_a.payload["deterministic_payload_sha256"]
        != validated_run_b.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("run_a/run_b: deterministic payload hashes differ")
    if not _canonical_equal(validated_run_a.artifact, validated_run_b.artifact):
        raise EvidenceAssemblyError("run_a/run_b: artifact bytes differ")
    _validate_acceptance(
        acceptance,
        validated_plan,
        validated_run_a,
        validated_run_b,
        synthetic_test=synthetic_test,
    )
    artifact = copy.deepcopy(validated_run_a.artifact)
    direct = cast(dict[str, Any], run_a["deterministic_payload"])["artifact"]
    if canonical_bytes(artifact) != canonical_bytes(direct):
        raise EvidenceAssemblyError("artifact: direct Runner round-trip mismatch")
    return artifact


def artifact_canonical_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return the exact LF-free LCJ-1 artifact bytes."""

    return canonical_bytes(dict(artifact))


def artifact_canonical_file_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return the exact LCJ-1 artifact bytes with one trailing LF."""

    return canonical_file_bytes(dict(artifact))


def validate_assembled_artifact(
    payload: Mapping[str, Any], *, synthetic_test: bool = False
) -> None:
    """Validate a standalone direct Runner artifact for one execution path."""

    _validate_artifact(payload, synthetic=synthetic_test)


def load_manifest_file(path: Path) -> dict[str, Any]:
    """Load exact canonical JSON using Runner's LCJ-1 plus-one-LF transport."""

    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise EvidenceAssemblyError(f"{path}: UTF-8 BOM is forbidden")
    if b"\r" in raw:
        raise EvidenceAssemblyError(f"{path}: CR bytes are forbidden")
    if raw.count(b"\n") != 1 or not raw.endswith(b"\n"):
        raise EvidenceAssemblyError(f"{path}: canonical file requires exactly one trailing LF")
    value = loads_canonical(raw[:-1])
    payload = _as_dict(value, path=str(path))
    if canonical_file_bytes(payload) != raw:
        raise EvidenceAssemblyError(f"{path}: noncanonical LCJ-1 file bytes")
    return payload


def load_artifact_file(path: Path, *, synthetic_test: bool = False) -> dict[str, Any]:
    """Load and validate one direct Runner artifact file."""

    artifact = load_manifest_file(path)
    validate_assembled_artifact(artifact, synthetic_test=synthetic_test)
    return artifact


def _refuse_packaged_artifact_output(output: Path) -> None:
    resolved = output.resolve()
    if resolved.name == "biglotto_next_draw_recommendation_evidence_v1.json":
        raise EvidenceAssemblyError("refusing to overwrite the current packaged V1 artifact")
    if "src/lottolab/strategies/data" in resolved.as_posix():
        raise EvidenceAssemblyError("R2 output may not be written into packaged strategy data")


def assemble_from_paths(
    *,
    plan_path: Path,
    run_a_path: Path,
    run_b_path: Path,
    acceptance_path: Path,
    output_path: Path,
    synthetic_test: bool = False,
) -> dict[str, Any]:
    """Load four direct canonical Runner files and emit the embedded artifact."""

    _refuse_packaged_artifact_output(output_path)
    artifact = assemble_artifact(
        load_manifest_file(plan_path),
        load_manifest_file(run_a_path),
        load_manifest_file(run_b_path),
        load_manifest_file(acceptance_path),
        synthetic_test=synthetic_test,
    )
    output_path.write_bytes(artifact_canonical_file_bytes(artifact))
    return artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="canonical Runner Plan V2")
    parser.add_argument("--run-a", required=True, type=Path, help="canonical Runner Run A V2")
    parser.add_argument("--run-b", required=True, type=Path, help="canonical Runner Run B V2")
    parser.add_argument(
        "--acceptance", required=True, type=Path, help="canonical Runner Acceptance V2"
    )
    parser.add_argument("--output", required=True, type=Path, help="new artifact output path")
    parser.add_argument(
        "--synthetic-test",
        action="store_true",
        help="allow SYNTHETIC_TEST_ONLY documents; never use for real-evidence output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        artifact = assemble_from_paths(
            plan_path=args.plan,
            run_a_path=args.run_a,
            run_b_path=args.run_b,
            acceptance_path=args.acceptance,
            output_path=args.output,
            synthetic_test=args.synthetic_test,
        )
    except (OSError, EvidenceAssemblyError, ValueError) as exc:
        parser.error(str(exc))
    print(artifact["artifact_sha256"])
    return 0


__all__ = [
    "ACCEPTANCE_MANIFEST_SCHEMA_VERSION",
    "ARTIFACT_SCHEMA_VERSION",
    "CANONICALIZATION_VERSION",
    "EXPECTED_EVALUATED_CELL_COUNT",
    "EXPECTED_HIT_TIER_ID",
    "EXPECTED_RANDOM_REFERENCE",
    "EXPECTED_RECORD_COUNT",
    "EXPECTED_REPLAY_DEPTH",
    "EXPECTED_RNG_CLASSIFICATION_SHA256",
    "EXPECTED_STRATEGY_COUNT",
    "EXPECTED_STRATEGY_IDS",
    "EXPECTED_STRATEGY_ORDER_SHA256",
    "EXPECTED_STRATEGY_UNIVERSE_SHA256",
    "EXPECTED_WINDOW_ELIGIBLE_COUNTS",
    "EXPECTED_WINDOW_ORDER",
    "PLAN_MANIFEST_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "REAL_DATA_KIND",
    "REPOSITORY_HEAD",
    "REPOSITORY_TREE",
    "RUN_MANIFEST_SCHEMA_VERSION",
    "SYNTHETIC_DATA_KIND",
    "ZONE_STRATEGY_ID",
    "EvidenceAssemblyError",
    "artifact_canonical_bytes",
    "artifact_canonical_file_bytes",
    "assemble_artifact",
    "assemble_from_paths",
    "load_artifact_file",
    "load_manifest_file",
    "validate_assembled_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
