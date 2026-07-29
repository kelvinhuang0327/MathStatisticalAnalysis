"""Build the pinned 221-method BIG_LOTTO research-universe catalog.

This tool is intentionally not a discovery scanner.  It joins the frozen
P541B method classification to the later P541B-R2 source/safety evidence and
refuses to emit anything unless the audited 221-method universe is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

EXPECTED_METHOD_COUNT = 221
CATALOG_SCHEMA_VERSION = "BIG_LOTTO_FULL_STRATEGY_CATALOG_V1"
CATALOG_POLICY_VERSION = "BIG_LOTTO_ALL_ACTUAL_METHODS_REGARDLESS_LEGACY_GOVERNANCE_V1"
RESEARCH_DISCLAIMER = (
    "Historical success rates and random-baseline comparisons are descriptive "
    "research only and do not guarantee future prizes."
)
FIRST_BATCH_REPLAY_STRATEGY_IDS = (
    "bet2_fourier_expansion_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_ts3_markov_4bet_w30",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "ts3_regime_3bet",
)
FIRST_BATCH_EXACT_METHOD_MAPPINGS = {
    "biglotto_triple_strike": "tools/predict_biglotto_triple_strike.py",
    "biglotto_ts3_markov_4bet_w30": (
        "tools/backtest_biglotto_5bet_ts3markov.py"
    ),
}
FIRST_BATCH_MAPPING_REASONS = {
    "bet2_fourier_expansion_biglotto": (
        "P541A points to replay_strategy_registry.py and the P42 wrapper; neither "
        "is one of the audited 221 actual-method rows."
    ),
    "biglotto_deviation_2bet": (
        "The registry imports tools/predict_biglotto_deviation_2bet.py, but that "
        "source is not one of the audited 221 actual-method rows."
    ),
    "biglotto_echo_aware_3bet": (
        "The P93 adapter imports tools/predict_biglotto_echo_3bet.py; the audited "
        "221 contains a distinct echo_2bet source, not this strategy."
    ),
    "cold_complement_biglotto": (
        "P541A points to the excluded P42 wrapper and supplies no one-to-one "
        "foreign key into the audited 221 rows."
    ),
    "coldpool15_biglotto": (
        "P541A points to the excluded P42 wrapper and supplies no one-to-one "
        "foreign key into the audited 221 rows."
    ),
    "fourier30_markov30_biglotto": (
        "P541A points to the excluded P42 wrapper and supplies no one-to-one "
        "foreign key into the audited 221 rows."
    ),
    "markov_2bet_biglotto": (
        "P541A points to the excluded P42 wrapper and supplies no one-to-one "
        "foreign key into the audited 221 rows."
    ),
    "markov_single_biglotto": (
        "P541A points to the excluded P42 wrapper and supplies no one-to-one "
        "foreign key into the audited 221 rows."
    ),
    "ts3_regime_3bet": (
        "The registry documents a compatibility reconstruction but supplies no "
        "one-to-one foreign key into the audited 221 rows."
    ),
}
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
REPLAY_EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_REPLAY_BATCH_EXACT2_EVIDENCE_V1"
RANDOM_NATIVE_EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_RANDOM_NATIVE_EVIDENCE_V1"
)
RANDOM_NATIVE_PROTOCOL = "legacy_random_native/cpython_mt19937_v1"
RANDOM_NATIVE_METHODS = {
    "lottery_api/models/core_satellite.py": (
        "611284461323dbbca0b5959498bf3f0e86bfaa35c4b902fdb64aabfe5076a6e2"
    ),
    "lottery_api/models/zone_split.py": (
        "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211"
    ),
}
HISTORY_NATIVE_EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HISTORY_NATIVE_EVIDENCE_V1"
)
HISTORY_NATIVE_PROTOCOL = "legacy_history_native/v1"
HISTORY_NATIVE_METHODS = {
    "lottery_api/models/optimized_ensemble.py": (
        "e05e0fde22d7a477cfa64f7562dec853a95eaa5e200764531eefe8158df887a2",
        2148,
        1,
        {"CLOSED_INSUFFICIENT_HISTORY": 1},
    ),
    "lottery_api/models/social_wisdom_predictor.py": (
        "a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b",
        2148,
        8,
        {"CLOSED_INSUFFICIENT_HISTORY": 1},
    ),
    "tools/quick_ml_predict.py": (
        "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80",
        4,
        2,
        {
            "CLOSED_EXECUTION_ERROR": 2144,
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
    ),
    "tools/big_lotto_exhaustive_audit.py": (
        "694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c",
        2099,
        3,
        {"CLOSED_INSUFFICIENT_HISTORY": 50},
    ),
}
STATIC_DISPOSITION_EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_EVIDENCE_V1"
)
STATIC_CLOSED_METHODS = {
    "tools/analyze_theoretical_vs_actual.py": (
        "7b4cedc419e1435085f376acd57baac2c3534413f3d10ad332aad9ef96f5e532",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "lottery_api/models/p47_wave4_powerlotto_adapters.py": (
        "f167f693f4a322ba3bcf4037b7fbebca4f03d4085a967ca8145a94859f37e514",
        "FROZEN_SOURCE_SUPPORTS_POWER_LOTTO_ONLY",
    ),
    "lottery_api/models/big_lotto_optimizer.py": (
        "bbeb05c435774e6406a7af4097b69194e5844aec42dd63a96fa3e0bc6d947cb0",
        "REQUIRED_UPSTREAM_PREDICTIONS_NOT_IDENTIFIED_OR_PRESERVED",
    ),
    "tools/advanced_prediction_engine.py": (
        "f92be0a25fc2da83eb9d999081a80d59c4c9af089edcefcdf44f6f3cfc16a8ce",
        "RUNTIME_DATASET_AND_ML_BACKEND_BRANCH_NOT_PINNED",
    ),
    "lottery_api/models/bayesian_ensemble.py": (
        "711996adc4539b149a3b5de6b48d39ec2d453c2a00725519e377885c42ecead1",
        "REQUIRED_UNIFIED_ENGINE_IMPLEMENTATION_NOT_IDENTIFIED",
    ),
    "lottery_api/models/autogluon_model.py": (
        "e9a3e1a09e721c2646a93ca124216ea6c79e64a7c750539712ea79d680645571",
        "MUTABLE_OPTIONAL_BEST_CONFIG_NOT_PRESERVED",
    ),
}


class CatalogBuildError(ValueError):
    """The frozen audit inputs do not satisfy the catalog build contract."""


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogBuildError(f"{path}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise CatalogBuildError(f"{path}: top-level JSON must be an object")
    return cast(dict[str, Any], parsed), hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _required_text(mapping: dict[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CatalogBuildError(f"{context}: {key} must be a non-empty string")
    return value


def _strategy_id(method_id: str, source_sha256: str) -> str:
    basename = Path(method_id).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", basename).strip("_")
    if not slug:
        slug = "method"
    return f"legacy_biglotto__{slug}__{source_sha256[:12]}"


def _build_record(
    historical: dict[str, Any],
    r2: dict[str, Any],
    *,
    frozen_source_commit: str,
) -> dict[str, object]:
    method_id = _required_text(historical, "method_id", context="P541B record")
    if r2.get("method_id") != method_id:
        raise CatalogBuildError(f"{method_id}: R2 method identity mismatch")

    source_identity_raw = r2.get("source_identity")
    safety_raw = r2.get("safety_classification")
    if not isinstance(source_identity_raw, dict) or not isinstance(safety_raw, dict):
        raise CatalogBuildError(f"{method_id}: incomplete R2 evidence")
    source_identity = cast(dict[str, Any], source_identity_raw)
    safety = cast(dict[str, Any], safety_raw)

    source_commit = _required_text(
        source_identity,
        "source_commit",
        context=f"{method_id} source_identity",
    )
    if source_commit != frozen_source_commit:
        raise CatalogBuildError(f"{method_id}: source commit leaves frozen snapshot")
    source_sha256 = _required_text(
        source_identity,
        "sha256",
        context=f"{method_id} source_identity",
    )
    if _SHA256.fullmatch(source_sha256) is None:
        raise CatalogBuildError(f"{method_id}: invalid source SHA-256")
    byte_size = source_identity.get("byte_size")
    if type(byte_size) is not int or byte_size < 0:
        raise CatalogBuildError(f"{method_id}: invalid source byte size")

    duplicate_target = historical.get("duplicate_of_existing_strategy")
    if duplicate_target is not None and (
        not isinstance(duplicate_target, str) or not duplicate_target
    ):
        raise CatalogBuildError(f"{method_id}: invalid duplicate target")
    reproduction_status = (
        "DUPLICATE_ALIAS"
        if isinstance(duplicate_target, str)
        else "OWNER_DECISION_REQUIRED"
    )
    if reproduction_status == "DUPLICATE_ALIAS":
        status_reason = (
            "The frozen P541B audit identifies this method as an alias of "
            f"{duplicate_target}; no independent ranking row may be fabricated."
        )
    else:
        status_reason = (
            "The method is in the authoritative 221-method universe, but its native "
            "ticket semantics and causal adapter have not yet been reproduced and "
            "therefore require an explicit owner disposition before ranking."
        )

    record: dict[str, object] = {
        "candidate_k_semantics": "NOT_YET_REPRODUCED",
        "combination_count_semantics": "NOT_YET_REPRODUCED",
        "discovery_group": _required_text(
            historical,
            "discovery_group",
            context=method_id,
        ),
        "legacy_method_id": method_id,
        "legacy_recommended_action": _required_text(
            historical,
            "recommended_action",
            context=method_id,
        ),
        "legacy_runnable_status": _required_text(
            historical,
            "runnable_status",
            context=method_id,
        ),
        "method_family": _required_text(historical, "method_family", context=method_id),
        "native_ticket_semantics": "NOT_YET_REPRODUCED",
        "reproduction_status": reproduction_status,
        "source_blob_id": _required_text(
            source_identity,
            "blob_id",
            context=f"{method_id} source_identity",
        ),
        "source_byte_size": byte_size,
        "source_commit": source_commit,
        "source_path": _required_text(historical, "source_path", context=method_id),
        "source_scan_status": _required_text(r2, "scan_status", context=method_id),
        "source_sha256": source_sha256,
        "source_type": _required_text(historical, "source_type", context=method_id),
        "status_reason": status_reason,
        "strategy_id": _strategy_id(method_id, source_sha256),
        "strategy_version": (
            f"legacy-source-{source_commit[:12]}-{source_sha256[:12]}"
        ),
        "ticket_order_semantics": "NOT_YET_REPRODUCED",
        "ticket_duplicate_semantics": "NOT_YET_REPRODUCED",
        "unranked_reason": (
            "DUPLICATE_ALIAS"
            if reproduction_status == "DUPLICATE_ALIAS"
            else "OWNER_DECISION_REQUIRED_NATIVE_SEMANTICS_NOT_REPRODUCED"
        ),
        "why_not_runnable": _required_text(
            historical,
            "why_not_runnable",
            context=method_id,
        ),
    }
    disposition = _required_text(safety, "disposition", context=f"{method_id} safety")
    record["r2_safety_disposition"] = disposition
    if isinstance(duplicate_target, str):
        record["duplicate_alias_target"] = duplicate_target
    return record


def _apply_replay_batch_evidence(
    records: list[dict[str, object]],
    evidence_path: Path,
) -> str:
    evidence, evidence_sha256 = _read_json(evidence_path)
    if evidence.get("evidence_schema_version") != REPLAY_EVIDENCE_SCHEMA_VERSION:
        raise CatalogBuildError("replay evidence schema version is unsupported")
    before = evidence.get("source_database_sha256_before")
    after = evidence.get("source_database_sha256_after")
    if (
        type(before) is not str
        or _SHA256.fullmatch(before) is None
        or after != before
    ):
        raise CatalogBuildError("replay evidence does not prove an unchanged source DB")
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
    ):
        value = evidence.get(key)
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise CatalogBuildError(f"replay evidence {key} is invalid")
    if (
        evidence.get("constructor") != "strategy_preserving_20_ticket/v1"
        or evidence.get("backtest_policy_version")
        != "BIG_LOTTO_CAUSAL_ORDERED_20_PREFIX_5_10_15_20_V1"
        or evidence.get("target_draw_count") != 1552
    ):
        raise CatalogBuildError("replay evidence execution contract is invalid")

    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogBuildError("replay evidence must contain exactly two strategies")
    rows = cast(list[object], rows_raw)
    if len(rows) != 2:
        raise CatalogBuildError("replay evidence must contain exactly two strategies")
    record_by_id = {
        cast(str, record["strategy_id"]): record for record in records
    }
    expected = {
        "biglotto_triple_strike": (
            FIRST_BATCH_EXACT_METHOD_MAPPINGS["biglotto_triple_strike"],
            1550,
            3,
        ),
        "biglotto_ts3_markov_4bet_w30": (
            FIRST_BATCH_EXACT_METHOD_MAPPINGS[
                "biglotto_ts3_markov_4bet_w30"
            ],
            1500,
            4,
        ),
    }
    seen: set[str] = set()
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogBuildError(f"replay evidence strategies[{index}] is invalid")
        row = cast(dict[str, Any], candidate)
        registry_id = _required_text(
            row,
            "registry_strategy_id",
            context=f"replay evidence strategies[{index}]",
        )
        if registry_id in seen or registry_id not in expected:
            raise CatalogBuildError("replay evidence strategy identity is invalid")
        seen.add(registry_id)
        method_id, execution_count, native_count = expected[registry_id]
        if (
            row.get("legacy_method_id") != method_id
            or row.get("execution_count") != execution_count
            or row.get("native_ticket_count") != native_count
        ):
            raise CatalogBuildError("replay evidence native execution contract changed")
        catalog_id = _required_text(
            row,
            "catalog_strategy_id",
            context=f"replay evidence strategies[{index}]",
        )
        record = record_by_id.get(catalog_id)
        if (
            record is None
            or record["legacy_method_id"] != method_id
            or row.get("strategy_version") != record["strategy_version"]
        ):
            raise CatalogBuildError("replay evidence leaves the frozen 221 universe")
        record.update(
            {
                "candidate_k_semantics": "NOT_APPLICABLE_NO_CANDIDATE_K",
                "combination_count_semantics": (
                    "NOT_APPLICABLE_NO_STRATEGY_COMBINATION_COUNT"
                ),
                "native_ticket_semantics": (
                    f"EXACT_REPLAY_BACKED_SOURCE_NATIVE_{native_count}_TICKETS"
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    f"Exact source/symbol replay reproduction completed for "
                    f"{execution_count} causal executions; compact evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "SOURCE_NATIVE_ORDER_PRESERVED_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )
    if seen != set(expected):
        raise CatalogBuildError("replay evidence omits an exact-mapped strategy")
    return evidence_sha256


def _apply_random_native_batch_evidence(
    records: list[dict[str, object]],
    evidence_path: Path,
) -> str:
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        evidence.get("evidence_schema_version")
        != RANDOM_NATIVE_EVIDENCE_SCHEMA_VERSION
    ):
        raise CatalogBuildError("random-native evidence schema is unsupported")
    before = evidence.get("source_database_sha256_before")
    after = evidence.get("source_database_sha256_after")
    if (
        type(before) is not str
        or _SHA256.fullmatch(before) is None
        or after != before
    ):
        raise CatalogBuildError(
            "random-native evidence does not prove an unchanged source DB"
        )
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
    ):
        value = evidence.get(key)
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise CatalogBuildError(f"random-native evidence {key} is invalid")
    if (
        evidence.get("constructor") != "strategy_preserving_20_ticket/v1"
        or evidence.get("random_native_protocol") != RANDOM_NATIVE_PROTOCOL
        or evidence.get("target_draw_count") != 2149
    ):
        raise CatalogBuildError("random-native execution contract changed")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogBuildError("random-native evidence strategies are missing")
    rows = cast(list[object], rows_raw)
    if len(rows) != len(RANDOM_NATIVE_METHODS):
        raise CatalogBuildError(
            "random-native evidence must contain exactly two strategies"
        )
    record_by_id = {
        cast(str, record["strategy_id"]): record for record in records
    }
    seen: set[str] = set()
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogBuildError(
                f"random-native evidence strategies[{index}] is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = _required_text(
            row,
            "legacy_method_id",
            context=f"random-native evidence strategies[{index}]",
        )
        if method_id in seen or method_id not in RANDOM_NATIVE_METHODS:
            raise CatalogBuildError("random-native method identity is invalid")
        seen.add(method_id)
        if (
            row.get("source_sha256") != RANDOM_NATIVE_METHODS[method_id]
            or row.get("successful_execution_count") != 2148
            or row.get("closed_execution_count") != 1
            or row.get("native_ticket_count") != 3
        ):
            raise CatalogBuildError(
                "random-native native execution contract changed"
            )
        catalog_id = _required_text(
            row,
            "catalog_strategy_id",
            context=f"random-native evidence strategies[{index}]",
        )
        record = record_by_id.get(catalog_id)
        if (
            record is None
            or record["legacy_method_id"] != method_id
            or record["source_sha256"] != RANDOM_NATIVE_METHODS[method_id]
            or record["strategy_version"] != row.get("strategy_version")
        ):
            raise CatalogBuildError(
                "random-native evidence leaves the frozen 221 universe"
            )
        record.update(
            {
                "candidate_k_semantics": "NOT_APPLICABLE_NO_CANDIDATE_K",
                "combination_count_semantics": (
                    "NOT_APPLICABLE_NO_STRATEGY_COMBINATION_COUNT"
                ),
                "native_ticket_semantics": (
                    "FROZEN_FACTORY_RANDOM_NATIVE_3_TICKETS_WITH_VERSIONED_SEED"
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen factory parity and 2148 causal executions completed; "
                    "the first draw is explicitly closed without a prior cutoff; "
                    f"compact evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_FACTORY_BET_ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )
    if seen != set(RANDOM_NATIVE_METHODS):
        raise CatalogBuildError("random-native evidence omits a frozen method")
    return evidence_sha256


def _apply_history_native_batch_evidence(
    records: list[dict[str, object]],
    evidence_path: Path,
) -> str:
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        evidence.get("evidence_schema_version")
        != HISTORY_NATIVE_EVIDENCE_SCHEMA_VERSION
    ):
        raise CatalogBuildError("history-native evidence schema is unsupported")
    before = evidence.get("source_database_sha256_before")
    after = evidence.get("source_database_sha256_after")
    if (
        type(before) is not str
        or _SHA256.fullmatch(before) is None
        or after != before
    ):
        raise CatalogBuildError(
            "history-native evidence does not prove an unchanged source DB"
        )
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
    ):
        value = evidence.get(key)
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise CatalogBuildError(f"history-native evidence {key} is invalid")
    if (
        evidence.get("constructor") != "strategy_preserving_20_ticket/v1"
        or evidence.get("history_native_protocol") != HISTORY_NATIVE_PROTOCOL
        or evidence.get("target_draw_count") != 2149
    ):
        raise CatalogBuildError("history-native execution contract changed")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogBuildError("history-native evidence strategies are missing")
    rows = cast(list[object], rows_raw)
    if len(rows) != len(HISTORY_NATIVE_METHODS):
        raise CatalogBuildError(
            "history-native evidence must contain exactly four strategies"
        )
    record_by_id = {
        cast(str, record["strategy_id"]): record for record in records
    }
    seen: set[str] = set()
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogBuildError(
                f"history-native evidence strategies[{index}] is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = _required_text(
            row,
            "legacy_method_id",
            context=f"history-native evidence strategies[{index}]",
        )
        if method_id in seen or method_id not in HISTORY_NATIVE_METHODS:
            raise CatalogBuildError("history-native method identity is invalid")
        seen.add(method_id)
        source_sha256, success_count, native_count, closed_counts = (
            HISTORY_NATIVE_METHODS[method_id]
        )
        if (
            row.get("source_sha256") != source_sha256
            or row.get("successful_execution_count") != success_count
            or row.get("native_ticket_count") != native_count
            or row.get("closed_status_counts") != closed_counts
        ):
            raise CatalogBuildError(
                "history-native execution semantics changed"
            )
        catalog_id = _required_text(
            row,
            "catalog_strategy_id",
            context=f"history-native evidence strategies[{index}]",
        )
        record = record_by_id.get(catalog_id)
        if (
            record is None
            or record["legacy_method_id"] != method_id
            or record["source_sha256"] != source_sha256
            or record["strategy_version"] != row.get("strategy_version")
        ):
            raise CatalogBuildError(
                "history-native evidence leaves the frozen 221 universe"
            )
        record.update(
            {
                "candidate_k_semantics": "NOT_APPLICABLE_NO_CANDIDATE_K",
                "combination_count_semantics": (
                    "NOT_APPLICABLE_NO_STRATEGY_COMBINATION_COUNT"
                ),
                "native_ticket_semantics": (
                    f"FROZEN_HISTORY_NATIVE_SOURCE_{native_count}_TICKETS"
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    f"Frozen-source parity completed with {success_count} causal "
                    f"executions and explicit closed-result preservation; compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_ENTRYPOINT_ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )
    if seen != set(HISTORY_NATIVE_METHODS):
        raise CatalogBuildError("history-native evidence omits a frozen method")
    return evidence_sha256


def _apply_static_disposition_evidence(
    records: list[dict[str, object]],
    evidence_path: Path,
    *,
    frozen_source_commit: str,
) -> str:
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        evidence.get("evidence_schema_version")
        != STATIC_DISPOSITION_EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit") != frozen_source_commit
        or evidence.get("review_policy_version")
        != "BIG_LOTTO_FROZEN_SOURCE_EXECUTABILITY_REVIEW_V1"
    ):
        raise CatalogBuildError("static disposition evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogBuildError("static dispositions are missing")
    rows = cast(list[object], rows_raw)
    if len(rows) != len(STATIC_CLOSED_METHODS):
        raise CatalogBuildError(
            "static disposition evidence must contain the expected methods"
        )
    record_by_method = {
        cast(str, record["legacy_method_id"]): record for record in records
    }
    seen: set[str] = set()
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogBuildError(
                f"static dispositions[{index}] is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = _required_text(
            row,
            "legacy_method_id",
            context=f"static dispositions[{index}]",
        )
        if method_id in seen or method_id not in STATIC_CLOSED_METHODS:
            raise CatalogBuildError("static disposition method is invalid")
        seen.add(method_id)
        source_sha256, reason_code = STATIC_CLOSED_METHODS[method_id]
        facts = row.get("decisive_source_facts")
        status_reason = _required_text(
            row,
            "status_reason",
            context=f"static dispositions[{index}]",
        )
        record = record_by_method.get(method_id)
        if (
            row.get("reproduction_status") != "CLOSED_UNEXECUTABLE"
            or row.get("source_sha256") != source_sha256
            or row.get("reason_code") != reason_code
            or not isinstance(facts, list)
            or len(cast(list[object], facts)) < 2
            or record is None
            or record["source_sha256"] != source_sha256
        ):
            raise CatalogBuildError("static disposition contract changed")
        record.update(
            {
                "candidate_k_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "combination_count_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "native_ticket_semantics": (
                    "NO_EXECUTABLE_BIG_LOTTO_NATIVE_TICKETS"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{status_reason} Frozen-source disposition evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "ticket_order_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "unranked_reason": f"CLOSED_UNEXECUTABLE:{reason_code}",
            }
        )
    if seen != set(STATIC_CLOSED_METHODS):
        raise CatalogBuildError("static disposition evidence omits a method")
    return evidence_sha256


def build_catalog(
    p541b_path: Path,
    p541b_r2_path: Path,
    replay_batch_evidence_path: Path,
    random_native_evidence_path: Path,
    history_native_evidence_path: Path,
    static_disposition_evidence_path: Path,
) -> dict[str, object]:
    historical_document, historical_sha256 = _read_json(p541b_path)
    r2_document, r2_sha256 = _read_json(p541b_r2_path)

    historical_rows_value = historical_document.get("method_classification_records")
    r2_rows_value = r2_document.get("method_classification_records")
    if not isinstance(historical_rows_value, list) or not isinstance(r2_rows_value, list):
        raise CatalogBuildError("both audit inputs must contain method_classification_records")
    historical_rows_raw = cast(list[object], historical_rows_value)
    r2_rows_raw = cast(list[object], r2_rows_value)

    historical_rows: list[dict[str, Any]] = []
    for candidate in historical_rows_raw:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("is_actual_prediction_method") is True:
            historical_rows.append(row)
    if len(historical_rows) != EXPECTED_METHOD_COUNT:
        raise CatalogBuildError(
            f"P541B actual-method count is {len(historical_rows)}, "
            f"expected {EXPECTED_METHOD_COUNT}"
        )

    r2_by_id: dict[str, dict[str, Any]] = {}
    for candidate in r2_rows_raw:
        if not isinstance(candidate, dict):
            raise CatalogBuildError("P541B-R2 contains a non-object record")
        row = cast(dict[str, Any], candidate)
        method_id = _required_text(row, "method_id", context="P541B-R2 record")
        if method_id in r2_by_id:
            raise CatalogBuildError(f"duplicate P541B-R2 method ID: {method_id}")
        r2_by_id[method_id] = row

    frozen_source_commit = _required_text(
        r2_document,
        "frozen_source_commit",
        context="P541B-R2 document",
    )
    records = [
        _build_record(
            row,
            r2_by_id[_required_text(row, "method_id", context="P541B record")],
            frozen_source_commit=frozen_source_commit,
        )
        for row in historical_rows
    ]
    records.sort(key=lambda row: cast(str, row["legacy_method_id"]))
    if len({record["strategy_id"] for record in records}) != EXPECTED_METHOD_COUNT:
        raise CatalogBuildError("derived strategy IDs are not unique")
    replay_evidence_sha256 = _apply_replay_batch_evidence(
        records,
        replay_batch_evidence_path,
    )
    random_native_evidence_sha256 = _apply_random_native_batch_evidence(
        records,
        random_native_evidence_path,
    )
    history_native_evidence_sha256 = _apply_history_native_batch_evidence(
        records,
        history_native_evidence_path,
    )
    static_disposition_evidence_sha256 = _apply_static_disposition_evidence(
        records,
        static_disposition_evidence_path,
        frozen_source_commit=frozen_source_commit,
    )

    status_counts = {
        status: sum(record["reproduction_status"] == status for record in records)
        for status in (
            "BACKTESTED",
            "CLOSED_UNEXECUTABLE",
            "DUPLICATE_ALIAS",
            "OWNER_DECISION_REQUIRED",
        )
    }
    record_by_method_id = {
        cast(str, record["legacy_method_id"]): record for record in records
    }
    first_batch_mappings: list[dict[str, object]] = []
    for registry_strategy_id in FIRST_BATCH_REPLAY_STRATEGY_IDS:
        exact_method_id = FIRST_BATCH_EXACT_METHOD_MAPPINGS.get(
            registry_strategy_id
        )
        if exact_method_id is not None:
            mapped_record = record_by_method_id.get(exact_method_id)
            if mapped_record is None:
                raise CatalogBuildError(
                    f"first-batch exact mapping leaves 221 universe: {exact_method_id}"
                )
            first_batch_mappings.append(
                {
                    "catalog_strategy_id": mapped_record["strategy_id"],
                    "legacy_method_id": exact_method_id,
                    "mapping_reason": (
                        "The frozen registry/P93 implementation imports this exact "
                        "audited source and symbol for native ticket generation."
                    ),
                    "mapping_status": "EXACT_SOURCE_SYMBOL_MATCH",
                    "registry_strategy_id": registry_strategy_id,
                }
            )
        else:
            first_batch_mappings.append(
                {
                    "mapping_reason": FIRST_BATCH_MAPPING_REASONS[
                        registry_strategy_id
                    ],
                    "mapping_status": "OWNER_DECISION_REQUIRED",
                    "registry_strategy_id": registry_strategy_id,
                }
            )
    document: dict[str, object] = {
        "catalog_policy_version": CATALOG_POLICY_VERSION,
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "expected_total_strategy_count": EXPECTED_METHOD_COUNT,
        "first_batch": {
            "declared_strategy_count": len(FIRST_BATCH_REPLAY_STRATEGY_IDS),
            "exact_mapping_count": len(FIRST_BATCH_EXACT_METHOD_MAPPINGS),
            "is_full_universe": False,
            "mappings": first_batch_mappings,
            "owner_decision_required_mapping_count": (
                len(FIRST_BATCH_REPLAY_STRATEGY_IDS)
                - len(FIRST_BATCH_EXACT_METHOD_MAPPINGS)
            ),
            "strategy_ids": list(FIRST_BATCH_REPLAY_STRATEGY_IDS),
        },
        "frozen_source_commit": frozen_source_commit,
        "full_universe_complete": False,
        "lottery_type": "BIG_LOTTO",
        "records": records,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_artifacts": [
            {
                "artifact_name": p541b_path.name,
                "artifact_sha256": historical_sha256,
                "evidence_role": "ACTUAL_METHOD_CLASSIFICATION",
            },
            {
                "artifact_name": p541b_r2_path.name,
                "artifact_sha256": r2_sha256,
                "evidence_role": "FROZEN_SOURCE_IDENTITY_AND_SAFETY",
            },
            {
                "artifact_name": replay_batch_evidence_path.name,
                "artifact_sha256": replay_evidence_sha256,
                "evidence_role": "EXACT_REPLAY_BATCH_CAUSAL_BACKTEST",
            },
            {
                "artifact_name": random_native_evidence_path.name,
                "artifact_sha256": random_native_evidence_sha256,
                "evidence_role": "RANDOM_NATIVE_BATCH_CAUSAL_BACKTEST",
            },
            {
                "artifact_name": history_native_evidence_path.name,
                "artifact_sha256": history_native_evidence_sha256,
                "evidence_role": "HISTORY_NATIVE_BATCH_CAUSAL_BACKTEST",
            },
            {
                "artifact_name": static_disposition_evidence_path.name,
                "artifact_sha256": static_disposition_evidence_sha256,
                "evidence_role": "STATIC_CLOSED_DISPOSITION_REVIEW",
            },
        ],
        "status_counts": status_counts,
    }
    document["catalog_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p541b", type=Path, required=True)
    parser.add_argument("--p541b-r2", type=Path, required=True)
    parser.add_argument("--replay-batch-evidence", type=Path, required=True)
    parser.add_argument("--random-native-evidence", type=Path, required=True)
    parser.add_argument("--history-native-evidence", type=Path, required=True)
    parser.add_argument("--static-disposition-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = build_catalog(
        args.p541b,
        args.p541b_r2,
        args.replay_batch_evidence,
        args.random_native_evidence,
        args.history_native_evidence,
        args.static_disposition_evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
