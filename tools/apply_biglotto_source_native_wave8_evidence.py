#!/usr/bin/env python3
"""Apply the eighth source-native evidence wave to a validated catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave8 import (
    CLUSTER_ENHANCEMENTS_METHOD_ID,
    DYNAMIC_FREQUENCY_METHOD_ID,
    GEMINI_PHASE2_METHOD_ID,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE8_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD,
    OPTIMIZE_THIRD_BET_METHOD_ID,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE8_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE8_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE8_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE8_METHOD,
    SOURCE_NATIVE_WAVE8_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "969a3af0bff008521a148fd1229b67e05a23b14492f0888d62806e4168875ff8"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE8_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 27,
    "CLOSED_UNEXECUTABLE": 21,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 169,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 31,
    "CLOSED_UNEXECUTABLE": 21,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 165,
}
EXPECTED_SUCCESS_COUNTS = {
    GEMINI_PHASE2_METHOD_ID: 2049,
    DYNAMIC_FREQUENCY_METHOD_ID: 1949,
    CLUSTER_ENHANCEMENTS_METHOD_ID: 169,
    OPTIMIZE_THIRD_BET_METHOD_ID: 2148,
}
EXPECTED_CLOSED_COUNTS = {
    GEMINI_PHASE2_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
    },
    DYNAMIC_FREQUENCY_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 200,
    },
    CLUSTER_ENHANCEMENTS_METHOD_ID: {
        "CLOSED_EXECUTION_ERROR": 1880,
        "CLOSED_INSUFFICIENT_HISTORY": 100,
    },
    OPTIMIZE_THIRD_BET_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
    },
}
EXPECTED_NATIVE_COUNT_VALUES = {
    GEMINI_PHASE2_METHOD_ID: [7],
    DYNAMIC_FREQUENCY_METHOD_ID: [1],
    CLUSTER_ENHANCEMENTS_METHOD_ID: [14, 15],
    OPTIMIZE_THIRD_BET_METHOD_ID: [1],
}
EXPECTED_CANDIDATE_K_VALUES = {
    GEMINI_PHASE2_METHOD_ID: [],
    DYNAMIC_FREQUENCY_METHOD_ID: [],
    CLUSTER_ENHANCEMENTS_METHOD_ID: [],
    OPTIMIZE_THIRD_BET_METHOD_ID: [20, 21],
}
EXPECTED_CANDIDATE_COMBINATION_VALUES = {
    GEMINI_PHASE2_METHOD_ID: [],
    DYNAMIC_FREQUENCY_METHOD_ID: [],
    CLUSTER_ENHANCEMENTS_METHOD_ID: [],
    OPTIMIZE_THIRD_BET_METHOD_ID: [38760, 54264],
}
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The base catalog or wave-8 evidence violates the overlay contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return (
        cast(dict[str, Any], parsed),
        hashlib.sha256(raw).hexdigest(),
    )


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_digest(value: object, context: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CatalogOverlayError(
            f"{context} must be a lowercase SHA-256"
        )


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE8_PROTOCOL
        or evidence.get("constructor")
        != "strategy_preserving_20_ticket/v1"
        or evidence.get("backtest_policy_version")
        != "BIG_LOTTO_CAUSAL_ORDERED_20_PREFIX_5_10_15_20_V1"
        or evidence.get("target_draw_count") != 2149
        or evidence.get("catalog_sha256_before_status_overlay")
        != BASE_CATALOG_SHA256
        or evidence.get("source_database_sha256_before")
        != evidence.get("source_database_sha256_after")
        or evidence.get("candidate_k_semantics")
        != (
            "EXECUTION_LEVEL_SEARCH_POOL_SIZE_DISTINCT_FROM_NATIVE_"
            "TICKET_AND_SOURCE_CONFIGURATION_COUNTS"
        )
        or evidence.get("combination_count_semantics")
        != (
            "SOURCE_ENTRYPOINT_METHOD_OR_PARAMETER_CONFIGURATION_COUNT"
        )
    ):
        raise CatalogOverlayError("wave-8 evidence identity changed")
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
        "source_database_sha256_before",
    ):
        _validate_digest(evidence.get(key), f"evidence {key}")
    reproducibility_raw = evidence.get("reproducibility")
    parity_raw = evidence.get("frozen_source_parity")
    if (
        not isinstance(reproducibility_raw, dict)
        or not isinstance(parity_raw, dict)
    ):
        raise CatalogOverlayError(
            "wave-8 reproducibility/parity evidence changed"
        )
    reproducibility = cast(dict[str, Any], reproducibility_raw)
    parity = cast(dict[str, Any], parity_raw)
    if (
        reproducibility.get("input_byte_identical") is not True
        or reproducibility.get("report_directory_byte_identical")
        is not True
        or reproducibility.get("repeat_input_raw_sha256")
        != evidence.get("input_raw_sha256")
        or reproducibility.get("repeat_report_file_sha256")
        != evidence.get("report_file_sha256")
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 12
        or parity.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError(
            "wave-8 reproducibility/parity evidence changed"
        )
    _validate_digest(
        parity.get("artifact_sha256"),
        "frozen-source parity artifact",
    )
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-8 evidence must contain four strategies"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 4:
        raise CatalogOverlayError(
            "wave-8 evidence must contain four strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-8 evidence strategy is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id in by_method
            or method_id not in SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS
        ):
            raise CatalogOverlayError(
                "wave-8 strategy identity is invalid"
            )
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[method_id]
            or row.get("successful_execution_count")
            != EXPECTED_SUCCESS_COUNTS[method_id]
            or row.get("closed_status_counts")
            != EXPECTED_CLOSED_COUNTS[method_id]
            or row.get("minimum_history_draws")
            != MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE8_METHOD[method_id]
            or row.get("native_ticket_count_values")
            != EXPECTED_NATIVE_COUNT_VALUES[method_id]
            or row.get("native_ticket_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD[
                method_id
            ]
            or row.get("random_protocol")
            != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE8_METHOD[method_id]
            or row.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE8_METHOD[
                method_id
            ]
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE8_METHOD[
                method_id
            ]
            or row.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE8_METHOD[
                    method_id
                ]
            )
            or row.get("candidate_k_values")
            != EXPECTED_CANDIDATE_K_VALUES[method_id]
            or row.get("candidate_combination_count_values")
            != EXPECTED_CANDIDATE_COMBINATION_VALUES[method_id]
        ):
            raise CatalogOverlayError(
                f"wave-8 strategy evidence changed: {method_id}"
            )
        by_method[method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS):
        raise CatalogOverlayError(
            "wave-8 evidence method coverage changed"
        )
    return by_method


def _candidate_semantics(method_id: str) -> str:
    if method_id == OPTIMIZE_THIRD_BET_METHOD_ID:
        return (
            "EXECUTION_LEVEL_FROZEN_TOP_20_PLUS_UP_TO_3_WEAK_ZONE_"
            "SEARCH_POOL_K_VALUES_20_OR_21_DISTINCT_FROM_NATIVE_TICKET"
        )
    return "NOT_APPLICABLE_NO_PRE_TICKET_CANDIDATE_K"


def _combination_semantics(method_id: str) -> str:
    if method_id == GEMINI_PHASE2_METHOD_ID:
        return (
            "FROZEN_SOURCE_METHOD_CONFIGURATION_COUNT_7_DISTINCT_"
            "FROM_NATIVE_TICKET_COUNT"
        )
    if method_id == DYNAMIC_FREQUENCY_METHOD_ID:
        return (
            "FROZEN_SOURCE_WINDOW_CONFIGURATION_COUNT_5_DISTINCT_"
            "FROM_NATIVE_TICKET_COUNT"
        )
    if method_id == CLUSTER_ENHANCEMENTS_METHOD_ID:
        return (
            "FROZEN_SOURCE_STRATEGY_CONFIGURATION_COUNT_8_DISTINCT_"
            "FROM_FLATTENED_NATIVE_TICKET_COUNT"
        )
    return (
        "FROZEN_SOURCE_ENTRYPOINT_COUNT_1_DISTINCT_FROM_CANDIDATE_"
        "COMBINATION_SEARCH_COUNT"
    )


def apply_wave8_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, _raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version")
        != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise CatalogOverlayError("base catalog identity changed")
    _validate_digest(evidence_sha256, "evidence file digest")
    evidence_by_method = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    records = cast(list[object], records_raw)
    if len(records) != 221:
        raise CatalogOverlayError("base catalog records changed")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = row

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[method_id]
            or record.get("strategy_id")
            != evidence_row.get("strategy_id")
            or record.get("strategy_version")
            != evidence_row.get("strategy_version")
        ):
            raise CatalogOverlayError(
                "wave-8 evidence leaves the validated base universe"
            )
        closed = EXPECTED_CLOSED_COUNTS[method_id]
        invalid_note = (
            " The 1,880 frozen non-six-number outputs remain explicit "
            "execution closures and are reflected in coverage."
            if method_id == CLUSTER_ENHANCEMENTS_METHOD_ID
            else ""
        )
        record.update(
            {
                "candidate_k_semantics": (
                    _candidate_semantics(method_id)
                ),
                "combination_count_semantics": (
                    _combination_semantics(method_id)
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen-commit function parity passed 12 "
                    f"cross-method cases; {EXPECTED_SUCCESS_COUNTS[method_id]} "
                    "causal executions completed while closures remained "
                    f"explicit as {closed}.{invalid_note} Compact evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES_ACROSS_"
                    "SOURCE_CONFIGURATIONS"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_CONFIGURATION_AND_BET_LOOP_ORDER_"
                    "BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
            }
        )

    artifacts_raw = catalog.get("source_artifacts")
    if not isinstance(artifacts_raw, list):
        raise CatalogOverlayError("base source artifacts changed")
    cast(list[object], artifacts_raw).append(
        {
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE8_BATCH_CAUSAL_BACKTEST"
            ),
        }
    )
    catalog["status_counts"] = EXPECTED_OUTPUT_STATUS_COUNTS
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = apply_wave8_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
