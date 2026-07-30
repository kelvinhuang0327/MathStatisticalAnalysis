#!/usr/bin/env python3
"""Apply wave-20 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave20 import (
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD,
    ZONE_BALANCE_500_METHOD_ID,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "9d5bbcc15bc584b3bbda51bf38ad49a5e0e93b7f30ff38bfc88d82a67d9c8261"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE20_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "7d9c179f7bc1b8fd51379ebc90b219442bef41014b5cb896ad9487dbaefa5abc"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 136,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 44,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 135,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-20 evidence is inconsistent."""


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
) -> dict[str, Any]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "5da4175b54fc75ee0b484a549acfef7eeb52b4381e08a80a812f38db9200e143"
    ):
        raise CatalogOverlayError("wave-20 evidence identity changed")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-20 evidence must contain one strategy"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-20 evidence must contain one strategy"
        )
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id")
        != ZONE_BALANCE_500_METHOD_ID
        or strategy.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
            ZONE_BALANCE_500_METHOD_ID
        ]
        or strategy.get("native_ticket_count") != 5
        or strategy.get("combination_count") != 4
        or strategy.get("candidate_k") is not None
        or strategy.get("native_duplicate_ticket_count_values")
        != [1, 2, 3, 4]
        or strategy.get("ok_execution_count") != 2148
    ):
        raise CatalogOverlayError("wave-20 strategy identity changed")
    parity_raw = evidence.get("parity")
    if not isinstance(parity_raw, dict):
        raise CatalogOverlayError("wave-20 parity evidence changed")
    parity = cast(dict[str, Any], parity_raw)
    if (
        parity.get("case_count") != 4
        or parity.get("status") != "PASS"
        or not isinstance(parity.get("source_artifact"), dict)
        or not isinstance(parity.get("support_artifact"), dict)
    ):
        raise CatalogOverlayError("wave-20 parity evidence changed")
    return strategy


def apply_wave20_evidence(
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
        raise CatalogOverlayError("wave-20 evidence file changed")
    strategy = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
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

    record = record_by_method.get(ZONE_BALANCE_500_METHOD_ID)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != strategy.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-20 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_NO_PRE_TICKET_CANDIDATE_K"
            ),
            "combination_count_semantics": (
                "FOUR_FROZEN_WINDOW_CONFIGURATIONS_DISTINCT_FROM_"
                "FIVE_POSITIONAL_NATIVE_OUTPUT_TICKETS"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                    ZONE_BALANCE_500_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen-method parity passed four causal history "
                "cutoffs with the UnifiedPredictionEngine support "
                "source pinned. The main 500-window recommendation and "
                "the printed 100/200/300/500 comparison outputs were "
                "preserved as five positional tickets, including the "
                "repeated 500-window position. 2148 causal executions "
                "completed and one insufficient-history closure "
                "remained explicit. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "PRESERVE_ALL_POSITIONAL_DUPLICATES_INCLUDING_MAIN_"
                "500_AND_COMPARISON_500"
            ),
            "ticket_order_semantics": (
                "FROZEN_MAIN_500_THEN_COMPARISON_100_200_300_500_"
                "ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
            ),
            "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
        }
    )

    source_artifacts_raw = catalog.get("source_artifacts")
    if not isinstance(source_artifacts_raw, list):
        raise CatalogOverlayError("base source artifacts changed")
    source_artifacts = cast(list[object], source_artifacts_raw)
    source_artifacts.append(
        {
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE20_ZONE_BALANCE_WINDOWS_CAUSAL_"
                "BACKTEST"
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
    catalog = apply_wave20_evidence(
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
