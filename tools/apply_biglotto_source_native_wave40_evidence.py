#!/usr/bin/env python3
"""Apply wave-40 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave40 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD,
    PORTFOLIO_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "9970c56da9efc613fb9d2b033bb613dc6d6124a9227458183b303b2a369c6141"
)
BASE_CATALOG_FILE_SHA256 = (
    "f013536b311d93ee2af19f9d6041701aebc3f4fd930e073b79e301147968ad0e"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE40_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "26db8ff17a7040b9f424026b131d06837f36d80d270e40c6f6cd594959677ca1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave40_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 74,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 79,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 73,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-40 evidence is inconsistent."""


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
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(document, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return (
        cast(dict[str, Any], document),
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
) -> dict[str, Any]:
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
        != "1103cc021d3cae176f3c070d6e1099ff51d8463d90aa6f0cd5bdeae36bf0b8e7"
    ):
        raise CatalogOverlayError("wave-40 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-40 evidence must contain one strategy"
        )
    row = cast(dict[str, Any], rows[0])
    if (
        row.get("legacy_method_id") != PORTFOLIO_METHOD_ID
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[
            PORTFOLIO_METHOD_ID
        ]
        or row.get("native_ticket_count_upper_bound")
        != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD[
            PORTFOLIO_METHOD_ID
        ]
        or row.get("native_ticket_count_distribution") != {"4": 2049}
        or row.get("native_duplicate_ticket_count_distribution")
        != {"0": 2049}
        or row.get("source_method_combination_count")
        != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD[
            PORTFOLIO_METHOD_ID
        ]
        or row.get("closed_execution_count") != 100
        or row.get("ok_execution_count") != 2049
        or row.get("candidate_k_distribution") != {"null": 2049}
        or row.get("random_protocol")
        != "NONE_DETERMINISTIC_NATIVE_SELECTION"
        or row.get("source_duplicate_suppression_distribution")
        != {
            "AUXILIARY_DUPLICATE_SUPPRESSED+"
            "WINDOW50_FILL_APPENDED": 2049
        }
    ):
        raise CatalogOverlayError("wave-40 strategy identity changed")
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 65
        or parity.get("status") != "PASS"
        or parity.get("parity_sha256")
        != "70d1e24808e9dba9df77d22a6f74aac2770c110228dba73c0c06832d5da63852"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 1
        or not isinstance(
            parity.get("frozen_source_behavior_facts"), dict
        )
    ):
        raise CatalogOverlayError("wave-40 parity evidence changed")
    return row


def apply_wave40_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the validated wave-40 BACKTESTED disposition."""

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
        raise CatalogOverlayError("wave-40 evidence file changed")
    evidence_row = _validate_evidence(evidence)

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
    record = record_by_method.get(PORTFOLIO_METHOD_ID)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != evidence_row.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-40 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NULL_NO_COMBINATORIAL_CANDIDATE_K"
            ),
            "combination_count_semantics": (
                "FROZEN_THREE_SOURCE_PORTFOLIO_COMPONENTS_DISTINCT_"
                "FROM_NATIVE_TICKETS_AND_ORDERED_20"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD[
                    PORTFOLIO_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Frozen source and Cluster Pivot support parity covered "
                "65 causal histories and preserved the three core "
                "tickets, auxiliary exact-duplicate suppression, "
                "window-50 fill, and four-ticket cap. 2049 causal "
                "executions completed and 100 minimum-history closures "
                "remained explicit. The source's seeded random baseline "
                "is not part of native strategy selection. Compact "
                f"evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "PRESERVE_FROZEN_POST_SUPPRESSION_NATIVE_POSITIONS_"
                "AND_ANY_REMAINING_DUPLICATES"
            ),
            "ticket_order_semantics": (
                "THREE_CLUSTER_PIVOT_CORE_TICKETS_THEN_AUXILIARY_"
                "OR_WINDOW50_FILL_BEFORE_ORDERED_20"
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
                "SOURCE_NATIVE_WAVE40_CLUSTER_3_PLUS_1_CAUSAL_BACKTEST"
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
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    catalog = apply_wave40_evidence(
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
