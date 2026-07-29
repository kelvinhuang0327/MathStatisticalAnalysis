#!/usr/bin/env python3
"""Apply wave-28 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave28 import (
    DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "39c5335761c4dbf9e655d2c5aa003617d076386ded36b4172b307889e50aaf5e"
)
BASE_CATALOG_FILE_SHA256 = (
    "d8b28cc828c3656b9640db2fd134e3ede82f5f30b5c49e9be454ca09f0ce9ed9"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE28_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "3181285d28709e348d1865f4bb213b32047385ba87b837bb0191870ff89bd706"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave28_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 67,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 111,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 70,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 108,
}
EXPECTED_NATIVE_TICKET_DISTRIBUTIONS = {
    "tools/predict_biglotto_115000007_2bets.py": {"2": 2148},
    "tools/predict_biglotto_7bets.py": {
        "4": 8,
        "5": 24,
        "6": 677,
        "7": 1439,
    },
    "tools/predict_biglotto_elite7.py": {"7": 2148},
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-28 evidence is inconsistent."""


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
        != "f4b3da9356ed502c649d4f2f32352b78f5d16fcc5cdaac8d8f52321ff2926682"
    ):
        raise CatalogOverlayError("wave-28 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 3:
        raise CatalogOverlayError(
            "wave-28 evidence must contain three strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-28 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-28 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            or row.get("declared_native_ticket_count")
            != DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                method_id
            ]
            or row.get("native_ticket_count_distribution")
            != EXPECTED_NATIVE_TICKET_DISTRIBUTIONS[method_id]
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                method_id
            ]
            or row.get("closed_execution_count") != 1
            or row.get("ok_execution_count") != 2148
            or not isinstance(row.get("candidate_k_distribution"), dict)
            or not isinstance(
                row.get("native_duplicate_ticket_count_distribution"),
                dict,
            )
            or not isinstance(
                row.get("closed_reason_code_distribution"),
                dict,
            )
        ):
            raise CatalogOverlayError(
                "wave-28 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 210
        or parity.get("closed_parity_case_count") != 0
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 3
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 5
    ):
        raise CatalogOverlayError("wave-28 parity evidence changed")
    return by_method


def apply_wave28_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay three validated BACKTESTED dispositions."""

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
        raise CatalogOverlayError("wave-28 evidence file changed")
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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
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
                "wave-28 evidence leaves the validated universe"
            )
        ticket_distribution = cast(
            dict[str, int],
            evidence_row["native_ticket_count_distribution"],
        )
        duplicate_distribution = cast(
            dict[str, int],
            evidence_row[
                "native_duplicate_ticket_count_distribution"
            ],
        )
        candidate_distribution = cast(
            dict[str, int],
            evidence_row["candidate_k_distribution"],
        )
        record.update(
            {
                "candidate_k_semantics": (
                    "EXECUTION_SPECIFIC_FROZEN_WEIGHTED_CANDIDATE_POOL_"
                    "LENGTH_OR_NULL_FOR_ELITE_DISTINCT_FROM_NATIVE_TICKETS"
                ),
                "combination_count_semantics": (
                    "FROZEN_SOURCE_PREDICTOR_CONFIGURATION_COUNT_DISTINCT_"
                    "FROM_CANDIDATE_K_NATIVE_TICKETS_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen high-level AST parity covered 210 cases with "
                    "all candidate-pool, dynamic kill-number, positional "
                    "ticket, newest-first database-order, source-tail "
                    "window, and duplicate-ticket outputs matching. "
                    "2148 causal executions completed and the first target "
                    "remained explicitly closed for insufficient history. "
                    f"Candidate-K distribution is {candidate_distribution}; "
                    f"native ticket-count distribution is "
                    f"{ticket_distribution}; duplicate distribution is "
                    f"{duplicate_distribution}. Compact evidence SHA-256 "
                    f"is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_TICKETS_INCLUDING_"
                    "ELITE_CONSENSUS_AND_ANY_SOURCE_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER_BEFORE_"
                    "ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
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
                "SOURCE_NATIVE_WAVE28_WEIGHTED_AND_ELITE7_CAUSAL_BACKTEST"
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
    catalog = apply_wave28_evidence(
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
