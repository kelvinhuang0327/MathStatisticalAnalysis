#!/usr/bin/env python3
"""Apply wave-54 source-grid evidence to the full strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_grid_native_portfolios_wave54 import (
    FROZEN_SOURCE_COMMIT,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE54_METHOD,
    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = "f7203b3a3951f56f09d8f635998697d8903aa3d345854626e9ac44be7916a1aa"
BASE_CATALOG_FILE_SHA256 = "6c2f6f1addcf3545aad655957331c79edceba0695009c8db861bdb0479862224"
EXPECTED_EVIDENCE_SHA256 = "e37f7074d5f7385077c16d7dc7ef28680f087341d0b55f6eb398d29e0701fee3"
EXPECTED_EVIDENCE_FILE_SHA256 = (
    "b8f41fec1687b7798d3b9d01ca73c586df8fc17a1f39021dd948368382a6721a"
)
EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE54_EVIDENCE_V1"
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_grid_native_wave54_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 119,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 26,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 121,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 24,
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-54 evidence is inconsistent."""


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
    reduced = {key: value for key, value in document.items() if key != "catalog_sha256"}
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_evidence(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("evidence_sha256") != EXPECTED_EVIDENCE_SHA256
        or evidence.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256") != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256") != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "a8508a240024bc0faff6f343233449577a8abe606acca5d3199c71e00366bf15"
        or evidence.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or evidence.get("final_progress")
        != {
            "backtested_count": 121,
            "closed_count": 65,
            "duplicate_alias_count": 11,
            "owner_decision_required_count": 24,
            "reproduced_count": 121,
            "total_strategy_count": 221,
            "uncompleted_count": 24,
        }
    ):
        raise CatalogOverlayError("wave-54 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-54 strategy evidence changed")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            method_id not in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
            or method_id in by_method
        ):
            raise CatalogOverlayError("wave-54 strategy method set changed")
        typed_method_id = cast(str, method_id)
        expected_ok = EXPECTED_OK_COUNTS[typed_method_id]
        expected_native_count = NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD[
            typed_method_id
        ]
        expected_configuration_count = (
            SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD[typed_method_id]
        )
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE54_METHOD[typed_method_id]
            or row.get("ok_execution_count") != expected_ok
            or row.get("closed_execution_count")
            != EXPECTED_CLOSED_COUNTS[typed_method_id]
            or row.get("candidate_k_distribution") != {"49": expected_ok}
            or row.get("native_ticket_count_distribution")
            != {str(expected_native_count): expected_ok}
            or row.get("source_configuration_count") != expected_configuration_count
            or row.get("source_configuration_count_distribution")
            != {str(expected_configuration_count): expected_ok}
            or row.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE54_METHOD[
                    typed_method_id
                ]
            )
            or row.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
            or row.get("randomness_used")
            is not RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE54_METHOD[typed_method_id]
            or row.get("randomness_reproduction")
            != "EXACT_FROZEN_RUNTIME_LEDGER"
        ):
            raise CatalogOverlayError(
                f"wave-54 strategy evidence changed: {method_id}"
            )
        by_method[typed_method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS):
        raise CatalogOverlayError("wave-54 strategy evidence is incomplete")
    return by_method


def apply_wave54_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay two BACKTESTED rows."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_file_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version") != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence_file_sha256 != EXPECTED_EVIDENCE_FILE_SHA256
    ):
        raise CatalogOverlayError("base catalog or evidence changed")
    evidence_by_method = _validate_evidence(evidence)
    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("base catalog record is invalid")
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256") != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError("wave-54 evidence leaves the validated universe")
        configuration_count = SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD[
            method_id
        ]
        native_count = NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
        record.update(
            {
                "candidate_k_semantics": (
                    "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                    "DISTINCT_FROM_NATIVE_TICKET_COUNT_SOURCE_"
                    "CONFIGURATION_COUNT_AND_ORDERED_20"
                ),
                "combination_count_semantics": (
                    "FROZEN_SOURCE_LOCAL_CONFIGURATION_COUNT_"
                    f"{configuration_count}_DISTINCT_FROM_CANDIDATE_K_"
                    "NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE54_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen CPython/NumPy/SciPy selection logic was "
                    "captured in a checksummed full-prefix causal ledger. "
                    f"This method completed {EXPECTED_OK_COUNTS[method_id]} "
                    "causal executions and retained "
                    f"{EXPECTED_CLOSED_COUNTS[method_id]} explicit "
                    "insufficient-history closures. Candidate-K, "
                    f"{configuration_count} source configuration(s), "
                    f"{native_count} native positional ticket(s), duplicates, "
                    "and ordered-20 remain separate. Compact evidence SHA-256 "
                    f"is {EXPECTED_EVIDENCE_SHA256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_NATIVE_TICKETS_"
                    "INCLUDING_CROSS_CONFIGURATION_DUPLICATES_BEFORE_"
                    "CHECKSUMMED_ORDERED_20_DERIVATION"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_"
                    "ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )
    source_artifacts = cast(list[object], catalog.get("source_artifacts", []))
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": EXPECTED_EVIDENCE_SHA256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE54_CONSENSUS_AND_EVOLUTIONARY_GUM_"
                "CAUSAL_BACKTEST"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], item)["reproduction_status"])
        for item in records
    )
    if dict(status_counts) != EXPECTED_OUTPUT_STATUS_COUNTS:
        raise CatalogOverlayError("output status counts changed")
    catalog["status_counts"] = dict(EXPECTED_OUTPUT_STATUS_COUNTS)
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    catalog = apply_wave54_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    payload = _canonical_bytes(catalog) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "catalog_sha256": catalog["catalog_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(payload).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
