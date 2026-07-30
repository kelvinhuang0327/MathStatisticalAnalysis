#!/usr/bin/env python3
"""Apply wave-29 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave29 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "d35ea79ecccbc89dbe8584b85f7d9f621d075cabda769df94880fd31ad97e079"
)
BASE_CATALOG_FILE_SHA256 = (
    "aa9f313aac761aef4d9dcd542b0e6ee31629107174717d16b95aac9904ffd852"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE29_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "f243b727b44214ea0c15b1382c41a3d22892b6e28611f005048a808659931cf4"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave29_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 70,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 108,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 72,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 106,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "0": 1515,
    "1": 424,
    "2": 137,
    "3": 31,
    "4": 41,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-29 evidence is inconsistent."""


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


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "721f9c3a72f83846a924ae0d09e0c47017597fd6745a139c69a55bfbe0092e2b"
    ):
        raise CatalogOverlayError("wave-29 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 2:
        raise CatalogOverlayError(
            "wave-29 evidence must contain two strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-29 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-29 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or row.get("native_duplicate_ticket_count_distribution")
            != EXPECTED_DUPLICATE_DISTRIBUTION
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or row.get("closed_execution_count") != 1
            or row.get("ok_execution_count") != 2148
            or row.get("candidate_k_distribution") != {"null": 2148}
            or not isinstance(
                row.get("closed_reason_code_distribution"),
                dict,
            )
            or not isinstance(
                row.get("all_base_methods_failed_behavior"),
                str,
            )
        ):
            raise CatalogOverlayError(
                "wave-29 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 130
        or parity.get("closed_parity_case_count") != 0
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 2
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 4
        or not isinstance(
            parity.get("frozen_source_behavior_facts"),
            dict,
        )
    ):
        raise CatalogOverlayError("wave-29 parity evidence changed")
    return by_method


def apply_wave29_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay two validated BACKTESTED dispositions."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version")
        != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError("base catalog identity changed")
    if evidence_sha256 != EXPECTED_EVIDENCE_SHA256:
        raise CatalogOverlayError("wave-29 evidence file changed")
    evidence_by_method = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "base catalog record is invalid"
            )
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-29 evidence leaves the validated universe"
            )
        failure_behavior = cast(
            str,
            evidence_row["all_base_methods_failed_behavior"],
        )
        record.update(
            {
                "candidate_k_semantics": (
                    "NULL_NO_FROZEN_SOURCE_CANDIDATE_POOL_DISTINCT_FROM_"
                    "NATIVE_TICKETS"
                ),
                "combination_count_semantics": (
                    "SIX_FROZEN_RECENT_WINDOW_PREDICTOR_CONFIGURATIONS_"
                    "DISTINCT_FROM_NATIVE_TICKETS_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Instrumented frozen high-level AST parity captured "
                    "130 portfolios after source construction and before "
                    "outcome scoring. All six chronological recent-window "
                    "Unified tickets, unweighted consensus position, "
                    "Counter insertion ties, ticket duplicates, and the "
                    f"distinct all-base-methods-failed behavior "
                    f"{failure_behavior} were preserved. 2148 causal "
                    "executions completed and the first target remained "
                    "explicitly closed for insufficient history. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_SEVEN_FROZEN_POSITIONS_INCLUDING_BASE_"
                    "AND_CONSENSUS_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "SIX_FROZEN_RECENT_WINDOW_CONFIG_POSITIONS_THEN_"
                    "UNWEIGHTED_CONSENSUS_POSITION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )

    source_artifacts = cast(
        list[object],
        catalog.get("source_artifacts", []),
    )
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE29_ROLLING_ELITE7_CAUSAL_BACKTEST"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], record)["reproduction_status"])
        for record in records
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
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    catalog = apply_wave29_evidence(
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
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
