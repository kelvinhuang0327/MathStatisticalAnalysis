#!/usr/bin/env python3
"""Apply wave-24 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave24 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE24_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "4bf91cc16f300afa0eb40236fff1f7f791eacbc1d5ca462772dc795411a3dff4"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE24_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "e83363e8b67e6ecc0139d8ff3de7709e0ba4261d131c8b24eea3ba75500d647e"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave24_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 48,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 131,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 54,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 125,
}
EXPECTED_OK_COUNTS = {
    "lottery_api/models/biglotto_2bet_final.py": 2148,
    "lottery_api/models/biglotto_3bet_optimizer.py": 2147,
    "tools/test_asm.py": 2148,
    "tools/test_dcb.py": 2148,
    "tools/test_4bet_dcb.py": 2134,
    "tools/test_ecp.py": 2147,
}
EXPECTED_CLOSED_COUNTS = {
    method_id: 2149 - ok_count
    for method_id, ok_count in EXPECTED_OK_COUNTS.items()
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-24 evidence is inconsistent."""


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
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "a5fceb854cab476d39e4a339b3d2e7c4fc1da2d36e552f4eacd3b82e34ba6436"
    ):
        raise CatalogOverlayError("wave-24 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 6:
        raise CatalogOverlayError(
            "wave-24 evidence must contain six strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-24 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-24 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD[
                method_id
            ]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD[
                method_id
            ]
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD[
                method_id
            ]
            or row.get("closed_execution_count")
            != EXPECTED_CLOSED_COUNTS[method_id]
            or row.get("ok_execution_count")
            != EXPECTED_OK_COUNTS[method_id]
            or row.get("native_duplicate_ticket_count_distribution")
            != {"0": EXPECTED_OK_COUNTS[method_id]}
            or not isinstance(row.get("candidate_k_distribution"), dict)
            or not isinstance(row.get("execution_status_counts"), dict)
            or not isinstance(row.get("kill_count_distribution"), dict)
        ):
            raise CatalogOverlayError(
                "wave-24 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 198
        or parity.get("closed_parity_case_count") != 16
        or parity.get("status") != "PASS"
        or parity.get("upstream_unified_parity_evidence_sha256")
        != "8064df37f44f695699e87071a4ffe2cb7a816405862f73d37fa14e038f73edd5"
        or not isinstance(parity.get("source_artifacts"), list)
        or not isinstance(parity.get("support_artifacts"), list)
    ):
        raise CatalogOverlayError("wave-24 parity evidence changed")
    return by_method


def apply_wave24_evidence(
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
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError("base catalog identity changed")
    if evidence_sha256 != EXPECTED_EVIDENCE_SHA256:
        raise CatalogOverlayError("wave-24 evidence file changed")
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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS:
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
                "wave-24 evidence leaves the validated universe"
            )
        ok_count = EXPECTED_OK_COUNTS[method_id]
        closed_count = EXPECTED_CLOSED_COUNTS[method_id]
        record.update(
            {
                "candidate_k_semantics": (
                    "EXECUTION_SPECIFIC_FROZEN_RANKED_NUMBER_POOL_LENGTH_"
                    "DISTINCT_FROM_NATIVE_TICKET_COUNT"
                ),
                "combination_count_semantics": (
                    "FROZEN_WEIGHTED_UNIFIED_PREDICTOR_MEMBER_COUNT_"
                    "DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKETS_AND_"
                    "ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE24_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen AST class parity covered all first 30 causal "
                    "cutoffs plus 50, 150, and 2148 draws, preserving "
                    "weighted Counter order, dynamic entropy kill numbers, "
                    "candidate-pool order, native slices, and explicit "
                    "invalid-short-ticket closures. "
                    f"{ok_count} causal executions completed and "
                    f"{closed_count} closures remained explicit. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_TICKETS_INCLUDING_"
                    "ANY_SOURCE_DUPLICATES"
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
                "SOURCE_NATIVE_WAVE24_WEIGHTED_CANDIDATE_POOL_"
                "CAUSAL_BACKTEST"
            ),
        }
    )
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
    catalog = apply_wave24_evidence(
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
