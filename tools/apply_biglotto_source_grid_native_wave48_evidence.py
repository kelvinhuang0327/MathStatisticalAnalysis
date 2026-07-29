#!/usr/bin/env python3
"""Apply wave-48 source-grid evidence to the full strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_grid_native_portfolios_wave48 import (
    FROZEN_SOURCE_COMMIT,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE48_METHOD,
    OPTIMIZE_5BET_ALIAS_METHOD_ID,
    OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = "ec260faa8b40d9cf8435ee2b6c460be1ec5ba500ac27968923fce26b869c1bfe"
BASE_CATALOG_FILE_SHA256 = "d09eb4876f0dbaa47c8d8fc83e9e5fcd9926ab3a4d14f3cd632a402410d43f4d"
EXPECTED_EVIDENCE_SHA256 = "a07f4af5037d7b172425855f96411999307161b2f8bf5d59f2971b59149f4cae"
EXPECTED_EVIDENCE_FILE_SHA256 = (
    "c24bd6976d5311066fc0c5a8ccf3f58b41b6897c6cdb9ff8adc3c868dcfd2d02"
)
EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE48_EVIDENCE_V1"
EVIDENCE_ARTIFACT_NAME = "biglotto_legacy_source_grid_native_wave48_evidence_v1.json"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 106,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 10,
    "OWNER_DECISION_REQUIRED": 40,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 108,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 37,
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-48 evidence is inconsistent."""


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


def _validate_evidence(
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("evidence_sha256") != EXPECTED_EVIDENCE_SHA256
        or evidence.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256") != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256") != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "d8538162672b1048719fdef97c6700f8dd380f58695e534a4424985ad961495a"
        or evidence.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or evidence.get("final_progress")
        != {
            "backtested_count": 108,
            "closed_count": 65,
            "duplicate_alias_count": 11,
            "owner_decision_required_count": 37,
            "reproduced_count": 108,
            "total_strategy_count": 221,
            "uncompleted_count": 37,
        }
    ):
        raise CatalogOverlayError("wave-48 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-48 strategy evidence changed")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS or method_id in by_method:
            raise CatalogOverlayError("wave-48 strategy method set changed")
        typed_method_id = cast(str, method_id)
        expected_ok = EXPECTED_OK_COUNTS[typed_method_id]
        expected_native_count = NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD[
            typed_method_id
        ]
        expected_configuration_count = (
            SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD[typed_method_id]
        )
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD[typed_method_id]
            or row.get("ok_execution_count") != expected_ok
            or row.get("closed_execution_count") != EXPECTED_CLOSED_COUNTS[typed_method_id]
            or row.get("candidate_k_distribution") != {"49": expected_ok}
            or row.get("native_ticket_count_distribution")
            != {str(expected_native_count): expected_ok}
            or row.get("source_configuration_count") != expected_configuration_count
            or row.get("source_configuration_count_distribution")
            != {str(expected_configuration_count): expected_ok}
            or row.get("source_candidate_k_values") != [49]
            or row.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(f"wave-48 strategy evidence changed: {method_id}")
        by_method[typed_method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS):
        raise CatalogOverlayError("wave-48 strategy evidence is incomplete")
    alias = evidence.get("alias_disposition")
    if not isinstance(alias, dict):
        raise CatalogOverlayError("wave-48 alias evidence changed")
    typed_alias = cast(dict[str, Any], alias)
    if (
        typed_alias.get("alias_method_id") != OPTIMIZE_5BET_ALIAS_METHOD_ID
        or typed_alias.get("canonical_method_id") != OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID
        or typed_alias.get("overlapping_causal_output_case_count") != 1500
        or typed_alias.get("output_mismatch_count") != 0
        or typed_alias.get("status") != "DUPLICATE_ALIAS"
    ):
        raise CatalogOverlayError("wave-48 alias proof changed")
    return by_method, typed_alias


def apply_wave48_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay two BACKTESTED rows and one DUPLICATE_ALIAS row."""

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
    evidence_by_method, alias_evidence = _validate_evidence(evidence)
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256") != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError("wave-48 evidence leaves the validated universe")
        configuration_count = SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD[
            method_id
        ]
        native_count = NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
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
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen CPython/NumPy/SciPy execution was captured "
                    "in a checksummed full-prefix causal ledger. This method "
                    f"completed {EXPECTED_OK_COUNTS[method_id]} causal executions "
                    f"and retained {EXPECTED_CLOSED_COUNTS[method_id]} explicit "
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
    alias_record = record_by_method.get(OPTIMIZE_5BET_ALIAS_METHOD_ID)
    canonical_record = record_by_method.get(OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID)
    if (
        alias_record is None
        or canonical_record is None
        or alias_record.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or canonical_record.get("reproduction_status") != "BACKTESTED"
        or alias_record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD[OPTIMIZE_5BET_ALIAS_METHOD_ID]
        or alias_evidence.get("alias_strategy_id") != alias_record.get("strategy_id")
        or alias_evidence.get("canonical_strategy_id")
        != canonical_record.get("strategy_id")
    ):
        raise CatalogOverlayError("wave-48 duplicate alias leaves the validated universe")
    alias_record.update(
        {
            "candidate_k_semantics": "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS",
            "combination_count_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "duplicate_alias_target": canonical_record["strategy_id"],
            "native_ticket_semantics": "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO",
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                "The frozen five-ticket portfolio matched "
                "standard_ts3_5bet.py at all 1,500 overlapping causal "
                "cutoffs with zero positional ticket mismatches. Ranking it "
                "independently would double count the same selection method. "
                f"Compact evidence SHA-256 is {EXPECTED_EVIDENCE_SHA256}."
            ),
            "ticket_duplicate_semantics": "INHERITED_FROM_DUPLICATE_ALIAS_TARGET",
            "ticket_order_semantics": "INHERITED_FROM_DUPLICATE_ALIAS_TARGET",
            "unranked_reason": "DUPLICATE_ALIAS",
        }
    )
    source_artifacts = cast(list[object], catalog.get("source_artifacts", []))
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": EXPECTED_EVIDENCE_SHA256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE48_ENHANCEMENT_AND_DIRECTION_GRID_"
                "CAUSAL_BACKTEST_AND_STANDARD_TS3_ALIAS_PROOF"
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
    catalog = apply_wave48_evidence(
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
