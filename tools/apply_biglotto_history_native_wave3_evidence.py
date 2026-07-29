"""Apply the third history-native evidence wave to a validated base catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios_wave3 import (
    CORE_SATELLITE_METHOD_ID,
    HISTORY_NATIVE_WAVE3_PROTOCOL,
    NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD,
    NEGATIVE_SELECTION_METHOD_ID,
    QUANTUM_RANDOM_METHOD_ID,
    SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE3_METHOD,
    SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE3_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE3_METHOD,
    SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD,
    SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "e12aabce6146eaa691d44f5bb86d0ba0dbd89e32328dfb98623c57c800779c0f"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HISTORY_NATIVE_WAVE3_EVIDENCE_V1"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 12,
    "CLOSED_UNEXECUTABLE": 6,
    "DUPLICATE_ALIAS": 3,
    "OWNER_DECISION_REQUIRED": 200,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 15,
    "CLOSED_UNEXECUTABLE": 6,
    "DUPLICATE_ALIAS": 3,
    "OWNER_DECISION_REQUIRED": 197,
}
EXPECTED_NATIVE_COUNT_VALUES = {
    CORE_SATELLITE_METHOD_ID: [12],
    NEGATIVE_SELECTION_METHOD_ID: [7, 8],
    QUANTUM_RANDOM_METHOD_ID: [8],
}
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The base catalog or wave-3 evidence violates the overlay contract."""


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
    return cast(dict[str, Any], parsed), hashlib.sha256(raw).hexdigest()


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_digest(value: object, context: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CatalogOverlayError(f"{context} must be a lowercase SHA-256")


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("history_native_protocol")
        != HISTORY_NATIVE_WAVE3_PROTOCOL
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
        != "NOT_APPLICABLE_NO_SINGLE_TOP_K_CANDIDATE_CONTRACT"
        or evidence.get("combination_count_semantics")
        != "EXECUTION_LEVEL_SOURCE_ENTRYPOINT_OR_MODE_COUNT"
    ):
        raise CatalogOverlayError("wave-3 evidence identity changed")
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
        "source_database_sha256_before",
    ):
        _validate_digest(evidence.get(key), f"evidence {key}")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-3 evidence must contain exactly three strategies"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 3:
        raise CatalogOverlayError(
            "wave-3 evidence must contain exactly three strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                f"wave-3 strategies[{index}] must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id in by_method
            or method_id not in SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS
        ):
            raise CatalogOverlayError(
                "wave-3 strategy identity is invalid"
            )
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD[method_id]
            or row.get("successful_execution_count") != 2148
            or row.get("closed_status_counts")
            != {"CLOSED_INSUFFICIENT_HISTORY": 1}
            or row.get("native_ticket_count_values")
            != EXPECTED_NATIVE_COUNT_VALUES[method_id]
            or row.get("native_ticket_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                method_id
            ]
            or row.get("candidate_k") is not None
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE3_METHOD[
                method_id
            ]
            or row.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                    method_id
                ]
            )
            or row.get("source_candidate_ticket_counts")
            != list(
                SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                    method_id
                ]
            )
        ):
            raise CatalogOverlayError(
                "wave-3 execution semantics changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS):
        raise CatalogOverlayError("wave-3 evidence omits a frozen method")
    return by_method


def _combination_semantics(method_id: str) -> str:
    count = SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE3_METHOD[
        method_id
    ]
    if count is None:
        return "NOT_APPLICABLE_SINGLE_SOURCE_ENTRYPOINT"
    return (
        f"FROZEN_SOURCE_COMBINATION_COUNT_{count}_DISTINCT_FROM_NATIVE_TICKETS"
    )


def apply_wave3_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, _raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version") != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
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

    for method_id in SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256")
            != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD[method_id]
            or record.get("strategy_id")
            != evidence_row.get("catalog_strategy_id")
            or record.get("strategy_version")
            != evidence_row.get("strategy_version")
        ):
            raise CatalogOverlayError(
                "wave-3 evidence leaves the validated base universe"
            )
        record.update(
            {
                "candidate_k_semantics": (
                    "NOT_APPLICABLE_NO_SINGLE_TOP_K_CANDIDATE_CONTRACT"
                ),
                "combination_count_semantics": _combination_semantics(
                    method_id
                ),
                "native_ticket_semantics": (
                    "FROZEN_HISTORY_NATIVE_SOURCE_"
                    + NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen-source call-order parity and 2148 causal "
                    "executions completed with explicit source combination "
                    "semantics and one insufficient-history closed result; "
                    f"compact evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES_ACROSS_SOURCE_COMBINATIONS"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_ENTRYPOINT_AND_BET_ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
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
                "HISTORY_NATIVE_WAVE3_BATCH_CAUSAL_BACKTEST"
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
    catalog = apply_wave3_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
