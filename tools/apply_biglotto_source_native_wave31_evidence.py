#!/usr/bin/env python3
"""Apply wave-31 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave31 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD,
    RADICAL_BACKTEST_METHOD_ID,
    RADICAL_PREDICT_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "1b1b66eb3821d48ab0df9e94460fae3dfd69da104fd3532b3ff2bbebd1c56b7e"
)
BASE_CATALOG_FILE_SHA256 = (
    "f9a0b7f07b949d1156deaa9b5a52ed44124df8e4f583901241bd7f6d097d3014"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE31_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "4faa3f7f4b6b2fcd647b268557259748a67f1a61d3f2340282203d31413fb97a"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave31_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 73,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 105,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 75,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 103,
}
EXPECTED_DUPLICATE_DISTRIBUTION_BY_METHOD = {
    RADICAL_PREDICT_METHOD_ID: {"0": 2116},
    RADICAL_BACKTEST_METHOD_ID: {"0": 1961, "1": 9},
}
EXPECTED_OK_COUNT_BY_METHOD = {
    RADICAL_PREDICT_METHOD_ID: 2116,
    RADICAL_BACKTEST_METHOD_ID: 1970,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-31 evidence is inconsistent."""


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
        != "2aef79b614b1c5205fe3d6de3958c1463647de0d5d27e2f72cc688d08431a8ce"
    ):
        raise CatalogOverlayError("wave-31 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 2:
        raise CatalogOverlayError(
            "wave-31 evidence must contain two strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-31 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-31 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[method_id]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or row.get("native_duplicate_ticket_count_distribution")
            != EXPECTED_DUPLICATE_DISTRIBUTION_BY_METHOD[method_id]
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or row.get("closed_execution_count")
            != 2149 - EXPECTED_OK_COUNT_BY_METHOD[method_id]
            or row.get("ok_execution_count")
            != EXPECTED_OK_COUNT_BY_METHOD[method_id]
            or row.get("candidate_k_distribution")
            != {"null": EXPECTED_OK_COUNT_BY_METHOD[method_id]}
            or not isinstance(
                row.get("closed_reason_code_distribution"),
                dict,
            )
            or row.get("random_protocol") != "NONE_DETERMINISTIC"
        ):
            raise CatalogOverlayError(
                "wave-31 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 130
        or parity.get("closed_parity_case_count") != 61
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 2
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 4
        or not isinstance(
            parity.get("frozen_source_behavior_facts"), dict
        )
    ):
        raise CatalogOverlayError("wave-31 parity evidence changed")
    return by_method


def apply_wave31_evidence(
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
        raise CatalogOverlayError("wave-31 evidence file changed")
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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS:
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
                "wave-31 evidence leaves the validated universe"
            )
        record.update(
            {
                "candidate_k_semantics": (
                    "NULL_NO_COMBINATORIAL_CANDIDATE_K_WHILE_FROZEN_"
                    "SOURCE_TOP12_POOLS_ARE_RETAINED_SEPARATELY"
                ),
                "combination_count_semantics": (
                    "FROZEN_COMPONENT_OR_GAP_CONFIGURATION_COUNT_"
                    "DISTINCT_FROM_NATIVE_TICKETS_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen class-method AST parity covered 130 cases and "
                    "preserved recent-first history, gap exclusions, "
                    "weighted Counter insertion ties, candidate pools, "
                    "the live method's hardcoded 115000007 filter and "
                    "low-sum shift, and the rolling method's 300-draw "
                    "window plus 50-draw warm-up. Source outputs with fewer "
                    "than six numbers remain CLOSED_INVALID_OUTPUT instead "
                    "of being filled. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_FROZEN_POSITIONAL_GAP_TICKET_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "LIVE_SINGLE_GAP_01_19_OR_ROLLING_GAP_01_19_THEN_"
                    "GAP_20_29_SOURCE_ORDER"
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
                "SOURCE_NATIVE_WAVE31_RADICAL_GAP_CAUSAL_BACKTEST"
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
    catalog = apply_wave31_evidence(
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
