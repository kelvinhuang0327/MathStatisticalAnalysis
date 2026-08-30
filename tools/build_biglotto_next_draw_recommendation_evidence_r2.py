"""Assemble the synthetic, accepted R2 Next-Draw evidence artifact.

This module is deliberately an assembler, not a replay runner.  It consumes
three already-sealed R2 documents (one plan, two run manifests, and one
acceptance manifest), validates their closed contracts, and projects the
accepted ``M3_PLUS`` success counts into the repository's existing evidence
domain model.

The input contract is intentionally local to this tooling task.  It is
content-addressed with LCJ-1 and keeps run-specific operational metadata in an
explicit ``operational`` envelope.  That envelope is required for provenance
documents and is covered by each manifest's self-digest.  It is excluded only
from the run's deterministic comparison digest, so two independent synthetic
runs can differ in paths, timestamps, or process identifiers without being
mistaken for different empirical results.

No adapter, replay session, database, or packaged evidence artifact is
imported by this module.  The only production-domain import is the immutable
LCJ-1/evidence model used for the final projection.
"""

from __future__ import annotations

import argparse
import copy
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from lottolab.evidence.next_draw_recommendation_evidence import (
    RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    NextDrawRecommendationEvidenceArtifact,
    RecommendationEvidenceStrategyRecord,
    RecommendationEvidenceWindow,
    StrategyBacktestStatus,
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

EXPECTED_STRATEGY_COUNT = 54
EXPECTED_RECORD_COUNT = 55
EXPECTED_REPLAY_DEPTH = 800
EXPECTED_EVALUATED_CELL_COUNT = EXPECTED_STRATEGY_COUNT * EXPECTED_REPLAY_DEPTH
EXPECTED_ZONE_ORDINAL = 19
ZONE_STRATEGY_ID = "legacy_biglotto__zone_momentum_predict__9e89f2b41add"
ZONE_STRATEGY_NAME = "大樂透區域動量預測器"
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

EXPECTED_STRATEGY_ORDER_SHA256 = "1efeba5519693c58f1b407f859d5b37f54647efcd4a34b424b9eed71ff7c9493"
EXPECTED_STRATEGY_UNIVERSE_SHA256 = (
    "02cf7c5403e4714416824ae1a71ef7478a4a975ff973b7f237f9992b6f9dd0a9"
)
EXPECTED_RNG_CLASSIFICATION_SHA256 = (
    "cda9f5ff34784da35ef762425d1e5e6b3539a20e6bdd5fcad82bbb10f92c86d7"
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")

PLAN_KEYS = frozenset(
    {
        "manifest_schema_version",
        "protocol_version",
        "canonicalization",
        "old_84_reuse",
        "source_fingerprint",
        "dataset_fingerprint",
        "runtime_fingerprint",
        "target_identity",
        "evaluator_contract",
        "strategy_order_sha256",
        "strategy_universe_sha256",
        "rng_classification_sha256",
        "strategy_universe",
        "zone_exclusion",
        "execution_contract",
        "manifest_sha256",
        "operational",
    }
)
RUN_KEYS = frozenset(
    {
        "manifest_schema_version",
        "protocol_version",
        "canonicalization",
        "plan_manifest_sha256",
        "old_84_reuse",
        "source_fingerprint",
        "dataset_fingerprint",
        "runtime_fingerprint",
        "target_identity",
        "evaluator_contract",
        "strategy_order_sha256",
        "strategy_universe_sha256",
        "rng_classification_sha256",
        "strategy_universe",
        "zone_exclusion",
        "execution_contract",
        "evaluation_records",
        "deterministic_payload_sha256",
        "manifest_sha256",
        "operational",
    }
)
ACCEPTANCE_KEYS = frozenset(
    {
        "manifest_schema_version",
        "protocol_version",
        "canonicalization",
        "plan_manifest_sha256",
        "run_a_manifest_sha256",
        "run_b_manifest_sha256",
        "old_84_reuse",
        "source_fingerprint",
        "dataset_fingerprint",
        "runtime_fingerprint",
        "target_identity",
        "evaluator_contract",
        "strategy_order_sha256",
        "strategy_universe_sha256",
        "rng_classification_sha256",
        "strategy_universe",
        "zone_exclusion",
        "execution_contract",
        "comparison",
        "acceptance_status",
        "manifest_sha256",
        "operational",
    }
)

SOURCE_FINGERPRINT_KEYS = frozenset(
    {
        "repository_head",
        "repository_tree",
        "source_tree_sha256",
        "source_draw_db_sha256",
    }
)
DATASET_FINGERPRINT_KEYS = frozenset(
    {
        "lottery_type",
        "dataset_schema_version",
        "logical_dataset_sha256",
        "source_draw_count",
        "last_causal_draw_id",
    }
)
RUNTIME_FINGERPRINT_KEYS = frozenset({"fingerprint_sha256", "details"})
TARGET_IDENTITY_KEYS = frozenset({"target_count", "target_order_sha256"})
EVALUATOR_KEYS = frozenset(
    {
        "evaluator_semantic_version",
        "lottery_type",
        "hit_tier_id",
        "window_order",
        "eligible_draw_counts",
        "random_reference",
        "native_ticket_count",
    }
)
EXECUTION_KEYS = frozenset(
    {
        "process_model",
        "seed_timing",
        "cache_policy",
        "cache_constructor",
        "parallelization",
        "max_concurrency",
        "replay_depth",
        "source_import_policy",
    }
)
IDENTITY_KEYS = frozenset(
    {
        "strategy_id",
        "strategy_version",
        "adapter_path",
        "min_history",
        "native_ticket_count",
        "response_shape",
    }
)
ZONE_KEYS = frozenset({"strategy_id", "catalog_ordinal", "status", "windows"})
RUN_WINDOW_KEYS = frozenset(
    {"window_kind", "window_status", "eligible_draw_count", "success_count"}
)
RUN_RECORD_KEYS = frozenset(
    {"strategy_id", "strategy_name", "native_ticket_count", "hit_tier_id", "windows"}
)
COMPARISON_KEYS = frozenset(
    {
        "status",
        "run_a_deterministic_payload_sha256",
        "run_b_deterministic_payload_sha256",
        "evaluated_strategy_count",
        "eligible_cell_count",
        "zone_status",
        "target_order_sha256",
    }
)


class EvidenceAssemblyError(ValueError):
    """An R2 input or projected artifact violates the closed contract."""


@dataclass(frozen=True, slots=True)
class _ValidatedPlan:
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ValidatedRun:
    payload: dict[str, Any]
    records: tuple[dict[str, Any], ...]


def _as_dict(value: object, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceAssemblyError(f"{path} must be an object")
    return cast(dict[str, Any], value)


def _as_list(value: object, *, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceAssemblyError(f"{path} must be an array")
    return cast(list[Any], value)


def _require_exact_keys(payload: Mapping[str, Any], expected: frozenset[str], *, path: str) -> None:
    actual = set(payload)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        raise EvidenceAssemblyError(f"{path} keys mismatch; missing={missing}, extra={extra}")


def _require_string(value: object, *, path: str, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise EvidenceAssemblyError(f"{path} must be a non-empty string")
    return value


def _require_int(value: object, *, path: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise EvidenceAssemblyError(f"{path} must be an integer")
    integer = value
    if minimum is not None and integer < minimum:
        raise EvidenceAssemblyError(f"{path} must be >= {minimum}")
    return integer


def _require_hash(value: object, *, path: str) -> str:
    candidate = _require_string(value, path=path)
    if _HASH_RE.fullmatch(candidate) is None:
        raise EvidenceAssemblyError(f"{path} must be a lowercase SHA-256 hex digest")
    return candidate


def _require_bool(value: object, *, path: str) -> bool:
    if type(value) is not bool:
        raise EvidenceAssemblyError(f"{path} must be a boolean")
    return value


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def manifest_sha256(payload: Mapping[str, Any]) -> str:
    """Compute a manifest identity covering every field except the digest itself."""

    return self_key_removed_sha256(dict(payload), "manifest_sha256")


def deterministic_run_sha256(payload: Mapping[str, Any]) -> str:
    """Compute the hash of a run's deterministic content only."""

    deterministic = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "manifest_sha256",
            "deterministic_payload_sha256",
            "operational",
        }
    }
    return sha256_hex(canonical_bytes(deterministic))


def seal_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with a correct manifest self hash.

    This helper is useful for synthetic fixture authors.  It intentionally
    does not skip validation; the normal assembly path validates the sealed
    result with the exact schema for its document kind.
    """

    sealed = copy.deepcopy(dict(payload))
    sealed["manifest_sha256"] = "0" * 64
    sealed["manifest_sha256"] = manifest_sha256(sealed)
    return sealed


def seal_run_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a synthetic run manifest with both deterministic and self hashes."""

    sealed = copy.deepcopy(dict(payload))
    sealed["deterministic_payload_sha256"] = "0" * 64
    sealed["deterministic_payload_sha256"] = deterministic_run_sha256(sealed)
    sealed["manifest_sha256"] = "0" * 64
    sealed["manifest_sha256"] = manifest_sha256(sealed)
    return sealed


def _validate_manifest_self_hash(payload: dict[str, Any], *, path: str) -> None:
    declared = _require_hash(payload.get("manifest_sha256"), path=f"{path}.manifest_sha256")
    expected = manifest_sha256(payload)
    if declared != expected:
        raise EvidenceAssemblyError(
            f"{path}.manifest_sha256 does not match deterministic manifest content"
        )


def _validate_common_identity(payload: dict[str, Any], *, path: str) -> None:
    protocol_version = _require_string(payload["protocol_version"], path=f"{path}.protocol_version")
    if protocol_version != PROTOCOL_VERSION:
        if protocol_version in OLD_PROTOCOL_VERSIONS:
            raise EvidenceAssemblyError(f"{path}: old protocol is forbidden")
        raise EvidenceAssemblyError(f"{path}: protocol_version must be R2")
    canonicalization = _require_string(payload["canonicalization"], path=f"{path}.canonicalization")
    if canonicalization != CANONICALIZATION_VERSION:
        raise EvidenceAssemblyError(f"{path}: LCJ-1 canonicalization is required")
    if _require_bool(payload["old_84_reuse"], path=f"{path}.old_84_reuse"):
        raise EvidenceAssemblyError(f"{path}: old_84_reuse must be false")

    source = _as_dict(payload["source_fingerprint"], path=f"{path}.source_fingerprint")
    _require_exact_keys(source, SOURCE_FINGERPRINT_KEYS, path=f"{path}.source_fingerprint")
    if source["repository_head"] != REPOSITORY_HEAD:
        raise EvidenceAssemblyError(f"{path}: repository_head is not the frozen R2 authority")
    if source["repository_tree"] != REPOSITORY_TREE:
        raise EvidenceAssemblyError(f"{path}: repository_tree is not the frozen R2 authority")
    _require_hash(source["source_tree_sha256"], path=f"{path}.source_tree_sha256")
    _require_hash(source["source_draw_db_sha256"], path=f"{path}.source_draw_db_sha256")

    dataset = _as_dict(payload["dataset_fingerprint"], path=f"{path}.dataset_fingerprint")
    _require_exact_keys(dataset, DATASET_FINGERPRINT_KEYS, path=f"{path}.dataset_fingerprint")
    if dataset["lottery_type"] != "BIG_LOTTO":
        raise EvidenceAssemblyError(f"{path}: dataset lottery_type must be BIG_LOTTO")
    _require_string(dataset["dataset_schema_version"], path=f"{path}.dataset_schema_version")
    _require_hash(dataset["logical_dataset_sha256"], path=f"{path}.logical_dataset_sha256")
    _require_int(dataset["source_draw_count"], path=f"{path}.source_draw_count", minimum=1)
    _require_string(dataset["last_causal_draw_id"], path=f"{path}.last_causal_draw_id")

    runtime = _as_dict(payload["runtime_fingerprint"], path=f"{path}.runtime_fingerprint")
    _require_exact_keys(runtime, RUNTIME_FINGERPRINT_KEYS, path=f"{path}.runtime_fingerprint")
    declared_runtime_hash = _require_hash(
        runtime["fingerprint_sha256"], path=f"{path}.runtime_fingerprint.fingerprint_sha256"
    )
    details = _as_dict(runtime["details"], path=f"{path}.runtime_fingerprint.details")
    if not details:
        raise EvidenceAssemblyError(f"{path}.runtime_fingerprint.details must not be empty")
    if declared_runtime_hash != sha256_hex(canonical_bytes(details)):
        raise EvidenceAssemblyError(f"{path}: runtime fingerprint digest mismatch")

    target = _as_dict(payload["target_identity"], path=f"{path}.target_identity")
    _require_exact_keys(target, TARGET_IDENTITY_KEYS, path=f"{path}.target_identity")
    if _require_int(target["target_count"], path=f"{path}.target_count") != EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError(f"{path}: exactly 800 targets are required")
    _require_hash(target["target_order_sha256"], path=f"{path}.target_identity.target_order_sha256")

    evaluator = _as_dict(payload["evaluator_contract"], path=f"{path}.evaluator_contract")
    _require_exact_keys(evaluator, EVALUATOR_KEYS, path=f"{path}.evaluator_contract")
    if evaluator["evaluator_semantic_version"] != EXPECTED_EVALUATOR_SEMANTIC_VERSION:
        raise EvidenceAssemblyError(f"{path}: evaluator semantic version mismatch")
    if evaluator["lottery_type"] != "BIG_LOTTO":
        raise EvidenceAssemblyError(f"{path}: evaluator lottery_type mismatch")
    if evaluator["hit_tier_id"] != EXPECTED_HIT_TIER_ID:
        raise EvidenceAssemblyError(f"{path}: evaluator hit tier must be M3_PLUS")
    window_order = _as_list(
        evaluator["window_order"], path=f"{path}.evaluator_contract.window_order"
    )
    normalized_window_order = tuple(
        _require_string(item, path=f"{path}.evaluator_contract.window_order[{index}]")
        for index, item in enumerate(window_order)
    )
    if normalized_window_order != EXPECTED_WINDOW_ORDER:
        raise EvidenceAssemblyError(f"{path}: evaluator window order mismatch")
    eligible_draw_counts = _as_list(
        evaluator["eligible_draw_counts"],
        path=f"{path}.evaluator_contract.eligible_draw_counts",
    )
    normalized_eligible_draw_counts = tuple(
        _require_int(
            item,
            path=f"{path}.evaluator_contract.eligible_draw_counts[{index}]",
            minimum=1,
        )
        for index, item in enumerate(eligible_draw_counts)
    )
    if normalized_eligible_draw_counts != EXPECTED_WINDOW_ELIGIBLE_COUNTS:
        raise EvidenceAssemblyError(f"{path}: evaluator eligible counts mismatch")
    if evaluator["native_ticket_count"] != 1:
        raise EvidenceAssemblyError(f"{path}: evaluator native_ticket_count must be one")
    _validate_fraction_pair(
        evaluator["random_reference"],
        expected=EXPECTED_RANDOM_REFERENCE,
        path=f"{path}.evaluator_contract.random_reference",
    )

    if payload["strategy_order_sha256"] != EXPECTED_STRATEGY_ORDER_SHA256:
        raise EvidenceAssemblyError(f"{path}: strategy order hash mismatch")
    if payload["strategy_universe_sha256"] != EXPECTED_STRATEGY_UNIVERSE_SHA256:
        raise EvidenceAssemblyError(f"{path}: strategy universe hash mismatch")
    if payload["rng_classification_sha256"] != EXPECTED_RNG_CLASSIFICATION_SHA256:
        raise EvidenceAssemblyError(f"{path}: RNG classification hash mismatch")

    strategy_universe = _as_list(payload["strategy_universe"], path=f"{path}.strategy_universe")
    _validate_strategy_universe(strategy_universe, path=f"{path}.strategy_universe")

    zone = _as_dict(payload["zone_exclusion"], path=f"{path}.zone_exclusion")
    _require_exact_keys(zone, ZONE_KEYS, path=f"{path}.zone_exclusion")
    if zone["strategy_id"] != ZONE_STRATEGY_ID:
        raise EvidenceAssemblyError(f"{path}: zone exclusion identity mismatch")
    if zone["catalog_ordinal"] != EXPECTED_ZONE_ORDINAL:
        raise EvidenceAssemblyError(f"{path}: zone exclusion ordinal must be 19")
    if zone["status"] != ZONE_STATUS:
        raise EvidenceAssemblyError(f"{path}: zone exclusion must be DRIVER_ERROR")
    if zone["windows"] != []:
        raise EvidenceAssemblyError(f"{path}: zone exclusion must have no windows")

    execution = _as_dict(payload["execution_contract"], path=f"{path}.execution_contract")
    _require_exact_keys(execution, EXECUTION_KEYS, path=f"{path}.execution_contract")
    expected_execution = {
        "process_model": "ONE_PROCESS_PER_STRATEGY",
        "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
        "cache_policy": "NO_REPLAY_RESULT_CACHE",
        "cache_constructor": "ReplayHistoricalPredictions(cache=None)",
        "parallelization": "SERIAL_ONLY_R1",
        "max_concurrency": 1,
        "replay_depth": EXPECTED_REPLAY_DEPTH,
        "source_import_policy": "EXACT_REPLAY_SOURCE_TREE",
    }
    if execution != expected_execution:
        raise EvidenceAssemblyError(f"{path}: execution contract is not the frozen R2 contract")


def _validate_strategy_universe(rows: Sequence[Any], *, path: str) -> None:
    if len(rows) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path} must contain exactly 54 strategies")
    normalized: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, raw in enumerate(rows, 1):
        row = _as_dict(raw, path=f"{path}[{index}]")
        _require_exact_keys(row, IDENTITY_KEYS, path=f"{path}[{index}]")
        strategy_id = _require_string(row["strategy_id"], path=f"{path}[{index}].strategy_id")
        ids.append(strategy_id)
        if row["strategy_version"] != "v0.1":
            raise EvidenceAssemblyError(f"{path}[{index}]: strategy version must be v0.1")
        _require_string(row["adapter_path"], path=f"{path}[{index}].adapter_path")
        _require_int(row["min_history"], path=f"{path}[{index}].min_history", minimum=1)
        if row["native_ticket_count"] != 1:
            raise EvidenceAssemblyError(f"{path}[{index}]: native_ticket_count must be one")
        if row["response_shape"] != "SINGLE_TICKET":
            raise EvidenceAssemblyError(f"{path}[{index}]: response_shape must be SINGLE_TICKET")
        normalized.append(row)
    if tuple(ids) != EXPECTED_STRATEGY_IDS:
        raise EvidenceAssemblyError(
            f"{path}: strategy order/identity is not the frozen 54 universe"
        )
    if len(set(ids)) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}: duplicate strategy id")
    if sha256_hex(canonical_bytes(ids)) != EXPECTED_STRATEGY_ORDER_SHA256:
        raise EvidenceAssemblyError(f"{path}: computed strategy order hash mismatch")
    if sha256_hex(canonical_bytes(normalized)) != EXPECTED_STRATEGY_UNIVERSE_SHA256:
        raise EvidenceAssemblyError(f"{path}: computed normalized strategy hash mismatch")


def _validate_plan(plan: Mapping[str, Any]) -> _ValidatedPlan:
    payload = copy.deepcopy(dict(plan))
    validate_value_domain(payload)
    _require_exact_keys(payload, PLAN_KEYS, path="plan_manifest")
    if payload["manifest_schema_version"] != PLAN_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError("plan_manifest: schema version mismatch")
    _validate_common_identity(payload, path="plan_manifest")
    _validate_manifest_self_hash(payload, path="plan_manifest")
    return _ValidatedPlan(payload)


def _validate_plan_binding(payload: dict[str, Any], plan: _ValidatedPlan, *, path: str) -> None:
    for field in (
        "protocol_version",
        "canonicalization",
        "old_84_reuse",
        "source_fingerprint",
        "dataset_fingerprint",
        "runtime_fingerprint",
        "target_identity",
        "evaluator_contract",
        "strategy_order_sha256",
        "strategy_universe_sha256",
        "rng_classification_sha256",
        "strategy_universe",
        "zone_exclusion",
        "execution_contract",
    ):
        if not _canonical_equal(payload[field], plan.payload[field]):
            raise EvidenceAssemblyError(f"{path}: {field} does not match the accepted plan")


def _validate_run_window(
    raw: object, *, path: str, expected_kind: str, expected_count: int
) -> dict[str, Any]:
    window = _as_dict(raw, path=path)
    _require_exact_keys(window, RUN_WINDOW_KEYS, path=path)
    if window["window_kind"] != expected_kind:
        raise EvidenceAssemblyError(f"{path}: window order/kind mismatch")
    if window["window_status"] != "COMPLETE":
        raise EvidenceAssemblyError(f"{path}: window must be COMPLETE")
    if window["eligible_draw_count"] != expected_count:
        raise EvidenceAssemblyError(f"{path}: eligible_draw_count mismatch")
    success_count = _require_int(window["success_count"], path=f"{path}.success_count", minimum=0)
    if success_count > expected_count:
        raise EvidenceAssemblyError(f"{path}: success_count exceeds eligible_draw_count")
    return window


def _validate_run_records(value: object, *, path: str) -> tuple[dict[str, Any], ...]:
    records = _as_list(value, path=path)
    if len(records) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}: exactly 54 complete evaluation records are required")
    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(records, 1):
        record = _as_dict(raw, path=f"{path}[{index}]")
        _require_exact_keys(record, RUN_RECORD_KEYS, path=f"{path}[{index}]")
        if record["strategy_id"] != EXPECTED_STRATEGY_IDS[index - 1]:
            raise EvidenceAssemblyError(f"{path}[{index}]: strategy order/identity mismatch")
        _require_string(record["strategy_name"], path=f"{path}[{index}].strategy_name")
        if record["native_ticket_count"] != 1:
            raise EvidenceAssemblyError(f"{path}[{index}]: native_ticket_count must be one")
        if record["hit_tier_id"] != EXPECTED_HIT_TIER_ID:
            raise EvidenceAssemblyError(f"{path}[{index}]: hit tier must be M3_PLUS")
        windows = _as_list(record["windows"], path=f"{path}[{index}].windows")
        if len(windows) != len(EXPECTED_WINDOW_ORDER):
            raise EvidenceAssemblyError(f"{path}[{index}]: four windows are required")
        validated_windows = [
            _validate_run_window(
                raw_window,
                path=f"{path}[{index}].windows[{window_index}]",
                expected_kind=EXPECTED_WINDOW_ORDER[window_index],
                expected_count=EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index],
            )
            for window_index, raw_window in enumerate(windows)
        ]
        if len({window["window_kind"] for window in validated_windows}) != len(
            EXPECTED_WINDOW_ORDER
        ):
            raise EvidenceAssemblyError(f"{path}[{index}]: duplicate window kind")
        normalized_record = dict(record)
        normalized_record["windows"] = validated_windows
        validated.append(normalized_record)
    ids = [record["strategy_id"] for record in validated]
    if len(set(ids)) != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError(f"{path}: duplicate strategy id")
    if set(ids) != set(EXPECTED_STRATEGY_IDS):
        raise EvidenceAssemblyError(f"{path}: missing or extra strategy id")
    return tuple(validated)


def _validate_run(run: Mapping[str, Any], plan: _ValidatedPlan, *, label: str) -> _ValidatedRun:
    payload = copy.deepcopy(dict(run))
    validate_value_domain(payload)
    _require_exact_keys(payload, RUN_KEYS, path=label)
    if payload["manifest_schema_version"] != RUN_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError(f"{label}: schema version mismatch")
    if payload["plan_manifest_sha256"] != plan.payload["manifest_sha256"]:
        raise EvidenceAssemblyError(f"{label}: plan manifest binding mismatch")
    _validate_common_identity(payload, path=label)
    _validate_plan_binding(payload, plan, path=label)
    records = _validate_run_records(
        payload["evaluation_records"], path=f"{label}.evaluation_records"
    )
    declared_deterministic = _require_hash(
        payload["deterministic_payload_sha256"], path=f"{label}.deterministic_payload_sha256"
    )
    if declared_deterministic != deterministic_run_sha256(payload):
        raise EvidenceAssemblyError(f"{label}: deterministic payload hash mismatch")
    _validate_manifest_self_hash(payload, path=label)
    return _ValidatedRun(payload, records)


def _validate_fraction_pair(
    value: object, *, expected: Fraction | None = None, path: str
) -> Fraction:
    pair = _as_dict(value, path=path)
    if set(pair) != {"numerator", "denominator"}:
        raise EvidenceAssemblyError(f"{path}: fraction pair must have numerator and denominator")
    numerator = _require_string(pair["numerator"], path=f"{path}.numerator", nonempty=False)
    denominator = _require_string(pair["denominator"], path=f"{path}.denominator")
    if _DECIMAL_RE.fullmatch(numerator) is None or _DECIMAL_RE.fullmatch(denominator) is None:
        raise EvidenceAssemblyError(
            f"{path}: fraction components must be canonical decimal strings"
        )
    numerator_int = int(numerator)
    denominator_int = int(denominator)
    if denominator_int <= 0:
        raise EvidenceAssemblyError(f"{path}: denominator must be positive")
    fraction = Fraction(numerator_int, denominator_int)
    if numerator != str(fraction.numerator) or denominator != str(fraction.denominator):
        raise EvidenceAssemblyError(f"{path}: fraction is not reduced")
    if expected is not None and fraction != expected:
        raise EvidenceAssemblyError(f"{path}: fraction differs from the frozen reference")
    return fraction


def _validate_acceptance(
    acceptance: Mapping[str, Any],
    plan: _ValidatedPlan,
    run_a: _ValidatedRun,
    run_b: _ValidatedRun,
) -> None:
    payload = copy.deepcopy(dict(acceptance))
    validate_value_domain(payload)
    _require_exact_keys(payload, ACCEPTANCE_KEYS, path="acceptance_manifest")
    if payload["manifest_schema_version"] != ACCEPTANCE_MANIFEST_SCHEMA_VERSION:
        raise EvidenceAssemblyError("acceptance_manifest: schema version mismatch")
    if payload["plan_manifest_sha256"] != plan.payload["manifest_sha256"]:
        raise EvidenceAssemblyError("acceptance_manifest: plan binding mismatch")
    if payload["run_a_manifest_sha256"] != run_a.payload["manifest_sha256"]:
        raise EvidenceAssemblyError("acceptance_manifest: run-A binding mismatch")
    if payload["run_b_manifest_sha256"] != run_b.payload["manifest_sha256"]:
        raise EvidenceAssemblyError("acceptance_manifest: run-B binding mismatch")
    if run_a.payload["manifest_sha256"] == run_b.payload["manifest_sha256"]:
        raise EvidenceAssemblyError(
            "acceptance_manifest: two distinct run manifest identities are required"
        )
    _validate_common_identity(payload, path="acceptance_manifest")
    _validate_plan_binding(payload, plan, path="acceptance_manifest")
    if payload["acceptance_status"] != "PASS":
        raise EvidenceAssemblyError("acceptance_manifest: two-run acceptance must be PASS")
    comparison = _as_dict(payload["comparison"], path="acceptance_manifest.comparison")
    _require_exact_keys(comparison, COMPARISON_KEYS, path="acceptance_manifest.comparison")
    if comparison["status"] != "PASS":
        raise EvidenceAssemblyError("acceptance_manifest: comparison status must be PASS")
    if (
        comparison["run_a_deterministic_payload_sha256"]
        != run_a.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("acceptance_manifest: run-A deterministic hash mismatch")
    if (
        comparison["run_b_deterministic_payload_sha256"]
        != run_b.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("acceptance_manifest: run-B deterministic hash mismatch")
    if (
        run_a.payload["deterministic_payload_sha256"]
        != run_b.payload["deterministic_payload_sha256"]
    ):
        raise EvidenceAssemblyError("acceptance_manifest: two runs differ deterministically")
    if comparison["evaluated_strategy_count"] != EXPECTED_STRATEGY_COUNT:
        raise EvidenceAssemblyError("acceptance_manifest: evaluated strategy count mismatch")
    if comparison["eligible_cell_count"] != EXPECTED_EVALUATED_CELL_COUNT:
        raise EvidenceAssemblyError("acceptance_manifest: eligible cell count mismatch")
    if comparison["zone_status"] != ZONE_STATUS:
        raise EvidenceAssemblyError("acceptance_manifest: zone status mismatch")
    if comparison["target_order_sha256"] != plan.payload["target_identity"]["target_order_sha256"]:
        raise EvidenceAssemblyError("acceptance_manifest: target identity mismatch")
    _validate_manifest_self_hash(payload, path="acceptance_manifest")


def _project_record(record: dict[str, Any]) -> RecommendationEvidenceStrategyRecord:
    windows: list[RecommendationEvidenceWindow] = []
    for raw_window in cast(list[dict[str, Any]], record["windows"]):
        eligible_count = cast(int, raw_window["eligible_draw_count"])
        observed = Fraction(cast(int, raw_window["success_count"]), eligible_count)
        windows.append(
            RecommendationEvidenceWindow(
                window_kind=cast(str, raw_window["window_kind"]),
                window_status="COMPLETE",
                eligible_draw_count=eligible_count,
                observed_value=observed,
                random_reference=EXPECTED_RANDOM_REFERENCE,
                delta_vs_random=observed - EXPECTED_RANDOM_REFERENCE,
            )
        )
    return RecommendationEvidenceStrategyRecord(
        strategy_id=cast(str, record["strategy_id"]),
        strategy_name=cast(str, record["strategy_name"]),
        native_ticket_count=1,
        status=StrategyBacktestStatus.EVALUATED,
        hit_tier_id=EXPECTED_HIT_TIER_ID,
        windows=tuple(windows),
    )


def _zone_record() -> RecommendationEvidenceStrategyRecord:
    return RecommendationEvidenceStrategyRecord(
        strategy_id=ZONE_STRATEGY_ID,
        strategy_name=ZONE_STRATEGY_NAME,
        native_ticket_count=1,
        status=StrategyBacktestStatus.DRIVER_ERROR,
        hit_tier_id=EXPECTED_HIT_TIER_ID,
        windows=(),
    )


def assemble_artifact(
    plan_manifest: Mapping[str, Any],
    run_a_manifest: Mapping[str, Any],
    run_b_manifest: Mapping[str, Any],
    acceptance_manifest: Mapping[str, Any],
) -> NextDrawRecommendationEvidenceArtifact:
    """Validate accepted R2 material and assemble the 55-record artifact.

    This function is pure with respect to replay state: it does not open a
    database, import an adapter, execute a target, or write a file.
    """

    plan = _validate_plan(plan_manifest)
    run_a = _validate_run(run_a_manifest, plan, label="run_a_manifest")
    run_b = _validate_run(run_b_manifest, plan, label="run_b_manifest")
    _validate_acceptance(acceptance_manifest, plan, run_a, run_b)

    records: list[RecommendationEvidenceStrategyRecord] = [
        _project_record(record) for record in run_a.records
    ]
    records.insert(EXPECTED_ZONE_ORDINAL - 1, _zone_record())
    if len(records) != EXPECTED_RECORD_COUNT:
        raise EvidenceAssemblyError("assembled artifact record census is not 55")

    dataset = cast(dict[str, Any], plan.payload["dataset_fingerprint"])
    artifact = NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256=cast(
            str, plan.payload["source_fingerprint"]["source_draw_db_sha256"]
        ),
        source_draw_count=cast(int, dataset["source_draw_count"]),
        last_causal_draw_id=cast(str, dataset["last_causal_draw_id"]),
        replay_depth=EXPECTED_REPLAY_DEPTH,
        hit_tier_id=EXPECTED_HIT_TIER_ID,
        records=tuple(records),
    )
    validate_assembled_artifact(artifact.canonical_dict())
    return artifact


def build_evidence(
    plan_manifest: Mapping[str, Any],
    run_a_manifest: Mapping[str, Any],
    run_b_manifest: Mapping[str, Any],
    acceptance_manifest: Mapping[str, Any],
) -> dict[str, object]:
    """Compatibility wrapper returning the canonical artifact mapping."""

    return assemble_artifact(
        plan_manifest,
        run_a_manifest,
        run_b_manifest,
        acceptance_manifest,
    ).canonical_dict()


def artifact_canonical_bytes(artifact: NextDrawRecommendationEvidenceArtifact) -> bytes:
    """Return LF-free LCJ-1 bytes for the assembled artifact."""

    return canonical_file_bytes(artifact.canonical_dict())[:-1]


def artifact_canonical_file_bytes(artifact: NextDrawRecommendationEvidenceArtifact) -> bytes:
    """Return repository artifact bytes: canonical JSON plus exactly one LF."""

    return canonical_file_bytes(artifact.canonical_dict())


def validate_assembled_artifact(payload: Mapping[str, Any]) -> None:
    """Validate an assembled artifact's census, fractions, and self digest."""

    document = copy.deepcopy(dict(payload))
    validate_value_domain(document)
    artifact_keys = frozenset(
        {
            "artifact_schema_version",
            "artifact_sha256",
            "computation_status",
            "hit_tier_id",
            "last_causal_draw_id",
            "lottery_type",
            "records",
            "replay_depth",
            "source_draw_count",
            "source_draw_db_sha256",
        }
    )
    _require_exact_keys(document, artifact_keys, path="artifact")
    if document["artifact_schema_version"] != RECOMMENDATION_EVIDENCE_SCHEMA_VERSION:
        raise EvidenceAssemblyError("artifact schema version mismatch")
    if document["computation_status"] != "FRESH_UNREVIEWED":
        raise EvidenceAssemblyError("artifact computation status mismatch")
    if document["lottery_type"] != "BIG_LOTTO":
        raise EvidenceAssemblyError("artifact lottery type mismatch")
    if document["hit_tier_id"] != EXPECTED_HIT_TIER_ID:
        raise EvidenceAssemblyError("artifact hit tier mismatch")
    if document["replay_depth"] != EXPECTED_REPLAY_DEPTH:
        raise EvidenceAssemblyError("artifact replay depth mismatch")
    _require_hash(document["source_draw_db_sha256"], path="artifact.source_draw_db_sha256")
    _require_int(document["source_draw_count"], path="artifact.source_draw_count", minimum=1)
    _require_string(document["last_causal_draw_id"], path="artifact.last_causal_draw_id")
    declared = _require_hash(document["artifact_sha256"], path="artifact.artifact_sha256")
    if declared != self_key_removed_sha256(document, "artifact_sha256"):
        raise EvidenceAssemblyError("artifact self digest mismatch")

    records = _as_list(document["records"], path="artifact.records")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise EvidenceAssemblyError("artifact must contain exactly 55 records")
    expected_ids: list[str] = list(EXPECTED_STRATEGY_IDS)
    expected_ids.insert(EXPECTED_ZONE_ORDINAL - 1, ZONE_STRATEGY_ID)
    for index, raw_record in enumerate(records, 1):
        record = _as_dict(raw_record, path=f"artifact.records[{index}]")
        _require_exact_keys(
            record,
            RUN_RECORD_KEYS - {"windows"} | {"status", "windows"},
            path=f"artifact.records[{index}]",
        )
        if record["strategy_id"] != expected_ids[index - 1]:
            raise EvidenceAssemblyError(f"artifact.records[{index}]: wrong strategy order")
        _require_string(record["strategy_name"], path=f"artifact.records[{index}].strategy_name")
        if record["native_ticket_count"] != 1:
            raise EvidenceAssemblyError(f"artifact.records[{index}]: native ticket count mismatch")
        if record["hit_tier_id"] != EXPECTED_HIT_TIER_ID:
            raise EvidenceAssemblyError(f"artifact.records[{index}]: hit tier mismatch")
        windows = _as_list(record["windows"], path=f"artifact.records[{index}].windows")
        if index == EXPECTED_ZONE_ORDINAL:
            if record["status"] != "DRIVER_ERROR" or windows:
                raise EvidenceAssemblyError("artifact zone placeholder is malformed")
            continue
        if record["status"] != "EVALUATED" or len(windows) != len(EXPECTED_WINDOW_ORDER):
            raise EvidenceAssemblyError(
                f"artifact.records[{index}]: evaluated record is incomplete"
            )
        for window_index, raw_window in enumerate(windows):
            window = _as_dict(raw_window, path=f"artifact.records[{index}].windows[{window_index}]")
            window_keys = frozenset(
                {
                    "window_kind",
                    "window_status",
                    "eligible_draw_count",
                    "observed_value",
                    "random_reference",
                    "delta_vs_random",
                }
            )
            _require_exact_keys(
                window, window_keys, path=f"artifact.records[{index}].windows[{window_index}]"
            )
            if window["window_kind"] != EXPECTED_WINDOW_ORDER[window_index]:
                raise EvidenceAssemblyError("artifact window order mismatch")
            if window["window_status"] != "COMPLETE":
                raise EvidenceAssemblyError("artifact window status mismatch")
            eligible = EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index]
            if window["eligible_draw_count"] != eligible:
                raise EvidenceAssemblyError("artifact eligible count mismatch")
            observed = _validate_fraction_pair(
                window["observed_value"], path="artifact.observed_value"
            )
            random_reference = _validate_fraction_pair(
                window["random_reference"],
                expected=EXPECTED_RANDOM_REFERENCE,
                path="artifact.random_reference",
            )
            delta = _validate_fraction_pair(
                window["delta_vs_random"], path="artifact.delta_vs_random"
            )
            if delta != observed - random_reference:
                raise EvidenceAssemblyError("artifact delta fraction mismatch")
            if observed < 0 or observed > 1:
                raise EvidenceAssemblyError("artifact observed fraction is outside [0, 1]")
            if eligible % observed.denominator != 0:
                raise EvidenceAssemblyError(
                    "artifact observed fraction is not an eligible-count ratio"
                )

    if [cast(dict[str, Any], record)["strategy_id"] for record in records].count(
        ZONE_STRATEGY_ID
    ) != 1:
        raise EvidenceAssemblyError("artifact zone placeholder census mismatch")


def load_manifest_file(path: Path) -> dict[str, Any]:
    """Load one exact canonical manifest file (one trailing LF, no extras)."""

    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise EvidenceAssemblyError(f"{path}: UTF-8 BOM is forbidden")
    if b"\r" in raw:
        raise EvidenceAssemblyError(f"{path}: CRLF/CR bytes are forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise EvidenceAssemblyError(f"{path}: canonical file must end with exactly one LF")
    value = loads_canonical(raw[:-1])
    payload = _as_dict(value, path=str(path))
    if canonical_file_bytes(payload) != raw:
        raise EvidenceAssemblyError(f"{path}: bytes are not canonical LCJ-1 file bytes")
    return payload


def load_artifact_file(path: Path) -> NextDrawRecommendationEvidenceArtifact:
    """Load and validate a canonical assembled artifact file."""

    payload = load_manifest_file(path)
    validate_assembled_artifact(payload)
    return NextDrawRecommendationEvidenceArtifact.from_canonical_dict(payload)


def _refuse_packaged_artifact_output(output: Path) -> None:
    resolved = output.resolve()
    if resolved.name == "biglotto_next_draw_recommendation_evidence_v1.json":
        raise EvidenceAssemblyError("refusing to overwrite the current packaged v1 artifact")
    if "src/lottolab/strategies/data" in resolved.as_posix():
        raise EvidenceAssemblyError(
            "R2 assembly output may not be written into packaged strategy data"
        )


def assemble_from_paths(
    *,
    plan_path: Path,
    run_a_path: Path,
    run_b_path: Path,
    acceptance_path: Path,
    output_path: Path,
) -> NextDrawRecommendationEvidenceArtifact:
    """CLI-oriented path wrapper; the output is written only after validation."""

    _refuse_packaged_artifact_output(output_path)
    artifact = assemble_artifact(
        load_manifest_file(plan_path),
        load_manifest_file(run_a_path),
        load_manifest_file(run_b_path),
        load_manifest_file(acceptance_path),
    )
    output_path.write_bytes(artifact_canonical_file_bytes(artifact))
    return artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="sealed R2 plan manifest")
    parser.add_argument("--run-a", required=True, type=Path, help="sealed R2 run-A manifest")
    parser.add_argument("--run-b", required=True, type=Path, help="sealed R2 run-B manifest")
    parser.add_argument(
        "--acceptance", required=True, type=Path, help="sealed R2 acceptance manifest"
    )
    parser.add_argument("--output", required=True, type=Path, help="new synthetic artifact path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        artifact = assemble_from_paths(
            plan_path=args.plan,
            run_a_path=args.run_a,
            run_b_path=args.run_b,
            acceptance_path=args.acceptance,
            output_path=args.output,
        )
    except (OSError, EvidenceAssemblyError, ValueError) as exc:
        _parser().error(str(exc))
    print(artifact.artifact_sha256)
    return 0


__all__ = [
    "ACCEPTANCE_MANIFEST_SCHEMA_VERSION",
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
    "REPOSITORY_HEAD",
    "REPOSITORY_TREE",
    "RUN_MANIFEST_SCHEMA_VERSION",
    "ZONE_STRATEGY_ID",
    "EvidenceAssemblyError",
    "artifact_canonical_bytes",
    "artifact_canonical_file_bytes",
    "assemble_artifact",
    "assemble_from_paths",
    "build_evidence",
    "deterministic_run_sha256",
    "load_artifact_file",
    "load_manifest_file",
    "manifest_sha256",
    "seal_manifest",
    "seal_run_manifest",
    "validate_assembled_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
