#!/usr/bin/env python3
"""Apply wave-30 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave30 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "dca1c838cc8d9003e51ff84d66d68248e44fe48f9b7fbde1ee77ba9d093f0c3f"
)
BASE_CATALOG_FILE_SHA256 = (
    "72275a74a5459e7f5fd27c8d1185e54d988abaf257e872bb0e47c256eb24ec70"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE30_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "4041ca30bc3998612b24bc38039c4c2572c87b7c372cdb665c9364d55d22a8df"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave30_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 72,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 106,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 73,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 105,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "0": 1219,
    "1": 769,
    "2": 134,
    "3": 11,
    "4": 11,
    "5": 2,
    "6": 2,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-30 evidence is inconsistent."""


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
        != "fb5499b38e138eb9cda76aaf872aa513340057ed49217ca1dd3fd9dd3358ca7b"
    ):
        raise CatalogOverlayError("wave-30 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 1:
        raise CatalogOverlayError(
            "wave-30 evidence must contain one strategy"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-30 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-30 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or row.get("native_duplicate_ticket_count_distribution")
            != EXPECTED_DUPLICATE_DISTRIBUTION
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or row.get("closed_execution_count") != 1
            or row.get("ok_execution_count") != 2148
            or row.get("candidate_k_distribution") != {"null": 2148}
            or not isinstance(
                row.get("closed_reason_code_distribution"),
                dict,
            )
            or row.get("numpy_version_pin") != "numpy==1.26.2"
            or row.get("numpy_scalar_exp_reproduction")
            != "SCALAR_NUMPY_EXP_REPRODUCED_WITH_IEEE754_MATH_EXP"
            or not isinstance(row.get("random_protocol"), str)
        ):
            raise CatalogOverlayError(
                "wave-30 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 65
        or parity.get("closed_parity_case_count") != 0
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 5
        or parity.get("frozen_numpy_version_pin") != "numpy==1.26.2"
        or not isinstance(
            parity.get("numpy_scalar_exp_instrumentation_facts"), dict
        )
    ):
        raise CatalogOverlayError("wave-30 parity evidence changed")
    return by_method


def apply_wave30_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay one validated BACKTESTED disposition."""

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
        raise CatalogOverlayError("wave-30 evidence file changed")
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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS:
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
                "wave-30 evidence leaves the validated universe"
            )
        record.update(
            {
                "candidate_k_semantics": (
                    "NULL_NO_FROZEN_SOURCE_CANDIDATE_POOL_DISTINCT_FROM_"
                    "NATIVE_TICKETS"
                ),
                "combination_count_semantics": (
                    "TEN_FROZEN_METHOD_POSITIONS_"
                    "DISTINCT_FROM_NATIVE_TICKETS_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Instrumented frozen high-level AST parity captured "
                    "65 portfolios after all ten source tickets were "
                    "constructed and before outcome scoring. All seven "
                    "chronological Unified engine positions, scalar EWMA "
                    "lambda positions 0.03/0.10/0.15, frozen NumPy 1.26.2 "
                    "scalar-exp semantics, reseeded statistical calls, "
                    "stable ties, ticket order, and duplicates were "
                    "preserved. 2148 causal "
                    "executions completed and the first target remained "
                    "explicitly closed for insufficient history. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_TEN_FROZEN_POSITIONS_INCLUDING_UNIFIED_"
                    "ENGINE_AND_EWMA_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "SEVEN_FROZEN_ENGINE_METHOD_POSITIONS_THEN_EWMA_"
                    "LAMBDA_0.03_0.10_0.15"
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
                "SOURCE_NATIVE_WAVE30_TEN_BET_CAUSAL_BACKTEST"
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
    catalog = apply_wave30_evidence(
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
