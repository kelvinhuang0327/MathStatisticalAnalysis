#!/usr/bin/env python3
"""Apply wave-23 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave23 import (
    FIVE_ME_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS,
    TME_METHOD_ID,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "a9049b4dfe6167731f256fae70e6d3fa4af09ecd48147b3a2a859d1501236838"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE23_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "397ff15d0691c85ed4c21a331e5148fba60126501bd632246219a331781469d5"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 46,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 133,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 48,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 131,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-23 evidence is inconsistent."""


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
        != "51f21c411eeaa0b796e6c1bc7e6e3e7660294afbca105fac8d1288f56923ce3a"
    ):
        raise CatalogOverlayError("wave-23 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 2:
        raise CatalogOverlayError(
            "wave-23 evidence must contain two strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-23 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-23 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id, expected_count in (
        (FIVE_ME_METHOD_ID, 5),
        (TME_METHOD_ID, 3),
    ):
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[
                method_id
            ]
            or row.get("native_ticket_count") != expected_count
            or row.get("combination_count") != expected_count
            or row.get("candidate_k") is not None
            or row.get("closed_execution_count") != 1
            or row.get("ok_execution_count") != 2148
            or row.get("markov_order_distribution")
            != {"1": 49, "2": 100, "3": 1999}
            or row.get("statistical_candidate_count_distribution")
            != {"20": 2148}
        ):
            raise CatalogOverlayError(
                "wave-23 strategy identity changed"
            )
    if by_method[FIVE_ME_METHOD_ID].get(
        "native_duplicate_ticket_count_distribution"
    ) != {"0": 2139, "1": 9} or by_method[TME_METHOD_ID].get(
        "native_duplicate_ticket_count_distribution"
    ) != {"0": 2148}:
        raise CatalogOverlayError(
            "wave-23 duplicate semantics changed"
        )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 12
        or parity.get("status") != "PASS"
        or not isinstance(parity.get("source_artifacts"), list)
        or not isinstance(parity.get("support_artifact"), dict)
    ):
        raise CatalogOverlayError("wave-23 parity evidence changed")
    return by_method


def apply_wave23_evidence(
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
        raise CatalogOverlayError("wave-23 evidence file changed")
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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS:
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
                "wave-23 evidence leaves the validated universe"
            )
        method_count = cast(int, evidence_row["combination_count"])
        position_words = "FIVE" if method_count == 5 else "THREE"
        record.update(
            {
                "candidate_k_semantics": (
                    "NOT_APPLICABLE_NO_DECLARED_PRE_TICKET_CANDIDATE_K"
                ),
                "combination_count_semantics": (
                    f"{position_words}_FROZEN_UNIFIED_METHODS_DISTINCT_"
                    f"FROM_{position_words}_POSITIONAL_NATIVE_TICKETS"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen AST statement parity passed six pinned causal "
                    "history cutoffs for this positional UnifiedPrediction"
                    "Engine composition, including adaptive Markov order, "
                    "pinned BIG_LOTTO configuration, and the source's "
                    "history-length statistical seed. 2148 causal "
                    "executions completed and one insufficient-history "
                    "closure remained explicit. Compact evidence SHA-256 "
                    f"is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_POSITIONAL_METHOD_TICKETS_WHEN_TWO_"
                    "UNIFIED_METHODS_EMIT_THE_SAME_TICKET"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_DECLARED_METHOD_ORDER_BEFORE_"
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
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE23_5ME_TME_CAUSAL_BACKTEST"
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
    catalog = apply_wave23_evidence(
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
